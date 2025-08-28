from brainops.logger_setup import setup_logger
import logging
import os
import mysql.connector

#setup_logger("db_connection", logging.INFO)
logger = logging.getLogger("db_connection")

# Configuration de la base via les variables d'environnement
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}

def get_db_connection():
    """ Établit une connexion à MySQL en utilisant les variables d'environnement """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"❌ ERREUR de connexion à MySQL : {err}")
        return None
