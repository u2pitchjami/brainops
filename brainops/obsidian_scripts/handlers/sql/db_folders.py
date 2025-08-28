from brainops.logger_setup import setup_logger
import logging
from pathlib import Path
from brainops.obsidian_scripts.handlers.sql.db_connection import get_db_connection
from brainops.obsidian_scripts.handlers.sql.db_utils import safe_execute
from brainops.obsidian_scripts.handlers.sql.db_categs_utils import remove_unused_category

#setup_logger("db_folders", logging.DEBUG)
logger = logging.getLogger("db_folders")

def add_folder_to_db(folder_name, folder_path, folder_type, parent_id=None, category_id=None, subcategory_id=None):
    logger.debug("[DEBUG] entrée add_folder_to_db")
    
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    # Vérif d'existence
    result = safe_execute(cursor, "SELECT id FROM obsidian_folders WHERE path = %s", (str(folder_path),)).fetchone()
    logger.debug(f"[DEBUG] result : {result}")
    if result:
        logger.debug(f"[DEBUG] dossier existant : {result}")
        return result[0]

    logger.debug(f"[DEBUG] folder_name : {folder_name}, str(folder_path) : {str(folder_path)}, folder_type : {folder_type}, parent_id : {parent_id}, category_id : {category_id}, subcategory_id : {subcategory_id}")
    cursor.execute("""
        INSERT INTO obsidian_folders (name, path, folder_type, parent_id, category_id, subcategory_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (folder_name, str(folder_path), folder_type, parent_id, category_id, subcategory_id))

    conn.commit()
    folder_id = cursor.lastrowid
    logger.debug(f"[DEBUG] insertion db : {folder_id}")
    conn.close()
    return folder_id

    
def delete_folder_from_db(folder_path: str) -> bool:
    """
    Supprime un dossier de la base de données **seulement s’il est vide**,
    et nettoie les catégories associées si elles sont devenues orphelines.
    """
    try:
        conn = None
        path = Path(folder_path)
        if path.exists():
            # 🔒 Vérifie si le dossier contient des fichiers ou sous-dossiers
            if any(path.iterdir()):
                logger.warning(f"[DELETE] Dossier non vide, suppression ignorée : {folder_path}")
                return False

        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()

        # 🔍 Récupérer les IDs de catégorie avant suppression
        result = safe_execute(cursor,
            "SELECT category_id, subcategory_id FROM obsidian_folders WHERE path = %s",
            (folder_path,)
        ).fetchone()

        if not result:
            logger.warning(f"[DELETE] Aucun dossier trouvé en base : {folder_path}")
            return False

        category_id, subcategory_id = result
        logger.debug(f"[DELETE] Suppression dossier : {folder_path} | categ_id={category_id}, subcateg_id={subcategory_id}")

        # 🧹 Supprimer le dossier de la base
        safe_execute(cursor, "DELETE FROM obsidian_folders WHERE path = %s", (folder_path,))
        conn.commit()
        logger.info(f"[DELETE] Dossier supprimé en base : {folder_path}")

        # 🧼 Nettoyer les catégories orphelines
        if category_id:
            remove_unused_category(category_id)
        if subcategory_id and subcategory_id != category_id:
            remove_unused_category(subcategory_id)

        return True

    except Exception as e:
        logger.error(f"[ERROR] delete_folder_from_db({folder_path}) : {e}")
        return False

    finally:
        if conn:
            conn.close()

def update_folder_in_db(folder_id, new_path, category_id, subcategory_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE obsidian_folders
        SET path = %s, category_id = %s, subcategory_id = %s
        WHERE id = %s
    """, (new_path, category_id, subcategory_id, folder_id))
    conn.commit()
    conn.close()

