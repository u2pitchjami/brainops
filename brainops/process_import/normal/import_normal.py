"""
# handlers/process/import_normal.py
"""

from __future__ import annotations

from pathlib import Path

from brainops.header.headers import make_properties
from brainops.io.note_reader import read_note_full
from brainops.io.paths import exists, remove_file
from brainops.io.utils import count_words
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.models.metadata import NoteMetadata
from brainops.ollama.check_ollama import check_ollama_health
from brainops.process_folders.folders import ensure_folder_exists
from brainops.process_import.get_type.by_ollama import get_type_by_ollama
from brainops.process_import.join.join_header_body import join_header_body
from brainops.process_import.synthese.import_synthese import (
    process_import_syntheses,
)
from brainops.process_import.utils.archive import build_archive_path, build_synthesis_path
from brainops.process_import.utils.divers import rename_file
from brainops.sql.get_linked.db_get_linked_folders_utils import get_category_context_from_folder
from brainops.sql.notes.db_update_notes import update_obsidian_note, update_obsidian_tags
from brainops.utils.config import SAV_PATH
from brainops.utils.files import clean_content, copy_file_with_date
from brainops.utils.logger import get_logger

logger = get_logger("Brainops Imports")


def import_normal(filepath: str | Path, note_id: int, force_categ: bool = False) -> bool:
    """
    Étapes : 1) Définir la catégorisation (chemin cible) via process_get_note_type() 2) Renommer/déplacer le fichier
    (rename_file) 3) Mettre à jour la DB (file_path) 4) Brancher sur import_normal()

    Retourne le chemin final (str) ou None en cas d’erreur.
    """

    src = Path(filepath)
    name = src.stem
    suffix = src.suffix
    base_folder = src.parent.as_posix()
    logger.info("[INFO] ▶️ LANCEMENT IMPORT : (id=%s) path=%s", note_id, src.as_posix())
    logger.debug("[DEBUG] +++ ▶️ PRE IMPORT NORMAL pour %s", src.as_posix())

    try:
        logger.info("[INFO] Vérification de l'état d'Ollama...")
        check = check_ollama_health(logger=logger)
        if not check:
            logger.error("[ERREUR] 🚨 Ollama ne répond pas, import annulé pour (id=%s)", note_id)
            raise BrainOpsError(
                "[IMPORT] ❌ Check Ollama KO",
                code=ErrCode.OLLAMA,
                ctx={"step": "import_normal", "note_id": note_id, "filepath": filepath},
            )
        meta_yaml, body = read_note_full(src, logger=logger)
        content = clean_content(body)
        wc = count_words(content)
        if force_categ is False:
            # 1) classification → chemin cible (fonction existante)
            classification = get_type_by_ollama(content, note_id, logger=logger)
            if not classification:
                logger.warning("[WARN] ❌ get_note_type n'a rien renvoyé pour (id=%s)", note_id)
                raise BrainOpsError(
                    "[IMPORT] ❌ Definition du type par Ollama KO",
                    code=ErrCode.METADATA,
                    ctx={"step": "import_normal", "note_id": note_id, "filepath": filepath},
                )
        else:
            classification = get_category_context_from_folder(base_folder, logger=logger)
            if not classification:
                logger.warning("[WARN] ❌ get_note_type n'a rien renvoyé pour (id=%s)", note_id)
                raise BrainOpsError(
                    "[IMPORT] ❌ Echec de la classification forcée",
                    code=ErrCode.METADATA,
                    ctx={"step": "import_normal", "note_id": note_id, "filepath": filepath},
                )
        logger.debug(f"classification : {classification}")
        # Cas particulier : conversation GPT → on s'arrête là
        if "gpt_import" in base_folder:
            logger.info("[INFO] Conversation GPT détectée, conservée dans : %s", base_folder)
            logger.debug("[DEBUG] 🏁 FIN IMPORT GPT (id=%s)", note_id)
            return True

        logger.debug("[DEBUG] import_normal : envoi vers make_properties")
        # 5) Traitement de l'entête
        meta_final: NoteMetadata = make_properties(
            content=content,
            meta_yaml=meta_yaml,
            classification=classification,
            note_id=note_id,
            status="archive",
            logger=logger,
        )
        if not meta_final:
            logger.error(
                "[ERREUR] 🚨 Problème lors de la mise à jour des métadonnées pour (id=%s)",
                note_id,
            )
        logger.debug(f"meta_final : {meta_final}")
        # 2) rename
        new_name = rename_file(name=name, created=meta_final.created, note_id=note_id, logger=logger)

        # 3) build Archive path
        archive_path = build_archive_path(
            original_path=classification.dest_folder, original_name=new_name, suffix=suffix
        )
        synthesis_path = build_synthesis_path(
            original_path=classification.dest_folder, original_name=new_name, suffix=suffix
        )

        # 4) verif presence dossiers
        ensure_folder_exists(folder_path=archive_path.parent.as_posix(), logger=logger)
        ensure_folder_exists(folder_path=synthesis_path.parent.as_posix(), logger=logger)

        updates = {
            "file_path": str(archive_path),
            "category_id": classification.category_id,
            "subcategory_id": classification.subcategory_id,
            "status": "archive",
            "folder_id": classification.folder_id,
            "summary": meta_final.summary,
            "word_count": wc,
        }
        update_obsidian_note(note_id, updates)
        update_obsidian_tags(note_id, tags=meta_final.tags, logger=logger)

        archive_def = join_header_body(
            body=content, meta_yaml=meta_final, filepath=archive_path, write_file=True, logger=logger
        )
        if not archive_def:
            logger.error(
                "[ERREUR] 🚨 Problème lors de l'enregistrement de l'archive (id=%s)",
                note_id,
            )
            raise BrainOpsError(
                "[IMPORT] ❌ Echec enregistrement de l'archive",
                code=ErrCode.FILEERROR,
                ctx={"step": "import_normal", "note_id": note_id, "filepath": filepath},
            )
        # 4) Sauvegarde (optionnelle) vers SAV_PATH
        if SAV_PATH:
            try:
                copy_file_with_date(archive_path, SAV_PATH, logger=logger)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("[ERREUR] Sauvegarde dans SAV_PATH échouée : %s", exc)
        else:
            logger.warning("[WARN] 🚨 SAV_PATH non défini dans utils.config, sauvegarde ignorée.")

        # 5) Génération de la synthèse
        synthesis = process_import_syntheses(
            content, note_id, archive_path, synthesis_path, meta_final, classification, logger=logger
        )

        if not synthesis:
            logger.error(
                "[ERREUR] 🚨 Problème lors de la génération de la synthèse pour (id=%s)",
                note_id,
            )
            raise BrainOpsError(
                "[IMPORT] ❌ Echec de la génération de la synthèse",
                code=ErrCode.UNEXPECTED,
                ctx={"step": "import_normal", "note_id": note_id, "filepath": filepath},
            )

        if exists(synthesis_path) and exists(archive_path):
            logger.info("[INFO] Fichiers Synthèse et Archives OK")
            if exists(src.as_posix()):
                remove_file(src.as_posix())
                logger.info("[INFO] Suppression note originale confirmée : %s", src.as_posix())
        else:
            logger.error("[ERREUR] 🚨 Fichiers Synthèse ou Archives manquants pour (id=%s)", note_id)
            raise BrainOpsError(
                "[IMPORT] ❌ Fichiers Synthèse ou Archives manquants",
                code=ErrCode.NOFILE,
                ctx={"step": "import_normal", "note_id": note_id, "filepath": filepath},
            )

        logger.info("[INFO] 🏁 IMPORT terminé pour (id=%s)", note_id)
        return True
    except BrainOpsError as exc:
        exc.with_context(
            {"step": "import_normal", "note_id": note_id, "filepath": filepath, "force_categ": force_categ}
        )
        raise
    except Exception as exc:
        raise BrainOpsError(
            "[IMPORT] ❌ Import normal KO",
            code=ErrCode.UNEXPECTED,
            ctx={
                "step": "import_normal",
                "note_id": note_id,
                "filepath": filepath,
                "root_exc": type(exc).__name__,
                "root_msg": str(exc),
            },
        ) from exc
