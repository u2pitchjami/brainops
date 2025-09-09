"""# models/classification.py"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True, kw_only=True)
class ClassificationResult:
    """
    Résultat de la classification d'une note.
    """

    note_type: str  # "Category/Subcategory" normalisé
    category_id: Optional[int]
    subcategory_id: Optional[int]
    folder_id: Optional[int]
    dest_folder: str  # dossier cible (absolu POSIX)
    status: str = "archive"  # statut choisi pour l'import normal
