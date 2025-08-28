# pylint: disable=C0413
import logging
import os
import sys

from dotenv import load_dotenv

from brainops.logger_setup import setup_logger
from brainops.obsidian_scripts.handlers.watcher.watcher import start_watcher

logging.basicConfig(level=logging.DEBUG)  # 🔥 Force le root logger à DEBUG
print("🔥 Initialisation du script main.py")

# Chemin dynamique basé sur le script en cours
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
# Charger le fichier .env
load_dotenv(env_path)
base_script = os.getenv("BASE_SCRIPT")
sys.path.append(os.path.abspath(base_script))


setup_logger("obsidian_notes", logging.DEBUG)
logger = logging.getLogger("obsidian_notes")


if __name__ == "__main__":
    start_watcher()
