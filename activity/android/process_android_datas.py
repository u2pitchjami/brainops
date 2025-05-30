import mysql.connector
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from logger_setup import setup_logger

# Charger les variables d'environnement
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
load_dotenv(env_path)
logger = setup_logger("android_process")

def process_android_datas():

    DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
    except mysql.connector.Error as err:
        logger.error(f"Erreur connexion DB: {err}")
        exit()

    try:
        # Récupérer les timestamps distincts de android_tmp, triés par ordre chronologique
        cursor.execute("SELECT DISTINCT execution_timestamp FROM android_tmp ORDER BY execution_timestamp ASC;")
        timestamps = cursor.fetchall()

        prev_execution_timestamp = None  # Stocke le timestamp de la période précédente

        for row in timestamps:
            execution_timestamp = row["execution_timestamp"]
            
            # Vérifier si on traite une nouvelle journée
            if prev_execution_timestamp and execution_timestamp.date() == prev_execution_timestamp.date():
                period_start = prev_execution_timestamp
            else:
                period_start = execution_timestamp - timedelta(minutes=10)  # Assumer qu'on suit un pas de 10 min
                logger.info(f"🌙 Nouveau jour détecté, period_start initialisé à {period_start}")
            
            period_end = execution_timestamp  # Période de fin = exécution actuelle

            # Vérifier si la période existe déjà dans android_usage
            cursor.execute("SELECT COUNT(*) as count FROM android_usage WHERE timestamp = %s;", (execution_timestamp,))
            result = cursor.fetchone()

            if result["count"] == 0:
                # Sélectionner uniquement les enregistrements actifs dans la période
                cursor.execute("""
                    SELECT machine_id, package_name AS application_id, last_used, duration_seconds, execution_timestamp
                    FROM android_tmp
                    WHERE execution_timestamp = %s
                    AND last_used BETWEEN %s AND %s;
                """, (execution_timestamp, period_start, period_end))
                
                active_entries = cursor.fetchall()

                if active_entries:
                    for entry in active_entries:
                        cursor.execute("""
                            INSERT INTO android_usage (machine_id, application_id, last_used, duration_seconds, timestamp)
                            VALUES (%s, %s, %s, %s, %s);
                        """, (entry["machine_id"], entry["application_id"], entry["last_used"], entry["duration_seconds"], entry["execution_timestamp"]))
                    conn.commit()
                    logger.info(f"✅ Données insérées pour {execution_timestamp}")
                else:
                    logger.info(f"🔍 Aucune donnée active à insérer pour {execution_timestamp}")
            else:
                logger.info(f"❌ {execution_timestamp} déjà traité, pas d'insertion.")
            
            # Mise à jour du timestamp précédent pour la prochaine itération
            prev_execution_timestamp = execution_timestamp

    except mysql.connector.Error as e:
        logger.error(f"❌ Erreur MySQL lors du traitement des données : {e}")
    # Nettoyage des anciennes données de android_tmp en fonction du dernier timestamp de android_usage
    try:
        cursor.execute("SELECT MAX(timestamp) AS last_timestamp FROM android_usage;")
        result = cursor.fetchone()
        last_timestamp = result["last_timestamp"]

        if last_timestamp:
            cursor.execute("""
                DELETE FROM android_tmp 
                WHERE execution_timestamp < %s - INTERVAL 12 HOUR;
            """, (last_timestamp,))
            conn.commit()
            logger.info(f"🗑️ Suppression des entrées de android_tmp antérieures à {last_timestamp - timedelta(hours=12)}.")
        else:
            logger.info("ℹ️ Aucune donnée dans android_usage, pas de purge de android_tmp.")
    except mysql.connector.Error as e:
        logger.error(f"❌ Erreur lors du nettoyage de android_tmp : {e}")
    finally:
        cursor.close()
        conn.close()
        logger.info("🔌 Connexion MySQL fermée.")
