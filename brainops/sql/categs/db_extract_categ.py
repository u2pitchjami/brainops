"""
# sql/db_categs_utils.py
"""

from __future__ import annotations

from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def categ_extract(
    base_folder: str, *, logger: LoggerProtocol | None = None
) -> tuple[str | None, str | None, int | None, int | None]:
    """
    Retourne (category_name, subcategory_name, category_id, subcategory_id) pour un dossier.

    Utilise des curseurs bufferisés pour éviter 'Unread result found'.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)

    try:
        # 1) Récupère les IDs depuis le dossier
        with conn.cursor(buffered=True) as cur:
            row = safe_execute(
                cur,
                "SELECT category_id, subcategory_id FROM obsidian_folders WHERE path=%s",
                (base_folder,),
                logger=logger,
            ).fetchone()

        if not row:
            logger.warning("[CATEG] Aucun dossier trouvé pour: %s", base_folder)
            return None, None, None, None

        category_id: int | None = int(row[0]) if row[0] is not None else None
        subcategory_id: int | None = int(row[1]) if row[1] is not None else None
        logger.debug(
            "[CATEG] Dossier: %s | cat_id=%s | subcat_id=%s",
            base_folder,
            category_id,
            subcategory_id,
        )

        # 2) Résout les noms (séparément, curseur bufferisé)
        category_name: str | None = None
        subcategory_name: str | None = None

        with conn.cursor(buffered=True) as cur:
            if category_id is not None:
                r = safe_execute(
                    cur,
                    "SELECT name FROM obsidian_categories WHERE id=%s LIMIT 1",
                    (category_id,),
                    logger=logger,
                ).fetchone()
                category_name = str(r[0]) if r else None
                logger.debug("[CATEG] Catégorie trouvée: %s (id=%s)", category_name, category_id)

            if subcategory_id is not None:
                r = safe_execute(
                    cur,
                    "SELECT name FROM obsidian_categories WHERE id=%s LIMIT 1",
                    (subcategory_id,),
                    logger=logger,
                ).fetchone()
                subcategory_name = str(r[0]) if r else None
                logger.debug(
                    "[CATEG] Sous-catégorie trouvée: %s (id=%s)",
                    subcategory_name,
                    subcategory_id,
                )

        return category_name, subcategory_name, category_id, subcategory_id

    finally:
        conn.close()
