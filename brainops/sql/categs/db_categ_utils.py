"""
# sql/db_categs_utils.py
"""

from __future__ import annotations

from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def remove_unused_category(category_id: int, *, logger: LoggerProtocol | None = None) -> bool:
    """
    Supprime une catégorie si plus utilisée dans `obsidian_folders` (category_id ou subcategory_id).

    Retourne True si supprimée.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            row = safe_execute(
                cur,
                "SELECT COUNT(*) FROM obsidian_folders WHERE category_id=%s OR subcategory_id=%s",
                (category_id, category_id),
                logger=logger,
            ).fetchone()
            if row and int(row[0]) == 0:
                safe_execute(
                    cur,
                    "DELETE FROM obsidian_categories WHERE id=%s",
                    (category_id,),
                    logger=logger,
                )
                conn.commit()
                logger.info("[CLEAN] Catégorie supprimée (id=%s)", category_id)
                return True
            logger.debug("[CLEAN] Catégorie conservée (id=%s) encore référencée", category_id)
            return False
    finally:
        conn.close()
