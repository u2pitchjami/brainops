from brainops.logger_setup import setup_logger
import logging
from brainops.obsidian_scripts.handlers.sql.db_get_linked_data import get_note_linked_data

#setup_logger("db_get_linked_notes_utils", logging.DEBUG)
logger = logging.getLogger("db_get_notes_utils")


def get_subcategory_prompt(note_id: int) -> str:
    """
    Récupère le prompt_name de la sous-catégorie associée à une note.
    Retourne 'divers' si non défini ou erreur.
    """
    data = get_note_linked_data(note_id, "subcategory")
    if isinstance(data, dict) and "prompt_name" in data:
        return data["prompt_name"]
    return "divers"
        
def get_category_and_subcategory_names(note_id: int) -> tuple[str, str]:
    category = get_note_linked_data(note_id, "category")
    subcategory = get_note_linked_data(note_id, "subcategory")

    return (
        category.get("name") if isinstance(category, dict) else "Inconnue",
        subcategory.get("name") if isinstance(subcategory, dict) else "Inconnue"
    )

def get_note_folder_type(note_id: int) -> str:
    """
    Récupère le type de dossier (folder_type) associé à une note.

    Args:
        note_id (int): L'identifiant de la note.

    Returns:
        str: Le type du dossier (ex: 'archive', 'projet', etc.), ou 'inconnu' si non trouvé.
    """
    folder = get_note_linked_data(note_id, "folder")
    return folder.get("folder_type") if isinstance(folder, dict) else "inconnu"

def get_synthesis_metadata(note_id: int) -> tuple[str, str, str, str]:
    """
    Récupère title, source, author, created depuis une note synthesis.
    """
    note_data = get_note_linked_data(note_id, "note")
    logger.debug(f"[DEBUG] get_synthesis_metadata | note_data = {note_data}")

    title = note_data.get("title") if isinstance(note_data, dict) else ""
    source = note_data.get("source") if isinstance(note_data, dict) else ""
    author = note_data.get("author") if isinstance(note_data, dict) else ""
    created = note_data.get("created_at") if isinstance(note_data, dict) else ""
    category_id = note_data.get("category_id") if isinstance(note_data, dict) else ""
    sub_category_id = note_data.get("sub_category_id") if isinstance(note_data, dict) else ""

    return title, source, author, created, category_id, sub_category_id

def get_note_tags(note_id: int) -> list:
    """
    Récupère les tags associés à une note.

    Args:
        note_id (int): L'identifiant de la note.

    Returns:
        list: Une liste de tags associés à la note, ou une liste vide si aucun tag trouvé.
    """
    tags_data = get_note_linked_data(note_id, "tags")
    logger.debug(f"[DEBUG] tags_data = {tags_data}")
    if isinstance(tags_data, list):
        # Si on récupère une liste, on la retourne telle quelle
        return [tag.get("tag") for tag in tags_data if isinstance(tag, dict)]
    return []  # Retourne une liste vide si aucune donnée n'est trouvée

def get_new_note_test_metadata(note_id: int) -> tuple[str, str, str, str]:
    """
    Récupère title, source, author, created depuis une note synthesis.
    """
    note_data = get_note_linked_data(note_id, "note")
    logger.debug(f"[DEBUG] get_synthesis_metadata | note_data = {note_data}")

    title = note_data.get("title") if isinstance(note_data, dict) else ""
    source = note_data.get("source") if isinstance(note_data, dict) else ""
    author = note_data.get("author") if isinstance(note_data, dict) else ""
    source_hash = note_data.get("source_hash") if isinstance(note_data, dict) else ""
    
    return title, source, author, source_hash

def get_note_lang(note_id: int) -> str:
    """
    Récupère le type de dossier (folder_type) associé à une note.

    Args:
        note_id (int): L'identifiant de la note.

    Returns:
        str: Le type du dossier (ex: 'archive', 'projet', etc.), ou 'inconnu' si non trouvé.
    """
    lang_data = get_note_linked_data(note_id, "note")
    return lang_data.get("lang") if isinstance(lang_data, dict) else "inconnu"

def get_data_for_should_trigger(note_id: int) -> tuple[str, str, str]:
    """
    Récupère title, source, author, created depuis une note synthesis.
    """
    note_data = get_note_linked_data(note_id, "note")
    
    status = note_data.get("status") if isinstance(note_data, dict) else ""
    parent_id = note_data.get("parent_id") if isinstance(note_data, dict) else ""
    word_count = note_data.get("word_count") if isinstance(note_data, dict) else ""
    
    return status, parent_id, word_count

def get_parent_id(note_id: int) -> tuple[str]:
    """
    Récupère title, source, author, created depuis une note synthesis.
    """
    note_data = get_note_linked_data(note_id, "note")
    parent_id = note_data.get("parent_id") if isinstance(note_data, dict) else ""    
    return parent_id

def get_file_path(note_id: int) -> tuple[str]:
    """
    Récupère title, source, author, created depuis une note synthesis.
    """
    note_data = get_note_linked_data(note_id, "note")
    file_path = note_data.get("file_path") if isinstance(note_data, dict) else ""    
    return file_path
