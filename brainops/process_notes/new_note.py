"""
# process/new_note.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from brainops.header.header_utils import hash_source
from brainops.header.yaml_read import ensure_status_in_yaml
from brainops.io.note_reader import read_metadata_object
from brainops.io.note_writer import merge_metadata_in_note
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.note import Note
from brainops.process_import.utils.divers import lang_detect
from brainops.process_import.utils.paths import path_is_inside
from brainops.process_notes.new_note_utils import (
    _handle_duplicate_note,
    _normalize_abs_posix,
    compute_wc_and_hash,
)
from brainops.process_regen.regen_utils import regen_header
from brainops.sql.get_linked.db_get_linked_folders_utils import (
    get_category_context_from_folder,
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
    logger.debug(f"[NEW_NOTE] fp : {fp}")
    base_folder = fp.parent
    logger.debug(f"[NEW_NOTE] base_folder : {base_folder}")
    try:
        # ---- construire le modèle Note ---------------------------------------
        metadata = read_metadata_object(str(fp), logger=logger)
        logger.debug(f"[NEW_NOTE] metadata : {metadata}")
        # 🔹 Fallback et nettoyage
        title = metadata.title
        created = metadata.created
        title_sani = sanitize_yaml_title(metadata.title)
        created_sani = sanitize_created(metadata.created)
        source = metadata.source
        author = metadata.author
        project = metadata.project
        classification = get_category_context_from_folder(base_folder.as_posix(), logger=logger)
        logger.debug(f"[NEW_NOTE] classification : {classification}")
        # --- Langue -----------------------------------------------------------------
        lang = None
        try:
            lang = lang_detect(fp.as_posix(), logger=logger)
            if lang:
                lang = lang[:3].lower()
        except Exception:
            lang = None

        modified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        wc, chash = compute_wc_and_hash(fp)
        source_hash = hash_source(source) if source else None
        note = Note(
            title=title_sani,
            file_path=fp.as_posix(),
            folder_id=classification.folder_id,
            category_id=classification.category_id,
            subcategory_id=classification.subcategory_id,
            status=classification.status,
            summary=None,
            source=source,
            author=author,
            project=project,
            created_at=created_sani,
            modified_at=modified_at,
            word_count=wc,
            content_hash=chash,
            source_hash=source_hash,
            lang=None,
        )

        # ---- upsert en DB -----------------------------------------------------
        note_id: int = upsert_note_from_model(note, logger=logger)
        logger.debug(f"[NEW_NOTE] note_id : {note_id}")
        if title != title_sani or created_sani != created:
            updates_head: dict[str, str | int | list[str]] = {"created": created_sani, "title": title_sani}
            merge_metadata_in_note(filepath=file_path, updates=updates_head, logger=logger)

        # ---- détection doublons pour les imports ------------------------------
        if path_is_inside(IMPORTS_PATH, base_folder.as_posix()):
            is_dup, dup_info = check_duplicate(note_id, fp.as_posix(), metadata, logger=logger)
            logger.debug("[DUP] is_dup=%s dup_info=%s", is_dup, dup_info)
            if is_dup:
                new_path = _handle_duplicate_note(fp, dup_info, logger=logger)
                updates = {"file_path": new_path.as_posix(), "status": "duplicate"}
                logger.debug("[NOTES] Mise à jour DB (duplicate): %s", updates)
                update_obsidian_note(note_id, updates, logger=logger)
                ensure_status_in_yaml(new_path.as_posix(), status="duplicate", logger=logger)
                raise BrainOpsError(
                    "Note en doublon",
                    code=ErrCode.DB,
                    ctx={"step": "new_note", "note_id": note_id, "dup_info": dup_info},
                )

        # ---- règles spécifiques Archives -------------------------------------
        if "Archives" in fp.as_posix():
            header = regen_header(note_id, fp.as_posix())
            if not header:
                logger.warning("[NOTES] 🚨 Echec Ajout métadonnées YAML (Archives)")
            logger.info("[NOTES] Ajout métadonnées YAML (Archives)")

    except BrainOpsError as exc:
        exc.with_context({"step": "new_note", "note_id": note_id})
        raise
    except Exception as exc:
        raise BrainOpsError(
            "[NOTE] ❌ CREATION NOTE KO",
            code=ErrCode.UNEXPECTED,
            ctx={
                "step": "new_note",
                "note_id": note_id,
                "root_exc": type(exc).__name__,
                "root_msg": str(exc),
            },
        ) from exc
    return note_id
