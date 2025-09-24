"""
# io/move_uncategorized.py
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil

from brainops.io.paths import to_abs
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_folders.folders import ensure_folder_exists
from brainops.sql.get_linked.db_get_linked_folders_utils import get_folder_id
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.utils.config import (
    UNCATEGORIZED_JSON,
    UNCATEGORIZED_PATH,
)
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def handle_uncategorized(
    note_id: int,
    filepath: str | Path,
    note_type: str | None,
    llama_proposition: str,
    *,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Déplace la note vers UNCATEGORIZED_PATH et journalise pour reprocessing.
    """
    logger = ensure_logger(logger, __name__)
    src = Path(str(filepath))
    try:
        ensure_folder_exists(Path(UNCATEGORIZED_PATH), logger=logger)
        dest = Path(UNCATEGORIZED_PATH) / src.name

        shutil.move(Path(to_abs(src)).as_posix(), to_abs(dest).as_posix())
        logger.warning("[WARNING] 🚨 Note déplacée vers 'uncategorized' : %s", dest.as_posix())

        # MAJ DB avec le vrai folder_id de UNCATEGORIZED_PATH
        unc_folder_id = get_folder_id(Path(UNCATEGORIZED_PATH).as_posix(), logger=logger)
        updates = {"folder_id": unc_folder_id, "file_path": dest.as_posix()}
        update_obsidian_note(note_id, updates, logger=logger)

        # Journal JSON
        data = {}
        if Path(UNCATEGORIZED_JSON).exists():
            with open(UNCATEGORIZED_JSON, encoding="utf-8") as f:
                data = json.load(f)
        data[dest.as_posix()] = {
            "original_type": note_type,
            "llama_proposition": llama_proposition or "",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(UNCATEGORIZED_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    except Exception as exc:
        raise BrainOpsError(
            "[METADATA] ❌ déplacement uncategorized KO",
            code=ErrCode.METADATA,
            ctx={"fonction": "handle_uncategorized", "note_id": note_id, "llama_proposition": llama_proposition},
        ) from exc
