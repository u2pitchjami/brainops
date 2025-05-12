import logging
from handlers.sql.db_connection import get_db_connection


logger = logging.getLogger("obsidian_notes." + __name__)

def update_obsidian_note(note_id, updates):
    logger.debug(f"[DEBUG] entrée update_obsidian_note note_id {note_id}")
    # Ouvre la connexion à la base de données
    conn = get_db_connection()
    if not conn:
        print("[ERROR] Impossible de se connecter à la base de données.")
        return

    # Crée un curseur pour exécuter la requête SQL
    cursor = conn.cursor()

    try:
        # Construire la partie SET de la requête SQL
        set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
        logger.debug(f"[DEBUG] set_clause : {set_clause}")
        # Paramètres pour la requête (les valeurs dans updates + note_id)
        values = list(updates.values()) + [note_id]

        # Requête SQL
        query = f"""
        UPDATE obsidian_notes
        SET {set_clause}
        WHERE id = %s
        """
        
        # Exécution de la requête
        cursor.execute(query, values)
        conn.commit()  # Sauvegarde les modifications dans la base de données
        
        logger.info(f"[INFO] Note avec id {note_id} mise à jour avec succès.")
    except Exception as e:
        logger.error(f"[ERROR] Erreur lors de la mise à jour de la note : {e}")
    finally:
        cursor.close()  # Toujours fermer le curseur
        conn.close()    # Fermer la connexion

def update_obsidian_tags(note_id, tags):
    # Ouvre la connexion à la base de données
    conn = get_db_connection()
    if not conn:
        print("[ERROR] Impossible de se connecter à la base de données.")
        return

    # Crée un curseur pour exécuter la requête SQL
    cursor = conn.cursor()

    try:
        # Supprimer les anciens tags associés à cette note
        cursor.execute("DELETE FROM obsidian_tags WHERE note_id = %s", (note_id,))

        # Ajouter les nouveaux tags
        for tag in tags:
            cursor.execute("INSERT INTO obsidian_tags (note_id, tag) VALUES (%s, %s)", (note_id, tag))

        # Commit les changements
        conn.commit()
        print(f"[INFO] Tags mis à jour pour la note {note_id}.")
    
    except Exception as e:
        print(f"[ERROR] Erreur lors de la mise à jour des tags : {e}")
    
    finally:
        # Fermer le curseur et la connexion
        cursor.close()
        conn.close()
