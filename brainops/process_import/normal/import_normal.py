"""
# handlers/process/import_normal.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.header.headers import make_properties
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_import.get_type.by_force import get_type_by_force
from brainops.process_import.get_type.by_ollama import get_type_by_ollama
from brainops.process_import.synthese.import_synthese import (
    process_import_syntheses,
)
from brainops.process_import.utils.divers import rename_file
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.utils.config import SAV_PATH
from brainops.utils.files import copy_file_with_date
from brainops.utils.logger import get_logger

logger = get_logger("Brainops Imports")


def import_normal(filepath: str | Path, note_id: int, force_categ: bool = False) -> bool:
    """
    Étapes : 1) Définir la catégorisation (chemin cible) via process_get_note_type() 2) Renommer/déplacer le fichier
    (rename_file) 3) Mettre à jour la DB (file_path) 4) Brancher sur import_normal()

    Retourne le chemin final (str) ou None en cas d’erreur.
    """

    src = Path(str(filepath)).expanduser().resolve()
    logger.info("[INFO] ▶️ LANCEMENT IMPORT : (id=%s) path=%s", note_id, src.as_posix())
    logger.debug("[DEBUG] +++ ▶️ PRE IMPORT NORMAL pour %s", src.as_posix())

    try:
        if force_categ is False:
            # 1) classification → chemin cible (fonction existante)
            new_path = get_type_by_ollama(src.as_posix(), note_id, logger=logger)
            logger.debug("[DEBUG] pre_import_normal fin get_note_type new_path : %s", new_path)
            if not new_path:
                logger.warning("[WARN] ❌ get_note_type n'a rien renvoyé pour (id=%s)", note_id)
                return False
            # 2) rename/move (idempotent)
            moved_path = rename_file(new_path, note_id, logger=logger)
            logger.debug("[DEBUG] pre_import_normal fin rename_file : %s", moved_path)
        else:
            moved_path = Path(get_type_by_force(src.as_posix(), note_id, logger=logger))
            if not moved_path:
                logger.warning("[WARN] ❌ get_note_type n'a rien renvoyé pour (id=%s)", note_id)
                return False

        final_path = Path(str(moved_path)).expanduser().resolve().as_posix()

        # 3) mise à jour DB (file_path uniquement ici)
        updates = {"file_path": final_path}
        logger.debug("[DEBUG] pre_import_normal MAJ DB : %s", updates)
        update = update_obsidian_note(note_id, updates, logger=logger)
        if not update:
            logger.warning("[WARN] ❌ Echec de l'update pour (id=%s)", note_id)
            return False

        # Cas particulier : conversation GPT → on s'arrête là
        base_folder = Path(final_path).parent.as_posix()
        if "gpt_import" in base_folder:
            logger.info("[INFO] Conversation GPT détectée, conservée dans : %s", base_folder)
            logger.debug("[DEBUG] 🏁 FIN IMPORT GPT (id=%s)", note_id)
            return True

        # 4) Sauvegarde (optionnelle) vers SAV_PATH
        if SAV_PATH:
            try:
                copy_file_with_date(final_path, SAV_PATH, logger=logger)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("[ERREUR] Sauvegarde dans SAV_PATH échouée : %s", exc)
        else:
            logger.warning("[WARN] 🚨 SAV_PATH non défini dans utils.config, sauvegarde ignorée.")

        logger.debug("[DEBUG] import_normal : envoi vers make_properties %s", final_path)

        # 5) Traitement de l'entête
        properties = make_properties(final_path, note_id, status="archive", logger=logger)
        if not properties:
            logger.error(
                "[ERREUR] 🚨 Problème lors de la mise à jour des métadonnées pour (id=%s)",
                note_id,
            )

        # 5) Génération de la synthèse
        synthesis = process_import_syntheses(final_path, note_id, logger=logger)
        if not synthesis:
            logger.error(
                "[ERREUR] 🚨 Problème lors de la génération de la synthèse pour (id=%s)",
                note_id,
            )
            return False

        logger.info("[INFO] 🏁 IMPORT terminé pour (id=%s)", note_id)
        return True
    except BrainOpsError as exc:
        exc.with_context(
            {"step": "import_normal", "note_id": note_id, "filepath": filepath, "force_categ": force_categ}
        )
        raise
    except Exception as exc:
        raise BrainOpsError(
            "[METADATA] ❌ Definition du type par Ollama KO",
            code=ErrCode.UNEXPECTED,
            ctx={
                "step": "get_type_by_ollama",
                "note_id": note_id,
                "filepath": filepath,
                "root_exc": type(exc).__name__,
                "root_msg": str(exc),
            },
        ) from exc
