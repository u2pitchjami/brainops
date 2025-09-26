# sql/db_notes.py

from __future__ import annotations

from brainops.io.paths import to_abs, to_rel
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.db_connection import get_db_connection, get_dict_cursor
from brainops.sql.db_utils import safe_execute_dict
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def delete_note_by_path(file_path: str, *, logger: LoggerProtocol | None = None) -> bool:
    """
    Supprime une note (et ses dépendances) de MySQL, et le fichier si nécessaire.

    `file_path` peut être relatif vault (recommandé) ou un absolu sous BASE_PATH (/notes/...).
    """
    logger = ensure_logger(logger, __name__)
    file_rel = file_path  # canonise dès l’entrée

    logger.debug("🗑️ Suppression note: %s", file_rel)
    try:
        conn = get_db_connection(logger=logger)
        with get_dict_cursor(conn) as cur:  # autocommit=False → commit à la sortie si OK
            safe_execute_dict(
                cur,
                "SELECT id, parent_id, status FROM obsidian_notes WHERE file_path = %s",
                (file_rel,),
            )
            row = cur.fetchone()
            logger.debug("🔍 Note row: %s", row)
            if not row:
                logger.warning("⚠️ Aucune note trouvée pour %s, suppression annulée", file_rel)
                return False

            note_id: int = row["id"]
            parent_id: int | None = row["parent_id"]
            status: str = row["status"]

            logger.debug("🔍 Note %s (status=%s), parent=%s", note_id, status, parent_id)

            # 2) Supprimer les temp_blocks liés à la note
            safe_execute_dict(cur, "DELETE FROM obsidian_temp_blocks WHERE note_id = %s", (note_id,))
            logger.info("🧹 Blocks supprimés pour note %s", note_id)

            # 3) Supprimer les tags de la note
            safe_execute_dict(cur, "DELETE FROM obsidian_tags WHERE note_id = %s", (note_id,))
            logger.info("🏷️ Tags supprimés pour note %s", note_id)

            # 4) Cas status
            if status == "synthesis" and parent_id:
                # 4a) Récupérer le chemin de l’archive liée
                safe_execute_dict(
                    cur,
                    "SELECT file_path FROM obsidian_notes WHERE id = %s",
                    (parent_id,),
                )
                prow = cur.fetchone()

                if prow and prow.get("file_path"):
                    parent_file_rel: str = to_rel(prow["file_path"])
                    p = to_abs(parent_file_rel)
                    try:
                        if p.is_file():
                            p.unlink()
                            logger.info("🗑️ Fichier archive supprimé: %s", parent_file_rel)
                        else:
                            logger.warning("⚠️ Fichier archive introuvable: %s", parent_file_rel)
                    except Exception as exc:  # pylint: disable=broad-except
                        logger.warning(
                            "⚠️ Échec suppression fichier archive %s: %s", parent_file_rel, exc, exc_info=True
                        )

                # 4b) Supprimer l’archive + ses tags
                safe_execute_dict(cur, "DELETE FROM obsidian_notes WHERE id = %s", (parent_id,))
                safe_execute_dict(cur, "DELETE FROM obsidian_tags WHERE note_id = %s", (parent_id,))
                logger.info("🧹 Archive %s et ses tags supprimés", parent_id)

            elif status == "archive" and parent_id:
                # Dissocier la synthesis
                safe_execute_dict(cur, "UPDATE obsidian_notes SET parent_id = NULL WHERE id = %s", (parent_id,))
                logger.info("🔄 Synthesis %s dissociée de son archive", parent_id)

            # 5) Supprimer la note elle-même
            safe_execute_dict(cur, "DELETE FROM obsidian_notes WHERE id = %s", (note_id,))
            rc: int = cur.rowcount or 0
            conn.commit()

            logger.info("🗑️ Note %s supprimée (rowcount=%s)", note_id, rc)
            return rc > 0

    except BrainOpsError:
        # Si ton safe_execute lève déjà un BrainOpsError, on relaie
        raise
    except Exception as exc:  # pylint: disable=broad-except
        # db_conn fera rollback si nécessaire; on enrobe en erreur métier
        raise BrainOpsError("Suppression note KO", code=ErrCode.DB, ctx={"file_path": file_rel}) from exc
    finally:
        if conn:
            conn.close()
