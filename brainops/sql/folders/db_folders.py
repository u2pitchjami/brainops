"""# sql/db_folders.py (ajouts)"""

from __future__ import annotations

from pathlib import Path

from brainops.models.folders import Folder
from brainops.sql.categs.db_categ_utils import remove_unused_category
from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def add_folder_from_model(folder: Folder, *, logger: LoggerProtocol | None = None) -> int | None:
    """
    Upsert idempotent par path à partir d'un modèle Folder.
    Requiert idéalement UNIQUE(path).
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO obsidian_folders
                  (name, path, folder_type, parent_id, category_id, subcategory_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  name = VALUES(name),
                  folder_type = VALUES(folder_type),
                  parent_id = VALUES(parent_id),
                  category_id = VALUES(category_id),
                  subcategory_id = VALUES(subcategory_id),
                  id = LAST_INSERT_ID(id)
                """,
                folder.to_upsert_params(),
            )
            cur.execute("SELECT LAST_INSERT_ID()")
            row = cur.fetchone()
            conn.commit()
            fid = int(row[0]) if row and row[0] else None
            logger.debug("[DB] Upsert folder %s -> id=%s", folder.path, fid)
            return fid
    finally:
        conn.close()


@with_child_logger
def update_folder_from_model(folder_id: int, new_folder: Folder, *, logger: LoggerProtocol | None = None) -> None:
    """
    Met à jour path, name, parent, (sub)cat, type depuis un modèle Folder.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE obsidian_folders
                   SET path=%s,
                       name=%s,
                       parent_id=%s,
                       category_id=%s,
                       subcategory_id=%s,
                       folder_type=%s
                 WHERE id=%s
                """,
                (
                    new_folder.path,
                    new_folder.name,
                    new_folder.parent_id,
                    new_folder.category_id,
                    new_folder.subcategory_id,
                    new_folder.folder_type.value,
                    folder_id,
                ),
            )
        conn.commit()
        logger.debug("[DB] Update folder id=%s → %s", folder_id, new_folder.path)
    finally:
        conn.close()


@with_child_logger
def delete_folder_from_db(folder_path: str, logger: LoggerProtocol | None = None) -> bool:
    """
    Supprime un dossier de la base de données **seulement s’il est vide**, et nettoie les catégories associées si elles
    sont devenues orphelines.
    """
    logger = ensure_logger(logger, __name__)
    try:
        conn = None
        path = Path(folder_path)
        if path.exists():
            # 🔒 Vérifie si le dossier contient des fichiers ou sous-dossiers
            if any(path.iterdir()):
                logger.warning(f"[DELETE] Dossier non vide, suppression ignorée : {folder_path}")
                return False

        conn = get_db_connection(logger=logger)
        if not conn:
            return False
        cursor = conn.cursor()

        # 🔍 Récupérer les IDs de catégorie avant suppression
        result = safe_execute(
            cursor,
            "SELECT category_id, subcategory_id FROM obsidian_folders WHERE path = %s",
            (folder_path,),
            logger=logger,
        ).fetchone()

        if not result:
            logger.warning(f"[DELETE] Aucun dossier trouvé en base : {folder_path}")
            return False

        category_id, subcategory_id = result
        logger.debug(
            f"[DELETE] Suppression dossier : {folder_path} | categ_id={category_id}, subcateg_id={subcategory_id}"
        )

        # 🧹 Supprimer le dossier de la base
        safe_execute(
            cursor,
            "DELETE FROM obsidian_folders WHERE path = %s",
            (folder_path,),
            logger=logger,
        )
        conn.commit()
        logger.info(f"[DELETE] Dossier supprimé en base : {folder_path}")

        # 🧼 Nettoyer les catégories orphelines
        if category_id:
            remove_unused_category(category_id, logger=logger)
        if subcategory_id and subcategory_id != category_id:
            remove_unused_category(subcategory_id, logger=logger)

        return True

    except Exception as e:
        logger.error(f"[ERROR] delete_folder_from_db({folder_path}) : {e}")
        return False

    finally:
        if conn:
            conn.close()
