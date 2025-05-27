import mysql.connector
from logger_setup import setup_logger
from datetime import datetime
from garminconnect import Garmin
from dotenv import load_dotenv
import os

logger = setup_logger("garmin_import")

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

def get_garmin_client():
    
    EMAIL = os.getenv('EMAIL')
    PASSWORD = os.getenv('PASSWORD')
    try:
        client = Garmin(EMAIL, PASSWORD)
        client.login()
        return client
    except Exception as e:
        logger.error(f"Erreur connexion Garmin: {e}")
        return None