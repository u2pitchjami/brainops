from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NoteMetadata:
    title: str = ""
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    category: str = ""
    subcategory: str = ""
    created: str | None = None
    last_modified: str | None = None
    source: str = ""
    author: str = ""
    status: str = "draft"
    project: str = ""

    # ------------------------- Constructeurs --------------------------------

    @classmethod
    def from_yaml_dict(cls, data: Mapping[str, Any] | None) -> NoteMetadata:
        """
        Construit un NoteMetadata à partir d'un dict YAML.
        - Tolère data == None ou data non-mapping (ex: str) -> renvoie des valeurs par défaut.
        - Normalise 'subcategory' / 'sub category'.
        - Normalise 'tags' (liste attendue ; si str CSV, split).
        """
        if not isinstance(data, Mapping):
            # data peut être None, str, etc. On sécurise.
            return cls()

        def _as_str(x: Any, default: str = "") -> str:
            return default if x is None else str(x)

        # subcategory: alias
        subcat = data.get("subcategory", data.get("sub category", ""))

        # tags: accepter list[str] ou str "tag1, tag2"
        raw_tags = data.get("tags", [])
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        else:
            tags = []

        return cls(
            title=_as_str(data.get("title")),
            tags=tags,
            summary=_as_str(data.get("summary")),
            category=_as_str(data.get("category")),
            subcategory=_as_str(subcat),
            created=_as_str(data.get("created")) or None,
            last_modified=_as_str(data.get("last_modified")) or None,
            source=_as_str(data.get("source")),
            author=_as_str(data.get("author")),
            status=_as_str(data.get("status") or "draft"),
            project=_as_str(data.get("project")),
        )

    @classmethod
    def from_db_dict(cls, data: dict[str, str | int | None]) -> NoteMetadata:
        """
        Construit un objet à partir des champs DB.
        """
        return cls(
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            source=str(data.get("source", "")),
            author=str(data.get("author", "")),
            project=str(data.get("project", "")),
            status=str(data.get("status", "draft")),
            created=str(data.get("created_at", "")) or None,
        )

    @classmethod
    def merge(cls, *sources: NoteMetadata) -> NoteMetadata:
        """
        Fusionne plusieurs objets Metadata : priorité à gauche.
        """
        result = cls()
        for source in reversed(sources):
            for field_name in result.__dataclass_fields__:
                val = getattr(source, field_name)
                if val:
                    setattr(result, field_name, val)
        return result

    # ------------------------- Exporteurs -----------------------------------

    def to_yaml_dict(self) -> dict[str, str | list[str]]:
        return {
            "title": self.title,
            "tags": [str(t).replace(" ", "_") for t in self.tags],
            "summary": self.summary.strip(),
            "category": self.category,
            "sub category": self.subcategory,
            "created": self.created or "",
            "last_modified": self.last_modified or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": self.source,
            "author": self.author,
            "status": self.status,
            "project": self.project,
        }

    def to_dict(self) -> dict[str, str | list[str]]:
        """
        Export générique (ex: DB, API).
        """
        return self.to_yaml_dict()
