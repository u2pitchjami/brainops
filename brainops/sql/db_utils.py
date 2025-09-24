"""
# sql/db_utils.py
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from brainops.models.cursor_protocol import CursorProtocol
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger

Row = tuple[Any, ...]  # ou dict[str, Any] si DictCursor
C = TypeVar("C", bound="CursorProtocol")


# class CursorProtocol(Protocol):
#     # Attributs DB-API fréquents
#     rowcount: int | None

#     # Exécution
#     def execute(
#         self,
#         operation: str,
#         params: Sequence[Any] | Mapping[str, Any] | None = ...,
#     ) -> None: ...
#     def nextset(self) -> bool | None: ...

#     # Récupération
#     def fetchone(self) -> Row | None: ...
#     def fetchall(self) -> list[Row]: ...
#     def close(self) -> None: ...


@with_child_logger
def flush_cursor(cursor: CursorProtocol, logger: LoggerProtocol | None = None) -> None:
    """
    Vide proprement le curseur MySQL (utile pour éviter les erreurs 'Unread result found' lors d'appels successifs).

    On itère tant qu'il reste des jeux de résultats non consommés.
    """
    logger = ensure_logger(logger, __name__)
    try:
        while cursor.nextset():
            pass
    except Exception as exc:
        # On ignore volontairement : certains drivers lèvent quand il n'y a rien à nettoyer.
        logger.debug("flush_cursor: ignore exception while draining cursor: %s", exc)


@with_child_logger
def safe_execute(
    cursor: CursorProtocol,
    query: str,
    params: Sequence[Any] | Mapping[str, Any] | None = None,
    logger: LoggerProtocol | None = None,
) -> CursorProtocol:
    """
    Exécute une requête après avoir flush le curseur.

    Args:
        cursor: curseur DB conforme au protocole minimal.
        query: requête SQL.
        params: paramètres positionnels (Sequence) ou nommés (Mapping).

    Returns:
        Le même curseur (chaînable avec .fetchone() / .fetchall()).
    """
    logger = ensure_logger(logger, __name__)
    try:
        flush_cursor(cursor, logger=logger)
        if params is not None:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor
    except Exception as exc:
        raise BrainOpsError("Erreur requête DB", code=ErrCode.DB, ctx={"query": query}) from exc
