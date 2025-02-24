import yaml
import time
import re
from logger_setup import setup_logger
import logging
from pathlib import Path
import shutil
import os
from difflib import get_close_matches
from handlers.utils.process_note_paths import get_path_from_classification, load_note_paths, get_path_by_category_and_subcategory, categ_extract
from handlers.process.headers import add_metadata_to_yaml
from handlers.process_imports.import_syntheses import process_import_syntheses
from handlers.utils.files import make_relative_link
from handlers.utils.extract_yaml_header import extract_yaml_header, extract_category_and_subcategory, extract_metadata, extract_summary, extract_tags

setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

def validate_category_and_subcategory(category, subcategory):
    """
    Valide la catégorie et sous-catégorie en les comparant avec note_paths.json.
    Renvoie le chemin attendu en cas de succès, sinon None.
    """
    logger.debug(f"[DEBUG] Validate_category_and_subcategory {category} / {subcategory}")
    note_paths = load_note_paths()
    categories = note_paths.get("categories", {})
    folders = note_paths.get("folders", {})
    
    # Vérification directe de la catégorie et sous-catégorie
    if category in categories:
        logger.debug("[DEBUG] Validate_category_and_subcategory categ trouvée")
        if subcategory:
            subcategories = categories[category].get("subcategories", {})
            if subcategory in subcategories:
                # Recherche du chemin dans la section 'folders'
                logger.debug("[DEBUG] Validate_category_and_subcategory categ / subcateg trouvées")
                for folder_path, folder_info in folders.items():
                    if folder_info["category"] == category and folder_info.get("subcategory") == subcategory:
                        logger.debug(f"[DEBUG] Validate_category_and_subcategory folder_info trouvé : {folder_info['path']}")
                        return folder_info["path"]
        else:
            # 🔹 Si aucune sous-catégorie n'est spécifiée, retourner le chemin de la catégorie
            for folder_info in folders.values():
                if folder_info["category"] == category and folder_info.get("subcategory") is None:
                    path = Path(folder_info["path"])  # 🔥 Conversion explicite en `Path`
                    logger.debug(f"[DEBUG] Validate_category_and_subcategory - Catégorie uniquement : {path}")
                    return path

    # 🔎 Recherche d'une correspondance approximative pour la catégorie et la sous-catégorie
    all_categories = categories.keys()
    all_subcategories = [
        sub for cat in categories.values() for sub in cat.get("subcategories", {}).keys()
    ]

    closest_category = get_close_matches(category, all_categories, n=1, cutoff=0.8)
    closest_subcategory = get_close_matches(subcategory, all_subcategories, n=1, cutoff=0.8)

    if closest_category or closest_subcategory:
        logger.warning(
            f"[ATTENTION] Correction suggérée : category={closest_category[0] if closest_category else category}, "
            f"subcategory={closest_subcategory[0] if closest_subcategory else subcategory}"
        )
        return None

    logger.error(f"[ERREUR] Catégorie ou sous-catégorie invalide : {category}/{subcategory}")
    return None


def verify_and_correct_category(filepath):
    """
    Vérifie et corrige la catégorie d'une synthèse, en déplaçant et modifiant si nécessaire.
    """
    try:
        logger.debug(f"[DEBUG] verify_and_correct_category {type(filepath)}")
        filepath = Path(filepath)
        logger.debug(f"[DEBUG] verify_and_correct_category {type(filepath)}")
        # Extraire la catégorie et sous-catégorie
        category, subcategory = extract_category_and_subcategory(filepath)
        logger.debug(f"[DEBUG] catégorie/sous-catégorie {category} / {subcategory}")
        if not category or not subcategory:
            logger.warning(f"[ATTENTION] Impossible d'extraire catégorie/sous-catégorie pour {filepath}")
            return False

        # Valider la catégorie et sous-catégorie
        expected_path = Path(validate_category_and_subcategory(category, subcategory))
        logger.debug(f"[DEBUG] validation catégorie/sous-catégorie {category} / {subcategory}")
        if not expected_path:
            logger.error(f"[ERREUR] Catégorie ou sous-catégorie non valide pour {filepath}. Opération annulée.")
            return False

        logger.debug(f"[DEBUG] expected_path type: {type(expected_path)} - value: {expected_path}")

        # Vérifier si le fichier est déjà dans le bon dossier
        current_path = filepath.parent.resolve()
        logger.debug(f"[DEBUG] current_path {type(current_path)}")
        logger.debug(f"[DEBUG] current_path {current_path}")
        if current_path != expected_path.resolve():
            logger.debug(f"[DEBUG] current_path {current_path} != {category} / {subcategory}")
            # Récupération de l'archive
            archive_path = add_archives_to_path(filepath)
            logger.debug(f"[DEBUG] archive_path {archive_path} - {filepath}")
            if not archive_path or not archive_path.exists():
                logger.warning(f"[ATTENTION] Aucun fichier archive trouvé")
                return False

            # Modification de la catégorie dans l'archive
            with open(archive_path, "r+", encoding="utf-8") as file:
                lines = file.readlines()
                for i, line in enumerate(lines):
                    if line.startswith("category:"):
                        lines[i] = f"category: {category}\n"
                    elif line.startswith("sub category:"):
                        lines[i] = f"sub category: {subcategory}\n"
                file.seek(0)
                file.writelines(lines)
                file.truncate()

            # Déplacer le fichier au bon endroit
            new_path = expected_path / archive_path.name
            archive_path.rename(new_path)
            logger.info(f"[INFO] Fichier déplacé : {archive_path} --> {new_path}")

            # Supprimer l'ancien fichier
            filepath.unlink(missing_ok=True)

            # Lancer le processus de régénération de synthèse (appel à une fonction dédiée)
            #process_import_syntheses(new_path, category, subcategory)
            logger.info(f"[INFO] Synthèse régénérée pour category={category}, subcategory={subcategory}")

            return True

        # Tout est correct
        logger.info(f"[INFO] Catégorie correcte pour {filepath}")
        return True

    except Exception as e:
        logger.error(f"[ERREUR] Échec de la vérification/correction pour {filepath} : {e}")
        return False
    
def add_archives_to_path(filepath):
    # Créer un objet Path à partir du chemin
    logger.debug("[DEBUG] add_archives_to_path %s", filepath)
    path_obj = Path(filepath)
    logger.debug("[DEBUG] add_archives_to_path path_obj : %s", path_obj)
    # Insérer "Archives" entre le dossier parent et le fichier
    archives_dir = path_obj.parent / "Archives"  # Ajouter "Archives" au dossier parent
    logger.debug("[DEBUG] add_archives_to_path archives_dir : %s", archives_dir)
    archives_dir.mkdir(parents=True, exist_ok=True)  # Créer le dossier Archives s'il n'existe pas
    
    archive_path = archives_dir / path_obj.name
    logger.debug("[DEBUG] add_archives_to_path archive_path : %s", archive_path)
    return archive_path

def process_sync_entete_with_path(filepath):
    """
    Synchronise l'entête YAML avec le chemin physique du fichier.
    """
    note_paths = load_note_paths()
    filepath = Path(filepath)  # Nouveau chemin
    file = filepath.name
    base_folder = filepath.parent  # Simplification avec Path
    
    new_category, new_subcategory = categ_extract(base_folder)  # Nouvelles catégories

    logger.debug("[DEBUG] process_sync_entete_with_path %s", filepath)

    category, subcategory = extract_category_and_subcategory(filepath)  # Anciennes catégories
    logger.debug("[DEBUG] process_sync_entete_with_path %s %s", category, subcategory)
    path_src = get_path_by_category_and_subcategory(category, subcategory)  # Ancien chemin
    logger.debug("[DEBUG] process_sync_entete_with_path %s ", path_src)
    logger.debug("[DEBUG] process_sync_entete_with_path %s ", type(path_src))
    file_path_src = path_src / file
    archives_path_src = add_archives_to_path(file_path_src)  # Ancien chemin archive
    logger.debug("[DEBUG] process_sync_entete_with_path %s ", archives_path_src)
    archives_path_dest = add_archives_to_path(filepath)  # Nouveau chemin archive
    logger.debug("[DEBUG] process_sync_entete_with_path %s ", archives_path_dest)

    # Vérifier que le fichier source existe avant de copier
    if archives_path_src.exists():
            shutil.move(archives_path_src, archives_path_dest)
            logger.info(f"[INFO] Move réussi vers : {archives_path_dest}")
            # Supprimer l'ancien fichier archive
            #archives_path_src.unlink(missing_ok=True)
    else:
        logger.warning(f"[WARN] Archive source introuvable : {archives_path_src}") 

    time.sleep(5)
    
    ##### MODIF CATEG ARCHIVE
    with open(archives_path_dest, "r", encoding="utf-8") as file:
        archive_content = file.read()
    # Récupérer les valeurs existantes
    tags_existants = []
    resume_existant = []
    status_existant = ""
    yaml_header_archive, body_content_archive = extract_yaml_header(archive_content)
    logger.debug(f"[DEBUG] yaml_header_archive : {yaml_header_archive}")
    tags_existants = extract_tags(yaml_header_archive)
    resume_existant = extract_summary(yaml_header_archive)
    status_existant = extract_metadata(yaml_header_archive, key_to_extract="status")

    logger.debug(f"[DEBUG] Extraction terminée : Tags={tags_existants}, Summary=\n{resume_existant}, Status={status_existant}")

    
    # Mettre à jour l'entête avec les nouvelles catégories tout en conservant les autres valeurs
    add_metadata_to_yaml(archives_path_dest, tags_existants, resume_existant, new_category, new_subcategory, status_existant)
    
            
            
    
    ##### MODIF CATEG SYNTHESE + LIEN ARCHIVE
    with open(filepath, "r", encoding="utf-8") as file:
        content = file.read()
    archives_path_dest_relative = make_relative_link(archives_path_dest, link_text="Voir la note originale")
    update_archive_link(filepath, content, archives_path_dest_relative)
    yaml_header, body_content = extract_yaml_header(content)
    logger.debug(f"[DEBUG] Contenu actuel de yaml_header : {yaml_header}")
    # Récupérer les valeurs existantes
    tags_existants = extract_tags(yaml_header)
    resume_existant = extract_summary(yaml_header)
    status_existant = extract_metadata(yaml_header, key_to_extract="status")
    
    
    logger.debug(f"[DEBUG] tags envoyés : {tags_existants}")    
    logger.debug(f"[DEBUG] résumé envoyés : {resume_existant}")
    #tags_formatted = f"[{', '.join(tags_existants)}]"
 
    # Mettre à jour l'entête avec les nouvelles catégories tout en conservant les autres valeurs
    add_metadata_to_yaml(filepath, tags_existants, resume_existant, new_category, new_subcategory, status_existant)

def update_archive_link(filepath, content, new_archive_path):
    """
    Met à jour le lien vers l'archive dans les 10 premières lignes de `content`.
    """
    pattern = r"(\[Voir la note originale\]\()(.*?)(\))"
    lines = content.splitlines()
    modified = False

    for i in range(len(lines)):  
        if re.search(pattern, lines[i]):  
            lines[i] = re.sub(pattern, rf"\1{new_archive_path}\3", lines[i])
            modified = True
            logger.info(f"[INFO] Lien mis à jour sur la ligne {i+1} avec : {new_archive_path}")
            break  

    if not modified:
        logger.warning("⚠️ Aucun lien d'archive trouvé.")

    new_content = "\n".join(lines)  # ✅ Assemble les lignes en un seul texte
    with open(filepath, "w", encoding="utf-8") as file:  # ✅ Ouvre bien le fichier
        file.write(new_content)  # ✅ Écrit le texte dans le fichier

    logger.info(f"[INFO] Lien mis à jour pour : {filepath}")  # ✅ Confirme l'action
    
    return

def dump_yaml_header(header):
    """
    Convertit un dictionnaire YAML en chaîne de caractères.
    """
    return "---\n" + yaml.dump(header, sort_keys=False) + "---\n"