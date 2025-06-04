import os
import json
import argparse
import mysql.connector
from mysql.connector import Error
from pathlib import Path
from dotenv import load_dotenv
from logger_setup import setup_logger

# === INITIALISATION ENV + LOGGING ===
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
load_dotenv(env_path)

logger = setup_logger("listenbrainz_reclassify")

# === CONFIGURATION BASE + RÈGLES ===
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "brainops_user"),
    "password": os.getenv("DB_PASSWORD", "password123"),
    "database": os.getenv("DB_NAME", "brainops")
}
RULES_FILE = Path("scrobble_rules.json")

# === CHARGEMENT DES RÈGLES ===
def load_rules():
    try:
        with open(RULES_FILE, encoding="utf-8") as f:
            rules = json.load(f)
            logger.info(f"✅ {len(rules)} règles chargées depuis {RULES_FILE}")
            return rules
    except Exception as e:
        logger.error(f"❌ Erreur chargement des règles : {e}")
        raise

# === MÉCANISME DE MATCHING ===
def check_condition(value: str, pattern, match_type: str = "contains", logic: str = "or") -> bool:
    value = str(value or "").strip().lower()

    # Gestion null
    if match_type == "not_null":
        return bool(value)
    if match_type == "is_null":
        return not bool(value)

    # Gestion des patterns multiples
    patterns = pattern if isinstance(pattern, list) else [pattern]
    patterns = [str(p).strip().lower() for p in patterns]

    results = []
    for pat in patterns:
        if match_type == "contains":
            results.append(pat in value)
        elif match_type == "startswith":
            results.append(value.startswith(pat))
        elif match_type == "endswith":
            results.append(value.endswith(pat))
        elif match_type == "exact":
            results.append(value == pat)

    if logic == "and":
        return all(results)
    return any(results)  # default OR

def classify_from_rules(scrobble, rules):
    for rule in rules:
        if not rule.get("active", True):
            continue  # on saute la règle désactivée
        conditions = rule.get("conditions")
        if conditions:
            if all(
                check_condition(
                scrobble.get(cond["field"]),
                cond.get("pattern"),
                cond.get("match", "contains"),
                cond.get("logic", "or")
                )

                for cond in conditions
            ):
                return rule["scrobble_type"]
        else:
            field = rule["field"]
            pattern = rule.get("pattern", "")
            match_type = rule.get("match", "contains")
            value = scrobble.get(field)
            if check_condition(value, pattern, match_type):
                return rule["scrobble_type"]
    return "unknown"

# === TRAITEMENT PRINCIPAL ===
def reclassify_unknown_scrobbles(dry_run=False):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        logger.info("🔍 Connexion à la base réussie")
        rules = load_rules()

        cursor.execute("SELECT * FROM listenbrainz_tracks WHERE scrobble_type = 'unknown'")
        rows = cursor.fetchall()
        logger.info(f"🔎 {len(rows)} scrobbles à reclasser")

        updated = 0
        for row in rows:
            new_type = classify_from_rules(row, rules)
            if new_type != "unknown":
                logger.info(f"[{row['track_id']}] {row['artist'][:20]} -- {row['title']} → {new_type}")
                if not dry_run:
                    cursor.execute(
                        "UPDATE listenbrainz_tracks SET scrobble_type = %s WHERE track_id = %s",
                        (new_type, row["track_id"])
                    )
                    updated += 1

        if not dry_run:
            conn.commit()
            logger.info(f"✅ {updated} scrobbles mis à jour.")
        else:
            logger.info(f"ℹ️ {updated} scrobbles à modifier (dry-run activé).")

    except Error as e:
        logger.error(f"❌ Erreur SQL : {e}")
    except Exception as e:
        logger.error(f"❌ Erreur inattendue : {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            logger.info("🔌 Connexion à la base fermée.")

# === CLI ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Afficher sans modifier")
    args = parser.parse_args()

    logger.info("🚀 Lancement reclassification ListenBrainz")
    reclassify_unknown_scrobbles(dry_run=args.dry_run)
