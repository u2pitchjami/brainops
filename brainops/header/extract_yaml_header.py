from __future__ import annotations

from typing import List, Tuple

from brainops.utils.files import maybe_clean, read_note_content
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def extract_yaml_header(
    filepath: str, clean: bool = True, *, logger: LoggerProtocol | None = None
) -> Tuple[List[str], str]:
    """
    Extrait l'entête YAML d'un fichier Obsidian.

    Retourne (header_lines, content_str)
      - header_lines: liste des lignes, incluant les délimiteurs '---' si présents
      - content_str: le corps (str), nettoyé si clean=True
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] entrée extract_yaml_header: %s", filepath)

    content = read_note_content(filepath, logger=logger)
    lines = content.strip().splitlines()

    header_lines: List[str] = []
    content_lines: List[str] = []

    if lines and lines[0].strip() == "---":
        try:
            logger.debug(
                "[DEBUG] extract_yaml_header: détection '---' en première ligne"
            )
            yaml_end_idx = next(
                i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"
            )
            header_lines = lines[: yaml_end_idx + 1]  # inclut la 2e barrière '---'
            content_lines = lines[yaml_end_idx + 1 :]
        except StopIteration:
            logger.warning("[WARN] En-tête YAML ouvert mais jamais fermé.")
            content_lines = lines
    else:
        content_lines = lines

    body = "\n".join(content_lines)
    if clean:
        body = maybe_clean(body)

    logger.debug("[DEBUG] extract_yaml_header header_lines: %r", header_lines)
    logger.debug("[DEBUG] extract_yaml_header content preview: %s", body[:500])
    return header_lines, body


@with_child_logger
def extract_metadata(
    filepath: str, key: str | None = None, *, logger: LoggerProtocol | None = None
) -> dict:
    """
    Extrait les métadonnées YAML (tout le dict ou une clé spécifique).
    """
    from brainops.header.header_utils import (  # import tardif pour éviter cycles
        get_yaml,
        get_yaml_value,
    )

    logger = ensure_logger(logger, __name__)
    try:
        content = read_note_content(filepath, logger=logger)
        logger.debug("[DEBUG] extract_metadata preview: %s", content[:500])
        return (
            get_yaml(content, logger=logger)
            if not key
            else get_yaml_value(content, key, logger=logger) or {}
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "[ERREUR] Impossible de lire l'entête de %s : %s", filepath, exc
        )
        return {}


@with_child_logger
def extract_note_metadata(
    filepath: str,
    old_metadata: dict | None = None,
    *,
    logger: LoggerProtocol | None = None,
) -> dict:
    """
    Extrait toutes les métadonnées d'une note (lecture unique), fusionne avec old_metadata si fourni.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] extract_note_metadata: %s", filepath)

    meta = extract_metadata(filepath, logger=logger)

    defaults = {
        "title": None,
        "category": None,
        "sub category": None,
        "tags": [],
        "status": "draft",
        "created": None,
        "last_modified": None,
        "project": None,
        "note_id": None,
    }
    if old_metadata:
        defaults.update(old_metadata)
    # on n’écrase que par des valeurs “truthy”
    defaults.update({k: v for k, v in meta.items() if v})

    logger.debug("[DEBUG] Métadonnées finales: %s", defaults)
    return defaults
