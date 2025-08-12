from logger_setup import setup_logger
from utils.config import DB_CONFIG
import os
import mysql.connector

logger = setup_logger("db_connection")

def get_db_connection():
    """ Établit une connexion à MySQL en utilisant les variables d'environnement """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"❌ ERREUR de connexion à MySQL : {err}")
        return None
