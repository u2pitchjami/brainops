from brainops.logger_setup import setup_logger
import logging
from brainops.obsidian_scripts.handlers.sql.db_connection import get_db_connection
from brainops.obsidian_scripts.handlers.sql.db_utils import safe_execute

#setup_logger("db_folder_utils", logging.DEBUG)
logger = logging.getLogger("db_folder_utils")

def is_folder_included(path, include_types=None, exclude_types=None):
    """
    Vérifie si un dossier est inclus en fonction des types spécifiés, en utilisant MySQL.
    """
    logger.debug("[DEBUG] is_folder_included pour : %s", path)
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()

    # 🔹 Récupérer le type du dossier depuis `obsidian_folders`
    result = safe_execute(cursor, "SELECT folder_type FROM obsidian_folders WHERE path = %s", (path,)).fetchone()
    
    if not result:
        logger.debug(f"[DEBUG] Dossier non trouvé dans obsidian_folders : {path}")
        conn.close()
        return False

    folder_type = result[0]
    conn.close()

    # 🔹 Vérifier les exclusions et inclusions
    if exclude_types and folder_type in exclude_types:
        logger.debug(f"[DEBUG] Dossier exclu : {path} (type : {folder_type})")
        return False

    if include_types and folder_type not in include_types:
        logger.debug(f"[DEBUG] Dossier non inclus : {path} (type : {folder_type})")
        return False

    logger.debug(f"[DEBUG] Dossier inclus : {path} (type : {folder_type})")
    return True

def get_path_from_classification(category_id, subcategory_id=None):
    """
    Récupère le chemin du dossier d'une note selon sa catégorie et sous-catégorie en base MySQL.
    """
    logger.debug("[DEBUG] get_path_from_classification pour catégorie: %s, sous-catégorie: %s", category_id, subcategory_id)
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    # 🔹 Si la sous-catégorie est spécifiée, on la cherche en priorité
    if subcategory_id:
        result = safe_execute(cursor, "SELECT id, path FROM obsidian_folders WHERE category_id = %s AND subcategory_id = %s LIMIT 1", (category_id, subcategory_id)).fetchone()
        
        logger.debug("[DEBUG] get_path_from_classification result %s", result)
        # 🔥 Si on trouve un dossier correspondant à la catégorie/sous-catégorie, on le retourne
        if result:
            conn.close()
            return result

    # 🔹 Si aucune sous-catégorie trouvée OU si elle n'était pas spécifiée, on cherche la catégorie seule
    result = safe_execute(cursor, "SELECT id, path FROM obsidian_folders WHERE category_id = %s AND subcategory_id IS NULL LIMIT 1", (category_id,)).fetchone()
    
    logger.debug("[DEBUG] get_path_from_classification result categ %s", result)
    conn.close()

    if result:
        return result

    logger.warning("[WARN] Aucun dossier trouvé pour la catégorie: %s et sous-catégorie: %s", category_id, subcategory_id)
    return None

def get_note_folder_type(folder_path: int) -> str:
    """
    Récupère le type de dossier (folder_type) associé à une note.

    Args:
        note_id (int): L'identifiant de la note.

    Returns:
        str: Le type du dossier (ex: 'archive', 'projet', etc.), ou 'inconnu' si non trouvé.
    """
    folder = get_note_linked_data(note_id, "folder")
    return folder.get("folder_type") if isinstance(folder, dict) else "inconnu"