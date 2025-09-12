# brainops/core/exceptions.py
from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum  # py>=3.11
from typing import Any


class ErrCode(StrEnum):
    METADATA = "METADATA"
    OLLAMA = "OLLAMA"
    DB = "DB"
    UNEXPECTED = "UNEXPECTED"
    NOFILE = "NOFILE"
    FILEERROR = "FILEERROR"


class BrainOpsError(RuntimeError):
    """Erreur métier avec code + contexte structuré."""

    __slots__ = ("code", "ctx")

    def __init__(self, message: str, *, code: ErrCode, ctx: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.ctx: dict[str, Any] = dict(ctx or {})

    def __str__(self) -> str:  # utile dans les logs
        return f"{self.code}: {super().__str__()}"
