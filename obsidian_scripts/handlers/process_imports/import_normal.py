from handlers.ollama.ollama_utils import large_or_standard_note
from handlers.process.headers import make_properties
from handlers.process.keywords import process_and_update_file
from handlers.process.get_type import process_get_note_type
from handlers.process.divers import rename_file
from handlers.sql.db_update_notes import update_obsidian_note
from handlers.utils.files import copy_file_with_date, read_note_content, count_words
from handlers.sql.db_get_linked_data import get_note_linked_data
from handlers.sql.db_get_linked_notes_utils import get_data_for_should_trigger
from handlers.utils.divers import prompt_name_and_model_selection, should_trigger_process
import os
import logging

logger = logging.getLogger("obsidian_notes." + __name__)

def pre_import_normal(filepath, note_id):
    logger.info(f"[INFO] ===== Import détecté : {note_id} {filepath}")
    logger.debug(f"[DEBUG] +++ ▶️ PRE IMPORT NORMAL pour {filepath}")
    try:
        new_path = process_get_note_type(filepath, note_id)
        logger.debug(f"[DEBUG] pre_import_normal fin get_note_type new_path : {new_path}")
        filepath = new_path
        base_folder = os.path.dirname(new_path)
        logger.debug(f"[DEBUG] pre_import_normal base_folder : {base_folder}")
        new_path = rename_file(filepath, note_id)
        logger.debug(f"[DEBUG] pre_import_normal fin rename_file : {new_path}")
                                
        updates = {
        'file_path': str(new_path)
        }
        logger.debug(f"[DEBUG] pre_import_normal mise à jour base de données : {updates}")
        update_obsidian_note(note_id, updates)
                    
        filepath = new_path
        if "gpt_import" in base_folder:
            logger.info(f"[INFO] Conversation GPT détectée, déplacement vers : {base_folder}")
            psn = True
            return psn
        
        logger.debug(f"[DEBUG] === ⏹️ FIN PRE IMPORT NORMAL pour {filepath}")
        filepath = import_normal(filepath, note_id)
        return filepath
    except Exception as e:
            logger.error(f"[ERREUR] Problème lors de l'import : {e}")

def import_normal(filepath, note_id):
    logger.debug(f"[DEBUG] démarrage du process_import_normal pour : {filepath}")
    logger.debug(f"[DEBUG] +++ ▶️ IMPORT NORMAL pour {filepath}")
    try:
        sav_dir = os.getenv('SAV_PATH')
        copy_file_with_date(filepath, sav_dir)
        # prompt_key = "reformulation"
        # large_or_standard_note(
        #     filepath=filepath, 
        #     source="reformulation", 
        #     process_mode="large_note", 
        #     prompt_key=prompt_key, 
        #     note_id=note_id,
        #     word_limit=2000
        #     )                
        
        # word_count = count_words(filepath=filepath)
        # updates = {
        # 'word_count': word_count
        # }
        # update_obsidian_note(note_id, updates)
        # logger.debug(f"[DEBUG] import_normal :retour du process_large {filepath}")
        #logger.debug(f"[DEBUG] import_normal : import normal envoi vers process & update {filepath}")
        #process_and_update_file(filepath)
        logger.debug(f"[DEBUG] import_normal : import normal envoi vers make_properties {filepath}")
        make_properties(filepath, note_id, status = "archive")
        logger.debug(f"[DEBUG] === ⏹️ FIN IMPORT NORMAL pour {filepath}")
        return filepath
        
    except Exception as e:
        print(f"[ERREUR] Impossible de traiter {filepath} : {e}")