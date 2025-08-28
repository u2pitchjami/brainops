import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from brainops.logger_setup import setup_logger

# Chargement des variables d'environnement
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
load_dotenv(env_path)
logger = setup_logger("db_backup")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "3306"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME"),
}

BACKUP_DB_DIR = os.getenv("BACKUP_DB_DIR", "../db_sav")
IMAGE_NAME = os.getenv("CLIENT_IMAGE", "clients_db:latest")
NETWORK = os.getenv("DB_NETWORK", "brainops_net")


def backup_database():
    """Crée une sauvegarde compressée de la base MariaDB via un conteneur client."""
    os.makedirs(BACKUP_DB_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_file = os.path.join(
        BACKUP_DB_DIR, f"{timestamp}_{DB_CONFIG['database']}.sql.gz"
    )

    try:
        logger.info("Sauvegarde de la base en cours...")
        with open(backup_file, "wb") as f:
            dump_cmd = [
                "docker", "run", "--rm",
                "--network", NETWORK,
                "--entrypoint", "mysqldump",
                IMAGE_NAME,
                f"-h{DB_CONFIG['host']}",
                f"-P{DB_CONFIG['port']}",
                f"-u{DB_CONFIG['user']}",
                f"-p{DB_CONFIG['password']}",
                DB_CONFIG["database"],
            ]
            proc_dump = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE)
            proc_gzip = subprocess.Popen(["gzip"], stdin=proc_dump.stdout, stdout=f)
            proc_dump.stdout.close()
            proc_gzip.communicate()

        logger.info(f"Sauvegarde effectuée: {backup_file}")
        
        result = subprocess.run(["gzip", "-t", backup_file], capture_output=True)
        if result.returncode == 0:
            logger.info("Archive gzip valide ✅")
        else:
            logger.error("Archive corrompue ❌")
        
        with subprocess.Popen(["zcat", backup_file], stdout=subprocess.PIPE) as proc:
            head = [next(proc.stdout).decode("utf-8") for _ in range(20)]
        if any("CREATE TABLE" in line or "INSERT INTO" in line for line in head):
            logger.info("Le dump contient des données SQL ✅")
        else:
            logger.error("Le dump semble vide ou incomplet ❌")

        
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde: {e}")


if __name__ == "__main__":
    backup_database()
