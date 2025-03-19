from handlers.process.large_note import process_large_note
from handlers.process.large_note_gpt import process_large_note_gpt_test
from handlers.process.ollama import call_ollama_with_retry, OllamaError
from handlers.process.headers import make_properties
from handlers.process.keywords import process_and_update_file
from handlers.utils.divers import read_note_content, clean_content
from handlers.utils.files import copy_file_with_date, move_file_with_date, make_relative_link, copy_to_archives
from handlers.process.prompts import PROMPTS
from datetime import datetime
from logger_setup import setup_logger
import logging
import re
import shutil
import os
from pathlib import Path
from handlers.process_imports.import_syntheses import process_import_syntheses

setup_logger("obsidian_notes", logging.DEBUG)
logger = logging.getLogger("obsidian_notes")

def process_clean_gpt(filepath):
    logger.debug(f"[DEBUG] démarrage du process_clean_gpt pour : {filepath}")
    sav_dir = Path(os.getenv('SAV_PATH'))
    copy_file_with_date(filepath, sav_dir)
    content = read_note_content(filepath)
        
        
    logger.debug(f"[DEBUG] process_clean_gpt : envoie vers clean content {filepath}")
    content = clean_content(content, filepath)
    # entry_type = "gpt_reformulation"
    # logger.debug(f"[DEBUG] process_clean_gpt : prompt {entry_type}")
    # prompt = PROMPTS[entry_type].format(content=content) 
    # logger.debug(f"[DEBUG] process_clean_gpt : {prompt[:50]}")

    # logger.debug(f"[DEBUG] process_clean_gpt : envoie vers ollama")    
    # response = call_ollama_with_retry(prompt)
    # logger.debug(f"[DEBUG] process_clean_gpt : reponse {response[:50]}")
    
    with open(filepath, 'w', encoding='utf-8') as file:
            file.write(content)
        
def process_import_gpt(filepath):
    """
    Traite toutes les notes dans gpt_import, en les découpant si la ligne 1 contient un titre.
    """
    logger.debug(f"[DEBUG] démarrage du process_import_gpt pour : {filepath}")
    # Définition des chemins sur le serveur Unraid
    gpt_import_dir = Path(os.getenv('GPT_IMPORT_DIR'))
    gpt_output_dir = Path(os.getenv('GPT_OUTPUT_DIR')) 
    
    # Vérifier et créer les dossiers si nécessaire
    if not gpt_import_dir.exists():
        gpt_import_dir.mkdir(parents=True, exist_ok=True)
        print(f"Création du dossier gpt_import à : {gpt_import_dir}")
    if not gpt_output_dir.exists():
        gpt_output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Création du dossier gpt_output à : {gpt_output_dir}")
            
    gpt_import_dir = Path(gpt_import_dir)
    logger.debug(f"[DEBUG] process_import_gpt input : {gpt_import_dir}")
    gpt_output_dir = Path(gpt_output_dir)
    gpt_output_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"[DEBUG] process_import_gpt output : {gpt_output_dir}")
    processed_count = 0
    ignored_count = 0


    for file in gpt_import_dir.glob("*.md"):
        logger.debug(f"[DEBUG] process_import_gpt : file : {file}")
        if is_ready_for_split(file):  # Vérifie si la première ligne est prête
            logger.info(f"Traitement du fichier : {file}")
            logger.debug(f"[DEBUG] process_import_gpt : ready_for split TRUE {file}")
            try:
                process_gpt_conversation(file, gpt_output_dir, prefix="GPT_Conversation")
                processed_count += 1
            except Exception as e:
                logger.error(f"Erreur lors du traitement du fichier {file} : {e}")
            
            #mouvement :
            move_file_with_date(file, "/mnt/user/Documents/Obsidian/notes/.sav/")
            logger.debug(f"[DEBUG] process_import_gpt : déplacement ")
        else:
            logger.info(f"Note ignorée, pas prête pour le découpage : {file}")
            ignored_count += 1
    logger.info(f"Fichiers traités : {processed_count}")
    logger.info(f"Fichiers ignorés : {ignored_count}")       


def is_ready_for_split(filepath):
    """
    Vérifie si la première ligne d'une note contient un titre #.
    """
    logger.debug(f"[DEBUG] is_ready_for_split {filepath}")
    with open(filepath, "r", encoding="utf-8") as file:
        first_line = file.readline().strip()  # Lire la première ligne et enlever les espaces
        logger.debug(f"[DEBUG] is_ready_for_split {first_line}")
    return first_line.startswith("# ")  # Retourne True si la ligne commence par #

def process_gpt_conversation(filepath, output_dir, prefix="GPT_Conversation"):
    """
    Traite une conversation GPT uniquement si la première ligne est un titre.
    """
    logger.debug(f"[DEBUG] process_gpt_conversation {filepath}")
    if not is_ready_for_split(filepath):
        logger.debug(f"[DEBUG] process_gpt_conversation re test is NOT ready for split")
        print(f"Note ignorée, pas de titre en ligne 1 : {filepath}")
        return  # Ignorer la note si pas prête

    with open(filepath, "r", encoding="utf-8") as file:
        content = file.read()

    # Découper la conversation en sections
    logger.debug(f"[DEBUG] process_gpt_conversation ENVOI VERS split_gpt_conversation")
    sections = split_gpt_conversation(content)

    # Créer le répertoire de sortie si nécessaire
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for title, body in sections:
        # Générer un nom de fichier à partir du titre
        safe_title = re.sub(r'[^\w\s-]', '_', title)  # Remplacer les caractères spéciaux
        filename = f"{prefix}_{safe_title}.md"
        logger.debug(f"[DEBUG] process_gpt_conversation filename {filename}")
        filepath = output_dir / filename

        # Sauvegarder la section
        with open(filepath, "w", encoding="utf-8") as file:
            file.write(f"# {title}\n\n{body}")
        print(f"Section sauvegardée : {filepath}")
        
def split_gpt_conversation(content):
    """
    Découpe une conversation GPT en sections basées sur les titres de niveau #.
    """
    logger.debug(f"[DEBUG] split_gpt_conversation")
    # Utiliser une regex pour détecter les titres de niveau #
    sections = re.split(r'(?m)^# (.+)$', content)
    logger.debug(f"[DEBUG] split_gpt_conversation : sections : {sections[:5]}")
    # La première section (avant le premier titre) peut être ignorée si vide
    results = []
    for i in range(1, len(sections), 2):  # Sauter par 2 : Titre / Contenu
        title = sections[i].strip()
        body = sections[i + 1].strip()
        results.append((title, body))
    
    return results

def process_class_gpt(filepath, category, subcategory):
    logger.info(f"[DEBUG] démarrage du process_clean_gpt pour : {filepath}")
    
    content = read_note_content(filepath)
    cleaned_content = clean_content(content, filepath)
    content = cleaned_content    
    process_large_note(content, filepath, "gpt_reformulation")
   
    content = cleaned_content    
    
    process_large_note(content, filepath, "gpt_reformulation")
    #content = read_note_content(filepath)
   # process_large_note(content, filepath, "test_gpt")
    process_and_update_file(filepath)
    content = read_note_content(filepath)
    logger.debug(f"[DEBUG] content : {content}")
    
    
    make_properties(content, filepath, category, subcategory, status = "archive")
    #process_import_syntheses(filepath, category, subcategory)
    return

def process_class_gpt_test(filepath):
    logger.info(f"[DEBUG] démarrage du process_clean_gpt test pour : {filepath}")
    destination_path = "/mnt/user/Documents/Obsidian/notes/Z_technical/test_output_gpt/"
    filename = os.path.basename(filepath)  # Extrait "fichier.txt"
    logger.debug(f"[DEBUG] filename : {filename}")
    #models_ollama = ["mixtral:8x7b-instruct-v0.1-q5_K_M", "mistral:7B-Instruct", "mixtral:latest", "mistral:latest", "llama3:8b-instruct-q6_K","llama-summary-gguf:latest", "qwen2.5:14b", "llama-chat-summary-3.2-3b:latest", "llama3.2-vision:11b", "deepseek-r1:14b", "llama3.2:latest", "llama3:latest"]  # Liste des modèles à tester
    models_ollama = ["deepseek-r1:8b"]  # Liste des modèles à tester
    
    for model in models_ollama:
        logger.debug(f"[DEBUG] model : {model}")
        safe_model_name = re.sub(r'[\/:*?"<>|]', '_', model)
        new_filename = f"{os.path.splitext(filename)[0]}_{safe_model_name}{os.path.splitext(filename)[1]}"  # Ajoute model_llama avant l'extension
        destination_file = os.path.join(destination_path, new_filename)
        new_file_path = shutil.copy(filepath, destination_file)
        logger.debug(f"[DEBUG] new_file_path : {new_file_path}")
        content = read_note_content(new_file_path)
        cleaned_content = clean_content(content, new_file_path)
        content = cleaned_content
        
        process_large_note_gpt_test(content, new_file_path, model)
        
        # destination_path1 = "/mnt/user/Documents/Obsidian/Agora/01/"
        # shutil.copy(new_file_path, destination_path1)
        # print(f"Fichier copié avec succès : {destination_path1}")
        # content = cleaned_content    
        # destination_path2 = "/mnt/user/Documents/Obsidian/Agora/02/"
        # shutil.copy(new_file_path, destination_path2)
        # print(f"Fichier copié avec succès : {destination_path2}")
        # process_large_note_gpt_test(content, new_file_path, model)
        
    
    return