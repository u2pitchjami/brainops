"""
# utils/regen_utils.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.header.headers import make_properties
from brainops.io.note_reader import read_note_full
from brainops.models.classification import ClassificationResult
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.metadata import NoteMetadata
from brainops.process_import.synthese.add_or_update import update_synthesis
from brainops.process_import.synthese.import_synthese import process_import_syntheses
from brainops.sql.get_linked.db_get_linked_folders_utils import get_category_context_from_folder
from brainops.sql.get_linked.db_get_linked_notes_utils import get_file_path, get_parent_id
from brainops.sql.temp_blocs.db_delete_temp_blocs import delete_blocs_by_path_and_source
from brainops.utils.files import clean_content
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
        delete_blocs_by_path_and_source(note_id, source="all", logger=logger)

        # recup archives datas
        recup_id, recup_path, meta_yaml, content, classification = recup_note_data(note_id)

        # Relance synthèse
        synthesis = process_import_syntheses(
            content=content,
            note_id=note_id,
            archive_path=recup_path,
            synthesis_path=path,
            meta_final=meta_yaml,
            classification=classification,
            regen=True,
            logger=logger,
        )
        if not synthesis:
            return False
        logger.info("[REGEN] Synthèse régénérée pour note_id=%s", note_id)
        return True
    except BrainOpsError as exc:
        logger.exception("[ERROR] regen_synthese_from_archive(%s) : %s", note_id, exc)
        exc.ctx.setdefault("note_id", note_id)
        raise


def regen_header(note_id: int, filepath: str | Path) -> bool:
    """
    Régénère l'entête (tags, summary, champs YAML) d'une note.

    Détermine le 'status' attendu :
      - si parent_id est fourni : 'synthesis' si le parent est 'archive', sinon 'archive'
      - sinon : 'archive' si le chemin contient un segment 'Archives' (insensible casse), sinon 'synthesis'
    """
    try:
        path = Path(str(filepath))

        # recup datas
        recup_id, recup_path, meta_yaml, content, classification = recup_note_data(note_id, recup_parent=False)

        logger.info("[REGEN_HEADER] %s → status=%s", path.name, classification.status)
        properties = make_properties(
            content=content,
            meta_yaml=meta_yaml,
            classification=classification,
            note_id=recup_id,
            status=classification.status,
            logger=logger,
        )
        if not properties:
            return False
        return True

        update = update_synthesis(
            final_synth_body_content=content,
            note_id=recup_id,
            synthesis_path=filepath,
            meta_synth_final=properties,
            classification=classification,
            logger=logger,
        )
        if not update:
            return False
        return True

    except BrainOpsError as exc:
        logger.exception("[ERROR] regen_header(%s) : %s", note_id, exc)
        exc.ctx.setdefault("note_id", note_id)
        raise


def recup_note_data(
    note_id: int, recup_parent: bool = True
) -> tuple[int, Path, NoteMetadata, str, ClassificationResult]:
    """
    recup_note_data _summary_

    _extended_summary_

    Args:
        note_id (int): _description_
    """
    parent_id = get_parent_id(note_id=note_id, logger=logger)
    if not parent_id:
        raise BrainOpsError(
            "[REGEN] ❌ Aucun parent_id impossible de regen",
            code=ErrCode.METADATA,
            ctx={"fonction": "recup_note_data", "note_id": note_id},
        )
    if recup_parent:
        recup_id = parent_id
    else:
        recup_id = note_id
    recup_path = Path(get_file_path(recup_id))
    recup_folder = recup_path.parent.as_posix()
    try:
        meta_yaml, body = read_note_full(recup_path, logger=logger)
        content = clean_content(body)
        classification = get_category_context_from_folder(recup_folder, logger=logger)
        if not classification:
            logger.warning("[WARN] ❌ get_note_type n'a rien renvoyé pour (id=%s)", note_id)
            raise BrainOpsError(
                "[REGEN] ❌ Aucune classif, regen impossible",
                code=ErrCode.METADATA,
                ctx={"fonction": "recup_note_data", "note_id": note_id},
            )
        logger.debug(f"classification : {classification}")

        return recup_id, recup_path, meta_yaml, content, classification
    except BrainOpsError as exc:
        logger.exception("[ERROR] regen_synthese_from_archive(%s) : %s", note_id, exc)
        exc.ctx.setdefault("note_id", note_id)
        raise
