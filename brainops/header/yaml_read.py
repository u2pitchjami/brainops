"""
header.yaml_read.
"""

from __future__ import annotations

from brainops.header.header_utils import merge_yaml_header
from brainops.io.note_reader import read_metadata_field
from brainops.io.note_writer import update_yaml_field
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.types import StrOrPath
from brainops.utils.files import hash_file_content, read_note_content, safe_write
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import sanitize_yaml_title


@with_child_logger
def test_title(file_path: StrOrPath, *, logger: LoggerProtocol | None = None) -> bool:
    """
    Vérifie/corrige le champ YAML 'title' d'une note.
    - Lit uniquement la valeur 'title' depuis l'entête.
    - Si la version normalisée diffère, met à jour l'entête (champ unique).

    Returns:
        bool: True si OK (déjà propre ou correction faite), False si échec I/O.
    """
    logger = ensure_logger(logger, __name__)
    try:
        current = read_metadata_field(file_path, "title", logger=logger)

        if current is None or not current:
            logger.debug("[test_title] Pas de champ 'title' pour %s", file_path)
            raise BrainOpsError("Note sans titre", code=ErrCode.METADATA, ctx={"path": file_path})

        sanitized = sanitize_yaml_title(str(current))

        if str(current) == sanitized:
            logger.debug("[test_title] Titre déjà conforme pour %s: %r", file_path, current)
            return False

        # Écrit uniquement le champ 'title' (YAML merge interne)
        if update_yaml_field(file_path, "title", sanitized, logger=logger):
            logger.info("[test_title] Titre corrigé pour %s: %r -> %r", file_path, current, sanitized)
            return True
    except FileNotFoundError as exc:  # pylint: disable=broad-except
        raise BrainOpsError(
            "Note absente !!",
            code=ErrCode.NOFILE,
            ctx={"path": file_path},
        ) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise BrainOpsError(
            "Erreur inattendue exécutrice",
            code=ErrCode.UNEXPECTED,
            ctx={"path": file_path},
        ) from exc


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
