"""
utils/files.py.
"""

from __future__ import annotations

from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def join_yaml_and_body(
    header_lines: list[str],
    body: str,
    *,
    logger: LoggerProtocol | None = None,
) -> str:
    """
    Recompose un document à partir de l'entête YAML (lignes) et du corps.

    - Accepte header_lines avec ou sans délimiteurs '---'
    - Normalise le frontmatter sous la forme:
        ---\n<yaml>\n---\n\n<body>\n
    - Évite la prolifération de lignes vides (exactement une entre YAML et corps)
    - Ajoute toujours un newline final.

    Args:
        header_lines: L'entête YAML en lignes (tel que renvoyé par split/parse).
        body: Le corps de la note (texte, sans l'entête).
        logger: Logger optionnel.

    Returns:
        Le contenu complet normalisé (str).
    """
    log = ensure_logger(logger, __name__)

    if not header_lines:
        return body.strip() + "\n"

    lines = [ln.rstrip("\r\n") for ln in header_lines]
    if lines:
        lines[0] = lines[0].lstrip("\ufeff")  # BOM éventuel

    has_start = bool(lines and lines[0].strip() == "---")
    end_idx = None
    if has_start:
        for i, ln in enumerate(lines[1:], start=1):
            if ln.strip() == "---":
                end_idx = i
                break

    if has_start and end_idx is not None:
        inner = lines[1:end_idx]
    else:
        if has_start and end_idx is None:
            log.warning("[join_yaml_and_body] Entête YAML ouvert mais non fermé, normalisation.")
            inner = lines[1:]
        else:
            inner = lines

    yaml_text = "\n".join(inner).strip()
    frontmatter = f"---\n{yaml_text}\n---\n"
    body_clean = body.lstrip("\r\n").strip()
    return f"{frontmatter}\n{body_clean}\n"
