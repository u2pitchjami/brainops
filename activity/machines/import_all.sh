#!/bin/bash

SCRIPT_DIR=$(dirname "$(realpath "$0")")
source ${SCRIPT_DIR}/.config.cfg

NOW=$(date +%s)
FILES_FOUND=0
SQL_COMMAND=""

# Construire une série de commandes SQL pour chaque fichier CSV disponible
for file in $IMPORT_DIR/recap_*.csv; do
    
    if [ -f "$file" ]; then
        FILE_TIME=$(stat -c %Y "$file")
        AGE=$((NOW - FILE_TIME))

        if [ $AGE -le $THRESHOLD_TIME ]; then
            FILES_FOUND=$((FILES_FOUND + 1))
            echo "$DATE [INFO] Ajout de $file dans le process d'import..." >> $LOG_FILE
            
            # Ajouter l'import du fichier à la requête SQL globale
            SQL_COMMAND+="LOAD DATA INFILE '/mariadb-import/$(basename "$file")' INTO TABLE recap_staging
            FIELDS TERMINATED BY '|' 
            ENCLOSED BY '\"'
            LINES TERMINATED BY '\n'
            IGNORE 2 ROWS
            (@dummy, @dummy, ip_address, timestamp, user_id, user_name, application_id, application_name, window_id, window_title, duration);
            "
            # Stocker le fichier pour le déplacer après
            FILES_TO_MOVE+=("$file")
            
        else
            echo "$DATE [WARNING] Fichier $file trop vieux (+10 min), ignoré." >> $LOG_FILE
        fi
    fi
done

# Si au moins un fichier a été ajouté, exécuter le SQL complet
if [ $FILES_FOUND -ge 1 ]; then
    echo "$DATE [INFO] Importation de $FILES_FOUND fichiers en une seule exécution..." >> $LOG_FILE

    mysql central_db -e "
        CREATE TEMPORARY TABLE recap_temp LIKE recap;
        CREATE TEMPORARY TABLE recap_staging LIKE recap_temp;
        ALTER TABLE recap_staging DROP INDEX unique_entry;
        $SQL_COMMAND
        SOURCE $PROCESS_RECAP;
    "
     # Déplacer les fichiers SEULEMENT après l'import MySQL
    for file in "${FILES_TO_MOVE[@]}"; do
        mv "$file" "$file.processed"
        echo "$DATE [INFO] Fichier $file déplacé après traitement." >> $LOG_FILE
    done
    
else
    echo "$DATE [INFO] Aucun fichier récent, report de l'import." >> $LOG_FILE
fi
