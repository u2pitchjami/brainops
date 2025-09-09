"""# sql/db_categs_utils.py"""

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
    if not conn:
        return None, None, None, None

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


@with_child_logger
def get_prompt_name(
    category: str,
    subcategory: str | None = None,
    *,
    logger: LoggerProtocol | None = None,
) -> str | None:
    """
    Retourne `prompt_name` en priorité depuis la sous-catégorie, sinon depuis la catégorie.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            if subcategory:
                row = safe_execute(
                    cur,
                    """
                    SELECT c2.prompt_name
                      FROM obsidian_categories c2
                      JOIN obsidian_categories c1 ON c2.parent_id=c1.id
                     WHERE c2.name=%s AND c1.name=%s
                     LIMIT 1
                    """,
                    (subcategory, category),
                    logger=logger,
                ).fetchone()
                if row and row[0]:
                    return str(row[0])

            row = safe_execute(
                cur,
                """
                SELECT prompt_name
                  FROM obsidian_categories
                 WHERE name=%s AND parent_id IS NULL
                 LIMIT 1
                """,
                (category,),
                logger=logger,
            ).fetchone()
            return str(row[0]) if row else None
    finally:
        conn.close()


@with_child_logger
def generate_classification_dictionary(*, logger: LoggerProtocol | None = None) -> str:
    """
    Génère la section "Classification Dictionary" (catégories + sous-catégories) depuis la DB.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return ""
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT id, name, description FROM obsidian_categories WHERE parent_id IS NULL")
            categories = cur.fetchall()

            lines: list[str] = ["Classification Dictionary:"]
            for cat in categories:
                description = cat["description"] or "No description available."
                lines.append(f'- "{cat["name"]}": {description}')
                cur.execute(
                    "SELECT name, description FROM obsidian_categories WHERE parent_id=%s",
                    (cat["id"],),
                )
                subcats = cur.fetchall()
                for sc in subcats:
                    sub_desc = sc["description"] or "No description available."
                    lines.append(f'  - "{sc["name"]}": {sub_desc}')
            return "\n".join(lines)
    finally:
        conn.close()


@with_child_logger
def generate_optional_subcategories(*, logger: LoggerProtocol | None = None) -> str:
    """
    Génère la liste des sous-catégories disponibles (groupées par catégorie).
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return ""
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
            return ""

        lines: list[str] = ["Optional Subcategories:"]
        for cat, subs in groups.items():
            lines.append(f'- "{cat}": {", ".join(sorted(subs))}')
        return "\n".join(lines)
    finally:
        conn.close()


@with_child_logger
def generate_categ_dictionary(*, logger: LoggerProtocol | None = None) -> str:
    """
    Génère la liste des catégories racines avec descriptions.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return ""
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT name, description FROM obsidian_categories WHERE parent_id IS NULL")
            categories = cur.fetchall()
        lines = ["Categ Dictionary:"]
        for cat in categories:
            expl = cat["description"] or "No description available."
            lines.append(f'- "{cat["name"]}": {expl}')
        return "\n".join(lines)
    finally:
        conn.close()


# ---- CRUD simples utilisés ailleurs (conservés) ---------------------------------


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
    if not conn:
        return 0
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
    if not conn:
        return 0
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
    finally:
        conn.close()


@with_child_logger
def remove_unused_category(category_id: int, *, logger: LoggerProtocol | None = None) -> bool:
    """
    Supprime une catégorie si plus utilisée dans `obsidian_folders`
    (category_id ou subcategory_id). Retourne True si supprimée.
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
