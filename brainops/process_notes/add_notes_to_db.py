"""# sql/db_notes.py"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from brainops.header.extract_yaml_header import extract_note_metadata
from brainops.header.header_utils import hash_source
from brainops.models.note import Note
from brainops.process_folders.folders import add_folder
from brainops.process_folders.process_folder_event import (
    _detect_folder_type as detect_folder_type,  # garde ton detecteur
)
from brainops.process_import.utils.divers import lang_detect
from brainops.process_notes.wc_and_hash import compute_wc_and_hash
from brainops.sql.get_linked.db_get_linked_folders_utils import (
    get_category_context_from_folder,
    get_folder_id,
)
from brainops.sql.notes.db_notes import upsert_note_from_model
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import sanitize_created, sanitize_yaml_title


@with_child_logger
def add_note_to_db(
    file_path: str | Path, *, logger: LoggerProtocol | None = None
) -> Optional[int]:
    """
    Crée ou met à jour une note (upsert par file_path UNIQUE) à partir d'un fichier.
    - Normalise le chemin
    - Récupère folder/category/subcategory
    - Lit les métadonnées YAML (title, status, created, last_modified, summary, source, author, project)
    - Calcule word_count + content_hash en 1 seul passage
    - Détecte la langue
    Retourne l'id de la note (toujours).
    """
    logger = ensure_logger(logger, __name__)
    fp = Path(str(file_path)).expanduser().resolve()
    base_folder = fp.parent.as_posix()

    # --- Dossier/Classification -------------------------------------------------
    folder_id = get_folder_id(base_folder, logger=logger)
    if not folder_id:
        logger.warning("[NOTES] Dossier manquant en DB: %s → création…", base_folder)
        ftype = detect_folder_type(base_folder)
        folder_id = add_folder(base_folder, ftype, logger=logger)  # ⚠️ on crée le folder
        # on redemande l'id (suivant ton implémentation d'add_folder)
        folder_id = folder_id or get_folder_id(base_folder, logger=logger)
        if not folder_id:
            logger.error(
                "[NOTES] Impossible de récupérer folder_id pour %s", base_folder
            )
            return None

    cat_id, subcat_id, _cname, _scname = get_category_context_from_folder(
        base_folder, logger=logger
    )

    # --- Métadonnées YAML -------------------------------------------------------
    meta = extract_note_metadata(fp.as_posix(), logger=logger) or {}
    title = sanitize_yaml_title(meta.get("title")) or fp.stem.replace("_", " ")
    status = str(meta.get("status", "draft")).strip() or "draft"
    created = sanitize_created(meta.get("created"), logger=logger)  # -> date | None
    modified_raw = meta.get("last_modified")
    modified_at: Optional[datetime] = None
    if isinstance(modified_raw, datetime):
        modified_at = modified_raw
    elif isinstance(modified_raw, str):
        try:
            modified_at = datetime.fromisoformat(modified_raw)
        except ValueError:
            modified_at = None

    summary = meta.get("summary")
    source = meta.get("source")
    author = meta.get("author")
    project = meta.get("project")

    # --- Word count + hash en 1 passage ----------------------------------------
    word_count, content_hash = compute_wc_and_hash(fp)

    source_hash = hash_source(source) if source else None

    # --- Langue -----------------------------------------------------------------
    lang = None
    try:
        lang = lang_detect(fp.as_posix(), logger=logger)
        if lang:
            lang = lang[:3].lower()
    except Exception:
        lang = None

    # --- Dates FS en secours si YAML absent ------------------------------------
    try:
        st = fp.stat()
        if created is None:
            created = datetime.fromtimestamp(st.st_ctime).date()
        if modified_at is None:
            modified_at = datetime.fromtimestamp(st.st_mtime)
    except Exception:
        pass

    # --- Dataclass Note & upsert ------------------------------------------------
    note = Note(
        title=title,
        file_path=fp.as_posix(),
        folder_id=int(folder_id),
        category_id=cat_id,
        subcategory_id=subcat_id,
        status=status,
        summary=summary,
        source=source,
        author=author,
        project=project,
        created_at=created if isinstance(created, date) else None,
        modified_at=modified_at,
        word_count=int(word_count or 0),
        content_hash=content_hash,
        source_hash=source_hash,
        lang=lang,
    )

    note_id = upsert_note_from_model(note, logger=logger)
    if not note_id:
        logger.error("[NOTES] upsert_note_from_model a échoué pour %s", fp.as_posix())
        return None

    logger.debug("[NOTES] Upsert OK %s -> id=%s", fp.as_posix(), note_id)
    return note_id
