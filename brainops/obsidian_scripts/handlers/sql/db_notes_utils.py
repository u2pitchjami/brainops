import logging
import os
import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path

from brainops.obsidian_scripts.handlers.header.header_utils import hash_source
from brainops.obsidian_scripts.handlers.sql.db_connection import get_db_connection
from brainops.obsidian_scripts.handlers.sql.db_get_linked_notes_utils import (
    get_new_note_test_metadata,
)
from brainops.obsidian_scripts.handlers.sql.db_utils import safe_execute
from brainops.obsidian_scripts.handlers.utils.files import hash_file_content
from brainops.obsidian_scripts.handlers.utils.paths import ensure_folder_exists

# setup_logger("db_notes_utils", logging.DEBUG)
logger = logging.getLogger("db_notes_utils")


def link_notes_parent_child(incoming_note_id, yaml_note_id):
    """
    Lie une note archive à sa note synthèse via `parent_id` et vice- versa.
    """
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    try:
        # 🔗 Mise à jour des parent_id dans les deux sens
        cursor.execute(
            "UPDATE obsidian_notes SET parent_id = %s WHERE id = %s",
            (yaml_note_id, incoming_note_id),
        )
        cursor.execute(
            "UPDATE obsidian_notes SET parent_id = %s WHERE id = %s",
            (incoming_note_id, yaml_note_id),
        )

        conn.commit()  # ✅ 🔥 IMPORTANT : On commit avant de fermer la connexion
        logger.info(
            f"🔗 [INFO] Liens parent_id créés : Archive {incoming_note_id} ↔ Synthèse {yaml_note_id}"
        )

    except Exception as e:
        logger.error(f"❌ [ERROR] Impossible d'ajouter les liens parent_id : {e}")
        conn.rollback()  # 🔥 Annule les modifs en cas d'erreur
    finally:
        cursor.close()  # 🔥 Toujours fermer le curseur
        conn.close()  # 🔥 Ferme la connexion proprement


def check_synthesis_and_trigger_archive(note_id, dest_path):
    """
    Si une `synthesis` est modifiée, force un recheck de l'archive associée.
    """
    from brainops.obsidian_scripts.handlers.process.headers import add_metadata_to_yaml

    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()

    try:
        # 🔍 1. Récupérer le chemin de la synthesis
        cursor.execute("SELECT file_path FROM obsidian_notes WHERE id = %s", (note_id,))
        synthesis_path = Path(cursor.fetchone()[0])

        # 🔍 2. Extraire le nom de base
        synthesis_name = synthesis_path.stem  # ex : '2025-03-22 - Rapport X'
        archive_name = f"{synthesis_name} (archive).md"
        new_archive_path = synthesis_path.with_name(archive_name)

        # 🔍 3. Comparer avec le nom actuel de l'archive
        cursor.execute(
            "SELECT id, file_path FROM obsidian_notes WHERE parent_id = %s AND status = 'archive'",
            (note_id,),
        )
        archive_result = cursor.fetchone()

        if archive_result:
            archive_id, current_archive_path = archive_result
            current_archive_path = Path(current_archive_path)

            # Récupérer le dossier de la synthèse
            synthesis_folder = os.path.dirname(dest_path)
            synthesis_folder = Path(synthesis_folder)

            # Nom du fichier de la synthèse
            synthesis_name = synthesis_path.stem

            # Créer le dossier Archives s'il n'existe pas
            archive_folder = synthesis_folder / "Archives"
            ensure_folder_exists(archive_folder)

            # Nom du fichier de l'archive
            archive_name = f"{synthesis_name} (archive).md"
            new_archive_path = (
                archive_folder / archive_name
            )  # Nouvelle archive dans le dossier "Archives"

            # Si l'archive doit être déplacée et renommée
            if current_archive_path != new_archive_path:
                logger.info(
                    f"[SYNC] Déplacement et renommage archive : {current_archive_path} → {new_archive_path}"
                )
                if new_archive_path.exists():
                    logger.warning(
                        f"[WARN] Fichier {new_archive_path} existe déjà, déplacement annulé."
                    )
                else:
                    shutil.move(
                        str(current_archive_path), str(new_archive_path)
                    )  # Déplacement réel du fichier avec shutil.move()
                    cursor.execute(
                        "UPDATE obsidian_notes SET file_path = %s WHERE id = %s",
                        (str(new_archive_path), archive_id),
                    )
                    conn.commit()

            # 🔁 Mise à jour YAML
            add_metadata_to_yaml(
                note_id=archive_id,
                filepath=new_archive_path,
                status="archive",
                synthesis_id=note_id,
            )

        else:
            logger.warning(f"[WARN] Aucune archive trouvée pour la synthèse {note_id}")

    except Exception as e:
        logger.error(
            f"❌ [ERROR] Erreur lors de la vérification de la synthesis {note_id} : {e}"
        )
    finally:
        cursor.close()
        conn.close()


def file_path_exists_in_db(file_path, src_path=None):
    """
    Vérifie si un file_path ou src_path existe dans la table obsidian_notes.

    Retourne le note_id si trouvé, sinon None.
    """
    logger.debug("[DEBUG] entrée file_path_exists_in_db")
    logger.debug(f"file_path : {file_path}")
    logger.debug(f"src_path : {src_path}")

    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        paths_to_check = []
        if src_path:
            paths_to_check.append(str(src_path))
        paths_to_check.append(str(file_path))

        for path in paths_to_check:
            result = safe_execute(
                cursor,
                "SELECT id FROM obsidian_notes WHERE file_path = %s LIMIT 1",
                (path,),
            ).fetchone()
            logger.debug(f"[DEBUG] file_path_exists_in_db, result for {path}: {result}")
            if result:
                return result[0]

        return None

    except Exception as err:
        logger.error(f"[DB ERROR] {err}")
        return None

    finally:
        cursor.close()
        conn.close()


def check_duplicate(
    note_id: int, file_path: str, threshold: float = 0.9
) -> tuple[bool, list[dict]]:
    """
    Vérifie s'il existe une note avec un titre ou un contenu similaire (hash source ou fichier).
    """
    logger.debug(f"[DUPLICATE] Début vérification duplicata pour note_id={note_id}")

    try:
        # 🔍 Récupération des métadonnées de la note
        title, source, author, _ = get_new_note_test_metadata(note_id)
        source_hash = hash_source(source)
        content_hash = hash_file_content(file_path)

        conn = get_db_connection()
        if not conn:
            return False, []

        cursor = conn.cursor()
        matches = []
        seen_ids = set()

        # 🔡 Fuzzy match sur le titre
        title_cleaned = clean_title(title)
        rows = safe_execute(
            cursor,
            "SELECT id, title FROM obsidian_notes WHERE status = %s",
            ("archive",),
        ).fetchall()
        for existing_id, existing_title in rows:
            similarity = SequenceMatcher(None, title_cleaned, existing_title).ratio()
            if similarity >= threshold:
                if existing_id not in seen_ids:
                    matches.append(
                        {
                            "id": existing_id,
                            "title": existing_title,
                            "similarity": round(similarity, 3),
                            "match_type": "title",
                        }
                    )
                    seen_ids.add(existing_id)

        # 🔐 Match sur le hash de source
        cursor.execute(
            "SELECT id, title FROM obsidian_notes WHERE status = %s AND source_hash = %s",
            ("archive", source_hash),
        )
        for row in cursor.fetchall():
            if row[0] not in seen_ids:
                matches.append(
                    {
                        "id": row[0],
                        "title": row[1],
                        "similarity": 1.0,
                        "match_type": "source_hash",
                    }
                )
                seen_ids.add(row[0])

        # 📄 Match sur le hash de contenu (fichier)
        cursor.execute(
            "SELECT id, title FROM obsidian_notes WHERE status = %s AND content_hash = %s",
            ("archive", content_hash),
        )
        for row in cursor.fetchall():
            if row[0] not in seen_ids:
                matches.append(
                    {
                        "id": row[0],
                        "title": row[1],
                        "similarity": 1.0,
                        "match_type": "content_hash",
                    }
                )
                seen_ids.add(row[0])

        if matches:
            logger.info(
                f"[DUPLICATE] {len(matches)} doublon(s) détecté(s) pour note_id={note_id}"
            )
            return True, matches

        logger.debug(f"[DUPLICATE] Aucun doublon trouvé pour note_id={note_id}")
        return False, []

    except Exception as e:
        logger.error(f"[ERROR] check_duplicate({note_id}) : {e}")
        return False, []


def clean_title(title):
    # Supprimer les chiffres de date et les underscores pour une meilleure comparaison
    return re.sub(r"^\d{6}_?", "", title.replace("_", " ")).lower()
