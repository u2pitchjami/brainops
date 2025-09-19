"""
# handlers/process/synthesis.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.header.headers import make_properties
from brainops.header.join_header_body import apply_to_note_body
from brainops.io.note_reader import read_note_body
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.ollama.ollama_utils import large_or_standard_note
from brainops.process_import.synthese.embeddings import make_embeddings_synthesis
from brainops.process_import.utils.archive import copy_to_archive
from brainops.process_import.utils.divers import make_relative_link
from brainops.sql.get_linked.db_get_linked_notes_utils import (
    get_file_path,
    get_parent_id,
)
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import clean_fake_code_blocks


@with_child_logger
def process_import_syntheses(
    filepath: str | Path,
    note_id: int,
    *,
    logger: LoggerProtocol | None = None,
) -> bool:
    """
    Orchestrateur de la génération de synthèse :

    - si pas de parent → copie en 'archive' et embeddings sur la note
    - sinon → embeddings sur l'archive liée
    - construit glossaire, questions, traduction FR si besoin
    - écrit le fichier final et met à jour le YAML/DB (status='synthesis')
    """
    logger = ensure_logger(logger, __name__)
    path = Path(str(filepath)).expanduser().resolve().as_posix()
    logger.info("[SYNTH] ▶️ Génération de la synthèse pour : (id=%s)", note_id)
    logger.debug("[DEBUG] +++ ▶️ SYNTHESE pour %s", path)
    try:
        parent_id = get_parent_id(note_id, logger=logger)
        logger.info("[SYNTH] Démarage Embeddings pour : (id=%s)", note_id)
        if not parent_id:
            logger.debug("[DEBUG] Pas de parent: lancement copy_to_archive")
            archive_path = copy_to_archive(path, note_id, logger=logger)
            if not archive_path:
                logger.error("[ERROR] ❌ archive_path None: abandon synthèse.")
                return False
            final_response = make_embeddings_synthesis(note_id, path, logger=logger)
        else:
            archive_path = Path(get_file_path(parent_id, logger=logger))
            logger.debug("[DEBUG] archive_path %s", archive_path)
            if not archive_path:
                raise BrainOpsError("archive_path introuvable KO", code=ErrCode.NOFILE, ctx={"note_id": note_id})
            final_response = make_embeddings_synthesis(note_id, str(archive_path), logger=logger)

        if not final_response:
            logger.error("[ERROR] ❌ final_response None: abandon synthèse.")
            return False
        logger.info("[SYNTH] 👌 Embeddings OK : (id=%s)", note_id)

        original_path = make_relative_link(archive_path, path, logger=logger)
        logger.debug("[DEBUG] original_path (relative link) : %s", original_path)
        if not original_path:
            logger.error("[ERROR] ❌ Lien synthèse - archive introuvable")
        logger.info("[SYNTH] 👌 Lien Synthèse <--> Archive OK : (id=%s)", note_id)

        logger.debug("[DEBUG] Génération du glossaire…")
        glossary = make_glossary(archive_path, note_id, logger=logger)
        if not glossary:
            logger.error("[ERROR] ❌ Glossaire KO")
        logger.info("[SYNTH] 👌 Glossaire OK : (id=%s)", note_id)

        logger.debug("[DEBUG] Génération des questions…")
        questions = make_questions(
            filepath=archive_path,
            note_id=note_id,
            content=final_response,
            logger=logger,
        )
        if not questions:
            logger.error("[ERROR] ❌ Génération des questions.")
        logger.info("[SYNTH] 👌 Questions OK : (id=%s)", note_id)

        translate_synth: str | None = None
        # note_lang = get_note_lang(note_id, logger=logger)
        # if note_lang and note_lang != "fr":
        #     logger.debug("[DEBUG] Traduction synthèse (lang=%s → fr)…", note_lang)
        #     translate_synth = make_translate(path, note_id, logger=logger)

        logger.debug("[DEBUG] Assemblage de la synthèse…")
        make_syntheses(
            filepath=path,
            note_id=note_id,
            original_path=str(original_path),
            translate_synth=translate_synth,
            glossary=glossary,
            questions=questions,
            content_lines=final_response,
            logger=logger,
        )

        logger.debug("[DEBUG] Maj propriétés (status='synthesis')…")
        make_properties(path, note_id, status="synthesis", logger=logger)

        logger.debug("[DEBUG] === ⏹️ FIN SYNTHESE pour %s", path)
        logger.info("[INFO] ✅ Synthèse terminée pour (id=%s)", note_id)
        return True

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ERREUR] Impossible de traiter %s : %s", path, exc)
        return False


@with_child_logger
def make_translate(filepath: str | Path, note_id: int, logger: LoggerProtocol | None = None) -> str | None:
    """
    make_translate _summary_

    _extended_summary_

    Args:
        filepath (str | Path): _description_
        note_id (int): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        Optional[str]: _description_
    """
    logger = ensure_logger(logger, __name__)
    prompt_key = "synth_translate"
    return large_or_standard_note(
        filepath=str(filepath),
        source="synth_translate",
        process_mode="standard_note",
        prompt_key=prompt_key,
        note_id=note_id,
        write_file=False,
        logger=logger,
    )


@with_child_logger
def make_questions(
    filepath: str | Path,
    note_id: int,
    content: str | None,
    logger: LoggerProtocol | None = None,
) -> str | None:
    """
    make_questions _summary_

    _extended_summary_

    Args:
        filepath (str | Path): _description_
        note_id (int): _description_
        content (Optional[str]): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        Optional[str]: _description_
    """
    logger = ensure_logger(logger, __name__)
    prompt_key = "add_questions"
    return large_or_standard_note(
        filepath=str(filepath),
        content=content or "",
        source="add_questions",
        process_mode="standard_note",
        prompt_key=prompt_key,
        note_id=note_id,
        write_file=False,
        logger=logger,
    )


@with_child_logger
def make_glossary(filepath: str | Path, note_id: int, logger: LoggerProtocol | None = None) -> str:
    """
    make_glossary _summary_

    _extended_summary_

    Args:
        filepath (str | Path): _description_
        note_id (int): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.

    Returns:
        str: _description_
    """
    # 1/2 : extraction brute
    logger = ensure_logger(logger, __name__)
    prompt_key = "glossaires"
    glossary_sections = large_or_standard_note(
        filepath=str(filepath),
        note_id=note_id,
        source="glossary",
        process_mode="large_note",
        prompt_key=prompt_key,
        write_file=False,
        logger=logger,
    )
    if not glossary_sections:
        # On retourne chaîne vide (le bloc sera simplement omis)
        return ""

    # 2/2 : regroupement
    prompt_key = "glossaires_regroup"
    final_glossary = large_or_standard_note(
        filepath=str(filepath),
        note_id=note_id,
        content=glossary_sections,
        source="glossary_regroup",
        process_mode="standard_note",
        prompt_key=prompt_key,
        write_file=False,
        logger=logger,
    )
    return final_glossary or ""


@with_child_logger
def make_syntheses(
    filepath: str | Path,
    note_id: int,
    original_path: str,
    translate_synth: str | None = None,
    glossary: str | None = None,
    questions: str | None = None,
    content_lines: str | None = None,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Construit le contenu final de la synthèse et l’écrit dans le fichier.

    - content_lines peut être fournis ; sinon on relit le fichier.
    """
    logger = ensure_logger(logger, __name__)
    path = Path(str(filepath)).expanduser().resolve().as_posix()

    try:
        # Lecture si besoin
        if not content_lines:
            content_lines = read_note_body(path, logger=logger)

        # Fallbacks propres
        content_lines = (content_lines or "").strip()

        # Lien vers la note originale
        original_link = f"[[{original_path}|Voir la note originale]]"

        # Blocs optionnels
        # translate_block = format_optional_block("Traduction française", translate_synth)
        glossary_block = format_optional_block("Glossaire", glossary)
        questions_block = format_optional_block("Questions", questions)

        # Assemblage
        blocks = [original_link, "", content_lines]
        # Séparateurs facultatifs
        # if translate_block:
        # blocks += ["", "---", "", translate_block]
        if glossary_block:
            blocks += ["", "---", "", glossary_block]
        if questions_block:
            blocks += ["", "---", "", questions_block]

        body_content = "\n".join(blocks).strip()
        final_body_content = clean_fake_code_blocks(body_content)
        apply_to_note_body(
            filepath=filepath,
            transform=final_body_content,
            write_file=True,
            logger=logger,
        )

    except Exception as exc:  # pylint: disable=broad-except
        # Utiliser logger global si dispo (pas de décorateur ici)
        logger.exception("[ERREUR] make_syntheses(%s) : %s", path, exc)


def format_optional_block(title: str, content: str | None) -> str:
    """
    Ajoute un titre markdown si le contenu est présent et non vide.
    """
    if content and content.strip():
        return f"## {title}\n\n{content.strip()}"
    return ""
