"""# sql/db_categs.py"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from brainops.process_import.utils.paths import ensure_folder_exists
from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.config import Z_STORAGE_PATH
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import normalize_full_path


@with_child_logger
def delete_category_from_db(
    category_name: str,
    subcategory_name: Optional[str] = None,
    *,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Supprime une catégorie ou une sous-catégorie par nom.
    - Si `subcategory_name` est fourni → supprime la sous-catégorie sous `category_name`.
    - Sinon → supprime la catégorie uniquement si elle n'a plus de sous-catégories.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            if subcategory_name:
                safe_execute(
                    cur,
                    """
                    DELETE FROM obsidian_categories
                     WHERE name=%s
                       AND parent_id IN (SELECT id FROM obsidian_categories WHERE name=%s)
                    """,
                    (subcategory_name, category_name),
                    logger=logger,
                )
            else:
                safe_execute(
                    cur,
                    """
                    DELETE FROM obsidian_categories oc
                     WHERE oc.name=%s
                       AND NOT EXISTS (SELECT 1 FROM obsidian_categories c WHERE c.parent_id=oc.id)
                    """,
                    (category_name,),
                    logger=logger,
                )
        conn.commit()
        logger.info(
            "[CATEG] Suppression demandée: category=%s subcategory=%s",
            category_name,
            subcategory_name,
        )
    finally:
        conn.close()


@with_child_logger
def get_path_safe(
    note_type: str,
    filepath: str,
    note_id: int,
    *,
    logger: LoggerProtocol | None = None,
) -> Optional[Tuple[int, int]]:
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
        logger.error("Format inattendu de note_type=%r : %s", note_type, exc)
        return None

    conn = get_db_connection(logger=logger)
    if not conn:
        return None
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
                category_id = add_dynamic_category(category, logger=logger) or 0

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
                    subcategory_id = (
                        add_dynamic_subcategory(category, subcategory, logger=logger)
                        or 0
                    )
            else:
                subcategory_id = 0  # pas de sous-catégorie

        return category_id, subcategory_id if subcategory_id != 0 else None  # type: ignore[return-value]
    finally:
        conn.close()


@with_child_logger
def add_dynamic_subcategory(
    category: str,
    subcategory: str,
    *,
    logger: LoggerProtocol | None = None,
) -> Optional[int]:
    """
    Crée une sous-catégorie sous `category` et son dossier associé sous Z_STORAGE_PATH/<category>/<subcategory>.
    Si le dossier de catégorie n'existe pas en DB, il est créé sous Z_STORAGE_PATH/<category>.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            # 1) ID catégorie parent
            parent_row = safe_execute(
                cur,
                "SELECT id FROM obsidian_categories WHERE name=%s AND parent_id IS NULL",
                (category,),
                logger=logger,
            ).fetchone()
            if not parent_row:
                logger.warning("[CATEG] Parent category absente: %s", category)
                return None
            category_id = int(parent_row[0])

            # 2) Dossier de catégorie existant ?
            cat_folder = safe_execute(
                cur,
                "SELECT id, path FROM obsidian_folders WHERE category_id=%s AND subcategory_id IS NULL LIMIT 1",
                (category_id,),
                logger=logger,
            ).fetchone()

            z_storage = normalize_full_path(Z_STORAGE_PATH)
            categ_path = Path(z_storage) / category
            category_folder_id: Optional[int]
            category_folder_path: str

            if cat_folder:
                category_folder_id = int(cat_folder[0])
                category_folder_path = str(cat_folder[1])
            else:
                # Trouver le folder racine Z_STORAGE_PATH
                storage_parent = safe_execute(
                    cur,
                    "SELECT id FROM obsidian_folders WHERE path=%s AND category_id IS NULL AND subcategory_id IS NULL",
                    (z_storage,),
                    logger=logger,
                ).fetchone()
                parent_id = int(storage_parent[0]) if storage_parent else None
                safe_execute(
                    cur,
                    """
                    INSERT INTO obsidian_folders (name, path, folder_type, parent_id, category_id, subcategory_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        category,
                        categ_path.as_posix(),
                        "storage",
                        parent_id,
                        category_id,
                        None,
                    ),
                    logger=logger,
                )
                category_folder_id = int(cur.lastrowid)
                category_folder_path = categ_path.as_posix()

            new_subcateg_path = Path(category_folder_path) / subcategory

            # 3) Créer la sous-catégorie
            safe_execute(
                cur,
                """
                INSERT INTO obsidian_categories (name, parent_id, description, prompt_name)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    subcategory,
                    category_id,
                    f"Note about {subcategory.lower()}",
                    "divers",
                ),
                logger=logger,
            )
            subcategory_id = int(cur.lastrowid)

            # 4) Créer le dossier de sous-catégorie
            safe_execute(
                cur,
                """
                INSERT INTO obsidian_folders (name, path, folder_type, parent_id, category_id, subcategory_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    subcategory,
                    new_subcateg_path.as_posix(),
                    "storage",
                    category_folder_id,
                    category_id,
                    subcategory_id,
                ),
                logger=logger,
            )

        conn.commit()
        ensure_folder_exists(new_subcateg_path, logger=logger)
        logger.info("[CATEG] Sous-catégorie créée: %s/%s", category, subcategory)
        return subcategory_id
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "[CATEG] add_dynamic_subcategory(%s, %s) : %s", category, subcategory, exc
        )
        return None
    finally:
        conn.close()


@with_child_logger
def add_dynamic_category(
    category: str,
    *,
    logger: LoggerProtocol | None = None,
) -> Optional[int]:
    """
    Crée une catégorie racine et son dossier sous Z_STORAGE_PATH/<category>.
    Requiert l'existence du folder racine Z_STORAGE_PATH en DB.
    """
    logger = ensure_logger(logger, __name__)
    z_storage = normalize_full_path(Z_STORAGE_PATH)
    new_categ_path = Path(z_storage) / category

    conn = get_db_connection(logger=logger)
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            # Folder racine Z_STORAGE_PATH
            row = safe_execute(
                cur,
                "SELECT id FROM obsidian_folders WHERE path=%s AND category_id IS NULL AND subcategory_id IS NULL",
                (z_storage,),
                logger=logger,
            ).fetchone()
            if not row:
                logger.warning(
                    "[CATEG] Folder racine absent en DB pour Z_STORAGE_PATH=%s",
                    z_storage,
                )
                return None
            folder_parent_id = int(row[0])

            # Catégorie
            safe_execute(
                cur,
                """
                INSERT INTO obsidian_categories (name, description, prompt_name)
                VALUES (%s, %s, %s)
                """,
                (category, f"Note about {category.lower()}", "divers"),
                logger=logger,
            )
            category_id = int(cur.lastrowid)

            # Dossier de catégorie
            safe_execute(
                cur,
                """
                INSERT INTO obsidian_folders (name, path, folder_type, parent_id, category_id, subcategory_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    category,
                    new_categ_path.as_posix(),
                    "storage",
                    folder_parent_id,
                    category_id,
                    None,
                ),
                logger=logger,
            )

        conn.commit()
        ensure_folder_exists(new_categ_path, logger=logger)
        logger.info("[CATEG] Catégorie créée: %s", category)
        return category_id
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[CATEG] add_dynamic_category(%s) : %s", category, exc)
        return None
    finally:
        conn.close()
