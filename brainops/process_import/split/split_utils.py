"""
process_import.utils.large_note.
"""

from __future__ import annotations

from collections.abc import Sequence
import re


def split_large_note(content: str, max_words: int = 1000) -> list[str]:
    """
    Découpe une note en blocs de taille optimale (max_words).
    """
    words = content.split()
    blocks: list[str] = []
    current_block: list[str] = []

    for word in words:
        current_block.append(word)
        if len(current_block) >= max_words:
            blocks.append(" ".join(current_block))
            current_block = []

    if current_block:
        blocks.append(" ".join(current_block))
    return blocks


def split_large_note_by_titles(content: str) -> list[str]:
    """
    Découpe en blocs basés sur les titres (#, ##, ###), gère l'intro avant le 1er titre.

    Chaque bloc contient le titre et son contenu.
    """
    title_pattern = r"(?m)^(\#{1,3})\s+.*$"
    matches = list(re.finditer(title_pattern, content))

    blocks: list[str] = []
    if matches:
        if matches[0].start() > 0:
            intro = content[: matches[0].start()].strip()
            if intro:
                blocks.append("## **Introduction**\n\n" + intro)

        for i, match in enumerate(matches):
            title = match.group().strip()
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos].strip()
            blocks.append(f"{title}\n{section_content}")
    else:
        intro = content.strip()
        if intro:
            blocks.append("## **Introduction**\n\n" + intro)

    return blocks


def split_large_note_by_titles_and_words(content: str, word_limit: int = 1000) -> list[str]:
    """
    Découpe par titres, puis regroupe en paquets ≤ word_limit mots, sans briser les sections.
    """
    title_pattern = r"(?m)^(\#{1,5})\s+.*$"
    matches = list(re.finditer(title_pattern, content))

    blocks: list[str] = []
    temp_block: list[str] = []
    word_count = 0

    def add_block() -> None:
        if temp_block:
            blocks.append("\n\n".join(temp_block))
            temp_block.clear()

    if matches:
        if matches[0].start() > 0:
            intro = content[: matches[0].start()].strip()
            if intro:
                temp_block.append("## **Introduction**\n\n" + intro)
                word_count += len(intro.split())

        for i, match in enumerate(matches):
            title = match.group().strip()
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos].strip()
            section_words = len(section_content.split())

            if word_count + section_words > word_limit:
                add_block()
                word_count = 0

            temp_block.append(f"{title}\n{section_content}")
            word_count += section_words

        add_block()
    else:
        intro = content.strip()
        if intro:
            blocks.append("## **Introduction**\n" + intro)

    return blocks


def ensure_titles_in_blocks(blocks: Sequence[str], default_title: str = "# Introduction") -> list[str]:
    """
    S'assure que chaque bloc commence par un titre Markdown ; sinon en ajoute un.
    """
    processed: list[str] = []
    for i, block in enumerate(blocks):
        b = (block or "").strip()
        if not b.startswith("#"):
            title = default_title if i == 0 else f"# Section {i + 1}"
            b = f"{title}\n{b}"
        processed.append(b)
    return processed
