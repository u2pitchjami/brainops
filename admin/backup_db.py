import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from logger_setup import setup_logger

# Chargement des variables d'environnement
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
load_dotenv(env_path)
logger = setup_logger("db_backup")

DB_CONFIG = {
    "user": os.getenv("DB_USER"),
    "database": os.getenv("DB_NAME"),
}

BACKUP_DB_DIR = os.getenv("BACKUP_DB_DIR", "../db_sav")


def backup_database():
    """Crée une sauvegarde compressée de la base MariaDB."""
    backup_dir = BACKUP_DB_DIR
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_file = os.path.join(backup_dir, f"{timestamp}_{DB_CONFIG['database']}.sql.gz")

        
    try:
        logger.info("Sauvegarde de la base en cours...")
        with open(backup_file, "wb") as f:
            dump_cmd = [
                "mysqldump",
                "--column-statistics=0",
                f"-u{DB_CONFIG['user']}",
                DB_CONFIG['database']
            ]
            proc_dump = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE)
            proc_gzip = subprocess.Popen(["gzip"], stdin=proc_dump.stdout, stdout=f)
            proc_dump.stdout.close()
            proc_gzip.communicate()
            
        logger.info(f"Sauvegarde effectuée: {backup_file}")
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde: {e}")

if __name__ == "__main__":
    
    backup_database()