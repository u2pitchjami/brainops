#!/bin/bash

SCRIPT_DIR=$(dirname "$(realpath "$0")")
source ${SCRIPT_DIR}/.config.cfg

NOW=$(date +%s)
FILES_FOUND=0
SQL_COMMAND=""

# Construire une série de commandes SQL pour chaque fichier CSV disponible
for file in $IMPORT_DIR/recap_windows_*.csv; do
    
    if [ -f "$file" ]; then
        FILE_TIME=$(stat -c %Y "$file")
        AGE=$((NOW - FILE_TIME))

        if [ $AGE -le $THRESHOLD_TIME ]; then
            FILES_FOUND=$((FILES_FOUND + 1))
            echo "$DATE_LOGS [INFO] Ajout de $file dans le process d'import..." >> $LOG_FILE
            
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
            echo "$DATE_LOGS [WARNING] Fichier $file trop vieux (+10 min), ignoré." >> $LOG_FILE
        fi
    fi
done

# Si au moins un fichier a été ajouté, exécuter le SQL complet
if [ $FILES_FOUND -ge 1 ]; then
    echo "$DATE_LOGS [INFO] Importation de $FILES_FOUND fichiers en une seule exécution..." >> $LOG_FILE

    # 🔥 Récupérer le nombre de lignes avant l'import
    NB_LIGNES_AVANT=$(mysql --defaults-file=$CNF_FILE brainops_db -N -B -e "SELECT COUNT(*) FROM recap;")

    mysql --defaults-file=$CNF_FILE brainops_db -e "
        CREATE TEMPORARY TABLE recap_temp LIKE recap;
        CREATE TEMPORARY TABLE recap_staging LIKE recap_temp;
        ALTER TABLE recap_staging DROP INDEX unique_entry;
        $SQL_COMMAND
        SOURCE $PROCESS_RECAP;
    "
    # 🔥 Récupérer le nombre de lignes après l'import
    NB_LIGNES_APRES=$(mysql --defaults-file=$CNF_FILE brainops_db -N -B -e "SELECT COUNT(*) FROM recap;")

    # 🔥 Calculer le nombre de nouvelles lignes insérées
    NB_LIGNES=$((NB_LIGNES_APRES - NB_LIGNES_AVANT))
    echo "${DATE_LOGS} - [INFO] Nombre de lignes ajoutées: $NB_LIGNES" | tee -a "$LOG_FILE"
    # Déplacer les fichiers SEULEMENT après l'import MySQL
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
