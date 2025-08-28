import logging
from pathlib import Path

from brainops.obsidian_scripts.handlers.header.extract_yaml_header import (
    extract_yaml_header,
)
from brainops.obsidian_scripts.handlers.ollama.ollama_call import call_ollama_with_retry
from brainops.obsidian_scripts.handlers.ollama.prompts import PROMPTS
from brainops.obsidian_scripts.handlers.sql.db_temp_blocs import (
    get_existing_bloc,
    insert_bloc,
    update_bloc_response,
)
from brainops.obsidian_scripts.handlers.utils.files import (
    join_yaml_and_body,
    maybe_clean,
    safe_write,
)
from brainops.obsidian_scripts.handlers.utils.normalization import (
    clean_fake_code_blocks,
)

logger = logging.getLogger("obsidian_notes." + __name__)


def process_standard_note(
    note_id,
    filepath: str | Path,
    content: str = None,
    model_ollama: str = None,
    prompt_name: str = "import",
    source: str = "import",
    write_file=True,
    resume_if_possible: bool = True,
) -> str:
    """
    Traite une note entière sans découpage (bloc unique).
    Vérifie si déjà traité avant d'appeler Ollama.

    :param filepath: chemin de la note à traiter
    :param model_ollama: nom du modèle IA (ex: "llama3")
    :param entry_type: clé de prompt dans PROMPTS
    :param source: identifiant logique du traitement (ex: "import")
    :param resume_if_possible: si True, récupère la réponse si elle existe déjà
    :return: réponse finale (déjà traitée ou nouvelle)
    """
    try:
        logger.debug(f"[DEBUG] process_standard_note model_ollama : {model_ollama}")
        filepath = Path(filepath).resolve()
        if not content:
            header_lines, content_lines = extract_yaml_header(filepath)
            content = maybe_clean(content_lines)

        prompt_template = PROMPTS.get(prompt_name)
        if not prompt_template:
            raise ValueError(f"Prompt '{prompt_name}' introuvable dans PROMPTS.")
        prompt = prompt_template.format(content=content)

        logger.debug(f"[PROMPT] Généré pour {filepath.name} : {prompt}...")

        note_path = str(filepath)
        block_index = 0
        split_method = "none"
        word_limit = 0

        # Vérification si bloc déjà traité
        existing = get_existing_bloc(
            note_id=note_id,
            filepath=note_path,
            block_index=block_index,
            prompt=prompt_name,
            model=model_ollama,
            split_method=split_method,
            word_limit=word_limit,
            source=source,
        )

        if existing and existing[1] == "processed" and resume_if_possible:
            logger.info(f"[SKIP] Note déjà traitée : {filepath.name}")
            return existing[0].strip()

        # Sinon : insertion + traitement
        insert_bloc(
            note_id=note_id,
            filepath=note_path,
            block_index=block_index,
            content=content,
            prompt=prompt_name,
            model=model_ollama,
            split_method=split_method,
            word_limit=word_limit,
            source=source,
        )
        response = call_ollama_with_retry(prompt, model_ollama)
        logger.debug(f"Type response: {type(response)}")
        logger.debug(f"[DEBUG] response : {response}")
        update_bloc_response(
            note_id,
            note_path,
            block_index,
            response.strip(),
            source,
            status="processed",
        )

        if write_file:
            final_body_content = clean_fake_code_blocks(maybe_clean(response))
            logger.debug(f"[DEBUG] final_body_content : {final_body_content[:200]}")
            final_content = join_yaml_and_body(header_lines, final_body_content)
            success = safe_write(filepath, content=final_content)
            if not success:
                logger.error(f"[main] Problème lors de l’écriture de {filepath}")
            else:
                logger.info(f"[INFO] Note enregistrée : {filepath}")
                logger.debug(f"[DEBUG] Contenu Final : {response}")
        else:
            return response.strip()

    except Exception as e:
        logger.error(f"[ERROR] Traitement échoué pour {filepath} : {e}")
        raise
