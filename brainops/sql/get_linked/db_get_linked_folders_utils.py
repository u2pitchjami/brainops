"""
# sql/db_get_linked_folders_utils.py
"""

from __future__ import annotations

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.folders.db_folder_utils import is_folder_exist
from brainops.sql.get_linked.db_get_linked_data import get_folder_linked_data
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def get_folder_id(folder_path: str, *, logger: LoggerProtocol | None = None) -> int:
    """
    Retourne l'identifiant du dossier pour un chemin donné.

    Lève BrainOpsError si introuvable / invalide.  # <- doc alignée
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[get_folder_id] entrée get_folder_id")
    try:
        exist = is_folder_exist(folderpath=folder_path, logger=logger)
        logger.debug("[get_folder_id] exist: %s", exist)
        if not exist:
            logger.debug("[get_folder_id] not exist")
            from brainops.process_folders.folders import add_folder

            logger.warning("[FOLDER] 🚨 Dossier absent de la DB")
            new_id = add_folder(folder_path=folder_path, logger=logger)  # <- nom différent
            if not new_id:
                raise BrainOpsError("Récup FolderID KO", code=ErrCode.DB, ctx={"folder": folder_path})
            return int(new_id)
        logger.debug("[get_folder_id] exist")
        folder = get_folder_linked_data(folder_path, "folder", logger=logger)

        if isinstance(folder, dict) and "error" not in folder:
            raw_id = folder.get("id")
            if raw_id is None:
                raise BrainOpsError("FolderID manquant", code=ErrCode.DB, ctx={"folder": folder_path})
            try:
                return int(raw_id)
            except (TypeError, ValueError) as exc:
                raise BrainOpsError(
                    "FolderID invalide",
                    code=ErrCode.DB,
                    ctx={"folder": folder_path, "id": raw_id},
                ) from exc

        raise BrainOpsError("Récup FolderID KO", code=ErrCode.DB, ctx={"folder": folder_path})

    except BrainOpsError:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        # filet : on remonte proprement
        raise BrainOpsError(
            "Erreur inattendue get_folder_id",
            code=ErrCode.DB,
            ctx={"folder": folder_path},
        ) from exc


@with_child_logger
def get_category_context_from_folder(
    folder_path: str, *, logger: LoggerProtocol | None = None
) -> tuple[int | None, int | None, str, str]:
    """
    Retourne (category_id, subcategory_id, category_name, subcategory_name) pour un chemin de dossier.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] get_category_context_from_folder(%s)", folder_path)
    try:
        category = get_folder_linked_data(folder_path, "category", logger=logger)
        subcategory = get_folder_linked_data(folder_path, "subcategory", logger=logger)

        category_id = int(category["id"]) if isinstance(category, dict) and "id" in category else None
        category_name = str(category["name"]) if isinstance(category, dict) and "name" in category else ""

        subcategory_id = int(subcategory["id"]) if isinstance(subcategory, dict) and "id" in subcategory else None
        subcategory_name = str(subcategory["name"]) if isinstance(subcategory, dict) and "name" in subcategory else ""

        logger.debug(
            "[DEBUG] get_category_context_from_folder(%s) -> cat(%s,%s) sub(%s,%s)",
            folder_path,
            category_id,
            category_name,
            subcategory_id,
            subcategory_name,
        )
        return category_id, subcategory_id, category_name, subcategory_name
    except Exception as exc:  # pylint: disable=broad-except
        raise BrainOpsError(
            "Récup categ context KO",
            code=ErrCode.DB,
            ctx={"folder_path": folder_path},
        ) from exc
