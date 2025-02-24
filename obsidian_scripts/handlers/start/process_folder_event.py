import os
import json
from logger_setup import setup_logger
import logging
import time
from pathlib import Path
from dotenv import load_dotenv
from handlers.utils.process_note_paths import load_note_paths, save_note_paths, detect_folder_type, categ_extract
setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")
base_path = os.getenv('BASE_PATH')

def process_folder_event(event):
    folder_path = event.get('path')
    action = event.get('action')
    logger.debug(f"[DEBUG] process_folder_event() a reçu un {action} pour {event['path']}")

    if folder_path.startswith('.') or 'untitled' in folder_path.lower():
        logger.info(f"[INFO] Dossier ignoré : {folder_path}")
        return  # Ignore les dossiers cachés ou non pertinents

    note_paths = load_note_paths()
    relative_path = os.path.relpath(folder_path, base_path)
    relative_path = relative_path
    
    # Vérification pour éviter l'ajout de dossiers vides
    if not relative_path.strip():
        logger.warning(f"[WARNING] Dossier avec un chemin vide détecté et ignoré : {folder_path}")
        return

    logger.debug(f"[DEBUG] relative_path : {relative_path}")

    parts = Path(relative_path).parts
    category = None
    subcategory = None
    folder_type = detect_folder_type(Path(folder_path))
    category, subcategory = categ_extract(folder_path)
    logger.debug(f"[DEBUG] process_folder_event category : {category} / {subcategory}")
    # Normalisation du chemin pour éviter les incohérences
    normalized_path = Path(relative_path).resolve()
    logger.debug(f"[DEBUG] normalized_path : {normalized_path}")
    if action == 'created':
        # Vérifier si la catégorie doit être créée (uniquement si folder_type == storage)
        if folder_type == "storage":
            category = parts[1].lower() if len(parts) > 1 else None
            subcategory = parts[2].lower() if len(parts) > 2 else None
            if category not in note_paths['categories']:
                note_paths['categories'][category] = {
                    "description": f"note about {category}",
                    "prompt_name": "divers",
                    "subcategories": {}
                }
                logger.info(f"[INFO] Catégorie ajoutée : {category}")

            # Ajouter une sous-catégorie si nécessaire
            if subcategory:
                if "subcategories" not in note_paths['categories'][category]:
                    note_paths['categories'][category]["subcategories"] = {}

                if subcategory not in note_paths['categories'][category]['subcategories']:
                    note_paths['categories'][category]['subcategories'][subcategory] = {
                        "description": f"note about {subcategory}",
                        "prompt_name": "divers"
                    }
                    logger.info(f"[INFO] Sous-catégorie ajoutée : {subcategory} dans {category}")

        if not normalized_path in note_paths['folders']:
            # Ajouter dans folders (toujours)
            note_paths['folders'][relative_path] = {
                "path": folder_path,
                "category": category,
                "subcategory": subcategory,
                "folder_type": folder_type
            }
            logger.info(f"[INFO] Dossier ajouté : {relative_path}")
        else:
            logger.info(f"[INFO] Dossier déjà présent, pas d'ajout : {relative_path}")

    elif action == 'deleted':
        logger.debug(f"[DEBUG] process_folder_event() a reçu un {action} pour {event['path']}")
        # Suppression des sous-catégories uniquement si elles existent
        if category and subcategory:
            try:
                if category in note_paths['categories'] and subcategory in note_paths['categories'][category]['subcategories']:
                    del note_paths['categories'][category]['subcategories'][subcategory]
                    logger.info(f"[INFO] Sous-catégorie supprimée : {subcategory} dans {category}")
                # Vérifier si la catégorie n'a plus de sous-catégories avant de la supprimer
                if not note_paths['categories'][category]['subcategories']:
                    del note_paths['categories'][category]
                    logger.info(f"[INFO] Catégorie supprimée car vide : {category}")
            except KeyError:
                logger.warning(f"[WARNING] Tentative de suppression d'une sous-catégorie inexistante : {subcategory} dans {category}")

        elif category and not subcategory:
            try:
                if category in note_paths['categories'] and not note_paths['categories'][category]['subcategories']:
                    del note_paths['categories'][category]
                    logger.info(f"[INFO] Catégorie supprimée car vide : {category}")
            except KeyError:
                logger.warning(f"[WARNING] Tentative de suppression d'une catégorie inexistante : {category}")
        
        
        # Attendre un court instant pour éviter les conflits avec Obsidian
        time.sleep(0.5)
        
        # 🔥 Supprimer récursivement tous les sous-dossiers imbriqués avant de supprimer le dossier principal
        subfolders = sorted(
            [key for key in note_paths['folders'] if key.startswith(relative_path + "/")], 
            key=lambda x: -len(x.split('/')) # Trie pour supprimer les plus profonds d'abord
        )
        for subfolder in subfolders:
            try:
                del note_paths['folders'][subfolder]
                logger.info(f"[INFO] Sous-dossier supprimé : {subfolder}")
            except KeyError:
                logger.warning(f"[WARNING] Tentative de suppression d'un sous-dossier inexistant : {subfolder}")

        # Suppression du dossier lui-même
        try:
            if relative_path in note_paths['folders']:
                del note_paths['folders'][relative_path]
                logger.info(f"[INFO] Dossier supprimé : {relative_path}")
        except KeyError:
            logger.warning(f"[WARNING] Tentative de suppression d'un dossier inexistant : {relative_path}")

        
    
    save_note_paths(note_paths)


def extract_category_subcategory(relative_path):
    parts = relative_path.split(os.sep)
    logger.debug(f"[DEBUG] parts : {parts}")
    if len(parts) >= 3:
        return parts[1], parts[2]  # Première partie = catégorie, deuxième partie = sous-catégorie
    elif len(parts) == 2:
        return parts[1], None  # Seulement une catégorie, pas de sous-catégorie
    return None, None