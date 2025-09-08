# utils/regen_utils.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from brainops.header.headers import make_properties
from brainops.process_import.normal.import_normal import import_normal
from brainops.process_import.synthese.import_synthese import process_import_syntheses
from brainops.process_import.utils.divers import rename_file
from brainops.sql.categs.db_categ_utils import categ_extract
from brainops.sql.get_linked.db_get_linked_data import get_note_linked_data
from brainops.sql.get_linked.db_get_linked_notes_utils import get_file_path
from brainops.sql.notes.db_temp_blocs import delete_blocs_by_path_and_source
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.utils.logger import (
    LoggerProtocol,
    ensure_logger,
    get_logger,
    with_child_logger,
)

logger = get_logger("Brainops Regen")


def regen_synthese_from_archive(
    note_id: int, filepath: Optional[str | Path] = None
) -> bool:
    """
    Régénère la synthèse d'une note à partir de son archive liée.
    - Purge les blocs temporaires (embeddings / prompts) pour repartir propre.
    - Relance le pipeline de synthèse sur le fichier cible.
    """
    try:
        path = Path(str(filepath)) if filepath else Path(get_file_path(note_id) or "")
        if not path or not path.as_posix():
            logger.error(
                "[REGEN] Impossible de déterminer le filepath pour note_id=%s", note_id
            )
            return

        logger.info("[REGEN] Synthèse → note_id=%s | path=%s", note_id, path.as_posix())
        # Purge de tous les blocs liés à ce chemin (embeddings, prompts, etc.)
        delete_blocs_by_path_and_source(
            note_id, path.as_posix(), source="all", logger=logger
        )

        # Relance synthèse
        process_import_syntheses(path.as_posix(), note_id, logger=logger)
        logger.info("[REGEN] Synthèse régénérée pour note_id=%s", note_id)
        return True

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ERROR] regen_synthese_from_archive(%s) : %s", note_id, exc)
        return False


def regen_header(
    note_id: int, filepath: str | Path, parent_id: Optional[int] = None
) -> bool:
    """
    Régénère l'entête (tags, summary, champs YAML) d'une note.
    Détermine le 'status' attendu :
      - si parent_id est fourni : 'synthesis' si le parent est 'archive', sinon 'archive'
      - sinon : 'archive' si le chemin contient un segment 'Archives' (insensible casse), sinon 'synthesis'
    """
    try:
        path = Path(str(filepath)).resolve()
        if parent_id:
            parent = get_note_linked_data(parent_id, "note", logger=logger)
            parent_status = (parent or {}).get("status")
            status = "synthesis" if parent_status == "archive" else "archive"
        else:
            status = (
                "archive"
                if any(part.lower() == "archives" for part in path.parts)
                else "synthesis"
            )

        logger.info("[REGEN_HEADER] %s → status=%s", path.name, status)
        make_properties(path.as_posix(), note_id, status)
        return True

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "[ERROR] regen_header(%s) : %s",
            path.as_posix() if "path" in locals() else filepath,
            exc,
        )
        return False
