#!/usr/bin/env python3
import json
import mysql.connector
from datetime import datetime
from pathlib import Path

# --- CONFIG ---
DB_CONFIG = {
    "host": "localhost",
    "user": "ton_user",
    "password": "ton_mdp",
    "database": "brainops_db"
}

# --- DB ---
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def insert_watched(cursor, entry, type_):
    if type_ == "movie":
        item = entry["movie"]
        title = item.get("title", "")
        prod_date = item.get("year")
        episode_title = None
        num_season = None
        num_episode = None
        imdb_id = item["ids"].get("imdb")
        tmdb_id = item["ids"].get("tmdb")
    else:  # show/episode
        show = entry["show"]
        episode = entry["episode"]
        title = show.get("title", "")
        prod_date = show.get("year")
        episode_title = episode.get("title", "")
        num_season = episode.get("season")
        num_episode = episode.get("number")
        imdb_id = show["ids"].get("imdb")
        tmdb_id = show["ids"].get("tmdb")

    watched_date = entry.get("watched_at")
    rating = entry.get("rating")  # déjà fusionné plus bas
    last_updated = datetime.now()

    cursor.execute("""
        INSERT INTO trakt_watched
        (type, title, prod_date, episode_title, num_season, num_episode,
         imdb_id, tmdb_id, watched_date, rating, last_updated)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            rating=VALUES(rating),
            watched_date=VALUES(watched_date),
            last_updated=VALUES(last_updated);
    """, (
        type_, title, prod_date, episode_title, num_season, num_episode,
        imdb_id, tmdb_id, watched_date, rating, last_updated
    ))

def load_and_merge(history_file, ratings_file, type_):
    """Charge un historique et fusionne avec les notes"""
    history = json.loads(Path(history_file).read_text())
    ratings = json.loads(Path(ratings_file).read_text())
    ratings_map = {}

    # Construire un dictionnaire des notes
    for r in ratings:
        key = None
        if type_ == "movie":
            key = r["movie"]["ids"].get("tmdb") or r["movie"]["ids"].get("imdb")
        else:
            key = f"{r['show']['ids'].get('tmdb')}-{r['episode']['season']}-{r['episode']['number']}"
        ratings_map[key] = r.get("rating")

    # Fusionner avec l’historique
    for h in history:
        key = None
        if type_ == "movie":
            key = h["movie"]["ids"].get("tmdb") or h["movie"]["ids"].get("imdb")
        else:
            key = f"{h['show']['ids'].get('tmdb')}-{h['episode']['season']}-{h['episode']['number']}"
        if key in ratings_map:
            h["rating"] = ratings_map[key]
        else:
            h["rating"] = None
    return history

def main():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Movies
    movies = load_and_merge(
        "/chemin/vers/USERNAME-history_movies.json",
        "/chemin/vers/USERNAME-ratings_movies.json",
        "movie"
    )
    for entry in movies:
        insert_watched(cursor, entry, "movie")

    # Shows
    shows = load_and_merge(
        "/chemin/vers/USERNAME-history_shows.json",
        "/chemin/vers/USERNAME-ratings_episodes.json",
        "show"
    )
    for entry in shows:
        insert_watched(cursor, entry, "show")

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Import JSON → MariaDB terminé")

if __name__ == "__main__":
    main()
