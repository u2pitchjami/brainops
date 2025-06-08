import sys
import os
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv
from activity.listenbrainz.normalize.load_json import load_chronique_config, load_video_config, build_video_artist_index
from activity.listenbrainz.normalize.db import get_scrobbles_from_db, inject_normalized_scrobble
from activity.listenbrainz.normalize.podcast import normalize_france_inter_live, enrich_podcast_scrobble
from activity.listenbrainz.normalize.video import enrich_video_scrobble
from logger_setup import setup_logger
logger = setup_logger("normalize_scrobbles")

# Initialisation
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
load_dotenv(env_path)

def convert_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normalisation des scrobbles ListenBrainz")
    parser.add_argument("--dry-run", action="store_true", help="Mode test : n'injecte rien dans la base")
    parser.add_argument("--all", action="store_true", help="prends tous les scrobbles (au lieu de ceux des 24 dernières heures)")
    parser.add_argument("--logfile", type=str, default="not_found_scrobbles.log", help="Fichier log pour les scrobbles non reconnus")
    args = parser.parse_args()

    raw_video_config = load_video_config()  # nouveau format groupé
    video_artist_index = build_video_artist_index(raw_video_config)
    config = load_chronique_config()
    if not config or not raw_video_config:
        logger.error("Aucune configuration de chronique chargée. Abandon.")
        sys.exit(1)

    scrobbles = get_scrobbles_from_db(all=args.all)
    for s in scrobbles:
        #print(f"🚧 Traitement scrobble {s.get("track_id")}, {s.get("artist")}, {s.get("title")}")
        s = normalize_france_inter_live(s)
        s = enrich_podcast_scrobble(s, config, not_found_logfile=args.logfile)
        s = enrich_video_scrobble(s, video_artist_index)
        # if s.get("_normalized"):
        #     logger.info("pouet")
        
        # s.pop("_normalized", None)

        if args.dry_run:
            print(json.dumps(s, indent=2, ensure_ascii=False, default=convert_datetime))
        else:
            inject_normalized_scrobble(s)

