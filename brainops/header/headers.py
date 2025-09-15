"""
# handlers/header/headers.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from brainops.header.get_tags_and_summary import (
    get_summary_from_ollama,
    get_tags_from_ollama,
)
from brainops.io.note_reader import read_metadata_object, read_note_full
from brainops.io.note_writer import write_metadata_to_note
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.metadata import NoteMetadata
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
from brainops.utils.files import count_words
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import sanitize_created, sanitize_yaml_title


@with_child_logger
def add_metadata_to_yaml(
    note_id: int,
    filepath: str | Path,
    tags: list[str] | None = None,
    summary: str | None = None,
    status: str | None = None,
    synthesis_id: int | None = None,
    *,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Rassemble les métadonnées (YAML existant, DB, etc.) et réécrit une entête propre.
    """
    logger = ensure_logger(logger, __name__)
    path = Path(str(filepath)).expanduser().resolve().as_posix()
    try:
        logger.debug("[DEBUG] add_yaml : démarrage pour %s", path)

        # 1) Métadonnées existantes YAML
        meta_yaml = read_metadata_object(path, logger=logger)

        # 2) Métadonnées DB
        data = get_note_linked_data(note_id, "note", logger=logger)
        meta_db = NoteMetadata.from_db_dict(data) if isinstance(data, dict) else NoteMetadata()

        # 3) Métadonnées liées à une synthèse (écrasement)
        if synthesis_id:
            logger.debug("[SYNC] Archive liée à la synthesis %s, synchronisation", synthesis_id)
            (
                title_syn,
                source_syn,
                author_syn,
                created_syn,
                _cat_id_syn,
                _subcat_id_syn,
            ) = get_synthesis_metadata(synthesis_id, logger=logger)

            meta_syn = NoteMetadata(
                title=title_syn or "",
                source=source_syn or "",
                author=author_syn or "",
                created=str(created_syn) if created_syn else None,
            )
        else:
            meta_syn = NoteMetadata()

        # 4) Fusion dans l'ordre de priorité : Synthèse > DB > YAML
        meta_final = NoteMetadata.merge(meta_syn, meta_db, meta_yaml)

        # 5) Catégories
        cat, subcat = get_category_and_subcategory_names(note_id, logger=logger)
        meta_final.category = cat or meta_final.category
        meta_final.subcategory = subcat or meta_final.subcategory

        # 6) Tags
        if tags:
            meta_final.tags = tags
        else:
            tags_db = get_note_tags(note_id, logger=logger) or []
            meta_final.tags = tags_db or meta_yaml.tags

        # 7) Autres mises à jour (status / summary)
        if summary:
            meta_final.summary = summary.strip()
        if status:
            meta_final.status = status

        # 8) Normalisation
        meta_final.title = sanitize_yaml_title(meta_final.title or Path(path).stem)
        meta_final.created = sanitize_created(meta_final.created, logger=logger)

        # 9) Écriture dans le fichier
        success = write_metadata_to_note(path, meta_final, logger=logger)
        if not success:
            logger.error("[ERREUR] Échec de l’écriture sécurisée pour %s", path)
            return

        logger.info("[INFO] Écriture YAML terminée pour %s", path)

    except FileNotFoundError as exc:
        raise BrainOpsError("fichier non trouvé KO", code=ErrCode.METADATA, ctx={"note_id": note_id}) from exc
    except Exception as exc:
        raise BrainOpsError("ajout YAML KO", code=ErrCode.METADATA, ctx={"note_id": note_id}) from exc


@with_child_logger
def make_properties(
    filepath: str | Path,
    note_id: int,
    status: str,
    *,
    synthesis_id: int | None = None,  # gardé si tu synchronises ailleurs
    logger: LoggerProtocol | None = None,
) -> bool:
    """
    Génère/rafraîchit les propriétés d'une note :

    1) Lecture YAML + body 2) Appels IA (tags + summary) sur le body 3) Mise à jour DB (status, summary, tags,
    word_count) 4) Réécriture YAML consolidée via NoteMetadata

    Retourne True si tout s'est bien passé.
    """
    log = ensure_logger(logger, __name__)
    try:
        path = Path(str(filepath)).expanduser().resolve().as_posix()
        log.debug("[make_properties] start for %s (note_id=%s)", path, note_id)

        # 1) Lecture unique : métadonnées typées + corps
        meta_yaml, body = read_note_full(path, logger=log)

        # 2) Appels IA (sur body uniquement)
        log.debug("[make_properties] IA: tags + summary")
        tags = get_tags_from_ollama(body, note_id, logger=log) or []
        summary = (get_summary_from_ollama(body, note_id, logger=log) or "").strip()

        # 3) DB : status + summary + tags, puis word_count
        updates_note = {"status": status, "summary": summary}
        update_obsidian_note(note_id, updates_note, logger=log)
        update_obsidian_tags(note_id, tags, logger=log)

        # 4) Catégorisation lisible (noms) pour YAML
        cat_name, subcat_name = get_category_and_subcategory_names(note_id, logger=log)

        # 5) Construire l’objet NoteMetadata final (fusion YAML existant + ajouts)
        meta_final = NoteMetadata.merge(
            NoteMetadata(  # priorité aux nouvelles infos
                tags=tags,
                summary=summary,
                status=status,
                category=cat_name or "",
                subcategory=subcat_name or "",
                last_modified=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
            meta_yaml,  # puis l’existant
        )

        if not write_metadata_to_note(path, meta_final, logger=log):
            log.error("[make_properties] Échec écriture YAML pour %s", path)
            return False
        # 7) Recalcul word_count (après réécriture YAML)
        word_count = count_words(filepath=path, logger=log)
        update_obsidian_note(note_id, {"word_count": word_count}, logger=log)
        log.info("[make_properties] OK (id=%s, wc=%s)", note_id, word_count)
        return True
    except Exception as exc:  # pylint: disable=broad-except
        raise BrainOpsError("construction header KO", code=ErrCode.METADATA, ctx={"note_id": note_id}) from exc
