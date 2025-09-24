# brainops/services/coherence_checks.py

from typing import cast

from pymysql.cursors import DictCursor

from brainops.models.reconcile import Anomaly, NoteRow, Severity
from brainops.sql.db_connection import get_db_connection


def detect_archives_syntheses_incoherences() -> list[Anomaly]:
    anomalies: list[Anomaly] = []

    conn = get_db_connection()
    try:
        with conn.cursor(DictCursor) as cursor:
            cursor.execute("SELECT id, parent_id, file_path, status FROM obsidian_notes")
            notes = cast(list[NoteRow], list(cursor.fetchall()))

        # Index notes par ID
        notes_by_id = {n["id"]: n for n in notes}
        notes_by_parent: dict[int, list[NoteRow]] = {}

        for n in notes:
            pid = n.get("parent_id")
            if pid:
                notes_by_parent.setdefault(pid, []).append(n)

        for note in notes:
            note_id = note["id"]
            status = note["status"]
            parent_id = note.get("parent_id")

            # Cas : Synthèse sans archive
            if status == "synthesis" and note_id not in notes_by_parent:
                anomalies.append(
                    Anomaly(
                        severity=Severity.WARNING,
                        code="synthesis_without_archive",
                        message="Synthèse sans archive liée",
                        note_ids=(note_id,),
                        paths=(note["file_path"],),
                    )
                )

            # Cas : Archive sans parent (orpheline)
            if status == "archive" and (not parent_id or parent_id not in notes_by_id):
                anomalies.append(
                    Anomaly(
                        severity=Severity.ERROR,
                        code="archive_orphan",
                        message="Archive orpheline",
                        note_ids=(note_id,),
                        paths=(note["file_path"],),
                    )
                )

        return anomalies
    finally:
        conn.close()
