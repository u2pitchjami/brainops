from logger_setup import setup_logger
import logging
from handlers.sql.db_connection import get_db_connection
from handlers.sql.db_utils import safe_execute

#setup_logger("db_get_linked_data", logging.DEBUG)
logger = logging.getLogger("db_get_linked_data")


def get_note_linked_data(note_id: int, what: str) -> dict:
    """
    Récupère des informations liées à une note à partir de son note_id.
    
    Args:
        note_id (int): L'ID de la note de base (obsidian_notes).
        what (str): Le type de données à récupérer : 'note', 'category', 'subcategory', 'folder', 'tags'

    Returns:
        dict: Les données récupérées ou une erreur.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {"error": "Connexion à la base échouée."}
        cursor = conn.cursor(dictionary=True)

        # Étape 1 : récupérer les infos de la note
        note = safe_execute(cursor, "SELECT * FROM obsidian_notes WHERE id = %s", (note_id,)).fetchone()
        
        
        if not note:
            return {"error": f"Aucune note avec l'ID {note_id}"}

        # Cas 1 : on veut juste la note elle-même
        if what == "note":
            return note

        # Cas 2 : on veut la catégorie
        if what == "category":
            cat_id = note.get("category_id")
            if cat_id:
                cursor.execute("SELECT * FROM obsidian_categories WHERE id = %s", (cat_id,))
                return cursor.fetchone() or {"error": f"Catégorie {cat_id} introuvable"}
            return {"error": "Aucune catégorie associée à cette note"}

        # Cas 3 : sous-catégorie
        if what == "subcategory":
            subcat_id = note.get("subcategory_id")
            if subcat_id:
                cursor.execute("SELECT * FROM obsidian_categories WHERE id = %s", (subcat_id,))
                return cursor.fetchone() or {"error": f"Sous-catégorie {subcat_id} introuvable"}
            return {"error": "Aucune sous-catégorie associée à cette note"}

        # Cas 4 : dossier
        if what == "folder":
            folder_id = note.get("folder_id")
            if folder_id:
                cursor.execute("SELECT * FROM obsidian_folders WHERE id = %s", (folder_id,))
                return cursor.fetchone() or {"error": f"Dossier {folder_id} introuvable"}
            return {"error": "Aucun dossier associé à cette note"}

        # Cas 5 : tags
        if what == "tags":
            cursor.execute("SELECT tag FROM obsidian_tags WHERE note_id = %s", (note_id,))
            return {"tags": [row["tag"] for row in cursor.fetchall()]}

        # Cas 6 : temp_blocks
        if what == "temp_blocks":
            cursor.execute("SELECT * FROM obsidian_temp_blocks WHERE note_id = %s", (note_id,))
            return cursor.fetchone() or {"error": f"temp_blocks introuvable"}

        return {"error": f"Type de donnée non reconnu : {what}"}

    except mysql.connector.Error as err:
        return {"error": f"Erreur SQL : {err}"}

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_folder_linked_data(folder_path: str, what: str) -> dict:
    """
    Récupère des informations liées à un dossier Obsidian à partir de son chemin.

    Args:
        folder_path (str): Le chemin complet du dossier.
        what (str): Le type de données à récupérer : 'folder', 'category', 'subcategory', 'parent'

    Returns:
        dict: Les données récupérées ou un dictionnaire avec une clé 'error'
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {"error": "Connexion à la base échouée."}
        cursor = conn.cursor(dictionary=True)

        # Étape 1 : récupérer les infos du dossier
        folder = safe_execute(cursor,
            "SELECT * FROM obsidian_folders WHERE path = %s",
            (folder_path,)
        ).fetchone()

        if not folder:
            return {"error": f"Aucun dossier trouvé pour : {folder_path}"}

        # Retour simple : juste les données du dossier
        if what == "folder":
            return folder

        # Récupération de la catégorie liée
        if what == "category":
            category_id = folder.get("category_id")
            if category_id:
                return safe_execute(cursor,
                    "SELECT * FROM obsidian_categories WHERE id = %s",
                    (category_id,)
                ).fetchone() or {}

        # Récupération de la sous-catégorie liée
        if what == "subcategory":
            sub_id = folder.get("subcategory_id")
            if sub_id:
                return safe_execute(cursor,
                    "SELECT * FROM obsidian_categories WHERE id = %s",
                    (sub_id,)
                ).fetchone() or {}

        # Récupération du dossier parent
        if what == "parent":
            parent_id = folder.get("parent_id")
            if parent_id:
                return safe_execute(cursor,
                    "SELECT * FROM obsidian_folders WHERE id = %s",
                    (parent_id,)
                ).fetchone() or {}

        return {"error": f"Type de donnée '{what}' non pris en charge."}

    except Exception as e:
        logger.error(f"[FOLDER] Erreur dans get_folder_linked_data : {e}")
        return {"error": str(e)}