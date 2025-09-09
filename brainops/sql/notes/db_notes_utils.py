"""
# sql/db_notes_utils.py
"""

from __future__ import annotations

from difflib import SequenceMatcher
import os
from pathlib import Path
import re
import shutil

from brainops.header.header_utils import hash_source
from brainops.process_import.utils.paths import ensure_folder_exists
from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.sql.get_linked.db_get_linked_notes_utils import get_new_note_test_metadata
from brainops.utils.files import hash_file_content
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def link_notes_parent_child(
    incoming_note_id: int,
    yaml_note_id: int,
    *,
    logger: LoggerProtocol | None = None,
) -> bool:
    """
    Lie archive -> synthesis via parent_id.

    🔧 Règle métier observée dans ton code:
    - L'archive doit avoir parent_id = synthesis_id
    - La synthesis NE doit PAS pointer vers l'archive (évite cycle/confusion)
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            # on met parent_id sur la note "archive"
            safe_execute(
                cur,
                "UPDATE obsidian_notes SET parent_id=%s WHERE id=%s",
                (yaml_note_id, incoming_note_id),
                logger=logger,
            )
        conn.commit()
        logger.info("[LINK] archive %s → synthesis %s", incoming_note_id, yaml_note_id)
        return True
    except Exception as exc:  # pylint: disable=broad-except
        conn.rollback()
        logger.exception(
            "[LINK] Echec link archive=%s / synth=%s : %s",
            incoming_note_id,
            yaml_note_id,
            exc,
        )
        return False
    finally:
        conn.close()


@with_child_logger
def check_synthesis_and_trigger_archive(
    note_id: int, dest_path: str | Path, *, logger: LoggerProtocol | None = None
) -> None:
    """
    Si une synthesis est modifiée, s'assurer que l'archive liée:

    - est sous 'Archives/',
    - porte le bon nom,
    - a son YAML synchronisé.
    """
    from brainops.header.headers import (
        add_metadata_to_yaml,  # import local pour éviter cycles
    )

    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            row = safe_execute(
                cur,
                "SELECT file_path FROM obsidian_notes WHERE id=%s",
                (note_id,),
                logger=logger,
            ).fetchone()
            if not row:
                logger.warning("[SYNC] synthesis id=%s introuvable", note_id)
                return
            synthesis_path = Path(str(row[0]))
            synthesis_name = synthesis_path.stem

            # Archive actuelle (si existe)
            row = safe_execute(
                cur,
                "SELECT id, file_path FROM obsidian_notes WHERE parent_id=%s AND status='archive'",
                (note_id,),
                logger=logger,
            ).fetchone()

            if row:
                archive_id, current_archive_path = int(row[0]), Path(str(row[1]))
                synth_folder = Path(os.path.dirname(str(dest_path)))
                archive_folder = synth_folder / "Archives"
                ensure_folder_exists(archive_folder, logger=logger)

                new_archive_path = archive_folder / f"{synthesis_name} (archive).md"
                if current_archive_path != new_archive_path:
                    if new_archive_path.exists():
                        logger.warning("[SYNC] Fichier existe déjà: %s", new_archive_path)
                    else:
                        shutil.move(str(current_archive_path), str(new_archive_path))
                        safe_execute(
                            cur,
                            "UPDATE obsidian_notes SET file_path=%s WHERE id=%s",
                            (new_archive_path.as_posix(), archive_id),
                            logger=logger,
                        )
                        conn.commit()

                add_metadata_to_yaml(
                    note_id=archive_id,
                    filepath=new_archive_path,
                    status="archive",
                    synthesis_id=note_id,
                    logger=logger,
                )
            else:
                logger.warning("[SYNC] Aucune archive liée à la synthesis %s", note_id)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[SYNC] check_synthesis_and_trigger_archive(%s) : %s", note_id, exc)
    finally:
        conn.close()


@with_child_logger
def file_path_exists_in_db(
    file_path: str,
    src_path: str | None = None,
    *,
    logger: LoggerProtocol | None = None,
) -> int | None:
    """
    Retourne note_id si file_path (ou src_path) existe, sinon None.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            for path in [p for p in (src_path, file_path) if p]:
                row = safe_execute(
                    cur,
                    "SELECT id FROM obsidian_notes WHERE file_path=%s LIMIT 1",
                    (path,),
                    logger=logger,
                ).fetchone()
                if row:
                    return int(row[0])
        return None
    finally:
        conn.close()


@with_child_logger
def check_duplicate(
    note_id: int,
    file_path: str,
    threshold: float = 0.9,
    *,
    logger: LoggerProtocol | None = None,
) -> tuple[bool, list[dict]]:
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
        matches: list[dict] = []
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
