# handlers/start/process_note_event.py
from logger_setup import setup_logger
import logging
import re
import os
from datetime import datetime
from pathlib import Path
from handlers.utils.sql_helpers import (
    check_synthesis_and_trigger_archive, add_note_to_db, update_note_in_db, delete_note_from_db, check_duplicate, categ_extract)
from handlers.utils.extract_yaml_header import extract_tags, extract_note_metadata, ensure_note_id_in_yaml
from handlers.utils.queue_manager import event_queue
from handlers.process.headers import add_metadata_to_yaml
from Levenshtein import ratio
setup_logger("process_note_event", logging.DEBUG)
logger = logging.getLogger("process_note_event")
RELATIVE_PATH = os.getenv('RELATIVE_PATH')

def get_relative_path(filepath):
    """Retourne le chemin relatif d'un fichier par rapport au vault Obsidian"""
    return str(Path(filepath).relative_to(RELATIVE_PATH))

def process_note_event(event):
    """Gère les événements liés aux notes (création, modification, suppression, déplacement)."""

    logger.debug(f"[DEBUG] ===== process_note_event() reçu : {event}")
    file_path = event.get("path", event.get("src_path"))
    relative_filepath = str(Path(file_path).relative_to(RELATIVE_PATH))
    note_title = Path(file_path).stem.replace("_", " ").replace(":", " ")
    
    src_path = None
    tags = None
    note_id = None
    category_id = None
    subcategory_id = None
    status = None
    new_title = note_title
    

    if note_title.lower() == "untitled" or not note_title.strip():
        logger.info(f"[INFO] Ignoré : fichier temporaire ou sans titre ({file_path})")
        return

    if event['action'] == 'created':
        try:
            logger.debug(f"[DEBUG] ===== CREATED Ajout de la note : {note_title}")

            # if "Z_technical" in file_path:
            #      # Vérification des doublons avant ajout
            #     if check_duplicate(note_title):
            #         logger.warning(f"[DOUBLON] Note similaire déjà existante : {note_title}")
            #         return

            metadata = extract_note_metadata(file_path)
            print("title", metadata["title"])       # ➝ "Ma super note"
            status = metadata["status"]      # ➝ "In Progress"
            print("category :", metadata["category"])
            print("subcategory :", metadata["sub category"])
            print("created_at :", metadata["created"])
            print("modified_at :", metadata["last_modified"])
                        
            
            note_id = add_note_to_db(
                file_path, note_title, 
                metadata.get("category"), metadata.get("sub category"),
                metadata.get("tags", []), metadata.get("status", "draft"),
                metadata.get("created", datetime.now().strftime('%Y-%m-%d')),
                metadata.get("last_modified", datetime.now().strftime('%Y-%m-%d'))
            )

            logger.info(f"[INFO] Note ajoutée en base : {relative_filepath}")
            
            ensure_note_id_in_yaml(file_path, note_id, status)
            
            if "Archives" in file_path:
                add_metadata_to_yaml(file_path)
                return note_id
            
            
            return note_id
            
        except Exception as e:
            logger.error(f"[ERREUR] Erreur lors de l'ajout de la note : {e}")

    elif event["action"] == "moved":
        logger.debug(f"[DEBUG] ===== MOVED Déplacement détecté pour {file_path}")

        src_path = event.get("src_path")
        path = event.get("path")

        if not src_path or not path:
            logger.error(f"[ERREUR] `moved` reçu sans `src_path` ou `path` : {event}")
            return  
        base_folder = os.path.dirname(Path(file_path))
        metadata = extract_note_metadata(file_path)
        src_path = file_path
        note_id = metadata.get("note_id")
        logger.debug(f"[DEBUG] process_note_event Modified note_id : {note_id}")
        status = metadata.get("status")
        logger.debug(f"[DEBUG] process_note_event Modified status : {status}")
        _, _, category_id, subcategory_id = categ_extract(base_folder)
        new_title = Path(src_path).stem.replace("_", " ")
        if note_id:
            tags = metadata.get("tags", [])
            note_id = update_note_in_db(src_path, new_title, note_id, tags, category_id, subcategory_id, status)
            logger.info(f"[INFO] Déplacement mis à jour en base : {src_path} → {src_path}")
        else:
            status = metadata["status"]
            note_id = add_note_to_db(
                file_path, note_title, 
                metadata.get("category"), metadata.get("sub category"),
                metadata.get("tags", []), metadata.get("status", "Draft"),
                metadata.get("created", datetime.now().strftime('%Y-%m-%d')),
                metadata.get("last_modified", datetime.now().strftime('%Y-%m-%d'))
            )
            logger.info(f"[INFO] Note ajoutée en base : {relative_filepath}")
            
            ensure_note_id_in_yaml(file_path, note_id, status)
            return note_id
        ensure_note_id_in_yaml(file_path, note_id, status)
        return note_id

    elif event["action"] == "deleted":
        delete_note_from_db(file_path)
        logger.info(f"[INFO] Note supprimée de la base : {relative_filepath}")

    elif event["action"] == "modified":
        logger.debug(f"[DEBUG] ===== MODIFIED note : {note_title}")
        base_folder = os.path.dirname(Path(file_path))
        metadata = extract_note_metadata(file_path)
        src_path = file_path
        note_id = metadata.get("note_id")
        logger.debug(f"[DEBUG] process_note_event Modified note_id : {note_id}")
        status = metadata.get("status")
        logger.debug(f"[DEBUG] process_note_event Modified status : {status}")
        if status == "synthesis":
            check_synthesis_and_trigger_archive(note_id)
            
        _, _, category_id, subcategory_id = categ_extract(base_folder)
        new_title = note_title
        if note_id:
            tags = metadata.get("tags", [])
            note_id = update_note_in_db(src_path, new_title, note_id, tags, category_id, subcategory_id, status)
            logger.info(f"[INFO] Note mise à jour pour {relative_filepath}")
        else:
            status = metadata["status"]
            note_id = add_note_to_db(
                file_path, note_title, 
                metadata.get("category"), metadata.get("sub category"),
                metadata.get("tags", []), metadata.get("status", "draft"),
                metadata.get("created", datetime.now().strftime('%Y-%m-%d')),
                metadata.get("last_modified", datetime.now().strftime('%Y-%m-%d'))
            )
            logger.info(f"[INFO] Note ajoutée en base : {relative_filepath}")
        ensure_note_id_in_yaml(file_path, note_id, status)
        return note_id