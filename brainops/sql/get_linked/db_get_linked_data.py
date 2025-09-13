"""
# sql/db_get_linked_data.py
"""

from __future__ import annotations

from typing import Any, Literal, cast

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.sql.db_connection import get_db_connection
from brainops.sql.db_utils import safe_execute
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger

What = Literal["note", "category", "subcategory", "folder", "tags", "temp_blocks"]


@with_child_logger
def get_note_linked_data(
    note_id: int, what: What, *, logger: LoggerProtocol | None = None
) -> dict[str, Any] | list[str]:
    """
    Récupère des informations liées à une note à partir de son id.

    Retour:
      - 'note' / 'category' / 'subcategory' / 'folder' → dict (ou {"error": ...})
      - 'tags' → list[str]
      - 'temp_blocks' → dict (ou {"error": ...})
    """
    logger = ensure_logger(logger, __name__)
    conn = get_db_connection(logger=logger)

    try:
        with conn.cursor(dictionary=True) as cur:
            # Base: la note
            note = safe_execute(
                cur,
                "SELECT * FROM obsidian_notes WHERE id=%s",
                (note_id,),
                logger=logger,
            ).fetchone()
            if not note:
                raise BrainOpsError("Note id KO", code=ErrCode.DB, ctx={"note_id": note_id})

            note_dict = cast(dict[str, Any], note)
            if what == "note":
                return note_dict

            if what == "category":
                cat_id = note_dict.get("category_id")
                if cat_id:
                    row_categ = safe_execute(
                        cur,
                        "SELECT * FROM obsidian_categories WHERE id=%s",
                        (cat_id,),
                        logger=logger,
                    ).fetchone()
                    row_categ_dict = cast(dict[str, Any], row_categ)
                    return row_categ_dict or {"error": f"Catégorie {cat_id} introuvable"}
                return {"error": "Aucune catégorie associée à cette note"}

            if what == "subcategory":
                subcat_id = note_dict.get("subcategory_id")
                if subcat_id:
                    row_sub = safe_execute(
                        cur,
                        "SELECT * FROM obsidian_categories WHERE id=%s",
                        (subcat_id,),
                        logger=logger,
                    ).fetchone()
                    row_sub_dict = cast(dict[str, Any], row_sub)
                    return row_sub_dict or {"error": f"Sous-catégorie {subcat_id} introuvable"}
                return {"error": "Aucune sous-catégorie associée à cette note"}

            if what == "folder":
                folder_id = note_dict.get("folder_id")
                if folder_id:
                    row_folder = safe_execute(
                        cur,
                        "SELECT * FROM obsidian_folders WHERE id=%s",
                        (folder_id,),
                        logger=logger,
                    ).fetchone()
                    row_folder_dict = cast(dict[str, Any], row_folder)
                    return row_folder_dict
                return {}

            if what == "tags":
                rows_tags = safe_execute(
                    cur,
                    "SELECT tag FROM obsidian_tags WHERE note_id=%s",
                    (note_id,),
                    logger=logger,
                ).fetchall()
                rows_tags_list = cast(list[dict[str, Any]], rows_tags)
                return [r["tag"] for r in rows_tags_list]
            return []

            if what == "temp_blocks":
                row = safe_execute(
                    cur,
                    "SELECT * FROM obsidian_temp_blocks WHERE note_id=%s",
                    (note_id,),
                    logger=logger,
                ).fetchone()
                return row
            return {}

            raise BrainOpsError("what KO", code=ErrCode.DB, ctx={"note_id": note_id})
    except Exception as exc:
        raise BrainOpsError(
            "Récup get link Note KO",
            code=ErrCode.DB,
            ctx={"note_id": note_id},
        ) from exc
    finally:
        conn.close()


@with_child_logger
def get_folder_linked_data(
    folder_path: str,
    what: Literal["folder", "category", "subcategory", "parent"],
    *,
    logger: LoggerProtocol | None = None,
) -> dict[str, Any]:
    """
    Récupère des informations liées à un dossier Obsidian à partir de son chemin.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug(f"[DEBUG] get_folder_linked_data({folder_path}, {what})")
    try:
        conn = get_db_connection(logger=logger)

        # ✅ buffered=True évite "Unread result found"
        cursor = conn.cursor(dictionary=True, buffered=True)

        cursor.execute(
            "SELECT * FROM obsidian_folders WHERE path = %s LIMIT 1",
            (folder_path,),
        )
        folder = cursor.fetchone()
        if not folder:
            raise BrainOpsError("Récup Folder KO", code=ErrCode.DB, ctx={"path": folder_path})

        folder_dict = cast(dict[str, Any], folder)
        if what == "folder":
            return folder_dict

        if what == "category":
            cat_id = folder.get("category_id")
            logger.debug(f"[DEBUG] get_folder_linked_data category_id: {cat_id}")
            if cat_id:
                cursor.execute(
                    "SELECT * FROM obsidian_categories WHERE id = %s LIMIT 1",
                    (cat_id,),
                )
                return cursor.fetchone() or {}
            return {}

        if what == "subcategory":
            sub_id = folder.get("subcategory_id")
            if sub_id:
                cursor.execute(
                    "SELECT * FROM obsidian_categories WHERE id = %s LIMIT 1",
                    (sub_id,),
                )
                return cursor.fetchone() or {}
            return {}

        if what == "parent":
            parent_id = folder.get("parent_id")
            if parent_id:
                cursor.execute(
                    "SELECT * FROM obsidian_folders WHERE id = %s LIMIT 1",
                    (parent_id,),
                )
                return cursor.fetchone() or {}
            return {}

        raise BrainOpsError("what KO", code=ErrCode.DB, ctx={"path": folder_path})

    except Exception as exc:
        raise BrainOpsError(
            "Récup get link Folder KO",
            code=ErrCode.DB,
            ctx={"path": folder_path},
        ) from exc
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
