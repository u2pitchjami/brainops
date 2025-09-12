"""
# handlers/process/get_type.py
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_import.utils.paths import ensure_folder_exists
from brainops.sql.get_linked.db_get_linked_folders_utils import (
    get_folder_id,
)
from brainops.sql.get_linked.db_get_linked_notes_utils import get_data_for_should_trigger, get_file_path
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.utils.config import ERRORED_JSON, ERRORED_PATH
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def handle_errored_file(
    note_id: int,
    filepath: str | Path,
    exc: BrainOpsError,
    *,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Déplace la note vers UNCATEGORIZED_PATH et journalise pour reprocessing.
    """
    logger = ensure_logger(logger, __name__)

    try:
        ensure_folder_exists(Path(ERRORED_PATH), logger=logger)

        status, parent_id, _ = get_data_for_should_trigger(note_id=note_id, logger=logger)

        if parent_id:
            parent_filepath = get_file_path(note_id=parent_id, logger=logger)
            updates = {"parent_id": None}
            update_obsidian_note(note_id, updates, logger=logger)
            update_obsidian_note(parent_id, updates, logger=logger)

        if not status:
            raise BrainOpsError("déplacement uncategorized KO", code=ErrCode.METADATA, ctx={"note_id": note_id})

        if status == "synthesis":
            src = Path(str(parent_filepath)).expanduser().resolve()
            path_to_delete = filepath
            def_note_id = parent_id
        else:
            src = Path(str(filepath)).expanduser().resolve()
            path_to_delete = parent_filepath
            def_note_id = note_id

        dest = Path(ERRORED_PATH) / src.name
        shutil.move(src.as_posix(), dest.as_posix())
        logger.warning("[WARNING] 🚨 Note déplacée vers 'error' : %s", dest.as_posix())

        if os.path.isfile(path_to_delete):
            os.remove(path_to_delete)
            logger.info(f"🗑️ [FILE] Fichier supprimé : {path_to_delete}")

        # MAJ DB avec le vrai folder_id de ERRORED_PATH
        unc_folder_id = get_folder_id(Path(ERRORED_PATH).as_posix(), logger=logger)
        if def_note_id:
            updates_folder = {"folder_id": unc_folder_id, "file_path": dest.as_posix()}
            update_obsidian_note(def_note_id, updates_folder, logger=logger)

        # Journal JSON
        data = {}
        if Path(ERRORED_JSON).exists():
            with open(ERRORED_JSON, encoding="utf-8") as f:
                data = json.load(f)
        data[dest.as_posix()] = {
            "note_id": note_id,
            "msg": exc or "",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(ERRORED_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    except Exception as exc:
        logger.exception("[ERREUR] handle_uncategorized(%s) : %s", src.as_posix(), exc)
        raise BrainOpsError("déplacement uncategorized KO", code=ErrCode.METADATA, ctx={"note_id": note_id}) from exc
