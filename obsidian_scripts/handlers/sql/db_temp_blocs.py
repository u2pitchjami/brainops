# handlers/sql/db_temp_blocs.py
import json
import logging
from logger_setup import setup_logger
from mysql.connector.errors import IntegrityError
from handlers.sql.db_connection import get_db_connection

#setup_logger("db_temp_blocs")
logger = logging.getLogger("db_temp_blocs")

def get_existing_bloc(note_id, filepath, block_index, prompt, model, split_method, word_limit, source):
    """
    Retourne (response, status) pour un bloc existant, ou None.
    """
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT response, status FROM obsidian_temp_blocks
            WHERE note_id = %s AND note_path = %s AND block_index = %s
            AND prompt = %s AND model_ollama = %s AND split_method = %s
            AND word_limit = %s AND source = %s
        """, (note_id, str(filepath), block_index, prompt, model, split_method, word_limit, source))
        return cursor.fetchone()

def insert_bloc(note_id, filepath, block_index, content, prompt, model, split_method, word_limit, source):
    """
    Insère un nouveau bloc avec statut 'waiting'.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO obsidian_temp_blocks (
                    note_id, note_path, block_index, content,
                    prompt, model_ollama, split_method, word_limit, source,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'waiting')
            """, (note_id, str(filepath), block_index, content, prompt, model, split_method, word_limit, source))
            conn.commit()
    except IntegrityError:
        logger.warning(
            "[SKIP] Bloc déjà existant : index=%s path=%s", block_index, filepath
        )
    except Exception as e:
        logger.error(f"[ERROR] Insertion bloc échouée : {e}")
        raise

def update_bloc_response(note_id, filepath, block_index, response, source, status="processed"):
    """
    Met à jour un bloc avec la réponse et le statut associé (par défaut : 'processed').
    """
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE obsidian_temp_blocks
            SET response = %s, status = %s
            WHERE note_id = %s AND note_path = %s AND source = %s AND block_index = %s
        """, (response.strip(), status, note_id, str(filepath), source, block_index))
        conn.commit()

def mark_bloc_as_error(note_id, filepath, block_index):
    """
    Marque un bloc comme ayant échoué ('error').
    """
    update_bloc_response(note_id, filepath, block_index, "", status="error")

def delete_blocs_by_path_and_source(note_id, file_path: str, source: str) -> None:
    """
    Supprime des blocs dans obsidian_temp_blocks selon le fichier et la source.

    :param file_path: Le chemin du fichier concerné
    :param source: La source des blocs ("synth*", "all", "archive", etc.)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if source == "all":
                cursor.execute("""
                    DELETE FROM obsidian_temp_blocks
                    WHERE note_id = %s
                """, (note_id,))

            elif "*" in source:
                like_pattern = source.replace("*", "%")
                cursor.execute("""
                    DELETE FROM obsidian_temp_blocks
                    WHERE note_path = %s AND source LIKE %s
                """, (str(file_path), like_pattern))

            else:
                cursor.execute("""
                    DELETE FROM obsidian_temp_blocks
                    WHERE note_path = %s AND source = %s
                """, (str(file_path), source))

            conn.commit()
            logger.info("[DELETE] Blocs supprimés pour %s (source=%s)", file_path, source)

    except Exception as e:
        logger.error(f"[ERROR] Suppression échouée pour {file_path} : {e}")
        raise

def get_blocks_and_embeddings_by_note(note_id):
    """
    Charge les blocs de texte et leurs embeddings (stockés dans `response`)
    pour une note donnée identifiée par note_id.
    """
    logger.debug("[DEBUG] get_blocks_and_embeddings_by_note")
    conn = get_db_connection()
    if not conn:
        logging.error("[DB] Connexion à la base échouée")
        return None

    cursor = conn.cursor(dictionary=True)  # dict pour accès via row["champ"]

    query = """
        SELECT block_index, content, response
        FROM obsidian_temp_blocks
        WHERE note_id = %s
          AND source = 'embeddings'
          AND status = 'processed'
        ORDER BY block_index;
    """
    try:
        cursor.execute(query, (note_id,))
        rows = cursor.fetchall()
    except Exception as e:
        logging.error(f"[DB] Erreur lors de l'exécution de la requête : {e}")
        return [], []

    blocks = []
    embeddings = []

    for row in rows:
        try:
            embedding = json.loads(row["response"])
            if isinstance(embedding, list) and len(embedding) > 0:
                blocks.append(row["content"])
                embeddings.append(embedding)
            else:
                logging.warning(f"[DB LOAD] Embedding vide au bloc {row['block_index']}")
        except Exception as e:
            logging.error(f"[DB LOAD] Erreur parsing embedding bloc {row['block_index']} : {e}")

    return blocks, embeddings
