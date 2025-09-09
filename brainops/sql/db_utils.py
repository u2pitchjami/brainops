"""# sql/db_utils.py"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence

from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


class CursorProtocol(Protocol):
    """Contrat minimal pour un curseur MySQL utilisé ici."""

    def nextset(
        self,
    ) -> Optional[bool]:  # True s'il reste un jeu de résultats, sinon None/False
        """
        nextset _summary_

        _extended_summary_

        Returns:
            Optional[bool]: _description_
        """
        ...

    def execute(
        self, operation: str, params: Optional[Sequence[Any] | Mapping[str, Any]] = ...
    ) -> None:
        """
        execute _summary_

        _extended_summary_

        Args:
            operation (str): _description_
            params (Optional[Sequence[Any]  |  Mapping[str, Any]], optional): _description_. Defaults to ....
        """
        ...


@with_child_logger
def flush_cursor(cursor: CursorProtocol, logger: LoggerProtocol | None = None) -> None:
    """
    Vide proprement le curseur MySQL (utile pour éviter
    les erreurs 'Unread result found' lors d'appels successifs).

    On itère tant qu'il reste des jeux de résultats non consommés.
    """
    logger = ensure_logger(logger, __name__)
    try:
        while cursor.nextset():
            pass
    except Exception as exc:  # noqa: BLE001
        # On ignore volontairement : certains drivers lèvent quand il n'y a rien à nettoyer.
        logger.debug("flush_cursor: ignore exception while draining cursor: %s", exc)


@with_child_logger
def safe_execute(
    cursor: CursorProtocol,
    query: str,
    params: Optional[Sequence[Any] | Mapping[str, Any]] = None,
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
    flush_cursor(cursor, logger=logger)
    if params is not None:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    return cursor
