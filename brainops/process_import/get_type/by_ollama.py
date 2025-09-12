"""
# handlers/process/get_type.py
"""

from __future__ import annotations

from pathlib import Path
import shutil

from brainops.io.note_reader import read_note_body
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_import.get_type.by_ollama_utils import (
    _classify_with_llm,
    _resolve_destination,
    clean_note_type,
    handle_uncategorized,
    parse_category_response,
)
from brainops.process_import.utils.paths import ensure_folder_exists
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.utils.files import clean_content
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def get_type_by_ollama(filepath: str, note_id: int, *, logger: LoggerProtocol | None = None) -> str:
    """
    Analyse le type via LLM → calcule dossier cible → déplace → met à jour la DB.

    Retourne le **nouveau chemin complet** ou None.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] Entrée process_get_note_type")
    llama_proposition: str = ""  # évite variable potentiellement non définie (#bug)

    try:
        # 1) contenu sans YAML
        content_lines = read_note_body(filepath, logger=logger)
        content_lines = clean_content(content_lines)
        logger.debug("[DEBUG] Contenu net (extrait) ok")

        # 2) LLM
        llama_proposition = _classify_with_llm(note_id, content_lines, logger=logger)
        logger.debug("[DEBUG] LLM proposition : %s", llama_proposition)

        # 3) Parse réponse ollama
        parsed = parse_category_response(llama_proposition)

        note_type = clean_note_type(parsed)
        if any(term in note_type.lower() for term in ["uncategorized", "unknow"]):
            handle_uncategorized(note_id, filepath, note_type, llama_proposition, logger=logger)
            raise BrainOpsError(
                "Classification invalide → 'uncategorized",
                code=ErrCode.OLLAMA,
                ctx={"llama_proposition": llama_proposition},
            )

        logger.info("[TYPE] 👌 Type de note détecté pour (ID=%s) : %s", note_id, note_type)

        # 3) Résolution dossier cible
        classification = _resolve_destination(note_type, note_id, filepath, logger=logger)

        # 4) Déplacement physique + MAJ DB
        ensure_folder_exists(Path(classification.dest_folder), logger=logger)
        logger.debug("[DEBUG] Dossier cible ok : %s", classification.dest_folder)
        src = Path(filepath).expanduser().resolve()
        logger.debug("[DEBUG] src %s", src.as_posix())
        new_path: str = shutil.move(src.as_posix(), classification.dest_folder)
        logger.debug("[DEBUG] new_path %s", new_path)
        if not new_path or not Path(new_path).exists():
            raise BrainOpsError("Echec déplacement", code=ErrCode.UNEXPECTED, ctx={"note_id": note_id})
        logger.info("[DEPLACEMENT] 👌 Réussi : %s", new_path)

        # 5) Update de la base
        updates = {
            "folder_id": classification.folder_id,
            "file_path": new_path,  # ⚠️ utiliser le chemin retourné (#bugfix)
            "category_id": classification.category_id,
            "subcategory_id": classification.subcategory_id,
            "status": classification.status,
        }
        logger.debug("[DEBUG] updates : %s", updates)
        update_note = update_obsidian_note(note_id, updates, logger=logger)

    except Exception as exc:
        logger.exception("Crash inattendu dans : %s", exc)
        handle_uncategorized(note_id, filepath, note_type, llama_proposition, logger=logger)
        raise BrainOpsError("get_type_by_ollama KO", code=ErrCode.UNEXPECTED, ctx={"note_id": note_id}) from exc
    return new_path
