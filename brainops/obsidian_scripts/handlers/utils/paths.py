import logging
from pathlib import Path

logger = logging.getLogger("obsidian_notes." + __name__)

def path_contains_segment(path: str | Path, segment: str) -> bool:
    """
    Vérifie si un segment (dossier ou fichier) est présent dans le chemin (peu importe la position).
    """
    try:
        return segment in Path(path).parts
    except Exception:
        return False

def path_is_inside(base: str | Path, target: str | Path) -> bool:
    """
    Vérifie si target est contenu dans base (au sens structure de dossier).
    Évite les faux positifs d'un simple 'in'.
    """
    try:
        return Path(target).resolve(strict=False).is_relative_to(Path(base).resolve(strict=False))
    except AttributeError:
        # Pour Python < 3.9
        try:
            return Path(base).resolve(strict=False) in Path(target).resolve(strict=False).parents
        except Exception:
            return False
    except Exception:
        return False

def get_relative_parts(folder_path: str | Path, base_path: str | Path):
    """
    Renvoie les parties relatives de `folder_path` par rapport à `base_path`, ou None si erreur.
    """
    try:
        return Path(folder_path).resolve().relative_to(Path(base_path).resolve()).parts
    except ValueError:
        logger.warning(f"[WARN] get_relative_parts : {folder_path} n'est pas dans {base_path}")
        return None
    
def build_archive_path(original_path: str | Path) -> Path:
    original_path = Path(original_path)
    archive_dir = original_path.parent / "Archives"
    filename = original_path.stem
    
    archive_name = f"{filename} (archive){original_path.suffix}"
    return archive_dir / archive_name

def ensure_folder_exists(folder_path: str | Path):
    """
    Crée physiquement un dossier s'il n'existe pas encore (équivalent mkdir -p).
    """
    folder = Path(folder_path)
    if not folder.exists():
        try:
            folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"[FOLDER] Dossier créé : {folder}")
        except Exception as e:
            logger.error(f"[FOLDER] Échec de création du dossier {folder} : {e}")
    else:
        logger.debug(f"[FOLDER] Dossier déjà existant : {folder}")