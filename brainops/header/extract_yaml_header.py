"""
header.extract_yaml_header.
"""

from __future__ import annotations

from typing import Any

from brainops.header.header_utils import get_yaml
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.metadata import NoteMetadata
from brainops.models.types import StrOrPath
from brainops.utils.files import read_note_content
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def extract_yaml_header(filepath: str, *, logger: LoggerProtocol | None = None) -> tuple[list[str], str]:
    """
    Sépare le fichier en entête YAML (en lignes) et contenu (corps de note).

    Retourne (header_lines, content_str)
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] entrée extract_yaml_header: %s", filepath)
    try:
        content = read_note_content(filepath, logger=logger)
        lines = content.strip().splitlines()
        header_lines: list[str] = []
        content_lines: list[str] = []

        if lines and lines[0].strip() == "---":
            try:
                yaml_end_idx = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
                header_lines = lines[: yaml_end_idx + 1]
                content_lines = lines[yaml_end_idx + 1 :]
            except StopIteration:
                logger.warning("[WARN] En-tête YAML ouvert mais jamais fermé.")
                content_lines = lines
        else:
            content_lines = lines

        body = "\n".join(content_lines)
        logger.debug("[DEBUG] extract_yaml_header: header=%r", header_lines)
        logger.debug("[DEBUG] extract_yaml_header: body=%r", body[:300])
        return header_lines, body
    except FileNotFoundError as exc:  # pylint: disable=broad-except
        raise BrainOpsError(
            "Note absente !!",
            code=ErrCode.NOFILE,
            ctx={"path": filepath},
        ) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise BrainOpsError(
            "Erreur inattendue exécutrice",
            code=ErrCode.UNEXPECTED,
            ctx={"path": filepath},
        ) from exc


@with_child_logger
def extract_metadata(
    filepath: StrOrPath, key: str | None = None, *, logger: LoggerProtocol | None = None
) -> dict[str, Any] | Any:
    """
    Extrait et parse l'en-tête YAML du fichier.

    - Si `key` est fournie, retourne uniquement la valeur correspondante.
    - Sinon, retourne toutes les métadonnées (dict).
    """
    logger = ensure_logger(logger, __name__)
    try:
        header_lines, _ = extract_yaml_header(str(filepath), logger=logger)
        yaml_text = "\n".join(header_lines)
        parsed = get_yaml(yaml_text, logger=logger)

        if key:
            return parsed.get(key)
        return parsed

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ERREUR] extract_metadata: %s", exc)
        raise BrainOpsError(
            "extract_metadata",
            code=ErrCode.METADATA,
            ctx={"path": filepath},
        ) from exc


@with_child_logger
def extract_note_metadata(
    filepath: StrOrPath,
    *,
    logger: LoggerProtocol | None = None,
) -> NoteMetadata:
    """
    Extrait les métadonnées YAML sous forme d'objet typé NoteMetadata.
    """
    logger = ensure_logger(logger, __name__)
    meta_dict = extract_metadata(filepath, logger=logger)
    return NoteMetadata.from_yaml_dict(meta_dict)
