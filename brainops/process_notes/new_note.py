"""
# process/new_note.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.header.headers import add_metadata_to_yaml
from brainops.header.yaml_read import ensure_status_in_yaml
from brainops.io.note_reader import read_metadata_object
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.note import Note
from brainops.process_import.utils.paths import path_is_inside
from brainops.process_notes.new_note_utils import (
    _handle_duplicate_note,
    _normalize_abs_posix,
    _safe_stat_times,
    compute_wc_and_hash,
)
from brainops.sql.get_linked.db_get_linked_folders_utils import (
    get_category_context_from_folder,
    get_folder_id,
)
from brainops.sql.notes.db_check_duplicate_note import check_duplicate
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.sql.notes.db_upsert_note import upsert_note_from_model
from brainops.utils.config import IMPORTS_PATH
from brainops.utils.logger import (
    LoggerProtocol,
    ensure_logger,
    with_child_logger,
)
from brainops.utils.normalization import sanitize_created, sanitize_yaml_title


@with_child_logger
def new_note(file_path: str | Path, logger: LoggerProtocol | None = None) -> int:
    """
    Crée/Met à jour une note à partir d'un fichier du vault.

    - Upsert par `file_path` (UNIQUE).
    - Vérifie les doublons si la note vient de IMPORTS_PATH.
    - Tag 'duplicate' + déplacement dans DUPLICATES_PATH si doublon confirmé.
    - Ajoute métadonnées YAML si dans 'Archives'.
    """
    logger = ensure_logger(logger, __name__)
    fp = _normalize_abs_posix(file_path)
    base_folder = fp.parent

    try:
        # ---- construire le modèle Note ---------------------------------------
        metadata = read_metadata_object(str(fp), logger=logger)
        # 🔹 Fallback et nettoyage
        title = sanitize_yaml_title(metadata.title)
        status = metadata.status
        created = sanitize_created(metadata.created)
        source = metadata.source
        author = metadata.author
        project = metadata.project
        folder_id = get_folder_id(base_folder.as_posix(), logger=logger) or 0
        cat_id, subcat_id, _cat_name, _subcat_name = get_category_context_from_folder(
            base_folder.as_posix(), logger=logger
        )

        _, modified_at = _safe_stat_times(fp)
        wc, chash = compute_wc_and_hash(fp)

        note = Note(
            title=title,
            file_path=fp.as_posix(),
            folder_id=int(folder_id),
            category_id=cat_id,
            subcategory_id=subcat_id,
            status=status,
            summary=None,
            source=source,
            author=author,
            project=project,
            created_at=created,
            modified_at=modified_at,
            word_count=wc,
            content_hash=chash,
            source_hash=None,
            lang=None,
        )

        # ---- upsert en DB -----------------------------------------------------
        note_id: int = upsert_note_from_model(note, logger=logger)

        # ---- détection doublons pour les imports ------------------------------
        if path_is_inside(IMPORTS_PATH, base_folder.as_posix()):
            is_dup, dup_info = check_duplicate(note_id, fp.as_posix(), logger=logger)
            logger.debug("[DUP] is_dup=%s dup_info=%s", is_dup, dup_info)
            if is_dup:
                new_path = _handle_duplicate_note(fp, dup_info, logger=logger)
                updates = {"file_path": new_path.as_posix(), "status": "duplicate"}
                logger.debug("[NOTES] Mise à jour DB (duplicate): %s", updates)
                update_obsidian_note(note_id, updates, logger=logger)
                ensure_status_in_yaml(new_path.as_posix(), status="duplicate", logger=logger)
                raise BrainOpsError("Note en doublon", code=ErrCode.DB, ctx={"note_id": note_id})

        # ---- règles spécifiques Archives -------------------------------------
        if "Archives" in fp.as_posix():
            header = add_metadata_to_yaml(note_id, fp.as_posix(), logger=logger)
            if not header:
                logger.warning("[NOTES] 🚨 Echec Ajout métadonnées YAML (Archives)")
            logger.info("[NOTES] Ajout métadonnées YAML (Archives)")

    except Exception as exc:  # pylint: disable=broad-except
        raise BrainOpsError("Note Upsert KO", code=ErrCode.DB, ctx={"note_id": note_id}) from exc
    return note_id
