from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from brainops.header.extract_yaml_header import extract_yaml_header
from brainops.ollama.ollama_call import OllamaError, call_ollama_with_retry
from brainops.ollama.prompts import PROMPTS
from brainops.sql.notes.db_temp_blocs import (
    get_existing_bloc,
    insert_bloc,
    mark_bloc_as_error,
    update_bloc_response,
)
from brainops.utils.config import MODEL_LARGE_NOTE
from brainops.utils.files import join_yaml_and_body, maybe_clean, safe_write
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import clean_fake_code_blocks


def determine_max_words(filepath: str | Path) -> int:
    """
    Détermine dynamiquement la taille des blocs en fonction du fichier.
    """
    fp = str(filepath).lower()
    return 1000 if "gpt_import" in fp else 1000


def split_large_note(content: str, max_words: int = 1000) -> List[str]:
    """
    Découpe une note en blocs de taille optimale (max_words).
    """
    words = content.split()
    blocks: List[str] = []
    current_block: List[str] = []

    for word in words:
        current_block.append(word)
        if len(current_block) >= max_words:
            blocks.append(" ".join(current_block))
            current_block = []

    if current_block:
        blocks.append(" ".join(current_block))
    return blocks


@with_child_logger
def process_large_note(
    note_id: int | None,
    filepath: str | Path,
    entry_type: str | None = None,
    word_limit: int = 1000,
    split_method: str = "titles_and_words",
    write_file: bool = True,
    send_to_model: bool = True,
    model_name: str | None = None,
    custom_prompts: Dict[str, str] | None = None,
    persist_blocks: bool = True,
    resume_if_possible: bool = True,
    source: str = "normal",
    *,
    logger: LoggerProtocol | None = None,
) -> str | None:
    """
    Traite une note volumineuse (split + appel LLM par bloc).
    Si persist_blocks=True, chaque bloc est stocké en base dans `obsidian_temp_blocks`.
    Retourne le contenu final (si write_file=False), sinon None.
    """
    logger = ensure_logger(logger, __name__)
    path = Path(str(filepath)).resolve()
    model_ollama = model_name or MODEL_LARGE_NOTE

    if not entry_type and not custom_prompts:
        logger.error(
            "[ERROR] Aucun 'entry_type' (clé PROMPTS) ni 'custom_prompts' fournis."
        )
        return None

    try:
        header_lines, content_lines = extract_yaml_header(
            path.as_posix(), logger=logger
        )
        logger.debug("[DEBUG] content_lines extrait : %s", content_lines)
        content = maybe_clean(content_lines)
        logger.debug("[DEBUG] content nettoyé : %s", content)

        # Choix de la méthode de split
        if split_method == "titles_and_words":
            blocks = split_large_note_by_titles_and_words(
                content, word_limit=word_limit
            )
            logger.debug("[DEBUG] blocks extrait : %s", blocks)
        elif split_method == "titles":
            blocks = split_large_note_by_titles(content)
        elif split_method == "words":
            blocks = split_large_note(content, max_words=word_limit)
        else:
            logger.error("[ERROR] Méthode de split inconnue : %s", split_method)
            return None

        logger.info("[INFO] Note découpée en %d blocs", len(blocks))
        processed_blocks: List[str] = []

        for i, block in enumerate(blocks):
            logger.debug("[DEBUG] Bloc %d/%d", i + 1, len(blocks))
            block_index = i

            # Vérifie si déjà traité (si persistance active)
            if persist_blocks:
                try:
                    row = get_existing_bloc(
                        note_id=note_id,
                        filepath=path.as_posix(),
                        block_index=block_index,
                        prompt=entry_type or "",  # ok si custom_prompts
                        model=model_ollama,
                        split_method=split_method,
                        word_limit=word_limit,
                        source=source,
                        logger=logger,
                    )
                    if row:
                        response, status = row
                        if status == "processed" and resume_if_possible:
                            logger.debug("[DEBUG] Bloc %d déjà traité, skip", i)
                            if isinstance(response, list):
                                response = "\n".join(map(str, response))
                            elif not isinstance(response, str):
                                response = str(response)
                            processed_blocks.append(response.strip())
                            continue
                    else:
                        insert_bloc(
                            note_id=note_id,
                            filepath=Path(path).as_posix(),
                            block_index=block_index,
                            content=block,
                            prompt=entry_type or "",
                            model=model_ollama,
                            split_method=split_method,
                            word_limit=word_limit,
                            source=source,
                            logger=logger,
                        )
                except Exception as exc:  # pylint: disable=broad-except
                    logger.exception("[ERROR] Insertion bloc %d échouée : %s", i, exc)

            # Traitement du bloc
            response: str | list | None = block
            if send_to_model:
                # Sélection du prompt
                if custom_prompts:
                    if i == 0 and "first" in custom_prompts:
                        prompt = custom_prompts["first"].format(content=block)
                    elif i == len(blocks) - 1 and "last" in custom_prompts:
                        prompt = custom_prompts["last"].format(content=block)
                    else:
                        prompt = custom_prompts.get(
                            "middle", PROMPTS.get(entry_type, "{content}")
                        ).format(content=block)
                else:
                    prompt_tpl = PROMPTS.get(entry_type or "")
                    if not prompt_tpl:
                        logger.error(
                            "[ERROR] Prompt '%s' introuvable dans PROMPTS.", entry_type
                        )
                        prompt = block  # fallback minimal
                    else:
                        prompt = prompt_tpl.format(content=block)

                try:
                    response = call_ollama_with_retry(
                        prompt, model_ollama, logger=logger
                    )
                except OllamaError:
                    logger.error("[ERROR] Échec du bloc %d, saut…", i + 1)
                    if persist_blocks:
                        mark_bloc_as_error(path.as_posix(), block_index, logger=logger)
                    continue

            # Normalisation de la réponse
            if source == "embeddings":
                # response devrait être une list[float] renvoyée par get_embedding()
                if isinstance(response, list):
                    response = json.dumps(response)  # OK: on stocke un JSON array
                elif isinstance(response, str):
                    s = response.strip()
                    if s.startswith("[") and s.endswith("]"):
                        # déjà un JSON array → on le garde tel quel
                        response = s
                    else:
                        # on essaie de normaliser proprement
                        try:
                            parsed = json.loads(s)
                            if isinstance(parsed, list):
                                response = json.dumps(parsed)
                            else:
                                response = "null"
                        except Exception:
                            response = "null"
            else:
                if isinstance(response, list):
                    response = "\n".join(map(str, response))
                elif not isinstance(response, str):
                    response = str(response)

            if persist_blocks:
                update_bloc_response(
                    note_id=note_id,
                    filepath=path.as_posix(),
                    block_index=block_index,
                    response=response or "",
                    source=source,
                    status="processed",
                    logger=logger,
                )

            processed_blocks.append((response or "").strip())

        # Titre de secours par bloc si manquant
        final_blocks = ensure_titles_in_blocks(processed_blocks)

        # ✅ Correction: on assemble en texte puis nettoyage
        blocks_text = "\n\n".join(final_blocks)
        final_body_content = clean_fake_code_blocks(maybe_clean(blocks_text))
        final_content = join_yaml_and_body(header_lines, final_body_content)

        if write_file:
            success = safe_write(
                path.as_posix(), content=str(final_content), logger=logger
            )
            if not success:
                logger.error(
                    "[main] Problème lors de l’écriture de %s", path.as_posix()
                )
            else:
                logger.info("[INFO] Note enregistrée : %s", path.as_posix())
            return None

        return str(final_content)

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ERREUR] Traitement de %s échoué : %s", path.as_posix(), exc)
        return None


def split_large_note_by_titles(content: str) -> List[str]:
    """
    Découpe en blocs basés sur les titres (#, ##, ###), gère l'intro avant le 1er titre.
    Chaque bloc contient le titre et son contenu.
    """
    title_pattern = r"(?m)^(\#{1,3})\s+.*$"
    matches = list(re.finditer(title_pattern, content))

    blocks: List[str] = []
    if matches:
        if matches[0].start() > 0:
            intro = content[: matches[0].start()].strip()
            if intro:
                blocks.append("## **Introduction**\n\n" + intro)

        for i, match in enumerate(matches):
            title = match.group().strip()
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos].strip()
            blocks.append(f"{title}\n{section_content}")
    else:
        intro = content.strip()
        if intro:
            blocks.append("## **Introduction**\n\n" + intro)

    return blocks


def split_large_note_by_titles_and_words(
    content: str, word_limit: int = 1000
) -> List[str]:
    """
    Découpe par titres, puis regroupe en paquets ≤ word_limit mots, sans briser les sections.
    """
    title_pattern = r"(?m)^(\#{1,5})\s+.*$"
    matches = list(re.finditer(title_pattern, content))

    blocks: List[str] = []
    temp_block: List[str] = []
    word_count = 0

    def add_block() -> None:
        if temp_block:
            blocks.append("\n\n".join(temp_block))
            temp_block.clear()

    if matches:
        if matches[0].start() > 0:
            intro = content[: matches[0].start()].strip()
            if intro:
                temp_block.append("## **Introduction**\n\n" + intro)
                word_count += len(intro.split())

        for i, match in enumerate(matches):
            title = match.group().strip()
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos].strip()
            section_words = len(section_content.split())

            if word_count + section_words > word_limit:
                add_block()
                word_count = 0

            temp_block.append(f"{title}\n{section_content}")
            word_count += section_words

        add_block()
    else:
        intro = content.strip()
        if intro:
            blocks.append("## **Introduction**\n" + intro)

    return blocks


def ensure_titles_in_blocks(
    blocks: Sequence[str], default_title: str = "# Introduction"
) -> List[str]:
    """
    S'assure que chaque bloc commence par un titre Markdown ; sinon en ajoute un.
    """
    processed: List[str] = []
    for i, block in enumerate(blocks):
        b = (block or "").strip()
        if not b.startswith("#"):
            title = default_title if i == 0 else f"# Section {i + 1}"
            b = f"{title}\n{b}"
        processed.append(b)
    return processed


def ensure_titles_in_initial_content(
    blocks: Sequence[str], default_title: str = "# Introduction"
) -> List[str]:
    """
    Variante (compat) — même logique que ensure_titles_in_blocks.
    """
    return ensure_titles_in_blocks(blocks, default_title=default_title)
