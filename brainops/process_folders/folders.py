# process/folders.py
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from brainops.models.folders import Folder, FolderType
from brainops.process_folders.folders_context import (
    _detect_folder_type,
    add_folder_context,
    normalize_folder_path,
    resolve_folder_context,
)
from brainops.process_import.utils.paths import get_relative_parts, path_is_inside
from brainops.sql.categs.db_categ_utils import (
    get_or_create_category,
    get_or_create_subcategory,
    remove_unused_category,
)
from brainops.sql.folders.db_folders import (
    add_folder_from_model,
    update_folder_from_model,
)
from brainops.sql.get_linked.db_get_linked_data import get_folder_linked_data
from brainops.sql.get_linked.db_get_linked_folders_utils import (
    get_category_context_from_folder,
    get_folder_id,
)
from brainops.utils.config import Z_STORAGE_PATH
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger

FolderType = Literal["storage", "archive", "technical", "project", "personnal"]


def _norm_path(p: str | Path) -> Path:
    """Normalise un chemin en Path absolu, séparateurs POSIX pour la DB."""
    return Path(str(p)).expanduser().resolve()


def _is_ignored(p: str | Path) -> bool:
    s = str(p).lower()
    return "untitled" in s or any(part.startswith(".") for part in Path(s).parts)


@with_child_logger
def add_folder(
    folder_path: str | Path,
    folder_type_hint: str,
    *,
    logger: LoggerProtocol | None = None,
) -> Optional[int]:
    logger = ensure_logger(logger, __name__)
    logger.debug("add_folder called")
    p_str = normalize_folder_path(folder_path)
    logger.debug(f"Normalized path: {p_str}")

    # ignore cachés/temp
    if (
        "untitled" in Path(p_str).name.lower()
        or "sans titre" in Path(p_str).name.lower()
    ):
        logger.debug(f"[DEBUG] Dossier ignoré (temp/caché) : {p_str}")
        logger.info("[FOLDER] Dossier ignoré (temp/caché) : %s", p_str)
        return None

    ctx = add_folder_context(p_str, logger=logger)
    # Remarque: folder_type_hint peut rester si tu veux un override manuel.
    ftype = ctx.folder_type

    new_folder = Folder(
        id=None,  # laissé à None, il sera rempli par la DB
        name=Path(p_str).name,
        path=p_str,
        folder_type=ftype,
        parent_id=ctx.parent_id,
        category_id=ctx.category_id,
        subcategory_id=ctx.subcategory_id,
    )

    return add_folder_from_model(new_folder, logger=logger)


@with_child_logger
def update_folder(
    old_path: str | Path, new_path: str | Path, *, logger: LoggerProtocol | None = None
) -> None:
    logger = ensure_logger(logger, __name__)

    old_p = normalize_folder_path(old_path)
    new_p = normalize_folder_path(new_path)

    folder = get_folder_linked_data(old_p, "folder", logger=logger)
    if "error" in folder:
        logger.warning("[FOLDER] Dossier introuvable: %s", old_p)
        return

    folder_id: int = folder["id"]
    old_cat_id: Optional[int] = folder.get("category_id")
    old_subcat_id: Optional[int] = folder.get("subcategory_id")

    ctx = add_folder_context(new_p)

    folder = Folder(
        id=folder_id,
        name=Path(new_p).name,
        path=new_p,
        folder_type=ctx.folder_type,  # ⚠️ Enum FolderType, pas une str
        parent_id=ctx.parent_id,
        category_id=ctx.category_id,
        subcategory_id=ctx.subcategory_id,
        logger=logger,
    )
    update_folder_from_model(folder_id, folder, logger=logger)

    if old_cat_id and old_cat_id != ctx.category_id:
        remove_unused_category(old_cat_id, logger=logger)
    if old_subcat_id and old_subcat_id != ctx.subcategory_id:
        remove_unused_category(old_subcat_id, logger=logger)
