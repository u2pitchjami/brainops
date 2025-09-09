"""# process/imports_test.py"""

from __future__ import annotations

from pathlib import Path
import re
import shutil

from brainops.header.extract_yaml_header import extract_yaml_header
from brainops.process_import.utils.large_note import process_large_note
from brainops.process_import.utils.standard_note import process_standard_note
from brainops.utils.config import OUTPUT_TESTS_IMPORTS_DIR
from brainops.utils.files import join_yaml_and_body, safe_write
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def process_class_imports_test(filepath: str | Path, note_id: int, *, logger: LoggerProtocol | None = None) -> None:
    """
    Duplique un fichier source dans un répertoire de tests, applique plusieurs
    passes (reformulations/synthèses), puis assemble la dernière sortie avec le YAML existant.
    """
    logger = ensure_logger(logger, __name__)
    src = Path(str(filepath)).resolve()
    dest_dir = Path(OUTPUT_TESTS_IMPORTS_DIR).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[INFO] Démarrage imports_test pour : %s", src.name)

    # Liste de modèles à tester (identiques à ta version d'origine)
    models = [
        "mistral:7B-Instruct",
        "mistral:latest",
        "llama3:8b-instruct-q6_K",
        "llama-summary-gguf:latest",
        "qwen2.5:7b",
        "llama-chat-summary-3.2-3b:latest",
        "llama3.2-vision:11b",
        "deepseek-r1:14b",
        "llama3.2:latest",
    ]

    for model in models:
        try:
            logger.debug("[DEBUG] Modèle : %s", model)
            safe_model = re.sub(r'[\/:*?"<>|]', "_", model)

            # Copie 1
            new_filename1 = f"{src.stem}_{safe_model}{src.suffix}"
            dst1 = dest_dir / new_filename1
            shutil.copy(src.as_posix(), dst1.as_posix())
            logger.debug("[DEBUG] Copie → %s", dst1.name)

            # Pass 1
            process_large_note(
                note_id=note_id,
                filepath=dst1.as_posix(),
                entry_type="reformulation2",
                model_name=model,
                source="other1",
                logger=logger,
            )

            # Copie 2
            new_filename2 = f"{dst1.stem}_synt1{dst1.suffix}"
            dst2 = dest_dir / new_filename2
            shutil.copy(dst1.as_posix(), dst2.as_posix())

            # Pass 2
            process_large_note(
                note_id=note_id,
                filepath=dst2.as_posix(),
                entry_type="divers",
                model_name=model,
                source="other2",
                logger=logger,
            )

            # Copie 3
            new_filename3 = f"{dst1.stem}_synt2{dst1.suffix}"
            dst3 = dest_dir / new_filename3
            shutil.copy(dst2.as_posix(), dst3.as_posix())

            # Extraction YAML existant pour réassemblage
            header_lines, _ = extract_yaml_header(dst3.as_posix(), logger=logger)

            # Synthèse finale standard (sans écriture automatique)
            response = process_standard_note(
                note_id=note_id,
                filepath=dst3.as_posix(),
                model_ollama=model,
                prompt_name="synthese2",
                source="other3",
                resume_if_possible=True,
                write_file=False,
                logger=logger,
            )

            if response is None:
                logger.error("[ERROR] Aucune réponse générée pour %s", dst3.name)
                continue

            body_content = response.strip()
            final_content = join_yaml_and_body(header_lines, body_content)
            logger.debug("[DEBUG] Contenu final généré (%s) : %s", dst3.name, final_content[:800])

            ok = safe_write(dst3.as_posix(), content=final_content, logger=logger)
            if not ok:
                logger.error("[ERROR] Échec écriture finale : %s", dst3.name)

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("[ERROR] Échec sur le modèle %s : %s", model, exc)
