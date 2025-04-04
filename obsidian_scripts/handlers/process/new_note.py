from logger_setup import setup_logger
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from handlers.sql.db_notes import add_note_to_db
from handlers.sql.db_notes_utils import check_duplicate
from handlers.process.headers import add_metadata_to_yaml
from handlers.utils.config import IMPORTS_PATH, DUPLICATES_PATH
from handlers.sql.db_update_notes import update_obsidian_note
from handlers.utils.paths import path_is_inside
from handlers.header.yaml_read import ensure_status_in_yaml

setup_logger("new_note", logging.DEBUG)
logger = logging.getLogger("new_note")
duplicates_logs = os.getenv("DUPLICATES_LOGS")
duplicates_path = DUPLICATES_PATH
def new_note(file_path):
    """Gère les événements liés aux notes (création, modification, suppression, déplacement)."""
    logger.debug(f"[DEBUG] Entrée new_note : {file_path}")
    try:
        base_folder = os.path.dirname(file_path)
        note_title = Path(file_path).stem.replace("_", " ")
        note_id = None
        
        logger.debug(f"[DEBUG] ajout base de données")
        note_id = add_note_to_db(file_path)
        
        if path_is_inside(IMPORTS_PATH, base_folder):
            # Vérification des doublons avant ajout
            logger.debug(f"[DEBUG] vérif doublon")
            is_dup, dup_info = check_duplicate(note_id, file_path)
            logger.debug("[DEBUG] is_dup : %s, dup_info %s", is_dup, dup_info)
            if is_dup:
                new_path = handle_duplicate_note(file_path, dup_info)
                updates = {
                'file_path': str(new_path),
                'status': "duplicate"
                }
                logger.debug(f"[DEBUG] process_single_note mise à jour base de données : {updates}")
                update_obsidian_note(note_id, updates)
                ensure_status_in_yaml(new_path, status="duplicate")
                return None  # ou return new_path, selon la logique voulue
            
        if "Archives" in file_path:
            logger.info("[INFO] Réor entete Archives")
            add_metadata_to_yaml(note_id, file_path)
            return note_id
                    
        return note_id
        
    except Exception as e:
        logger.error(f"[ERREUR] Erreur lors de l'ajout de la note : {e}")


def handle_duplicate_note(file_path: str | Path, match_info: list[dict]) -> Path:
    """
    Déplace une note vers le dossier `duplicates` et log les infos.
    """
    file_path = Path(file_path)
    new_path = duplicates_path / file_path.name

    try:
        shutil.move(str(file_path), str(new_path))
        logger.warning(f"Note déplacée vers 'duplicates' : {new_path}")

        # Optionnel : log des infos doublon
        with open(duplicates_logs, "a", encoding="utf-8") as log_file:
            log_file.write(f"{datetime.now()} - {file_path.name} doublon de {match_info}\n")

        return new_path

    except Exception as e:
        logger.error(f"[DUPLICATE] Échec déplacement vers 'duplicates' : {e}")
        return file_path
