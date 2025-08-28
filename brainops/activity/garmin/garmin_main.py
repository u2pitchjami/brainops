import os
from datetime import datetime

from dotenv import load_dotenv
from garmin_client import get_garmin_client
from garmin_heart_rate import get_garmin_heart_rate
from garmin_summary import fetch_summary, get_days_to_update, update_summary_db

from brainops.logger_setup import setup_logger

# Chemin dynamique basé sur le script en cours
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
# Charger le fichier .env
load_dotenv(env_path)
logger = setup_logger("garmin_import")


def main():
    client = get_garmin_client()
    if not client:
        logger.error("❌ Impossible de se connecter à Garmin, arrêt du script.")
        return

    logger.info("✅ Connexion réussie à Garmin Connect !")

    date_today = datetime.now().strftime("%Y-%m-%d")
    get_garmin_heart_rate(client)
    summary_today = fetch_summary(client)

    if not summary_today or not summary_today["last_sync"]:
        logger.warning(
            f"⏳ Aucune synchro détectée pour aujourd'hui ({date_today}), on attend."
        )
        return

    last_sync_time = datetime.strptime(summary_today["last_sync"], "%Y-%m-%d %H:%M:%S")
    days_to_update = get_days_to_update(last_sync_time)

    logger.info(f"📆 Jours à mettre à jour : {days_to_update}")

    for date_to_update in days_to_update:
        if date_to_update == date_today:
            summary = summary_today  # 🔥 Évite un appel API inutile
        else:
            get_garmin_heart_rate(client, date_to_update)
            summary = fetch_summary(client, date_to_update)

        if summary:
            update_summary_db(summary)
            logger.info(f"✅ Données mises à jour pour {date_to_update}")

    logger.info("🎉 Mise à jour complète terminée.")


if __name__ == "__main__":
    main()
