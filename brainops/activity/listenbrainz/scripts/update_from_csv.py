import csv
import mysql.connector
from dotenv import load_dotenv
import os

# Load .env
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}

def update_from_csv(csv_file):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                cursor.execute("""
                    UPDATE listenbrainz_tracks
                    SET title = %s, artist = %s, artist_mbid = %s, album = %s, album_mbid = %s, track_mbid = %s, service = %s, client = %s, scrobble_type = %s, theme = %s
                    WHERE id = %s
                """, (
                    row["title"],
                    row["artist"],
                    row["artist_mbid"],
                    row["album"],
                    row["album_mbid"],
                    row["track_mbid"],
                    row["service"],
                    row["client"],
                    row["scrobble_type"],
                    row["theme"],
                    row["id"]
                ))
            except Exception as e:
                print(f"Erreur ligne ID {row.get('id')} : {e}")

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    update_from_csv("correctifs_scrobbles.csv")
