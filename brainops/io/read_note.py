"""
io.utils.py — Fonctions ytils centralisées de lecture de notes Obsidian.
"""

from __future__ import annotations

from pathlib import Path

from brainops.io.paths import to_abs
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.types import StrOrPath
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def read_note_content(filepath: StrOrPath, *, logger: LoggerProtocol | None = None) -> str:
    """
    Lit le contenu d'une note (UTF-8).
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[read_note_content] %s, pour %s", filepath)
    p = Path(to_abs(filepath))
    logger.debug("[read_note_content] p %s", p)
    try:
        text = p.read_text(encoding="utf-8")
        logger.debug("[read] %s (%d chars)", p, len(text))
    except Exception as exc:
        raise BrainOpsError("Lecture KO", code=ErrCode.FILEERROR, ctx={"filepath": filepath}) from exc
    return text
