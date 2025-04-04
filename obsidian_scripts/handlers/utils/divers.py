from pathlib import Path
from logger_setup import setup_logger
import logging

setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

def make_relative_link(original_path, filepath):
    """
    Convertit un chemin absolu en lien Markdown relatif.
    
    :param original_path: Chemin absolu du fichier cible
    :param base_path: Répertoire de base pour générer des liens relatifs
    :param link_text: Texte visible pour le lien (par défaut : "Voir la note originale")
    :return: Lien Markdown au format [texte](chemin_relatif)
    """
    logger.debug("[DEBUG] entrée make_relative_link")
        
    
    original_path = Path(original_path)
    synt_path = Path(filepath).resolve()
    synt_path = synt_path.parent
    
     # Vérifie que le fichier appartient au répertoire de base
    if synt_path in original_path.parents:
        # Extraire le chemin relatif
        relative_path = original_path.relative_to(synt_path)
        logger.debug("[DEBUG] relative_path : %s", relative_path)
        return relative_path
    else:
        raise ValueError(f"Le fichier {original_path} est hors du répertoire de base {synt_path}")
    