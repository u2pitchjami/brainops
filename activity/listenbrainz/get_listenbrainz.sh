#!/bin/bash

# ⚙️ CONFIGURATION
SCRIPT_DIR=$(dirname "$(realpath "$0")")
source ${SCRIPT_DIR}/.config.cfg  # Contient LISTENBRAINZ_USER

# 🔥 Récupérer les morceaux depuis l'API ListenBrainz
echo "[INFO] Récupération des morceaux ListenBrainz..." | tee -a $LOG_FILE
response=$(curl -s "https://api.listenbrainz.org/1/user/${LISTENBRAINZ_USER}/listens?count=50")

# ⚠️ Vérification si l'API renvoie des données
if [ -z "$response" ]; then
    echo "[ERROR] Réponse vide de l'API !" | tee -a $LOG_FILE
    exit 1
fi

# 📜 Parser le JSON et récupérer les MBID
echo "$response" | jq -r '.payload.listens[] | 
    [.track_metadata.artist_name, 
     .track_metadata.mbid_mapping.artist_mbids[0], 
     .track_metadata.track_name, 
     .track_metadata.release_name, 
     .track_metadata.mbid_mapping.release_mbid, 
     .track_metadata.mbid_mapping.recording_mbid, 
     .listened_at] | @csv' > $SQL_FILE

# ⚠️ Vérification si le fichier CSV contient des données
if [ ! -s $SQL_FILE ]; then
    echo "[INFO] Aucun morceau valide à importer !" | tee -a $LOG_FILE
    exit 0
fi


# 📥 Import dans MySQL
echo "[INFO] Importation en cours dans MySQL..." | tee -a $LOG_FILE
mysql central_db -e "
    
    LOAD DATA INFILE '$DB_FILE'
    IGNORE INTO TABLE listenbrainz_tracks
    FIELDS TERMINATED BY ',' ENCLOSED BY '\"'
    LINES TERMINATED BY '\n'
    (artist, artist_mbid, title, album, album_mbid, track_mbid, @played_at)
    SET played_at = FROM_UNIXTIME(@played_at);
    
"

NB_LIGNES=$(mysql central_db -N -B -e "SELECT ROW_COUNT();")

echo "[INFO] Aperçu des dernières lignes importées :" | tee -a "$LOG_FILE"

extract=$(mysql central_db -e "
    SELECT artist, title, played_at
    FROM listenbrainz_tracks
    ORDER BY played_at DESC
    LIMIT $NB_LIGNES;
")

echo "[INFO] ${extract}" | tee -a "$LOG_FILE"

echo "[SUCCESS] Import terminé !" | tee -a $LOG_FILE
mv $SQL_FILE $SQL_FILE_PROCESSED # Nettoyage du fichier temporaire


