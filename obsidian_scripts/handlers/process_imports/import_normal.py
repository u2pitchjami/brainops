from handlers.process.large_note import process_large_note
from handlers.process.headers import make_properties
from handlers.process.keywords import process_and_update_file
from handlers.sql.db_update_notes import update_obsidian_note
from handlers.utils.files import copy_file_with_date, read_note_content, count_words
from handlers.sql.db_get_linked_data import get_note_linked_data
import os
from logger_setup import setup_logger
import logging

setup_logger("import_normal", logging.DEBUG)
logger = logging.getLogger("import_normal")

def import_normal(filepath, note_id):
    logger.debug(f"[DEBUG] démarrage du process_import_normal pour : {filepath}")
    try:
        sav_dir = os.getenv('SAV_PATH')
        copy_file_with_date(filepath, sav_dir)
        content = read_note_content(filepath)
        lines = content.splitlines()
        
        # Définir le seuil de mots pour déclencher l'analyse
        nombre_mots_actuels = count_words(content)
        seuil_mots_initial = 100
        seuil_modif = 100
        ancienne_valeur = 0
        updates = {
        'word_count': nombre_mots_actuels
        }
        update_obsidian_note(note_id, updates)
        # Lire les métadonnées existantes
        logger.debug(f"[DEBUG] import_normal lecture des metadonnees {filepath}")
           
        for line in lines:
            if line.startswith("word_count:"):
                try:
                    ancienne_valeur = int(line.split(":")[1].strip())
                    logger.debug(f"[DEBUG] import_normal ligne word_count trouvée {filepath}")
                except ValueError:
                    ancienne_valeur = 0  # Si la valeur est absente ou invalide
                                    
            if line.startswith("created:"):
                logger.debug(f"[DEBUG] import_normal ligne created trouvée {filepath}")
                date_creation = line.split(":")[1].strip()
                    
        logger.info(f"[INFO] Mots avant modif : {ancienne_valeur}, Mots actuels : {nombre_mots_actuels}")
        logger.debug(f"[DEBUG] import_normal Mots avant modif : {ancienne_valeur}, Mots actuels : {nombre_mots_actuels}-->{filepath}")
        # Conditions d'analyse
        if nombre_mots_actuels < seuil_mots_initial:
            logger.info("[INFO] Note trop courte. Aucun traitement.")
            logger.debug(f"[DEBUG] import_normal : note courte")
            return
        
        # Détection de modification significative
        if nombre_mots_actuels - ancienne_valeur >= seuil_modif or ancienne_valeur == 0:
            logger.info("[INFO] Modification significative détectée. Reformulation du texte.")
            logger.debug(f"[DEBUG] import_normal : modif significative {filepath}")
            logger.debug(f"[DEBUG] import_normal : envoie process_large {filepath}")
            data = get_note_linked_data(note_id, "note")
            logger.debug(f"[DEBUG] data : {data}")
            process_large_note(filepath, entry_type="reformulation")
            data = get_note_linked_data(note_id, "note")
            logger.debug(f"[DEBUG] data : {data}")
            logger.debug(f"[DEBUG] import_normal :retour du process_large {filepath}")
            logger.debug(f"[DEBUG] import_normal : import normal envoi vers process & update {filepath}")
            data = get_note_linked_data(note_id, "note")
            logger.debug(f"[DEBUG] data : {data}")
            process_and_update_file(filepath)
            data = get_note_linked_data(note_id, "note")
            logger.debug(f"[DEBUG] data : {data}")
            logger.debug(f"[DEBUG] import_normal : import normal envoi vers make_properties {filepath}")
            make_properties(filepath, note_id, status = "archive")
            
            
            return
        else:
            print("[INFO] Modification non significative. Pas de mise à jour.")
            logger.debug(f"[DEBUG] import_normal pas suffisament de modif")   
    except Exception as e:
        print(f"[ERREUR] Impossible de traiter {filepath} : {e}")