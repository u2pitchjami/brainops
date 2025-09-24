"""
# models/classification.py
"""

from __future__ import annotations

from dataclasses import dataclass


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
    status: str = "archive"  # statut choisi pour l'import normal
