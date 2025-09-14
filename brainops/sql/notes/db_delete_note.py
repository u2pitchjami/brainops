"""
# sql/db_notes.py
"""

from __future__ import annotations

from contextlib import closing
import os

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def delete_note_by_path(file_path: str, *, logger: LoggerProtocol | None = None) -> bool:
    """
    Supprime une note et ses tags associés de MySQL.
    """
    logger = ensure_logger(logger, __name__)
    with closing(get_db_connection(logger=logger)) as conn:
        try:
            # 🔍 Trouver le `note_id`, `parent_id` et `status` AVANT suppression
            with conn.cursor() as cur:
                # safe_execute exécute, on lit le rowcount sur le cursor (DB-API standard)
                result = safe_execute(
                    cur,
                    "SELECT id, parent_id, status FROM obsidian_notes WHERE file_path = %s",
                    (file_path,),
                    logger=logger,
                ).fetchone()
            conn.commit()
            if not result:
                logger.warning(f"⚠️ [WARNING] Aucune note trouvée pour {file_path}, suppression annulée")
                return False
            note_id, parent_id, status = result

            logger.debug(f"🔍 [DEBUG] Note {note_id} (status={status}) liée à parent {parent_id}")
            # 🔥 Supprimer les temp_blocks associés AVANT la note
            with conn.cursor() as cur:
                safe_execute(cur, "DELETE FROM obsidian_temp_blocks WHERE note_path = %s", (file_path,))
            logger.info(f"🏷️ [INFO] Blocks supprimés pour la note {note_id}")
            conn.commit()

            # 🔥 Supprimer les tags associés AVANT la note
            with conn.cursor() as cur:
                safe_execute(cur, "DELETE FROM obsidian_tags WHERE note_id = %s", (note_id,))
            conn.commit()
            logger.info(f"🏷️ [INFO] Tags supprimés pour la note {note_id}")

            # 🔥 Cas 1 : Suppression d'une `synthesis` → Supprime aussi l'archive associée (si elle existe)
            if status == "synthesis" and parent_id:
                try:
                    # 1. Récupération du chemin du fichier à supprimer
                    with conn.cursor() as cur:
                        result = safe_execute(
                            cur,
                            "SELECT file_path FROM obsidian_notes WHERE id = %s",
                            (parent_id,),
                        ).fetchone()

                    if result:
                        file_path = result[0]
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            logger.info(f"🗑️ [FILE] Fichier supprimé : {file_path}")
                        else:
                            logger.warning(f"⚠️ [FILE] Fichier introuvable : {file_path}")
                    else:
                        logger.warning(f"⚠️ [DB] Aucun chemin de fichier trouvé pour ID {parent_id}")

                except Exception as e:
                    logger.error(f"❌ [ERROR] Échec de suppression du fichier associé à {parent_id} : {e}")

                # 2. Suppression dans la base de données
                logger.info(f"🗑️ [INFO] Suppression de l'archive associée : {parent_id}")
                with conn.cursor() as cur:
                    safe_execute(cur, "DELETE FROM obsidian_notes WHERE id = %s", (parent_id,))
                    conn.commit()
                with conn.cursor() as cur:
                    safe_execute(cur, "DELETE FROM obsidian_tags WHERE note_id = %s", (parent_id,))
                    conn.commit()
                logger.info(f"🏷️ [INFO] Tags supprimés pour l'archive {parent_id}")

            # 🔥 Cas 2 : Suppression d'une `archive` → Met `parent_id = NULL` dans la `synthesis` (si parent existe)
            elif status == "archive" and parent_id:
                logger.info(f"🔄 [INFO] Dissociation de la `synthesis` {parent_id} (plus d'archive liée)")
                with conn.cursor() as cur:
                    safe_execute(cur, "UPDATE obsidian_notes SET parent_id = NULL WHERE id = %s", (parent_id,))
                conn.commit()
            # 🔥 Suppression de la note actuelle en base
            with conn.cursor() as cur:
                safe_execute(cur, "DELETE FROM obsidian_notes WHERE id = %s", (note_id,))
            conn.commit()
            rc: int | None = getattr(cur, "rowcount", None)

            logger.info(f"🗑️ [INFO] Note {note_id} supprimée avec succès")

        except Exception as exc:
            logger.error(f"❌ [ERROR] Erreur lors de la suppression de la note {file_path} : {exc}")
            conn.rollback()
            raise BrainOpsError("Note supprt KO", code=ErrCode.DB, ctx={"file_path": file_path}) from exc
        finally:
            cur.close()
            conn.close()
    # DB-API: rc peut valoir None ou -1 quand non applicable
    deleted: bool = isinstance(rc, int) and rc > 0
    return deleted
