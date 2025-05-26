#!/bin/bash
# ⚙️ Configuration
SCRIPT_DIR=$(dirname "$(realpath "$0")")
source ${SCRIPT_DIR}/.config.cfg  # Contient LISTENBRAINZ_USER

# 🔥 Récupération des morceaux depuis l'API ListenBrainz
echo "${DATE_LOGS} - [INFO] Récupération des morceaux ListenBrainz..." | tee -a $LOG_FILE
response=$(curl -s "https://api.listenbrainz.org/1/user/${LISTENBRAINZ_USER}/listens?count=50")

# ⚠️ Vérification si l'API renvoie des données
if [ -z "$response" ]; then
    echo "${DATE_LOGS} - [ERROR] Réponse vide de l'API !" | tee -a $LOG_FILE
    exit 1
fi


echo "$response" | jq -r '.payload.listens[] | 
    [.track_metadata.artist_name, 
     .track_metadata.mbid_mapping.artist_mbids[0], 
     .track_metadata.track_name, 
     .track_metadata.release_name, 
     .track_metadata.mbid_mapping.release_mbid, 
     .track_metadata.mbid_mapping.recording_mbid, 
     .track_metadata.additional_info.music_service_name, 
     .track_metadata.additional_info.submission_client, 
     .listened_at] | @csv' > "$SQL_FILE"

# 🔥 Import du fichier CSV dans la base (sans scrobble_type)
mysql brainops_db -e "
    LOAD DATA INFILE '$DB_FILE'
    IGNORE INTO TABLE listenbrainz_tracks
    FIELDS TERMINATED BY ',' ENCLOSED BY '\"'
    LINES TERMINATED BY '\n'
    (artist, artist_mbid, title, album, album_mbid, track_mbid, service, client, @played_at)
    SET played_at = FROM_UNIXTIME(@played_at), scrobble_type = 'unknown';
"

# 🔄 Mise à jour des types de scrobble directement en SQL
mysql brainops_db -e "
    UPDATE listenbrainz_tracks
    SET scrobble_type = 'music'
    WHERE (artist_mbid <> '')
    AND DATE(played_at) = CURDATE();

    UPDATE listenbrainz_tracks
    SET scrobble_type = 'video'
    WHERE client = 'Web Scrobbler' AND service = 'YouTube'
    AND DATE(played_at) = CURDATE();

    UPDATE listenbrainz_tracks
    SET scrobble_type = 'podcast'
    WHERE (client = 'Web Scrobbler' AND service = 'Radio France') 
    OR (client = 'Pano Scrobbler' AND artist_mbid = '' AND album <> '')
    AND DATE(played_at) = CURDATE();
    
"

# 🔄 Vérification après import
NB_LIGNES=$(mysql brainops_db -N -B -e "SELECT COUNT(*) FROM listenbrainz_tracks WHERE DATE(played_at) = CURDATE();")
echo "${DATE_LOGS} - [INFO] Nombre de scrobbles importés aujourd'hui: $NB_LIGNES" | tee -a "$LOG_FILE"

# 🛠 Nettoyage
mv "$SQL_FILE" "$SQL_FILE_PROCESSED"

echo "${DATE_LOGS} - [SUCCESS] Import et mise à jour des types terminés !" | tee -a $LOG_FILE
