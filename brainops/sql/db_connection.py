"""# sql/db_connection.py"""

from __future__ import annotations

from typing import Optional

from mysql.connector import MySQLConnection, connect
from mysql.connector.errors import Error as MySQLError

from brainops.utils.config import DB_CONFIG
from brainops.utils.logger import LoggerProtocol, ensure_logger


def get_db_connection(
    logger: LoggerProtocol | None = None,
) -> Optional[MySQLConnection]:
    """
    Ouvre une connexion MySQL à partir de la config centralisée (.env chargée par utils.config).
    Retourne None si la connexion échoue.
    """
    logger = ensure_logger(logger, __name__)
    try:
        conn = connect(**DB_CONFIG)
        return conn
    except MySQLError as err:  # noqa: TRY003
        logger.error("❌ MySQL connection error: %s", err)
        return None
