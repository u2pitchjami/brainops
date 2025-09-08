# process/gpt_imports.py
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from brainops.header.headers import make_properties
from brainops.ollama.ollama_utils import large_or_standard_note
from brainops.process_import.synthese.embeddings_utils import make_embeddings_synthesis
from brainops.process_import.utils.paths import ensure_folder_exists
from brainops.utils.config import GPT_IMPORT_DIR, GPT_OUTPUT_DIR, MODEL_FR, SAV_PATH
from brainops.utils.files import (
    clean_content,
    copy_file_with_date,
    move_file_with_date,
    read_note_content,
    safe_write,
)
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def process_clean_gpt(
    filepath: str | Path, *, logger: LoggerProtocol | None = None
) -> None:
    """
    Nettoie une note 'GPT' (content cleaning léger) et sauvegarde.
    """
    logger = ensure_logger(logger, __name__)
    path = Path(str(filepath)).resolve()
    logger.debug("[DEBUG] démarrage process_clean_gpt pour : %s", path)

    try:
        copy_file_with_date(path.as_posix(), Path(SAV_PATH), logger=logger)
        content = read_note_content(path.as_posix(), logger=logger)
        cleaned = clean_content(content)

        ok = safe_write(path.as_posix(), content=cleaned, logger=logger)
        if not ok:
            logger.error("[ERROR] Écriture sécurisée échouée pour %s", path)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[ERROR] process_clean_gpt(%s) : %s", path, exc)


@with_child_logger
def process_import_gpt(
    filepath: str | Path | None = None, *, logger: LoggerProtocol | None = None
) -> None:
    """
    Traite toutes les notes dans GPT_IMPORT_DIR, si la ligne 1 contient un titre.
    (Le paramètre 'filepath' est ignoré, conservé pour compat.)
    """
    logger = ensure_logger(logger, __name__)
    in_dir = Path(GPT_IMPORT_DIR).resolve()
    out_dir = Path(GPT_OUTPUT_DIR).resolve()

    ensure_folder_exists(in_dir, logger=logger)
    ensure_folder_exists(out_dir, logger=logger)

    logger.info("[INFO] GPT import → in=%s | out=%s", in_dir, out_dir)

    processed = 0
    ignored = 0

    for file in in_dir.glob("*.md"):
        try:
            if is_ready_for_split(file):
                logger.info("[INFO] Traitement : %s", file.name)
                process_gpt_conversation(
                    file, out_dir, prefix="GPT_Conversation", logger=logger
                )
                processed += 1
                # Archivage dans SAV_PATH
                move_file_with_date(file.as_posix(), SAV_PATH, logger=logger)
            else:
                logger.info("[INFO] Ignorée (pas de titre en ligne 1) : %s", file.name)
                ignored += 1
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("[ERROR] Fichier %s : %s", file, exc)

    logger.info(
        "[INFO] GPT import terminé — traités=%d | ignorés=%d", processed, ignored
    )


def is_ready_for_split(filepath: str | Path) -> bool:
    """
    True si la 1re ligne commence par '# '.
    """
    path = Path(str(filepath))
    try:
        with path.open("r", encoding="utf-8") as f:
            first_line = (f.readline() or "").strip()
        return first_line.startswith("# ")
    except FileNotFoundError:
        return False


@with_child_logger
def process_gpt_conversation(
    filepath: str | Path,
    output_dir: str | Path,
    *,
    prefix: str = "GPT_Conversation",
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Découpe une conversation GPT (titres '# ') en sections et crée 1 fichier par section.
    """
    logger = ensure_logger(logger, __name__)
    src = Path(str(filepath)).resolve()
    out = Path(str(output_dir)).resolve()

    if not is_ready_for_split(src):
        logger.debug("[DEBUG] Ignorée (pas de titre en ligne 1) : %s", src)
        return

    content = read_note_content(src.as_posix(), logger=logger)
    sections = split_gpt_conversation(content)
    ensure_folder_exists(out, logger=logger)

    for title, body in sections:
        safe_title = re.sub(r"[^\w\s-]", "_", title).strip()
        filename = f"{prefix}_{safe_title}.md"
        dst = out / filename
        # On ajoute un titre H1 au début du fichier
        text = f"# {title}\n\n{body}"
        ok = safe_write(dst.as_posix(), content=text, logger=logger)
        if not ok:
            logger.error("[ERROR] Écriture section échouée : %s", dst)


def split_gpt_conversation(content: str) -> List[Tuple[str, str]]:
    """
    Découpe une conversation GPT en sections basées sur les titres de niveau '# '.
    Retourne [(title, body), ...].
    """
    # Répartition par titres capturés : ["pre", title1, body1, title2, body2, ...]
    parts = re.split(r"(?m)^# (.+)$", content)
    results: List[Tuple[str, str]] = []
    for i in range(1, len(parts), 2):
        title = (parts[i] or "").strip()
        body = (parts[i + 1] or "").strip()
        results.append((title, body))
    return results


@with_child_logger
def process_class_gpt(
    filepath: str | Path, note_id: int, *, logger: LoggerProtocol | None = None
) -> None:
    """
    Pipeline de "reformulation" pour une note GPT :
      - nettoyage via process_large_note (entry_type='gpt_reformulation')
      - extraction de mots-clés (process_and_update_file)
      - properties YAML + DB (status='archive')
    """
    logger = ensure_logger(logger, __name__)
    path = Path(str(filepath)).resolve()
    logger.info("[INFO] process_class_gpt : %s", path)

    # Reformulation (1 passage suffit)
    large_or_standard_note(
        note_id=note_id,
        filepath=path.as_posix(),
        prompt_name="gpt_reformulation",
        model_ollama=MODEL_FR,
        source="other",
        logger=logger,
    )

    # Mots-clés + update éventuelle
    # process_and_update_file(path.as_posix())

    # Finalisation YAML / DB
    make_properties(path.as_posix(), note_id, status="archive", logger=logger)


@with_child_logger
def process_class_gpt_test(
    filepath: str | Path, note_id: int, *, logger: LoggerProtocol | None = None
) -> None:
    """
    Variante de test :
      - duplique le fichier pour différents modèles,
      - reformulation,
      - génère une synthèse via embeddings,
      - sauvegarde la synthèse dans le fichier.
    """
    logger = ensure_logger(logger, __name__)
    src = Path(str(filepath)).resolve()
    dest_dir = Path(
        "/mnt/user/Documents/Obsidian/notes/Z_technical/test_output_gpt/"
    ).resolve()
    ensure_folder_exists(dest_dir, logger=logger)

    filename = src.name
    models = ["llama3.1:8b-instruct-q8_0"]  # liste de modèles à tester

    for model in models:
        safe_model = re.sub(r'[\/:*?"<>|]', "_", model)
        first_copy = dest_dir / f"{src.stem}_{safe_model}{src.suffix}"
        second_copy = dest_dir / f"{src.stem}_{safe_model}_suite{src.suffix}"

        try:
            copied_1 = shutil.copy(src.as_posix(), first_copy.as_posix())
            logger.debug("[DEBUG] Copie 1 : %s", copied_1)
            large_or_standard_note(
                note_id=note_id,
                filepath=first_copy.as_posix(),
                prompt_name="clean_gpt",
                word_limit=500,
                model_ollama=model,
                source="other",
                logger=logger,
            )

            copied_2 = shutil.copy(first_copy.as_posix(), second_copy.as_posix())
            logger.debug("[DEBUG] Copie 2 : %s", copied_2)

            final_response = make_embeddings_synthesis(
                note_id, second_copy.as_posix(), logger=logger
            )
            safe_write(
                second_copy.as_posix(), content=final_response or "", logger=logger
            )

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "[ERROR] process_class_gpt_test(%s, %s) : %s", src, model, exc
            )
