"""
# process/update_note.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.io.note_reader import read_metadata_object
from brainops.io.note_writer import merge_metadata_in_note
from brainops.io.utils import count_words
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_import.utils.paths import path_is_inside
from brainops.process_notes.utils import check_if_tags
from brainops.process_regen.regen_utils import regen_header, regen_synthese_from_archive
from brainops.sql.get_linked.db_get_linked_folders_utils import get_category_context_from_folder
from brainops.sql.get_linked.db_get_linked_notes_utils import get_note_wc
from brainops.sql.notes.db_notes_utils import check_synthesis_and_trigger_archive
from brainops.sql.notes.db_update_notes import (
    update_obsidian_note,
)
from brainops.utils.config import Z_STORAGE_PATH
from brainops.utils.files import wait_for_file
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import sanitize_created, sanitize_yaml_title


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

    regen_synth_trigger = False
    regen_header_trigger = False
    regen_tags_trigger = False

    try:
        # 1) Métadonnées depuis YAML
        meta = read_metadata_object(str(dp), logger=logger)
        logger.debug(f"meta : {meta}")
        title_yaml = meta.title or dp.stem.replace("_", " ").replace(":", " ")
        status_yaml = meta.status or "draft"
        summary_yaml = meta.summary
        source_yaml = meta.source
        author_yaml = meta.author
        project_yaml = meta.project
        created_yaml = meta.created
        categ_yaml = meta.category
        subcateg_yaml = meta.subcategory or None

        if status_yaml == "regen":
            regen_synth_trigger = True
        elif status_yaml == "regen_hearder":
            regen_header_trigger = True

        # 2) Contexte catégories depuis le chemin
        base_folder = str(dp.parent)
        classification = get_category_context_from_folder(base_folder, logger=logger)

        logger.debug(
            "[UPDATE_NOTE] path→categ: %s / %s | ids: %s / %s",
            classification.category_name,
            classification.subcategory_name,
            classification.category_id,
            classification.subcategory_id,
        )

        # 4) Valeurs finales (YAML prioritaire si présent)
        title = sanitize_yaml_title(title_yaml)
        created = sanitize_created(created_yaml)
        author = author_yaml
        source = source_yaml
        project = project_yaml
        status_temp = status_yaml
        summary = summary_yaml

        new_status = classification.status
        def_status = new_status or status_temp

        actual_db_wc = get_note_wc(note_id, logger=logger) or 0
        wc = count_words(content=None, filepath=dp, logger=logger)
        if wc != actual_db_wc:
            regen_tags_trigger = True

        # 6) Update DB principal
        updates = {
            "file_path": str(dp),
            "title": title,
            "folder_id": classification.folder_id,
            "category_id": classification.category_id,
            "subcategory_id": classification.subcategory_id,
            "status": def_status,
            "summary": summary,
            "source": source,
            "author": author,
            "project": project,
            "created_at": created,
            "word_count": wc,
        }
        update_obsidian_note(note_id, updates, logger=logger)

        logger.info("[UPDATE_NOTE] Note mise à jour: %s (id=%s)", dp, note_id)

        # 9) Actions selon status
        if def_status == "synthesis":
            logger.debug("[UPDATE_NOTE] Post-action: check_synthesis_and_trigger_archive")
            check_synthesis_and_trigger_archive(note_id, str(dp), logger=logger)
        if regen_synth_trigger:
            logger.debug("[UPDATE_NOTE] Post-action: regen_synthese_from_archive")
            regen_synthese_from_archive(note_id, filepath=str(dp))
        if regen_header_trigger:
            logger.debug("[UPDATE_NOTE] Post-action: regen_header")
            regen_header(note_id, str(dp))

        if regen_tags_trigger:
            logger.debug("[UPDATE_NOTE] Post-action: regen_tags (via check_if_tags)")
            check_tags = check_if_tags(
                filepath=dp.as_posix(),
                note_id=note_id,
                wc=wc,
                status=def_status,
                classification=classification,
                logger=logger,
            )
            if check_tags:
                logger.info("[UPDATE_NOTE] Tags ajoutés automatiquement")

        if path_is_inside(Z_STORAGE_PATH, dp):
            if classification.category_name != categ_yaml or (classification.subcategory_name or "") != (
                subcateg_yaml or ""
            ):
                if classification.subcategory_name is None:
                    updates_head: dict[str, str | int | list[str]] = {
                        "category": classification.category_name,
                    }
                else:
                    updates_head = {
                        "category": classification.category_name,
                        "subcategory": classification.subcategory_name,
                    }
                merge = merge_metadata_in_note(filepath=dp, updates=updates_head, logger=logger)
                logger.debug(f"[UPDATE_NOTE] merge header : {merge}")
        return

    except Exception as exc:
        raise BrainOpsError("Update Note KO", code=ErrCode.UNEXPECTED, ctx={"status": "ollama"}) from exc
        return None
