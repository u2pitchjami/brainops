import json
import os
from logger_setup import setup_logger
import logging
from dotenv import load_dotenv
load_dotenv()

setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

logger = setup_logger("clean_note_paths", logging.DEBUG)

def clean_note_paths_file():
    note_paths_file = os.getenv('NOTE_PATHS_FILE')
    
    with open(note_paths_file, 'r', encoding='utf-8') as f:
        note_paths = json.load(f)

    # Supprimer les anciennes sections
    keys_to_remove = ['notes', 'categories', 'folders']
    for key in keys_to_remove:
        if key in note_paths:
            print(f"[INFO] Suppression de la clé obsolète : {key}")
            del note_paths[key]

    # Sauvegarde du fichier nettoyé
    with open(note_paths_file, 'w', encoding='utf-8') as f:
        json.dump(note_paths, f, indent=4)

    print("[SUCCESS] Fichier note_paths.json nettoyé avec succès !")

# Exécute le nettoyage
clean_note_paths_file()
