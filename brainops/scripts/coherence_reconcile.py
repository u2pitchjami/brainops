#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Réconcilie la cohérence entre Obsidian (fichiers) et la base MariaDB.

- Phase 1 : collecte des écarts (comme coherence_checker.py) et export CSV.
- Phase 2 (optionnelle, --apply) : applique les corrections :
    * notes manquantes -> brainops.process_notes.new_note.new_note
    * notes fantômes  -> brainops.sql.notes.db_notes.delete_note_by_path
    * dossiers manquants -> brainops.process_folders.folders.add_folder
    * dossiers fantômes  -> brainops.sql.folders.db_folders.delete_folder_from_db

Toutes les fonctions cibles reçoivent (filepath, logger=logger).
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Literal, Tuple, TypedDict

from brainops.process_folders.folders import add_folder

# Cibles fournies par toi
from brainops.process_notes.new_note import new_note
from brainops.sql.db_connection import get_db_connection
from brainops.sql.folders.db_folders import delete_folder_from_db
from brainops.sql.notes.db_notes import delete_note_by_path
from brainops.utils.config import LOG_FILE_PATH
from brainops.utils.logger import LoggerProtocol, get_logger

logger: LoggerProtocol = get_logger("coherence_reconcile")


# ------------------------------ Types & config -------------------------------

Scope = Literal["notes", "folders", "all"]


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
    file_path: str


# --------------------------------- Utils -------------------------------------


def _is_hidden_path(p: Path) -> bool:
    return any(part.startswith(".") for part in p.parts)


def _iter_physical_dirs(base: Path) -> Iterable[Path]:
    for p in base.rglob("*"):
        try:
            if p.is_dir() and not _is_hidden_path(p):
                yield p.resolve()
        except Exception:  # pragma: no cover
            continue


def _iter_md_files(base: Path) -> Iterable[Path]:
    for p in base.rglob("*.md"):
        if not _is_hidden_path(p):
            yield p.resolve()


def _export_to_csv(rows: list[tuple[str, str]], out_dir: Path, prefix: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = out_dir / f"{prefix}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    with filename.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["type", "detail"])
        writer.writerows(rows)
    logger.info("📄 Rapport CSV généré : %s", filename)
    return filename


# ------------------------------- Collecte ------------------------------------


@dataclass(frozen=True)
class DiffSets:
    folders_missing_in_db: list[str]
    folders_ghost_in_db: list[str]
    notes_missing_in_db: list[str]
    notes_missing_file: list[str]  # notes en DB dont le fichier a disparu


def collect_diffs(cfg: CheckConfig) -> DiffSets:
    logger.info("=== COLLECTE DES ÉCARTS ===")
    errors: list[tuple[str, str]] = []

    # --- Folders
    conn = get_db_connection(logger=logger)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, path, folder_type, category_id, subcategory_id FROM obsidian_folders"
    )
    db_folders: List[FolderRow] = cursor.fetchall()  # type: ignore[assignment]

    physical_dirs = {p for p in _iter_physical_dirs(cfg.base_path)}
    db_folder_paths = {Path(row["path"]).resolve() for row in db_folders}

    folders_missing_in_db = sorted(str(p) for p in (physical_dirs - db_folder_paths))
    folders_ghost_in_db = sorted(str(p) for p in (db_folder_paths - physical_dirs))

    for p in folders_missing_in_db:
        logger.info("📁 + Dossier à ajouter (DB) : %s", p)
        errors.append(("folder_missing_in_db", p))
    for p in folders_ghost_in_db:
        logger.info("📁 - Dossier à supprimer (DB) : %s", p)
        errors.append(("folder_ghost_in_db", p))

    # --- Notes
    cursor.execute("SELECT id, file_path FROM obsidian_notes")
    notes: List[NoteRow] = cursor.fetchall()  # type: ignore[assignment]

    notes_missing_file: list[str] = []
    for note in notes:
        fpath = Path(note["file_path"]).resolve()
        if not fpath.is_file():
            notes_missing_file.append(str(fpath))
            errors.append(("note_missing_file", str(fpath)))
            logger.info("📝 - Note fantôme en DB (fichier absent) : %s", fpath)

    all_md_files = {p for p in _iter_md_files(cfg.base_path)}
    db_note_paths = {Path(n["file_path"]).resolve() for n in notes}
    notes_missing_in_db = sorted(str(p) for p in (all_md_files - db_note_paths))
    for p in notes_missing_in_db:
        errors.append(("note_missing_in_db", p))
        logger.info("📝 + Note à ajouter (DB) : %s", p)

    cursor.close()
    conn.close()

    # Export d’un rapport “collecte”
    _export_to_csv(errors, cfg.out_dir, prefix="coherence_diffs")
    return DiffSets(
        folders_missing_in_db=folders_missing_in_db,
        folders_ghost_in_db=folders_ghost_in_db,
        notes_missing_in_db=notes_missing_in_db,
        notes_missing_file=notes_missing_file,
    )


# ------------------------------ Application ----------------------------------


@dataclass
class ApplyStats:
    added_folders: int = 0
    deleted_folders: int = 0
    added_notes: int = 0
    deleted_notes: int = 0
    errors: int = 0


def apply_diffs(diffs: DiffSets, scope: Scope, dry_run: bool) -> ApplyStats:
    """
    Applique les corrections en appelant les 4 fonctions fournies.
    dry_run=True -> log uniquement sans modifier.
    """
    stats = ApplyStats()

    # 1) Dossiers
    if scope in ("folders", "all"):
        for path in diffs.folders_missing_in_db:
            try:
                if dry_run:
                    logger.info("DRY-RUN 📁 add_folder(%s)", path)
                else:
                    add_folder(folder_path=path, logger=logger)  # type: ignore[arg-type]
                stats.added_folders += 1
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Erreur add_folder(%s): %s", path, exc)
                stats.errors += 1

        for path in diffs.folders_ghost_in_db:
            try:
                if dry_run:
                    logger.info("DRY-RUN 📁 delete_folder_from_db(%s)", path)
                else:
                    delete_folder_from_db(file_path=path, logger=logger)  # type: ignore[arg-type]
                stats.deleted_folders += 1
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Erreur delete_folder_from_db(%s): %s", path, exc)
                stats.errors += 1

    # 2) Notes
    if scope in ("notes", "all"):
        # a) Ajouter les notes physiques absentes en DB
        for path in diffs.notes_missing_in_db:
            try:
                if dry_run:
                    logger.info("DRY-RUN 📝 new_note(%s)", path)
                else:
                    new_note(file_path=path, logger=logger)  # type: ignore[arg-type]
                stats.added_notes += 1
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Erreur new_note(%s): %s", path, exc)
                stats.errors += 1

        # b) Supprimer de la DB les notes dont le fichier a disparu
        for path in diffs.notes_missing_file:
            try:
                if dry_run:
                    logger.info("DRY-RUN 📝 delete_note_by_path(%s)", path)
                else:
                    delete_note_by_path(file_path=path, logger=logger)  # type: ignore[arg-type]
                stats.deleted_notes += 1
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Erreur delete_note_by_path(%s): %s", path, exc)
                stats.errors += 1

    return stats


# --------------------------------- Main --------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit & réconciliation Obsidian <-> MariaDB"
    )
    parser.add_argument(
        "--base-path",
        default=None,
        help="Racine du vault Obsidian (sinon config BASE_PATH)",
    )
    parser.add_argument(
        "--out-dir", default=None, help="Répertoire des rapports (sinon config LOG_DIR)"
    )
    parser.add_argument(
        "--scope",
        default="all",
        choices=["all", "notes", "folders"],
        help="Cible de la réconciliation",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Appliquer les corrections (sinon dry-run)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_path = Path(args.base_path or get_str("BASE_PATH", ".")).resolve()
    out_dir = Path(args.out_dir or LOG_FILE_PATH).resolve()
    cfg = CheckConfig(base_path=base_path, out_dir=out_dir)

    logger.info(
        "=== DÉMARRAGE RÉCONCILIATION (scope=%s, apply=%s) ===", args.scope, args.apply
    )
    try:
        diffs = collect_diffs(cfg)
        stats = apply_diffs(diffs, scope=args.scope, dry_run=(not args.apply))
        # Export d’un résumé CSV “actions”
        summary_rows = [
            ("added_folders", str(stats.added_folders)),
            ("deleted_folders", str(stats.deleted_folders)),
            ("added_notes", str(stats.added_notes)),
            ("deleted_notes", str(stats.deleted_notes)),
            ("errors", str(stats.errors)),
            ("scope", str(args.scope)),
            ("apply", str(args.apply)),
        ]
        _export_to_csv(summary_rows, cfg.out_dir, prefix="coherence_actions_summary")
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
