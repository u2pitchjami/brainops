"""
# utils/divers.py
"""

from __future__ import annotations

from brainops.header.get_tags_and_summary import get_tags_from_ollama
from brainops.io.note_reader import read_note_body
from brainops.models.classification import ClassificationResult
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.get_linked.db_get_linked_notes_utils import (
    get_data_for_should_trigger,
)
from brainops.sql.notes.db_update_notes import update_obsidian_tags
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def check_if_tags(
    filepath: str,
    note_id: int,
    wc: int,
    status: str,
    classification: ClassificationResult,
    logger: LoggerProtocol | None = None,
) -> bool:
    """
    Vérifie si des tags doivent être ajoutés et les met à jour si besoin.

    Retourne True si des tags ont été ajoutés, False sinon.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug(
        "[TAGS] Vérification des tags pour note_id=%s, filepath=%s, wc=%s, status=%s", note_id, filepath, wc, status
    )
    tags = []
    try:
        if classification.status in (
            "synthesis",
            "archive",
            "duplicate",
            "error",
            "draft",
            "uncategorized",
            "templates",
            "technical",
        ):
            return False

        if wc > 100:
            content = read_note_body(filepath=filepath, logger=logger)
            tags = get_tags_from_ollama(content=content, note_id=note_id, logger=logger)
        if classification.category_name not in tags:
            tags.append(classification.category_name)
        if classification.subcategory_name and classification.subcategory_name not in tags:
            tags.append(classification.subcategory_name)

        if tags:
            logger.debug("[DEBUG] Tags à ajouter : %s", tags)
            if update_obsidian_tags(note_id, tags=tags, logger=logger):
                logger.info("[INFO] Tags mis à jour avec succès : %s", tags)
                return True
        return False
    except Exception as exc:
        raise BrainOpsError(
            "[TAGS] ❌ Erreur dans la recherche de tags",
            code=ErrCode.METADATA,
            ctx={"step": "check_if_tags", "file": filepath, "note_id": note_id, "status": status, "word_count": wc},
        ) from exc


@with_child_logger
def should_trigger_process(
    note_id: int,
    new_word_count: int,
    threshold: int = 100,
    logger: LoggerProtocol | None = None,
) -> tuple[bool, str | None, int | None]:
    """
    Détermine si une note doit être retraitée en fonction de l'écart de word_count.

    Retourne (trigger, status, parent_id).
    """
    logger = ensure_logger(logger, __name__)
    status, parent_id, old_word_count = get_data_for_should_trigger(note_id, logger=logger)
    word_diff = abs((old_word_count or 0) - new_word_count)
    trigger = word_diff > threshold

    if not trigger:
        return False, None, None

    if status == "archive":
        return True, "archive", parent_id
    if status == "synthesis":
        return True, "synthesis", parent_id
    return True, None, parent_id
