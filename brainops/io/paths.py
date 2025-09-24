# brainops/utils/paths.py
"""
Helpers chemins relatifs/absolus (pylint OK).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
import os
from pathlib import Path, PurePosixPath
import tempfile
import time

from brainops.models.types import StrOrPath
from brainops.utils.config import BASE_PATH


def canonical_rel(path: StrOrPath) -> str:
    s = os.fspath(path).replace("\\", "/").strip()
    print(f"s :{s}")
    base = Path(BASE_PATH).as_posix().rstrip("/")
    print(f"base :{base}")

    if s.startswith("/"):
        if s == base:
            s = ""
        elif s.startswith(base + "/"):
            s = s[len(base) + 1 :]
            print(f"s2 :{s}")
        else:
            raise ValueError(f"Chemin absolu hors vault: {s} (BASE_PATH={base})")

    norm = PurePosixPath(s).as_posix()
    print(f"norm :{norm}")
    if norm == ".." or norm.startswith("../"):
        raise ValueError(f"Hors vault (..): {path}")
    return norm.lstrip("/")


def to_rel(path: StrOrPath) -> str:
    """
    Toujours une REL posix sans / initial.
    """
    return canonical_rel(path)


def to_abs(rel: StrOrPath) -> Path:
    """
    Retourne un Path ABSOLU sous BASE_PATH (prêt pour .read_text(), .rglob(), etc.).
    """
    rel_canon = canonical_rel(rel)
    p = (Path(BASE_PATH) / rel_canon).resolve()
    if not p.is_relative_to(BASE_PATH):
        raise ValueError(f"Path escape: {rel}")
    return p


def to_abs_str(rel: StrOrPath) -> str:
    """
    Compat string si nécessaire (ex: lib qui n’accepte pas Path).
    """
    return to_abs(rel).as_posix()


def rglob_rel(pattern: str, base_rel: str = "") -> Iterator[Path]:
    """Convenience: rglob sous un répertoire REL."""
    return to_abs(base_rel).rglob(pattern)


# --- Opérations de haut niveau ------------------------------------------------
def exists(rel: StrOrPath) -> bool:
    return to_abs(rel).exists()


def mkdirs(rel_dir: StrOrPath) -> Path:
    p = to_abs(rel_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def rglob(pattern: str, base_rel: str = "") -> Iterator[Path]:
    return to_abs(base_rel).rglob(pattern)


def read_text(rel_path: str, *, retries: int = 1, delay: float = 0.1, encoding: str = "utf-8") -> str:
    """
    Lit un fichier (relatif au vault) avec petits retries si FileNotFoundError (fichier en mouvement).
    """
    p: Path = to_abs(rel_path)
    for attempt in range(retries + 1):
        try:
            return p.read_text(encoding=encoding)
        except FileNotFoundError:
            if attempt == retries:
                # dernier essai -> on relance l'exception
                raise
            time.sleep(delay)
    # unreachable, mais garde-le si ton linter le demande
    raise RuntimeError("Unreachable")


def write_text_atomic(rel: StrOrPath, content: str, *, encoding: str = "utf-8") -> Path:
    """
    Écrit de façon atomique (tmp -> replace) pour éviter les demi-fichiers et boucles watcher.
    """
    final_p = to_abs(rel)
    final_p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding=encoding, dir=final_p.parent, delete=False) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_p = Path(tmp.name)
    os.replace(tmp_p, final_p)
    return final_p


def remove_file(rel: StrOrPath) -> None:
    p = to_abs(rel)
    if p.exists() and p.is_file():
        p.unlink()


def move(rel_src: StrOrPath, rel_dst: StrOrPath) -> Path:
    src, dst = to_abs(rel_src), to_abs(rel_dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.replace(dst)
    return dst


def _iter_physical_dirs(base: Path) -> Iterable[Path]:
    root = Path(to_abs(base))
    for p in root.rglob("*.md"):
        print("Found md file: %s", p)
        try:
            if Path(str(p)).is_dir() and not _is_hidden_path(p):
                print("Path(to_rel(p)): %s", Path(to_rel(p)))
                yield Path(to_rel(p))
        except Exception:  # pylint: disable=broad-except  # pragma: no cover
            continue


def _iter_md_files(base: Path) -> Iterable[Path]:
    root = Path(to_abs(base))
    for p in root.rglob("*.md"):
        if not _is_hidden_path(p):
            yield Path(p)


def _is_hidden_path(p: Path) -> bool:
    return any(part.startswith(".") for part in Path(to_abs(p)).parts)
