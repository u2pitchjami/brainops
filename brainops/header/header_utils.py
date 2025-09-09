"""header.header_utils"""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import re

import yaml

from brainops.utils.files import read_note_content, safe_write
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger

_YAML_FENCE = re.compile(r"^\ufeff?\s*---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n)?", re.DOTALL)  # gère BOM/CRLF/espaces


@with_child_logger
def get_yaml(content: str, *, logger: LoggerProtocol | None = None) -> dict[str, str]:
    """
    Extrait et parse l'en-tête YAML. Retourne {} si absent.
    """
    logger = ensure_logger(logger, __name__)
    try:
        m = _YAML_FENCE.match(content)
        if m:
            return yaml.safe_load(m.group(1)) or {}
    except Exception as exc:  # pylint: disable=broad-except
        # on ne log pas le contenu complet pour éviter le bruit
        logger.warning(f"[get_yaml] Erreur parsing YAML : {exc}")
    return {}


@with_child_logger
def get_yaml_value(content: str, key: str, default: str | None = None, *, logger: LoggerProtocol | None = None) -> str | None:
    """
    get_yaml_value _summary_

    _extended_summary_

    Args:
        content (str): _description_
        key (str): _description_
        default (_type_, optional): _description_. Defaults to None.
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    logger = ensure_logger(logger, __name__)
    y = get_yaml(content, logger=logger)
    return y.get(key, default)


@with_child_logger
def update_yaml_header(content: str, new_metadata: dict[str, str], *, logger: LoggerProtocol | None = None) -> str:
    """
    Remplace l’en-tête YAML par new_metadata (écrase tout l’entête).
    """
    _ = ensure_logger(logger, __name__)
    new_yaml = yaml.safe_dump(new_metadata, default_flow_style=False, sort_keys=False, allow_unicode=True)
    new_front = f"---\n{new_yaml}---\n"

    m = _YAML_FENCE.match(content)
    body = content[len(m.group(0)) :] if m else content
    return new_front + body


@with_child_logger
def merge_yaml_header(content: str, new_metadata: dict[str, str], *, logger: LoggerProtocol | None = None) -> str:
    """
    Fusionne de nouvelles métadonnées dans l’en-tête YAML (conserve le reste).
    """
    logger = ensure_logger(logger, __name__)
    try:
        m = _YAML_FENCE.match(content)
        if m:
            existing = yaml.safe_load(m.group(1)) or {}
            body = content[len(m.group(0)) :]
        else:
            existing = {}
            body = content

        merged = {**existing, **new_metadata}
        new_yaml = yaml.safe_dump(merged, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return f"---\n{new_yaml}---\n{body}"
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ERROR] merge_yaml_header: %s", exc)
        return content


@with_child_logger
def patch_yaml_line(
    yaml_text: str,
    key: str,
    patch_func: Callable[[str], str],
    *,
    logger: LoggerProtocol | None = None,
) -> str:
    """
    Applique une fonction de transformation sur la valeur d'une ligne 'key: value' (yaml_text = bloc YAML + délimiteurs).
    """
    _ = ensure_logger(logger, __name__)
    pattern = rf"^({re.escape(key)}\s*:\s*)(.+)$"
    return re.sub(
        pattern,
        lambda m: f"{m.group(1)}{patch_func(m.group(2))}",
        yaml_text,
        flags=re.MULTILINE,
    )


@with_child_logger
def clean_yaml_spacing_in_file(file_path: str, *, logger: LoggerProtocol | None = None) -> bool:
    """
    Nettoie: s’assure d’une seule ligne vide après l’entête YAML, puis le corps.
    """
    logger = ensure_logger(logger, __name__)
    try:
        content = read_note_content(file_path, logger=logger)
        if not content:
            return False
        lines = content.splitlines()
        inside = False
        yaml_end_idx: int | None = None

        for i, line in enumerate(lines):
            if line.strip() == "---":
                if not inside:
                    inside = True
                else:
                    yaml_end_idx = i
                    break

        if yaml_end_idx is None:
            return False  # pas d’entête

        body_start = yaml_end_idx + 1
        while body_start < len(lines) and lines[body_start].strip() == "":
            body_start += 1

        new_lines = lines[: yaml_end_idx + 1] + [""] + lines[body_start:]
        new_content = "\n".join(new_lines).strip() + "\n"
        return safe_write(file_path, new_content, logger=logger)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ERREUR] clean_yaml_spacing_in_file: %s", exc)
        return False


def hash_source(source: str) -> str:
    """
    hash_source _summary_

    _extended_summary_

    Args:
        source (str): _description_

    Returns:
        str: _description_
    """
    return hashlib.sha256(source.strip().lower().encode("utf-8")).hexdigest()
