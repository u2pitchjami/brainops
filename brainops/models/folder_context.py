"""
# models/folder.py
"""

from __future__ import annotations

from dataclasses import dataclass

from brainops.models.folders import FolderType


@dataclass(frozen=True, slots=True)
class FolderContext:
    """
    Contexte DB & logique pour un dossier.
    """

    # arborescence
    parent_path: str | None
    parent_id: int | None
    # catégories
    category_id: int | None
    subcategory_id: int | None
    category_name: str | None
    subcategory_name: str | None
    # type logique
    folder_type: FolderType
