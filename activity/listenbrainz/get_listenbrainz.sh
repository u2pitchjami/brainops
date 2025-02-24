#!/bin/bash

# ⚙️ CONFIGURATION
SCRIPT_DIR=$(dirname "$(realpath "$0")")
source ${SCRIPT_DIR}/.config.cfg  # Contient LISTENBRAINZ_USER

# 🔥 Récupérer les morceaux depuis l'API ListenBrainz
echo "${DATE_LOGS} - [INFO] Récupération des morceaux ListenBrainz..." | tee -a $LOG_FILE
response=$(curl -s "https://api.listenbrainz.org/1/user/${LISTENBRAINZ_USER}/listens?count=50")

# ⚠️ Vérification si l'API renvoie des données
if [ -z "$response" ]; then
    echo "${DATE_LOGS} - [ERROR] Réponse vide de l'API !" | tee -a $LOG_FILE
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
    echo "${DATE_LOGS} - [INFO] Aucun morceau valide à importer !" | tee -a $LOG_FILE
    exit 0
fi

# 🔥 Récupérer le nombre de lignes avant l'import
NB_LIGNES_AVANT=$(mysql central_db -N -B -e "SELECT COUNT(*) FROM listenbrainz_tracks;")

# 📥 Import dans MySQL
echo "${DATE_LOGS} - [INFO] Importation en cours dans MySQL..." | tee -a $LOG_FILE
mysql central_db -e "
    
    LOAD DATA INFILE '$DB_FILE'
    IGNORE INTO TABLE listenbrainz_tracks
    FIELDS TERMINATED BY ',' ENCLOSED BY '\"'
    LINES TERMINATED BY '\n'
    (artist, artist_mbid, title, album, album_mbid, track_mbid, @played_at)
    SET played_at = FROM_UNIXTIME(@played_at);
    
"

# 🔥 Récupérer le nombre de lignes après l'import
NB_LIGNES_APRES=$(mysql central_db -N -B -e "SELECT COUNT(*) FROM listenbrainz_tracks;")

# 🔥 Calculer le nombre de nouvelles lignes insérées
NB_LIGNES=$((NB_LIGNES_APRES - NB_LIGNES_AVANT))

echo "${DATE_LOGS} - [INFO] Lignes avant import: $NB_LIGNES_AVANT, après import: $NB_LIGNES_APRES, nouvelles lignes ajoutées: $NB_LIGNES" | tee -a "$LOG_FILE"

if [[ $NB_LIGNES -ne "0" ]]; then
    extract=$(mysql central_db -e "
        SELECT artist, title, played_at
        FROM listenbrainz_tracks
        ORDER BY played_at DESC
        LIMIT $NB_LIGNES;
    ")

    while IFS=$'\t' read -r artist title played_at; do
        echo "${DATE_LOGS} - [INFO] Artist: ${artist}, Title: ${title}, Played At: ${played_at}" | tee -a "$LOG_FILE"
    done <<< "$extract"

    echo "${DATE_LOGS} - [SUCCESS] Import terminé !" | tee -a $LOG_FILE
fi
 if [[ ! -d ${IMPORT_DIR}/${DATE} ]]; then
        mkdir ${IMPORT_DIR}/${DATE}
    fi

mv $SQL_FILE $SQL_FILE_PROCESSED # Nettoyage du fichier temporaire


