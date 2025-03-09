import os
from handlers.process_imports.import_gpt import process_import_gpt, process_clean_gpt, process_class_gpt, process_class_gpt_test
from handlers.process_imports.import_normal import import_normal
from handlers.process_imports.import_syntheses import process_import_syntheses
from handlers.process.get_type import process_get_note_type
from handlers.utils.files import rename_file
from handlers.utils.process_note_paths import is_folder_included, categ_extract
from handlers.standalone.standalone import make_synthese_standalone, make_header_standalone
from handlers.standalone.check_categ import process_sync_entete_with_path
from handlers.utils.queue_manager import log_event_queue
from logger_setup import setup_logger
import logging
from pathlib import Path
import fnmatch
setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

def process_single_note(filepath, dest_path=None):
    logger.debug(f"[DEBUG] démarrage du process_single_note pour : {filepath}")
    if not filepath.endswith(".md"):
        return
    # Obtenir le dossier contenant le fichier
    base_folder = os.path.dirname(filepath)
    log_event_queue()
    
        
    def process_import(filepath, base_folder):
        """ Fonction interne pour éviter la duplication de code """
        logger.info(f"[INFO] Import détecté : {filepath}")
        try:
            log_event_queue()
            new_path = process_get_note_type(filepath)
            logger.debug(f"[DEBUG] process_single_note fin get_note_type new_path : {new_path}")
            filepath = new_path
            base_folder = os.path.dirname(new_path)
            logger.debug(f"[DEBUG] process_single_note base_folder : {base_folder}")
            new_path = rename_file(filepath)
            logger.debug(f"[DEBUG] process_single_note fin rename_file : {new_path}")
            filepath = new_path
            if "gpt_import" in base_folder:
                logger.info(f"[INFO] Conversation GPT détectée, déplacement vers : {base_folder}")
                return
            category, subcategory = categ_extract(base_folder)
            log_event_queue()
            import_normal(filepath, category, subcategory)
            logger.debug(f"[DEBUG] process_single_note import normal terminé {category}/{subcategory}")
            log_event_queue()
            process_import_syntheses(filepath, category, subcategory)
            logger.info(f"[INFO] Import terminé pour : {filepath}")
            log_event_queue()
        except Exception as e:
            logger.error(f"[ERREUR] Problème lors de l'import : {e}")

     # 1. Vérifier si c'est un déplacement
    if dest_path is not None:
        logger.debug(f"[DEBUG] démarrage du process_single_note pour : Déplacement {dest_path}")
        if not os.path.exists(dest_path):
            logger.warning(f"[WARNING] Le fichier n'existe pas ou plus : {dest_path}")
            return
        dest_folder = os.path.dirname(dest_path)
        # 1.1 Déplacement valide entre dossiers catégorisés (hors exclus)
        if (is_folder_included(base_folder, include_types=['storage']) and 
    is_folder_included(dest_folder, include_types=['storage'])):
            logger.info(f"[INFO] Déplacement valide détecté : {filepath} -> {dest_path}")
            process_sync_entete_with_path(dest_path)
            return  # Sortir après le traitement du déplacement
        
        elif "Z_technical/imports" in base_folder:
            process_import(filepath, base_folder)
                
        # 1.2 Autres déplacements (exemple : ZMake)
        elif "Z_technical/ZMake_Synthese" in dest_folder:
            logger.info(f"[INFO] Déplacement manuel vers ZMake_Synthese : {filepath} -> {dest_path}")
            make_synthese_standalone(dest_path)
            return

        elif "Z_technical/ZMake_Header" in dest_folder:
            logger.info(f"[INFO] Déplacement manuel vers ZMake_Header : {filepath} -> {dest_path}")
            make_header_standalone(dest_path)
            return

        # Autres cas : déplacement ignoré
        else:
            logger.info(f"[INFO] Déplacement ignoré : {filepath} -> {dest_path}")
            return

    # 2. Sinon : Gérer les créations ou modifications
    else:
        if not os.path.exists(filepath):
            logger.warning(f"[WARNING] Le fichier n'existe pas ou plus : {filepath}")
            return
        logger.debug(f"[DEBUG] démarrage du process_single_note pour : création - modif")
        
        if "Z_technical/imports" in base_folder:
            process_import(filepath, base_folder)

        elif "Z_technical/gpt_import" in base_folder:
            logger.info(f"[INFO] Split de la conversation GPT : {filepath}")
            try:
                logger.debug(f"[DEBUG] process_single_note : envoi vers gpt_import")
                process_import_gpt(filepath)
                return
            except Exception as e:
                logger.error(f"[ERREUR] Anomalie l'import gpt : {e}")
                return
        elif "Z_technical/gpt_output" in base_folder:
            logger.info(f"[INFO] Import issu d'une conversation GPT : {filepath}")
            try:
                process_clean_gpt(filepath)
                new_path = process_get_note_type(filepath)
                base_folder = os.path.dirname(new_path)
                logger.info(f"[INFO] base_folder : {base_folder}")
                filepath = new_path
                print ("filepath:", filepath)
                new_path = rename_file(filepath)
                logger.info(f"[INFO] Note renommée : {filepath} --> {new_path}")
                filepath = new_path
                base_folder = os.path.dirname(new_path)
                logger.info(f"[INFO] base_folder : {base_folder}")
                category, subcategory = categ_extract(base_folder)
                process_class_gpt(filepath, category, subcategory)
                logger.info(f"[INFO] Import terminé pour : {filepath}")
                return
            except Exception as e:
                logger.error(f"[ERREUR] Anomalie l'import gpt : {e}")
                return
        elif "Z_technical/test_gpt" in base_folder:
            logger.info(f"[INFO] Import issu d'une conversation GPT TEST : {filepath}")
            try:
                process_class_gpt_test(filepath)
                logger.info(f"[INFO] Import terminé pour : {filepath}")
                return
            except Exception as e:
                logger.error(f"[ERREUR] Anomalie l'import gpt : {e}")
                return

        else:
            # Traitement pour les autres cas
            logger.debug(f"[DEBUG] Aucune correspondance pour : {filepath}")
            return