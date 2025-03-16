import re
import os
from logger_setup import setup_logger
import logging

setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

def count_words(content):
    logger.debug(f"[DEBUG] def count_word")
    return len(content.split())

def clean_content(content, filepath):
    logger.debug(f"[DEBUG] clean_content : {filepath}")
    """
    Nettoie le contenu avant de l'envoyer au modèle.
    - Conserve les blocs de code Markdown (``` ou ~~~).
    - Supprime les balises SVG ou autres éléments non pertinents.
    - Élimine les lignes vides ou répétitives inutiles.
    """
    # Supprimer les balises SVG ou autres formats inutiles
    content = re.sub(r'<svg[^>]*>.*?</svg>', '', content, flags=re.DOTALL)

    # Supprimer les lignes vides multiples
    #content = re.sub(r'\n\s*\n', '\n', content)

    # Vérifier le type et l'état final
    logger.debug(f"[DEBUG] Après nettoyage : {type(content)}, longueur = {len(content)}")
    
    return content.strip()

def read_note_content(filepath):
    """Lit le contenu d'une note depuis le fichier."""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            logger.debug(f"[DEBUG] lecture du fichier {filepath}")
            
            return file.read()
    except Exception as e:
        logger.error(f"[ERREUR] Impossible de lire le fichier {filepath} : {e}")
        return None