"""
sql/db_temp_blocs.py.
"""

from __future__ import annotations

import pymysql

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.db_connection import get_db_connection, get_dict_cursor
from brainops.sql.db_utils import safe_execute_dict
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def get_existing_bloc(
    note_id: int,
    block_index: int,
    prompt: str,
    model: str,
    split_method: str,
    word_limit: int,
    source: str,
    logger: LoggerProtocol | None = None,
) -> tuple[str, str] | None:
    """
    Retourne (response, status) pour un bloc existant, ou None.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    with get_dict_cursor(conn) as cur:
        try:
            safe_execute_dict(
                cur,
                """
                SELECT response, status
                FROM obsidian_temp_blocks
                WHERE note_id = %s              
                AND block_index = %s
                AND prompt = %s
                AND model_ollama = %s
                AND split_method = %s
                AND word_limit = %s
                AND source = %s
                LIMIT 1
                """,
                (
                    note_id,
                    block_index,
                    prompt,
                    model,
                    split_method,
                    word_limit,
                    source,
                ),
            )
            row = cur.fetchone()
            return (row["response"], row["status"]) if row else None
        except Exception as e:
            logger.error("[ERROR] get_existing_bloc: %s", e)
            return None
        finally:
            cur.close()
            conn.close()


@with_child_logger
def insert_bloc(
    note_id: int,
    block_index: int,
    content: str,
    prompt: str,
    model: str,
    split_method: str,
    word_limit: int,
    source: str,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Insère un nouveau bloc avec statut 'waiting'.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    with get_dict_cursor(conn) as cur:
        try:
            safe_execute_dict(
                cur,
                """
                INSERT INTO obsidian_temp_blocks (
                    note_id, block_index, content,
                    prompt, model_ollama, split_method, word_limit, source, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'waiting')
                """,
                (
                    note_id,
                    block_index,
                    content,
                    prompt,
                    model,
                    split_method,
                    word_limit,
                    source,
                ),
            )
            conn.commit()
        except pymysql.MySQLError:
            logger.warning("[SKIP] Bloc déjà existant : index=%s id=%s", block_index, note_id)
        except Exception as exc:
            logger.error("[ERROR] insert_bloc: %s", exc)
            conn.rollback()
            raise BrainOpsError("Insert Temp_bloc KO", code=ErrCode.DB, ctx={"note_id": note_id}) from exc
        finally:
            cur.close()
            conn.close()


@with_child_logger
def update_bloc_response(
    note_id: int,
    block_index: int,
    response: str,
    source: str,
    *,
    status: str = "processed",
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Met à jour un bloc avec la réponse et le statut (par défaut 'processed').

    Filtrage par (note_id, note_path, source, block_index).
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    with get_dict_cursor(conn) as cur:
        try:
            safe_execute_dict(
                cur,
                """
                UPDATE obsidian_temp_blocks
                SET response = %s,
                    status   = %s
                WHERE note_id    = %s
                AND source     = %s
                AND block_index = %s
                """,
                (response.strip(), status, note_id, source, block_index),
            )
            conn.commit()
        except Exception as exc:
            logger.error("[ERROR] update_bloc_response: %s", exc)
            conn.rollback()
            raise BrainOpsError("update_bloc KO", code=ErrCode.DB, ctx={"note_id": note_id}) from exc
        finally:
            cur.close()
            conn.close()
