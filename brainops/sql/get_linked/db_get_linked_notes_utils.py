"""# sql/db_get_linked_notes_utils.py"""

from __future__ import annotations

from typing import List, Optional, Tuple

from brainops.sql.get_linked.db_get_linked_data import get_note_linked_data
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def get_subcategory_prompt(
    note_id: int, *, logger: LoggerProtocol | None = None
) -> str:
    """
    Retourne le prompt_name de la sous-catégorie associée à une note, ou 'divers'.
    """
    logger = ensure_logger(logger, __name__)
    data = get_note_linked_data(note_id, "subcategory", logger=logger)
    if isinstance(data, dict) and "prompt_name" in data and data["prompt_name"]:
        return str(data["prompt_name"])
    return "divers"


@with_child_logger
def get_category_and_subcategory_names(
    note_id: int, *, logger: LoggerProtocol | None = None
) -> Tuple[str, str]:
    """
    get_category_and_subcategory_names _summary_

    _extended_summary_

    Args:
        note_id (int): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        Tuple[str, str]: _description_
    """
    logger = ensure_logger(logger, __name__)
    category = get_note_linked_data(note_id, "category", logger=logger)
    subcategory = get_note_linked_data(note_id, "subcategory", logger=logger)

    cat_name = (
        str(category.get("name"))
        if isinstance(category, dict) and "name" in category
        else "Inconnue"
    )
    sub_name = (
        str(subcategory.get("name"))
        if isinstance(subcategory, dict) and "name" in subcategory
        else "Inconnue"
    )
    return cat_name, sub_name


@with_child_logger
def get_note_folder_type(note_id: int, *, logger: LoggerProtocol | None = None) -> str:
    """
    Retourne folder_type (storage/archive/technical/project/personnal) ou 'inconnu'.
    """
    logger = ensure_logger(logger, __name__)
    folder = get_note_linked_data(note_id, "folder", logger=logger)
    return (
        str(folder.get("folder_type"))
        if isinstance(folder, dict) and "folder_type" in folder
        else "inconnu"
    )


@with_child_logger
def get_synthesis_metadata(
    note_id: int, *, logger: LoggerProtocol | None = None
) -> Tuple[str, str, str, str, Optional[int], Optional[int]]:
    """
    Récupère (title, source, author, created_at, category_id, subcategory_id) pour une note.
    """
    logger = ensure_logger(logger, __name__)
    note_data = get_note_linked_data(note_id, "note", logger=logger)
    if not isinstance(note_data, dict):
        return "", "", "", "", None, None

    title = str(note_data.get("title") or "")
    source = str(note_data.get("source") or "")
    author = str(note_data.get("author") or "")
    created = str(note_data.get("created_at") or "")
    category_id = (
        int(note_data["category_id"])
        if note_data.get("category_id") is not None
        else None
    )
    subcategory_id = (
        int(note_data["subcategory_id"])
        if note_data.get("subcategory_id") is not None
        else None
    )
    return title, source, author, created, category_id, subcategory_id


@with_child_logger
def get_note_tags(note_id: int, *, logger: LoggerProtocol | None = None) -> List[str]:
    """
    Retourne la liste des tags (vide si aucun).
    """
    logger = ensure_logger(logger, __name__)
    tags = get_note_linked_data(note_id, "tags", logger=logger)
    return list(tags) if isinstance(tags, list) else []


@with_child_logger
def get_new_note_test_metadata(
    note_id: int, *, logger: LoggerProtocol | None = None
) -> Tuple[str, str, str, str]:
    """
    Récupère (title, source, author, source_hash) pour vérifications (doublons, etc.).
    """
    logger = ensure_logger(logger, __name__)
    note_data = get_note_linked_data(note_id, "note", logger=logger)
    if not isinstance(note_data, dict):
        return "", "", "", ""
    title = str(note_data.get("title") or "")
    source = str(note_data.get("source") or "")
    author = str(note_data.get("author") or "")
    source_hash = str(note_data.get("source_hash") or "")
    return title, source, author, source_hash


@with_child_logger
def get_note_lang(note_id: int, *, logger: LoggerProtocol | None = None) -> str:
    """
    Retourne la langue (3 lettres) ou 'inconnu'.
    """
    logger = ensure_logger(logger, __name__)
    data = get_note_linked_data(note_id, "note", logger=logger)
    return (
        str(data.get("lang"))
        if isinstance(data, dict) and data.get("lang")
        else "inconnu"
    )


@with_child_logger
def get_data_for_should_trigger(
    note_id: int, *, logger: LoggerProtocol | None = None
) -> Tuple[str, Optional[int], int]:
    """
    Retourne (status, parent_id, word_count) pour décider si un traitement doit être déclenché.
    """
    logger = ensure_logger(logger, __name__)
    note = get_note_linked_data(note_id, "note", logger=logger)
    if not isinstance(note, dict):
        return "", None, 0
    status = str(note.get("status") or "")
    parent_id = int(note["parent_id"]) if note.get("parent_id") is not None else None
    word_count = int(note.get("word_count") or 0)
    return status, parent_id, word_count


@with_child_logger
def get_parent_id(
    note_id: int, *, logger: LoggerProtocol | None = None
) -> Optional[int]:
    """
    get_parent_id _summary_

    _extended_summary_

    Args:
        note_id (int): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        Optional[int]: _description_
    """
    logger = ensure_logger(logger, __name__)
    note = get_note_linked_data(note_id, "note", logger=logger)
    if not isinstance(note, dict):
        return None
    return int(note["parent_id"]) if note.get("parent_id") is not None else None


@with_child_logger
def get_file_path(
    note_id: int, *, logger: LoggerProtocol | None = None
) -> Optional[str]:
    """
    get_file_path _summary_

    _extended_summary_

    Args:
        note_id (int): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        Optional[str]: _description_
    """
    logger = ensure_logger(logger, __name__)
    note = get_note_linked_data(note_id, "note", logger=logger)
    if not isinstance(note, dict):
        return None
    return str(note["file_path"]) if note.get("file_path") else None
