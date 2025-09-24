# brainops/sql/db_utils.py

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CursorProtocol(Protocol):
    """
    Protocole minimal compatible avec les curseurs pymysql, utilisé pour typage mypy des fonctions SQL génériques.
    """

    rowcount: int | None
    lastrowid: int | None

    # Contexte "with"
    def __enter__(self) -> CursorProtocol: ...
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...

    # Exécution de requêtes
    def execute(
        self,
        operation: str,
        params: Sequence[Any] | Mapping[str, Any] | None = ...,
    ) -> None: ...

    def nextset(self) -> bool | None: ...

    # Récupération
    def fetchone(self) -> tuple[Any, ...] | None: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def close(self) -> None: ...
