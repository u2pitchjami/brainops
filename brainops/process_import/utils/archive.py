"""
# process/divers.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_folders.folders import add_folder
from brainops.process_import.utils.paths import build_archive_path, ensure_folder_exists
from brainops.process_notes.add_notes_to_db import add_note_to_db
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def copy_to_archive(original_path: str | Path, note_id: int, *, logger: LoggerProtocol | None = None) -> Path:
    """
    Copie le fichier vers son sous-dossier 'Archives', crée la note archivée en base, et relie archive ↔ synthèse via
    parent_id.

    Retourne le Path de l'archive.
    """
    logger = ensure_logger(logger, __name__)
    src = Path(str(original_path)).resolve()
    if not src.exists():
        msg = f"Source introuvable : {src}"
        logger.error("[ARCHIVE] %s", msg)
        raise FileNotFoundError(msg)
        raise BrainOpsError("KO copie archive : aucun src_path", code=ErrCode.UNEXPECTED, ctx={"src": src})

    archive_path = build_archive_path(src)
    ensure_folder_exists(archive_path.parent, logger=logger)
    add_folder(Path(archive_path.parent).as_posix(), logger=logger)

    try:
        # Copie vers Archives
        archive_path.write_bytes(src.read_bytes())
        logger.info("[ARCHIVE] Copie → %s", archive_path)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ARCHIVE] Échec de la copie : %s", exc)
        raise BrainOpsError("KO copie archive", code=ErrCode.UNEXPECTED, ctx={"note_id": note_id}) from exc

    # Enregistrement DB + lien parent
    try:
        archive_note_id = add_note_to_db(Path(archive_path).as_posix(), logger=logger)
        update_obsidian_note(note_id, {"parent_id": archive_note_id}, logger=logger)
        update_obsidian_note(archive_note_id, {"parent_id": note_id}, logger=logger)
        logger.info("[ARCHIVE] Lien synthèse : %s → %s", note_id, archive_note_id)
    except Exception as exc:
        raise BrainOpsError("Copy Archive KO", code=ErrCode.DB, ctx={"note_id": note_id}) from exc

    return archive_path
