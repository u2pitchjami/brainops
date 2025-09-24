"""
# process/folders.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.io.paths import to_abs
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.folders import Folder
from brainops.process_folders.folders_context import (
    add_folder_context,
    normalize_folder_path,
)
from brainops.sql.categs.db_categ_utils import remove_unused_category
from brainops.sql.folders.db_folders import (
    add_folder_from_model,
    update_folder_from_model,
)
from brainops.sql.get_linked.db_get_linked_data import get_folder_linked_data
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def ensure_folder_exists(folder_path: str | Path, *, logger: LoggerProtocol | None = None) -> bool:
    """
    Crée le dossier physiquement (mkdir -p) si besoin.
    """
    logger = ensure_logger(logger, __name__)
    folder = Path(to_abs(str(folder_path)))
    if folder.exists():
        logger.debug("[FOLDER] déjà présent : %s", folder)
        return True
    try:
        folder.mkdir(parents=False, exist_ok=True)
        addfold = add_folder(folder_path=folder_path, logger=logger)
        if addfold is not None:
            return True
        return False
    except Exception as exc:
        raise BrainOpsError("folder_exist KO", code=ErrCode.UNEXPECTED, ctx={"folder_path": folder_path}) from exc
    logger.info("[FOLDER] créé : %s", folder)


@with_child_logger
def add_folder(
    folder_path: str | Path,
    logger: LoggerProtocol | None = None,
) -> int:
    """
    add_folder _summary_

    _extended_summary_

    Args:
        folder_path (str | Path): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        Optional[int]: _description_
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("add_folder called folder_path %s", folder_path)
    try:
        p_str = normalize_folder_path(folder_path)
        logger.debug(f"Normalized path: {p_str}")

        # ignore cachés/temp
        if "untitled" in Path(p_str).name.lower() or "sans titre" in Path(p_str).name.lower():
            logger.debug(f"[DEBUG] Dossier ignoré (temp/caché) : {p_str}")
            raise BrainOpsError("dossier ignoré (temp/caché)", code=ErrCode.UNEXPECTED, ctx={"folder": folder_path})

        ctx = add_folder_context(p_str, logger=logger)
        # Remarque: folder_type_hint peut rester si tu veux un override manuel.
        logger.debug(f"[DEBUG] ctx.folder_type : {ctx.folder_type}")

        new_folder = Folder(
            id=None,  # laissé à None, il sera rempli par la DB
            name=Path(p_str).name,
            path=p_str,
            folder_type=ctx.folder_type,
            parent_id=ctx.parent_id,
            category_id=ctx.category_id,
            subcategory_id=ctx.subcategory_id,
        )

        folder_id = add_folder_from_model(new_folder, logger=logger)
        logger.debug(f"folder_id : {folder_id}")
        ensure_folder_exists(folder_path=p_str, logger=logger)
        return folder_id
    except Exception as exc:  # pylint: disable=broad-except
        raise BrainOpsError(
            "KO création folder",
            code=ErrCode.DB,
            ctx={"path": folder_path},
        ) from exc


@with_child_logger
def update_folder(old_path: str | Path, new_path: str | Path, *, logger: LoggerProtocol | None = None) -> None:
    """
    update_folder _summary_

    _extended_summary_

    Args:
        old_path (str | Path): _description_
        new_path (str | Path): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.
    """
    logger = ensure_logger(logger, __name__)

    old_p = normalize_folder_path(old_path)
    new_p = normalize_folder_path(new_path)

    folder = get_folder_linked_data(old_p, "folder", logger=logger)
    if "error" in folder:
        logger.warning("[FOLDER] Dossier introuvable: %s", old_p)
        return

    folder_id: int = folder["id"]
    old_cat_id: int | None = folder.get("category_id")
    old_subcat_id: int | None = folder.get("subcategory_id")

    ctx = add_folder_context(new_p)

    update = Folder(
        id=folder_id,
        name=Path(new_p).name,
        path=new_p,
        folder_type=ctx.folder_type,  # ⚠️ Enum FolderType, pas une str
        parent_id=ctx.parent_id,
        category_id=ctx.category_id,
        subcategory_id=ctx.subcategory_id,
    )
    update_folder_from_model(folder_id, update, logger=logger)

    if old_cat_id and old_cat_id != ctx.category_id:
        remove_unused_category(old_cat_id, logger=logger)
    if old_subcat_id and old_subcat_id != ctx.subcategory_id:
        remove_unused_category(old_subcat_id, logger=logger)
