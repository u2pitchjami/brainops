from db_connection import get_db_connection
import os
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

OBS_TABLES = [
    "obsidian_notes",
    "obsidian_categories",
    "obsidian_tags",
    "obsidian_temp_blocks", 
    "obsidian_folders"
]

def main():
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    for table in OBS_TABLES:
        print(f"\n🧱 Table : {table}")

        # Utiliser un curseur temporaire en mode tuple pour SHOW COLUMNS
        temp_cursor = conn.cursor()
        temp_cursor.execute(f"SHOW COLUMNS FROM {table}")
        columns = [row[0] for row in temp_cursor.fetchall()]
        temp_cursor.close()
        truc

        # Choix du champ de tri par priorité
        if "updated_at" in columns:
            order_field = "updated_at"
        elif "created_at" in columns:
            order_field = "created_at"
        elif "id" in columns:
            order_field = "id"
        else:
            order_field = None

        # Résumé
        cursor.execute(f"SELECT COUNT(*) AS total FROM {table}")
        total_rows = cursor.fetchone()["total"]

        print(f"📊 Total : {total_rows}")
        print(f"📅 Tri par : {order_field if order_field else 'aucun (ordre brut)'}")

        # Derniers enregistrements
        if order_field:
            cursor.execute(f"""
                SELECT * FROM {table}
                ORDER BY {order_field} DESC
                LIMIT 5
            """)
        else:
            cursor.execute(f"""
                SELECT * FROM {table}
                LIMIT 5
            """)

        rows = cursor.fetchall()
        headers = [desc[0] for desc in cursor.description]

        if rows:
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            print("Aucune donnée.")

        print("-" * 50)

    cursor.close()
    conn.close()
    

if __name__ == "__main__":
    main()
