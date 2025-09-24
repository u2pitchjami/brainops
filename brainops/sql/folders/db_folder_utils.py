"""
# sql/db_folder_utils.py
"""

from __future__ import annotations

from brainops.io.paths import exists
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.db_connection import get_cursor, get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def exist_vault_db(folderpath: str, logger: LoggerProtocol | None = None) -> bool:
    """
    exist_vault_db _summary_
    """
    logger = ensure_logger(logger, __name__)
    db = is_folder_exist(folderpath=folderpath, logger=logger)
    if not db:
        return False
    vault = exists(folderpath)
    if not vault:
        return False
    return True


@with_child_logger
def is_folder_exist(folderpath: str, logger: LoggerProtocol | None = None) -> bool:
    """
    is_folder_exist _summary_

    teste la présence d'un dossier dans la base

    Args:
        folderpath (str): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        bool: true si existe sinon false
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[is_folder_exist] entrée is_folder_exist %s", folderpath)
    conn = get_db_connection(logger=logger)
    try:
        with get_cursor(conn) as cur:
            row = safe_execute(
                cur,
                "SELECT id FROM obsidian_folders WHERE path=%s",
                (folderpath,),
                logger=logger,
            ).fetchone()
            if row:
                return True
            else:
                return False
    except Exception as exc:
        raise BrainOpsError("Erreur DB", code=ErrCode.DB, ctx={"folder": folderpath}) from exc
    finally:
        conn.close()


@with_child_logger
def get_folder_path_by_id(folder_id: int, *, logger: LoggerProtocol | None = None) -> str:
    """
    Retourne le `path` pour un identifiant de dossier, ou None si introuvable.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    try:
        with get_cursor(conn) as cur:
            row = safe_execute(
                cur,
                "SELECT path FROM obsidian_folders WHERE id=%s",
                (folder_id,),
                logger=logger,
            ).fetchone()
        if row is not None:
            return str(row[0])
        raise BrainOpsError(f"Aucun Path pour le folder id {folder_id}", code=ErrCode.DB, ctx={"folder_id": folder_id})
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[DB] get_folder_type_by_path(%s) erreur: %s", folder_id, exc)
        raise BrainOpsError(
            f"Aucun Path pour le folder id {folder_id}", code=ErrCode.DB, ctx={"folder_id": folder_id}
        ) from exc
    finally:
        conn.close()
