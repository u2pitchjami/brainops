"""
# handlers/process/get_type.py
"""

from __future__ import annotations

from pathlib import Path
import shutil

from brainops.header.extract_yaml_header import (
    extract_yaml_header,
)
from brainops.models.exceptions import BrainOpsError
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
        _, content_lines = extract_yaml_header(filepath, logger=logger)
        content_lines = clean_content(content_lines)

        if not content_lines.strip():
            logger.warning("[WARNING] 🚨 Contenu vide après nettoyage → UNCATEGORIZED")
            handle_uncategorized(note_id, filepath, "Empty content", llama_proposition, logger=logger)
            raise
        logger.debug("[DEBUG] Contenu net (extrait) ok")

        # 2) LLM
        llama_proposition = _classify_with_llm(content_lines, logger=logger) or ""

        if not llama_proposition:
            logger.warning("[WARNING] 🚨 Aucune proposition de classification reçue → UNCATEGORIZED")
            handle_uncategorized(note_id, filepath, "No classification", llama_proposition, logger=logger)
            raise
        logger.debug("[DEBUG] LLM proposition : %s", llama_proposition)

        # 3) Parse réponse ollama
        parsed = parse_category_response(llama_proposition)
        if not parsed:
            logger.warning("[WARNING] 🚨 Classification invalide → UNCATEGORIZED")
            handle_uncategorized(note_id, filepath, "Invalid format", llama_proposition, logger=logger)
            raise

        note_type = clean_note_type(parsed)
        if any(term in note_type.lower() for term in ["uncategorized", "unknow"]):
            logger.warning("[WARNING] 🚨 Classification invalide %s → 'uncategorized'", note_type)
            handle_uncategorized(note_id, filepath, note_type, llama_proposition, logger=logger)
            raise

        logger.info("[TYPE] 👌 Type de note détecté pour (ID=%s) : %s", note_id, note_type)

        # 3) Résolution dossier cible
        classification = _resolve_destination(note_type, note_id, filepath, logger=logger)
        if not classification:
            logger.warning(
                "[WARNING] 🚨 La note %s a été déplacée dans 'uncategorized' (destination manquante).",
                filepath,
            )
            handle_uncategorized(note_id, filepath, note_type, llama_proposition, logger=logger)
            raise

        # 4) Déplacement physique + MAJ DB
        ensure_folder_exists(Path(classification.dest_folder), logger=logger)
        logger.debug("[DEBUG] Dossier cible ok : %s", classification.dest_folder)
        src = Path(filepath).expanduser().resolve()
        logger.debug("[DEBUG] src %s", src.as_posix())
        new_path: str = shutil.move(src.as_posix(), classification.dest_folder)
        logger.debug("[DEBUG] new_path %s", new_path)
        if not new_path or not Path(new_path).exists():
            logger.warning("[WARNING] 🚨 Déplacement échoué : %s", new_path)
            handle_uncategorized(note_id, filepath, note_type, llama_proposition, logger=logger)
            raise
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
        if not update_note:
            logger.warning("[WARNING] 🚨 Erreur Update Base : %s", filepath)
            handle_uncategorized(note_id, filepath, note_type, llama_proposition, logger=logger)
            raise
    except BrainOpsError:
        raise
    except Exception as exc:
        logger.exception("Crash inattendu dans : %s", exc)
        handle_uncategorized(note_id, filepath, note_type, llama_proposition, logger=logger)
        raise BrainOpsError(f"Erreur inattendue: {exc}") from exc
    return new_path
