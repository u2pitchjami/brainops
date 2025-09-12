"""
# utils/regen_utils.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.header.headers import make_properties
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_import.synthese.import_synthese import process_import_syntheses
from brainops.sql.get_linked.db_get_linked_data import get_note_linked_data
from brainops.sql.get_linked.db_get_linked_notes_utils import get_file_path
from brainops.sql.temp_blocs.db_delete_temp_blocs import delete_blocs_by_path_and_source
from brainops.utils.logger import get_logger

logger = get_logger("Brainops Regen")


def regen_synthese_from_archive(note_id: int, filepath: str | Path | None = None) -> bool:
    """
    Régénère la synthèse d'une note à partir de son archive liée.

    - Purge les blocs temporaires (embeddings / prompts) pour repartir propre.
    - Relance le pipeline de synthèse sur le fichier cible.
    """
    try:
        path = Path(str(filepath)) if filepath else Path(get_file_path(note_id) or "")
        if not path or not path.as_posix():
            raise BrainOpsError("filepath KO", code=ErrCode.FILEERROR, ctx={"note_id": note_id})

        logger.info("[REGEN] Synthèse → note_id=%s | path=%s", note_id, path.as_posix())
        # Purge de tous les blocs liés à ce chemin (embeddings, prompts, etc.)
        delete_blocs_by_path_and_source(note_id, path.as_posix(), source="all", logger=logger)

        # Relance synthèse
        synthesis = process_import_syntheses(path.as_posix(), note_id, logger=logger)
        if not synthesis:
            return False
        logger.info("[REGEN] Synthèse régénérée pour note_id=%s", note_id)
        return True
    except BrainOpsError as exc:
        logger.exception("[ERROR] regen_synthese_from_archive(%s) : %s", note_id, exc)
        exc.ctx.setdefault("note_id", note_id)
        raise


def regen_header(note_id: int, filepath: str | Path, parent_id: int | None = None) -> bool:
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
            status = "archive" if any(part.lower() == "archives" for part in path.parts) else "synthesis"

        logger.info("[REGEN_HEADER] %s → status=%s", path.name, status)
        properties = make_properties(path.as_posix(), note_id, status)
        if not properties:
            return False
        return True

    except BrainOpsError as exc:
        logger.exception("[ERROR] regen_header(%s) : %s", note_id, exc)
        exc.ctx.setdefault("note_id", note_id)
        raise
