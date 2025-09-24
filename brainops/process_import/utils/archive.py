"""
# process/divers.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.io.paths import exists


def build_archive_path(original_path: str | Path, original_name: str, suffix: str) -> Path:
    """
    Construit le chemin d'archive : <dir>/Archives/<stem> (archive).md.
    """
    p = Path(original_path)
    archive_dir = p / "Archives"
    archive_name = f"{original_name} (archive){suffix}"
    archive_path = archive_dir / archive_name
    # Résolution des collisions
    counter = 1
    while exists(archive_path):
        new_name = f"{original_name} (archive)_{counter}{suffix}"
        archive_path = archive_dir / new_name
        counter += 1
    return archive_path


def build_synthesis_path(original_path: str | Path, original_name: str, suffix: str) -> Path:
    """
    Construit le chemin d'archive : <dir>/Archives/<stem> (archive).md.
    """
    p = Path(original_path)
    synthesis_name = f"{original_name}{suffix}"
    synthesis_path = p / synthesis_name
    # Résolution des collisions
    counter = 1
    while exists(synthesis_path):
        new_name = f"{original_name}_{counter}{suffix}"
        synthesis_path = p / new_name
        counter += 1
    return synthesis_path
