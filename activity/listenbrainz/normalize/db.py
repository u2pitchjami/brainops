import os
import mysql.connector
from logger_setup import setup_logger
logger = setup_logger("normalize_scrobbles")

# Configuration DB
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}

def get_scrobbles_from_db(all=None):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        if not all:
            cursor.execute("SELECT * FROM listenbrainz_tracks WHERE last_updated > NOW() - INTERVAL 1 DAY AND theme IS NULL AND scrobble_type != 'music'")
        else:
            cursor.execute("SELECT * FROM listenbrainz_tracks WHERE theme IS NULL AND scrobble_type != 'music'")
        results = cursor.fetchall()
        logger.info("Scrobbles récupérés depuis la base : %d", len(results))
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        logger.error("Erreur lors de la lecture de la base : %s", e)
        return []

def inject_normalized_scrobble(scrobble: dict):
    try:
        if scrobble.get("_normalized"):
            #print(f"Scrobble ID {scrobble.get('track_id')} déjà normalisé, {scrobble.get("_normalized")}")
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            sql = """
            UPDATE listenbrainz_tracks
            SET title = %s, artist = %s, album = %s, service = %s,
                theme = %s, scrobble_type = %s
            WHERE track_id = %s
            """
            values = (
                scrobble.get("title"),
                scrobble.get("artist"),
                scrobble.get("album"),
                scrobble.get("service"),
                scrobble.get("theme"),
                scrobble.get("scrobble_type"),
                scrobble.get("track_id")
            )
            cursor.execute(sql, values)
            conn.commit()
            logger.info("👌 Scrobble ID %s - [%s] - %s - %s mis à jour.", scrobble.get("track_id"), scrobble.get("_normalized"), scrobble.get("artist"), scrobble.get("title"))
            cursor.close()
            conn.close()
        else:
            logger.warning("🚨 Scrobble ID %s - %s - %s non normalisé, pas d'injection.", scrobble.get("track_id"), scrobble.get("artist"), scrobble.get("title"))
    except Exception as e:
        logger.error("Erreur injection en base pour ID %s : %s", scrobble.get("track_id"), e)