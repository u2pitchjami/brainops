# process/new_note.py
from __future__ import annotations

import shutil
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Optional, Tuple

from brainops.header.extract_yaml_header import extract_note_metadata
from brainops.header.headers import add_metadata_to_yaml
from brainops.header.yaml_read import ensure_status_in_yaml
from brainops.models.note import Note
from brainops.process_import.utils.paths import path_is_inside
from brainops.process_notes.wc_and_hash import compute_wc_and_hash
from brainops.sql.get_linked.db_get_linked_folders_utils import (
    get_category_context_from_folder,
    get_folder_id,
)
from brainops.sql.notes.db_notes import upsert_note_from_model
from brainops.sql.notes.db_notes_utils import check_duplicate
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.utils.config import DUPLICATES_LOGS, DUPLICATES_PATH, IMPORTS_PATH
from brainops.utils.logger import (
    LoggerProtocol,
    ensure_logger,
    get_logger,
    with_child_logger,
)
from brainops.utils.normalization import sanitize_created, sanitize_yaml_title

# ---------- helpers FS ---------------------------------------------------------


def _normalize_abs_posix(p: str | Path) -> Path:
    return Path(str(p)).expanduser().resolve()


def _safe_stat_times(fp: Path) -> Tuple[Optional[date], Optional[datetime]]:
    try:
        st = fp.stat()
        cdate = datetime.fromtimestamp(st.st_ctime).date()
        mdt = datetime.fromtimestamp(st.st_mtime)
        return cdate, mdt
    except Exception:
        return None, None


def _safe_word_count(fp: Path) -> int:
    try:
        if fp.suffix.lower() not in {".md", ".txt"}:
            return 0
        # lecture raisonnable (éviter fichiers énormes)
        text = fp.read_text(encoding="utf-8", errors="ignore")
        return len(text.split())
    except Exception:
        return 0


def _sha256_file(fp: Path) -> Optional[str]:
    try:
        h = sha256()
        with fp.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _ensure_duplicates_dir() -> None:
    Path(DUPLICATES_PATH).mkdir(parents=True, exist_ok=True)
    Path(DUPLICATES_LOGS).parent.mkdir(parents=True, exist_ok=True)


# ---------- core ---------------------------------------------------------------
@with_child_logger
def new_note(
    file_path: str | Path, logger: Optional[LoggerProtocol] = None
) -> Optional[int]:
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
        metadata = extract_note_metadata(file_path)

        # 🔹 Fallback et nettoyage
        title = sanitize_yaml_title(metadata.get("title"))
        status = metadata.get("status", "draft")
        created = sanitize_created(metadata.get("created"))
        source = metadata.get("source", None)
        author = metadata.get("author", None)
        project = metadata.get("project", None)
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
        note_id = upsert_note_from_model(note, logger=logger)
        if not note_id:
            logger.error(
                "[NOTES] upsert_note_from_model a échoué pour %s", fp.as_posix()
            )
            return None

        # ---- détection doublons pour les imports ------------------------------
        if path_is_inside(IMPORTS_PATH, base_folder.as_posix()):
            is_dup, dup_info = check_duplicate(note_id, fp.as_posix(), logger=logger)
            logger.debug("[DUP] is_dup=%s dup_info=%s", is_dup, dup_info)
            if is_dup:
                new_path = _handle_duplicate_note(fp, dup_info, logger=logger)
                updates = {"file_path": new_path.as_posix(), "status": "duplicate"}
                logger.debug("[NOTES] Mise à jour DB (duplicate): %s", updates)
                update_obsidian_note(note_id, updates, logger=logger)
                ensure_status_in_yaml(
                    new_path.as_posix(), status="duplicate", logger=logger
                )
                return None  # ou retourner new_path si tu préfères

        # ---- règles spécifiques Archives -------------------------------------
        if "Archives" in fp.as_posix():
            logger.info("[NOTES] Ajout métadonnées YAML (Archives)")
            add_metadata_to_yaml(note_id, fp.as_posix(), logger=logger)

        return note_id

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[NOTES] Erreur new_note(%s): %s", fp.as_posix(), exc)
        return None


@with_child_logger
def _handle_duplicate_note(
    file_path: Path, match_info: list[dict], *, logger: LoggerProtocol
) -> Path:
    """
    Déplace une note vers DUPLICATES_PATH et journalise les infos.
    """
    logger = logger
    _ensure_duplicates_dir()
    new_path = Path(DUPLICATES_PATH) / file_path.name

    try:
        shutil.move(str(file_path), str(new_path))
        logger.warning("Note déplacée vers 'duplicates' : %s", new_path.as_posix())

        with open(DUPLICATES_LOGS, "a", encoding="utf-8") as log_file:
            log_file.write(
                f"{datetime.now().isoformat()} - {file_path.name} doublon de {match_info}\n"
            )

        return new_path
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[DUPLICATE] Échec déplacement vers 'duplicates' : %s", exc)
        return file_path
