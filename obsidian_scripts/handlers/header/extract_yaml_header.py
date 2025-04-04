"""
Ce module extrait les en-têtes YAML des fichiers de notes Obsidian.
"""
from logger_setup import setup_logger
from handlers.utils.files import read_note_content, maybe_clean
from handlers.header.header_utils import get_yaml, get_yaml_value
import logging

setup_logger("extract_yaml_header", logging.DEBUG)
logger = logging.getLogger("extract_yaml_header")

def extract_yaml_header(filepath: str, clean: bool = True) -> tuple[list[str], str]:
    """
    Extrait l'entête YAML d'un texte s'il existe.
    
    Args:
        text (str): Le texte à analyser.
        clean=True → nettoie automatiquement le corps
    
    Returns:
        tuple: (header_lines, content_lines)
            - header_lines : Liste contenant les lignes de l'entête YAML.
            - content_lines : Liste contenant le reste du texte sans l'entête.
    """
    logger.debug("[DEBUG] entrée extract_yaml_header")
    content = read_note_content(filepath)
    lines = content.strip().splitlines()
    
    header_lines = []
    content_lines = []

    if lines and lines[0].strip() == "---":
        try:
            logger.debug("[DEBUG] extract_yaml_header line 0 : ---")
            yaml_end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
            header_lines = lines[:yaml_end + 1]
            content_lines = lines[yaml_end + 1:]
        except StopIteration:
            logger.warning("[WARN] En-tête YAML ouvert mais jamais fermé.")
            content_lines = lines  # On ne touche pas
    else:
        content_lines = lines
        
    if clean:
        content_lines = maybe_clean("\n".join(content_lines))
    else:
        content_lines = "\n".join(content_lines)   
    
    
    logger.debug("[DEBUG] extract_yaml_header header : %s ", repr(header_lines))
    logger.debug("[DEBUG] extract_yaml_header content : %s ", content_lines[:5])
    # Rejoindre content_lines pour retourner une chaîne
    return header_lines, content_lines

def extract_metadata(filepath, key=None):
    """
    Extrait toutes les métadonnées YAML d'une note.
    """
    try:
        content = read_note_content(filepath)
        logger.debug(f"[DEBUG] extract_metadata : {content[:500]}")
        
        metadata = get_yaml(content) if not key else get_yaml_value(content, key)
        
        return metadata or {}

    except Exception as e:
        logger.error(f"[ERREUR] Impossible de lire l'entête du fichier {filepath} : {e}")
        return {}

def extract_note_metadata(filepath, old_metadata=None):
    """
    Extrait toutes les métadonnées d'une note en une seule lecture,
    en fusionnant avec d'anciennes métadonnées si nécessaire.

    :param filepath: Chemin absolu du fichier Markdown.
    :param old_metadata: Métadonnées précédentes (ex: en cas de déplacement).
    :return: Dictionnaire avec `title`, `category`, `subcategory`, `tags`, `status`, etc.
    """
    logger.debug(f"[DEBUG] extract_note_metadata : {filepath}")

    # 🔥 Récupération directe des métadonnées avec `extract_metadata()`
    metadata = extract_metadata(filepath)

    # 🔥 Définition des valeurs par défaut si absentes
    default_values = {
        "title": None,
        "category": None,
        "sub category": None,
        "tags": [],
        "status": "draft",
        "created": None,
        "last_modified": None,
        "project": None,
        "note_id": None
    }

    # 🔥 Fusion avec `old_metadata` et application des valeurs par défaut
    if old_metadata:
        default_values.update(old_metadata)  # 🔄 Priorité aux anciennes valeurs si existantes
    default_values.update({k: v for k, v in metadata.items() if v})  # 🔄 Ajout des nouvelles valeurs si elles existent

    logger.debug(f"[DEBUG] Métadonnées finales : {default_values}")
    return default_values
