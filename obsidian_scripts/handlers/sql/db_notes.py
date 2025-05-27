from logger_setup import setup_logger
import logging
import os
from pathlib import Path
from datetime import datetime
from handlers.sql.db_connection import get_db_connection
from handlers.sql.db_utils import safe_execute
from handlers.header.extract_yaml_header import extract_note_metadata
from handlers.header.header_utils import hash_source
from handlers.utils.normalization import sanitize_created, sanitize_yaml_title
from handlers.utils.files import hash_file_content, count_words
from handlers.utils.divers import lang_detect
from handlers.process.folders import add_folder
from handlers.start.process_folder_event import detect_folder_type

#setup_logger("db_add_notes", logging.DEBUG)
logger = logging.getLogger("db_add_notes")

def add_note_to_db(file_path):
    """Ajoute ou met à jour une note dans la base MySQL"""
    logger.debug("[DEBUG] ===== Entrée add_note_to_db")
    
    lang = None
    content_hash = None
    created = None
    modified_at = None
    title = None
    tags = []
    note_id = None
    category = None
    subcategory = None
    category_id = None
    subcategory_id = None
    summary = None
    source = None
    author = None
    project = None
    word_count = None
    folder_id = None
    source_hash = None
    content_hash = hash_file_content(file_path)
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    word_count = count_words(filepath=file_path)
    logger.debug(f"[DEBUG]ADD_NOTE !!! word_count = {word_count}")
    lang = lang_detect(file_path)
    logger.debug(f"[DEBUG] lang = {lang}")
    metadata = extract_note_metadata(file_path)

    # 🔹 Fallback et nettoyage
    title = sanitize_yaml_title(metadata.get("title"))
    category = metadata.get("category", None)
    subcategory = metadata.get("sub category", None)
    status = metadata.get("status", "draft")
    tags = metadata.get("tags", [])
    created = metadata.get("created")
    logger.debug("[DEBUG] created %s : %s", created, type(created))
    created = sanitize_created(metadata.get("created"))
    logger.debug("[DEBUG] created %s", created)
    modified_at = metadata.get("last_modified", datetime.now().strftime('%Y-%m-%d'))
    summary = metadata.get("summary", None)
    source = metadata.get("source", None)
    author = metadata.get("author", None)
    project = metadata.get("project", None)
    logger.debug(f"[DEBUG] word_count = {word_count}")
    if source:
        source_hash = hash_source(source)
    
    # 🔹 Dossier parent
    folder_path = str(Path(file_path).parent)
    folder_result = safe_execute(cursor, "SELECT id FROM obsidian_folders WHERE path = %s", (folder_path,)).fetchone()
    folder_id = folder_result[0] if folder_result else None
    if not folder_id:
        logger.warning(f"[WARNING] Dossier non trouvé pour {folder_path}, ajout en base")
        logger
        folder_type = detect_folder_type(folder_path)
        folder_id = add_folder(folder_path, folder_type)
        return folder_id


    # 🔹 Insertion / Mise à jour
    cursor.execute("""
        INSERT INTO obsidian_notes (
            title, file_path, folder_id, category_id, subcategory_id, 
            status, created_at, modified_at,
            summary, source, author, project, word_count, content_hash, source_hash, lang
        )
        VALUES (
            %s, %s, %s, 
            (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1),
            (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1),
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            category_id = VALUES(category_id),
            subcategory_id = VALUES(subcategory_id),
            status = VALUES(status),
            modified_at = VALUES(modified_at),
            summary = VALUES(summary),
            source = VALUES(source),
            author = VALUES(author),
            project = VALUES(project),
            word_count = VALUES(word_count)
                        """, (
        title, str(file_path), folder_id, category, subcategory,
        status, created, modified_at,
        summary, source, author, project, word_count, content_hash, source_hash, lang
    ))

    note_id = cursor.lastrowid
    logger.debug(f"[DEBUG] add_note_to_db note_id = {note_id}")
    
    
    # # 🔹 MàJ des tags
    # if note_id:
    #     cursor.execute("DELETE FROM obsidian_tags WHERE note_id = %s", (note_id,))
    #     for tag in tags:
    #         cursor.execute("INSERT INTO obsidian_tags (note_id, tag) VALUES (%s, %s)", (note_id, tag))

    conn.commit()
    conn.close()
    
    return note_id

def delete_note_from_db(file_path):
    """Supprime une note et ses tags associés de MySQL."""
    logger.debug("delete_note_from_db")
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()

    try:
        # 🔍 Trouver le `note_id`, `parent_id` et `status` AVANT suppression
        result = safe_execute(cursor, "SELECT id, parent_id, status FROM obsidian_notes WHERE file_path = %s", (file_path,)).fetchone()
        
        if not result:
            logger.warning(f"⚠️ [WARNING] Aucune note trouvée pour {file_path}, suppression annulée")
            return

        note_id, parent_id, status = result
        logger.debug(f"🔍 [DEBUG] Note {note_id} (status={status}) liée à parent {parent_id}")
        # 🔥 Supprimer les temp_blocks associés AVANT la note
        cursor.execute("DELETE FROM obsidian_temp_blocks WHERE note_path = %s", (file_path,))
        logger.info(f"🏷️ [INFO] Blocks supprimés pour la note {note_id}")

        # 🔥 Supprimer les tags associés AVANT la note
        cursor.execute("DELETE FROM obsidian_tags WHERE note_id = %s", (note_id,))
        logger.info(f"🏷️ [INFO] Tags supprimés pour la note {note_id}")

        # 🔥 Cas 1 : Suppression d'une `synthesis` → Supprime aussi l'archive associée (si elle existe)
        if status == "synthesis" and parent_id:
            try:
                # 1. Récupération du chemin du fichier à supprimer
                result = safe_execute(cursor, "SELECT file_path FROM obsidian_notes WHERE id = %s", (parent_id,)).fetchone()
                
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
            cursor.execute("DELETE FROM obsidian_notes WHERE id = %s", (parent_id,))
            cursor.execute("DELETE FROM obsidian_tags WHERE note_id = %s", (parent_id,))
            logger.info(f"🏷️ [INFO] Tags supprimés pour l'archive {parent_id}")

        # 🔥 Cas 2 : Suppression d'une `archive` → Met `parent_id = NULL` dans la `synthesis` (si parent existe)
        elif status == "archive" and parent_id:
            logger.info(f"🔄 [INFO] Dissociation de la `synthesis` {parent_id} (plus d'archive liée)")
            cursor.execute("UPDATE obsidian_notes SET parent_id = NULL WHERE id = %s", (parent_id,))

        # 🔥 Suppression de la note actuelle en base
        cursor.execute("DELETE FROM obsidian_notes WHERE id = %s", (note_id,))
        conn.commit()
        logger.info(f"🗑️ [INFO] Note {note_id} supprimée avec succès")

    except Exception as e:
        logger.error(f"❌ [ERROR] Erreur lors de la suppression de la note {file_path} : {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
