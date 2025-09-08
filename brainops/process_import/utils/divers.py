# process/divers.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from langdetect import detect

from brainops.models.note import Note
from brainops.sql.get_linked.db_get_linked_data import get_note_linked_data
from brainops.sql.get_linked.db_get_linked_notes_utils import get_note_lang
from brainops.utils.config import MODEL_EN, MODEL_FR
from brainops.utils.files import count_words, read_note_content
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import sanitize_created, sanitize_filename


@with_child_logger
def rename_file(
    filepath: str | Path, note_id: int, *, logger: Optional[LoggerProtocol] = None
) -> Path:
    """
    Renomme un fichier en préfixant par la date (créée ou actuelle), en évitant les collisions.
    Retourne le nouveau chemin.
    """
    logger = ensure_logger(logger, __name__)
    file_path = Path(str(filepath)).resolve()

    logger.debug("[DEBUG] rename_file → %s", file_path)
    if not file_path.exists():
        msg = f"Le fichier {file_path} n'existe pas."
        logger.error("[ERROR] %s", msg)
        raise FileNotFoundError(msg)

    # Récupère created_at depuis la DB si dispo, sinon now()
    created_at_raw: Optional[str] = None
    try:
        data = get_note_linked_data(note_id, "note", logger=logger)
        if isinstance(data, dict):
            created_at_raw = data.get("created_at")  # peut être str, date, datetime
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("[WARN] Impossible de lire created_at en DB : %s", exc)

    created_str = (
        sanitize_created(created_at_raw, logger=logger)
        if created_at_raw
        else datetime.now().strftime("%Y-%m-%d")
    )
    stem_sanitized = sanitize_filename(file_path.stem, logger=logger)
    new_name = f"{created_str}_{stem_sanitized}{file_path.suffix}"
    new_path = file_path.with_name(new_name)

    # Résolution des collisions
    counter = 1
    while new_path.exists():
        new_name = f"{created_str}_{stem_sanitized}_{counter}{file_path.suffix}"
        new_path = file_path.with_name(new_name)
        counter += 1

    file_path.rename(new_path)
    logger.info("[INFO] Note renommée : %s → %s", file_path.name, new_path.name)
    return new_path


@with_child_logger
def make_relative_link(
    original_path: str | Path,
    filepath: str | Path,
    *,
    logger: Optional[LoggerProtocol] = None,
) -> Path:
    """
    Convertit un chemin absolu (original_path) en chemin relatif à partir du dossier de 'filepath'.
    Retourne un Path relatif utilisable dans un lien Obsidian.
    """
    logger = ensure_logger(logger, __name__)
    orig = Path(str(original_path)).resolve()
    base = Path(str(filepath)).resolve().parent

    if base in orig.parents:
        rel = orig.relative_to(base)
        logger.debug("[DEBUG] relative_path : %s", rel)
        return rel
    raise ValueError(f"Le fichier {orig} est hors du répertoire de base {base}")


@with_child_logger
def lang_detect(
    file_path: str | Path, *, logger: Optional[LoggerProtocol] = None
) -> str:
    """
    Détecte la langue ('fr', 'en', ...), 'na' si trop court (<50 mots) ou indétectable.
    """
    logger = ensure_logger(logger, __name__)
    content = read_note_content(Path(str(file_path)).as_posix(), logger=logger)
    nb_words = count_words(content=content, logger=logger)

    if nb_words < 50:
        return "na"

    try:
        lang = detect(content)
        return "fr" if lang == "fr" else lang
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("[DEBUG] lang_detect exception: %s", exc)
        return "na"


@with_child_logger
def prompt_name_and_model_selection(
    note_id: int,
    key: str,
    forced_model: Optional[str] = None,
    logger: Optional[LoggerProtocol] = None,
) -> tuple[str, str]:
    """
    Sélectionne (prompt_name, model_ollama) selon la langue de la note.
    - prompt suffixé _en si langue != 'fr'
    - modèle choisi via config (MODEL_FR / MODEL_EN) sauf si forced_model fourni
    """
    logger = ensure_logger(logger, __name__)
    valid_keys = {
        "reformulation",
        "reformulation2",
        "divers",
        "synthese2",
        "add_tags",
        "summary",
        "type",
        "glossaires",
        "glossaires_regroup",
        "synth_translate",
        "add_questions",
    }
    if key not in valid_keys:
        raise ValueError(f"Clé inconnue : {key}")

    lang = get_note_lang(note_id, logger=logger)
    prompt_name = f"{key}_en" if lang != "fr" else key
    model_ollama = forced_model or (MODEL_EN if lang != "fr" else MODEL_FR)
    return prompt_name, model_ollama
