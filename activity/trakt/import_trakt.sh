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
        echo "$DATE [INFO] Ajout de $file dans le process d'import..." >> $LOG_FILE
        
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
    for file in "${WATCHED_FILES[@]}"; do
        [ -f "$file" ] || continue  # Vérifie que c'est bien un fichier
        FILES_FOUND=$((FILES_FOUND + 1))
        echo "$DATE [INFO] Ajout de $file dans le process d'import..." >> $LOG_FILE
        
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

# Si au moins un fichier a été ajouté, exécuter le SQL complet
if [ $FILES_FOUND -ge 1 ]; then
    echo "$DATE [INFO] Importation de $FILES_FOUND fichiers en une seule exécution..." >> $LOG_FILE

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
    for file in "${FILES_TO_MOVE[@]}"; do
        mv "$file" "$file.processed"
        echo "$DATE [INFO] Fichier $file déplacé après traitement." >> $LOG_FILE
    done
else
    echo "$DATE [INFO] Aucun fichier récent, report de l'import." >> $LOG_FILE
fi
