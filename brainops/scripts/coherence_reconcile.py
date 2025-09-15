#!/usr/bin/env python3
"""
coherence_reconcile.py.

Audit & réconciliation Obsidian (fichiers) ↔ MariaDB + contrôle des paires
synthesis/archive.

Phases
------
1) Collecte des écarts (fichiers/dossiers ↔ DB) + export CSV.
2) (optionnelle, --apply) Application des corrections (add/delete dossiers & notes).
3) Contrôle des couples synthesis/archive (bloquants + warnings).
4) (optionnelle, --fix-non-blocking) Auto-fix des incohérences non bloquantes :
   - réciprocité parent_id ↔ id
   - category_id/subcategory_id depuis le chemin (get_category_context_from_folder)

Sécurité
--------
- **Important** : le dispatch vers `handle_errored_file` est **désactivé** tant que
  `--apply` n'est pas fourni (dry-run global). Utiliser `--no-dispatch` pour forcer
  le non-dispatch même en mode apply.

Compat
------
- Détection dynamique des noms de colonnes via INFORMATION_SCHEMA (id vs note_id,
  file_path vs filepath/path, folders.path vs folder_path).

Python >= 3.11, mypy-friendly, pylint-friendly.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Literal, TypedDict

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_folders.folders import add_folder
from brainops.process_import.utils.move_error_file import handle_errored_file
from brainops.process_notes.new_note import new_note
from brainops.sql.db_connection import get_db_connection
from brainops.sql.folders.db_folders import delete_folder_from_db
from brainops.sql.get_linked.db_get_linked_folders_utils import (
    get_category_context_from_folder,
)
from brainops.sql.notes.db_delete_note import delete_note_by_path
from brainops.utils.config import BASE_PATH, LOG_FILE_PATH
from brainops.utils.logger import LoggerProtocol, get_logger

logger: LoggerProtocol = get_logger("coherence_reconcile")

# ======================= DB schema helpers (robustness) ======================


def _detect_col(conn: Any, table: str, candidates: list[str]) -> str:
    """
    Retourne la première colonne existante parmi `candidates` pour `table`.

    Lève ValueError si aucune ne correspond.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE()")
        row = cur.fetchone()
        db = str(row[0]) if row else ""
        cur.execute(
            """
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
            """,
            (db, table),
        )
        names = cur.fetchall() or []
        cols = {str(r[0]) for r in names}
    for c in candidates:
        if c in cols:
            return c
    raise ValueError(f"None of {candidates} exists on {table}")


def _get_notes_cols(conn: Any) -> tuple[str, str]:
    """
    Retourne (id_col, file_path_col) pour obsidian_notes, compatible legacy.
    """
    id_col = _detect_col(conn, "obsidian_notes", ["id", "note_id"])  # pragma: no cover
    file_col = _detect_col(conn, "obsidian_notes", ["file_path", "filepath", "path"])  # pragma: no cover
    return id_col, file_col


def _get_folders_path_col(conn: Any) -> str:
    """
    Retourne le nom de la colonne du chemin pour obsidian_folders.
    """
    return _detect_col(conn, "obsidian_folders", ["path", "folder_path"])  # pragma: no cover


# ============================== Types & config ===============================

Scope = Literal["notes", "folders", "all"]
Severity = Literal["blocking", "warning"]


@dataclass(frozen=True)
class CheckConfig:
    base_path: Path
    out_dir: Path


class FolderRow(TypedDict):
    id: int
    path: str
    folder_type: str | None
    category_id: int | None
    subcategory_id: int | None


class NoteRow(TypedDict):
    id: int
    parent_id: int | None
    file_path: str
    category_id: int | None
    subcategory_id: int | None
    status: str


@dataclass
class ApplyStats:
    added_folders: int = 0
    deleted_folders: int = 0
    added_notes: int = 0
    deleted_notes: int = 0
    errors: int = 0


@dataclass(frozen=True)
class DiffSets:
    folders_missing_in_db: list[str]
    folders_ghost_in_db: list[str]
    notes_missing_in_db: list[str]
    notes_missing_file: list[str]


@dataclass
class Anomaly:
    severity: Severity
    code: str
    message: str
    note_ids: tuple[int, ...]
    paths: tuple[str, ...]


@dataclass
class FixStats:
    parent_links_fixed: int = 0
    categories_fixed: int = 0


# ================================ Utils FS ===================================


def _is_hidden_path(p: Path) -> bool:
    return any(part.startswith(".") for part in p.parts)


def _iter_physical_dirs(base: Path) -> Iterable[Path]:
    for p in base.rglob("*"):
        try:
            if p.is_dir() and not _is_hidden_path(p):
                yield p.resolve()
        except Exception:  # pylint: disable=broad-except  # pragma: no cover
            continue


def _iter_md_files(base: Path) -> Iterable[Path]:
    for p in base.rglob("*.md"):
        if not _is_hidden_path(p):
            yield p.resolve()


# ================================ Utils CSV ==================================


def _export_to_csv(rows: list[tuple[str, str]], out_dir: Path, prefix: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = out_dir / f"{prefix}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    with filename.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["type", "detail"])
        writer.writerows(rows)
    logger.info("📄 Rapport CSV généré : %s", filename)
    return filename


def _export_anomalies_csv(anomalies: list[Anomaly], out_dir: Path, prefix: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = out_dir / f"{prefix}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    with filename.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["severity", "code", "message", "note_ids", "paths"])
        for a in anomalies:
            writer.writerow(
                [
                    a.severity,
                    a.code,
                    a.message,
                    ";".join(map(str, a.note_ids)),
                    ";".join(a.paths),
                ]
            )
    logger.info("📄 Rapport anomalies généré : %s", filename)
    return filename


def _export_fixes_csv(stats: FixStats, out_dir: Path, prefix: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = out_dir / f"{prefix}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    with filename.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["parent_links_fixed", "categories_fixed"])
        writer.writerow([stats.parent_links_fixed, stats.categories_fixed])
    logger.info("📄 Rapport corrections généré : %s", filename)
    return filename


# ============================== Utils métier =================================


def in_z_storage(path: str) -> bool:
    """
    Détection robuste de Z_storage (supporte chemins absolus).
    """
    p = Path(str(path)).as_posix()
    return "/Z_Storage/" in p


def extract_branch(path: str) -> tuple[str | None, str | None]:
    """
    Retourne (category, subcategory) si le chemin est sous Z_storage, sinon (None, None).
    """
    p = Path(str(path)).as_posix()
    if "/Z_Storage/" not in p:
        return (None, None)
    rel = p.split("/Z_Storage/", 1)[1]
    parts = [x for x in rel.split("/") if x]
    if len(parts) < 3:
        return (None, None)
    return (parts[0], parts[1])


# ================================= Collecte ==================================


def collect_diffs(cfg: CheckConfig) -> DiffSets:
    logger.info("=== COLLECTE DES ÉCARTS ===")
    errors_rows: list[tuple[str, str]] = []

    conn = get_db_connection(logger=logger)
    try:
        # --- Folders
        folders_path_col = _get_folders_path_col(conn)
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                f"SELECT id, {folders_path_col} AS path, folder_type, category_id, subcategory_id FROM obsidian_folders"
            )
            db_folders: list[FolderRow] = cursor.fetchall()

        physical_dirs: set[Path] = set(_iter_physical_dirs(cfg.base_path))
        db_folder_paths = {Path(row["path"]).resolve() for row in db_folders}

        folders_missing_in_db = sorted(str(p) for p in (physical_dirs - db_folder_paths))
        folders_ghost_in_db = sorted(str(p) for p in (db_folder_paths - physical_dirs))

        for p in folders_missing_in_db:
            logger.info("📁 + Dossier à ajouter (DB) : %s", p)
            errors_rows.append(("folder_missing_in_db", p))
        for p in folders_ghost_in_db:
            logger.info("📁 - Dossier à supprimer (DB) : %s", p)
            errors_rows.append(("folder_ghost_in_db", p))

        # --- Notes
        notes_id_col, notes_file_col = _get_notes_cols(conn)
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(f"SELECT {notes_id_col} AS id, {notes_file_col} AS file_path FROM obsidian_notes")
            notes_rows: list[dict[str, Any]] = cursor.fetchall() or []

        notes_missing_file: list[str] = []
        for note in notes_rows:
            fpath = Path(str(note["file_path"]))
            try:
                fpath_res = fpath.resolve()
                if not fpath_res.is_file():
                    notes_missing_file.append(str(fpath_res))
                    errors_rows.append(("note_missing_file", str(fpath_res)))
                    logger.info("📝 - Note fantôme en DB (fichier absent) : %s", fpath_res)
            except Exception:  # pylint: disable=broad-except  # pragma: no cover
                notes_missing_file.append(str(fpath))
                errors_rows.append(("note_missing_file", str(fpath)))
                logger.info("📝 - Note fantôme en DB (chemin non résolu) : %s", fpath)

        all_md_files: set[Path] = set(_iter_md_files(cfg.base_path))
        db_note_paths = {Path(str(n["file_path"])) for n in notes_rows}
        db_note_paths_resolved = {p.resolve() for p in db_note_paths if p.exists()}
        notes_missing_in_db = sorted(str(p) for p in (all_md_files - db_note_paths_resolved))
        for p in notes_missing_in_db:
            errors_rows.append(("note_missing_in_db", p))
            logger.info("📝 + Note à ajouter (DB) : %s", p)

        _export_to_csv(errors_rows, cfg.out_dir, prefix="coherence_diffs")

        return DiffSets(
            folders_missing_in_db=folders_missing_in_db,
            folders_ghost_in_db=folders_ghost_in_db,
            notes_missing_in_db=notes_missing_in_db,
            notes_missing_file=notes_missing_file,
        )
    finally:
        try:
            conn.close()
        except Exception:  # pylint: disable=broad-except  # pragma: no cover
            logger.warning("DB connection close failed", exc_info=True)


# ================== Contrôle couples synthesis/archive ========================


def _fetch_pairing_dataset() -> list[NoteRow]:
    conn = get_db_connection(logger=logger)
    try:
        notes_id_col, notes_file_col = _get_notes_cols(conn)
        # Backticks pour éviter tout conflit de nom/réservé
        idc = f"`{notes_id_col}`"
        fpc = f"`{notes_file_col}`"
        table_notes = "`obsidian_notes`"

        sql_main = (
            f"SELECT {idc} AS id, parent_id, {fpc} AS file_path, "
            f"category_id, subcategory_id, status "
            f"FROM {table_notes} "
            f"WHERE status IN ('synthesis','archive')"
        )
        rows: list[NoteRow] = []

        try:
            with conn.cursor(dictionary=True) as cur:
                logger.info("PAIR SELECT main: %s", sql_main)
                cur.execute(sql_main)
                rows = cur.fetchall()
        except Exception:  # pylint: disable=broad-except
            logger.exception("SQL failed: %s", sql_main)
            raise

        # Précharger aussi les enfants pour détecter des liaisons inattendues
        ids = tuple(r["id"] for r in rows)
        if ids:
            fmt = ",".join(["%s"] * len(ids))
            sql_children = (
                f"SELECT {idc} AS id, parent_id, {fpc} AS file_path, "
                f"category_id, subcategory_id, status "
                f"FROM {table_notes} WHERE parent_id IN ({fmt})"
            )
            try:
                with conn.cursor(dictionary=True) as cur:
                    logger.info("PAIR SELECT children: %s | ids=%s", sql_children, ids)
                    cur.execute(sql_children, ids)
                    extra: list[NoteRow] = cur.fetchall()
                    known = {r["id"] for r in rows}
                    rows.extend([r for r in extra if r["id"] not in known])
            except Exception:  # pylint: disable=broad-except
                logger.exception("SQL failed: %s", sql_children)
                raise

        return rows
    finally:
        try:
            conn.close()
        except Exception:  # pylint: disable=broad-except  # pragma: no cover
            logger.warning("DB connection close failed (pairs)", exc_info=True)


def _index(
    rows: list[NoteRow],
) -> tuple[dict[int, NoteRow], dict[int | None, list[NoteRow]], dict[str, list[NoteRow]]]:
    by_id: dict[int, NoteRow] = {}
    by_parent: dict[int | None, list[NoteRow]] = {}
    by_status: dict[str, list[NoteRow]] = {}
    for r in rows:
        rid = int(r["id"])  # ensure int
        by_id[rid] = r
        by_parent.setdefault(r.get("parent_id"), []).append(r)
        by_status.setdefault(str(r.get("status", "")).lower(), []).append(r)
    return by_id, by_parent, by_status


def _add_anomaly(
    out: list[Anomaly], severity: Severity, code: str, message: str, note_ids: Iterable[int], paths: Iterable[str]
) -> None:
    out.append(
        Anomaly(
            severity=severity,
            code=code,
            message=message,
            note_ids=tuple(int(i) for i in note_ids),
            paths=tuple(paths),
        )
    )


def _build_pairs(
    by_id: dict[int, NoteRow], by_parent: dict[int | None, list[NoteRow]], by_status: dict[str, list[NoteRow]]
) -> list[tuple[NoteRow, NoteRow]]:
    pairs: list[tuple[NoteRow, NoteRow]] = []
    synths = by_status.get("synthesis", [])
    for s in synths:
        sid = int(s["id"])  # synthesis id
        children = [c for c in (by_parent.get(sid, []) or []) if str(c["status"]).lower() == "archive"]
        counterpart: NoteRow | None = None
        if len(children) == 1:
            counterpart = children[0]
        pid2 = s.get("parent_id")
        if pid2 is not None:
            cand = by_id.get(pid2)
            if cand and str(cand["status"]).lower() == "archive":
                counterpart = cand
        if counterpart is not None:
            pairs.append((s, counterpart))
    return pairs


def check_synthesis_archive_pairs(dispatch_blocking: bool) -> list[Anomaly]:
    rows = _fetch_pairing_dataset()
    by_id, by_parent, by_status = _index(rows)

    synths = by_status.get("synthesis", [])
    archives = by_status.get("archive", [])

    arch_ids = {int(a["id"]) for a in archives}
    synth_ids = {int(s["id"]) for s in synths}

    anomalies: list[Anomaly] = []

    # Localisation (bloquant si hors Z_storage)
    for r in synths + archives:
        path = str(r["file_path"])
        if not in_z_storage(path):
            _add_anomaly(
                anomalies,
                "blocking",
                "OUTSIDE_Z_STORAGE",
                f"{r['status']} outside Z_storage: {path}",
                [int(r["id"])],
                [path],
            )

    # Contrôles par synthèse
    for s in synths:
        sid = int(s["id"])  # synthesis id
        spath = str(s["file_path"])
        children = by_parent.get(sid, []) or []
        arch_children = [c for c in children if str(c.get("status", "")).lower() == "archive"]
        other_children = [c for c in children if str(c.get("status", "")).lower() != "archive"]

        pid_la = s.get("parent_id")
        linked_archive = by_id.get(pid_la) if pid_la is not None else None
        if linked_archive and str(linked_archive.get("status", "")).lower() != "archive":
            linked_archive = None

        if not arch_children and linked_archive is None:
            _add_anomaly(anomalies, "blocking", "MISSING_ARCHIVE", "Synthesis without archive", [sid], [spath])
        if len(arch_children) > 1:
            _add_anomaly(
                anomalies,
                "blocking",
                "MULTIPLE_ARCHIVES",
                f"Synthesis has {len(arch_children)} archives",
                [sid] + [int(a["id"]) for a in arch_children],
                [spath] + [str(a["file_path"]) for a in arch_children],
            )
        if other_children:
            _add_anomaly(
                anomalies,
                "blocking",
                "UNEXPECTED_CHILD",
                f"Synthesis has non-archive child(ren): {[c['status'] for c in other_children]}",
                [sid] + [int(c["id"]) for c in other_children],
                [spath] + [str(c["file_path"]) for c in other_children],
            )

        # Réciprocité
        pid = s.get("parent_id")
        if pid is not None and int(pid) not in arch_ids:
            if int(pid) not in by_id:
                _add_anomaly(
                    anomalies, "blocking", "ORPHAN_PARENT", f"Synthesis parent_id={pid} not found", [sid], [spath]
                )
            else:
                _add_anomaly(
                    anomalies,
                    "warning",
                    "NON_RECIPROCAL",
                    f"Synthesis parent_id={pid} points to non-archive",
                    [sid],
                    [spath],
                )

    # Contrôles par archive
    for a in archives:
        aid = int(a["id"])  # archive id
        apath = str(a["file_path"])
        children = by_parent.get(aid, []) or []
        synth_children = [c for c in children if str(c.get("status", "")).lower() == "synthesis"]
        other_children = [c for c in children if str(c.get("status", "")).lower() != "synthesis"]

        pid_ls = a.get("parent_id")
        linked_synth = by_id.get(pid_ls) if pid_ls is not None else None
        if linked_synth and str(linked_synth.get("status", "")).lower() != "synthesis":
            linked_synth = None

        if not synth_children and linked_synth is None:
            _add_anomaly(anomalies, "blocking", "MISSING_SYNTHESIS", "Archive without synthesis", [aid], [apath])
        if len(synth_children) > 1:
            _add_anomaly(
                anomalies,
                "blocking",
                "MULTIPLE_SYNTHESES",
                f"Archive has {len(synth_children)} syntheses",
                [aid] + [int(s["id"]) for s in synth_children],
                [apath] + [str(s["file_path"]) for s in synth_children],
            )
        if other_children:
            _add_anomaly(
                anomalies,
                "blocking",
                "UNEXPECTED_CHILD",
                f"Archive has non-synthesis child(ren): {[c['status'] for c in other_children]}",
                [aid] + [int(c["id"]) for c in other_children],
                [apath] + [str(c["file_path"]) for c in other_children],
            )

        pid = a.get("parent_id")
        if pid is not None and int(pid) not in synth_ids:
            if int(pid) not in by_id:
                _add_anomaly(
                    anomalies, "blocking", "ORPHAN_PARENT", f"Archive parent_id={pid} not found", [aid], [apath]
                )
            else:
                _add_anomaly(
                    anomalies,
                    "warning",
                    "NON_RECIPROCAL",
                    f"Archive parent_id={pid} points to non-synthesis",
                    [aid],
                    [apath],
                )

    # Comparaisons de paires (branche + catégories)
    for s in synths:
        sid = int(s["id"])  # synthesis id
        spath = str(s["file_path"])
        # Choisir l'archive correspondante (enfant unique sinon parent)
        children = [c for c in (by_parent.get(sid, []) or []) if str(c["status"]).lower() == "archive"]
        counterpart: NoteRow | None = None
        if len(children) == 1:
            counterpart = children[0]
        pid2 = s.get("parent_id")
        if pid2 is not None:
            cand = by_id.get(pid2)
            if cand and str(cand["status"]).lower() == "archive":
                counterpart = cand
        if counterpart is None:
            continue
        apath = str(counterpart["file_path"])

        s_branch = extract_branch(spath)
        a_branch = extract_branch(apath)
        if in_z_storage(spath) and in_z_storage(apath) and s_branch != a_branch:
            _add_anomaly(
                anomalies,
                "blocking",
                "DIFFERENT_BRANCH",
                "Synthesis and archive are in different Z_storage branches",
                [sid, int(counterpart["id"])],
                [spath, apath],
            )

        if s.get("category_id") != counterpart.get("category_id") or s.get("subcategory_id") != counterpart.get(
            "subcategory_id"
        ):
            _add_anomaly(
                anomalies,
                "warning",
                "CATEGORY_MISMATCH",
                "category_id/subcategory_id differ between synthesis and archive",
                [sid, int(counterpart["id"])],
                [spath, apath],
            )

        if "/Archives/" not in apath:
            _add_anomaly(
                anomalies,
                "warning",
                "ARCHIVES_FOLDER_EXPECTED",
                "Archive not under an 'Archives' folder",
                [int(counterpart["id"])],
                [apath],
            )

    # Dispatch des bloquants vers handle_errored_file (gating géré par main)
    if dispatch_blocking:
        for anom in anomalies:
            if anom.severity != "blocking":
                continue
            ids = list(anom.note_ids)
            paths = list(anom.paths)
            n = max(len(ids), len(paths))
            for i in range(n):
                note_id = ids[i] if i < len(ids) else (ids[0] if ids else -1)
                path = paths[i] if i < len(paths) else (paths[0] if paths else "")
                if note_id == -1 or not path:
                    logger.warning("Skip dispatch (missing id/path) for anomaly %s", anom.code)
                    err = BrainOpsError(
                        f"Coherence blocking: {anom.code}",
                        code=ErrCode.METADATA,
                        ctx={"anomaly": anom.code, "note_id": note_id},
                    )
                try:
                    handle_errored_file(note_id=note_id, filepath=path, exc=err, logger=logger)
                except Exception as exc:  # pylint: disable=broad-except
                    logger.exception(
                        "Erreur handle_errored_file(id=%s,path=%s,code=%s): %s",
                        note_id,
                        path,
                        a,
                        exc,
                    )

    return anomalies


# ======================== Auto-fix non bloquants ==============================


def _has_blocking_for_pair(anomalies: list[Anomaly], ids: set[int]) -> bool:
    return any(a.severity == "blocking" and any(i in ids for i in a.note_ids) for a in anomalies)


def auto_fix_non_blocking(anomalies: list[Anomaly], apply: bool) -> FixStats:
    """
    Corrige automatiquement les cas non-bloquants si *aucun bloquant* n'affecte la paire.

    - Répare la réciprocité parent_id <-> id.
    - Met à jour category_id/subcategory_id depuis le path.
    - Compatible schémas legacy (id vs note_id, file_path vs path)
    """
    rows = _fetch_pairing_dataset()
    by_id, by_parent, by_status = _index(rows)
    pairs = _build_pairs(by_id, by_parent, by_status)

    stats = FixStats()

    conn = get_db_connection(logger=logger)
    try:
        for s, a in pairs:
            s_id = int(s["id"])  # synthesis
            a_id = int(a["id"])  # archive
            pair_ids = {s_id, a_id}
            if _has_blocking_for_pair(anomalies, pair_ids):
                continue

            # 1) Réparer la réciprocité parent_id
            need_fix_parent = (s.get("parent_id") != a_id) or (a.get("parent_id") != s_id)
            if need_fix_parent:
                if apply:
                    notes_id_col, _notes_file_col = _get_notes_cols(conn)
                    with conn.cursor() as cur:
                        cur.execute(f"UPDATE obsidian_notes SET parent_id=%s WHERE {notes_id_col}=%s", (a_id, s_id))
                        cur.execute(f"UPDATE obsidian_notes SET parent_id=%s WHERE {notes_id_col}=%s", (s_id, a_id))
                    conn.commit()
                logger.info(
                    "%s Réparation parent_id: synthesis %s <-> archive %s", "APPLY" if apply else "DRY-RUN", s_id, a_id
                )
                stats.parent_links_fixed += 1

            # 2) Réparer catégories/subcat depuis le path
            s_dir = Path(str(s["file_path"]))
            a_dir = Path(str(a["file_path"]))
            cat_s, sub_s, _cname, _scname = get_category_context_from_folder(
                folder_path=s_dir.parent.as_posix(), logger=logger
            )
            cat_a, sub_a, _cname2, _scname2 = get_category_context_from_folder(
                folder_path=a_dir.parent.as_posix(), logger=logger
            )

            upd_s = (s.get("category_id") != cat_s) or (s.get("subcategory_id") != sub_s)
            upd_a = (a.get("category_id") != cat_a) or (a.get("subcategory_id") != sub_a)
            if upd_s or upd_a:
                if apply:
                    with conn.cursor() as cur:
                        if upd_s:
                            cur.execute(
                                "UPDATE obsidian_notes SET category_id=%s, subcategory_id=%s WHERE id=%s",
                                (cat_s, sub_s, s_id),
                            )
                        if upd_a:
                            cur.execute(
                                "UPDATE obsidian_notes SET category_id=%s, subcategory_id=%s WHERE id=%s",
                                (cat_a, sub_a, a_id),
                            )
                    conn.commit()
                logger.info(
                    "%s Categories fix: synthesis(id=%s)->(%s,%s), archive(id=%s)->(%s,%s)",
                    "APPLY" if apply else "DRY-RUN",
                    s_id,
                    cat_s,
                    sub_s,
                    a_id,
                    cat_a,
                    sub_a,
                )
                stats.categories_fixed += 1

        return stats
    finally:
        try:
            conn.close()
        except Exception:  # pylint: disable=broad-except  # pragma: no cover
            logger.warning("DB connection close failed on fixes", exc_info=True)


# ============================ Application diffs ===============================


def apply_diffs(diffs: DiffSets, scope: Scope, dry_run: bool) -> ApplyStats:
    stats = ApplyStats()

    # 1) Dossiers
    if scope in ("folders", "all"):
        for path in diffs.folders_missing_in_db:
            try:
                if dry_run:
                    logger.info("DRY-RUN 📁 add_folder(%s)", path)
                else:
                    add_folder(folder_path=path, logger=logger)
                stats.added_folders += 1
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Erreur add_folder(%s): %s", path, exc)
                stats.errors += 1

        for path in diffs.folders_ghost_in_db:
            try:
                if dry_run:
                    logger.info("DRY-RUN 📁 delete_folder_from_db(%s)", path)
                else:
                    delete_folder_from_db(folder_path=path, logger=logger)
                stats.deleted_folders += 1
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Erreur delete_folder_from_db(%s): %s", path, exc)
                stats.errors += 1

    # 2) Notes
    if scope in ("notes", "all"):
        for path in diffs.notes_missing_in_db:
            try:
                if dry_run:
                    logger.info("DRY-RUN 📝 new_note(%s)", path)
                else:
                    new_note(file_path=path, logger=logger)
                stats.added_notes += 1
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Erreur new_note(%s): %s", path, exc)
                stats.errors += 1

        for path in diffs.notes_missing_file:
            try:
                if dry_run:
                    logger.info("DRY-RUN 📝 delete_note_by_path(%s)", path)
                else:
                    delete_note_by_path(file_path=path, logger=logger)
                stats.deleted_notes += 1
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Erreur delete_note_by_path(%s): %s", path, exc)
                stats.errors += 1

    return stats


# ================================== Main =====================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit & réconciliation Obsidian <-> MariaDB")
    parser.add_argument("--base-path", default=None, help="Racine du vault Obsidian (sinon config BASE_PATH)")
    parser.add_argument("--out-dir", default=None, help="Répertoire des rapports (sinon config LOG_DIR)")
    parser.add_argument(
        "--scope", default="all", choices=["all", "notes", "folders"], help="Cible de la réconciliation"
    )
    parser.add_argument("--apply", action="store_true", help="Appliquer les corrections (sinon dry-run)")
    # Contrôle paires synthesis/archive
    parser.add_argument("--check-pairs", action="store_true", help="Activer le contrôle synthesis/archive")
    parser.add_argument(
        "--no-dispatch", action="store_true", help="Ne pas dispatcher les anomalies bloquantes vers handle_errored_file"
    )
    # Auto-fix non bloquants
    parser.add_argument(
        "--fix-non-blocking",
        action="store_true",
        help="Auto-corriger réciprocité et catégories si pas d'autres erreurs",
    )
    # Debug provenance
    parser.add_argument("--debug-provenance", action="store_true", help="Log du script/venv/DB courante")
    return parser.parse_args()


def _log_provenance() -> None:
    try:
        import os
        import time

        logger.info("RUN pid=%s", os.getpid())
        logger.info("SCRIPT %s (mtime=%s)", Path(__file__).resolve(), time.ctime(Path(__file__).stat().st_mtime))
        logger.info("PYTHON %s  VENV=%s", sys.executable, os.environ.get("VIRTUAL_ENV"))
        conn = get_db_connection(logger=logger)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT DATABASE()")
                row = cur.fetchone()
                current_db = str(row[0]) if row else ""
            notes_id_col, notes_file_col = _get_notes_cols(conn)
            folders_path_col = _get_folders_path_col(conn)
            logger.info(
                "DB=%s | notes.id_col=%s notes.file_col=%s | folders.path_col=%s",
                current_db,
                notes_id_col,
                notes_file_col,
                folders_path_col,
            )
        finally:
            try:
                conn.close()
            except Exception:  # pylint: disable=broad-except
                pass
    except Exception:  # pylint: disable=broad-except
        logger.exception("Provenance logging failed")


def main() -> int:
    args = parse_args()
    base_path = Path(args.base_path or BASE_PATH).resolve()
    out_dir = Path(args.out_dir or LOG_FILE_PATH).resolve()
    cfg = CheckConfig(base_path=base_path, out_dir=out_dir)

    if args.debug_provenance:
        _log_provenance()

    logger.info("=== DÉMARRAGE RÉCONCILIATION (scope=%s, apply=%s) ===", args.scope, args.apply)
    try:
        diffs = collect_diffs(cfg)
        stats = apply_diffs(diffs, scope=args.scope, dry_run=(not args.apply))

        # Contrôle paires + export
        anomalies: list[Anomaly] = []
        if args.check_pairs or args.fix_non_blocking:
            dispatch = bool(args.apply and not args.no_dispatch)  # ← garde-fou DRY-RUN global
            logger.info(
                "MODE: %s | check_pairs=%s | dispatch=%s",
                "APPLY" if args.apply else "DRY-RUN",
                args.check_pairs,
                dispatch,
            )
            anomalies = check_synthesis_archive_pairs(dispatch_blocking=dispatch)
            nb_blocking = sum(1 for a in anomalies if a.severity == "blocking")
            nb_warning = sum(1 for a in anomalies if a.severity == "warning")
            logger.info("Pairs check: %s blocking / %s warnings", nb_blocking, nb_warning)
            _export_anomalies_csv(anomalies, cfg.out_dir, prefix="coherence_pairs_anomalies")

        # Auto-fix non bloquants
        if args.fix_non_blocking:
            logger.info("=== AUTO-FIX NON BLOQUANTS (réciprocité & catégories) ===")
            fix_stats = auto_fix_non_blocking(anomalies, apply=args.apply)
            _export_fixes_csv(fix_stats, cfg.out_dir, prefix="coherence_pairs_fixes")
            logger.info(
                "Auto-fix terminé: parent_links_fixed=%s, categories_fixed=%s (apply=%s)",
                fix_stats.parent_links_fixed,
                fix_stats.categories_fixed,
                args.apply,
            )

        # Codes de retour : prioriser les anomalies paires si check demandé
        if anomalies and any(a.severity == "blocking" for a in anomalies):
            logger.error("Terminé avec anomalies bloquantes (pairs)")
            return 2
        if anomalies and any(a.severity == "warning" for a in anomalies):
            logger.warning("Terminé avec avertissements (pairs)")
            return 1

        logger.info(
            "✅ Terminé. Folders +%d/-%d, Notes +%d/-%d, Errors=%d (apply=%s)",
            stats.added_folders,
            stats.deleted_folders,
            stats.added_notes,
            stats.deleted_notes,
            stats.errors,
            args.apply,
        )
        return 0
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("❌ Échec de la réconciliation : %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
