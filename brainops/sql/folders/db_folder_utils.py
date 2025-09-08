# sql/db_folder_utils.py
from __future__ import annotations

from typing import Iterable, Optional, Tuple

from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def is_folder_included(
    path: str,
    include_types: Optional[Iterable[str]] = None,
    exclude_types: Optional[Iterable[str]] = None,
    *,
    logger: LoggerProtocol | None = None,
) -> bool:
    """
    Vérifie si un dossier (par son `path`) doit être inclus selon des listes
    d'inclusions/exclusions basées sur `folder_type`.

    Args:
        path: Chemin complet (absolu POSIX) du dossier.
        include_types: Types explicitement autorisés (si fourni).
        exclude_types: Types explicitement exclus (si fourni).
        logger: Logger injecté (decorator).

    Returns:
        True si inclus, False sinon.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            row = safe_execute(
                cur,
                "SELECT folder_type FROM obsidian_folders WHERE path=%s",
                (path,),
                logger=logger,
            ).fetchone()
        if not row:
            logger.debug("[FILTER] Dossier introuvable en base: %s", path)
            return False

        folder_type: str = str(row[0])
        excl = set(exclude_types or ())
        incl = set(include_types or ())

        if excl and folder_type in excl:
            logger.debug("[FILTER] Exclu: %s (type=%s)", path, folder_type)
            return False
        if incl and folder_type not in incl:
            logger.debug("[FILTER] Non inclus: %s (type=%s)", path, folder_type)
            return False

        logger.debug("[FILTER] Inclus: %s (type=%s)", path, folder_type)
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[FILTER] is_folder_included(%s) erreur: %s", path, exc)
        return False
    finally:
        conn.close()


@with_child_logger
def get_path_from_classification(
    category_id: int,
    subcategory_id: Optional[int] = None,
    *,
    logger: LoggerProtocol | None = None,
) -> Optional[Tuple[int, str]]:
    """
    Récupère (folder_id, path) à partir d'une classification (catégorie / sous-catégorie).
    Priorité à la sous-catégorie si fournie.

    Returns:
        (id, path) si trouvé, sinon None.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            # Priorité à (cat, subcat)
            if subcategory_id is not None:
                row = safe_execute(
                    cur,
                    """
                    SELECT id, path
                      FROM obsidian_folders
                     WHERE category_id=%s AND subcategory_id=%s
                     LIMIT 1
                    """,
                    (category_id, subcategory_id),
                    logger=logger,
                ).fetchone()
                if row:
                    return int(row[0]), str(row[1])

            # Sinon catégorie seule (sans sous-catégorie)
            row = safe_execute(
                cur,
                """
                SELECT id, path
                  FROM obsidian_folders
                 WHERE category_id=%s AND subcategory_id IS NULL
                 LIMIT 1
                """,
                (category_id,),
                logger=logger,
            ).fetchone()
            if row:
                return int(row[0]), str(row[1])

        logger.warning(
            "[DB] Aucun dossier pour catégorie=%s, sous-catégorie=%s",
            category_id,
            subcategory_id,
        )
        return None
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "[DB] get_path_from_classification(cat=%s, subcat=%s) erreur: %s",
            category_id,
            subcategory_id,
            exc,
        )
        return None
    finally:
        conn.close()


@with_child_logger
def get_folder_type_by_path(
    path: str, *, logger: LoggerProtocol | None = None
) -> Optional[str]:
    """
    Retourne le `folder_type` pour un chemin donné, ou None si introuvable.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            row = safe_execute(
                cur,
                "SELECT folder_type FROM obsidian_folders WHERE path=%s",
                (path,),
                logger=logger,
            ).fetchone()
        return str(row[0]) if row else None
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[DB] get_folder_type_by_path(%s) erreur: %s", path, exc)
        return None
    finally:
        conn.close()


@with_child_logger
def get_folder_type_by_id(
    folder_id: int, *, logger: LoggerProtocol | None = None
) -> Optional[str]:
    """
    Retourne le `folder_type` pour un identifiant de dossier, ou None si introuvable.
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            row = safe_execute(
                cur,
                "SELECT folder_type FROM obsidian_folders WHERE id=%s",
                (folder_id,),
                logger=logger,
            ).fetchone()
        return str(row[0]) if row else None
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[DB] get_folder_type_by_id(%s) erreur: %s", folder_id, exc)
        return None
    finally:
        conn.close()
