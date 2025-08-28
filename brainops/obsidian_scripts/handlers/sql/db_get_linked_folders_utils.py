from brainops.logger_setup import setup_logger
import logging
from brainops.obsidian_scripts.handlers.sql.db_get_linked_data import get_folder_linked_data

#setup_logger("db_get_linked_folders_utils", logging.DEBUG)
logger = logging.getLogger("db_get_folders_utils")

def get_folder_id(folder_path: str) -> tuple[str, str, int, int]:
    """
    Retourne (folder_id)
    à partir d'un chemin de dossier.
    """
    folder = get_folder_linked_data(folder_path, "folder")
    if "error" in folder:
        return "", "", None, None

    folder_id = folder.get("id")
    logger.debug("[DEBUG] folder_id : %s ,folder : %s", folder_id, folder)
    
    
    return folder_id

def get_category_context_from_folder(folder_path: str) -> tuple[int, int, str, str]:
    """
    Récupère category_id, subcategory_id, category_name, subcategory_name
    à partir du chemin d'un dossier.
    """
    category = get_folder_linked_data(folder_path, "category")
    subcategory = get_folder_linked_data(folder_path, "subcategory")

    category_id = category.get("id") if isinstance(category, dict) else None
    category_name = category.get("name") if isinstance(category, dict) else ""

    subcategory_id = subcategory.get("id") if isinstance(subcategory, dict) else None
    subcategory_name = subcategory.get("name") if isinstance(subcategory, dict) else ""

    return category_id, subcategory_id, category_name, subcategory_name