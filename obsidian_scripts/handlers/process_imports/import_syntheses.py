from handlers.process.large_note import process_large_note
from handlers.process.standard_note import process_standard_note
from handlers.process.divers import copy_to_archive
from handlers.header.extract_yaml_header import extract_yaml_header
from handlers.process.headers import make_properties
from handlers.sql.db_get_linked_notes_utils import get_subcategory_prompt
from handlers.utils.files import safe_write, join_yaml_and_body
from handlers.utils.divers import make_relative_link
from logger_setup import setup_logger
import logging
import os

setup_logger("import_synthese", logging.DEBUG)
logger = logging.getLogger("import_synthese")

def process_import_syntheses(filepath, note_id):
    logger.info(f"[INFO] Génération de la synthèse pour : {filepath}")
    logger.debug(f"[DEBUG] démarrage du process_import_synthèse pour : {note_id}")
    try:
        
        logger.debug(f"[DEBUG] process_import_syntheses lancement copy_to_archives")
                
        original_path = copy_to_archive(filepath, note_id)
        original_path = make_relative_link(original_path, filepath)
        logger.debug(f"[DEBUG] process_import_syntheses : original_path {original_path}")
        model_ollama = os.getenv('MODEL_SYNTHESIS1')
        make_pre_synthese(filepath, note_id, model_ollama, source="synthesis")
        
        model_ollama = os.getenv('MODEL_SYNTHESIS2')
        
        make_syntheses(filepath, note_id, model_ollama, original_path)        
        #logger.debug(f"[DEBUG] process_import_syntheses : envoi vers process & update {filepath}")
        #process_and_update_file(filepath)
        logger.debug(f"[DEBUG] process_import_syntheses : envoi vers make_properties {filepath} ")
        make_properties(filepath, note_id, status = "synthesis")
        logger.info(f"[INFO] Synthèse terminée pour {filepath}")
        return
        
      
    except Exception as e:
        print(f"[ERREUR] Impossible de traiter {filepath} : {e}")    

def make_pre_synthese(
    filepath,
    note_id=None,
    model_ollama=None,
    word_limit=1000,
    split_method="titles_and_words",
    write_file=True,
    send_to_model=True,
    custom_prompts=None,
    persist_blocks=True,
    resume_if_possible=True,
    source="normal"
):
    logger.debug(f"[DEBUG] Démarrage de make_pre_synthese pour {filepath}")
    try:
        # Extraire le contenu sans le YAML (utile si on veut le passer à l’IA à la main)
       
        prompt_name = get_subcategory_prompt(note_id) if note_id else "divers"
        logger.debug(f"[DEBUG] Prompt utilisé : {prompt_name}")

        response = process_large_note(
            filepath=filepath,
            entry_type=prompt_name,
            word_limit=word_limit,
            split_method=split_method,
            write_file=write_file,
            send_to_model=send_to_model,
            model_name=model_ollama,
            custom_prompts=custom_prompts,
            persist_blocks=persist_blocks,
            resume_if_possible=resume_if_possible,
            source=source
        )

        
        return response

    except Exception as e:
        logger.error(f"[ERREUR] make_pre_synthese : Impossible de traiter {filepath} : {e}")
        return ""
 
        
def make_syntheses(filepath: str, note_id: str, model_ollama: str, original_path: str):
    logger.debug(f"[DEBUG] Démarrage de make_syntheses pour {filepath}")

    try:
        # Lecture + séparation header / contenu
        header_lines, _ = extract_yaml_header(filepath)
        
        # Préparation du prompt
        prompt_name = "synthese2"
        response = process_standard_note(filepath, model_ollama, prompt_name, source = "synthesis2", resume_if_possible = True)
        
        # Traitement de la réponse
        if isinstance(response, str):
            body_content = response.strip()
        elif isinstance(response, list):
            body_content = "\n".join(block.strip() for block in response if isinstance(block, str)).strip()
        else:
            raise ValueError("La réponse d'Ollama n'est ni une chaîne ni une liste.")

        # Construction du lien vers la note originale
        original_link = f"[[{original_path}|Voir la note originale]]"
        logger.debug(f"[DEBUG] Lien original : {original_link}")

        # Recomposition du contenu final
        body_with_link = f"{original_link}\n\n{body_content.strip()}"
        header_content = "\n".join(header_lines).strip()
        final_content = join_yaml_and_body(header_lines, body_with_link)
        logger.debug(f"[DEBUG] Contenu final généré : {final_content[:2000]}...")

        # Écriture du fichier
        success = safe_write(filepath, content=final_content)
        if not success:
            logger.error(f"[ERROR] Échec de l’écriture du fichier : {filepath}")
            return

        logger.info(f"[INFO] Note synthétisée enregistrée : {filepath}")
    except Exception as e:
        logger.exception(f"[ERREUR] Échec dans make_syntheses pour {filepath} : {e}")
   
