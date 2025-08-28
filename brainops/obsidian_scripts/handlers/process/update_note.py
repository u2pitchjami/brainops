import logging
import os
from datetime import datetime
from pathlib import Path

from brainops.obsidian_scripts.handlers.header.extract_yaml_header import (
    extract_note_metadata,
)
from brainops.obsidian_scripts.handlers.process.headers import add_metadata_to_yaml
from brainops.obsidian_scripts.handlers.process.regen_utils import (
    regen_header,
    regen_synthese_from_archive,
)
from brainops.obsidian_scripts.handlers.sql.db_categs_utils import categ_extract
from brainops.obsidian_scripts.handlers.sql.db_folders_utils import (
    get_path_from_classification,
)
from brainops.obsidian_scripts.handlers.sql.db_get_linked_data import (
    get_note_linked_data,
)
from brainops.obsidian_scripts.handlers.sql.db_get_linked_notes_utils import (
    get_note_tags,
)
from brainops.obsidian_scripts.handlers.sql.db_notes_utils import (
    check_synthesis_and_trigger_archive,
)
from brainops.obsidian_scripts.handlers.sql.db_update_notes import (
    update_obsidian_note,
    update_obsidian_tags,
)

logger = logging.getLogger("obsidian_notes." + __name__)


def update_note(note_id, dest_path, src_path=None):
    """
    Met à jour une note existante dans la base, y compris en cas de déplacement.
    """
    logger.debug(f"[DEBUG] note_id : {note_id}")
    logger.debug(
        f"[DEBUG] ===== Entrée update_note | dest = {dest_path}, src = {src_path}"
    )
    categ_trigger = False

    created = None
    # modified_at = None
    title = None
    tags = []
    category = None
    subcategory = None
    category_id = None
    subcategory_id = None
    summary = None
    source = None
    author = None
    project = None

    try:
        # 🔍 Extraire les métadonnées depuis l'entête'
        metadata = extract_note_metadata(dest_path)

        title_yaml = metadata.get(
            "title", Path(dest_path).stem.replace("_", " ").replace(":", " ")
        )
        # category = metadata.get("category", None)
        # subcategory = metadata.get("sub category", None)
        status_yaml = metadata.get("status", "draft")
        tags = metadata.get("tags", [])
        summary = metadata.get("summary", None)
        source_yaml = metadata.get("source", None)
        author_yaml = metadata.get("author", None)
        project_yaml = metadata.get("project", None)
        created_yaml = metadata.get("created", datetime.now().strftime("%Y-%m-%d"))
        logger.debug(f"[DEBUG] status_yaml : {status_yaml}")
        # 🔍 Extraire categ/subcateg du path'
        base_folder = os.path.dirname(dest_path)
        category_name, subcategory_name, category_id_dest, subcategory_id_dest = (
            categ_extract(base_folder)
        )
        logger.debug(
            f"[DEBUG] {category_name}, {subcategory_name}, {category_id_dest}, {subcategory_id_dest}"
        )
        logger.debug(f"[DEBUG] note_id data: {note_id}")
        # 🔍 Extraire les métadonnées depuis la base'
        data = get_note_linked_data(note_id, "note")

        # Mettre à jour uniquement les valeurs manquantes ou modifiées dans l'entête
        title = title_yaml if title_yaml else data.get("title")
        created = created_yaml if created_yaml else data.get("created")
        author = author_yaml if author_yaml else data.get("author")
        source = source_yaml if source_yaml else data.get("source")
        project = project_yaml if project_yaml else data.get("project")
        parent_id = data.get("parent_id")
        category_id = data.get("category_id")
        subcategory_id = data.get("subcategory_id")
        folder_id = data.get("folder_id")
        status = status_yaml if status_yaml else data.get("status")
        summary = data.get("summary", None)

        logger.debug(f"[DEBUG] status : {status}")

        # si écart entre categ/subcateg base et entête
        if category_id != category_id_dest or subcategory_id != subcategory_id_dest:
            # Mettre à jour les IDs
            category_id = category_id_dest
            subcategory_id = subcategory_id_dest
            # Récupérer le folder_id associé à la nouvelle catégorie/sous-catégorie
            folder_id, _ = get_path_from_classification(category_id, subcategory_id)
            # Tu peux mettre à jour la base de données ou l'entête avec les nouvelles informations ici
            logger.debug(
                f"[DEBUG]Nouvelle catégorie : {category_name}, Nouvelle sous-catégorie :\
                    {subcategory_name}, Nouveau folder_id : {folder_id}"
            )
            categ_trigger = True

        # update de la base
        updates = {
            "file_path": str(dest_path),
            "title": title,
            "folder_id": folder_id,
            "category_id": category_id,
            "subcategory_id": subcategory_id,
            "status": status,
            "summary": summary,
            "source": source,
            "author": author,
            "project": project,
            "created_at": created,
        }
        update_obsidian_note(note_id, updates)

        # update des tags ou non
        logger.debug(f"[DEBUG] tags entête :{tags}")
        logger.debug(f"[DEBUG] note_id :{note_id}")
        db_tags = get_note_tags(note_id)
        logger.debug(f"[DEBUG] tags db :{db_tags}")
        if tags != db_tags:
            update_obsidian_tags(note_id, tags)

        # update de l'entête
        if categ_trigger:
            add_metadata_to_yaml(note_id, dest_path)

        logger.info(
            f"[INFO] Note mise à jour avec succès : {dest_path} (note_id={note_id})"
        )

        # ensure_note_id_in_yaml(dest_path, note_id, status)

        if status == "synthesis":
            logger.debug("[DEBUG] Envoie vers check_synthesis_and_trigger_archive")
            check_synthesis_and_trigger_archive(note_id, dest_path)
        elif status == "regen":
            logger.debug("[DEBUG] Envoie vers regen_synthese_from_archive")
            regen_synthese_from_archive(note_id, filepath=str(dest_path))
        elif status == "regen_header":
            logger.debug("[DEBUG] Envoie vers regen_synthese_from_archive")
            regen_header(note_id, dest_path, parent_id)

        logger.debug(f"[DEBUG] ===== Sortie update_note note_id = {note_id}")
        return note_id
    except Exception as e:
        print(f"[ERROR] Erreur lors de la mise à jour de la note {note_id}: {e}")
