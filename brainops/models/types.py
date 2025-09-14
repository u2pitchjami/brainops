"""
types.
"""

from __future__ import annotations

from pathlib import Path
import re

StrOrPath = str | Path

_YAML_FENCE = re.compile(r"^\ufeff?\s*---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n)?", re.DOTALL)  # gère BOM/CRLF/espaces
