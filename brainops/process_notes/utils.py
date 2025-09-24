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
