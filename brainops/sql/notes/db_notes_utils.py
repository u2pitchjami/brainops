"""
# sql/db_notes_utils.py
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil

from brainops.io.paths import to_abs
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_folders.folders import ensure_folder_exists
from brainops.process_regen.regen_utils import regen_header
from brainops.sql.db_connection import get_cursor, get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def check_synthesis_and_trigger_archive(
    note_id: int, dest_path: str | Path, *, logger: LoggerProtocol | None = None
) -> None:
    """
    Si une synthesis est modifiée, s'assurer que l'archive liée:

    - est sous 'Archives/',
    - porte le bon nom,
    - a son YAML synchronisé.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)

    try:
        with get_cursor(conn) as cur:
            row = safe_execute(
                cur,
                "SELECT file_path FROM obsidian_notes WHERE id=%s",
                (note_id,),
                logger=logger,
            ).fetchone()
            if not row:
                raise BrainOpsError("KO Note absente de la db", code=ErrCode.DB, ctx={"note_id": note_id})
            synthesis_path = Path(str(row[0]))
            synthesis_name = synthesis_path.stem

            # Archive actuelle (si existe)
            row = safe_execute(
                cur,
                "SELECT id, file_path FROM obsidian_notes WHERE parent_id=%s AND status='archive'",
                (note_id,),
                logger=logger,
            ).fetchone()

            if row:
                archive_id, current_archive_path = int(row[0]), Path(str(row[1]))
                synth_folder = Path(os.path.dirname(str(dest_path)))
                archive_folder = synth_folder / "Archives"
                ensure_folder_exists(archive_folder, logger=logger)

                new_archive_path = archive_folder / f"{synthesis_name} (archive).md"
                if current_archive_path != new_archive_path:
                    if Path(to_abs(new_archive_path)).exists():
                        logger.warning("[SYNC] Fichier existe déjà: %s", new_archive_path)
                    else:
                        shutil.move(str(to_abs(current_archive_path)), str(to_abs(new_archive_path)))
                        safe_execute(
                            cur,
                            "UPDATE obsidian_notes SET file_path=%s WHERE id=%s",
                            (new_archive_path.as_posix(), archive_id),
                            logger=logger,
                        )
                        conn.commit()
                regen_header(archive_id, str(new_archive_path))
            else:
                logger.warning("[SYNC] Aucune archive liée à la synthesis %s", note_id)
    except Exception as exc:
        raise BrainOpsError("check_synthesis_and_trigger KO", code=ErrCode.DB, ctx={"note_id": note_id}) from exc
    finally:
        conn.close()


@with_child_logger
def file_path_exists_in_db(
    file_path: str,
    src_path: str | None = None,
    *,
    logger: LoggerProtocol | None = None,
) -> int | None:
    """
    Retourne note_id si file_path (ou src_path) existe, sinon None.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None
    try:
        with get_cursor(conn) as cur:
            for path in [p for p in (src_path, file_path) if p]:
                row = safe_execute(
                    cur,
                    "SELECT id FROM obsidian_notes WHERE file_path=%s LIMIT 1",
                    (path,),
                    logger=logger,
                ).fetchone()
                if row:
                    return int(row[0])
        return None
    finally:
        conn.close()
