# handlers/header/headers.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import yaml

from brainops.header.extract_yaml_header import extract_metadata, extract_yaml_header
from brainops.header.get_tags_and_summary import (
    get_summary_from_ollama,
    get_tags_from_ollama,
)
from brainops.header.header_utils import clean_yaml_spacing_in_file
from brainops.sql.get_linked.db_get_linked_data import get_note_linked_data
from brainops.sql.get_linked.db_get_linked_notes_utils import (
    get_category_and_subcategory_names,
    get_note_tags,
    get_synthesis_metadata,
)
from brainops.sql.notes.db_update_notes import (
    update_obsidian_note,
    update_obsidian_tags,
)
from brainops.utils.files import count_words, read_note_content, safe_write
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import sanitize_created, sanitize_yaml_title


@with_child_logger
def add_metadata_to_yaml(
    note_id: int,
    filepath: str | Path,
    tags: Optional[list[str]] = None,
    summary: Optional[str] = None,
    status: Optional[str] = None,
    synthesis_id: Optional[int] = None,
    *,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Ajoute ou met à jour l'entête YAML d'un fichier Markdown.

    - Lit d'abord YAML existant + DB pour valeurs de référence
    - Écrit un YAML propre (PyYAML), puis le corps d'origine
    """
    logger = ensure_logger(logger, __name__)
    path = Path(str(filepath)).expanduser().resolve().as_posix()
    try:
        logger.debug("[DEBUG] add_yaml : démarrage pour %s", path)

        # --- 1) Métadonnées existantes YAML
        yaml_meta = extract_metadata(path, logger=logger) or {}
        title_yaml = yaml_meta.get("title") or Path(path).stem
        source_yaml = yaml_meta.get("source") or ""
        author_yaml = yaml_meta.get("author") or (
            "ChatGPT" if "ChatGPT" in title_yaml else ""
        )
        project_yaml = yaml_meta.get("project") or ""
        created_yaml = sanitize_created(yaml_meta.get("created"), logger=logger)
        print(f"header created_yaml : {created_yaml}")

        # --- 2) Métadonnées DB
        data = get_note_linked_data(note_id, "note", logger=logger)
        if isinstance(data, dict):
            title = sanitize_yaml_title(data.get("title") or title_yaml)
            category_id = data.get("category_id")
            subcategory_id = data.get("subcategory_id")
            status = data.get("status") if status is None else status
            summary = data.get("summary") if summary is None else summary
            source = data.get("source") or source_yaml
            author = data.get("author") or author_yaml
            project = data.get("project") or project_yaml
            created = data.get("created_at") or created_yaml
        else:
            title = sanitize_yaml_title(title_yaml)
            category_id = None
            subcategory_id = None
            source = source_yaml
            author = author_yaml
            project = project_yaml
            created = created_yaml

        print(f"header created : {created}")

        # --- 3) Cat/Sub Noms (pour l'entête lisible)
        category_name, subcategory_name = get_category_and_subcategory_names(
            note_id, logger=logger
        )

        # --- 4) Si archive liée à une synthèse → sync champs principaux
        if synthesis_id:
            logger.debug(
                "[SYNC] Archive liée à la synthesis %s, synchronisation", synthesis_id
            )
            (
                title_syn,
                source_syn,
                author_syn,
                created_syn,
                _cat_id_syn,
                _subcat_id_syn,
            ) = get_synthesis_metadata(synthesis_id, logger=logger)
            title = title_syn or title
            source = source_syn or source
            author = author_syn or author
            created = created_syn or created

        # --- 5) Tags : priorité paramètre > DB > YAML existant
        tags_final: list[str] = []
        if tags:
            tags_final = list(tags)
        else:
            tags_db = get_note_tags(note_id, logger=logger)
            if tags_db:
                tags_final = tags_db
            else:
                tags_yaml = yaml_meta.get("tags") or []
                tags_final = list(tags_yaml) if isinstance(tags_yaml, list) else []

        # --- 6) Corps du fichier sans entête (on ne touche pas au contenu)
        content = read_note_content(path, logger=logger)
        lines = content.splitlines(True)  # conserve CR/LF
        yaml_start, yaml_end = -1, -1
        if lines and lines[0].strip() == "---":
            yaml_start = 0
            yaml_end = next(
                (
                    i
                    for i, line in enumerate(lines[1:], start=1)
                    if line.strip() == "---"
                ),
                -1,
            )
        body_lines = (
            lines[yaml_end + 1 :] if (yaml_start != -1 and yaml_end != -1) else lines
        )

        # --- 7) Construire l'objet YAML final
        # NB: PyYAML gère les chaînes multilignes (summary) en block style automatiquement si besoin.
        yaml_dict = {
            "title": title or Path(path).stem,
            "tags": [str(t).replace(" ", "_") for t in tags_final],
            "summary": (summary or "").strip(),
            "category": category_name or "",
            "sub category": subcategory_name or "",
            "created": str(created or ""),
            "last_modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source or "",
            "author": author or "",
            "status": status or "draft",
            "project": project or "",
        }

        # --- 8) YAML + écriture sécurisée
        yaml_text = yaml.safe_dump(
            yaml_dict, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        new_content = f"---\n{yaml_text}---\n" + "".join(body_lines)

        success = safe_write(path, content=new_content, logger=logger)
        if not success:
            logger.error("[main] Problème lors de l’écriture sécurisée de %s", path)
            return

        clean_yaml_spacing_in_file(path, logger=logger)
        logger.info("[INFO] Génération de l'entête terminée avec succès pour %s", path)

    except FileNotFoundError:
        logger.error("Erreur : fichier non trouvé %s", path)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ERREUR] Problème lors de l'ajout du YAML : %s", exc)


@with_child_logger
def make_properties(
    filepath: str | Path,
    note_id: int,
    status: str,
    *,
    logger: LoggerProtocol | None = None,
) -> bool:
    """
    Génère les entêtes et met à jour les métadonnées (DB + YAML).
    - Appelle l'IA pour tags + résumé
    - Met à jour DB (status, summary, word_count)
    - Écrit l'entête YAML consolidée
    """
    logger = ensure_logger(logger, __name__)
    path = Path(str(filepath)).expanduser().resolve().as_posix()

    logger.debug("[DEBUG] make_pro : Entrée de la fonction")
    try:
        # 1) Récupérer le contenu hors YAML (une lecture)
        _, content_str = extract_yaml_header(path, logger=logger)
        content = content_str

        # 2) Tags + résumé via IA
        logger.debug("[DEBUG] make_pro : Récupération des tags et résumé")
        tags = get_tags_from_ollama(content, note_id, logger=logger)
        summary = get_summary_from_ollama(content, note_id, logger=logger)

        # 3) DB: status + summary
        updates = {
            "status": status,
            "summary": summary,
        }
        update_obsidian_note(note_id, updates, logger=logger)
        update_obsidian_tags(note_id, tags, logger=logger)

        # 4) YAML
        logger.debug("[DEBUG] make_pro : Mise à jour du YAML")
        add_metadata_to_yaml(
            note_id, path, tags=tags, summary=summary, status=status, logger=logger
        )

        # 5) Recalcule word_count (post-YAML)
        nombre_mots_actuels = count_words(filepath=path, logger=logger)
        update_obsidian_note(
            note_id, {"word_count": nombre_mots_actuels}, logger=logger
        )

        logger.debug("[DEBUG] make_pro : Écriture réussie et fichier mis à jour")
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "[ERREUR] Problème lors de la mise à jour des métadonnées pour %s : %s",
            filepath,
            exc,
        )
        return False


@with_child_logger
def check_type_header(
    filepath: str | Path, *, logger: LoggerProtocol | None = None
) -> Optional[str]:
    """
    Retourne la valeur du champ YAML 'type' si présent, sinon None.
    """
    logger = ensure_logger(logger, __name__)
    try:
        content = read_note_content(
            Path(str(filepath)).expanduser().resolve().as_posix(), logger=logger
        )
        meta = extract_metadata(Path(filepath).as_posix(), logger=logger)
        return (
            str(meta.get("type"))
            if isinstance(meta, dict) and meta.get("type")
            else None
        )
    except FileNotFoundError as exc:
        logger.error(
            "Erreur lors du traitement de l'entête YAML pour %s : %s", filepath, exc
        )
        return None


@with_child_logger
def extract_category_and_subcategory(
    filepath: str | Path, *, logger: LoggerProtocol | None = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Lit l'entête YAML pour extraire la catégorie et la sous-catégorie.
    Gère les deux variantes: 'subcategory' et 'sub category'.
    """
    logger = ensure_logger(logger, __name__)
    try:
        meta = extract_metadata(
            Path(str(filepath)).expanduser().resolve().as_posix(), logger=logger
        )
        category = meta.get("category")
        # compat: certains fichiers ont 'sub category' (avec espace)
        subcategory = meta.get("subcategory", meta.get("sub category"))
        return (
            str(category) if category else None,
            str(subcategory) if subcategory else None,
        )
    except FileNotFoundError as exc:
        logger.error(
            "[ERREUR] Impossible de lire l'entête du fichier %s : %s", filepath, exc
        )
        return None, None
