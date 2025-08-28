from brainops.logger_setup import setup_logger
import logging
import os
from pathlib import Path
from brainops.obsidian_scripts.handlers.sql.db_connection import get_db_connection
from brainops.obsidian_scripts.handlers.sql.db_utils import safe_execute
from brainops.obsidian_scripts.handlers.utils.normalization import normalize_full_path
from brainops.obsidian_scripts.handlers.utils.paths import ensure_folder_exists

#setup_logger("db_categs", logging.DEBUG)
logger = logging.getLogger("db_categs")

def delete_category_from_db(category_name, subcategory_name=None):
    """Supprime une catégorie si elle n'a plus de sous-catégories ou de dossiers associés"""
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()

    if subcategory_name:
        cursor.execute("DELETE FROM obsidian_categories WHERE name = %s AND parent_id IN (SELECT id FROM obsidian_categories WHERE name = %s)", (subcategory_name, category_name))
    else:
        # Supprimer la catégorie si elle n'a plus de sous-catégories
        cursor.execute("DELETE FROM obsidian_categories WHERE name = %s AND NOT EXISTS (SELECT 1 FROM obsidian_categories WHERE parent_id = obsidian_categories.id)", (category_name,))

    conn.commit()
    conn.close()

def get_path_safe(note_type, filepath, note_id):
    """
    Vérifie et crée les chemins si besoin pour une note importée.
    - Vérifie si la catégorie et la sous-catégorie existent.
    - Si non, elles sont créées automatiquement.
    - Vérifie aussi si une catégorie similaire existe avant d’en créer une nouvelle.
    """
    logger.debug("Entrée get_path_safe avec note_type: %s", note_type)
    
    try:
        category, subcategory = note_type.split("/")
        
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor(dictionary=True)

        # 🔹 Vérifier si la catégorie existe
        cursor.execute("SELECT id FROM obsidian_categories WHERE name = %s AND parent_id IS NULL", (category,))
        category_result = cursor.fetchone()
        logger.debug("get_path_safe category_result: %s", category_result)
        if not category_result:
            logger.info(f"[INFO] Catégorie absente : {category}. Création en cours...")
            category_id = add_dynamic_category(category)
        else:
            category_id = category_result["id"]

        # 🔹 Vérifier si la sous-catégorie existe
        cursor.execute("SELECT id FROM obsidian_categories WHERE name = %s AND parent_id = %s", (subcategory, category_id))
        subcategory_result = cursor.fetchone()
        conn.close()
        
        if not subcategory_result:
            logger.info(f"[INFO] Sous-catégorie absente : {subcategory}. Création en cours...")
            subcategory_id = add_dynamic_subcategory(category, subcategory)
        else:
            subcategory_id = subcategory_result["id"]

        logger.debug(f"[DEBUG] Sous-catégorie {subcategory_id} , categ : {category_id}.")
        
                
        return category_id, subcategory_id

    except ValueError:
        logger.error("Format inattendu du résultat Llama : %s", note_type)
        handle_uncategorized(note_id, filepath, llama_proposition="Invalid format")
        return None

    
def add_dynamic_subcategory(category, subcategory):
    """
    Ajoute une sous-catégorie dans la base de données.
    """
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    # 🔹 Récupérer l'ID de la catégorie parent
    cursor.execute("SELECT id FROM obsidian_categories WHERE name = %s AND parent_id IS NULL", (category,))
    category_result = cursor.fetchone()

    if not category_result:
        logger.warning(f"[WARN] Impossible d'ajouter la sous-catégorie {subcategory}, la catégorie {category} est absente.")
        conn.close()
        return None

    category_id = category_result[0]
    
    # 🔹 Récupérer l'ID du dossier parent
    cursor.execute("SELECT id, path FROM obsidian_folders WHERE category_id = %s AND subcategory_id IS NULL", (category_id,))
    folder_category_result = cursor.fetchone()

    if not folder_category_result:
        logger.warning(f"[WARN] Impossible folder_category_result est absente.")
        
        Z_STORAGE_PATH = os.getenv('Z_STORAGE_PATH')
        categ_path = Path(Z_STORAGE_PATH) / category
        subcategory_id = None
        
        # 🔹 Trouver le dossier parent
        result = safe_execute(cursor, "SELECT id FROM obsidian_folders WHERE path = %s", (Z_STORAGE_PATH,)).fetchone()
        parent_id = result[0] if result else None  # 🔥 Associer au parent si trouvé
        logger.debug("[DEBUG] result : %s , parent_id : %s", result, parent_id)
        
        cursor.execute("""
        INSERT INTO obsidian_folders (name, path, folder_type, parent_id, category_id, subcategory_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (category, str(categ_path), "storage", parent_id, category_id, subcategory_id))
        folder_id = cursor.lastrowid
        
    if folder_category_result:
        category_folder_id = folder_category_result[0]
        category_folder_path = folder_category_result[1]
    else:
        category_folder_id = folder_id
        category_folder_path = str(categ_path)

    new_subcateg_path = Path(category_folder_path) / subcategory

    logger.info(f"[INFO] Création de la sous-catégorie : {subcategory} sous {category}")

    # 🔹 Création de la sous-catégorie
    cursor.execute("""
        INSERT INTO obsidian_categories (name, parent_id, description, prompt_name) 
        VALUES (%s, %s, %s, %s)
    """, (subcategory, category_id, f"Note about {subcategory.lower()}", "divers"))

    subcategory_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO obsidian_folders (name, path, folder_type, parent_id, category_id, subcategory_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (subcategory, str(new_subcateg_path), "storage", category_folder_id, category_id, subcategory_id))
    
    conn.commit()
    conn.close()
    
    ensure_folder_exists(new_subcateg_path)

    
    return subcategory_id

def add_dynamic_category(category):
    """
    Ajoute une nouvelle catégorie dans la base de données si elle n'existe pas.
    """
    logger.debug(f"add_dynamic_category")
    z_storage_path = normalize_full_path(os.getenv('Z_STORAGE_PATH'))
    logger.debug(f"add_dynamic_category z_storage_path : {z_storage_path}")
    new_categ_path = Path(z_storage_path) / category
    logger.debug(f"add_dynamic_category new_categ_path : {new_categ_path}")
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    # 🔹 Récupérer l'ID de la dossier parent
    cursor.execute("SELECT id FROM obsidian_folders WHERE path = %s AND category_id IS NULL AND subcategory_id IS NULL", (str(z_storage_path),))
    folder_parent_id = cursor.fetchone()
    folder_parent_id = folder_parent_id[0]
    logger.debug(f"add_dynamic_category folder_parent_id: {folder_parent_id}")


    if not folder_parent_id:
        logger.warning(f"[WARN] Impossible folder_parent_id est absent.")
        conn.close()
        return None
    
    logger.info(f"[INFO] Création de la nouvelle catégorie : {category}")

    # 🔹 Création dans la base
    cursor.execute("""
        INSERT INTO obsidian_categories (name, description, prompt_name) 
        VALUES (%s, %s, %s)
    """, (category, f"Note about {category.lower()}", "divers"))

    category_id = cursor.lastrowid
    
    cursor.execute("""
    INSERT INTO obsidian_folders (name, path, folder_type, parent_id, category_id, subcategory_id) 
    VALUES (%s, %s, %s, %s, %s, %s)
""", (category, str(new_categ_path), "storage", folder_parent_id, category_id, None))
    
    
    conn.commit()
    conn.close()
    
    return category_id