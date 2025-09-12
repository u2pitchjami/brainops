"""
# sql/db_connection.py
"""

from __future__ import annotations

from mysql.connector import MySQLConnection, connect
from mysql.connector.errors import Error as MySQLError

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.utils.config import DB_CONFIG
from brainops.utils.logger import LoggerProtocol, ensure_logger


def get_db_connection(
    logger: LoggerProtocol | None = None,
) -> MySQLConnection:
    """
    Ouvre une connexion MySQL à partir de la config centralisée (.env chargée par utils.config).

    Retourne None si la connexion échoue.
    """
    logger = ensure_logger(logger, __name__)
    try:
        conn = connect(**DB_CONFIG)
    except MySQLError as exc:
        raise BrainOpsError("Erreur de connection DB", code=ErrCode.DB, ctx={"db": "db"}) from exc
    return conn
