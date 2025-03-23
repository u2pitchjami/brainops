from handlers.process.ollama import call_ollama_with_retry, OllamaError
from handlers.process.large_note import process_large_note
from handlers.utils.extract_yaml_header import extract_yaml_header
from handlers.process.headers import make_properties
from handlers.process.keywords import process_and_update_file
from handlers.utils.sql_helpers import get_subcategory_prompt
from handlers.utils.divers import read_note_content, clean_content
from handlers.utils.files import copy_file_with_date, move_file_with_date, make_relative_link, copy_to_archives, safe_write
from handlers.process.prompts import PROMPTS
from datetime import datetime
from logger_setup import setup_logger
import logging
import os

setup_logger("import_synthese", logging.DEBUG)
logger = logging.getLogger("import_synthese")

def process_import_syntheses(filepath, note_id):
    logger.info(f"[INFO] Génération de la synthèse pour : {filepath}")
    logger.debug(f"[DEBUG] démarrage du process_import_synthèse pour : {note_id}")
    try:
        content = read_note_content(filepath)
       #with open(filepath, "r", encoding="utf-8") as file:
       #     content = file.readlines()
        logger.debug(f"[DEBUG] Contenu brut : {repr(content[:100])}...")  # Limité pour éviter de surcharger
        logger.debug(f"[DEBUG] Type après lecture : {type(content)}")
        
        
        logger.debug(f"[DEBUG] process_import_syntheses lancement copy_to_archives")
                
        new_path = copy_to_archives(filepath)
        original_path = new_path
        original_path = make_relative_link(original_path, link_text="Voir la note originale")
        logger.debug(f"[DEBUG] process_import_syntheses : original_path {original_path}")
        
        
        header_lines, content_lines = extract_yaml_header(content)
        content = content_lines
        logger.debug(f"[DEBUG] process_import_synthese : original_path {original_path}")              
        make_syntheses(filepath, content, header_lines, note_id, original_path)        
        #logger.debug(f"[DEBUG] process_import_syntheses : envoi vers process & update {filepath}")
        #process_and_update_file(filepath)
        logger.debug(f"[DEBUG] process_import_syntheses : envoi vers make_properties {filepath} ")
        make_properties(content, filepath, note_id, status = "synthesis")
        logger.info(f"[INFO] Synthèse terminée pour {filepath}")
        return
        
      
    except Exception as e:
        print(f"[ERREUR] Impossible de traiter {filepath} : {e}")    
        
def make_syntheses(filepath, content, header_lines, note_id, original_path):
    logger.debug(f"[DEBUG] démarrage de make_synthèse pour {filepath}")
    model_ollama = os.getenv('MODEL_SYNTHESIS1')
    model_ollama2 = os.getenv('MODEL_SYNTHESIS2')
    try:
        prompt_name = get_subcategory_prompt(note_id)
            
        logger.debug(f"[DEBUG] make_syntheses : prompt : {prompt_name}")
        prompt = PROMPTS[prompt_name].format(content=content) 
        #logger.debug(f"[DEBUG] make_syntheses : prompt : {prompt}")
                 
        logger.debug(f"[DEBUG] make_syntheses : envoie vers ollama")
          
        body_content = process_large_note(content, filepath, entry_type=prompt_name, write_file=True)
        #response = call_ollama_with_retry(prompt, model_ollama)
        #logger.debug(f"[DEBUG] make_syntheses : type de response : {type(response)}")
        #logger.debug(f"[DEBUG] make_syntheses : contenu de response : {response[:50]}")
        
        
        prompt_name = "synthese2"
        logger.debug(f"[DEBUG] make_syntheses : prompt : {prompt_name}")
        prompt = PROMPTS[prompt_name].format(content=body_content) 
        logger.debug(f"[DEBUG] make_syntheses : prompt : {prompt}")            
        logger.debug(f"[DEBUG] make_syntheses : envoie vers ollama")    
        try:  
            response = call_ollama_with_retry(prompt, model_ollama2)
            logger.debug(f"[DEBUG] make_syntheses : type de response : {type(response)}")
            logger.debug(f"[DEBUG] make_syntheses : contenu de response : {response[:50]}")
        except OllamaError:
            logger.error("[ERROR] Import annulé.")
        
        # Étape 3 : Fusionner les blocs reformulés
        header_content = "\n".join(header_lines).strip()
        logger.debug(f"[DEBUG] make_syntheses header_content : {header_content[:50]}")
        # Construire le contenu principal
        if isinstance(response, str):
            body_content = response.strip()
        elif isinstance(response, list):
            body_content = "\n\n".join(block.strip() for block in response if isinstance(block, str)).strip()
        else:
            raise ValueError("Response de call_ollama_with_retry n'est ni une chaîne ni une liste valide")
        logger.debug(f"[DEBUG] make_syntheses body_content : {body_content[:50]}")
        # Construire le lien vers la note originale
        logger.debug(f"[DEBUG] process_import_synthese : original_path {original_path}") 
        original_link = f"[Voir la note originale]({original_path})"
        logger.debug(f"[DEBUG] process_import_synthese : original_link {original_link}") 
        # Ajouter le lien au début du corps principal
        body_content = f"{original_path}\n\n{body_content}"

        # Fusionner l'entête et le contenu principal
        final_content = f"{header_content}\n\n{body_content}" if header_content else body_content
        logger.debug(f"[DEBUG] make_syntheses final_content : {final_content[:50]}")
        print(f"\nTexte final recomposé :\n{final_content[:50]}...\n")  # Aperçu limité
        # Écriture de la note reformulée
        success = safe_write(filepath, content=final_content)
        if not success:
            logger.error(f"[main] Problème lors de l’écriture sécurisée de {filepath}")
        
        print(f"[INFO] make_syntheses a été traitée et enregistrée : {filepath}")
        logger.debug(f"[DEBUG] make_syntheses : mis à jour du fichier")
        return
    except Exception as e:
        print(f"[ERREUR] make_syntheses : Impossible de traiter : {e}")    
