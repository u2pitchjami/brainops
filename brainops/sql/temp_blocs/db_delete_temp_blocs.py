"""
sql/db_temp_blocs.py.
"""

from __future__ import annotations

from pathlib import Path

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.db_connection import get_db_connection
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def delete_blocs_by_path_and_source(
    note_id: int,
    file_path: str | Path,
    source: str,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Supprime des blocs dans obsidian_temp_blocks selon la stratégie:

    - source == "all"  -> purge tous les blocs de la note (par note_id)
    - source contient "*" -> supprime par LIKE sur source pour ce file_path
    - sinon -> supprime exactement (file_path, source)
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)

    cursor = conn.cursor()

    try:
        if source == "all":
            cursor.execute(
                "DELETE FROM obsidian_temp_blocks WHERE note_id = %s",
                (note_id,),
            )
        elif "*" in source:
            like_pattern = source.replace("*", "%")
            cursor.execute(
                """
                DELETE FROM obsidian_temp_blocks
                 WHERE note_path = %s
                   AND source LIKE %s
                """,
                (str(file_path), like_pattern),
            )
        else:
            cursor.execute(
                """
                DELETE FROM obsidian_temp_blocks
                 WHERE note_path = %s
                   AND source = %s
                """,
                (str(file_path), source),
            )

        conn.commit()
        logger.info("[DELETE] Blocs supprimés pour %s (source=%s)", file_path, source)
    except Exception as exc:
        conn.rollback()
        raise BrainOpsError("Delete temp_block KO", code=ErrCode.DB, ctx={"note_id": note_id}) from exc
    finally:
        cursor.close()
        conn.close()
