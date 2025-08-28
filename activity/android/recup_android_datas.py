import mysql.connector
import time
import csv
import re
import os
import shutil
from datetime import datetime
from dotenv import load_dotenv
from brainops.logger_setup import setup_logger


# Chemin dynamique basé sur le script en cours
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
# Charger le fichier .env
load_dotenv(env_path)
logger = setup_logger("android_import")

def connect_db():
    
    DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Erreur connexion DB: {err}")
        return None

def get_machine_id(device_name):
    """Récupère le machine_id depuis la table machines en fonction du device_name"""
    conn = connect_db()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute("SELECT machine_id FROM machines WHERE machine_name = %s", (device_name,))
    result = cursor.fetchone()

    machine_id = result[0] if result else None
    if machine_id:
        logger.info(f"[✅] Machine ID trouvé pour {device_name} : {machine_id}")
    else:
        logger.info(f"[❌] Machine {device_name} non trouvée en base !")

    cursor.close()
    conn.close()
    return machine_id

def process_log_file(file_path):
    """Traite un fichier de log et insère les données dans la table temporaire"""
    conn = connect_db()
    if not conn:
        return
    cursor = conn.cursor()
       
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        first_row = next(reader, None)  # Lire la première ligne pour choper device_name
        
        if not first_row:
            logger.info(f"[⚠] Fichier vide, ignoré : {file_path}")
            return
        
        device_name = first_row["device_name"]  # ✅ Récupérer le device_name ici
        machine_id = get_machine_id(device_name)

        if not machine_id:
            logger.error(f"[❌] Impossible de récupérer machine_id pour {device_name}, fichier ignoré.")
            return

        # Revenir au début du fichier après la première ligne lue
        csvfile.seek(0)
        next(reader)  # Ignorer l'en-tête

        for row in reader:
            execution_timestamp = row["execution_timestamp"]
            package_name = row["package_name"]
            last_used = datetime.strptime(row["last_used"], "%Y-%m-%d %H:%M:%S")
            duration_seconds = int(row["duration_seconds"])

            try:
                cursor.execute("""
                    INSERT INTO android_tmp (machine_id, execution_timestamp, package_name, last_used, duration_seconds)
                    VALUES (%s, %s, %s, %s, %s)
                """, (machine_id, execution_timestamp, package_name, last_used, duration_seconds))
                conn.commit()
                logger.info(f"[✅] {device_name} | {package_name} ({duration_seconds}s) inséré dans android_tmp")
                
            except mysql.connector.Error as e:
                logger.error(f"[❌] Erreur MySQL : {e}")

    cursor.close()
    conn.close()



def scan_and_process_logs():
    """Scan le dossier de logs et traite tous les fichiers correspondant au pattern"""
    
    # 2️⃣ Sleep de 30 secondes pour éviter le décalage avec Android
    logger.info("⏳ Pause de 30 secondes pour attendre la fin de l'envoi Android...")
    time.sleep(30)
    
    IMPORT_DIR = os.getenv('IMPORT_DIR')
    
    print("[📂] IMPORT_DIR", IMPORT_DIR)
    
    files = [f for f in os.listdir(IMPORT_DIR) if f.startswith("recap_android_") and f.endswith(".csv")]
    if not files:
        logger.info("[📂] Aucun fichier à traiter.")
        return

    for file_name in sorted(files):  # Trier par nom pour traiter dans l'ordre chronologique
        file_path = os.path.join(IMPORT_DIR, file_name)
        logger.info(f"[🔍] Traitement du fichier : {file_name}")
        file_date = datetime.now().strftime("%y%m%d") 
        process_log_file(file_path)
        # Construire le chemin du dossier d’archive
        archive_subdir = os.path.join(IMPORT_DIR, file_date)
        os.makedirs(archive_subdir, exist_ok=True)  # Créer le dossier si nécessaire

        # Construire le chemin du fichier archivé
        archived_file_path = os.path.join(archive_subdir, f"{file_name}.processed")

        # Déplacer le fichier dans l'archive
        shutil.move(file_path, archived_file_path)
        logger.info(f"📂 Fichier archivé : {archived_file_path}")

if __name__ == "__main__":
    scan_and_process_logs()
    from process_android_datas import process_android_datas
    process_android_datas()