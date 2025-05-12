import os
from handlers.utils.config import UNCATEGORIZED_PATH, IMPORTS_PATH, GPT_IMPORT_DIR, GPT_OUTPUT_DIR, GPT_TEST, IMPORTS_TEST, Z_STORAGE_PATH
from handlers.process_imports.import_gpt import process_import_gpt, process_clean_gpt, process_class_gpt, process_class_gpt_test
from handlers.process_imports.import_normal import pre_import_normal
from handlers.process_imports.import_test import process_class_imports_test
from handlers.process_imports.import_syntheses import process_import_syntheses
from handlers.process.regen_utils import force_categ_from_path, regen_header, regen_synthese_from_archive
from handlers.sql.db_update_notes import update_obsidian_note
from handlers.sql.db_folders_utils import is_folder_included
from handlers.sql.db_categs_utils import categ_extract
from handlers.watcher.queue_manager import log_event_queue
from handlers.utils.paths import path_is_inside
from handlers.utils.divers import should_trigger_process
from handlers.utils.files import count_words
import logging

logger = logging.getLogger("obsidian_notes." + __name__)


def process_single_note(filepath, note_id, src_path=None):
    logger.debug(f"[DEBUG] ===== Démarrage du process_single_note pour : {filepath}")
    psn = False
    if not filepath.endswith(".md"):
        return psn
    # Obtenir le dossier contenant le fichier
    base_folder = os.path.dirname(filepath)
    log_event_queue()
    
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
            filepath = pre_import_normal(filepath, note_id)
            process_import_syntheses(filepath, note_id)
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
            filepath = pre_import_normal(filepath, note_id)
            process_import_syntheses(filepath, note_id)
            psn = True
            return psn

        elif path_is_inside(Z_STORAGE_PATH, base_folder):
            new_word_count = count_words(filepath=filepath)
            logger.debug(f"[DEBUG] new_word_count : {new_word_count}")
            triggered, status, parent_id = should_trigger_process(note_id, new_word_count)
            if triggered:
                logger.info(f"[process_single_note] Retraitement déclenché pour {note_id} (type: {status})")
                
                if status == "archive":
                    regen_header(note_id, filepath, parent_id)
                    regen_synthese_from_archive(note_id=parent_id)

                elif status == "synthesis":
                    regen_synthese_from_archive(note_id, filepath)
            else:
                logger.info(f"[process_single_note] Aucun traitement requis pour la note {note_id}")
        
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
            
        elif path_is_inside(IMPORTS_TEST, base_folder):
            logger.info(f"[INFO] Import issu de IMPORTS TEST : {filepath}")
            try:
                process_class_imports_test(filepath, note_id)
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
