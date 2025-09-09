"""# process/folders_context.py"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from brainops.models.folders import Folder, FolderType
from brainops.process_import.utils.paths import get_relative_parts, path_is_inside
from brainops.sql.categs.db_categ_utils import (
    get_or_create_category,
    get_or_create_subcategory,
)
from brainops.sql.get_linked.db_get_linked_folders_utils import (
    get_category_context_from_folder,
    get_folder_id,
)
from brainops.utils.config import Z_STORAGE_PATH
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


def normalize_folder_path(p: str | Path) -> str:
    """Chemin absolu POSIX (stable multi-OS)."""
    return Path(str(p)).expanduser().resolve().as_posix()


def _detect_folder_type(path: str) -> FolderType:
    """Détection par règles simples sur le chemin complet (fallback) → Enum."""
    lower = path.lower()
    if "/archives" in lower or lower.endswith("/archives"):
        return FolderType.ARCHIVE
    if "/notes/z_storage/" in lower:
        return FolderType.STORAGE
    if "/notes/personnal/" in lower:
        return FolderType.PERSONNAL
    if "/notes/projects/" in lower:
        return FolderType.PROJECT
    if "/notes/z_technical/" in lower:
        return FolderType.TECHNICAL
    return FolderType.TECHNICAL


@dataclass(frozen=True, slots=True)
class FolderContext:
    """Contexte DB & logique pour un dossier."""

    # arborescence
    parent_path: Optional[str]
    parent_id: Optional[int]
    # catégories
    category_id: Optional[int]
    subcategory_id: Optional[int]
    category_name: Optional[str]
    subcategory_name: Optional[str]
    # type logique
    folder_type: FolderType


@with_child_logger
def resolve_folder_context(
    path: str | Path, logger: LoggerProtocol | None = None
) -> FolderContext:
    """
    Calcule le contexte d'un dossier (parent, catégories, type).
    Réutilisable par update_folder()
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] resolve_folder_context(%s)", path)
    p_str = normalize_folder_path(path)

    # parent
    p = Path(p_str)
    parent_path = p.parent.as_posix() if p.parent != p else None
    logger.debug("[DEBUG] parent_path: %s", parent_path)
    parent_id = get_folder_id(parent_path, logger=logger) if parent_path else None
    logger.debug("[DEBUG] parent_id: %s", parent_id)

    # catégories
    cat_id, subcat_id, cat_name, subcat_name = get_category_context_from_folder(
        p_str, logger=logger
    )
    # type
    ftype = _detect_folder_type(p_str)
    logger.debug("[DEBUG] initial folder_type: %s", ftype)
    if path_is_inside(Z_STORAGE_PATH, p_str):
        parts = get_relative_parts(p_str, Z_STORAGE_PATH, logger=logger) or []
        if len(parts) >= 3 and parts[2].lower() == "archives":
            ftype = FolderType.ARCHIVE

    return FolderContext(
        parent_path=parent_path,
        parent_id=parent_id,
        category_id=cat_id,
        subcategory_id=subcat_id,
        category_name=cat_name,
        subcategory_name=subcat_name,
        folder_type=ftype,
    )


@with_child_logger
def add_folder_context(
    path: str | Path, logger: LoggerProtocol | None = None
) -> FolderContext:
    """
    Calcule le contexte d'un dossier (parent, catégories, type).
    Réutilisable par add_folder().
    """
    logger = ensure_logger(logger, __name__)
    category, subcategory, category_id, subcategory_id = (
        None,
        None,
        None,
        None,
    )
    logger.debug("[DEBUG] resolve_folder_context(%s)", path)
    p_str = normalize_folder_path(path)

    # parent
    p = Path(p_str)
    parent_path = p.parent.as_posix() if p.parent != p else None
    parent_id = get_folder_id(parent_path, logger=logger) if parent_path else None

    # type
    ftype = _detect_folder_type(p_str)
    if path_is_inside(Z_STORAGE_PATH, p_str):
        relative_parts = get_relative_parts(p_str, Z_STORAGE_PATH, logger=logger) or []
        if len(relative_parts) == 1:
            category = relative_parts[0]
        elif len(relative_parts) == 2:
            category, subcategory = relative_parts
        elif len(relative_parts) == 3 and relative_parts[2].lower() == "archives":
            category, subcategory = relative_parts[0], relative_parts[1]
            ftype = FolderType.ARCHIVE

        if category:
            category_id = get_or_create_category(category, logger=logger)
            logger.debug(f"[DEBUG] category_id: {category_id} {category}")
        if subcategory:
            subcategory_id = get_or_create_subcategory(
                subcategory, category_id, logger=logger
            )
            logger.debug(f"[DEBUG] subcategory_id: {subcategory_id} {subcategory}")

    return FolderContext(
        parent_path=parent_path,
        parent_id=parent_id,
        category_id=category_id,
        subcategory_id=subcategory_id,
        category_name=category,
        subcategory_name=subcategory,
        folder_type=ftype,
    )


@with_child_logger
def build_folder(
    path: str | Path,
    *,
    override_type: Optional[FolderType] = None,
    logger: LoggerProtocol | None = None,
) -> Folder:
    """
    build_folder _summary_

    _extended_summary_

    Args:
        path (str | Path): _description_
        override_type (Optional[FolderType], optional): _description_. Defaults to None.

    Returns:
        Folder: _description_
    """
    logger = ensure_logger(logger, __name__)
    p = normalize_folder_path(path)
    name = Path(p).name
    parent_path = Path(p).parent.as_posix() if Path(p).parent != Path(p) else None
    parent_id = get_folder_id(parent_path, logger=logger) if parent_path else None

    cat_id, subcat_id, _cat_name, _subcat_name = get_category_context_from_folder(
        p, logger=logger
    )

    ftype = override_type or _detect_folder_type(p)
    if path_is_inside(Z_STORAGE_PATH, p):
        parts = get_relative_parts(p, Z_STORAGE_PATH, logger=logger) or []
        if len(parts) >= 3 and parts[2].lower() == "archives":
            ftype = FolderType.ARCHIVE

    return Folder(
        name=name,
        path=p,
        folder_type=ftype,  # << Enum garanti
        parent_id=parent_id,
        category_id=cat_id,
        subcategory_id=subcat_id,
    )
