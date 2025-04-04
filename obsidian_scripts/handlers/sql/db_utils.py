from logger_setup import setup_logger
import logging
from handlers.sql.db_connection import get_db_connection

setup_logger("db_utils", logging.DEBUG)
logger = logging.getLogger("db_utils")


def flush_cursor(cursor):
    """Vide proprement le curseur MySQL (utile pour éviter les erreurs 'Unread result found')."""
    try:
        while cursor.nextset():
            pass
    except Exception:
        pass


def safe_execute(cursor, query, params=None):
    """Flush le curseur avant d’exécuter une nouvelle requête SQL."""
    flush_cursor(cursor)
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    return cursor
