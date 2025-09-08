# sql/db_update_notes.py
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from brainops.sql.db_connection import get_db_connection
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger

# Colonnes autorisées à la mise à jour
_ALLOWED_COLUMNS: set[str] = {
    "parent_id",
    "title",
    "file_path",
    "folder_id",
    "category_id",
    "subcategory_id",
    "status",
    "summary",
    "source",
    "author",
    "project",
    "created_at",
    "modified_at",
    "word_count",
    "content_hash",
    "source_hash",
    "lang",
}


@with_child_logger
def update_obsidian_note(
    note_id: int,
    updates: Dict[str, Any],
    *,
    logger: LoggerProtocol | None = None,
) -> bool:
    logger = ensure_logger(logger, __name__)
    if not updates:
        logger.debug("[NOTES] Aucun champ à mettre à jour (id=%s)", note_id)
        return False

    # Filtrage strict pour éviter l'injection via les clés
    filtered = {k: v for k, v in updates.items() if k in _ALLOWED_COLUMNS}
    if not filtered:
        logger.warning(
            "[NOTES] Aucun champ autorisé dans updates: %s", list(updates.keys())
        )
        return False

    set_clause = ", ".join(f"{k} = %s" for k in filtered.keys())
    values = list(filtered.values()) + [note_id]

    conn = get_db_connection(logger=logger)
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE obsidian_notes SET {set_clause} WHERE id = %s",
                values,
            )
        conn.commit()
        logger.info(
            "[NOTES] Mise à jour OK (id=%s): %s", note_id, list(filtered.keys())
        )
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[NOTES] Erreur update_obsidian_note(id=%s): %s", note_id, exc)
        return False
    finally:
        conn.close()


@with_child_logger
def update_obsidian_tags(
    note_id: int, tags: Dict[str, Any], logger: LoggerProtocol | None = None
) -> None:
    logger = ensure_logger(logger, __name__)
    # Ouvre la connexion à la base de données
    conn = get_db_connection(logger=logger)
    if not conn:
        logger.error("[TAGS] Impossible de se connecter à la base de données.")
        return

    # Crée un curseur pour exécuter la requête SQL
    cursor = conn.cursor()

    try:
        # Supprimer les anciens tags associés à cette note
        cursor.execute("DELETE FROM obsidian_tags WHERE note_id = %s", (note_id,))

        # Ajouter les nouveaux tags
        for tag in tags:
            cursor.execute(
                "INSERT INTO obsidian_tags (note_id, tag) VALUES (%s, %s)",
                (note_id, tag),
            )

        # Commit les changements
        conn.commit()
        logger.info("[TAGS] Tags mis à jour pour la note %d.", note_id)

    except Exception as e:
        logger.error("[TAGS] Erreur lors de la mise à jour des tags : %s", e)

    finally:
        # Fermer le curseur et la connexion
        cursor.close()
        conn.close()
