import os
from brainops.obsidian_scripts.handlers.process.embeddings_utils import make_embeddings_synthesis
from brainops.obsidian_scripts.handlers.process.divers import rename_file
from brainops.obsidian_scripts.handlers.utils.divers import make_relative_link, prompt_name_and_model_selection
from brainops.obsidian_scripts.handlers.utils.files import safe_write
from brainops.obsidian_scripts.handlers.ollama.ollama_utils import large_or_standard_note
from brainops.obsidian_scripts.handlers.process_imports.import_syntheses import make_syntheses, process_import_syntheses
from brainops.obsidian_scripts.handlers.process.headers import make_properties
from brainops.obsidian_scripts.handlers.sql.db_get_linked_data import get_note_linked_data
from brainops.obsidian_scripts.handlers.sql.db_temp_blocs import delete_blocs_by_path_and_source
from brainops.obsidian_scripts.handlers.sql.db_update_notes import update_obsidian_note
import logging
from brainops.obsidian_scripts.handlers.sql.db_categs_utils import categ_extract
from brainops.obsidian_scripts.handlers.sql.db_get_linked_notes_utils import get_subcategory_prompt, get_note_lang, get_file_path
from brainops.obsidian_scripts.handlers.utils.files import safe_write
from brainops.obsidian_scripts.handlers.process_imports.import_normal import import_normal

logger = logging.getLogger("obsidian_notes." + __name__)

def regen_synthese_from_archive(note_id, filepath=None):
    """
    Régénère une synthèse pour une note à partir de son archive liée.
    """
    logger.info(f"[REGEN] Démarrage régénération synthèse pour note_id={note_id} filepath={filepath}")
    
    try:
        if not filepath:
            filepath=get_file_path(note_id)
            logger.debug(f"[REGEN] filepath={filepath}")
               
            
        delete_blocs_by_path_and_source(note_id, filepath, source="all")
        process_import_syntheses(filepath, note_id)
        logger.info(f"[REGEN] Régénération synthèse terminée pour note_id={note_id}")
       
    except Exception as e:
        logger.error(f"[ERREUR] Échec regen_synthese_from_archive : {e}")


def regen_header(note_id, filepath, parent_id=None):
    """
    Régénère les tags et le summary dans l'entête de la note.
    Détecte le statut correct (synthesis/archive) via parent_id ou chemin.
    """
    try:
        logger.info(f"[REGEN_HEADER] Traitement de {filepath}...")

        # Déterminer le nouveau statut
        if parent_id:
            data = get_note_linked_data(parent_id, "note")
            status_parent = data.get("status")
            status = "synthesis" if status_parent == "archive" else "archive"
        else:
            status = "archive" if "/Archives/" in filepath else "synthesis"

        make_properties(filepath, note_id, status)
        logger.info(f"[REGEN_HEADER] En-tête régénérée pour {filepath} avec statut {status}")

    except Exception as e:
        logger.error(f"[ERREUR] regen_header : {e}")


def force_categ_from_path(filepath, note_id):
    """
    Force la catégorisation à partir du chemin de destination, en contournant Ollama.
    """
    try:
        logger.info(f"[FORCE_CATEG] Tentative de catégorisation forcée pour {filepath}")
        base_folder = os.path.dirname(filepath)

        # Extraire catégorie et sous-catégorie
        category_name, subcategory_name, category_id, subcategory_id = categ_extract(base_folder)

        if subcategory_id is None:
            logger.warning(f"[FORCE_CATEG] Sous-catégorie non détectée, annulation.")
            return

        # Renommer et injecter
        new_path = rename_file(filepath, note_id)
        updates = {
            'file_path': str(new_path),
            "category_id": category_id,
            "subcategory_id": subcategory_id,
            "status": "processing"
        }
        
        logger.debug(f"[DEBUG] process_single_note mise à jour base de données : {updates}")
        update_obsidian_note(note_id, updates)
        import_normal(new_path, note_id)
        process_import_syntheses(new_path, note_id)

        logger.info(f"[FORCE_CATEG] Catégorisation et synthèse terminées pour {new_path}")

    except Exception as e:
        logger.error(f"[ERREUR] force_categ_from_path : {e}")
