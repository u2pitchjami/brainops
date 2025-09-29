"""
# models/classification.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from brainops.models.folders import FolderType


@dataclass(slots=True, kw_only=True)
class ClassificationResult:
    """
    Résultat de la classification d'une note.
    """

    category_name: str  # "Category/Subcategory" normalisé
    category_id: int
    subcategory_name: str | None
    subcategory_id: int | None
    folder_id: int
    dest_folder: str  # dossier cible (absolu POSIX)
    status: FolderType  # statut choisi pour l'import normal

    def to_yaml_dict(self) -> dict[str, Any]:
        return {
            "category": self.category_name,
            "subcategory": self.subcategory_name,
            "status": str(self.status),  # utilise __str__ de FolderType → "synthesis"
        }
