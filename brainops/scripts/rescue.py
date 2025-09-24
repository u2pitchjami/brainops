#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from pymysql.cursors import DictCursor

from brainops.io.paths import to_abs
from brainops.sql.db_connection import get_db_connection
from brainops.utils.config import ERRORED_PATH
from brainops.utils.logger import LoggerProtocol, get_logger

# Tables:
# - obsidian_notes(id, file_path, status, category_id, subcategory_id, folder_id, parent_id)
# - obsidian_folders(id, path, folder_type, category_id, subcategory_id)

logger: LoggerProtocol = get_logger("rescue_from_error")


def _pick_folder(
    conn: Any, category_id: int | None, subcategory_id: int | None, want_archive: bool
) -> tuple[int, str] | None:
    where = "category_id <=> %s AND subcategory_id <=> %s"
    type_clause = "folder_type='archive'" if want_archive else "folder_type='storage'"
    sql = f"SELECT id, path FROM obsidian_folders WHERE {where} AND {type_clause} ORDER BY id DESC LIMIT 1"
    with conn.cursor() as cur:
        cur.execute(sql, (category_id, subcategory_id))
        row = cur.fetchone()
        if row:
            return int(row[0]), str(row[1])
    # fallback: chercher un chemin se terminant par /Archives
    if want_archive:
        sql2 = (
            f"SELECT id, path FROM obsidian_folders WHERE {where} AND path LIKE '%/Archives' ORDER BY id DESC LIMIT 1"
        )
        with conn.cursor() as cur:
            cur.execute(sql2, (category_id, subcategory_id))
            row = cur.fetchone()
            if row:
                return int(row[0]), str(row[1])
    return None


def main() -> int:
    conn = get_db_connection(logger=logger)
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                "SELECT id, file_path, status, category_id, subcategory_id FROM obsidian_notes WHERE file_path LIKE %s",
                (Path(ERRORED_PATH).as_posix().rstrip("/") + "/%",),
            )
            moved = list(cur.fetchall() or [])
        if not moved:
            logger.info("Rien à rescuer ; ERRORED_PATH vide côté DB.")
            return 0

        logger.warning("🔁 Restauration de %d notes depuis ERRORED_PATH ...", len(moved))
        for row in moved:
            note_id = int(row["id"])
            status = str(row["status"] or "").lower()
            fname = Path(str(row["file_path"])).name
            cat_id = row["category_id"]
            sub_id = row["subcategory_id"]

            want_archive = status == "archive"  # on remet les archives dans /Archives
            target = _pick_folder(conn, cat_id, sub_id, want_archive=want_archive)
            if not target:
                logger.error(
                    "Pas de dossier cible (cat=%s, sub=%s, archive=%s) pour note %s",
                    cat_id,
                    sub_id,
                    want_archive,
                    note_id,
                )
                continue

            folder_id, folder_path = target
            dest = Path(folder_path).joinpath(fname)
            dest_parent = dest.parent
            Path(to_abs(dest_parent)).mkdir(parents=True, exist_ok=True)

            src = Path(str(row["file_path"]))
            if not src.exists():
                logger.error("Fichier manquant en ERRORED_PATH: %s (note %s)", src, note_id)
                continue

            # éviter l'écrasement
            final = dest
            i = 1
            while Path(to_abs(final)).exists():
                final = dest.with_name(f"{dest.stem}__restored{i}{dest.suffix}")
                i += 1

            shutil.move(Path(to_abs(src)).as_posix(), Path(to_abs(final)).as_posix())
            logger.info("✅ %s -> %s", src, final)

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE obsidian_notes SET file_path=%s, folder_id=%s, parent_id=NULL WHERE id=%s",
                    (final.as_posix(), folder_id, note_id),
                )
            conn.commit()
        logger.warning("👌 Restauration terminée.")
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
