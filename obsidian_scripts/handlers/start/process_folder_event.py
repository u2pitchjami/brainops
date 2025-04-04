import os
from logger_setup import setup_logger
import logging
from handlers.sql.db_folders import delete_folder_from_db
from handlers.process.folders import add_folder, update_folder


setup_logger("process_folder_event", logging.DEBUG)
logger = logging.getLogger("process_folder_event")
base_path = os.getenv('BASE_PATH')

def process_folder_event(event):
    """
    Gère un événement sur un dossier :
    - "created" → Ajoute le dossier en base
    - "deleted" → Supprime le dossier de la base
    - "moved" → Met à jour le dossier
    """
    folder_path = event.get('path')
    action = event.get('action')
    logger.debug(f"[DEBUG] process_folder_event() a reçu un {action} pour {event['path']}")

    if folder_path.startswith('.') or 'untitled' in folder_path.lower():
        logger.info(f"[INFO] Dossier ignoré : {folder_path}")
        return  # Ignore les dossiers cachés ou non pertinents

    logger.debug(f"[DEBUG] process_folder_event() detect_folder_type")
    folder_type = detect_folder_type(folder_path)  # 🔥 On détecte automatiquement le type
    logger.debug(f"[DEBUG] process_folder_event() folder_type {folder_type}")
    if action == 'created':
        logger.debug(f"[DEBUG] process_folder_event() envoie add_folder_to_db")
        add_folder(folder_path, folder_type)

    elif action == 'deleted':
        delete_folder_from_db(folder_path)

    elif action == 'moved':
        new_folder_path = event.get('new_path')
        logger.info(f"[INFO] new_folder_path : {new_folder_path}")
        if not new_folder_path:
            return
        update_folder(folder_path, new_folder_path)
        
def detect_folder_type(folder_path):
    """Détecte automatiquement le type de dossier en fonction de son chemin"""
    folder_path = folder_path.lower()  # 🔥 Normalisation en minuscule

    if "/archives" in folder_path:
        return "archive"
    elif "notes/z_storage/" in folder_path:
        return "storage"
    elif "notes/personnal/" in folder_path:
        return "personnal"
    elif "notes/projects/" in folder_path:
        return "project"
    elif "notes/z_technical/" in folder_path:
        return "technical"
    
    return "technical"  # Si aucun type n'est trouvé, on met une valeur par défaut
