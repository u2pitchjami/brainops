import json
import os
from logger_setup import setup_logger
import logging
from dotenv import load_dotenv

load_dotenv()

setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

# Configure le logging
logger.basicConfig(level=logger.INFO)

def validate_note_paths():
    """
    Vérifie la structure de note_paths.json et identifie les anomalies.
    """
    note_paths_file = os.getenv('NOTE_PATHS_FILE')

    try:
        with open(note_paths_file, "r", encoding="utf-8") as f:
            note_paths = json.load(f)
        
        # Vérifie que le fichier est bien un dictionnaire
        if not isinstance(note_paths, dict):
            logger.error("[ERREUR] Le fichier JSON n'est pas un dictionnaire. Type trouvé : %s", type(note_paths))
            return
        
        anomalies = []

        # Parcours chaque entrée pour vérifier la structure
        for key, value in note_paths.items():
            if not isinstance(key, str):
                anomalies.append(f"Clé non valide (attendu str) : {key} ({type(key)})")
            
            if not isinstance(value, dict):
                anomalies.append(f"Valeur non valide pour la clé '{key}' (attendu dict) : {type(value)}")
            else:
                # Vérifie que les champs essentiels sont bien là
                required_fields = ["path", "category", "subcategory"]
                for field in required_fields:
                    if field not in value:
                        anomalies.append(f"Champ manquant '{field}' dans l'entrée : {key}")

        if anomalies:
            logger.warning("[ATTENTION] Des anomalies ont été détectées dans note_paths.json :")
            for anomaly in anomalies:
                logger.warning(anomaly)
        else:
            logger.info("[SUCCESS] Aucune anomalie détectée dans note_paths.json. Structure correcte.")

    except json.JSONDecodeError as e:
        logger.error("[ERREUR] Impossible de lire le fichier JSON : %s", e)
    except FileNotFoundError:
        logger.error("[ERREUR] Le fichier note_paths.json est introuvable.")

# Lance la vérification
validate_note_paths()
