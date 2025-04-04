# handlers/sql/db_temp_blocs.py

import logging
from logger_setup import setup_logger
from mysql.connector.errors import IntegrityError
from handlers.sql.db_connection import get_db_connection

setup_logger("db_temp_blocs")
logger = logging.getLogger("db_temp_blocs")

def get_existing_bloc(filepath, block_index, prompt, model, split_method, word_limit, source):
    """
    Retourne (response, status) pour un bloc existant, ou None.
    """
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT response, status FROM obsidian_temp_blocks
            WHERE note_path = %s AND block_index = %s
            AND prompt = %s AND model_ollama = %s AND split_method = %s
            AND word_limit = %s AND source = %s
        """, (str(filepath), block_index, prompt, model, split_method, word_limit, source))
        return cursor.fetchone()

def insert_bloc(filepath, block_index, content, prompt, model, split_method, word_limit, source):
    """
    Insère un nouveau bloc avec statut 'waiting'.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO obsidian_temp_blocks (
                    note_path, block_index, content,
                    prompt, model_ollama, split_method, word_limit, source,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'waiting')
            """, (str(filepath), block_index, content, prompt, model, split_method, word_limit, source))
            conn.commit()
    except IntegrityError:
        logger.warning(
            "[SKIP] Bloc déjà existant : index=%s path=%s", block_index, filepath
        )
    except Exception as e:
        logger.error(f"[ERROR] Insertion bloc échouée : {e}")
        raise

def update_bloc_response(filepath, block_index, response, source, status="processed"):
    """
    Met à jour un bloc avec la réponse et le statut associé (par défaut : 'processed').
    """
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE obsidian_temp_blocks
            SET response = %s, status = %s
            WHERE note_path = %s AND source = %s AND block_index = %s
        """, (response.strip(), status, str(filepath), source, block_index))
        conn.commit()

def mark_bloc_as_error(filepath, block_index):
    """
    Marque un bloc comme ayant échoué ('error').
    """
    update_bloc_response(filepath, block_index, "", status="error")

def delete_blocs_by_path_and_source(file_path: str, source: str) -> None:
    """
    Supprime tous les blocs liés à une note et une source spécifique.

    :param note_path: Le chemin de la note concernée
    :param source: La source associée (ex: "normal", "archive", etc.)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM obsidian_temp_blocks
                WHERE note_path = %s AND source = %s
            """, (str(file_path), source))
            conn.commit()
            logger.info("[DELETE] Blocs supprimés pour %s (source=%s)", file_path, source)
    except Exception as e:
        logger.error(f"[ERROR] Suppression échouée pour {file_path} : {e}")
        raise
