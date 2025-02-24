import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
import inspect

def find_env_file():
    """
    Trouve le fichier .env en fonction du script appelant.
    Cherche d'abord dans son dossier, puis remonte dans la hiérarchie.
    """
    caller_script = inspect.stack()[2].filename  # Récupère le chemin du script qui appelle setup_logger()
    script_dir = os.path.dirname(os.path.abspath(caller_script))

    while script_dir != "/":
        env_path = os.path.join(script_dir, ".env")
        if os.path.exists(env_path):
            return env_path
        script_dir = os.path.dirname(script_dir)  # Remonte d'un niveau

    return None  # Aucun .env trouvé

# Charger le bon .env
env_file = find_env_file()
print("env_file : ", env_file)
if env_file:
    load_dotenv(env_file)

def setup_logger(script_name: str, level=logging.DEBUG):
    """
    Initialise un logger avec rotation journalière pour un script donné.
    
    :param script_name: Nom du fichier log (ex: 'beets', 'import_data', ...)
    :return: Logger configuré
    """
    log_dir = os.getenv('LOG_DIR', './logs')  # Dossier des logs (modifiable via .env)
    print ("logdir : ", log_dir)
    os.makedirs(log_dir, exist_ok=True)  # Crée le dossier s'il n'existe pas

    log_file = os.path.join(log_dir, f"{script_name}.log")  # Pas de date dans le nom

    logger = logging.getLogger(script_name)
    logger.setLevel(level)

    # Supprimer les handlers existants (évite la duplication)
    if logger.hasHandlers():
        logger.handlers.clear()

    # 🔥 Handler avec rotation journalière
    file_handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=7, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.suffix = "%Y-%m-%d"  # Ajoute la date automatiquement aux archives
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 🔥 Affichage des logs dans la console aussi
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    print(f"✅ Handlers du logger : {logger.handlers}")
    print(f"✅ Logger créé : {logger}")  # 🔥 Vérifions si le logger est bien instancié
    return logger  # Retourne un logger prêt à l'emploi
