import os
import re
from handlers.utils.extract_yaml_header import extract_yaml_header
from handlers.process.ollama import ollama_generate
from handlers.process.prompts import PROMPTS
from logger_setup import setup_logger
import logging

setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

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

def process_large_note(content, filepath, entry_type):
    logger.info(f"[DEBUG] entrée process_large_note")
    """
    Traite une note volumineuse en la découpant et en envoyant les blocs au modèle.
    """
    logger.debug(f"[DEBUG] Type de content avant extract_yaml_header : {type(content)}")
    logger.debug(f"[DEBUG] Contenu brut avant extract_yaml_header : {repr(content[:100])}")
    try:
        header_lines, content_lines = extract_yaml_header(content)
        content = content_lines
    
        # Étape 1 : Découpage en blocs optimaux
        #blocks = split_large_note(content, max_words=max_words)
        #blocks = split_large_note_by_titles(content)
        blocks = split_large_note_by_titles_and_words(content, word_limit=1000)
        print(f"[INFO] La note a été découpée en {len(blocks)} blocs.")
        logger.debug(f"[DEBUG] process_large_note : {len(blocks)} blocs")
        # Obtenir le dossier contenant le fichier
        base_folder = os.path.dirname(filepath)

                            
        processed_blocks = []
        for i, block in enumerate(blocks):
            print(f"[INFO] Traitement du bloc {i + 1}/{len(blocks)}...")
            logger.debug(f"[DEBUG] process_large_note : Traitement du bloc {i + 1}/{len(blocks)}")
            logger.debug(f"[DEBUG] process_large_note : prompt {entry_type}")
            prompt = PROMPTS[entry_type].format(content=block) 
            logger.debug(f"[DEBUG] process_large_note : {prompt[:50]}")
           
            logger.debug(f"[DEBUG] process_large_note : envoie vers ollama")    
            response = ollama_generate(prompt)
            logger.debug(f"[DEBUG] process_large_note : reponse {response[:50]}")
            
                    

                       
            logger.debug(f"[DEBUG] process_large_note : retour ollama, récupération des blocs")
            processed_blocks.append(response.strip())

        # Vérifie et corrige les titres après traitement
        final_blocks = ensure_titles_in_blocks(processed_blocks)
                
        

        # Étape 3 : Fusionner les blocs reformulés
        # Construire l'entête (sans saut de ligne final inutile)
        header_content = "\n".join(header_lines).strip()

        # Construire le contenu principal (final_blocks)
        body_content = "\n\n".join(final_blocks).strip()

        # Fusionner l'entête et le contenu principal avec un seul saut de ligne entre les deux
        final_content = f"{header_content}\n\n{body_content}" if header_content else body_content
        logger.debug(f"[DEBUG] process_large_note : {len(blocks)} blocs")
        print(f"\nTexte final recomposé :\n{final_content[:100]}...\n")  # Aperçu limité
        # Écriture de la note reformulée
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(final_content)
        print(f"[INFO] La note volumineuse a été traitée et enregistrée : {filepath}")
        logger.debug(f"[DEBUG] process_large_note : mis à jour du fichier")
        

    except Exception as e:
        print(f"[ERREUR] Impossible de traiter {filepath} : {e}")
        
        
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
    if matches and matches[0].start() > 0:
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