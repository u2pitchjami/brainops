"""
# sql/db_categs.py
"""

from __future__ import annotations

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.categs.db_dynamic_categ import add_dynamic_category, add_dynamic_subcategory
from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def get_path_safe(
    note_type: str,
    filepath: str,
    note_id: int,
    *,
    logger: LoggerProtocol | None = None,
) -> tuple[int, int]:
    """
    Vérifie / crée la catégorie et sous-catégorie si besoin, puis renvoie (category_id, subcategory_id).

    `note_type` attendu au format "Category/Subcategory" (Subcategory optionnelle).
    """
    logger = ensure_logger(logger, __name__)
    logger.debug(
        "Entrée get_path_safe: note_type=%s filepath=%s note_id=%s",
        note_type,
        filepath,
        note_id,
    )

    try:
        parts = [p.strip() for p in note_type.split("/", 1)]
        category = parts[0]
        subcategory = parts[1] if len(parts) == 2 and parts[1] else None
    except Exception as exc:  # pylint: disable=broad-except
        raise BrainOpsError(
            "Format inattendu de note_type", code=ErrCode.METADATA, ctx={"note_type": note_type}
        ) from exc

    conn = get_db_connection(logger=logger)
    try:
        with conn.cursor(dictionary=True) as cur:
            # Catégorie
            row = safe_execute(
                cur,
                "SELECT id FROM obsidian_categories WHERE name=%s AND parent_id IS NULL",
                (category,),
                logger=logger,
            ).fetchone()
            if row:
                category_id = int(row["id"])
            else:
                logger.info("[CATEG] Catégorie absente: %s → création…", category)
                category_id = add_dynamic_category(category, logger=logger)

            # Sous-catégorie
            if subcategory:
                row = safe_execute(
                    cur,
                    "SELECT id FROM obsidian_categories WHERE name=%s AND parent_id=%s",
                    (subcategory, category_id),
                    logger=logger,
                ).fetchone()
                if row:
                    subcategory_id = int(row["id"])
                else:
                    logger.info(
                        "[CATEG] Sous-catégorie absente: %s/%s → création…",
                        category,
                        subcategory,
                    )
                    subcategory_id = add_dynamic_subcategory(category, subcategory, logger=logger) or 0
            else:
                subcategory_id = 0  # pas de sous-catégorie

        return category_id, subcategory_id if subcategory_id != 0 else None  # type: ignore[return-value]
    except Exception as exc:
        raise BrainOpsError("Type by ollama KO", code=ErrCode.DB, ctx={"note_id": note_id}) from exc
    finally:
        conn.close()
