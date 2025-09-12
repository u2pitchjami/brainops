"""
# sql/db_notes_utils.py
"""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

from brainops.header.header_utils import hash_source
from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.sql.get_linked.db_get_linked_notes_utils import get_new_note_test_metadata
from brainops.utils.files import hash_file_content
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def check_duplicate(
    note_id: int,
    file_path: str,
    threshold: float = 0.9,
    *,
    logger: LoggerProtocol | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    """
    Cherche des doublons côté 'archive' via:

    - fuzzy match sur le titre,
    - source_hash,
    - content_hash.
    """
    logger = ensure_logger(logger, __name__)
    try:
        title, source, _author, _ = get_new_note_test_metadata(note_id, logger=logger)
        source_hash = hash_source(source) if source else None
        content_hash = hash_file_content(file_path)

        conn = get_db_connection(logger=logger)
        if not conn:
            return False, []
        matches: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        try:
            with conn.cursor() as cur:
                # fuzzy titre
                title_cleaned = clean_title(title or "")
                rows = safe_execute(
                    cur,
                    "SELECT id, title FROM obsidian_notes WHERE status=%s",
                    ("archive",),
                    logger=logger,
                ).fetchall()
                for existing_id, existing_title in rows:
                    similarity = SequenceMatcher(None, title_cleaned, existing_title or "").ratio()
                    if similarity >= threshold and existing_id not in seen_ids:
                        matches.append(
                            {
                                "id": int(existing_id),
                                "title": existing_title,
                                "similarity": round(similarity, 3),
                                "match_type": "title",
                            }
                        )
                        seen_ids.add(int(existing_id))

                # source_hash exact
                if source_hash:
                    for row in safe_execute(
                        cur,
                        "SELECT id, title FROM obsidian_notes WHERE status=%s AND source_hash=%s",
                        ("archive", source_hash),
                        logger=logger,
                    ).fetchall():
                        if int(row[0]) not in seen_ids:
                            matches.append(
                                {
                                    "id": int(row[0]),
                                    "title": row[1],
                                    "similarity": 1.0,
                                    "match_type": "source_hash",
                                }
                            )
                            seen_ids.add(int(row[0]))

                # content_hash exact
                for row in safe_execute(
                    cur,
                    "SELECT id, title FROM obsidian_notes WHERE status=%s AND content_hash=%s",
                    ("archive", content_hash),
                    logger=logger,
                ).fetchall():
                    if int(row[0]) not in seen_ids:
                        matches.append(
                            {
                                "id": int(row[0]),
                                "title": row[1],
                                "similarity": 1.0,
                                "match_type": "content_hash",
                            }
                        )
                        seen_ids.add(int(row[0]))
        finally:
            conn.close()

        if matches:
            logger.info("[DUP] %s doublon(s) détecté(s) pour note_id=%s", len(matches), note_id)
            return True, matches
        return False, []
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[DUP] check_duplicate(%s) : %s", note_id, exc)
        return False, []


def clean_title(title: str) -> str:
    """
    Nettoie le titre pour comparaison fuzzy (dates, underscores).
    """
    return re.sub(r"^\d{6}_?", "", (title or "").replace("_", " ")).lower()
