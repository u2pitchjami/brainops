"""
# sql/db_categs_utils.py
"""

from __future__ import annotations

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def get_or_create_category(name: str, *, logger: LoggerProtocol | None = None) -> int:
    """
    get_or_create_category _summary_

    _extended_summary_

    Args:
        name (str): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        int: _description_
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    try:
        with conn.cursor() as cur:
            row = safe_execute(
                cur,
                "SELECT id FROM obsidian_categories WHERE name=%s AND parent_id IS NULL",
                (name,),
                logger=logger,
            ).fetchone()
            if row:
                return int(row[0])

            safe_execute(
                cur,
                "INSERT INTO obsidian_categories (name, description, prompt_name) VALUES (%s, %s, %s)",
                (name, f"Note about {name}", "divers"),
                logger=logger,
            )
            conn.commit()
            return int(cur.lastrowid)
    except Exception as exc:
        raise BrainOpsError("KO récup ou création catg", code=ErrCode.DB, ctx={"name": name}) from exc
    finally:
        conn.close()


@with_child_logger
def get_or_create_subcategory(name: str, parent_id: int, *, logger: LoggerProtocol | None = None) -> int:
    """
    get_or_create_subcategory _summary_

    _extended_summary_

    Args:
        name (str): _description_
        parent_id (int): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        int: _description_
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    try:
        with conn.cursor() as cur:
            row = safe_execute(
                cur,
                "SELECT id FROM obsidian_categories WHERE name=%s AND parent_id=%s",
                (name, parent_id),
                logger=logger,
            ).fetchone()
            if row:
                return int(row[0])

            safe_execute(
                cur,
                "INSERT INTO obsidian_categories (name, parent_id, description, prompt_name) VALUES (%s, %s, %s, %s)",
                (name, parent_id, f"Note about {name}", "divers"),
                logger=logger,
            )
            conn.commit()
            return int(cur.lastrowid)
    except Exception as exc:
        raise BrainOpsError("KO récup ou création subcatg", code=ErrCode.DB, ctx={"name": name}) from exc
    finally:
        conn.close()
