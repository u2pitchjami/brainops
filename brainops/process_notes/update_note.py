"""
# process/update_note.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.header.headers import add_metadata_to_yaml
from brainops.io.note_reader import read_metadata_object
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_notes.utils import detect_update_status_by_folder
from brainops.process_regen.regen_utils import regen_header, regen_synthese_from_archive
from brainops.sql.categs.db_extract_categ import categ_extract
from brainops.sql.folders.db_folder_utils import get_path_from_classification
from brainops.sql.get_linked.db_get_linked_data import get_note_linked_data
from brainops.sql.get_linked.db_get_linked_notes_utils import get_note_tags
from brainops.sql.notes.db_notes_utils import check_synthesis_and_trigger_archive
from brainops.sql.notes.db_update_notes import (
    update_obsidian_note,
    update_obsidian_tags,
)
from brainops.utils.files import wait_for_file
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def update_note(
    note_id: int,
    dest_path: str | Path,
    src_path: str | Path | None = None,
    logger: LoggerProtocol | None = None,
) -> None:
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

    if not wait_for_file(dp, logger=logger):
        logger.warning("⚠️ Fichier introuvable, skip : %s", dp)
        return

    categ_trigger = False

    try:
        # 1) Métadonnées depuis YAML
        meta = read_metadata_object(str(dp), logger=logger)
        logger.debug(f"meta : {meta}")
        title_yaml = meta.title or dp.stem.replace("_", " ").replace(":", " ")
        status_yaml = meta.status or "draft"
        tags_yaml = meta.tags or []
        summary_yaml = meta.summary
        source_yaml = meta.source
        author_yaml = meta.author
        project_yaml = meta.project
        created_yaml = meta.created

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
            raise BrainOpsError("Update note KO", code=ErrCode.DB, ctx={"data": data})

        if isinstance(data, dict):
            parent_id = data.get("parent_id")
            folder_id = data.get("folder_id")
            category_id_db = data.get("category_id") or None
            subcategory_id_db = data.get("subcategory_id") or None
            db_title = data.get("title")
            logger.info("[UPDATE_NOTE] db_title=%s", db_title)
            if "untitled" or "sans titre" in str(db_title).strip().lower():
                db_title = Path(dp).stem
                logger.info("[UPDATE_NOTE 2] db_title=%s", db_title)

            # 4) Valeurs finales (YAML prioritaire si présent)
            title = title_yaml or db_title
            created = created_yaml or data.get("created_at")  # colonne DB = created_at
            author = author_yaml or data.get("author")
            source = source_yaml or data.get("source")
            project = project_yaml or data.get("project")
            status_temp = status_yaml or data.get("status")
            summary = summary_yaml if summary_yaml is not None else data.get("summary")

            new_status = detect_update_status_by_folder(path=str(dp), logger=logger)

            def_status = new_status or status_temp

            # 5) Si categ/subcateg diffèrent → retrouver folder_id cible
            category_id = category_id_db
            subcategory_id = subcategory_id_db
            if (category_id_db != category_id_dest) or (subcategory_id_db != subcategory_id_dest):
                category_id = category_id_dest
                subcategory_id = subcategory_id_dest
                if category_id is not None:
                    fp = get_path_from_classification(category_id, subcategory_id, logger=logger)
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
            "status": def_status,
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
        if def_status == "synthesis":
            logger.debug("[UPDATE_NOTE] Post-action: check_synthesis_and_trigger_archive")
            check_synthesis_and_trigger_archive(note_id, str(dp), logger=logger)
        elif def_status == "regen":
            logger.debug("[UPDATE_NOTE] Post-action: regen_synthese_from_archive")
            regen_synthese_from_archive(note_id, filepath=str(dp))
        elif def_status == "regen_header":
            logger.debug("[UPDATE_NOTE] Post-action: regen_header")
            regen_header(note_id, str(dp), parent_id)

        return

    except Exception as exc:
        raise BrainOpsError("Update Note KO", code=ErrCode.UNEXPECTED, ctx={"status": "ollama"}) from exc
        return None
