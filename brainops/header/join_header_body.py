from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Union, overload

from brainops.header.extract_yaml_header import extract_yaml_header
from brainops.header.header_utils import merge_yaml_header
from brainops.header.join_utils import join_yaml_and_body
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.types import StrOrPath
from brainops.utils.files import safe_write
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger

BodyTransform = Callable[[str], str | tuple[str, dict[str, Any]]]
BodyTransformInput = Union[str, BodyTransform]


@overload
def apply_to_note_body(
    filepath: StrOrPath,
    transform: str,
    *,
    write_file: bool = True,
    preserve_yaml: bool = True,
    yaml_keys_to_patch: list[str] | None = None,
    logger: LoggerProtocol | None = None,
) -> str: ...


@overload
def apply_to_note_body(
    filepath: StrOrPath,
    transform: BodyTransform,
    *,
    write_file: bool = True,
    preserve_yaml: bool = True,
    yaml_keys_to_patch: list[str] | None = None,
    logger: LoggerProtocol | None = None,
) -> str: ...


@with_child_logger
def apply_to_note_body(
    filepath: StrOrPath,
    transform: BodyTransformInput,
    *,
    write_file: bool = True,
    preserve_yaml: bool = True,  # laissé pour compat
    yaml_keys_to_patch: list[str] | None = None,  # non utilisé ici
    logger: LoggerProtocol | None = None,
) -> str:
    """
    Applique `transform` au CORPS d'une note (frontmatter YAML conservé), puis:
      - si write_file=True : écrit le fichier et retourne None
      - sinon : retourne le contenu complet (YAML + body) sous forme de str

    Le transform peut retourner:
      - str : nouveau body
      - (str, dict) : (nouveau body, mises à jour YAML à fusionner)
    """
    logger = ensure_logger(logger, __name__)
    try:
        path = Path(str(filepath)).expanduser().resolve()
        header_lines, body = extract_yaml_header(path.as_posix(), logger=logger)

        # 1) Transformation du corps
        # Discrimination de type à l'exécution
        if isinstance(transform, str):
            new_body = transform
            yaml_updates: dict[str, Any] = {}
        else:
            out = transform(body)
            if isinstance(out, tuple):
                new_body, yaml_updates = out
            else:
                new_body, yaml_updates = out, {}

        # 2) Recomposition entête + corps
        content = join_yaml_and_body(header_lines, new_body)

        # 3) Fusion YAML si nécessaire (normalisée via PyYAML)
        if yaml_updates:
            content = merge_yaml_header(content, yaml_updates, logger=logger)

        final_content = content  # str

        # 4) Écriture ou retour en mémoire
        if write_file:
            success = safe_write(path.as_posix(), content=str(final_content), logger=logger)
            if not success:
                logger.error("[apply_to_note_body] Problème lors de l’écriture de %s", path.as_posix())
            else:
                logger.info("[apply_to_note_body] Note enregistrée : %s", path.as_posix())

        return str(final_content)
    except Exception as exc:
        raise BrainOpsError("join body + yaml KO", code=ErrCode.FILEERROR, ctx={"filepath": filepath}) from exc
