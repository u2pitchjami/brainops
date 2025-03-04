# pylint: disable=C0413
import os
import sys
import logging
from dotenv import load_dotenv
import threading
print("🔥 Initialisation du script main.py")


# Chemin dynamique basé sur le script en cours
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
# Charger le fichier .env
load_dotenv(env_path)
base_script = os.getenv('BASE_SCRIPT')
sys.path.append(os.path.abspath(base_script))

from handlers.utils.backup_note_paths import backup_note_paths
from logger_setup import setup_logger
from handlers.start.watcher import start_watcher

setup_logger("obsidian_notes", logging.DEBUG)
logger = logging.getLogger("obsidian_notes")

print("✅ setup_logger a été exécuté !") 
print(f"✅ Logger après setup_logger : {logger}")


# 🔥 Démarrer la sauvegarde automatique en parallèle du watcher
backup_thread = threading.Thread(target=backup_note_paths, daemon=True)
backup_thread.start()

if __name__ == "__main__":
    start_watcher()
