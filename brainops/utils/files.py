# utils/files.py
from __future__ import annotations

import hashlib
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Union

from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger

StrOrPath = Union[str, Path]


@with_child_logger
def wait_for_file(
    file_path: StrOrPath,
    timeout: float = 3.0,
    *,
    logger: Optional[LoggerProtocol] = None,
) -> bool:
    """
    Attend que le fichier existe jusqu'à `timeout` secondes.
    """
    logger = ensure_logger(logger, __name__)
    start = time.time()
    path = Path(file_path)
    while not path.exists():
        if time.time() - start > timeout:
            logger.debug("[wait_for_file] timeout sur %s", path)
            return False
        time.sleep(0.5)
    return True


def hash_file_content(filepath: StrOrPath) -> Optional[str]:
    """
    SHA-256 du fichier, None en cas d'erreur.
    """
    try:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as exc:  # pylint: disable=broad-except
        # logger délégué au caller si besoin
        return None


@with_child_logger
def safe_write(
    file_path: StrOrPath,
    content: Union[str, Iterable[str]],
    *,
    verify_contains: Optional[list[str]] = None,
    logger: Optional[LoggerProtocol] = None,
) -> bool:
    """
    Écrit de façon sûre :
    - supporte str ou liste/iterable de str
    - fsync
    - vérification optionnelle de champs
    """
    logger = ensure_logger(logger, __name__)
    p = Path(file_path)
    try:
        with open(p, "w", encoding="utf-8") as f:
            if isinstance(content, str):
                f.write(content)
                logger.debug("[safe_write] write() %d chars → %s", len(content), p)
            else:
                lines = list(content)
                f.writelines(lines)
                logger.debug("[safe_write] writelines() %d lignes → %s", len(lines), p)
            f.flush()
            # fsync pour garantir la persistance disque
            os.fsync(f.fileno())

        if verify_contains:
            written = p.read_text(encoding="utf-8")
            for needle in verify_contains:
                if needle not in written:
                    logger.warning(
                        "[safe_write] Champ manquant '%s' dans %s", needle, p
                    )
                    return False
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("[safe_write] Erreur d'écriture %s : %s", p, exc)
        return False


@with_child_logger
def copy_file_with_date(
    filepath: StrOrPath,
    destination_folder: StrOrPath,
    *,
    logger: Optional[LoggerProtocol] = None,
) -> Optional[Path]:
    """
    Copie un fichier en préfixant par la date 'yymmdd_'.
    Retourne le chemin de destination ou None en cas d'erreur.
    """
    logger = ensure_logger(logger, __name__)
    src = Path(filepath).resolve()
    dst_dir = Path(destination_folder).resolve()
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        name = src.name
        stem, ext = src.stem, src.suffix
        date_str = datetime.now().strftime("%y%m%d")
        dst = dst_dir / f"{date_str}_{stem}{ext}"
        dst.write_bytes(src.read_bytes())
        logger.info("[copy] %s → %s", src, dst)
        return dst
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("[copy] Échec %s → %s : %s", src, dst_dir, exc)
        return None


@with_child_logger
def move_file_with_date(
    filepath: StrOrPath,
    destination_folder: StrOrPath,
    *,
    logger: Optional[LoggerProtocol] = None,
) -> Optional[Path]:
    """
    Déplace un fichier en préfixant par la date 'yymmdd_'.
    Retourne le nouveau chemin ou None en cas d'erreur.
    """
    logger = ensure_logger(logger, __name__)
    src = Path(filepath).resolve()
    dst_dir = Path(destination_folder).resolve()
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%y%m%d")
        dst = dst_dir / f"{date_str}_{src.name}"
        src.replace(dst)
        logger.info("[move] %s → %s", src, dst)
        return dst
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("[move] Échec %s → %s : %s", src, dst_dir, exc)
        return None


@with_child_logger
def count_words(
    *,
    content: Optional[str] = None,
    filepath: Optional[StrOrPath] = None,
    logger: LoggerProtocol | None = None,
) -> int:
    """
    Compte les mots à partir d'une chaîne ou d'un fichier.
    """
    logger = ensure_logger(logger, __name__)
    if content is None and filepath is None:
        logger.warning("[count_words] ni content ni filepath fournis")
        return 0

    if content is None and filepath:
        content = read_note_content(Path(filepath).as_posix(), logger=logger)
        if content is None:
            return 0

    if not isinstance(content, str):
        logger.warning("[count_words] contenu invalide (attendu str)")
        return 0

    wc = len(content.split())
    logger.debug("[count_words] %d mots", wc)
    return wc


def maybe_clean(content: Union[str, list[str]], *, force: bool = False) -> str:
    """
    Nettoie *si nécessaire* :
    - list -> join + clean
    - présence de balises HTML problématiques -> clean
    - force=True -> clean systématique
    """
    if force:
        return clean_content(content)

    if isinstance(content, list):
        return clean_content(content)

    if isinstance(content, str) and ("<svg" in content or "<iframe" in content):
        return clean_content(content)

    return content if isinstance(content, str) else "\n".join(map(str, content))


def clean_content(content: Union[str, list[str]]) -> str:
    """
    Nettoyage doux (pré-LLM) en conservant les blocs Markdown.
    """
    if isinstance(content, list):
        content = "\n".join(str(line).strip() for line in content)

    # retire balises <svg>...</svg>, bullets anormales, compresse les sauts
    content = re.sub(r"<svg[^>]*>.*?</svg>", "", content, flags=re.DOTALL)
    content = re.sub(r"^- .*\n?", "", content, flags=re.MULTILINE)
    content = re.sub(r"\n\s*\n+", "\n\n", content)

    return content.strip()


@with_child_logger
def read_note_content(
    filepath: StrOrPath, *, logger: LoggerProtocol | None = None
) -> Optional[str]:
    """
    Lit le contenu d'une note (UTF-8). None en cas d'erreur.
    """
    logger = ensure_logger(logger, __name__)
    p = Path(filepath)
    try:
        text = p.read_text(encoding="utf-8")
        logger.debug("[read] %s (%d chars)", p, len(text))
        return text
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("[read] Impossible de lire %s : %s", p, exc)
        return None


def join_yaml_and_body(header_lines: list[str], body: str) -> str:
    """
    Recompose YAML + corps :
    - YAML encadré par ---
    - une seule ligne vide entre YAML et corps
    - fin par \n
    """
    if not header_lines:
        return body.strip() + "\n"

    yaml_header = "\n".join(header_lines).strip()
    body_clean = body.strip()

    if yaml_header.count("---") < 2:
        return f"---\n{yaml_header}\n---\n\n{body_clean}\n"
    return f"{yaml_header}\n\n{body_clean}\n"
