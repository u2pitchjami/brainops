"""
# sql/db_categs_utils.py
"""

from __future__ import annotations

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.db_connection import get_db_connection, get_dict_cursor
from brainops.sql.db_utils import safe_execute_dict
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def generate_optional_subcategories(*, logger: LoggerProtocol | None = None) -> str:
    """
    Génère la liste des sous-catégories disponibles (groupées par catégorie).
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    try:
        with get_dict_cursor(conn) as cur:
            safe_execute_dict(
                cur,
                """
                SELECT DISTINCT c1.name AS category_name, c2.name AS subcategory_name
                FROM obsidian_categories c1
                JOIN obsidian_categories c2 ON c1.id = c2.parent_id
                JOIN obsidian_folders f ON f.category_id = c1.id
                WHERE f.path LIKE 'Z_Storage/%'
                ORDER BY c1.name, c2.name
                """,
            )
            results = cur.fetchall()

        groups: dict[str, list[str]] = {}
        for row in results:
            groups.setdefault(row["category_name"].lower(), []).append(row["subcategory_name"].lower())

        if not groups:
            raise BrainOpsError("KO récup optionnal subcateg", code=ErrCode.DB, ctx={"results": results})

        lines: list[str] = ["Optional Subcategories:"]
        for cat, subs in groups.items():
            lines.append(f'- "{cat}": {", ".join(sorted(subs))}'.lower())
        return "\n".join(lines)
    except Exception as exc:
        raise BrainOpsError("KO récup optionnal subcateg", code=ErrCode.DB, ctx={"results": results}) from exc
    finally:
        conn.close()


@with_child_logger
def generate_categ_dictionary(*, for_similar: bool = False, logger: LoggerProtocol | None = None) -> str:
    """
    Génère la liste des catégories racines avec descriptions.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    try:
        lines = []
        with get_dict_cursor(conn) as cur:
            safe_execute_dict(
                cur,
                (
                    "SELECT c.name, c.description\
                FROM obsidian_categories c\
                WHERE c.id IN (\
                    SELECT f.category_id\
                    FROM obsidian_folders f\
                    WHERE f.category_id IS NOT NULL\
                    AND f.path LIKE 'Z_Storage/%'\
                );"
                ),
            )
            categories = cur.fetchall()
            logger.debug(f"categories: {categories}")
        if not categories:
            raise BrainOpsError("KO récup optionnal subcateg", code=ErrCode.DB, ctx={"results": "categorie"})
        if not for_similar:
            lines = ["Categ Dictionary:"]
            for cat in categories:
                expl = cat["description"] or "No description available."
                lines.append(f'- "{cat["name"]}": {expl}'.lower())
            return "\n".join(lines)
        for cat in categories:
            lines.append(f"{cat['name']}".lower())
        return "\n".join(lines)
    finally:
        conn.close()


@with_child_logger
def get_categ_id_from_name(name: str, logger: LoggerProtocol | None = None) -> int | None:
    """
    Génère la liste des catégories racines avec descriptions.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    try:
        with get_dict_cursor(conn) as cur:
            row = safe_execute_dict(
                cur,
                "SELECT id FROM obsidian_categories WHERE parent_id IS NULL AND name = %s LIMIT 1",
                (name,),
                logger=logger,
            ).fetchone()
            if row is not None:
                return int(row["id"])
            return None
    except Exception as exc:
        logger.error(f"[ERROR] Erreur lors de la récupération de l'ID pour la catégorie {name}")
        raise BrainOpsError(f"Aucun ID pour la catégorie {name}", code=ErrCode.DB, ctx={"name": name}) from exc
    finally:
        conn.close()


@with_child_logger
def get_subcateg_from_categ(categ_id: int, logger: LoggerProtocol | None = None) -> str | None:
    """
    Génère la liste des subcatégories racines avec descriptions.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    try:
        lines = []
        with get_dict_cursor(conn) as cur:
            rows = safe_execute_dict(
                cur,
                "SELECT name FROM obsidian_categories WHERE parent_id = %s",
                (categ_id,),
                logger=logger,
            ).fetchall()

        if not rows:
            return None
        for cat in rows:
            lines.append(f"{cat['name']}".lower())
        return "\n".join(lines)
    finally:
        conn.close()
