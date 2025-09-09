"""
header.yaml_read.
"""

from __future__ import annotations

from brainops.header.extract_yaml_header import extract_yaml_header
from brainops.header.header_utils import merge_yaml_header, patch_yaml_line
from brainops.utils.files import hash_file_content, read_note_content, safe_write
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import sanitize_yaml_title


@with_child_logger
def test_title(file_path: str, *, logger: LoggerProtocol | None = None) -> None:
    """
    test_title _summary_

    _extended_summary_

    Args:
        file_path (str): _description_
        logger (LoggerProtocol | None, optional): _description_. Defaults to None.
    """
    logger = ensure_logger(logger, __name__)
    try:
        header_lines, body = extract_yaml_header(file_path, logger=logger)
        if not header_lines:
            logger.debug("[DEBUG] test_title: pas d'entête YAML pour %s", file_path)
            return

        yaml_text = "\n".join(header_lines)
        corrected_yaml_text = patch_yaml_line(yaml_text, "title", sanitize_yaml_title, logger=logger)

        if corrected_yaml_text != yaml_text:
            new_content = f"{corrected_yaml_text}\n{body}"
            success = safe_write(file_path, new_content, logger=logger)
            if not success:
                logger.error("[main] Problème d’écriture sécurisée: %s", file_path)
                return
            logger.info("[INFO] Titre corrigé dans : %s", file_path)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("❌ [ERREUR] Erreur dans test_title : %s", exc)


@with_child_logger
def ensure_status_in_yaml(file_path: str, status: str = "draft", *, logger: LoggerProtocol | None = None) -> None:
    """
    Insère/Met à jour le champ 'status' dans le YAML du fichier.

    - Ne modifie rien si déjà conforme.
    - Vérifie l'écriture en s'assurant que 'status:' est bien présent.
    """
    logger = ensure_logger(logger, __name__)
    content = read_note_content(file_path, logger=logger)
    if not content:
        return
    new_content = merge_yaml_header(content, {"status": status}, logger=logger)

    if content == new_content:
        logger.debug("🔄 [DEBUG] Fichier déjà à jour (status), pas d'écriture: %s", file_path)
        return

    logger.debug("💾 [DEBUG] Écriture du fichier (status mis à jour): %s", file_path)
    success = safe_write(file_path, content=new_content, verify_contains=["status:"], logger=logger)
    if not success:
        logger.error("[main] Problème lors de l’écriture sécurisée de %s", file_path)
        return

    # Vérif d’intégrité simple (hash stable sur 1s)
    pre_hash = hash_file_content(file_path)
    import time

    time.sleep(1)
    post_hash = hash_file_content(file_path)

    if pre_hash != post_hash:
        logger.warning("⚠️ Contenu modifié entre écriture et vérification: %s", file_path)
        logger.debug("Hash écrit : %s", pre_hash)
        logger.debug("Hash 1s après : %s", post_hash)
    else:
        logger.debug("✅ Intégrité confirmée post-écriture pour %s", file_path)
