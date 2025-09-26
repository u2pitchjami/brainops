"""
sql/db_temp_blocs.py.
"""

from __future__ import annotations

from brainops.sql.db_connection import get_db_connection, get_dict_cursor
from brainops.sql.db_utils import safe_execute_dict
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def mark_bloc_as_error(note_id: int, block_index: int, logger: LoggerProtocol | None = None) -> None:
    """
    Marque un bloc comme 'error' en se basant sur (note_path, block_index).

    (Chemin "compat" avec les anciens appels qui ne passaient pas note_id/source.) On ne touche pas aux blocs déjà
    'processed'.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    with get_dict_cursor(conn) as cur:
        try:
            safe_execute_dict(
                cur,
                """
                UPDATE obsidian_temp_blocks
                SET status = 'error'
                WHERE note_id = %s
                AND block_index = %s
                AND status <> 'processed'
                """,
                (note_id, block_index),
            )
            conn.commit()
        except Exception as e:
            logger.error("[ERROR] mark_bloc_as_error: %s", e)
            conn.rollback()
        finally:
            cur.close()
            conn.close()
