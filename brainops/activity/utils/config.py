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
    value = os.getenv(key)
    if value is None:
        print(f"[CONFIG ERROR] La variable {key} est requise mais absente.")
        sys.exit(1)
    return value


def get_bool(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).lower() in ("true", "1", "yes")


def get_str(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        print(f"[CONFIG ERROR] La variable {key} doit être un entier.")
        sys.exit(1)


# --- Variables d'environnement accessibles globalement ---

DB_CONFIG = {
    "host": get_required("DB_HOST"),
    "user": get_required("DB_USER"),
    "password": get_required("DB_PASSWORD"),
    "database": get_required("DB_NAME"),
}
