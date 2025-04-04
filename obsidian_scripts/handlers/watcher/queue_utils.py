from logger_setup import setup_logger
import logging

setup_logger("queue_utils", logging.DEBUG)
logger = logging.getLogger("queue_utils")

def get_lock_key(note_id, file_path):
    """
    Génère une clé unique pour le verrouillage de traitement d'une note.
    Si le note_id est disponible, il est prioritaire.
    Sinon, on utilise le chemin du fichier comme clé temporaire.
    """
    if note_id:
        return f"note:{note_id}"
    return f"path:{str(file_path)}"
