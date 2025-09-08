# models/note.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple


@dataclass(slots=True, kw_only=True)
class Note:
    """
    Miroir de la table `obsidian_notes`.
    Champs transients (non persistés) indiqués en commentaires.
    """

    id: Optional[int] = None
    parent_id: Optional[int] = None

    title: str
    file_path: str
    folder_id: int

    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None

    status: Optional[str] = None
    summary: Optional[str] = None
    source: Optional[str] = None
    author: Optional[str] = None
    project: Optional[str] = None

    created_at: Optional[date] = None
    modified_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None  # gérée par DB (timestamp ON UPDATE)

    word_count: int = 0
    content_hash: Optional[str] = None
    source_hash: Optional[str] = None
    lang: Optional[str] = None  # 3 lettres (ex: "fr", "en")

    # ---- transients (non stockés) ---------------------------------------------
    name: str = field(init=False, repr=False)  # basename dérivé de file_path
    ext: str = field(init=False, repr=False)  # extension dérivée

    def __post_init__(self) -> None:
        # Normaliser le chemin en absolu POSIX
        p = Path(self.file_path).expanduser().resolve()
        self.file_path = p.as_posix()
        self.name = p.name
        self.ext = p.suffix.lower().lstrip(".")

        # Langue sur 3 chars (si fournie)
        if self.lang:
            self.lang = self.lang.strip().lower()[:3]

        # Sécurité: word_count >= 0
        if self.word_count is None or self.word_count < 0:
            self.word_count = 0

    # ------------------- Mapping DB --------------------------------------------

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Note":
        """
        Construit une Note depuis un DictCursor (SELECT ...).
        Les clés doivent correspondre aux noms de colonnes SQL.
        """
        return cls(
            id=row.get("id"),
            parent_id=row.get("parent_id"),
            title=row["title"],
            file_path=row["file_path"],
            folder_id=row["folder_id"],
            category_id=row.get("category_id"),
            subcategory_id=row.get("subcategory_id"),
            status=row.get("status"),
            summary=row.get("summary"),
            source=row.get("source"),
            author=row.get("author"),
            project=row.get("project"),
            created_at=row.get("created_at"),
            modified_at=row.get("modified_at"),
            updated_at=row.get("updated_at"),
            word_count=row.get("word_count", 0) or 0,
            content_hash=row.get("content_hash"),
            source_hash=row.get("source_hash"),
            lang=row.get("lang"),
        )

    def to_upsert_params(self) -> Tuple[Any, ...]:
        """
        Ordre exactement aligné sur l'INSERT ci-dessous (DAO).
        """
        return (
            self.parent_id,
            self.title,
            self.file_path,
            self.folder_id,
            self.category_id,
            self.subcategory_id,
            self.status,
            self.summary,
            self.source,
            self.author,
            self.project,
            self.created_at,
            self.modified_at,
            self.word_count,
            self.content_hash,
            self.source_hash,
            self.lang,
        )
