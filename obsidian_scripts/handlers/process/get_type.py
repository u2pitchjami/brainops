"""
Ce module permet de définir la categ/sous categ d'une note.
"""
import shutil
import json
import os
import re
from logger_setup import setup_logger
import logging
from datetime import datetime
from pathlib import Path
from Levenshtein import ratio
from handlers.process.ollama import ollama_generate
from handlers.utils.extract_yaml_header import extract_yaml_header
from handlers.process.prompts import PROMPTS
from handlers.utils.process_note_paths import get_path_from_classification, save_note_paths, load_note_paths
from handlers.utils.extract_yaml_header import extract_category_and_subcategory

setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

similarity_warnings_log = os.getenv('SIMILARITY_WARNINGS_LOG')
uncategorized_log = os.getenv('UNCATEGORIZED_LOG')
uncategorized_path = Path(os.getenv('UNCATEGORIZED_PATH'))
uncategorized_path.mkdir(parents=True, exist_ok=True)
uncategorized_data = "uncategorized_notes.json"

def process_get_note_type(filepath):
    """Analyse le type de note via Llama3.2."""
    logger.debug("[DEBUG] Entrée process_get_note_type")

    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()
    try:
        note_paths = load_note_paths()
        _, content_lines = extract_yaml_header(content)
        subcateg_dict = generate_optional_subcategories()
        categ_dict = generate_categ_dictionary()
        entry_type = "type"

        prompt = PROMPTS[entry_type].format(categ_dict=categ_dict,
                    subcateg_dict=subcateg_dict, content=content_lines[:1500])

        logger.debug("[DEBUG] process_get_note_type : %s", prompt)
        response = ollama_generate(prompt)
        #response = "Cinema/test"
        logger.debug("[DEBUG] process_get_note_type response : %s", response)

        parse_category = parse_category_response(response)
        if parse_category is None:
            logger.warning("[WARNING] Classification invalide, tentative de reclassement ultérieur.")
            handle_uncategorized(filepath, "Invalid format", "")
            return None
        
        logger.debug("[DEBUG] process_get_note_type parse_category %s", parse_category)
        note_type = clean_note_type(parse_category)

        logger.info("Type de note détecté pour %s : %s", filepath, note_type)
    except Exception as e:
        logger.error("Erreur lors de l'analyse : %s", e)
        handle_uncategorized(filepath, "Error", "")
        return None

    dir_type_name = get_path_safe(note_type, filepath)
    if dir_type_name is None:
        logger.warning("La note %s a été déplacée dans 'uncategorized'.", filepath)
        return None

    try:
        dir_type_name = Path(dir_type_name)
        dir_type_name.mkdir(parents=True, exist_ok=True)
        logger.debug("[DEBUG] dirtype_name %s", type(dir_type_name))
        logger.info("[INFO] Catégorie définie %s", dir_type_name)
    except Exception as e:
        logger.error("[ERREUR] Anomalie lors du process de catégorisation : %s", e)
        handle_uncategorized(filepath, note_type, "")
        return None

    try:
        new_path = shutil.move(filepath, dir_type_name)
        logger.info("[INFO] Note déplacée vers : %s", new_path)
        return new_path
    except Exception as e:
        logger.error("[ERREUR] Pb lors du déplacement : %s", e)
        handle_uncategorized(filepath, note_type, "")
        return None

def parse_category_response(response):
    pattern = r'([A-Za-z0-9_ ]+)/([A-Za-z0-9_ ]+)'
    match = re.search(pattern, response)
    if match:
        return f"{match.group(1).strip()}/{match.group(2).strip()}"
    return None


def clean_note_type(response):
    """
    Supprimer les guillemets et mettre en minuscule
    """
    logger.debug("[DEBUG] clean_note_type : %s", response)
    clean_str = response.strip().lower().replace('"', '').replace("'", '')

    # Remplacer les espaces par des underscores
    clean_str = clean_str.replace(" ", "_")

    # Supprimer les caractères interdits pour un nom de dossier/fichier
    clean_str = re.sub(r'[\:*?"<>|]', '', clean_str)

    # Supprimer un point en fin de nom (interdit sous Windows)
    clean_str = re.sub(r'\.$', '', clean_str)
    logger.debug("[DEBUG] clean_note_type : %s", clean_str)
    return clean_str

def generate_classification_dictionary():
    """
    Génère la section 'Classification Dictionary' du prompt à partir de note_paths.json.
    :return: Texte formaté pour le dictionnaire
    """
    note_paths = load_note_paths()
    logger.debug("[DEBUG] generate_classification_dictionary")
    classification_dict = "Classification Dictionary:\n"

    categories = note_paths.get("categories", {})
    
    for category, details in categories.items():
        description = details.get("description", "No description available.")
        classification_dict += f'- "{category}": {description}\n'
        
        subcategories = details.get("subcategories", {})
        for subcategory, sub_details in subcategories.items():
            sub_description = sub_details.get("description", "No description available.")
            classification_dict += f'  - "{subcategory}": {sub_description}\n'

    return classification_dict

def generate_optional_subcategories():
    """
    Génère uniquement la liste des sous-catégories disponibles, 
    en excluant les catégories sans sous-catégories.
    
    :return: Texte formaté avec les sous-catégories optionnelles.
    """
    logger.debug("[DEBUG] generate_optional_subcategories")
    subcateg_dict = "Optional Subcategories:\n"
    
    note_paths = load_note_paths()

    # 🔍 Vérification que note_paths["categories"] est bien un dictionnaire
    categories = note_paths.get("categories", {})
    if not isinstance(categories, dict):
        logger.error("[ERREUR] `categories` n'est pas un dictionnaire mais %s : %s", type(categories), categories)
        return ""  # Évite un crash

    for category, details in categories.items():
        if not isinstance(details, dict):
            logger.error("[ERREUR] Détails de la catégorie %s invalide : type %s", category, type(details))
            continue  # Passe à la catégorie suivante
        
        subcategories = details.get("subcategories", {})
        if not isinstance(subcategories, dict):
            logger.error("[ERREUR] `subcategories` pour %s n'est pas un dict mais %s", category, type(subcategories))
            continue  # Passe à la catégorie suivante
        
        if subcategories:  # 🔹 Ignore les catégories sans sous-catégories
            subcateg_names = ", ".join(sorted(subcategories.keys()))
            subcateg_dict += f'- "{category}": {subcateg_names}\n'

    return subcateg_dict if subcateg_dict != "Optional Subcategories:\n" else ""

def generate_categ_dictionary():
    """
    Génère la liste de toutes les catégories avec leurs descriptions, 
    qu'elles aient des sous-catégories ou non.
    
    :return: Texte formaté avec toutes les catégories.
    """
    note_paths = load_note_paths()
    logger.debug("[DEBUG] generate_categ_dictionary")
    categ_dict = "Categ Dictionary:\n"

    categories = note_paths.get("categories", {})

    for category, details in categories.items():
        explanation = details.get("description", "No description available.")
        categ_dict += f'- "{category}": {explanation}\n'

    return categ_dict

# Trouver ou créer un chemin
def get_path_safe(note_type, filepath):
    """
    Vérifie et crée les chemins si besoin pour une note importée.
    - Vérifie si la catégorie et la sous-catégorie existent.
    - Si non, elles sont créées automatiquement.
    - Vérifie aussi si une catégorie similaire existe avant d’en créer une nouvelle.
    """
    logger.debug("entrée get_path_safe avec note_type: %s", note_type)
    note_paths = load_note_paths()

    try:
        category, subcategory = note_type.split("/")
        
        # 🔹 Vérifie si la catégorie existe
        if category not in note_paths.get("categories", {}):
            logger.info(f"[INFO] Catégorie absente : {category}. Vérification de la similarité...")

            existing_categories = list(note_paths.get("categories", {}).keys())
            validated_category = check_and_handle_similarity(category, existing_categories, entity_type="category")

            if validated_category is None:
                logger.debug("get_path_safe: uncategorized (catégorie inconnue)")
                handle_uncategorized(filepath, note_type, llama_proposition=category)
                return None

            if validated_category == category:
                logger.debug("get_path_safe: %s == %s (Nouvelle catégorie validée)", validated_category, category)
                add_dynamic_category(category)
            else:
                logger.info(f"[INFO] Fusion avec la catégorie existante : {validated_category}")
                category = validated_category  # ✅ On utilise la catégorie existante validée

        # 🔹 Vérifie si la sous-catégorie existe
        try:
            return get_path_from_classification(category, subcategory)
        except KeyError:
            logger.info("Sous-catégorie absente : %s. Vérification de la similarité...", subcategory)
            existing_subcategories = list(
                note_paths.get("categories", {}).get(category, {}).get("subcategories", {}).keys()
            )
            validated_subcategory = check_and_handle_similarity(subcategory, existing_subcategories, entity_type="subcategory")
            
            if validated_subcategory is None:
                logger.debug("get_path_safe: uncategorized (sous-catégorie inconnue)")
                handle_uncategorized(filepath, note_type, llama_proposition=subcategory)
                return None
            
            if validated_subcategory == subcategory:
                logger.debug("get_path_safe: %s == %s (Nouvelle sous-catégorie validée)", validated_subcategory, subcategory)
                return add_dynamic_subcategory(category, subcategory)

            return get_path_from_classification(category, validated_subcategory)

    except ValueError:
        logger.error("Format inattendu du résultat Llama : %s", note_type)
        handle_uncategorized(filepath, note_type, llama_proposition="Invalid format")
        return None



# Ajouter une sous-catégorie dynamiquement
def add_dynamic_subcategory(category, subcategory):
    """
    Ajoute une sous-catégorie dynamiquement.
    """
    note_paths = load_note_paths()
    categories = note_paths.get("categories", {})
    folders = note_paths.get("folders", {})

    logger.debug("[DEBUG] add_dynamic_subcategory")

    # 🔹 Vérifier que la catégorie existe, sinon la créer
    if category not in categories:
        logger.warning(f"[WARN] La catégorie {category} n'existe pas. Création en cours...")
        add_dynamic_category(category)

    # 🔹 Récupérer le chemin de la catégorie
    base_path_str = next(
        (folder["path"] for folder in folders.values()
         if folder["category"] == category and folder.get("subcategory") is None),
        None
    )

    if not base_path_str:
        raise ValueError(f"[❌] Chemin introuvable pour la catégorie : {category}")

    base_path = Path(base_path_str)
    logger.debug("[DEBUG] base_path %s", base_path)
    first_parent_name = Path(base_path).parent.name
    new_subcategory_name = subcategory.capitalize()
    category_name = category.capitalize()
    new_path = base_path / new_subcategory_name
    logger.debug("[DEBUG] new_path %s", new_path)

    # 🔹 Création du dossier si inexistant
    if not new_path.exists():
        logger.info("[INFO] Création du dossier : %s", new_path)
        new_path.mkdir(parents=True, exist_ok=True)

    # 🔹 Ajout de la sous-catégorie dans `categories`
    categories[category]["subcategories"][subcategory] = {
        "description": f"Note about {subcategory.lower()}",
        "prompt_name": "divers"
    }

    # 🔹 Ajout du dossier dans `folders`
    folder_key = f"{first_parent_name}/{category_name}/{new_subcategory_name}"
    folders[folder_key] = {
        "path": str(new_path),
        "category": category,
        "subcategory": subcategory,
        "folder_type": "storage"
    }
    logger.debug("[DEBUG] folder_key %s", folder_key)
    # 🔹 Sauvegarde de `note_paths.json`
    note_paths["categories"] = categories
    note_paths["folders"] = folders
    logger.info(f"[INFO] note_paths[categories] : {note_paths["categories"]}")
    logger.info(f"[INFO] note_paths[folders] : {note_paths["folders"]}")
    save_note_paths(note_paths)

    return new_path

# Gérer les notes non catégorisées
def handle_uncategorized(filepath, note_type, llama_proposition):
    new_path = uncategorized_path / Path(filepath).name
    shutil.move(filepath, new_path)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(uncategorized_log, "a", encoding='utf-8') as log_file:
        log_file.write(f"[{current_time}] Note: {new_path} | Proposition: {llama_proposition} | Type original: {note_type}\n")
    logger.warning("Note déplacée vers 'uncategorized' : %s", new_path)
    
    # Sauvegarde pour reclassement ultérieur
    try:
        if os.path.exists(uncategorized_data):
            with open(uncategorized_data, "r", encoding='utf-8') as file:
                uncategorized_notes = json.load(file)
        else:
            uncategorized_notes = {}
        uncategorized_notes[str(new_path)] = {
            "original_type": note_type,
            "llama_proposition": llama_proposition,
            "date": current_time
        }
        with open(uncategorized_data, "w", encoding='utf-8') as file:
            json.dump(uncategorized_notes, file, indent=4)
    except Exception as e:
        logger.error("Erreur lors de la sauvegarde des notes non catégorisées : %s", e)

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

def add_dynamic_category(category):
    """
    Ajoute une nouvelle catégorie à `note_paths.json` si elle n'existe pas.
    """
    note_paths = load_note_paths()
    categories = note_paths.get("categories", {})
    folders = note_paths.get("folders", {})

    logger.info(f"[INFO] Création de la nouvelle catégorie : {category}")

    # 🔹 Création du chemin physique pour la catégorie
    base_path = Path(os.getenv('BASE_PATH')) / "Z_Storage" / category
    if not base_path.exists():
        logger.info(f"[INFO] Création du dossier catégorie : {base_path}")
        base_path.mkdir(parents=True, exist_ok=True)

    # 🔹 Ajout dans `categories`
    categories[category] = {
        "description": f"Note about {category.lower()}",
        "prompt_name": "divers",
        "subcategories": {}  # Initialement vide
    }

    # 🔹 Ajout du dossier dans `folders`
    folder_key = f"{category}"
    folders[folder_key] = {
        "path": str(base_path),
        "category": category,
        "subcategory": None,
        "folder_type": "storage"
    }

    # 🔹 Mise à jour et sauvegarde de `note_paths.json`
    note_paths["categories"] = categories
    note_paths["folders"] = folders
    logger.info(f"[INFO] note_paths[categories] : {note_paths["categories"]}")
    logger.info(f"[INFO] note_paths[folders] : {note_paths["folders"]}")
    save_note_paths(note_paths)

    return base_path
