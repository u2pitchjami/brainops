from pathlib import Path
from langdetect import detect
from brainops.logger_setup import setup_logger
from brainops.obsidian_scripts.handlers.utils.files import read_note_content, count_words
from brainops.obsidian_scripts.handlers.sql.db_get_linked_notes_utils import get_note_lang, get_data_for_should_trigger
import logging
import os

#setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

def make_relative_link(original_path, filepath):
    """
    Convertit un chemin absolu en lien Markdown relatif.
    
    :param original_path: Chemin absolu du fichier cible
    :param base_path: Répertoire de base pour générer des liens relatifs
    :param link_text: Texte visible pour le lien (par défaut : "Voir la note originale")
    :return: Lien Markdown au format [texte](chemin_relatif)
    """
    logger.debug("[DEBUG] entrée make_relative_link")
        
    
    original_path = Path(original_path)
    synt_path = Path(filepath).resolve()
    synt_path = synt_path.parent
    
     # Vérifie que le fichier appartient au répertoire de base
    if synt_path in original_path.parents:
        # Extraire le chemin relatif
        relative_path = original_path.relative_to(synt_path)
        logger.debug("[DEBUG] relative_path : %s", relative_path)
        return relative_path
    else:
        raise ValueError(f"Le fichier {original_path} est hors du répertoire de base {synt_path}")

def lang_detect(file_path):
    lang = None
    content = read_note_content(file_path)
    nb_words = count_words(content=content)

    if nb_words < 50:
        return "na"

    try:
        lang = detect(content)
        return "fr" if lang == "fr" else lang
    except:
        return "na"

def prompt_name_and_model_selection(note_id, key, forced_model=None):
    logger.debug("[DEBUG] prompt_name_selection note_id: %s, key: %s, forced_model: %s", note_id, key, forced_model)
    MODEL_FR = os.getenv('MODEL_FR')
    MODEL_EN = os.getenv('MODEL_EN')
    lang = get_note_lang(note_id)

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
        "add_questions"
    }

    if key not in valid_keys:
        raise ValueError(f"Clé inconnue : {key}")

    prompt_name = f"{key}_en" if lang != "fr" else key

    if forced_model:
        model_ollama = forced_model
        logger.debug("[DEBUG] Modèle forcé utilisé : %s", model_ollama)
    else:
        model_ollama = MODEL_EN if lang != "fr" else MODEL_FR

    logger.debug("[DEBUG] Langue détectée : %s → prompt: %s, modèle: %s", lang, prompt_name, model_ollama)

    return prompt_name, model_ollama


def should_trigger_process(note_id: int, new_word_count: int, threshold: int = 100) -> tuple[bool, str | None, int | None]:
    """
    Détermine si une note doit être retraitée.

    Args:
        note_id (int): ID de la note.
        new_word_count (int): Nombre de mots actuel dans la note.
        threshold (int): Écart minimum pour déclencher le retraitement.

    Returns:
        tuple:
            - bool: True si retraitement requis
            - str | None: Type de note ("archive" ou "synthesis")
            - int | None: ID du parent associé (utile pour relancer la synthèse)
    """
    status, parent_id, old_word_count = get_data_for_should_trigger(note_id)
    word_diff = abs((old_word_count or 0) - new_word_count)

    logger.debug(f"[trigger_check] Note {note_id} | status: {status} | old_word_count: {old_word_count} |word_diff: {word_diff} | parent_id: {parent_id}")

    if word_diff > threshold:
        if status == "archive":
            return True, "archive", parent_id
        if status == "synthesis":
            return True, "synthesis", parent_id

    return False, None, None




