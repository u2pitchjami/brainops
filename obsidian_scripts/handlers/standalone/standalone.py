from handlers.utils.sql_helpers import get_path_from_classification
from handlers.utils.extract_yaml_header import extract_note_metadata
from handlers.utils.files import read_note_content
from handlers.process_imports.import_syntheses import process_import_syntheses
from handlers.process.headers import make_properties
from handlers.process.keywords import process_and_update_file
from logger_setup import setup_logger
import logging
from pathlib import Path
import shutil
import os

setup_logger("Standalone", logging.DEBUG)
logger = logging.getLogger("Standalone")

def make_synthese_standalone(filepath, src_path, note_id):
        
    # Étape 1 : Lire l'entête pour récupérer catégorie et sous-catégorie
    
    metadata = extract_note_metadata(filepath)
    category = (metadata["category"])
    subcategory = (metadata["sub category"])
    logger.debug("[DEBUG] make_synthese_standalone")
        
    # Étape 2 : Trouver le chemin cible
    target_path = src_path
    target_path = Path(target_path)
    logger.debug("[DEBUG] make_synthese_standalone target_path %s",target_path)
    if not target_path:
        logger.error(f"[ERREUR] Aucun chemin trouvé pour category={category}, subcategory={subcategory}")
        raise
    
    # Étape 3 : Construire le chemin complet de l'ancienne synthèse
    filename = os.path.basename(filepath)
    print(f"[DEBUG] Type de target_path: {type(target_path)}")  # Doit être Path, pas str
    print(f"[DEBUG] Type de filename: {type(filename)}")  # Doit être str

    original_file = target_path / filename
    if original_file.exists():
        try:
            original_file.unlink()  # Supprimer le fichier
            logger.info(f"[INFO] Synthèse originale supprimée : {original_file}")
        except Exception as e:
            logger.warning(f"[ATTENTION] Impossible de supprimer {original_file} (peut-être déjà supprimé ?) : {e}")
            raise
    else:
        logger.warning(f"[ATTENTION] Aucun fichier à supprimer trouvé pour : {original_file}")
    
    # Déplacer le fichier
    shutil.move(filepath, target_path)
    filepath = original_file
    # Étape 4 : Relancer la génération de synthèse
    try:
        process_import_syntheses(filepath, note_id)
        logger.info(f"[INFO] Synthèse régénérée pour note_id {note_id}")
    except Exception as e:
        logger.error(f"[ERREUR] Échec lors de la régénération de la synthèse : {e}")
        raise   
    
    
def make_header_standalone(filepath, src_path, note_id):
        
    # Étape 1 : Lire l'entête pour récupérer catégorie et sous-catégorie
    metadata = extract_note_metadata(filepath)
    category = (metadata["category"])
    subcategory = (metadata["sub category"])
    status = (metadata["status"])
    logger.debug("[DEBUG] make_header_standalone %s %s",category, subcategory)
    if not category or not subcategory:
        logger.error(f"[ERREUR] Impossible d'extraire les informations du fichier : {filepath}")
        raise
    
    # Étape 2 : Trouver le chemin cible
    target_path = src_path
    logger.debug("[DEBUG] make_sheader_standalone target_path %s",target_path)
    if not target_path:
        logger.error(f"[ERREUR] Aucun chemin trouvé pour category={category}, subcategory={subcategory}")
        raise
    
    # Étape 3 : Lire l'entête pour récupérer le statut
    
    logger.debug("[DEBUG] make_header_standalone status %s",status)
    if not status:
        logger.error(f"[ERREUR] Impossible d'extraire le statut du fichier : {filepath}")
        raise
    
    # Étape 4 : Construire le chemin complet de l'ancienne synthèse
    filename = os.path.basename(filepath)
    logger.debug(f"[DEBUG] filename {filename}")
    if status == "archive":
        original_file = Path(target_path) / status / filename
    else:
        original_file = Path(target_path) / filename

    target_path = original_file
    logger.debug(f"[DEBUG] target_path {filename}")
    # 🔍 Vérifications avant le déplacement
    logger.debug(f"[DEBUG] Vérification du déplacement de {filepath} vers {target_path}")

    if not Path(filepath).exists():
        logger.error(f"[ERREUR] Le fichier source {filepath} n'existe plus, annulation du déplacement.")
        return

    if not Path(target_path).parent.exists():
        logger.warning(f"[WARNING] Le dossier de destination {Path(target_path).parent} n'existe pas, création en cours.")
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)

    # Déplacement du fichier
    try:
        shutil.move(filepath, target_path)
        logger.info(f"[INFO] Fichier déplacé avec succès vers {target_path}")
    except Exception as e:
        logger.error(f"[ERREUR] Impossible de déplacer {filepath} vers {target_path} : {e}")
        return

    filepath = original_file  # Mise à jour du chemin
    # Étape 5 : Relancer la génération de synthèse
    
    try:
        content = read_note_content(filepath)
        if status == "archive":
            logger.debug(f"[DEBUG] envoi vers process & update {filepath}")
            process_and_update_file(filepath)
            logger.info(f"[INFO] Keywords mis à jour")
        logger.debug(f"[DEBUG] vers make_properties {filepath}")
        logger.debug(f"[DEBUG] make_properties() - File: {filepath}, Category: {category}, Subcategory: {subcategory}, Status: {status}")
        make_properties(content, filepath, note_id, status)
        logger.info(f"[INFO] Entête régénérée")    
        
        
        
    except Exception as e:
        logger.error(f"[ERREUR] Échec lors de la régénération de l'entête' : {e}")
        raise   
    
