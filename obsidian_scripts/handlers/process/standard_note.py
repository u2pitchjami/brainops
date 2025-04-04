from logger_setup import setup_logger
from pathlib import Path
from handlers.ollama.ollama import call_ollama_with_retry
from handlers.header.extract_yaml_header import extract_yaml_header
from handlers.ollama.prompts import PROMPTS
from handlers.sql.db_temp_blocs import (
    insert_bloc,
    update_bloc_response,
    get_existing_bloc
)
import logging

setup_logger("standard_note")
logger = logging.getLogger("standard_note")

def process_standard_note(filepath: str | Path, model_ollama: str = None, prompt_name: str = "import", source: str = "import", resume_if_possible: bool = True) -> str:
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
        filepath = Path(filepath).resolve()
        header_lines, content_lines = extract_yaml_header(filepath)
        content = content_lines

        prompt_template = PROMPTS.get(prompt_name)
        if not prompt_template:
            raise ValueError(f"Prompt '{prompt_name}' introuvable dans PROMPTS.")
        prompt = prompt_template.format(content=content)
        
        logger.debug(f"[PROMPT] Généré pour {filepath.name} : {prompt[:2000]}...")

        note_path = str(filepath)
        block_index = 0
        split_method = "none"
        word_limit = 0

        # Vérification si bloc déjà traité
        existing = get_existing_bloc(
            filepath=note_path,
            block_index=block_index,
            prompt=prompt_name,
            model=model_ollama,
            split_method=split_method,
            word_limit=word_limit,
            source=source
        )

        if existing and existing[1] == "processed" and resume_if_possible:
            logger.info(f"[SKIP] Note déjà traitée : {filepath.name}")
            return existing[0].strip()

        # Sinon : insertion + traitement
        insert_bloc(
            filepath=note_path,
            block_index=block_index,
            content=content,
            prompt=prompt_name,
            model=model_ollama,
            split_method=split_method,
            word_limit=word_limit,
            source=source
        )
        response = call_ollama_with_retry(prompt, model_ollama)

        update_bloc_response(note_path, block_index, response.strip(), source, status="processed")

        return response.strip()

    except Exception as e:
        logger.error(f"[ERROR] Traitement échoué pour {filepath} : {e}")
        raise
