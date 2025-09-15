"""
# utils/paths.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


def path_contains_segment(path: str | Path, segment: str) -> bool:
    """
    True si `segment` est un composant du chemin (quelque soit la position).
    """
    try:
        return segment in Path(path).parts
    except Exception:
        return False


def path_is_inside(base: str | Path, target: str | Path) -> bool:
    """
    True si `target` est strictement sous `base` (structure de dossiers).
    """
    try:
        return Path(target).resolve().is_relative_to(Path(base).resolve())
    except AttributeError:
        # Compat < 3.9
        try:
            return Path(base).resolve() in Path(target).resolve().parents
        except Exception:
            return False
    except Exception:
        return False


@with_child_logger
def get_relative_parts(
    folder_path: str | Path,
    base_path: str | Path,
    *,
    logger: LoggerProtocol | None = None,
) -> tuple[str, ...] | None:
    """
    Renvoie les parties relatives de `folder_path` par rapport à `base_path` (None si folder_path n'est pas dans
    base_path).
    """
    logger = ensure_logger(logger, __name__)
    try:
        rel = Path(folder_path).resolve().relative_to(Path(base_path).resolve())
        return rel.parts
    except ValueError:
        logger.warning("[paths] %s n'est pas dans %s", folder_path, base_path)
        return None


def build_archive_path(original_path: str | Path) -> Path:
    """
    Construit le chemin d'archive : <dir>/Archives/<stem> (archive).md.
    """
    p = Path(original_path)
    archive_dir = p.parent / "Archives"
    archive_name = f"{p.stem} (archive){p.suffix}"
    return archive_dir / archive_name


@with_child_logger
def ensure_folder_exists(folder_path: str | Path, *, logger: LoggerProtocol | None = None) -> None:
    """
    Crée le dossier physiquement (mkdir -p) si besoin.
    """
    logger = ensure_logger(logger, __name__)
    folder = Path(folder_path)
    if folder.exists():
        logger.debug("[FOLDER] déjà présent : %s", folder)
        return
    try:
        folder.mkdir(parents=False, exist_ok=True)
    except Exception as exc:
        raise BrainOpsError("folder_exist KO", code=ErrCode.UNEXPECTED, ctx={"folder_path": folder_path}) from exc
    logger.info("[FOLDER] créé : %s", folder)
