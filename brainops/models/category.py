"""# models/category.py"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True, kw_only=True)
class Category:
    """Miroir de la table obsidian_categories."""

    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    prompt_name: Optional[str] = None
    parent_id: Optional[int] = None
