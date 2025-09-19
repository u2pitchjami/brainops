"""
process_import.utils.standard_note.py.
"""

from __future__ import annotations

from pathlib import Path

from brainops.header.join_header_body import apply_to_note_body
from brainops.io.note_reader import read_note_body
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.ollama.ollama_call import call_ollama_with_retry
from brainops.ollama.prompts import PROMPTS
from brainops.sql.temp_blocs.db_temp_blocs import (
    get_existing_bloc,
    insert_bloc,
    update_bloc_response,
)
from brainops.utils.files import maybe_clean
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import clean_fake_code_blocks


@with_child_logger
def process_standard_note(
    note_id: int,
    filepath: str | Path,
    model_ollama: str,
    content: str | None = None,
    prompt_name: str = "import",
    source: str = "import",
    write_file: bool = True,
    resume_if_possible: bool = True,
    *,
    logger: LoggerProtocol | None = None,
) -> str:
    """
    Traite une note entière (bloc unique) et, si write_file=True, réécrit le corps via apply_to_note_body.

    Retourne la réponse brute (texte) si write_file=False, sinon None.
    """
    log = ensure_logger(logger, __name__)
    path = Path(str(filepath)).resolve()
    note_path = path.as_posix()

    # 1) Body
    if content is None:
        body = read_note_body(note_path, logger=log)
        content = maybe_clean(body)

    # 2) Prompt
    prompt_tpl = PROMPTS.get(prompt_name)
    if not prompt_tpl:
        log.error("Prompt '%s' introuvable dans PROMPTS.", prompt_name)
        raise BrainOpsError("Prompt introuvable", code=ErrCode.OLLAMA, ctx={"note_id": note_id})
    prompt = prompt_tpl.format(content=content)

    block_index = 0
    split_method = "none"
    word_limit = 0

    # 3) Resume si déjà traité
    existing = get_existing_bloc(
        note_id=note_id,
        filepath=note_path,
        block_index=block_index,
        prompt=prompt_name,
        model=model_ollama,
        split_method=split_method,
        word_limit=word_limit,
        source=source,
        logger=log,
    )
    if existing and existing[1] == "processed" and resume_if_possible:
        log.info("[SKIP] Note déjà traitée : %s", path.name)
        return existing[0].strip()

    # 4) Insert + appel LLM
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
        logger=log,
    )

    response = call_ollama_with_retry(prompt, model_ollama, logger=log) or ""
    response_clean = clean_fake_code_blocks(maybe_clean(response)).strip()

    update_bloc_response(
        note_id=note_id,
        filepath=note_path,
        block_index=block_index,
        response=response_clean,
        source=source,
        status="processed",
        logger=log,
    )

    # 5) Écriture via apply_to_note_body
    if write_file:
        join = apply_to_note_body(
            filepath=path,
            transform=response_clean,  # ou: lambda _b: response_clean si version stricte
            write_file=True,
            logger=log,
        )
        return join

    # 6) Retour "brut" compatible
    return response_clean
