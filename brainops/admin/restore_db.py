import argparse
import os
import subprocess

from dotenv import load_dotenv

from brainops.logger_setup import setup_logger

# Chargement des variables d'environnement
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
load_dotenv(env_path)
logger = setup_logger("db_restore")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": "3306",  # Port par défaut pour MySQL/MariaDB
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}


def restore_database(dump_file):
    if not os.path.exists(dump_file):
        logger.error(f"Fichier introuvable: {dump_file}")
        return

    confirm = (
        input(
            f"⚠️  Cette opération écrasera la base '{DB_CONFIG['database']}'. Continuer ? (oui/non) : "
        )
        .strip()
        .lower()
    )
    if confirm != "oui":
        logger.info("Annulé par l'utilisateur.")
        return

    try:
        logger.info(f"Restauration de {dump_file} en cours...")
        restore_cmd = [
            "mysql",
            "--protocol=TCP",
            f"--host={DB_CONFIG['host']}",
            f"--port={DB_CONFIG['port']}",
            f"--user={DB_CONFIG['user']}",
            f"--password={DB_CONFIG['password']}",
            DB_CONFIG["database"],
        ]
        with subprocess.Popen(
            ["gunzip", "-c", dump_file], stdout=subprocess.PIPE
        ) as unzip_proc:
            subprocess.run(restore_cmd, stdin=unzip_proc.stdout)
        logger.info("✅ Restauration terminée avec succès.")
    except Exception as e:
        logger.error(f"Erreur durant la restauration : {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Fichier .sql.gz à restaurer")
    args = parser.parse_args()

    restore_database(args.file)
