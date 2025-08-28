import logging

from brainops.obsidian_scripts.handlers.process.large_note import process_large_note
from brainops.obsidian_scripts.handlers.process.standard_note import (
    process_standard_note,
)
from brainops.obsidian_scripts.handlers.utils.divers import (
    prompt_name_and_model_selection,
)

logger = logging.getLogger("obsidian_notes." + __name__)


def large_or_standard_note(
    filepath,
    content=None,
    note_id=None,
    prompt_key=None,
    model_ollama=None,
    word_limit=1000,
    split_method="titles_and_words",
    write_file=True,
    send_to_model=True,
    custom_prompts=None,
    persist_blocks=True,
    resume_if_possible=True,
    source="normal",
    process_mode="large_note",
    prompt_name=None,
):
    try:
        logger.debug(
            f"[DEBUG] large_or_standard_note model_ollama envoyé : {model_ollama}"
        )
        if not prompt_name:
            if prompt_key:
                key = prompt_key
                prompt_name, model_ollama = prompt_name_and_model_selection(
                    note_id, key=key
                )
                logger.debug(
                    f"[DEBUG] large_or_standard_note model_ollama : {model_ollama}"
                )
            else:
                logger.error(
                    "[ERREUR] Aucun prompt_name, prompt_key ou note_id fourni. Impossible de continuer."
                )
                return ""

        if process_mode == "large_note":
            return process_large_note(
                note_id=note_id,
                filepath=filepath,
                entry_type=prompt_name,
                word_limit=word_limit,
                split_method=split_method,
                write_file=write_file,
                send_to_model=send_to_model,
                model_name=model_ollama,
                custom_prompts=custom_prompts,
                persist_blocks=persist_blocks,
                resume_if_possible=resume_if_possible,
                source=source,
            )
        elif process_mode == "standard_note":
            logger.debug(
                f"[DEBUG] large_or_standard_note, envoie standard_note : model_ollama : {model_ollama}"
            )
            return process_standard_note(
                note_id=note_id,
                filepath=filepath,
                content=content,
                model_ollama=model_ollama,
                prompt_name=prompt_name,
                source=source,
                write_file=write_file,
                resume_if_possible=resume_if_possible,
            )
        else:
            logger.error(f"[ERREUR] Mode de traitement inconnu : {process_mode}")
            return ""
    except Exception as e:
        logger.error(f"[ERREUR] large_or_standard_note : {e}")
        return ""
