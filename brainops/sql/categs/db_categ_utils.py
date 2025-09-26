"""
# sql/db_categs_utils.py
"""

from __future__ import annotations

from brainops.sql.db_connection import get_db_connection, get_dict_cursor
from brainops.sql.db_utils import safe_execute_dict
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
        with get_dict_cursor(conn) as cur:
            row = safe_execute_dict(
                cur,
                "SELECT COUNT(*) AS total_count FROM obsidian_folders WHERE category_id=%s OR subcategory_id=%s",
                (category_id, category_id),
                logger=logger,
            ).fetchone()
            if row and int(row["total_count"]) == 0:
                safe_execute_dict(
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


@with_child_logger
def recup_all_categ_dictionary(logger: LoggerProtocol | None = None) -> None:
    """
    Génère la liste id catégories.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    try:
        with get_dict_cursor(conn) as cur:
            safe_execute_dict(cur, ("SELECT id FROM obsidian_categories"))
            categories = cur.fetchall()
            logger.debug(f"categories: {categories}")
        if not categories:
            return

        for cat in categories:
            remove_unused_category(cat["id"], logger=logger)
        return

    finally:
        conn.close()
