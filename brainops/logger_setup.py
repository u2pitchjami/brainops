import inspect
import logging
import os
from logging.handlers import TimedRotatingFileHandler

from dotenv import load_dotenv


def find_env_file():
    """
    Trouve le fichier .env en fonction du script appelant.

    Cherche d'abord dans son dossier, puis remonte dans la hiérarchie.
    """
    caller_script = inspect.stack()[
        2
    ].filename  # Récupère le chemin du script qui appelle setup_logger()
    script_dir = os.path.dirname(os.path.abspath(caller_script))

    while script_dir != "/":
        env_path = os.path.join(script_dir, ".env")
        if os.path.exists(env_path):
            return env_path
        script_dir = os.path.dirname(script_dir)  # Remonte d'un niveau

    return None  # Aucun .env trouvé


# Charger le bon .env
env_file = find_env_file()
if env_file:
    load_dotenv(env_file)


def setup_logger(script_name: str, level=None):
    """
    Initialise un logger avec rotation journalière et support ENV.

    - ENV=dev  → DEBUG
    - ENV=prod → INFO (par défaut)
    """
    # Détermine le niveau si non fourni
    if level is None:
        env_mode = os.getenv("ENV", "prod").lower()
        level = logging.DEBUG if env_mode == "dev" else logging.INFO

    log_dir = os.getenv("LOG_DIR", "./logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"{script_name}.log")
    logger = logging.getLogger(script_name)
    logger.setLevel(level)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(name)s] %(message)s"
    )

    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    print(f"📝 Fichier de log : {logger.addHandler(file_handler)}")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.propagate = False

    logger.debug("🔍 Logger initialisé en mode DEBUG (env=dev)")
    logger.info(
        f"✅ Logger actif pour {script_name}, niveau : {logging.getLevelName(level)}"
    )
    return logger
