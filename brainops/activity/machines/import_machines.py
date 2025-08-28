#!/usr/bin/env python3
"""
Import CSV files from Windows activity tracker into MariaDB using mysql.connector instead of pymysql.
"""

import csv
import glob
import os
import subprocess
from datetime import datetime

import mysql.connector
import pytz
from dotenv import load_dotenv
from mysql.connector import Error

from brainops.logger_setup import setup_logger

# Chemin dynamique basé sur le script en cours
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
# Charger le fichier .env
load_dotenv(env_path)


PARIS_TZ = pytz.timezone("Europe/Paris")

logger = setup_logger("imports_windows")

# --- CONFIG ---
IMPORT_DIR = "/mnt/user/Zin-progress/brain_ops/mariadb-import"
LOG_FILE = "/home/pipo/data/logs/brainops/activity/machines/brainops_import.log"
PROCESS_RECAP = (
    "/home/pipo/dev/brain_ops/activity/machines/process_recap.sql"  # script SQL externe
)
MAX_LENGTHS = {"application_name": 255, "window_title": 500}


def get_db_connection():
    """
    Connexion DB via variables d'environnement.
    """
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
    )


def clean_row(row):
    """
    Nettoyer et tronquer une ligne CSV.
    """
    if len(row) < 9:  # moins de colonnes que prévu
        logger.warning("Ligne ignorée (colonnes insuffisantes) : %s", row)
        return None
    cleaned = []
    for idx, col in enumerate(row):
        value = col.strip() if col else None
        if idx == 6 and value and len(value) > MAX_LENGTHS["application_name"]:
            logger.warning("Tronqué ApplicationName : %s", value[:50])
            value = value[: MAX_LENGTHS["application_name"]]
        if idx == 8 and value and len(value) > MAX_LENGTHS["window_title"]:
            logger.warning("Tronqué WindowTitle : %s", value[:50])
            value = value[: MAX_LENGTHS["window_title"]]
        cleaned.append(value)
    return cleaned


def prepare_staging(cursor):
    """
    Préparer recap_staging comme dans l'ancien Bash.
    """
    cursor.execute("DROP TEMPORARY TABLE IF EXISTS recap_temp;")
    cursor.execute("DROP TEMPORARY TABLE IF EXISTS recap_staging;")
    cursor.execute("CREATE TEMPORARY TABLE recap_temp LIKE recap;")
    cursor.execute("CREATE TEMPORARY TABLE recap_staging LIKE recap_temp;")
    cursor.execute("ALTER TABLE recap_staging DROP INDEX unique_entry;")
    logger.info("✅ recap_staging recréée avec succès.")


def import_file(cursor, file_path):
    """
    Importer un fichier CSV dans recap_staging.
    """
    inserted_rows = 0
    with open(file_path, encoding="utf-8", newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter="|")
        for row_idx, row in enumerate(reader):
            if row_idx < 2:  # ignorer header + ligne de tirets
                continue
            if not any(row):
                continue
            cleaned = clean_row(row)
            if not cleaned:
                continue
            try:
                cursor.execute(
                    """
                    INSERT INTO recap_staging
                    (machine_id, ip_address, timestamp, user_id, user_name, application_id, \
                        application_name, window_id, window_title, duration)
                    VALUES (NULL, %s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    cleaned[2:11],  # skip les 2 colonnes "||"
                )
                inserted_rows += 1
            except Error as e:
                logger.error("Erreur insertion ligne (%s) : %s", e, cleaned)
    return inserted_rows


def run_process_recap():
    """
    Exécuter le script SQL externe.
    """
    try:
        subprocess.run(
            [
                "mysql",
                f"-h{os.getenv('DB_HOST')}",
                f"-u{os.getenv('DB_USER')}",
                f"-p{os.getenv('DB_PASSWORD')}",
                os.getenv("DB_NAME"),
                "-e",
                f"SOURCE {PROCESS_RECAP}",
            ],
            check=True,
        )
        logger.info("✅ Script PROCESS_RECAP exécuté avec succès.")
    except subprocess.CalledProcessError as e:
        logger.critical("❌ Erreur lors du PROCESS_RECAP : %s", e)


def main():
    files = glob.glob(os.path.join(IMPORT_DIR, "recap_windows_*.csv"))
    if not files:
        logger.info("Aucun fichier trouvé pour import.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Préparer la staging table
        prepare_staging(cursor)

        # lignes avant import
        cursor.execute("SELECT COUNT(*) FROM recap;")
        before = cursor.fetchone()[0]

        total_inserted = 0
        for file_path in files:
            logger.info("Traitement fichier : %s", file_path)
            inserted = import_file(cursor, file_path)
            total_inserted += inserted
            # Déplacer le fichier après import
            archive_dir = os.path.join(IMPORT_DIR, datetime.now().strftime("%Y-%m-%d"))
            os.makedirs(archive_dir, exist_ok=True)
            new_name = os.path.join(
                archive_dir, os.path.basename(file_path) + ".processed"
            )
            os.rename(file_path, new_name)
            logger.info("Fichier archivé : %s", new_name)

        conn.commit()

        run_process_recap()

        # lignes après import
        cursor.execute("SELECT COUNT(*) FROM recap;")
        after = cursor.fetchone()[0]
        logger.info("Import terminé. %d nouvelles lignes ajoutées.", after - before)

    except Error as e:
        logger.critical("Erreur critique dans l'import : %s", e)
    finally:
        if "conn" in locals() and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()
