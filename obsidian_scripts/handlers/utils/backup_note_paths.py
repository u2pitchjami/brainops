import threading
import shutil
import time
import os
import glob
from logger_setup import setup_logger
import logging

setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

BACKUP_INTERVAL = 600  # ⏳ 10 minutes
MAX_BACKUPS = 100  # 🔄 On garde 10 backups max
backup_dir = os.getenv('BACKUP_DIR')

def rotate_backups():
    """Gère la rotation des sauvegardes : supprime les plus anciennes si nécessaire."""
    backup_files = sorted(glob.glob(os.path.join(backup_dir, "note_paths_*.json")))

    if len(backup_files) > MAX_BACKUPS:
        num_to_delete = len(backup_files) - MAX_BACKUPS
        for i in range(num_to_delete):
            try:
                os.remove(backup_files[i])
                logger.info(f"[INFO] Suppression de l'ancienne sauvegarde : {backup_files[i]}")
            except Exception as e:
                logger.error(f"[ERREUR] Impossible de supprimer {backup_files[i]} : {e}")

def backup_note_paths():
    """Crée une sauvegarde de `note_paths.json` avec rotation automatique."""
    while True:
        time.sleep(BACKUP_INTERVAL)

        note_paths_file = os.getenv('NOTE_PATHS_FILE')
        if not os.path.exists(note_paths_file):
            continue

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_file = os.path.join(backup_dir, f"note_paths_{timestamp}.json")

        try:
            shutil.copy(note_paths_file, backup_file)
            logger.info(f"[INFO] Sauvegarde automatique créée : {backup_file}")
            rotate_backups()

        except Exception as e:
            logger.error(f"[ERREUR] Impossible de créer la sauvegarde : {e}")
