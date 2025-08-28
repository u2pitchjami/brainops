from brainops.logger_setup import setup_logger

logger = setup_logger("normalize_scrobbles")


def enrich_video_scrobble(scrobble: dict, index: dict) -> dict:
    try:
        if scrobble.get("_normalized"):
            return scrobble

        artist_key = scrobble.get("artist", "").strip().lower()
        if artist_key not in index:
            return scrobble

        rule = index[artist_key]
        scrobble["artist"] = rule["_original_artist"]
        scrobble["service"] = rule["service"]
        scrobble["theme"] = rule["theme"]
        scrobble["scrobble_type"] = rule["scrobble_type"]
        scrobble["_normalized"] = "Video"

    except Exception as e:
        logger.warning("Erreur enrichissement scrobble vidéo : %s", e)

    return scrobble
