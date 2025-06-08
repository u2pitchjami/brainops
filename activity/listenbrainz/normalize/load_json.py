import json
import os
from logger_setup import setup_logger
logger = setup_logger("normalize_scrobbles")

def load_chronique_config():
    try:
        json_path = os.getenv("PODCAST_JSON_PATH")
        with open(json_path, "r", encoding="utf-8") as file:
            raw_config = json.load(file)
        config = {k.lower(): {"_original_title": k, **v} for k, v in raw_config.items()}
        logger.info("Configuration des chroniques podcasts chargée (%d entrées)", len(config))
        return config
    except Exception as exc:
        logger.error("Erreur chargement configuration chroniques : %s", exc)
        return {}
    
def build_video_artist_index(config_raw):
    index = {}
    for theme, rule in config_raw.items():
        service = rule.get("service")
        for artist_name in rule.get("artist", []):
            key = artist_name.strip().lower()
            index[key] = {
                "service": service,
                "theme": theme,
                "scrobble_type": "video",
                "_original_artist": artist_name
            }
    logger.info("Index artistes vidéos construit (%d entrées)", len(index))
    return index

def load_video_config():
    try:
        json_path = os.getenv("VIDEO_JSON_PATH")
        with open(json_path, "r", encoding="utf-8") as file:
            raw_config = json.load(file)
        config = {k.lower(): {"_original_artist": k, **v} for k, v in raw_config.items()}
        logger.info("Configuration des vidéos chargée (%d entrées)", len(config))
        return config
    except Exception as exc:
        logger.error("Erreur chargement config vidéos : %s", exc)
        return {}
