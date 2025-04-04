# pylint: disable=C0413
import os
import sys
import logging
from dotenv import load_dotenv
import threading
logging.basicConfig(level=logging.DEBUG)  # 🔥 Force le root logger à DEBUG
print("🔥 Initialisation du script main.py")

# Chemin dynamique basé sur le script en cours
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
# Charger le fichier .env
load_dotenv(env_path)
base_script = os.getenv('BASE_SCRIPT')
sys.path.append(os.path.abspath(base_script))

from logger_setup import setup_logger

#print("setup_logger MAIN 1")
setup_logger("obsidian_notes", logging.DEBUG)
logger = logging.getLogger("obsidian_notes")
#logger.debug("Test DEBUG depuis main")
#logger.info("Test INFO depuis main")
#print("✅ setup_logger MAIN a été exécuté !") 
#print(f"✅ Logger MAIN après setup_logger : {logger}")

#root_logger = logging.getLogger()  # Logger root (sans argument)
#print(f"🔍 Niveau du root logger : {logging.getLevelName(root_logger.level)}")
#print(f"🔍 Nombre de handlers dans root logger : {len(root_logger.handlers)}")

#for handler in root_logger.handlers:
#    print(f"   🔹 Handler : {handler}, Niveau : {logging.getLevelName(handler.level)}")

#logging.debug("TEST DEBUG ROOT")  # 🔥 Ce message s'affiche-t-il ?
#logging.info("TEST INFO ROOT")

from handlers.watcher.watcher import start_watcher



# 🔥 Démarrer la sauvegarde automatique en parallèle du watcher
#backup_thread = threading.Thread(target=backup_note_paths, daemon=True)
#backup_thread.start()

if __name__ == "__main__":
    start_watcher()
