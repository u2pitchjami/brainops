#!/bin/bash

SCRIPT_DIR=$(dirname "$(realpath "$0")")
source ${SCRIPT_DIR}/.config.cfg

FILES_FOUND=0
SQL_COMMAND=""
FILES_TO_MOVE=()  # Initialiser un tableau vide pour stocker les fichiers à déplacer

# Vérifier si des fichiers existent avant la boucle
WATCHLIST_FILES=($IMPORT_DIR/watchlist_*.csv)
if [ -e "${WATCHLIST_FILES[0]}" ]; then
    for file in "${WATCHLIST_FILES[@]}"; do
        [ -f "$file" ] || continue  # Vérifie que c'est bien un fichier
        FILES_FOUND=$((FILES_FOUND + 1))
        echo "$DATE_LOGS [INFO] Ajout de $file dans le process d'import..." >> $LOG_FILE
        
        # Ajouter l'import du fichier à la requête SQL globale
        SQL_COMMAND+="LOAD DATA INFILE '/mariadb-import/$(basename "$file")' IGNORE INTO TABLE trakt_watchlist
        FIELDS TERMINATED BY ',' 
        ENCLOSED BY '\"'
        LINES TERMINATED BY '\n'
        (type, title, @prod_date, @imdb_id, @tmdb_id, @date_add)
        SET date_add = STR_TO_DATE(@date_add, '%Y-%m-%dT%H:%i:%s.000Z'),
            prod_date = NULLIF(@prod_date, ''),
            imdb_id = NULLIF(@imdb_id, ''),
            tmdb_id = NULLIF(@tmdb_id, '');
        "
        FILES_TO_MOVE+=("$file")
    done
fi

# Vérifier si des fichiers "watched" existent
WATCHED_FILES=($IMPORT_DIR/watched_*.csv)
if [ -e "${WATCHED_FILES[0]}" ]; then
    # 🔥 Récupérer le nombre de lignes avant l'import
    NB_LIGNES_AVANT_WATCHED=$(mysql central_db -N -B -e "SELECT COUNT(*) FROM trakt_watched;")
    for file in "${WATCHED_FILES[@]}"; do
        [ -f "$file" ] || continue  # Vérifie que c'est bien un fichier
        FILES_FOUND=$((FILES_FOUND + 1))
        echo "$DATE_LOGS [INFO] Ajout de $file dans le process d'import..." >> $LOG_FILE
        
        # Ajouter l'import du fichier à la requête SQL globale
        SQL_COMMAND+="LOAD DATA INFILE '/mariadb-import/$(basename "$file")'
        INTO TABLE trakt_watched_temp
        FIELDS TERMINATED BY ',' 
        ENCLOSED BY '\"'
        LINES TERMINATED BY '\n'
        (type, title, @prod_date, @episode_title, @num_season, @num_episode, @imdb_id, @tmdb_id, @watched_date, @rating)
        SET watched_date = STR_TO_DATE(@watched_date, '%Y-%m-%dT%H:%i:%s.000Z'),
            prod_date = NULLIF(@prod_date, ''),
            episode_title = NULLIF(@episode_title, ''),
            num_season = NULLIF(@num_season, ''),
            num_episode = NULLIF(@num_episode, ''),
            imdb_id = NULLIF(@imdb_id, ''),
            tmdb_id = NULLIF(@tmdb_id, ''),
            rating = NULLIF(@rating, '');
        "
        FILES_TO_MOVE+=("$file")
    done
    NB_LIGNES_APRES_WATCHED=$(mysql central_db -N -B -e "SELECT COUNT(*) FROM trakt_watched;")
    NB_LIGNES_WATCHED=$((NB_LIGNES_APRES_WATCHED - NB_LIGNES_AVANT_WATCHED))

echo "${DATE_LOGS} - [INFO] Nouvelles lignes ajoutées: $NB_LIGNES dans trakt_watched" | tee -a "$LOG_FILE"

[[ if $NB_LIGNES_WATCHED != 0 ]]; then
    extract=$(mysql central_db -e "
        SELECT type, title, watched_date
        FROM trakt_watched
        ORDER BY watched_date DESC
        LIMIT $NB_LIGNES;
    ")

    while IFS=$'\t' read -r artist title played_at; do
        echo "${DATE_LOGS} - [INFO] type: ${type}, Title: ${title}, Played At: ${watched_date}" | tee -a "$LOG_FILE"
    done <<< "$extract"

    echo "${DATE_LOGS} - [SUCCESS] Import terminé !" | tee -a $LOG_FILE
fi

# Si au moins un fichier a été ajouté, exécuter le SQL complet
if [ $FILES_FOUND -ge 1 ]; then
    echo "$DATE_LOGS [INFO] Importation de $FILES_FOUND fichiers en une seule exécution..." >> $LOG_FILE

    mysql central_db -e "
        CREATE TEMPORARY TABLE trakt_watched_temp LIKE trakt_watched;
        $SQL_COMMAND
        INSERT INTO trakt_watched (type, title, prod_date, episode_title, num_season, num_episode, imdb_id, tmdb_id, watched_date, rating)
        SELECT type, title, prod_date, episode_title, num_season, num_episode, imdb_id, tmdb_id, watched_date, rating
        FROM trakt_watched_temp
        ON DUPLICATE KEY UPDATE 
            watched_date = VALUES(watched_date),
            rating = VALUES(rating);
    "
    
    # Déplacer les fichiers SEULEMENT après l'import MySQL

    if [[ ! -d ${IMPORT_DIR}/${DATE} ]]; then
        mkdir ${IMPORT_DIR}/${DATE}
    fi

    for file in "${FILES_TO_MOVE[@]}"; do
        mv "$file" "${IMPORT_DIR}/${DATE}/$file.processed"
        echo "$DATE_LOGS [INFO] Fichier $file déplacé après traitement." >> $LOG_FILE
    done
else
    echo "$DATE_LOGS [INFO] Aucun fichier récent, report de l'import." >> $LOG_FILE
fi
