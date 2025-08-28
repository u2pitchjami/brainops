import mysql.connector
from utils.config import DB_CONFIG

from brainops.logger_setup import setup_logger

logger = setup_logger("db_connection")


def get_db_connection():
    """
    Établit une connexion à MySQL en utilisant les variables d'environnement.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"❌ ERREUR de connexion à MySQL : {err}")
        return None
