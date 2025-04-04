import unicodedata
import os
import re
from logger_setup import setup_logger
from datetime import datetime
import logging
setup_logger("sanitize", logging.DEBUG)
logger = logging.getLogger("sanitize")

def normalize_full_path(path):
    """ Nettoie un chemin de fichier (slashs, accents, espaces, etc.) """
    path = unicodedata.normalize("NFC", path)
    path = path.strip()
    return os.path.normpath(path)

def sanitize_created(created):
    try:
        if isinstance(created, datetime):
            return created.strftime('%Y-%m-%d')
        elif isinstance(created, str) and created.strip():
            return created.strip()
        else:
            return datetime.now().strftime('%Y-%m-%d')
    except Exception as e:
        logging.error(f"Erreur dans sanitize_created : {e}")
        return datetime.now().strftime('%Y-%m-%d')
    
def sanitize_yaml_title(title: str) -> str:
    """ Nettoie le titre pour éviter les erreurs YAML """
    if not title:
        return "Untitled"

    logger.debug("[DEBUG] avant sanitize title %s", title)
    
    # 🔥 Normalise les caractères Unicode
    title = unicodedata.normalize("NFC", title)

    # 🔥 Supprime les caractères non imprimables et spéciaux
    title = re.sub(r'[^\w\s\-\']', '', title)  # Garde lettres, chiffres, espace, tiret, apostrophe
    
    # 🔥 Remplace les " par ' et les : par un espace
    title = title.replace('"', "'").replace(':', ' ')

    logger.debug("[DEBUG] après sanitize title %s", title)
    # 🔥 Vérifie si le titre est encore valide après nettoyage
    if not title.strip():
        return "Untitled"

    return title

def sanitize_filename(filename):
    # Remplace les caractères interdits par des underscores
    try:
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)  # Pour Windows
        sanitized = sanitized.replace(' ', '_')  # Remplace les espaces par des underscores
        return sanitized
    except Exception as e:
            logger.error(f"[ERREUR] Anomalie lors du sanitized : {e}")
            return