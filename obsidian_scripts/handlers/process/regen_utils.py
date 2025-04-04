import os
from handlers.process.divers import rename_file
from handlers.utils.divers import make_relative_link
from handlers.utils.files import safe_write
from handlers.process_imports.import_syntheses import make_pre_synthese, make_syntheses
from handlers.process.headers import make_properties
from handlers.sql.db_get_linked_data import get_note_linked_data
from handlers.sql.db_temp_blocs import delete_blocs_by_path_and_source
from handlers.sql.db_update_notes import update_obsidian_note
from logger_setup import setup_logger
import logging
from handlers.sql.db_categs_utils import categ_extract
from handlers.process_imports.import_normal import import_normal
from handlers.process_imports.import_syntheses import process_import_syntheses


setup_logger("regen_utils")
logger = logging.getLogger("regen_utils")

def generate_synthesis_content(archive_path: str, synthesis_path: str, note_id: int) -> str:
    """
    Génére une synthèse à partir d'une archive et l'enregistre dans le fichier de synthèse.
    """
    try:
        delete_blocs_by_path_and_source(synthesis_path, source="synthesis")
        delete_blocs_by_path_and_source(synthesis_path, source="synthesis2")
        
        model_ollama = os.getenv('MODEL_SYNTHESIS1')
        response = make_pre_synthese(
            filepath=archive_path,
            write_file=False,
            model_ollama=model_ollama,
            source="synthesis"
        )

        if not response:
            logger.error("[ERREUR] Aucune réponse générée depuis make_pre_synthese.")
            return ""

        success = safe_write(synthesis_path, content=response)
        if not success:
            logger.error(f"[ERREUR] Écriture échouée pour : {synthesis_path}")
            return ""

        original_path = make_relative_link(archive_path, synthesis_path)
        model_ollama_2 = os.getenv('MODEL_SYNTHESIS2')

        make_syntheses(synthesis_path, note_id, model_ollama_2, original_path)
        make_properties(synthesis_path, note_id, status="synthesis")

        return response

    except Exception as e:
        logger.error(f"[ERREUR] generate_synthesis_content : {e}")
        return ""

def regen_synthese_from_archive(note_id, parent_id):
    """
    Régénère une synthèse pour une note à partir de son archive liée.
    """
    logger.info(f"[REGEN] Démarrage régénération synthèse pour note_id={note_id}, parent_id={parent_id}")
    
    try:
        data_synthese = get_note_linked_data(note_id, "note")
        synthese_path = data_synthese.get("file_path")

        data_archive = get_note_linked_data(parent_id, "note")
        archive_path = data_archive.get("file_path")

        if not archive_path or not os.path.exists(archive_path):
            logger.error(f"[ERREUR] Fichier archive introuvable : {archive_path}")
            return

        _ = generate_synthesis_content(archive_path, synthese_path, note_id)
        logger.info("[INFO] Synthese régen OK.")

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
