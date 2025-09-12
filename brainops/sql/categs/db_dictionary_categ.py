"""
# sql/db_categs_utils.py
"""

from __future__ import annotations

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.db_connection import get_db_connection
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def generate_optional_subcategories(*, logger: LoggerProtocol | None = None) -> str:
    """
    Génère la liste des sous-catégories disponibles (groupées par catégorie).
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT c1.name AS category_name, c2.name AS subcategory_name
                  FROM obsidian_categories c1
                  JOIN obsidian_categories c2 ON c1.id=c2.parent_id
                 ORDER BY c1.name, c2.name
                """
            )
            results = cur.fetchall()

        groups: dict[str, list[str]] = {}
        for row in results:
            groups.setdefault(row["category_name"], []).append(row["subcategory_name"])

        if not groups:
            raise BrainOpsError("KO récup optionnal subcateg", code=ErrCode.DB, ctx={"results": results})

        lines: list[str] = ["Optional Subcategories:"]
        for cat, subs in groups.items():
            lines.append(f'- "{cat}": {", ".join(sorted(subs))}')
        return "\n".join(lines)
    except Exception:
        raise BrainOpsError("KO récup optionnal subcateg", code=ErrCode.DB, ctx={"results": results})
    finally:
        conn.close()


@with_child_logger
def generate_categ_dictionary(*, logger: LoggerProtocol | None = None) -> str:
    """
    Génère la liste des catégories racines avec descriptions.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT name, description FROM obsidian_categories WHERE parent_id IS NULL")
            categories = cur.fetchall()
        if not categories:
            raise BrainOpsError("KO récup optionnal subcateg", code=ErrCode.DB, ctx={"results": "categorie"})
        lines = ["Categ Dictionary:"]
        for cat in categories:
            expl = cat["description"] or "No description available."
            lines.append(f'- "{cat["name"]}": {expl}')
        return "\n".join(lines)
    finally:
        conn.close()
