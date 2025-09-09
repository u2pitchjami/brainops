"""sql/db_temp_blocs.py"""

from __future__ import annotations

import json
from pathlib import Path

from mysql.connector.errors import IntegrityError

from brainops.sql.db_connection import get_db_connection
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def get_existing_bloc(
    note_id: int,
    filepath: str | Path,
    block_index: int,
    prompt: str,
    model: str,
    split_method: str,
    word_limit: int,
    source: str,
    logger: LoggerProtocol | None = None,
) -> tuple[str, str] | None:
    """
    Retourne (response, status) pour un bloc existant, ou None.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT response, status
            FROM obsidian_temp_blocks
            WHERE note_id = %s
              AND note_path = %s
              AND block_index = %s
              AND prompt = %s
              AND model_ollama = %s
              AND split_method = %s
              AND word_limit = %s
              AND source = %s
            LIMIT 1
            """,
            (
                note_id,
                str(filepath),
                block_index,
                prompt,
                model,
                split_method,
                word_limit,
                source,
            ),
        )
        row = cursor.fetchone()
        return (row[0], row[1]) if row else None
    except Exception as e:
        logger.error("[ERROR] get_existing_bloc: %s", e)
        return None
    finally:
        cursor.close()
        conn.close()


@with_child_logger
def insert_bloc(
    note_id: int,
    filepath: str | Path,
    block_index: int,
    content: str,
    prompt: str,
    model: str,
    split_method: str,
    word_limit: int,
    source: str,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Insère un nouveau bloc avec statut 'waiting'.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO obsidian_temp_blocks (
                note_id, note_path, block_index, content,
                prompt, model_ollama, split_method, word_limit, source, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'waiting')
            """,
            (
                note_id,
                str(filepath),
                block_index,
                content,
                prompt,
                model,
                split_method,
                word_limit,
                source,
            ),
        )
        conn.commit()
    except IntegrityError:
        logger.warning("[SKIP] Bloc déjà existant : index=%s path=%s", block_index, filepath)
    except Exception as e:
        logger.error("[ERROR] insert_bloc: %s", e)
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


@with_child_logger
def update_bloc_response(
    note_id: int,
    filepath: str | Path,
    block_index: int,
    response: str,
    source: str,
    *,
    status: str = "processed",
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Met à jour un bloc avec la réponse et le statut (par défaut 'processed').
    Filtrage par (note_id, note_path, source, block_index).
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE obsidian_temp_blocks
               SET response = %s,
                   status   = %s
             WHERE note_id    = %s
               AND note_path  = %s
               AND source     = %s
               AND block_index = %s
            """,
            (response.strip(), status, note_id, str(filepath), source, block_index),
        )
        conn.commit()
    except Exception as e:
        logger.error("[ERROR] update_bloc_response: %s", e)
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


@with_child_logger
def mark_bloc_as_error(filepath: str | Path, block_index: int, logger: LoggerProtocol | None = None) -> None:
    """
    Marque un bloc comme 'error' en se basant sur (note_path, block_index).
    (Chemin "compat" avec les anciens appels qui ne passaient pas note_id/source.)
    On ne touche pas aux blocs déjà 'processed'.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE obsidian_temp_blocks
               SET status = 'error'
             WHERE note_path = %s
               AND block_index = %s
               AND status <> 'processed'
            """,
            (str(filepath), block_index),
        )
        conn.commit()
    except Exception as e:
        logger.error("[ERROR] mark_bloc_as_error: %s", e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


@with_child_logger
def delete_blocs_by_path_and_source(
    note_id: int,
    file_path: str | Path,
    source: str,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Supprime des blocs dans obsidian_temp_blocks selon la stratégie:
      - source == "all"  -> purge tous les blocs de la note (par note_id)
      - source contient "*" -> supprime par LIKE sur source pour ce file_path
      - sinon -> supprime exactement (file_path, source)
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return
    cursor = conn.cursor()

    try:
        if source == "all":
            cursor.execute(
                "DELETE FROM obsidian_temp_blocks WHERE note_id = %s",
                (note_id,),
            )
        elif "*" in source:
            like_pattern = source.replace("*", "%")
            cursor.execute(
                """
                DELETE FROM obsidian_temp_blocks
                 WHERE note_path = %s
                   AND source LIKE %s
                """,
                (str(file_path), like_pattern),
            )
        else:
            cursor.execute(
                """
                DELETE FROM obsidian_temp_blocks
                 WHERE note_path = %s
                   AND source = %s
                """,
                (str(file_path), source),
            )

        conn.commit()
        logger.info("[DELETE] Blocs supprimés pour %s (source=%s)", file_path, source)
    except Exception as e:
        logger.error("[ERROR] delete_blocs_by_path_and_source(%s,%s): %s", file_path, source, e)
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


@with_child_logger
def get_blocks_and_embeddings_by_note(
    note_id: int, logger: LoggerProtocol | None = None
) -> tuple[list[str], list[list[float]]]:
    """
    Charge les blocs (content) et leurs embeddings (JSON dans `response`) pour une note donnée.
    Ne retourne jamais None: ([], []) en cas d'erreur.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] get_blocks_and_embeddings_by_note(%s)", note_id)
    conn = get_db_connection(logger=logger)
    if not conn:
        logger.error("[DB] Connexion à la base échouée")
        return [], []

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT block_index, content, response
              FROM obsidian_temp_blocks
             WHERE note_id = %s
               AND source = 'embeddings'
               AND status = 'processed'
             ORDER BY block_index
            """,
            (note_id,),
        )
        rows = cursor.fetchall()
    except Exception as e:
        logger.error("[DB] Erreur requête temp_blocks: %s", e)
        return [], []
    finally:
        cursor.close()
        conn.close()

    blocks: list[str] = []
    embeddings: list[list[float]] = []

    for row in rows:
        try:
            raw = row["response"]

            # 1er passage: si str, tenter un json.loads
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                parsed = raw

            # Si c’est encore une str qui ressemble à un JSON array → 2e loads
            if isinstance(parsed, str):
                s = parsed.strip()
                if s.startswith("[") and s.endswith("]"):
                    try:
                        parsed = json.loads(s)
                    except Exception:
                        parsed = None

            if isinstance(parsed, list) and parsed:
                vec = [float(x) for x in parsed]
                blocks.append(str(row["content"]))
                embeddings.append(vec)
            else:
                logger.warning("[DB LOAD] Embedding illisible au bloc %s", row["block_index"])

        except Exception as e:
            logger.error(
                "[DB LOAD] Erreur parsing embedding bloc %s : %s",
                row.get("block_index"),
                e,
            )

    return blocks, embeddings
