"""
Ce module permet de définir la categ/sous categ d'une note.
"""
import shutil
import json
import os
import re
import logging
from datetime import datetime
from pathlib import Path
from Levenshtein import ratio
from handlers.ollama.ollama_call import call_ollama_with_retry, OllamaError
from handlers.header.extract_yaml_header import extract_yaml_header
from handlers.utils.files import clean_content
from handlers.ollama.prompts import PROMPTS
from handlers.sql.db_folders_utils import get_path_from_classification
from handlers.sql.db_update_notes import update_obsidian_note
from handlers.sql.db_categs_utils import generate_categ_dictionary, generate_categ_dictionary, generate_optional_subcategories
from handlers.sql.db_categs import get_path_safe
from handlers.sql.db_get_linked_folders_utils import get_folder_id
from handlers.utils.paths import ensure_folder_exists
from handlers.utils.divers import prompt_name_and_model_selection

logger = logging.getLogger("obsidian_notes." + __name__)

similarity_warnings_log = os.getenv('SIMILARITY_WARNINGS_LOG')
uncategorized_log = os.getenv('UNCATEGORIZED_LOG')
uncategorized_path = Path(os.getenv('UNCATEGORIZED_PATH'))
uncategorized_data = Path(os.getenv('UNCATEGORIZED_JSON'))

def process_get_note_type(filepath: str, note_id: int):
    """Analyse le type de note via Llama3.2."""
    logger.debug("[DEBUG] Entrée process_get_note_type")
    
    try:
        logger.debug("[DEBUG] process_get_note_type avant extract yaml")
        _, content_lines = extract_yaml_header(filepath)
        content_lines = clean_content(content_lines)
        logger.debug("[DEBUG] process_get_note_type content_lines %s", content_lines)
        subcateg_dict = generate_optional_subcategories()
        logger.debug("[DEBUG] process_get_note_type subcateg_dict %s", subcateg_dict)
        categ_dict = generate_categ_dictionary()
        logger.debug("[DEBUG] process_get_note_type categ_dict %s", categ_dict)
        prompt_name, _ = prompt_name_and_model_selection(note_id, key="type")
        model_ollama = "mistral:latest"
        prompt = PROMPTS[prompt_name].format(categ_dict=categ_dict,
                    subcateg_dict=subcateg_dict, content=content_lines[:1500])

        logger.debug("[DEBUG] process_get_note_type : %s", prompt)
        
        try:
            llama_proposition = call_ollama_with_retry(prompt, model_ollama)
            #llama_proposition = "Bidule/sarkozy"
            logger.debug("[DEBUG] process_get_note_type llama_proposition : %s", llama_proposition)
        except OllamaError:
            logger.error("[ERROR] Import annulé.")

        parse_category = parse_category_response(llama_proposition)
        if parse_category is None:
            logger.warning("[WARNING] Classification invalide, tentative de reclassement ultérieur.")
            handle_uncategorized(note_id, filepath, "Invalid format", "")
            return None
        
        logger.debug("[DEBUG] process_get_note_type parse_category %s", parse_category)
        note_type = clean_note_type(parse_category)
        
        if any(term in note_type.lower() for term in ["uncategorized", "unknow"]):
            logger.warning(f"[REDIRECT] note_type = {note_type} redirigé vers 'uncategorized'")
            return handle_uncategorized(note_id, filepath, note_type, llama_proposition)

        logger.info("Type de note détecté pour %s : %s", filepath, note_type)
    except Exception as e:
        logger.error("Erreur lors de l'analyse : %s", e)
        handle_uncategorized(note_id, filepath, "Error", llama_proposition)
        return None

    category_id, subcategory_id = get_path_safe(note_type, filepath, note_id)
    folder_id, dir_type_name = get_path_from_classification(category_id, subcategory_id)
    
    if dir_type_name is None:
        logger.warning("La note %s a été déplacée dans 'uncategorized'.", filepath)
        return None

    try:
        dir_type_name = Path(dir_type_name)
        ensure_folder_exists(dir_type_name)
        logger.debug("[DEBUG] dirtype_name %s", type(dir_type_name))
        logger.info("[INFO] Catégorie définie %s", dir_type_name)
    except Exception as e:
        logger.error("[ERREUR] Anomalie lors du process de catégorisation : %s", e)
        handle_uncategorized(note_id, filepath, note_type, llama_proposition)
        return None

    try:
        new_path = shutil.move(filepath, dir_type_name)
        updates = {
        'folder_id': folder_id,      # Catégorie déterminée par `get_type`
        'file_path': str(dir_type_name),
        'category_id': category_id,      # Catégorie déterminée par get_path_safe
        'subcategory_id': subcategory_id        
        }
        logger.debug("[DEBUG] updates : %s", updates)
        update_obsidian_note(note_id, updates)
        
        logger.info("[INFO] Note déplacée vers : %s", new_path)
        return new_path
    except Exception as e:
        logger.error("[ERREUR] Pb lors du déplacement : %s", e)
        handle_uncategorized(note_id, filepath, note_type, llama_proposition)
        return None

def parse_category_response(llama_proposition):
    pattern = r'([A-Za-z0-9_ ]+)/([A-Za-z0-9_ ]+)'
    match = re.search(pattern, llama_proposition)
    if match:
        return f"{match.group(1).strip()}/{match.group(2).strip()}"
    return None


def clean_note_type(parse_category):
    """
    Supprimer les guillemets et mettre en minuscule
    """
    logger.debug("[DEBUG] clean_note_type : %s", parse_category)
    #clean_str = parse_category.strip().lower().replace('"', '').replace("'", '')
    clean_str = parse_category.strip().replace('"', '').replace("'", '')
    # Remplacer les espaces par des underscores
    clean_str = clean_str.replace(" ", "_")

    # Supprimer les caractères interdits pour un nom de dossier/fichier
    clean_str = re.sub(r'[\:*?"<>|]', '', clean_str)

    # Supprimer un point en fin de nom (interdit sous Windows)
    clean_str = re.sub(r'\.$', '', clean_str)
    logger.debug("[DEBUG] clean_note_type : %s", clean_str)
    return clean_str


# Gérer les notes non catégorisées
def handle_uncategorized(
    note_id: str,
    filepath: str | Path,
    note_type: str,
    llama_proposition: str
) -> None:
    """
    Déplace une note dans le dossier 'uncategorized' et enregistre les infos pour reclassement futur.
    """

    filepath = Path(filepath)
    try:
        # _, _, category_id, subcategory_id = categ_extract(uncategorized_path)
        # folder_id, _ = get_path_from_classification(category_id, subcategory_id)
        base_folder = os.path.dirname(filepath)
        folder_id = get_folder_id(base_folder)
        new_path = uncategorized_path / filepath.name

        shutil.move(str(filepath), str(new_path))
        logger.warning("Note déplacée vers 'uncategorized' : %s", new_path)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updates = {
            'folder_id': folder_id,
            'file_path': str(new_path)
        }

        update_obsidian_note(note_id, updates)
   

        data = {}
        if uncategorized_data.exists():
            with open(uncategorized_data, "r", encoding="utf-8") as f:
                data = json.load(f)

        data[str(new_path)] = {
            "original_type": note_type,
            "llama_proposition": llama_proposition,
            "date": current_time
        }

        with open(uncategorized_data, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    except Exception as e:
        logger.error("[ERREUR] dans handle_uncategorized pour %s : %s", filepath, e)

# Vérification des similarités avec Levenshtein
def find_similar_levenshtein(name, existing_names, threshold_low=0.7, entity_type="subcategory"):
    """
    Vérifie les similarités entre une catégorie/sous-catégorie et une liste existante avec Levenshtein.
    """
    similar = []
    for existing in existing_names:
        similarity = ratio(name, existing)  # ✅ Utilisation de Levenshtein
        logger.debug(f"find_similar_levenshtein ({entity_type}) : {name} <-> {existing} = {similarity:.2f}")
        if similarity >= threshold_low:
            similar.append((existing, similarity))
    
    return sorted(similar, key=lambda x: x[1], reverse=True)

# Gérer les similarités
def check_and_handle_similarity(name, existing_names, threshold_low=0.7, entity_type="subcategory"):
    """
    Vérifie les similarités pour une nouvelle catégorie/sous-catégorie et applique une logique automatique.
    :param name: Nom de la catégorie/sous-catégorie à tester.
    :param existing_names: Liste des noms existants.
    :param threshold_low: Seuil minimum de similarité.
    :param entity_type: "category" ou "subcategory".
    :return: Nom validé ou None en cas de doute.
    """
    threshold_high = 0.9  # 🔥 Seuil de fusion automatique
    similar = find_similar_levenshtein(name, existing_names, threshold_low, entity_type)

    logger.debug(f"check_and_handle_similarity ({entity_type}) : {name} - Similar found: {similar}")

    if similar:
        closest, score = similar[0]
        
        if score >= threshold_high:
            # 🔥 Fusion automatique si la similarité est très élevée
            logger.info(f"[INFO] Fusion automatique ({entity_type}) : {name} -> {closest} (score: {score:.2f})")
            return closest
        
        if threshold_low <= score < threshold_high:
            # 🚨 Loguer les similarités moyennes et NE PAS créer la catégorie/sous-catégorie
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = (
                f"[{current_time}] Doute sur {entity_type}: '{name}' proche de '{closest}' (score: {score:.2f})\n"
            )
            logger.warning(f"[WARN] Similitude moyenne détectée ({entity_type}) : '{name}' proche de '{closest}' (score: {score:.2f})")
            
            with open(similarity_warnings_log, "a", encoding='utf-8') as log_file:
                log_file.write(log_message)
            
            return None  # 🔥 Retourne None pour éviter la création automatique

    # ✅ Si aucune similarité significative, considérer comme une nouvelle catégorie/sous-catégorie
    return name
