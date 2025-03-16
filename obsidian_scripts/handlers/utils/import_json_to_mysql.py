import json
import mysql.connector
from datetime import datetime

def clean_title(title, file_path):
    """ Vérifie si le titre est valide, sinon met un titre par défaut """
    if not title or title.strip() == "":
        print(f"⚠️ WARNING: Note sans titre détectée → Assignation d'un titre par défaut. (File: {file_path})")
        return "Untitled Note"
    return title.strip()

def clean_date(date_str):
    """ Vérifie et nettoie une date : retourne None si vide ou invalide """
    if not date_str or date_str.strip() == "":
        return None  # 🔥 Remplace les dates vides par NULL
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()  # ✅ Vérifie si le format est correct
    except ValueError:
        return None  # 🔥 Si le format est mauvais, retourne NULL


# Charger le JSON
with open("note_paths.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Connexion à MariaDB
conn = mysql.connector.connect(
    host="192.168.50.12",
    user="root",
    password="IFS2]`I}_.rCiw+2C;Z:aZA.!0^{HzfH",
    database="central_db"
)
cursor = conn.cursor()

# ------------------------------
# 1️⃣ INSÉRER LES CATÉGORIES
# ------------------------------
category_ids = {}

for category, details in data["categories"].items():
    cursor.execute(
        "INSERT INTO obsidian_categories (name, description, prompt_name) VALUES (%s, %s, %s)",
        (category.lower(), details["description"], details["prompt_name"])
    )
    category_id = cursor.lastrowid
    category_ids[category.lower()] = category_id  # ✅ Stocke l'ID principal

    if "subcategories" in details:
        for subcat, sub_details in details["subcategories"].items():
            cursor.execute(
                "INSERT INTO obsidian_categories (name, description, prompt_name, parent_id) VALUES (%s, %s, %s, %s)",
                (subcat.lower(), sub_details["description"], sub_details["prompt_name"], category_id)  # 🔥 category_id est bien le parent !
            )
            category_ids[subcat.lower()] = cursor.lastrowid  # ✅ Stocke l'ID de la sous-catégorie


# ------------------------------
# 2️⃣ INSÉRER LES DOSSIERS (Storage et Archives)
# ------------------------------
folder_types = set()  # Ensemble pour stocker les valeurs uniques

for folder, details in data["folders"].items():
    if "folder_type" in details:  # Vérifie si folder_type existe
        folder_types.add(details["folder_type"])

print("📌 Liste des folder_type trouvés dans le JSON :", folder_types)


folder_ids = {}

for folder, details in data["folders"].items():
    parent_folder = "/".join(folder.split("/")[:-1]) if "/" in folder else None
    parent_id = folder_ids.get(parent_folder) if parent_folder else None  # 🔥 Correction ici

    category_id = category_ids.get(details["category"].lower()) if details.get("category") else None
    subcategory_id = category_ids.get(details["subcategory"].lower()) if details.get("subcategory") else None

    cursor.execute(
        "INSERT INTO obsidian_folders (name, path, folder_type, parent_id, category_id, subcategory_id) VALUES (%s, %s, %s, %s, %s, %s)",
        (folder.split("/")[-1], details["path"], details["folder_type"], parent_id, category_id, subcategory_id)
    )
    folder_ids[folder] = cursor.lastrowid  # ✅ Stocke bien l'ID du dossier

# ------------------------------
# 3️⃣ INSÉRER LES NOTES
# ------------------------------
# 🔥 Définir un dossier par défaut pour les notes sans dossier
DEFAULT_FOLDER_NAME = "Z_Technical"
DEFAULT_FOLDER_PATH = "/mnt/user/Documents/Obsidian/notes/Z_Technical"

# Vérifier si le dossier par défaut est en base, sinon l'ajouter
if DEFAULT_FOLDER_NAME not in folder_ids:
    cursor.execute(
        "INSERT INTO obsidian_folders (name, path, folder_type) VALUES (%s, %s, %s)",
        (DEFAULT_FOLDER_NAME, DEFAULT_FOLDER_PATH, "technical")
    )
    folder_ids[DEFAULT_FOLDER_NAME] = cursor.lastrowid

# 🔹 Insérer les notes
for file_path, details in data["notes"].items():
    folder_path = "/".join(file_path.split("/")[:-1])  # 🔥 Correction ici
    folder_id = folder_ids.get(folder_path, folder_ids[DEFAULT_FOLDER_NAME])  # 🔥 Si inconnu, attribuer un dossier par défaut

    category_id = category_ids.get(details["category"].lower()) if details.get("category") else None
    subcategory_id = category_ids.get(details.get("subcategory", "").lower()) if details.get("subcategory") else None

    created_at = clean_date(details.get("created_at", ""))
    modified_at = clean_date(details.get("modified_at", ""))

    title = clean_title(details.get("title", ""), file_path)  

    cursor.execute(
        """
        INSERT INTO obsidian_notes (title, file_path, folder_id, category_id, subcategory_id, status, created_at, modified_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (title, file_path, folder_id, category_id, subcategory_id, details["status"], created_at, modified_at)
    )



# Commit et fermeture
conn.commit()
conn.close()

print("✅ Migration terminée avec succès !")
