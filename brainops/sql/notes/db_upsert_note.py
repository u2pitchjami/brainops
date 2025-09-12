"""
# sql/db_notes.py
"""

from __future__ import annotations

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.note import Note
from brainops.sql.db_connection import get_db_connection
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def upsert_note_from_model(note: Note, *, logger: LoggerProtocol | None = None) -> int:
    """
    Upsert idempotent par `file_path` (UNIQUE) avec retour d'id via LAST_INSERT_ID(id).
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)

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
            if rid and rid[0]:
                nid = int(rid[0])
                logger.debug("[NOTES] upsert %s -> id=%s", note.file_path, nid)
            else:
                raise BrainOpsError("Upsert Note KO", code=ErrCode.DB, ctx={"note": note})
            return nid
    except Exception as exc:
        raise BrainOpsError("Upsert Note KO", code=ErrCode.DB, ctx={"note": note}) from exc
    finally:
        conn.close()
