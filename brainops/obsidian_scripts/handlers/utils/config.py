"""2025-08-27 - module config en lien avec env."""

# config.py
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Chargement du .env à la racine du projet
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# --- Fonctions utilitaires ---


def get_required(key: str) -> str:
    """
    Récupère la valeur d'une variable env requise.

    Si la variable n'est pas présente ou non définitie,
    affiche une erreur et quitte le programme avec un code de sortie 1.

    Args:
        key (str): La clé de la variable env à récupérer.

    Returns:
        str: La valeur de la variable env.
    """
    value = os.getenv(key)
    if value is None:
        print(f"[CONFIG ERROR] La variable {key} est requise mais absente.")
        sys.exit(1)
    return value


def get_bool(key: str, default: str = "false") -> bool:
    """
    Returns the environment variable as a string.

    If the variable is not set or empty, it returns the provided default value.

    Args:
        key (bool): The name of the environment variable to retrieve.
        default (bool): The default value to return if the variable is not set. Defaults to an empty string.

    Returns:
        bool: The value of the environment variable or the default value.
    """
    return os.getenv(key, default).lower() in ("true", "1", "yes")


def get_str(key: str, default: str = "") -> str:
    """
    Returns the environment variable as a string.

    If the variable is not set or empty, it returns the provided default value.

    Args:
        key (str): The name of the environment variable to retrieve.
        default (str): The default value to return if the variable is not set. Defaults to an empty string.

    Returns:
        str: The value of the environment variable or the default value.
    """
    return os.getenv(key, default)


def get_int(key: str, default: int = 0) -> int:
    """
    Récupère la valeur d'une variable env requise qui doit être un entier.

    Si la variable n'est pas présente ou non définitie,
    affiche une erreur et quitte le programme avec un code de sortie 1.
    Args:
        key (str): La clé de la variable env à récupérer.
        default (int, optional): Le valeur par défaut si la variable est absente. Defaults to 0.

    Returns:
        int: La valeur de la variable env, convertie en entier.
    """
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        print(f"[CONFIG ERROR] La variable {key} doit être un entier.")
        sys.exit(1)


BASE_PATH = get_required("BASE_PATH")
BASE_SCRIPT = get_required("BASE_SCRIPT")
UNCATEGORIZED_PATH = get_required("UNCATEGORIZED_PATH")
IMPORTS_PATH = get_required("IMPORTS_PATH")
Z_STORAGE_PATH = get_required("Z_STORAGE_PATH")
SAV_PATH = get_required("SAV_PATH")
PROJECT_PATH = get_required("PROJECT_PATH")
DUPLICATES_PATH = get_required("DUPLICATES_PATH")
GPT_IMPORT_DIR = get_required("GPT_IMPORT_DIR")
GPT_OUTPUT_DIR = get_required("GPT_OUTPUT_DIR")
GPT_TEST = get_required("GPT_TEST")
IMPORTS_TEST = get_required("IMPORTS_TEST")
BACKUP_DIR = get_required("BACKUP_DIR")

SIMILARITY_WARNINGS_LOG = get_str("SIMILARITY_WARNINGS_LOG")
UNCATEGORIZED_JSON = get_str("UNCATEGORIZED_JSON")
DUPLICATES_LOGS = get_str("DUPLICATES_LOGS")
