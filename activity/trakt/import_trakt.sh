#!/bin/bash

SCRIPT_DIR=$(dirname "$(realpath "$0")")
source ${SCRIPT_DIR}/.config.cfg

FILES_FOUND=0
SQL_COMMAND=""
FILES_TO_MOVE=()  # Initialiser un tableau vide pour stocker les fichiers à déplacer

# Vérifier si des fichiers existent avant la boucle
WATCHLIST_FILES=($IMPORT_DIR/watchlist_*.csv)
if [ -e "${WATCHLIST_FILES[0]}" ]; then
    NB_LIGNES_AVANT_WATCHLIST=$(mysql central_db -N -B -e "SELECT COUNT(*) FROM trakt_watchlist;")
    for file in "${WATCHLIST_FILES[@]}"; do
        [ -f "$file" ] || continue  # Vérifie que c'est bien un fichier
        FILES_FOUND=$((FILES_FOUND + 1))
        echo "$DATE_LOGS [INFO] Ajout de $file dans le process d'import..." >> $LOG_FILE
        
        # Ajouter l'import du fichier à la requête SQL globale
        SQL_COMMAND+="LOAD DATA INFILE '/mariadb-import/$(basename "$file")' IGNORE INTO TABLE trakt_watchlist_temp
        FIELDS TERMINATED BY ',' 
        ENCLOSED BY '\"'
        LINES TERMINATED BY '\n'
        (type, title, @prod_date, @imdb_id, @tmdb_id, @date_add)
        SET date_add = STR_TO_DATE(@date_add, '%Y-%m-%dT%H:%i:%s.000Z'),
        prod_date = NULLIF(@prod_date, ''),
        imdb_id = CASE 
                    WHEN @imdb_id = '' OR @imdb_id IS NULL THEN 'NO_IMDB'
                    ELSE @imdb_id
                END,
        tmdb_id = CASE 
                    WHEN @tmdb_id = '' OR @tmdb_id IS NULL THEN 'NO_TMDB'
                    ELSE @tmdb_id
                END;        
        "
        FILES_TO_MOVE+=("$file")
    done
fi
if [ $FILES_FOUND -ge 1 ]; then
    echo "$DATE_LOGS [INFO] Importation de $FILES_FOUND fichiers en une seule exécution..." >> $LOG_FILE

    mysql central_db -e "
        CREATE TEMPORARY TABLE trakt_watchlist_temp LIKE trakt_watchlist;
        $SQL_COMMAND
        INSERT INTO trakt_watchlist (type, title, prod_date, imdb_id, tmdb_id, date_add)
        SELECT type, title, prod_date, imdb_id, tmdb_id, date_add
        FROM trakt_watchlist_temp
        ON DUPLICATE KEY UPDATE 
            trakt_watchlist.imdb_id = IF(trakt_watchlist.imdb_id = 'NO_IMDB', VALUES(imdb_id), trakt_watchlist.imdb_id),
            trakt_watchlist.tmdb_id = IF(trakt_watchlist.tmdb_id = 'NO_TMDB', VALUES(tmdb_id), trakt_watchlist.tmdb_id);
    "
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
fi
    NB_LIGNES_APRES_WATCHLIST=$(mysql central_db -N -B -e "SELECT COUNT(*) FROM trakt_watchlist;")
    NB_LIGNES_WATCHLIST=$((NB_LIGNES_APRES_WATCHLIST - NB_LIGNES_AVANT_WATCHLIST))

    echo "${DATE_LOGS} - [INFO] Nouvelles lignes ajoutées: $NB_LIGNES_WATCHLIST dans trakt_watchlist" | tee -a "$LOG_FILE"


# Si au moins un fichier a été ajouté, exécuter le SQL complet
if [ $FILES_FOUND -ge 1 ]; then
    echo "$DATE_LOGS [INFO] Importation de $FILES_FOUND fichiers en une seule exécution..." >> $LOG_FILE

    mysql central_db -e "
        CREATE TEMPORARY TABLE trakt_watched_temp LIKE trakt_watched;
        CREATE TEMPORARY TABLE trakt_watchlist_temp LIKE trakt_watchlist;
        $SQL_COMMAND
        INSERT INTO trakt_watched (type, title, prod_date, episode_title, num_season, num_episode, imdb_id, tmdb_id, watched_date, rating)
        SELECT type, title, prod_date, episode_title, num_season, num_episode, imdb_id, tmdb_id, watched_date, rating
        FROM trakt_watched_temp
        ON DUPLICATE KEY UPDATE 
    trakt_watched.imdb_id = CASE 
        WHEN trakt_watched.imdb_id = 'NO_IMDB' AND VALUES(imdb_id) <> 'NO_IMDB' THEN VALUES(imdb_id) 
        ELSE trakt_watched.imdb_id 
    END,
    trakt_watched.tmdb_id = CASE 
        WHEN trakt_watched.tmdb_id = 'NO_TMDB' AND VALUES(tmdb_id) <> 'NO_TMDB' THEN VALUES(tmdb_id) 
        ELSE trakt_watched.tmdb_id
    END;
    "
    
    # Déplacer les fichiers SEULEMENT après l'import MySQL

    
    NB_LIGNES_APRES_WATCHED=$(mysql central_db -N -B -e "SELECT COUNT(*) FROM trakt_watched;")
    NB_LIGNES_WATCHED=$((NB_LIGNES_APRES_WATCHED - NB_LIGNES_AVANT_WATCHED))

echo "${DATE_LOGS} - [INFO] Nouvelles lignes ajoutées: $NB_LIGNES_WATCHED dans trakt_watched" | tee -a "$LOG_FILE"

if [[ $NB_LIGNES_WATCHED != 0 ]]; then
    extract=$(mysql central_db -N -B -e "SELECT type, title, watched_date FROM trakt_watched ORDER BY watched_date DESC LIMIT ${NB_LIGNES_WATCHED};")

    while IFS=$'\t' read -r type title watched_date; do
        echo "${DATE_LOGS} - [INFO] type: ${type}, Title: ${title}, Played At: ${watched_date}" | tee -a "$LOG_FILE"
    done <<< "$extract"

    echo "${DATE_LOGS} - [SUCCESS] Import terminé !" | tee -a $LOG_FILE
fi

    if [[ ! -d ${IMPORT_DIR}/${DATE} ]]; then
        mkdir ${IMPORT_DIR}/${DATE}
    fi

    for file in "${FILES_TO_MOVE[@]}"; do
        name=$(echo "$file" | rev | cut -d "/" -f1 | rev)
        mv "$file" "${IMPORT_DIR}/${DATE}/$name.processed"
        
        echo "$DATE_LOGS [INFO] Fichier $file déplacé après traitement." >> $LOG_FILE
    done
else
    echo "$DATE_LOGS [INFO] Aucun fichier récent, report de l'import." >> $LOG_FILE
fi