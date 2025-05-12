from handlers.process.large_note import process_large_note
from handlers.process.standard_note import process_standard_note
from handlers.header.extract_yaml_header import extract_yaml_header
from handlers.utils.files import safe_write, join_yaml_and_body
import logging
import re
import shutil
import os
from pathlib import Path

logger = logging.getLogger("obsidian_notes." + __name__)

def process_class_imports_test(filepath, note_id):
    logger.info(f"[DEBUG] démarrage du process_clean_gpt test pour : {filepath}")
    destination_path = "/mnt/user/Documents/Obsidian/notes/Z_technical/output_tests_imports/"
    filename = os.path.basename(filepath)  # Extrait "fichier.txt"
    logger.debug(f"[DEBUG] filename : {filename}")
    #models_ollama = ["mixtral:8x7b-instruct-v0.1-q5_K_M", "mistral:7B-Instruct", "mixtral:latest", "mistral:latest", "llama3:8b-instruct-q6_K","llama-summary-gguf:latest", "qwen2.5:14b", "llama-chat-summary-3.2-3b:latest", "llama3.2-vision:11b", "deepseek-r1:14b", "llama3.2:latest", "llama3:latest"]  # Liste des modèles à tester
    models_ollama = ["mistral:7B-Instruct", "mistral:latest", "llama3:8b-instruct-q6_K","llama-summary-gguf:latest", "qwen2.5:7b", "llama-chat-summary-3.2-3b:latest", "llama3.2-vision:11b", "deepseek-r1:14b", "llama3.2:latest"]  # Liste des modèles à tester
    
    for model in models_ollama:
        logger.debug(f"[DEBUG] model : {model}")
        safe_model_name = re.sub(r'[\/:*?"<>|]', '_', model)
        new_filename1 = f"{os.path.splitext(filename)[0]}_{safe_model_name}{os.path.splitext(filename)[1]}"  # Ajoute model_llama avant l'extension
        destination_file1 = os.path.join(destination_path, new_filename1)
        new_file_path1 = shutil.copy(filepath, destination_file1)
        logger.debug(f"[DEBUG] new_file_path : {new_file_path1}")
                        
        process_large_note(new_file_path1,  entry_type="reformulation2", model_name=model, source="other1")
        new_filename2 = f"{os.path.splitext(new_filename1)[0]}_synt1{os.path.splitext(new_filename1)[1]}"
        destination_file2 = os.path.join(destination_path, new_filename2)
        new_file_path2 = shutil.copy(new_file_path1, destination_file2)
                        
        process_large_note(new_file_path2,  entry_type="divers", model_name=model, source="other2")
        new_filename3 = f"{os.path.splitext(new_filename1)[0]}_synt2{os.path.splitext(new_filename1)[1]}"
        destination_file3 = os.path.join(destination_path, new_filename3)
        new_file_path3 = shutil.copy(new_file_path2, destination_file3)
                        
        header_lines, _ = extract_yaml_header(new_file_path3)
        response = process_standard_note(new_file_path3, model_ollama=model, prompt_name="synthese2", source = "other3", resume_if_possible = True)
    
        # Traitement de la réponse
        if isinstance(response, str):
            body_content = response.strip()
        elif isinstance(response, list):
            body_content = "\n".join(block.strip() for block in response if isinstance(block, str)).strip()
        else:
            raise ValueError("La réponse d'Ollama n'est ni une chaîne ni une liste.")

        
        # Recomposition du contenu final
        header_content = "\n".join(header_lines).strip()
        final_content = join_yaml_and_body(header_lines, body_content)
        logger.debug(f"[DEBUG] Contenu final généré : {final_content[:2000]}...")

        # Écriture du fichier
        success = safe_write(new_file_path3, content=final_content)
        if not success:
            logger.error(f"[ERROR] Échec de l’écriture du fichier : {filepath}")
            return          
    
    return