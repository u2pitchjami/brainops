# process/update_note.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from brainops.header.extract_yaml_header import extract_note_metadata
from brainops.header.headers import add_metadata_to_yaml
from brainops.process_regen.regen_utils import regen_header, regen_synthese_from_archive
from brainops.sql.categs.db_categ_utils import categ_extract
from brainops.sql.folders.db_folder_utils import get_path_from_classification
from brainops.sql.get_linked.db_get_linked_data import get_note_linked_data
from brainops.sql.get_linked.db_get_linked_notes_utils import get_note_tags
from brainops.sql.notes.db_notes_utils import check_synthesis_and_trigger_archive
from brainops.sql.notes.db_update_notes import (
    update_obsidian_note,
    update_obsidian_tags,
)
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def update_note(
    note_id: int,
    dest_path: str | Path,
    src_path: str | Path | None = None,
    logger: Optional[LoggerProtocol] = None,
) -> Optional[int]:
    """
    Met à jour une note existante dans la base, y compris en cas de déplacement.

    - lit l’entête YAML (fallback avec valeurs DB si manquantes)
    - recalcule categ/subcateg depuis le path effectif
    - met à jour obsidian_notes
    - synchronise tags si nécessaire
    - applique des actions selon status (synthesis / regen / regen_header)
    """
    logger = ensure_logger(logger, __name__)
    dp = Path(dest_path)
    sp = Path(src_path) if src_path is not None else None
    logger.debug("[UPDATE_NOTE] note_id=%s | dest=%s | src=%s", note_id, dp, sp)

    categ_trigger = False

    try:
        # 1) Métadonnées depuis YAML
        meta = extract_note_metadata(str(dp), logger=logger)
        title_yaml = meta.get("title") or dp.stem.replace("_", " ").replace(":", " ")
        status_yaml = meta.get("status", "draft")
        tags_yaml = meta.get("tags", []) or []
        summary_yaml = meta.get("summary")
        source_yaml = meta.get("source")
        author_yaml = meta.get("author")
        project_yaml = meta.get("project")
        created_yaml = meta.get("created")
        print(f"created_yaml = {created_yaml}")

        # 2) Contexte catégories depuis le chemin
        base_folder = str(dp.parent)
        (
            category_name,
            subcategory_name,
            category_id_dest,
            subcategory_id_dest,
        ) = categ_extract(base_folder, logger=logger)
        logger.debug(
            "[UPDATE_NOTE] path→categ: %s / %s | ids: %s / %s",
            category_name,
            subcategory_name,
            category_id_dest,
            subcategory_id_dest,
        )

        # 3) Données actuelles DB
        data = get_note_linked_data(note_id, "note", logger=logger)
        if "error" in data:
            logger.error("[UPDATE_NOTE] Note %s introuvable en DB: %s", note_id, data)
            return None

        parent_id = data.get("parent_id")
        folder_id = data.get("folder_id")
        category_id_db = data.get("category_id")
        subcategory_id_db = data.get("subcategory_id")

        # 4) Valeurs finales (YAML prioritaire si présent)
        title = title_yaml or data.get("title")
        created = created_yaml or data.get("created_at")  # colonne DB = created_at
        print(f"created = {created}")
        author = author_yaml or data.get("author")
        source = source_yaml or data.get("source")
        project = project_yaml or data.get("project")
        status = status_yaml or data.get("status")
        summary = summary_yaml if summary_yaml is not None else data.get("summary")

        # 5) Si categ/subcateg diffèrent → retrouver folder_id cible
        category_id = category_id_db
        subcategory_id = subcategory_id_db
        if (category_id_db != category_id_dest) or (
            subcategory_id_db != subcategory_id_dest
        ):
            category_id = category_id_dest
            subcategory_id = subcategory_id_dest

            fp = get_path_from_classification(
                category_id, subcategory_id, logger=logger
            )
            if fp:
                folder_id = fp[0]  # (folder_id, path)
                logger.debug(
                    "[UPDATE_NOTE] Nouvelle classification → folder_id=%s (path=%s)",
                    folder_id,
                    fp[1],
                )
                categ_trigger = True
            else:
                logger.warning(
                    "[UPDATE_NOTE] Aucune folder pour categ_id=%s / subcat_id=%s",
                    category_id,
                    subcategory_id,
                )

        # 6) Update DB principal
        updates = {
            "file_path": str(dp),
            "title": title,
            "folder_id": folder_id,
            "category_id": category_id,
            "subcategory_id": subcategory_id,
            "status": status,
            "summary": summary,
            "source": source,
            "author": author,
            "project": project,
            "created_at": created,
        }
        update_obsidian_note(note_id, updates, logger=logger)

        # 7) Tags : sync si différents
        db_tags = get_note_tags(note_id, logger=logger)
        if tags_yaml != db_tags:
            update_obsidian_tags(note_id, tags_yaml, logger=logger)

        # 8) Si reclassement, rafraîchir l’entête (cat/subcat/titre/etc.)
        if categ_trigger:
            add_metadata_to_yaml(note_id, str(dp), logger=logger)

        logger.info("[UPDATE_NOTE] Note mise à jour: %s (id=%s)", dp, note_id)

        # 9) Actions selon status
        if status == "synthesis":
            logger.debug(
                "[UPDATE_NOTE] Post-action: check_synthesis_and_trigger_archive"
            )
            check_synthesis_and_trigger_archive(note_id, str(dp), logger=logger)
        elif status == "regen":
            logger.debug("[UPDATE_NOTE] Post-action: regen_synthese_from_archive")
            regen_synthese_from_archive(note_id, filepath=str(dp), logger=logger)
        elif status == "regen_header":
            logger.debug("[UPDATE_NOTE] Post-action: regen_header")
            regen_header(note_id, str(dp), parent_id, logger=logger)

        return note_id

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "[UPDATE_NOTE] Erreur lors de la mise à jour (id=%s, dest=%s): %s",
            note_id,
            dest_path,
            exc,
        )
        return None
