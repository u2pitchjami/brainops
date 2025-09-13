"""
note_writer.py — Fonctions de mise à jour de l'entête YAML des notes Obsidian
"""

from __future__ import annotations

from pathlib import Path

import yaml

from brainops.header.header_utils import get_yaml, merge_yaml_header, update_yaml_header
from brainops.models.metadata import NoteMetadata
from brainops.models.types import StrOrPath
from brainops.utils.files import read_note_content, safe_write
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def write_metadata_to_note(
    filepath: StrOrPath, metadata: NoteMetadata, *, logger: LoggerProtocol | None = None
) -> bool:
    """
    Remplace complètement l'entête YAML par le contenu de NoteMetadata.
    """
    logger = ensure_logger(logger, __name__)
    filepath = Path(filepath).expanduser().resolve().as_posix()

    try:
        content = read_note_content(filepath, logger=logger)
        if not content:
            logger.warning("[WARN] Fichier vide ou non trouvé : %s", filepath)
            return False

        # On conserve uniquement le corps
        lines = content.splitlines(True)
        yaml_start, yaml_end = -1, -1
        if lines and lines[0].strip() == "---":
            yaml_start = 0
            yaml_end = next(
                (i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
                -1,
            )
        body_lines = lines[yaml_end + 1 :] if (yaml_start != -1 and yaml_end != -1) else lines

        yaml_dict = metadata.to_yaml_dict()
        yaml_text = yaml.safe_dump(yaml_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)

        new_content = f"---\n{yaml_text}---\n" + "".join(body_lines)
        return safe_write(filepath, content=new_content, logger=logger)

    except Exception as exc:
        logger.exception("[ERREUR] write_metadata_to_note: %s", exc)
        return False


@with_child_logger
def merge_metadata_in_note(
    filepath: StrOrPath, updates: dict[str, str | int | list[str]], *, logger: LoggerProtocol | None = None
) -> bool:
    """
    Fusionne des métadonnées dans l'entête YAML existant (sans perdre les anciennes).
    """
    logger = ensure_logger(logger, __name__)
    try:
        content = read_note_content(filepath, logger=logger)
        if not content:
            logger.warning("[WARN] Fichier vide ou non trouvé : %s", filepath)
            return False

        new_content = merge_yaml_header(content, updates, logger=logger)
        return safe_write(filepath, content=new_content, logger=logger)

    except Exception as exc:
        logger.exception("[ERREUR] merge_metadata_in_note: %s", exc)
        return False


@with_child_logger
def update_yaml_field(filepath: StrOrPath, key: str, value: str, *, logger: LoggerProtocol | None = None) -> bool:
    """
    Met à jour un champ unique dans l'entête YAML (écrase sa valeur).
    """
    logger = ensure_logger(logger, __name__)
    try:
        content = read_note_content(filepath, logger=logger)
        if not content:
            logger.warning("[WARN] Fichier vide ou non trouvé : %s", filepath)
            return False

        meta = get_yaml(content, logger=logger) or {}
        meta[key] = value
        new_content = update_yaml_header(content, meta, logger=logger)
        return safe_write(filepath, content=new_content, logger=logger)

    except Exception as exc:
        logger.exception("[ERREUR] update_yaml_field: %s", exc)
        return False
