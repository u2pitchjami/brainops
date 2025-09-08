from __future__ import annotations

from pathlib import Path
from typing import Optional

from brainops.header.extract_yaml_header import extract_yaml_header
from brainops.ollama.ollama_call import call_ollama_with_retry
from brainops.ollama.prompts import PROMPTS
from brainops.sql.notes.db_temp_blocs import (
    get_existing_bloc,
    insert_bloc,
    update_bloc_response,
)
from brainops.utils.files import join_yaml_and_body, maybe_clean, safe_write
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import clean_fake_code_blocks


@with_child_logger
def process_standard_note(
    note_id: int | None,
    filepath: str | Path,
    content: Optional[str] = None,
    model_ollama: Optional[str] = None,
    prompt_name: str = "import",
    source: str = "import",
    write_file: bool = True,
    resume_if_possible: bool = True,
    *,
    logger: LoggerProtocol | None = None,
) -> str | None:
    """
    Traite une note entière sans découpage (bloc unique).
    - Vérifie si déjà traité (obsidian_temp_blocks) si resume_if_possible=True.
    - Retourne la réponse si write_file=False, sinon None.
    """
    logger = ensure_logger(logger, __name__)
    path = Path(str(filepath)).resolve()
    header_lines, content_lines = extract_yaml_header(path.as_posix(), logger=logger)

    if content is None:
        content = maybe_clean(content_lines)

    prompt_tpl = PROMPTS.get(prompt_name)
    if not prompt_tpl:
        logger.error("Prompt '%s' introuvable dans PROMPTS.", prompt_name)
        return None
    prompt = prompt_tpl.format(content=content)

    note_path = path.as_posix()
    block_index = 0
    split_method = "none"
    word_limit = 0

    # Vérifier si déjà traité
    existing = get_existing_bloc(
        note_id=note_id,
        filepath=note_path,
        block_index=block_index,
        prompt=prompt_name,
        model=model_ollama,
        split_method=split_method,
        word_limit=word_limit,
        source=source,
        logger=logger,
    )
    if existing and existing[1] == "processed" and resume_if_possible:
        logger.info("[SKIP] Note déjà traitée : %s", path.name)
        return existing[0].strip()

    # Insérer le bloc puis traiter
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
        logger=logger,
    )

    response = call_ollama_with_retry(prompt, model_ollama, logger=logger) or ""
    update_bloc_response(
        note_id=note_id,
        filepath=note_path,
        block_index=block_index,
        response=response.strip(),
        source=source,
        status="processed",
        logger=logger,
    )

    if write_file:
        final_body = clean_fake_code_blocks(maybe_clean(response))
        final_content = join_yaml_and_body(header_lines, final_body)
        success = safe_write(path.as_posix(), content=str(final_content), logger=logger)
        if not success:
            logger.error("[main] Problème lors de l’écriture de %s", note_path)
        else:
            logger.info("[INFO] Note enregistrée : %s", note_path)
        return None

    return response.strip()
