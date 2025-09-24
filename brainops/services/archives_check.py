# brainops/services/archives_check.py

from collections import defaultdict
from typing import cast

from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from brainops.io.move_error_file import handle_errored_file
from brainops.models.reconcile import Anomaly, FixStats, NoteRow, Severity
from brainops.sql.db_connection import get_db_connection
from brainops.utils.config import Z_STORAGE_PATH
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def check_archives_syntheses_from_hash_source(
    auto_fix: bool = False, logger: LoggerProtocol | None = None
) -> tuple[list[Anomaly], FixStats]:
    z_storage_folder = Z_STORAGE_PATH.lower()
    conn = get_db_connection()
    anomalies: list[Anomaly] = []
    fixes = FixStats()
    logger = ensure_logger(logger, __name__)
    logger.debug("🔍 Vérification des paires archive/synthèse via hash_source dans %s", z_storage_folder)
    try:
        with conn.cursor(DictCursor) as cursor:
            cursor.execute(
                "SELECT id, file_path, parent_id, status, category_id, subcategory_id, source_hash "
                "FROM obsidian_notes "
                "WHERE LOWER(file_path) LIKE %s",
                (f"%{z_storage_folder}/%",),
            )
            notes = cast(list[NoteRow], list(cursor.fetchall()))

            logger.debug("  → %d notes trouvées dans %s", len(notes), z_storage_folder)

        notes_by_hash: dict[str, list[NoteRow]] = defaultdict(list)
        for note in notes:
            h = note.get("hash_source")
            if h:
                h_str = str(h)
                notes_by_hash[h_str].append(note)
                logger.debug("    • Note %s avec hash_source %s", note["file_path"], h_str)

        for hval, group in notes_by_hash.items():
            logger.debug("  → Analyse du groupe avec hash_source %s (%d notes)", hval, len(group))
            if len(group) == 2:
                synth = next((n for n in group if n["status"] == "synthesis"), None)
                arch = next((n for n in group if n["status"] == "archive"), None)

                if not synth or not arch:
                    anomalies.append(
                        Anomaly(
                            severity=Severity.ERROR,
                            code="invalid_status_pair",
                            message="Les deux notes avec même hash_source n'ont pas les bons statuts",
                            note_ids=tuple(n["id"] for n in group),
                            paths=tuple(n["file_path"] for n in group),
                        )
                    )
                    continue

                # Vérif parent_id croisé
                if synth["parent_id"] != arch["id"] or arch["parent_id"] != synth["id"]:
                    logger.info("🔁 Correction des parent_id croisés pour couple %s", hval)
                    _fix_parent_links(conn, synth["id"], arch["id"])
                    fixes.parent_links_fixed += 1

                # Vérif catégorie
                if synth["category_id"] != arch["category_id"] or synth["subcategory_id"] != arch["subcategory_id"]:
                    logger.info("🔁 Correction des catégories pour archive %s", arch["file_path"])
                    _fix_categories(conn, arch["id"], synth["category_id"], synth["subcategory_id"])
                    fixes.categories_fixed += 1

            elif len(group) == 1:
                note = group[0]
                anomalies.append(
                    Anomaly(
                        severity=Severity.WARNING,
                        code="hash_source_orphan",
                        message="Note avec hash_source sans binôme",
                        note_ids=(note["id"],),
                        paths=(note["file_path"],),
                    )
                )

            else:
                anomalies.append(
                    Anomaly(
                        severity=Severity.ERROR,
                        code="hash_source_ambiguous",
                        message=f"Plus de 2 notes avec le même hash_source : {hval}",
                        note_ids=tuple(n["id"] for n in group),
                        paths=tuple(n["file_path"] for n in group),
                    )
                )
        if auto_fix:
            for a in anomalies:
                if not a.fixed:
                    for nid, path in zip(a.note_ids, a.paths, strict=False):
                        try:
                            handle_errored_file(
                                note_id=nid, filepath=path, exc=[f"[{a.code}] {a.message}"], logger=logger
                            )
                        except Exception as move_exc:
                            logger.warning("❌ Impossible de déplacer %s : %s", path, move_exc)
        return anomalies, fixes

    finally:
        conn.close()


def _fix_parent_links(conn: Connection, synth_id: int, arch_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE obsidian_notes SET parent_id = %s WHERE id = %s", (arch_id, synth_id))
        cur.execute("UPDATE obsidian_notes SET parent_id = %s WHERE id = %s", (synth_id, arch_id))
    conn.commit()


def _fix_categories(conn: Connection, note_id: int, category_id: int, subcategory_id: int | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE obsidian_notes SET category_id = %s, subcategory_id = %s WHERE id = %s",
            (category_id, subcategory_id, note_id),
        )
    conn.commit()
