# sql/db_notes.py
from __future__ import annotations

from typing import Optional

from brainops.models.note import Note
from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def upsert_note_from_model(
    note: Note, *, logger: LoggerProtocol | None = None
) -> Optional[int]:
    """
    Upsert idempotent par `file_path` (UNIQUE) avec retour d'id via LAST_INSERT_ID(id).
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO obsidian_notes
                  (parent_id, title, file_path, folder_id,
                   category_id, subcategory_id, status, summary,
                   source, author, project, created_at, modified_at,
                   word_count, content_hash, source_hash, lang)
                VALUES
                  (%s,%s,%s,%s,
                   %s,%s,%s,%s,
                   %s,%s,%s,%s,%s,
                   %s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  parent_id=VALUES(parent_id),
                  title=VALUES(title),
                  folder_id=VALUES(folder_id),
                  category_id=VALUES(category_id),
                  subcategory_id=VALUES(subcategory_id),
                  status=VALUES(status),
                  summary=VALUES(summary),
                  source=VALUES(source),
                  author=VALUES(author),
                  project=VALUES(project),
                  created_at=VALUES(created_at),
                  modified_at=VALUES(modified_at),
                  word_count=VALUES(word_count),
                  content_hash=VALUES(content_hash),
                  source_hash=VALUES(source_hash),
                  lang=VALUES(lang),
                  id=LAST_INSERT_ID(id)
                """,
                note.to_upsert_params(),
            )
            cur.execute("SELECT LAST_INSERT_ID()")
            rid = cur.fetchone()
            conn.commit()
            nid = int(rid[0]) if rid and rid[0] else None
            logger.debug("[NOTES] upsert %s -> id=%s", note.file_path, nid)
            return nid
    finally:
        conn.close()


@with_child_logger
def get_note_by_path(
    file_path: str, *, logger: LoggerProtocol | None = None
) -> Optional[Note]:
    """
    Récupère une note par `file_path` (unique). Retourne None si introuvable.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None

    try:
        with conn.cursor(dictionary=True) as cur:
            row = safe_execute(
                cur,
                """
                SELECT id, parent_id, title, file_path, folder_id, category_id, subcategory_id,
                       status, summary, source, author, project,
                       created_at, modified_at, updated_at,
                       word_count, content_hash, source_hash, lang
                  FROM obsidian_notes
                 WHERE file_path=%s
                 LIMIT 1
                """,
                (file_path,),
                logger=logger,
            ).fetchone()
            return Note.from_row(row) if row else None
    finally:
        conn.close()


@with_child_logger
def delete_note_by_path(
    file_path: str, *, logger: LoggerProtocol | None = None
) -> bool:
    """
    Supprime une note par `file_path`. Retourne True si supprimée.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            res = safe_execute(
                cur,
                "DELETE FROM obsidian_notes WHERE file_path=%s",
                (file_path,),
                logger=logger,
            )
        conn.commit()
        deleted = res.rowcount > 0  # type: ignore[attr-defined]
        return deleted
    finally:
        conn.close()
