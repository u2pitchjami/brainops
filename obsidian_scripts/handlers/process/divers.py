from logger_setup import setup_logger
import logging
import shutil
from pathlib import Path
from datetime import datetime
from handlers.process.new_note import new_note
from handlers.utils.paths import build_archive_path, ensure_folder_exists
from handlers.sql.db_update_notes import update_obsidian_note
from handlers.sql.db_get_linked_data import get_note_linked_data
from handlers.sql.db_notes import add_note_to_db
from handlers.process.folders import add_folder
from handlers.utils.normalization import sanitize_filename


setup_logger("process_div", logging.DEBUG)
logger = logging.getLogger("process_div")

def rename_file(filepath, note_id):
    """
    Renomme un fichier avec un nouveau nom tout en conservant son dossier d'origine.
    """
        
    logger.debug(f"[DEBUG] entrée rename_file")
    
    tags = None
    src_path = None
    category_id = None
    subcategory_id = None
    status = None
    new_title = None
    
    try:
        file_path = Path(filepath)
        # Obtenir la date actuelle au format souhaité
        if not file_path.exists():
            logger.error(f"[ERREUR] Le fichier {filepath} n'existe pas.")
            raise # Ou lève une exception si c'est critique
        
        logger.debug(f"[DEBUG] rename_file file_path.name {file_path.name}")
        date_str = datetime.now().strftime("%y-%m-%d")  # Exemple : '250112'
        created_at = date_str
        logger.debug(f"[DEBUG] rename_file date_str {date_str}")
        data = get_note_linked_data(note_id, "note")
        if data:
            created_at = data.get("created_at") or date_str
        else:
            print("Aucune donnée trouvée pour ce note_id")
            
        new_name = f"{created_at}_{sanitize_filename(file_path.name)}"
        new_path = file_path.parent / new_name  # Nouveau chemin dans le même dossier
                       
        # Résolution des collisions : ajouter un suffixe si le fichier existe déjà
        counter = 1
        while new_path.exists():
            new_name = f"{created_at}_{sanitize_filename(file_path.stem)}_{counter}{file_path.suffix}"
            new_path = file_path.parent / new_name
            counter += 1
        
        file_path.rename(new_path)  # Renomme le fichier
        logger.info(f"[INFO] Note renommée : {filepath} --> {new_path}")
        
        return new_path
    except Exception as e:
            logger.error(f"[ERREUR] Anomalie lors du renommage : {e}")
            raise
 
def link_synthesis_and_archive(original_path: Path, synthese_id: int) -> None:
    """
    Crée une archive à partir du chemin de la synthèse et établit un lien parent_id croisé
    entre la synthèse et l'archive dans la base de données.
    """
    try:
        archive_id = new_note(str(original_path))
        if not archive_id:
            logger.error(f"[LINK] ❌ Impossible de créer l'archive pour {original_path}")
            return

        logger.debug(f"[LINK] 🗂️ Archive créée : {archive_id} ← issue de la synthèse {synthese_id}")

        # Mise à jour de l'archive → parent = synthèse
        update_obsidian_note(archive_id, {'parent_id': synthese_id})
        # Mise à jour de la synthèse → parent = archive
        update_obsidian_note(synthese_id, {'parent_id': archive_id})

        logger.info(f"[LINK] 🔗 Liens croisés posés : archive {archive_id} ⇄ synthèse {synthese_id}")
        return archive_id

    except Exception as e:
        logger.error(f"[LINK] 🚨 Erreur lors de la liaison archive/synthèse : {e}")

def copy_to_archive(original_path: str | Path, note_id: int) -> int:
    """
    Copie une note dans un sous-dossier 'Archives', crée la note correspondante en base,
    et lie l'archive à la note originale via 'synthesis_id'.
    """
    archive_path = build_archive_path(original_path)

    # 🛡️ S'assurer que le dossier existe physiquement et en base
    ensure_folder_exists(archive_path.parent)
    folder_id = add_folder(archive_path.parent, folder_type="archive")

    # 📥 Copier le fichier vers son dossier d'archive
    try:
        shutil.copy(original_path, archive_path)
        logger.info(f"[ARCHIVE] Copie de la note vers : {archive_path}")
    except Exception as e:
        logger.error(f"[ARCHIVE] Échec de la copie : {e}")
        return None

    # 🗂️ Enregistrer la nouvelle note archivée dans la base
    archive_note_id = add_note_to_db(archive_path)

    # 🔗 Lier l'archive à la note originale
    update_obsidian_note(note_id, {"parent_id": archive_note_id})
    update_obsidian_note(archive_note_id, {"parent_id": note_id})
    logger.info(f"[ARCHIVE] Lien synthèse établi : {note_id} → {archive_note_id}")

    return archive_path