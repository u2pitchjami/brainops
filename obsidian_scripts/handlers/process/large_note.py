import os
import re
from handlers.header.extract_yaml_header import extract_yaml_header
from handlers.ollama.ollama import call_ollama_with_retry, OllamaError
from handlers.ollama.prompts import PROMPTS
from handlers.utils.files import safe_write, clean_content, join_yaml_and_body
from handlers.sql.db_temp_blocs import (
    get_existing_bloc,
    insert_bloc,
    update_bloc_response,
    mark_bloc_as_error
)
from logger_setup import setup_logger
import logging

setup_logger("large_note", logging.DEBUG)
logger = logging.getLogger("large_note")

def determine_max_words(filepath):
    """Détermine dynamiquement la taille des blocs en fonction du fichier."""
    if "gpt_import" in filepath.lower():
        return 1000  # Petits blocs pour les fichiers importants
    else:
        return 1000  # Taille par défaut

def split_large_note(content, max_words=1000):
    logger.debug(f"[DEBUG] entrée split_large_note")
    """
    Découpe une note en blocs de taille optimale (max_words).
    """
    
    words = content.split()
    blocks = []
    current_block = []

    for word in words:
        current_block.append(word)
        if len(current_block) >= max_words:
            blocks.append(" ".join(current_block))
            current_block = []

    # Ajouter le dernier bloc s'il reste des mots
    if current_block:
        blocks.append(" ".join(current_block))

    return blocks

def process_large_note(
    filepath,
    entry_type,
    word_limit=1000,
    split_method="titles_and_words",
    write_file=True,
    send_to_model=True,
    model_name=None,
    custom_prompts=None,
    persist_blocks=True,
    resume_if_possible=True,
    source="normal"
):
    """
    Fonction unique pour traiter une note volumineuse.
    Si persist_blocks=True, chaque bloc est stocké en base dans `obsidian_temp_blocks`
    """
    
    setup_logger("process_large_note", logging.DEBUG)
    logger = logging.getLogger("process_large_note")

    logger.info(f"[DEBUG] Entrée process_large_note pour {filepath}")
    model_ollama = model_name or os.getenv('MODEL_LARGE_NOTE')

    try:
        header_lines, content_lines = extract_yaml_header(filepath)
        logger.debug(f"[DEBUG] Split_method : {split_method}")
        content = clean_content(content_lines)
        
        model = model_ollama
        
        # Choix de la méthode de split
        if split_method == "titles_and_words":
            blocks = split_large_note_by_titles_and_words(content, word_limit=word_limit)
        elif split_method == "titles":
            blocks = split_large_note_by_titles(content)
        elif split_method == "words":
            blocks = split_large_note(content, max_words=word_limit)
        else:
            logger.error(f"[ERROR] Méthode de split inconnue : {split_method}")
            return None

        logger.debug(f"[DEBUG] Split_method : {split_method} en {len(blocks)} blocs")
        logger.info(f"[INFO] Note découpée en {len(blocks)} blocs")

        processed_blocks = []
       
        for i, block in enumerate(blocks):
            logger.info(f"[INFO] Bloc {i + 1}/{len(blocks)}")
            block_index = i
            # Si persisté, vérifie si déjà traité
            if persist_blocks:
                try:
                    row = get_existing_bloc(filepath, block_index, entry_type, model, split_method, word_limit, source)

                    if row:
                        response, status = row
                        if status == "processed" and resume_if_possible:
                            logger.debug(f"[DEBUG] Bloc {i} déjà traité, skip")
                            processed_blocks.append(response.strip())
                            continue
                    else:
                        insert_bloc(filepath, block_index, content, entry_type, model, split_method, word_limit, source)
                
                except Exception as e:
                    logger.error(f"[ERROR] Insertion bloc {i} échouée pour {filepath} : {e}")
                    
            # Traitement du bloc (ou simple passage)
            response = block

            if send_to_model:
                if custom_prompts:
                    if i == 0 and "first" in custom_prompts:
                        prompt = custom_prompts["first"].format(content=block)
                    elif i == len(blocks) - 1 and "last" in custom_prompts:
                        prompt = custom_prompts["last"].format(content=block)
                    else:
                        prompt = custom_prompts.get("middle", PROMPTS[entry_type]).format(content=block)
                else:
                    prompt = PROMPTS[entry_type].format(content=block)

                try:
                    response = call_ollama_with_retry(prompt, model_ollama)
                except OllamaError:
                    logger.error(f"[ERROR] Échec du bloc {i+1}, saut...")
                    if persist_blocks:
                        mark_bloc_as_error(filepath, block_index)
                    continue

            if persist_blocks:
                update_bloc_response(filepath, block_index, response, source, status="processed")

            processed_blocks.append(response.strip())

        
        final_blocks = ensure_titles_in_blocks(processed_blocks)
        header_content = "\n".join(header_lines).strip()
        body_content = "\n\n".join(final_blocks).strip()
        final_content = join_yaml_and_body(header_lines, body_content)

        if write_file:
            success = safe_write(filepath, content=final_content)
            if not success:
                logger.error(f"[main] Problème lors de l’écriture de {filepath}")
            else:
                logger.info(f"[INFO] Note enregistrée : {filepath}")
                logger.debug(f"[DEBUG] Contenu Final : {final_content}")
        else:
            return final_content

    except Exception as e:
        logger.error(f"[ERREUR] Traitement de {filepath} échoué : {e}")
        return None

        
        
def split_large_note_by_titles(content):
    """
    Découpe une note en blocs basés sur les titres (#, ##, ###), 
    en gérant une éventuelle introduction avant le premier titre.
    Chaque bloc contient le titre et son contenu concaténés.
    """
    # Expression régulière pour détecter les titres
    title_pattern = r'(?m)^(\#{1,3})\s+.*$'
    
    # Trouver toutes les correspondances (positions et contenu)
    matches = list(re.finditer(title_pattern, content))
    logger.debug(f"[DEBUG] Titres trouvés : {[match.group() for match in matches]}")
    
    blocks = []
    last_pos = 0  # Position de début du dernier bloc
    
    # Cas 1 : S'il y a des titres
    if matches:
        # Gestion de l'introduction avant le premier titre
        if matches[0].start() > 0:
            intro = content[:matches[0].start()].strip()
            logger.debug(f"[DEBUG] Introduction détectée : {intro[:50]}")
            if intro:
                blocks.append(f"## **Introduction**\n\n{intro}")
        
        # Découpage basé sur les titres
        for i, match in enumerate(matches):
            title = match.group().strip()  # Le titre complet (ex. : "# Section")
            start_pos = match.end()  # Fin du titre
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            
            # Extraire le contenu de la section
            section_content = content[start_pos:end_pos].strip()
            blocks.append(f"{title}\n{section_content}")
    
    # Cas 2 : Aucun titre trouvé, tout le contenu est une introduction
    else:
        intro = content.strip()
        logger.debug(f"[DEBUG] Aucun titre trouvé, tout le contenu est traité comme une introduction : {intro[:50]}")
        if intro:
            blocks.append(f"## **Introduction**\n\n{intro}")
    
    return blocks

def split_large_note_by_titles_and_words(content, word_limit=1000):
    """
    Découpe une note en blocs basés sur les titres (#, ##, ###),
    et regroupe les sections en paquets de 1000 mots maximum.
    Chaque groupe conserve les titres et leurs contenus sans rupture.
    """
    # Expression régulière pour détecter les titres
    title_pattern = r'(?m)^(\#{1,3})\s+.*$'
    
    # Trouver toutes les correspondances (positions et contenu)
    matches = list(re.finditer(title_pattern, content))
    logger.debug(f"[DEBUG] Titres trouvés : {[match.group() for match in matches]}")

    blocks = []
    temp_block = []
    word_count = 0

    def add_block():
        """Ajoute le bloc actuel à la liste des résultats."""
        if temp_block:
            blocks.append("\n\n".join(temp_block))
            temp_block.clear()

    # Gestion de l'introduction avant le premier titre
    last_pos = 0
    if matches:
        if matches[0].start() > 0:
            intro = content[:matches[0].start()].strip()
            logger.debug(f"[DEBUG] Introduction détectée : {intro[:50]}")
            if intro:
                temp_block.append(f"## **Introduction**\n\n{intro}")
                word_count += len(intro.split())

        # Découpage basé sur les titres
        for i, match in enumerate(matches):
            title = match.group().strip()  # Le titre complet (ex. : "# Section")
            start_pos = match.end()  # Fin du titre
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)

            # Extraire le contenu de la section
            section_content = content[start_pos:end_pos].strip()
            section_word_count = len(section_content.split())

            # Vérifier si l'ajout dépasse la limite de mots
            if word_count + section_word_count > word_limit:
                add_block()  # On sauvegarde le bloc actuel
                word_count = 0  # On reset le compteur de mots

            # Ajouter le titre et son contenu au bloc courant
            temp_block.append(f"{title}\n{section_content}")
            word_count += section_word_count

        # Ajouter le dernier bloc restant
        add_block()
        
    else:
        intro = content.strip()
        logger.debug(f"[DEBUG] Aucun titre trouvé, tout le contenu est traité comme une introduction : {intro[:50]}")
        if intro:
            blocks.append(f"## **Introduction**\n{intro}")

    return blocks

def ensure_titles_in_blocks(blocks, default_title="# Introduction"):
    """
    Vérifie que chaque bloc commence par un titre Markdown valide.
    Ajoute un titre par défaut si nécessaire.
    """
    processed_blocks = []
    
    for i, block in enumerate(blocks):
        # Vérifier si le bloc commence par un titre Markdown
        if not block.strip().startswith("#"):
            logger.debug(f"[DEBUG] Bloc sans titre détecté : {block[:30]}...")
            # Ajouter un titre par défaut
            title = default_title if i == 0 else f"# Section {i + 1}"
            block = f"{title}\n{block.strip()}"
            logger.debug(f"[DEBUG] Block : {block[:30]}...")
        processed_blocks.append(block)
    
    return processed_blocks

def ensure_titles_in_initial_content(blocks, default_title="# Introduction"):
    """
    Vérifie que le contenu initial commence par un titre Markdown valide.
    Ajoute un titre par défaut si nécessaire.
    """
    processed_blocks = []
    
    for i, block in enumerate(blocks):
        # Vérifier si le bloc commence par un titre Markdown
        if not block.strip().startswith("#"):
            logger.debug(f"[DEBUG] Bloc sans titre détecté : {block[:30]}...")
            # Ajouter un titre par défaut
            title = default_title if i == 0 else f"# Section {i + 1}"
            block = f"{title}\n{block.strip()}"
            logger.debug(f"[DEBUG] Block : {block[:30]}...")
        processed_blocks.append(block)
    
    return processed_blocks