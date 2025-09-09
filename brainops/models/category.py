"""
# models/category.py
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class Category:
    """
    Miroir de la table obsidian_categories.
    """

    id: int | None = None
    name: str
    description: str | None = None
    prompt_name: str | None = None
    parent_id: int | None = None
