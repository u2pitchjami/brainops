import logging
import os
from pathlib import Path

from brainops.obsidian_scripts.handlers.sql.db_categs_utils import (
    get_or_create_category,
    get_or_create_subcategory,
    remove_unused_category,
)
from brainops.obsidian_scripts.handlers.sql.db_folders import (
    add_folder_to_db,
    update_folder_in_db,
)
from brainops.obsidian_scripts.handlers.sql.db_get_linked_data import (
    get_folder_linked_data,
)
from brainops.obsidian_scripts.handlers.sql.db_get_linked_folders_utils import (
    get_category_context_from_folder,
    get_folder_id,
)
from brainops.obsidian_scripts.handlers.utils.config import Z_STORAGE_PATH
from brainops.obsidian_scripts.handlers.utils.paths import (
    get_relative_parts,
    path_is_inside,
)

logger = logging.getLogger("obsidian_notes." + __name__)


def add_folder(folder_path: str | Path, folder_type: str) -> int | None:
    """
    Prépare un dossier pour l'ajout en base :

    - déduit parent_id, category_id, subcategory_id
    - appelle insert_folder_db()
    """
    folder_path = str(folder_path)
    if "untitled" in folder_path.lower():
        logger.info(f"[INFO] Dossier ignoré car temporaire : {folder_path}")
        return None

    parent_path = "/".join(folder_path.split("/")[:-1]) if "/" in folder_path else None
    parent_id = get_folder_id(parent_path) if parent_path else None
    logger.debug("[DEBUG] parent_id : %s ,parent_path : %s", parent_id, parent_path)

    folder_type_inferred = folder_type
    category, subcategory, archive, category_id, subcategory_id = (
        None,
        None,
        None,
        None,
        None,
    )

    if path_is_inside(Z_STORAGE_PATH, folder_path):
        logger.debug("[DEBUG] passage path_inside")
        relative_parts = get_relative_parts(folder_path, Z_STORAGE_PATH)
        if not relative_parts:
            return None

        if len(relative_parts) == 1:
            category = relative_parts[0]
        elif len(relative_parts) == 2:
            category, subcategory = relative_parts
        elif len(relative_parts) == 3 and relative_parts[2].lower() == "archives":
            category, subcategory = relative_parts[0], relative_parts[1]
            folder_type_inferred = "archive"

        if category:
            category_id = get_or_create_category(category)
        if subcategory:
            subcategory_id = get_or_create_subcategory(subcategory, category_id)
        if archive:
            folder_type_inferred = "archive"
    logger.debug("[DEBUG] prépa envoie add_folder_to_db")
    return add_folder_to_db(
        folder_name=Path(folder_path).name,
        folder_path=folder_path,
        folder_type=folder_type_inferred,
        parent_id=parent_id,
        category_id=category_id,
        subcategory_id=subcategory_id,
    )


def update_folder(old_path: str | Path, new_path: str | Path) -> None:
    """
    Met à jour un dossier : nouveau chemin, nouvelles catégories, et nettoyage des anciennes si inutilisées.
    """
    folder = get_folder_linked_data(old_path, "folder")
    if "error" in folder:
        logger.warning(f"[FOLDER] Dossier introuvable pour mise à jour : {old_path}")
        return

    folder_id = folder["id"]
    old_cat_id = folder.get("category_id")
    old_subcat_id = folder.get("subcategory_id")
    category_name, subcategory_name, category_id, subcategory_id = (
        None,
        None,
        None,
        None,
    )

    category_id, subcategory_id, category_name, subcategory_name = (
        get_category_context_from_folder(new_path)
    )

    logger.info(
        f"[FOLDER] Mise à jour dossier ID {folder_id} : categ={category_name}, subcateg={subcategory_name}"
    )

    update_folder_in_db(folder_id, new_path, category_id, subcategory_id)

    # 🧹 Nettoyage des anciennes catégorisations si devenues orphelines
    if old_cat_id and old_cat_id != category_id:
        remove_unused_category(old_cat_id)
    if old_subcat_id and old_subcat_id != subcategory_id:
        remove_unused_category(old_subcat_id)
