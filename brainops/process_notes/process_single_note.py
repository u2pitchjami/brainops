"""
# handlers/process/process_single_note.py
"""

from __future__ import annotations

import os

from brainops.models.exceptions import BrainOpsError
from brainops.process_import.gpt.gpt_imports import (
    process_class_gpt_test,
    process_import_gpt,
)
from brainops.process_import.gpt.import_test import (
    process_class_imports_test,
)
from brainops.process_import.normal.import_normal import (
    import_normal,
)
from brainops.process_import.utils.move_error_file import handle_errored_file
from brainops.process_import.utils.paths import path_is_inside
from brainops.process_notes.update_note import update_note
from brainops.process_notes.utils import should_trigger_process
from brainops.process_regen.regen_utils import (
    regen_header,
    regen_synthese_from_archive,
)
from brainops.sql.categs.db_extract_categ import categ_extract
from brainops.utils.config import (
    GPT_IMPORT_DIR,
    GPT_TEST,
    IMPORTS_PATH,
    IMPORTS_TEST,
    UNCATEGORIZED_PATH,
    Z_STORAGE_PATH,
)
from brainops.utils.files import count_words
from brainops.utils.logger import (
    LoggerProtocol,
    ensure_logger,
    with_child_logger,
)

# from brainops.watcher.queue_manager import log_event_queue


@with_child_logger
def process_single_note(
    filepath: str,
    note_id: int,
    src_path: str | None = None,
    logger: LoggerProtocol | None = None,
) -> bool:
    """
    Traite une note selon son emplacement et l'événement détecté.

    - Création/modification : import normal + synthèse si dans IMPORTS_PATH,
      sinon logique de régénération si dans Z_STORAGE_PATH, etc.
    - Déplacement : cas spécial depuis UNCATEGORIZED_PATH vers Z_STORAGE_PATH
      (force la catégorisation), ou import normal si destination dans IMPORTS_PATH.

    Args:
        filepath: Chemin absolu du fichier cible (.md attendu).
        note_id: ID de la note (en base).
        src_path: Chemin source en cas de déplacement (None sinon).

    Returns:
        True si un traitement a été déclenché, False sinon.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug(
        "=== process_single_note start | filepath=%s | note_id=%s | src=%s",
        filepath,
        note_id,
        src_path,
    )

    if not filepath.endswith(".md"):
        logger.debug("Ignoré (extension non .md) : %s", filepath)
        return False

    # Log état de la file d'événements (diagnostic)
    # log_event_queue()

    base_folder = os.path.dirname(filepath)

    # ------------------------
    # CAS DÉPLACEMENT (moved)
    # ------------------------
    if src_path is not None:
        logger.debug("Événement=move | src=%s -> dest=%s", src_path, filepath)
        if not os.path.exists(filepath):
            logger.warning(" 🚨 Fichier destination inexistant (race condition ?) : %s", filepath)
            return False

        src_folder = os.path.dirname(src_path)

        # 1) UNCATEGORIZED → Z_STORAGE : forcer la catégorisation à partir du chemin
        if path_is_inside(Z_STORAGE_PATH, base_folder) and path_is_inside(UNCATEGORIZED_PATH, src_folder):
            logger.info(
                "[MOVED] ✈️ (id=%s) : uncategorized → storage : Lancement Import",
                note_id,
            )
            try:
                importok = import_normal(filepath, note_id, force_categ=True)
                if not importok:
                    logger.warning("[WARNING] ❌ (id=%s) : Echec Import", note_id)
            except BrainOpsError as exc:
                logger.exception("[%s] %s | ctx=%r", exc.code, str(exc), exc.ctx)
                handle_errored_file(note_id, filepath, exc, logger=logger)
                return False
            logger.info("[IMPORT] ✅ (id=%s) : Import Réussi", note_id)
            return True

        # 2) Destination dans IMPORTS : import normal + synthèse
        elif path_is_inside(IMPORTS_PATH, base_folder):
            logger.info("[MOVED] ✈️ (id=%s) : → imports : Lancement Import", note_id)
            try:
                importok = import_normal(filepath, note_id, force_categ=False)
                if not importok:
                    logger.warning("[WARNING] ❌ (id=%s) : Echec Import", note_id)
            except BrainOpsError as exc:
                logger.exception("[%s] %s | ctx=%r", exc.code, str(exc), exc.ctx)
                handle_errored_file(note_id, filepath, exc, logger=logger)
                return False
            logger.info("[IMPORT] ✅ (id=%s) : Import Réussi", note_id)
            return True

        else:
            logger.info("[MOVED] ✈️ (id=%s) : %s → %s : Lancement Import", note_id, src_folder, base_folder)
            cat_name, subcat_name, _, _ = categ_extract(src_folder)
            new_cat_name, new_subcat_name, _, _ = categ_extract(base_folder)
            if not new_cat_name or not new_subcat_name:
                logger.warning(
                    "[WARN] ✈️ (id=%s) : Catégories non détectées",
                    note_id,
                )
                return False
            logger.info(
                "[MOVED] ✈️ (id=%s) : %s / %s → %s / %s",
                note_id,
                cat_name,
                subcat_name,
                new_cat_name,
                new_subcat_name,
            )
            update_note(note_id, filepath, src_path)
            return True

        # 3) Autres déplacements ignorés
        logger.info("[MOVED] 🚨 Déplacement inconnu : %s → %s", src_path, filepath)
        return False

    # ---------------------------------
    # CAS CRÉATION / MODIFICATION (no move)
    # ---------------------------------
    logger.debug("Événement=create/modify | path=%s", filepath)
    if not os.path.exists(filepath):
        logger.warning(" 🚨 Fichier inexistant (race condition ?) : %s", filepath)
        return False

    # A) Note dans IMPORTS : import normal + synthèse
    if path_is_inside(IMPORTS_PATH, base_folder):
        logger.info("[CREATED] ✨ (id=%s) : Lancement Import", note_id)
        try:
            importok = import_normal(filepath, note_id)
            if not importok:
                logger.warning("[WARNING] ❌ (id=%s) : Echec Import", note_id)
        except BrainOpsError as exc:
            logger.exception("[%s] %s | ctx=%r", exc.code, str(exc), exc.ctx)
            handle_errored_file(note_id, filepath, exc, logger=logger)
            return False
        logger.info("[IMPORT] ✅ (id=%s) : Import Réussi", note_id)
        return True

    # B) Note déjà dans le stockage : vérifier si on doit régénérer (header/synthèse)
    if path_is_inside(Z_STORAGE_PATH, base_folder):
        new_word_count: int = count_words(filepath=filepath, logger=logger)
        triggered, status, parent_id = should_trigger_process(note_id, new_word_count, logger=logger)
        logger.debug(
            "Trigger check | triggered=%s | status=%s | parent_id=%s | wc=%s",
            triggered,
            status,
            parent_id,
            new_word_count,
        )

        if not triggered:
            update_note(note_id, filepath, logger=logger)
            logger.info("[MODIFIED] ✨ (id=%s) : Aucun retraitement requis", note_id)
            return True
        logger.info("[MODIFIED] ✨ (id=%s) : Lancement Regen", note_id)
        if status == "archive":
            try:
                # On met à jour l'en-tête de l'archive, puis on relance la synthèse de sa synthèse parente
                header = regen_header(note_id, filepath, parent_id)
                if not header:
                    logger.warning(
                        "[MODIFIED] 🚨 (id=%s) : Échec de la régénération de l'en-tête",
                        note_id,
                    )
            except BrainOpsError as exc:
                logger.exception("[%s] %s | ctx=%r", exc.code, str(exc), exc.ctx)
                return False
            if parent_id is not None:
                try:
                    syntesis = regen_synthese_from_archive(note_id=parent_id)
                    if not syntesis:
                        logger.warning(
                            "[MODIFIED] 🚨 (parent_id=%s) : Échec de la régénération de la synthèse",
                            parent_id,
                        )
                except BrainOpsError as exc:
                    logger.exception("[%s] %s | ctx=%r", exc.code, str(exc), exc.ctx)
                    return False
            logger.info("[REGEN] ✅ (id=%s) : Regen Réussi", note_id)
            return True
        elif status == "synthesis":
            try:
                # On relance la synthèse directement sur ce fichier
                syntesis = regen_synthese_from_archive(note_id, filepath)
                if not syntesis:
                    logger.warning(
                        "[MODIFIED] 🚨 (id=%s) : Échec de la régénération de la synthèse",
                        note_id,
                    )
            except BrainOpsError as exc:
                logger.exception("[%s] %s | ctx=%r", exc.code, str(exc), exc.ctx)
                return False
        logger.info("[REGEN] ✅ (id=%s) : Regen Synthèse Réussi", note_id)
        return True

    # C) Fichiers dans GPT_IMPORT : split & export
    if path_is_inside(GPT_IMPORT_DIR, base_folder):
        logger.info("Fichier GPT à splitter : %s", filepath)
        try:
            process_import_gpt(filepath)
            return True
        except Exception as exc:
            logger.exception("Erreur import GPT : %s", exc)
            return False

    # D) Scénarios de test
    if path_is_inside(GPT_TEST, base_folder):
        logger.info("GPT TEST : %s", filepath)
        try:
            process_class_gpt_test(filepath, note_id)
            return True
        except Exception as exc:
            logger.exception("Erreur GPT TEST : %s", exc)
            return False

    if path_is_inside(IMPORTS_TEST, base_folder):
        logger.info("IMPORTS TEST : %s", filepath)
        try:
            process_class_imports_test(filepath, note_id)
            return True
        except Exception as exc:
            logger.exception("Erreur IMPORTS TEST : %s", exc)
            return False

    # E) Tous les autres cas : aucun traitement
    logger.info("🚨 (id=%s) Aucune règle indentifiée", note_id)
    return False
