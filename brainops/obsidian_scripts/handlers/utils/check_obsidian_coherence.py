import csv
import logging
import os
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv

# === Chargement des variables d'environnement ===
load_dotenv()
BASE_PATH = os.getenv("BASE_PATH")
LOG_DIR = os.getenv("LOG_DIR", ".")


# === Connexion DB ===
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


# === Setup logging ===
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("coherence_checker")

errors = []


# === Vérification des dossiers ===
def check_folders(conn) -> None:
    logger.info("\n📁 Vérification des dossiers...")
    cursor = conn.cursor(dictionary=True)

    physical_dirs = set()
    for root, dirs, _ in os.walk(BASE_PATH):
        dirs[:] = [d for d in dirs if not d.startswith(".")]  # exclude hidden dirs
        for d in dirs:
            full_path = os.path.join(root, d)
            physical_dirs.add(os.path.abspath(full_path))

    cursor.execute(
        "SELECT id, path, folder_type, category_id, subcategory_id FROM obsidian_folders"
    )
    db_folders = cursor.fetchall()
    db_paths = set(
        os.path.abspath(os.path.join(BASE_PATH, row["path"])) for row in db_folders
    )

    missing_in_db = physical_dirs - db_paths
    ghost_in_db = db_paths - physical_dirs

    for path in sorted(missing_in_db):
        errors.append(["missing_in_db", path])
        logger.info(f"  + {path}")

    for path in sorted(ghost_in_db):
        errors.append(["ghost_in_db", path])
        logger.info(f"  - {path}")

    cursor.execute("SELECT id FROM obsidian_categories")
    categories = set(row["id"] for row in cursor.fetchall())

    for folder in db_folders:
        ftype = folder["folder_type"]
        cat_id = folder["category_id"]
        subcat_id = folder["subcategory_id"]

        if ftype in ("archive", "storage") and cat_id is None:
            msg = f"{folder['path']} ({ftype}) devrait avoir une category_id"
            errors.append(["invalid_category", msg])
            logger.warning(f"❌ {msg}")

        if cat_id and cat_id not in categories:
            msg = f"category_id {cat_id} dans {folder['path']} n'existe pas"
            errors.append(["invalid_category_id", msg])
            logger.warning(f"❌ {msg}")

        if subcat_id and subcat_id not in categories:
            msg = f"subcategory_id {subcat_id} dans {folder['path']} n'existe pas"
            errors.append(["invalid_subcategory_id", msg])
            logger.warning(f"❌ {msg}")


# === Vérification des notes ===
def check_notes(conn) -> None:
    logger.info("\n📝 Vérification des notes...")
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, file_path FROM obsidian_notes")
    notes = cursor.fetchall()

    notes_missing_file = []
    for note in notes:
        fpath = os.path.abspath(note["file_path"])
        if not os.path.isfile(fpath):
            notes_missing_file.append(fpath)
            errors.append(["note_missing_file", fpath])

    all_md_files = set()
    for root, _, files in os.walk(BASE_PATH):
        if any(part.startswith(".") for part in root.split(os.sep)):
            continue
        for f in files:
            if f.endswith(".md"):
                all_md_files.add(os.path.abspath(os.path.join(root, f)))

    db_note_paths = set(os.path.abspath(note["file_path"]) for note in notes)
    md_files_missing_in_db = all_md_files - db_note_paths

    for f in sorted(md_files_missing_in_db):
        errors.append(["file_missing_in_db", f])
        logger.info(f"  + {f}")


# === Vérification des tags ===
def check_tags(conn) -> None:
    logger.info("\n🏷️  Vérification des tags...")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.note_id FROM obsidian_tags t
        LEFT JOIN obsidian_notes n ON t.note_id = n.id
        WHERE n.id IS NULL
    """
    )
    rows = cursor.fetchall()
    for (note_id,) in rows:
        errors.append(["tag_orphan", note_id])
        logger.info(f"  - tag lié à note_id inexistant : {note_id}")


# === Export CSV ===
def export_to_csv() -> None:
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(LOG_DIR, f"coherence_errors_{date_str}.csv")
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["type", "detail"])
        for row in errors:
            writer.writerow(row)
    logger.info(f"📄 Rapport CSV généré : {filename}")


# === MAIN ===
def main() -> None:
    logger.info("=== DÉMARRAGE DE L'AUDIT COHÉRENCE OBSIDIAN ===")
    try:
        conn = get_db_connection()
        check_folders(conn)
        check_notes(conn)
        check_tags(conn)
        conn.close()
    except Exception as e:
        logger.error(f"❌ Erreur durant le check : {e}")

    export_to_csv()
    logger.info("=== AUDIT TERMINÉ ===")


if __name__ == "__main__":
    main()
