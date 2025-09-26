# brainops/services/category_coherence_check.py

from datetime import datetime
from pathlib import Path
from typing import cast

from brainops.io.note_writer import merge_metadata_in_note
from brainops.models.reconcile import Anomaly, NoteRow, Severity
from brainops.sql.db_connection import get_db_connection, get_dict_cursor
from brainops.sql.db_utils import safe_execute_dict
from brainops.sql.get_linked.db_get_linked_folders_utils import get_category_context_from_folder
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


def get_all_notes_for_category_check(limit: int = 10) -> list[NoteRow]:
    conn = get_db_connection()
    try:
        with get_dict_cursor(conn) as cur:
            safe_execute_dict(
                cur,
                """
                SELECT id, file_path, folder_id, category_id, subcategory_id, status
                FROM obsidian_notes
                ORDER BY RAND() LIMIT %s
                """,
                (limit,),
            )
            notes = cast(list[NoteRow], list(cur.fetchall()))
            return notes
    finally:
        conn.close()


@with_child_logger
def check_file_path_category_coherence(
    auto_fix: bool = False, sample_size: int = 10, logger: LoggerProtocol | None = None
) -> list[Anomaly]:
    anomalies = []
    logger = ensure_logger(logger, __name__)
    notes = get_all_notes_for_category_check(limit=sample_size)
    logger.debug("🔍 Vérification de la cohérence file_path vs catégorie pour %d notes", len(notes))

    for note in notes:
        try:
            folder_path = Path(note["file_path"]).parent
            classification = get_category_context_from_folder(str(folder_path), logger=logger)
            logger.debug(
                "  • Note %s : folder_id=%s, category_id=%s, subcategory_id=%s, status=%s",
                note["file_path"],
                note["folder_id"],
                note["category_id"],
                note["subcategory_id"],
                note["status"],
            )
            logger.debug(
                "    → Classification attendue : folder_id=%s, category_id=%s, subcategory_id=%s, status=%s",
                classification.folder_id,
                classification.category_id,
                classification.subcategory_id,
                classification.status,
            )

            mismatch = (
                note["category_id"] != classification.category_id
                or note["subcategory_id"] != classification.subcategory_id
                or note["folder_id"] != classification.folder_id
                or note["status"] != classification.status
            )

            if mismatch:
                logger.warning("🔍 Incohérence détectée pour : %s", note["file_path"])

                if auto_fix:
                    logger.info("🔧 Correction automatique pour la note id=%s", note["id"])
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    update_obsidian_note(
                        note_id=note["id"],
                        updates={
                            "folder_id": classification.folder_id,
                            "category_id": classification.category_id,
                            "subcategory_id": classification.subcategory_id,
                            "status": classification.status,
                            "modified_at": now,
                        },
                        logger=logger,
                    )
                    if classification.subcategory_name is None:
                        merge_metadata_in_note(
                            filepath=note["file_path"],
                            updates={
                                "category": classification.category_name,
                            },
                            logger=logger,
                        )
                    else:
                        merge_metadata_in_note(
                            filepath=note["file_path"],
                            updates={
                                "category": classification.category_name,
                                "subcategory": classification.subcategory_name,
                            },
                            logger=logger,
                        )
                else:
                    anomalies.append(
                        Anomaly(
                            severity=Severity.WARNING,
                            code="category_mismatch",
                            message="Incohérence entre file_path et catégorisation",
                            note_ids=(note["id"],),
                            paths=(note["file_path"],),
                        )
                    )

        except Exception as exc:
            logger.warning("❌ Erreur sur %s : %s", note["file_path"], exc)
            # handle_errored_file(
            #     note_id=note["id"],
            #     filepath=note["file_path"],
            #     exc=str(exc),
            #     logger=logger
            # )

    return anomalies
