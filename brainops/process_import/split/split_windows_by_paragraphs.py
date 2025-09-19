"""
# process/split_windows_by_paragraphs.py
"""

from __future__ import annotations

import re


def split_windows_by_paragraphs(text: str, max_chars: int = 3800, overlap: int = 350) -> list[str]:
    """
    Découpe par paragraphes avec borne de caractères + overlap.
    """
    paras = [p for p in re.split(r"\n{2,}", text) if p.strip()]
    windows: list[str] = []
    buf = ""
    for p in paras:
        if not buf:
            buf = p.strip()
            continue
        if len(buf) + 2 + len(p) <= max_chars:
            buf = f"{buf}\n\n{p.strip()}"
        else:
            if windows:
                tail = windows[-1][-overlap:]
                buf = tail + buf  # léger chevauchement contextuel
            windows.append(buf)
            buf = p.strip()
    if buf:
        if windows:
            tail = windows[-1][-overlap:]
            buf = tail + buf
        windows.append(buf)
    return windows
