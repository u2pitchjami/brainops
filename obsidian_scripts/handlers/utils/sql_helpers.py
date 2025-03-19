from logger_setup import setup_logger
import logging
import os
import re
import mysql.connector
from dotenv import load_dotenv
from Levenshtein import ratio
from pathlib import Path
from datetime import datetime

setup_logger("sql", logging.DEBUG)
logger = logging.getLogger("sql")

# Charger les variables d'environnement
load_dotenv()

# Configuration de la base via les variables d'environnement
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}

def get_db_connection():
    """ Établit une connexion à MySQL en utilisant les variables d'environnement """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"❌ ERREUR de connexion à MySQL : {err}")
        return None
    
def add_folder_to_db(folder_path, folder_type):
    """Ajoute un dossier dans MySQL en respectant la structure spécifique de Z_Storage et en gérant le parent_id."""
    if "untitled" in folder_path.lower():
        logger.info(f"[INFO] Dossier ignoré car temporaire : {folder_path}")
        return  

    conn = get_db_connection()
    if not conn:
        return  
    cursor = conn.cursor()

    # 🔹 Vérifier si le dossier existe déjà en base
    cursor.execute("SELECT id FROM obsidian_folders WHERE path = %s", (folder_path,))
    if cursor.fetchone():
        logger.info(f"[INFO] Dossier déjà existant en base : {folder_path}")
        conn.close()
        return  

    base_storage = "/mnt/user/Documents/Obsidian/notes/Z_Storage"
    relative_parts = None
    category_id, subcategory_id, parent_id = None, None, None

    # 🔹 Trouver le dossier parent
    parent_folder = "/".join(folder_path.split("/")[:-1]) if "/" in folder_path else None
    if parent_folder:
        cursor.execute("SELECT id FROM obsidian_folders WHERE path = %s", (parent_folder,))
        result = cursor.fetchone()
        parent_id = result[0] if result else None  # 🔥 Associer au parent si trouvé

    # 🔹 Si on est dans `Z_Storage`, appliquer la logique des catégories
    if folder_path.startswith(base_storage):
        try:
            relative_parts = Path(folder_path).relative_to(base_storage).parts
        except ValueError:
            logger.warning(f"[WARN] Impossible de calculer le chemin relatif pour {folder_path}")
            conn.close()
            return  

        category, subcategory, archive = None, None, None

        if len(relative_parts) == 1:
            category = relative_parts[0]  

        elif len(relative_parts) == 2:
            category = relative_parts[0]
            subcategory = relative_parts[1]  

        elif len(relative_parts) == 3 and relative_parts[2].lower() == "archives":
            category = relative_parts[0]
            subcategory = relative_parts[1]
            archive = True  

        # 🔹 Vérifier et insérer la catégorie si elle n'existe pas
        if category:
            cursor.execute("SELECT id FROM obsidian_categories WHERE name = %s AND parent_id IS NULL", (category,))
            category_result = cursor.fetchone()
            if not category_result:
                cursor.execute("""
                    INSERT INTO obsidian_categories (name, description, prompt_name) 
                    VALUES (%s, %s, %s)
                """, (category, f"Note about {category}", "divers"))
                category_id = cursor.lastrowid
                logger.info(f"[INFO] Catégorie créée : {category}")
            else:
                category_id = category_result[0]
        # 🔹 Vérifier et insérer la sous-catégorie si elle n'existe pas
        if subcategory:
            cursor.execute("SELECT id FROM obsidian_categories WHERE name = %s AND parent_id = %s", (subcategory, category_id))
            subcategory_result = cursor.fetchone()
            if not subcategory_result:
                cursor.execute("""
                    INSERT INTO obsidian_categories (name, parent_id, description, prompt_name) 
                    VALUES (%s, %s, %s, %s)
                """, (subcategory, category_id, f"Note about {subcategory}", "divers"))
                subcategory_id = cursor.lastrowid
                logger.info(f"[INFO] Sous-catégorie créée : {subcategory}")
            else:
                subcategory_id = subcategory_result[0]

        if archive:
            folder_type = "archive"

    # 🔹 Insérer le dossier avec `parent_id` en base
    cursor.execute("""
        INSERT INTO obsidian_folders (name, path, folder_type, parent_id, category_id, subcategory_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (Path(folder_path).name, folder_path, folder_type, parent_id, category_id, subcategory_id))

    conn.commit()
    conn.close()

    
def delete_folder_from_db(folder_path):
    """Supprime un dossier de la base de données et nettoie les catégories si elles ne sont plus utilisées."""
    conn = get_db_connection()
    if not conn:
        return  
    cursor = conn.cursor()

    # 🔹 Récupérer les ID de la catégorie et sous-catégorie avant suppression du dossier
    cursor.execute("SELECT category_id, subcategory_id FROM obsidian_folders WHERE path = %s", (folder_path,))
    result = cursor.fetchone()
    if result:
        category_id, subcategory_id = result

    # 🔹 Supprimer le dossier
    cursor.execute("DELETE FROM obsidian_folders WHERE path = %s", (folder_path,))
    logger.info(f"[INFO] Dossier supprimé : {folder_path}")

    # 🔹 Vérifier si la catégorie est encore utilisée
    if category_id:
        cursor.execute("SELECT COUNT(*) FROM obsidian_folders WHERE category_id = %s", (category_id,))
        category_count = cursor.fetchone()[0]
        if category_count == 0:
            cursor.execute("DELETE FROM obsidian_categories WHERE id = %s", (category_id,))
            logger.info(f"[INFO] Catégorie supprimée car plus utilisée : ID {category_id}")

    # 🔹 Vérifier si la sous-catégorie est encore utilisée
    if subcategory_id:
        cursor.execute("SELECT COUNT(*) FROM obsidian_folders WHERE subcategory_id = %s", (subcategory_id,))
        subcategory_count = cursor.fetchone()[0]
        if subcategory_count == 0:
            cursor.execute("DELETE FROM obsidian_categories WHERE id = %s", (subcategory_id,))
            logger.info(f"[INFO] Sous-catégorie supprimée car plus utilisée : ID {subcategory_id}")

    conn.commit()
    conn.close()


def update_folder_in_db(old_path, new_path):
    """Met à jour le chemin d'un dossier dans MySQL et nettoie les catégories si elles ne sont plus utilisées."""
    conn = get_db_connection()
    if not conn:
        return  
    cursor = conn.cursor()

    # 🔹 Récupérer les anciennes IDs de catégorie et sous-catégorie
    cursor.execute("SELECT id, category_id, subcategory_id FROM obsidian_folders WHERE path = %s", (old_path,))
    result = cursor.fetchone()
    if not result:
        logger.warning(f"[WARN] Dossier non trouvé en base pour mise à jour : {old_path}")
        conn.close()
        return  
    folder_id, old_category_id, old_subcategory_id = result

    # 🔹 Déterminer la nouvelle catégorie/sous-catégorie
    category, subcategory = categ_extract(new_path)
    category_id, subcategory_id = None, None

    if category:
        cursor.execute("SELECT id FROM obsidian_categories WHERE name = %s AND parent_id IS NULL", (category,))
        category_result = cursor.fetchone()
        if not category_result:
            cursor.execute("""
                INSERT INTO obsidian_categories (name, description, prompt_name) 
                VALUES (%s, %s, %s)
            """, (category, f"Note about {category}", "divers"))
            category_id = cursor.lastrowid
            logger.info(f"[INFO] Nouvelle catégorie créée : {category}")
        else:
            category_id = category_result[0]

    if subcategory:
        cursor.execute("SELECT id FROM obsidian_categories WHERE name = %s AND parent_id = %s", (subcategory, category_id))
        subcategory_result = cursor.fetchone()
        if not subcategory_result:
            cursor.execute("""
                INSERT INTO obsidian_categories (name, parent_id, description, prompt_name) 
                VALUES (%s, %s, %s, %s)
            """, (subcategory, category_id, f"Note about {subcategory}", "divers"))
            subcategory_id = cursor.lastrowid
            logger.info(f"[INFO] Nouvelle sous-catégorie créée : {subcategory}")
        else:
            subcategory_id = subcategory_result[0]

    # 🔹 Mettre à jour le dossier dans `obsidian_folders`
    cursor.execute("""
        UPDATE obsidian_folders
        SET path = %s, category_id = %s, subcategory_id = %s
        WHERE id = %s
    """, (new_path, category_id, subcategory_id, folder_id))

    # 🔹 Vérifier si l’ancienne catégorie doit être supprimée
    if old_category_id:
        cursor.execute("SELECT COUNT(*) FROM obsidian_folders WHERE category_id = %s", (old_category_id,))
        category_count = cursor.fetchone()[0]
        if category_count == 0:
            cursor.execute("DELETE FROM obsidian_categories WHERE id = %s", (old_category_id,))
            logger.info(f"[INFO] Ancienne catégorie supprimée car plus utilisée : ID {old_category_id}")

    # 🔹 Vérifier si l’ancienne sous-catégorie doit être supprimée
    if old_subcategory_id:
        cursor.execute("SELECT COUNT(*) FROM obsidian_folders WHERE subcategory_id = %s", (old_subcategory_id,))
        subcategory_count = cursor.fetchone()[0]
        if subcategory_count == 0:
            cursor.execute("DELETE FROM obsidian_categories WHERE id = %s", (old_subcategory_id,))
            logger.info(f"[INFO] Ancienne sous-catégorie supprimée car plus utilisée : ID {old_subcategory_id}")

    conn.commit()
    conn.close()


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

def add_note_to_db(file_path, title, category, subcategory, tags, status, created_at, modified_at):
    """Ajoute une note dans MySQL avec gestion du dossier et des tags"""
    logger.debug("[DEBUG] ===== Entrée add_note_to_db")
    conn = get_db_connection()
    if not conn:
        return  
    cursor = conn.cursor()

    # 🔹 Récupérer l'ID du dossier où se trouve la note
    folder_path = "/".join(file_path.split("/")[:-1])
    logger.debug(f"add_note_to_db folder_path {folder_path}")
    cursor.execute("SELECT id FROM obsidian_folders WHERE path = %s", (folder_path,))
    result = cursor.fetchone()
    folder_id = result[0] if result else None
    logger.debug(f"add_note_to_db folder_id {folder_id}")

    # 🔹 Insérer la note avec `category_id` et `subcategory_id` en requête directe
    cursor.execute("""
        INSERT INTO obsidian_notes (title, file_path, folder_id, category_id, subcategory_id, status, created_at, modified_at)
        VALUES (%s, %s, %s, 
                (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1), 
                (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1), 
                %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            title = VALUES(title), category_id = VALUES(category_id), subcategory_id = VALUES(subcategory_id),
            status = VALUES(status), modified_at = VALUES(modified_at)
    """, (title, file_path, folder_id, category, subcategory, status, created_at, modified_at))

    note_id = cursor.lastrowid
    logger.debug(f"[DEBUG] ===== add_note_to_db note_id {note_id}")
    # 🔹 Gérer les tags
    cursor.execute("DELETE FROM obsidian_tags WHERE note_id = %s", (note_id,))
    for tag in tags:
        cursor.execute("INSERT INTO obsidian_tags (note_id, tag) VALUES (%s, %s)", (note_id, tag))

    conn.commit()
    conn.close()
    return note_id

def update_note_in_db(new_path, new_title, note_id, tags, category_id=None, subcategory_id=None, status=None):
    """Met à jour le chemin, le titre et le dossier d'une note en base."""
    logger.debug(f"[DEBUG] ===== entrée update_note_to_db  new_path {new_path}, note_id {note_id}")
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()
    logger.debug(f"update_note_in_db new_path {type(new_path)}")
    # 🔹 Récupérer le nouveau `folder_id`
    folder_path = str(Path(new_path).parent)
    new_path = str(new_path) 
    cursor.execute("SELECT id FROM obsidian_folders WHERE path = %s", (folder_path,))
    result = cursor.fetchone()
    folder_id = result[0] if result else None
    logger.debug(f"update_note_in_db folder_id {folder_id}")
    cursor.execute("""
        UPDATE obsidian_notes 
        SET file_path = %s, title = %s, folder_id = %s, category_id = %s, subcategory_id = %s, status = %s 
        WHERE id = %s
    """, (new_path, new_title, folder_id, category_id, subcategory_id, status, note_id))
    logger.debug(f"[DEBUG] ===== sortie update_note_in_db folder_id")
    
    # 🔹 Gérer les tags
    cursor.execute("DELETE FROM obsidian_tags WHERE note_id = %s", (note_id,))
    for tag in tags:
        cursor.execute("INSERT INTO obsidian_tags (note_id, tag) VALUES (%s, %s)", (note_id, tag))
    
    conn.commit()
    conn.close()
    return note_id

def delete_note_from_db(file_path):
    """Supprime une note et ses tags associés de MySQL."""
    logger.debug("delete_note_from_db")
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()

    try:
        # 🔍 Trouver le `note_id`, `parent_id` et `status` AVANT suppression
        cursor.execute("SELECT id, parent_id, status FROM obsidian_notes WHERE file_path = %s", (file_path,))
        result = cursor.fetchone()

        if not result:
            logger.warning(f"⚠️ [WARNING] Aucune note trouvée pour {file_path}, suppression annulée")
            return

        note_id, parent_id, status = result
        logger.debug(f"🔍 [DEBUG] Note {note_id} (status={status}) liée à parent {parent_id}")

        # 🔥 Supprimer les tags associés AVANT la note
        cursor.execute("DELETE FROM obsidian_tags WHERE note_id = %s", (note_id,))
        logger.info(f"🏷️ [INFO] Tags supprimés pour la note {note_id}")

        # 🔥 Cas 1 : Suppression d'une `synthesis` → Supprime aussi l'archive associée (si elle existe)
        if status == "synthesis" and parent_id:
            logger.info(f"🗑️ [INFO] Suppression de l'archive associée : {parent_id}")
            cursor.execute("DELETE FROM obsidian_notes WHERE id = %s", (parent_id,))
            cursor.execute("DELETE FROM obsidian_tags WHERE note_id = %s", (parent_id,))
            logger.info(f"🏷️ [INFO] Tags supprimés pour l'archive {parent_id}")

        # 🔥 Cas 2 : Suppression d'une `archive` → Met `parent_id = NULL` dans la `synthesis` (si parent existe)
        elif status == "archive" and parent_id:
            logger.info(f"🔄 [INFO] Dissociation de la `synthesis` {parent_id} (plus d'archive liée)")
            cursor.execute("UPDATE obsidian_notes SET parent_id = NULL WHERE id = %s", (parent_id,))

        # 🔥 Suppression de la note actuelle en base
        cursor.execute("DELETE FROM obsidian_notes WHERE id = %s", (note_id,))
        conn.commit()
        logger.info(f"🗑️ [INFO] Note {note_id} supprimée avec succès")

    except Exception as e:
        logger.error(f"❌ [ERROR] Erreur lors de la suppression de la note {file_path} : {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def move_note_in_db(old_path, new_path):
    """Déplace une note en base en mettant à jour son chemin et son dossier."""
    logger.debug("entrée move_note_in_db")
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()

    # 🔹 Récupérer le nouveau `folder_id`
    folder_path = "/".join(new_path.split("/")[:-1])  
    cursor.execute("SELECT id FROM obsidian_folders WHERE path = %s", (folder_path,))
    result = cursor.fetchone()
    folder_id = result[0] if result else None
    logger.debug(f"move_note_in_db folder_id {folder_id}")
    cursor.execute("""
        UPDATE obsidian_notes 
        SET file_path = %s, folder_id = %s 
        WHERE file_path = %s
    """, (new_path, folder_id, old_path))

    conn.commit()
    conn.close()


def check_duplicate(title):
    """Vérifie si une note avec un titre similaire existe déjà en base."""
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()

    cursor.execute("SELECT title FROM obsidian_notes")
    notes = cursor.fetchall()

    for existing_title in notes:
        similarity = ratio(clean_title(title), clean_title(existing_title[0]))
        if similarity >= 0.9:
            return True

    return False

def clean_title(title):
    # Supprimer les chiffres de date et les underscores pour une meilleure comparaison
    return re.sub(r'^\d{6}_?', '', title.replace('_', ' ')).lower()

def categ_extract(base_folder):
    """
    Extrait la catégorie et sous-catégorie d'une note selon son emplacement.
    Utilise MySQL au lieu de note_paths.json.
    """
    logger.debug("entrée categ_extract pour : %s", base_folder)
    base_folder = str(base_folder)
    conn = get_db_connection()
    if not conn:
        return None, None
    cursor = conn.cursor()

    # 🔹 Récupérer les `category_id` et `subcategory_id` depuis `obsidian_folders`
    cursor.execute("""
        SELECT category_id, subcategory_id FROM obsidian_folders WHERE path = %s
    """, (base_folder,))
    result = cursor.fetchone()

    if not result:
        logger.warning("[WARN] Aucun dossier correspondant trouvé pour : %s", base_folder)
        conn.close()
        return None, None

    category_id, subcategory_id = result
    category_name = subcategory_name = None

    # 🔹 Convertir `category_id` et `subcategory_id` en noms de catégories
    if category_id:
        cursor.execute("SELECT name FROM obsidian_categories WHERE id = %s", (category_id,))
        result = cursor.fetchone()
        category_name = result[0] if result else None

    if subcategory_id:
        cursor.execute("SELECT name FROM obsidian_categories WHERE id = %s", (subcategory_id,))
        result = cursor.fetchone()
        subcategory_name = result[0] if result else None

    conn.close()

    logger.debug("[DEBUG] Dossier trouvé - Catégorie: %s, Sous-catégorie: %s", category_name, subcategory_name)
    return category_name, subcategory_name, category_id, subcategory_id

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
    cursor.execute("SELECT folder_type FROM obsidian_folders WHERE path = %s", (path,))
    result = cursor.fetchone()

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

def get_path_from_classification(category, subcategory=None):
    """
    Récupère le chemin du dossier d'une note selon sa catégorie et sous-catégorie en base MySQL.
    """
    logger.debug("[DEBUG] get_path_from_classification pour catégorie: %s, sous-catégorie: %s", category, subcategory)
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    # 🔹 Si la sous-catégorie est spécifiée, on la cherche en priorité
    if subcategory:
        cursor.execute("""
            SELECT path FROM obsidian_folders 
            WHERE category_id = (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1) 
            AND subcategory_id = (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1)
            LIMIT 1
        """, (category, subcategory))
        result = cursor.fetchone()
        logger.debug("[DEBUG] get_path_from_classification result %s", result)
        # 🔥 Si on trouve un dossier correspondant à la catégorie/sous-catégorie, on le retourne
        if result:
            conn.close()
            return result[0]

    # 🔹 Si aucune sous-catégorie trouvée OU si elle n'était pas spécifiée, on cherche la catégorie seule
    cursor.execute("""
        SELECT path FROM obsidian_folders 
        WHERE category_id = (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1) 
        AND subcategory_id IS NULL
        LIMIT 1
    """, (category,))
    result = cursor.fetchone()
    logger.debug("[DEBUG] get_path_from_classification result categ %s", result)
    conn.close()

    if result:
        return result[0]



    logger.warning("[WARN] Aucun dossier trouvé pour la catégorie: %s et sous-catégorie: %s", category, subcategory)
    return None

def get_prompt_name(category, subcategory=None):
    """
    Récupère le nom du prompt basé sur la catégorie et la sous-catégorie depuis MySQL.
    """
    logger.debug("[DEBUG] get_prompt_name() pour catégorie: %s, sous-catégorie: %s", category, subcategory)
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    # 🔹 Vérifier d'abord si la sous-catégorie a un `prompt_name`
    if subcategory:
        cursor.execute("""
            SELECT prompt_name FROM obsidian_categories 
            WHERE name = %s AND parent_id = (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1)
            LIMIT 1
        """, (subcategory, category))
        result = cursor.fetchone()
        if result and result[0]:
            conn.close()
            return result[0]

    # 🔹 Si pas de `prompt_name` pour la sous-catégorie, récupérer celui de la catégorie
    cursor.execute("""
        SELECT prompt_name FROM obsidian_categories WHERE name = %s AND parent_id IS NULL LIMIT 1
    """, (category,))
    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None

def get_path_by_category_and_subcategory(category, subcategory=None):
    """
    Récupère le chemin du dossier correspondant à une catégorie et sous-catégorie depuis MySQL.
    """
    logger.debug("[DEBUG] get_path_by_category_and_subcategory() pour catégorie: %s, sous-catégorie: %s", category, subcategory)
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    # 🔹 Priorité à la recherche `category + subcategory`
    if subcategory:
        cursor.execute("""
            SELECT path FROM obsidian_folders 
            WHERE category_id = (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1) 
            AND subcategory_id = (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1)
            LIMIT 1
        """, (category, subcategory))
        result = cursor.fetchone()
        if result:
            conn.close()
            return Path(result[0])

    # 🔹 Sinon, récupérer le dossier de la catégorie seule
    cursor.execute("""
        SELECT path FROM obsidian_folders 
        WHERE category_id = (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1) 
        AND subcategory_id IS NULL
        LIMIT 1
    """, (category,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return Path(result[0])

    logger.warning("[WARN] Aucun dossier trouvé pour %s/%s.", category, subcategory)
    return None


def link_notes_parent_child(incoming_note_id, yaml_note_id):
    """
    Lie une note archive à sa note synthèse via `parent_id` et vice-versa.
    """
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    try:
        # 🔗 Mise à jour des parent_id dans les deux sens
        cursor.execute(
            "UPDATE obsidian_notes SET parent_id = %s WHERE id = %s",
            (yaml_note_id, incoming_note_id)
        )
        cursor.execute(
            "UPDATE obsidian_notes SET parent_id = %s WHERE id = %s",
            (incoming_note_id, yaml_note_id)
        )

        conn.commit()  # ✅ 🔥 IMPORTANT : On commit avant de fermer la connexion
        logger.info(f"🔗 [INFO] Liens parent_id créés : Archive {incoming_note_id} ↔ Synthèse {yaml_note_id}")

    except Exception as e:
        logger.error(f"❌ [ERROR] Impossible d'ajouter les liens parent_id : {e}")
        conn.rollback()  # 🔥 Annule les modifs en cas d'erreur
    finally:
        cursor.close()  # 🔥 Toujours fermer le curseur
        conn.close()  # 🔥 Ferme la connexion proprement
 
        
def check_synthesis_and_trigger_archive(note_id):
    """
    Si une `synthesis` est modifiée, force un recheck de l'archive associée.
    """
    from handlers.utils.queue_manager import event_queue   
    conn = get_db_connection()
    if not conn:
        return  
    cursor = conn.cursor()

    try:
        # 🔍 Chercher l'archive associée
        cursor.execute("SELECT file_path FROM obsidian_notes WHERE parent_id = %s AND status = 'archive'", (note_id,))
        archive_result = cursor.fetchone()

        if archive_result:
            archive_path = archive_result[0]
            logger.info(f"📂 [INFO] Archive trouvée : {archive_path}, ajout en file d'attente")

            # 🔥 Ajout de l'archive à la file d'attente pour re-traitement
            event_queue.put({'type': 'file', 'action': 'modified', 'path': archive_path})
        else:
            logger.warning(f"⚠️ [WARNING] Aucune archive associée trouvée pour la synthesis {note_id}")

    except Exception as e:
        logger.error(f"❌ [ERROR] Erreur lors de la vérification de la synthesis {note_id} : {e}")
    finally:
        cursor.close()
        conn.close()
        
def get_note_data(note_id: int, table_name: str):
    """
    Récupère les données associées à une note depuis une table spécifique.
    
    Arguments :
    - note_id (int) : L'ID de la note de référence.
    - table_name (str) : La table cible (folders, categories, tags, notes).

    Retourne :
    - dict contenant les données récupérées.
    """
    
    # Mapping des tables valides avec leurs jointures respectives
    table_mapping = {
        "folders": {
            "table": "obsidian_folders",
            "join_key": "folder_id",
            "columns": "id, name, path, folder_type, parent_id, category_id, subcategory_id"
        },
        "categories": {
            "table": "obsidian_categories",
            "join_key": "category_id",
            "columns": "id, name, description, prompt_name, parent_id"
        },
        "tags": {
            "table": "obsidian_tags",
            "join_key": "note_id",
            "columns": "tag"
        },
        "notes": {  # Ajout de obsidian_notes
            "table": "obsidian_notes",
            "join_key": "id",  # La clé est directement l'id de la note
            "columns": "id, parent_id, title, file_path, folder_id, category_id, subcategory_id, status, created_at, modified_at, updated_at"
        }
    }

    # Vérifier si la table demandée est valide
    if table_name not in table_mapping:
        return {"error": "Table non reconnue. Utilisez 'folders', 'categories', 'tags' ou 'notes'."}

    # Récupérer les infos de la table cible
    table_info = table_mapping[table_name]
    table = table_info["table"]
    join_key = table_info["join_key"]
    columns = table_info["columns"]

    # Connexion à la base de données
    conn = get_db_connection()
    if not conn:
        return {"error": "Impossible de se connecter à la base de données."}

    try:
        cursor = conn.cursor(dictionary=True)
        
        # Requête SQL sécurisée
        query = f"""
            SELECT {columns} 
            FROM {table} 
            WHERE {join_key} = %s
        """
        cursor.execute(query, (note_id,))
        results = cursor.fetchall()

        return results if results else {"error": "Aucune donnée trouvée pour ce note_id."}

    except mysql.connector.Error as err:
        return {"error": f"Erreur SQL : {err}"}

    finally:
        cursor.close()
        conn.close()
        
def adjust_event_action(event):
    """
    Vérifie si file_path est dans la base de données.
    Si absent, change 'modified' en 'created'.

    Arguments :
    - event : Dictionnaire contenant l'événement du watcher.

    Retourne :
    - event modifié avec la bonne action.
    """
    file_path = event.get("file_path")
    action = event.get("action")

    if not file_path:
        return event  # Aucun changement si le chemin est vide

    conn = get_db_connection()
    if not conn:
        return event  # Si la base est inaccessible, on ne modifie rien

    try:
        cursor = conn.cursor()
        query = "SELECT id FROM obsidian_notes WHERE file_path = %s"
        cursor.execute(query, (file_path,))
        result = cursor.fetchone()

        if not result and action == "modified":
            print(f"Correction : '{file_path}' passe de 'MODIFIED' à 'CREATED'")
            event["action"] = "created"

        return event

    except mysql.connector.Error as err:
        print(f"Erreur SQL : {err}")
        return event

    finally:
        cursor.close()
        conn.close()

        
def file_path_exists_in_db(file_path: str) -> bool:
    """
    Vérifie si un file_path existe dans la table obsidian_notes.

    Arguments :
    - file_path (str) : Le chemin du fichier à vérifier.

    Retourne :
    - True si le fichier existe dans la base, False sinon.
    """
    conn = get_db_connection()
    if not conn:
        return False  # En cas d'erreur de connexion, on considère que le fichier n'existe pas

    try:
        cursor = conn.cursor()
        query = "SELECT 1 FROM obsidian_notes WHERE file_path = %s LIMIT 1"
        cursor.execute(query, (file_path,))
        result = cursor.fetchone()
        return result is not None

    except mysql.connector.Error as err:
        print(f"Erreur SQL : {err}")
        return False

    finally:
        cursor.close()
        conn.close()
