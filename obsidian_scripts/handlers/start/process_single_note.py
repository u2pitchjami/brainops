import os
from handlers.utils.config import UNCATEGORIZED_PATH, IMPORTS_PATH, GPT_IMPORT_DIR, GPT_OUTPUT_DIR, GPT_TEST
from handlers.process_imports.import_gpt import process_import_gpt, process_clean_gpt, process_class_gpt, process_class_gpt_test
from handlers.process_imports.import_normal import import_normal
from handlers.process_imports.import_syntheses import process_import_syntheses
from handlers.process.get_type import process_get_note_type
from handlers.process.divers import rename_file
from handlers.process.regen_utils import force_categ_from_path
from handlers.sql.db_update_notes import update_obsidian_note
from handlers.sql.db_folders_utils import is_folder_included
from handlers.sql.db_categs_utils import categ_extract
from handlers.watcher.queue_manager import log_event_queue
from handlers.utils.paths import path_is_inside
from logger_setup import setup_logger
import logging

setup_logger("process_single_note", logging.DEBUG)
logger = logging.getLogger("process_single_note")


def process_single_note(filepath, note_id, src_path=None):
    logger.debug(f"[DEBUG] ===== Démarrage du process_single_note pour : {filepath}")
    psn = False
    if not filepath.endswith(".md"):
        return psn
    # Obtenir le dossier contenant le fichier
    base_folder = os.path.dirname(filepath)
    log_event_queue()
    
        
    def process_import(filepath, base_folder, note_id):
        """ Fonction interne pour éviter la duplication de code """
        logger.info(f"[INFO] ===== Import détecté : {note_id} {filepath}")
        try:
            log_event_queue()
            new_path = process_get_note_type(filepath, note_id)
            logger.debug(f"[DEBUG] process_single_note fin get_note_type new_path : {new_path}")
            filepath = new_path
            base_folder = os.path.dirname(new_path)
            log_event_queue()
            logger.debug(f"[DEBUG] process_single_note base_folder : {base_folder}")
            new_path = rename_file(filepath, note_id)
            logger.debug(f"[DEBUG] process_single_note fin rename_file : {new_path}")
                                    
            updates = {
            'file_path': str(new_path)
            }
            logger.debug(f"[DEBUG] process_single_note mise à jour base de données : {updates}")
            update_obsidian_note(note_id, updates)
                     
            filepath = new_path
            if "gpt_import" in base_folder:
                logger.info(f"[INFO] Conversation GPT détectée, déplacement vers : {base_folder}")
                psn = True
                return psn
           
            logger.debug(f"[DEBUG] ===== ▶️ IMPORT NORMAL pour {filepath}")
            import_normal(filepath, note_id)
            
            logger.debug(f"[DEBUG] ===== process_single_note IMPORT NORMAL terminé")
            
            logger.debug(f"[DEBUG] ===== ▶️ REPRISE SYNTHESE pour {filepath}")
            process_import_syntheses(filepath, note_id)
            logger.info(f"[INFO] ===== Process Single Note : SYNTHESE terminée pour : {filepath}")
            log_event_queue()
           
            
        except Exception as e:
            logger.error(f"[ERREUR] Problème lors de l'import : {e}")

     # 1. Vérifier si c'est un déplacement
    if src_path is not None:
        logger.debug(f"[DEBUG] ===== Démarrage du process_single_note pour : Déplacement {src_path}")
        if not os.path.exists(filepath):
            logger.warning(f"[WARNING] Le fichier n'existe pas ou plus : {filepath}")
            return psn
        src_folder = os.path.dirname(src_path)
        logger.debug(f"[DEBUG] src_folder, type : {type(src_folder)} : {src_folder}")
        logger.debug(f"[DEBUG] UNCATEGORIZED_PATH, type : {type(UNCATEGORIZED_PATH)} : {UNCATEGORIZED_PATH}")
        logger.debug(f"[DEBUG] repr(src_folder)        : {repr(src_folder)}")
        logger.debug(f"[DEBUG] repr(UNCATEGORIZED_PATH): {repr(UNCATEGORIZED_PATH)}")
        # 1.1 Déplacement valide entre dossiers catégorisés (hors exclus)
        if is_folder_included(base_folder, include_types=['storage']) and \
        path_is_inside(UNCATEGORIZED_PATH, src_folder):
            logger.info(f"[INFO] Déplacement force categ : {src_path} --> {filepath}")
            force_categ_from_path(filepath, note_id)
            psn = True
            return psn
        
        elif path_is_inside(IMPORTS_PATH, base_folder):
            process_import(filepath, base_folder, note_id)
            psn = True
            return psn
                
        # Autres cas : déplacement ignoré
        else:
            logger.info(f"[INFO] ===== Déplacement ignoré : {src_path} --> {filepath}")
            return psn

    # 2. Sinon : Gérer les créations ou modifications
    else:
        if not os.path.exists(filepath):
            logger.warning(f"[WARNING] Le fichier n'existe pas ou plus : {filepath}")
            return psn
        logger.debug(f"[DEBUG] ===== Démarrage du process_single_note pour : CREATION - MODIFICATION")
        
        if path_is_inside(IMPORTS_PATH, base_folder):
            process_import(filepath, base_folder, note_id)
            psn = True
            return psn

        elif path_is_inside(GPT_IMPORT_DIR, base_folder):
            logger.info(f"[INFO] Split de la conversation GPT : {filepath}")
            try:
                logger.debug(f"[DEBUG] process_single_note : envoi vers gpt_import")
                process_import_gpt(filepath)
                psn = True
                return psn
            except Exception as e:
                logger.error(f"[ERREUR] Anomalie l'import gpt : {e}")
                return psn
        elif path_is_inside(GPT_OUTPUT_DIR, base_folder):
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
                process_class_gpt(filepath, note_id)
                logger.info(f"[INFO] Import terminé pour : {filepath}")
                psn = True
                return psn
            except Exception as e:
                logger.error(f"[ERREUR] Anomalie l'import gpt : {e}")
                return psn
        elif path_is_inside(GPT_TEST, base_folder):
            logger.info(f"[INFO] Import issu d'une conversation GPT TEST : {filepath}")
            try:
                process_class_gpt_test(filepath, note_id)
                logger.info(f"[INFO] Import terminé pour : {filepath}")
                psn = True
                return psn
            except Exception as e:
                logger.error(f"[ERREUR] Anomalie l'import gpt : {e}")
                return psn

        else:
            # Traitement pour les autres cas
            logger.debug(f"[DEBUG] Aucune correspondance pour : {filepath}")
            return psn
