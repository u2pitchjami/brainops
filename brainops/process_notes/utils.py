"""
# utils/divers.py
"""

from __future__ import annotations

from brainops.sql.get_linked.db_get_linked_notes_utils import (
    get_data_for_should_trigger,
)
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


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


@with_child_logger
def detect_update_status_by_folder(path: str, logger: LoggerProtocol | None = None) -> str | None:
    """
    Détection par règles simples sur le chemin complet (fallback) → Enum.
    """
    new_status = None
    lower = path.lower()
    if "/z_technical/duplicates/" in lower:
        new_status = "duplicates"
    elif "/z_technical/error/" in lower:
        new_status = "error"
    elif "/z_technical/imports/" in lower:
        new_status = "draft"
    elif "/z_technical/uncategorized/" in lower:
        new_status = "uncategorized"
    elif "/z_technical/templates/" in lower:
        new_status = "templates"
    elif "/DailyNotes/" in lower:
        new_status = "daily_notes"
    elif "/notes/Personnal/" in lower:
        new_status = "personnal"
    elif "/notes/projects/" in lower:
        new_status = "projects"

    return new_status
