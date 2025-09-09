"""# process/divers.py"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from brainops.process_folders.folders import add_folder
from brainops.process_import.utils.paths import build_archive_path, ensure_folder_exists
from brainops.process_notes.add_notes_to_db import add_note_to_db
from brainops.process_notes.new_note import new_note
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def link_synthesis_and_archive(
    original_path: Path, synthese_id: int, *, logger: Optional[LoggerProtocol] = None
) -> Optional[int]:
    """
    Crée une note 'archive' depuis original_path et associe parent_id dans les deux sens.
    Retourne l'ID de l'archive créée (ou None).
    """
    logger = ensure_logger(logger, __name__)
    try:
        archive_id = new_note(str(original_path), logger=logger)
        if not archive_id:
            logger.error("[LINK] Impossible de créer l'archive pour %s", original_path)
            return None

        # parent_id croisé
        update_obsidian_note(archive_id, {"parent_id": synthese_id}, logger=logger)
        update_obsidian_note(synthese_id, {"parent_id": archive_id}, logger=logger)

        logger.info(
            "[LINK] Liens posés : archive %s ⇄ synthèse %s", archive_id, synthese_id
        )
        return archive_id
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[LINK] Erreur lors de la liaison archive/synthèse : %s", exc)
        return None


@with_child_logger
def copy_to_archive(
    original_path: str | Path, note_id: int, *, logger: Optional[LoggerProtocol] = None
) -> Path:
    """
    Copie le fichier vers son sous-dossier 'Archives', crée la note archivée en base,
    et relie archive ↔ synthèse via parent_id. Retourne le Path de l'archive.
    """
    logger = ensure_logger(logger, __name__)
    src = Path(str(original_path)).resolve()
    if not src.exists():
        msg = f"Source introuvable : {src}"
        logger.error("[ARCHIVE] %s", msg)
        raise FileNotFoundError(msg)

    archive_path = build_archive_path(src)
    ensure_folder_exists(archive_path.parent, logger=logger)
    add_folder(
        Path(archive_path.parent).as_posix(), folder_type_hint="archive", logger=logger
    )

    try:
        # Copie vers Archives
        archive_path.write_bytes(src.read_bytes())
        logger.info("[ARCHIVE] Copie → %s", archive_path)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ARCHIVE] Échec de la copie : %s", exc)
        raise

    # Enregistrement DB + lien parent
    try:
        # note = Note(
        #     # remplis les champs requis par ton dataclass Note
        #     title=Path(archive_path).stem,
        #     file_path=Path(archive_path).as_posix(),
        #     folder_id=folder_id,              # calcule/lookup avant
        #     category_id=category_id,          # idem
        #     subcategory_id=subcategory_id,    # idem
        #     status="archive",
        #     # ... autres champs si obligatoires ou mets None/defauts
        # )

        # archive_note_id = upsert_note_from_model(note)

        # archive_note_id = upsert_note_from_model(Path(archive_path).as_posix())
        archive_note_id = add_note_to_db(Path(archive_path).as_posix(), logger=logger)
        update_obsidian_note(note_id, {"parent_id": archive_note_id}, logger=logger)
        update_obsidian_note(archive_note_id, {"parent_id": note_id}, logger=logger)
        logger.info("[ARCHIVE] Lien synthèse : %s → %s", note_id, archive_note_id)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ARCHIVE] Échec lors de l'enregistrement DB/lien : %s", exc)
        raise

    return archive_path
