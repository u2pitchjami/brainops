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
from handlers.process.ollama import call_ollama_with_retry, OllamaError
from handlers.utils.extract_yaml_header import extract_yaml_header
from handlers.process.prompts import PROMPTS
from handlers.utils.sql_helpers import get_path_from_classification, get_db_connection

setup_logger("get_type", logging.INFO)
logger = logging.getLogger("get_type")

similarity_warnings_log = os.getenv('SIMILARITY_WARNINGS_LOG')
uncategorized_log = os.getenv('UNCATEGORIZED_LOG')
uncategorized_path = Path(os.getenv('UNCATEGORIZED_PATH'))
uncategorized_path.mkdir(parents=True, exist_ok=True)
uncategorized_data = "uncategorized_notes.json"

def process_get_note_type(filepath):
    """Analyse le type de note via Llama3.2."""
    logger.debug("[DEBUG] Entrée process_get_note_type")
    model_ollama = os.getenv('MODEL_GET_TYPE')

    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()
    try:
        logger.debug("[DEBUG] process_get_note_type avant extract yaml")
        _, content_lines = extract_yaml_header(content)
        logger.debug("[DEBUG] process_get_note_type content_lines %s", content_lines)
        subcateg_dict = generate_optional_subcategories()
        logger.debug("[DEBUG] process_get_note_type subcateg_dict %s", subcateg_dict)
        categ_dict = generate_categ_dictionary()
        logger.debug("[DEBUG] process_get_note_type categ_dict %s", categ_dict)
        entry_type = "type"

        prompt = PROMPTS[entry_type].format(categ_dict=categ_dict,
                    subcateg_dict=subcateg_dict, content=content_lines[:1500])

        logger.debug("[DEBUG] process_get_note_type : %s", prompt)
        
        try:
            response = call_ollama_with_retry(prompt, model_ollama)
            #response = "Politics/Europe"
            logger.debug("[DEBUG] process_get_note_type response : %s", response)
        except OllamaError:
            logger.error("[ERROR] Import annulé.")

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
    Génère la section 'Classification Dictionary' du prompt à partir de la base MySQL.
    :return: Texte formaté pour le dictionnaire
    """
    conn = get_db_connection()
    if not conn:
        return ""
    cursor = conn.cursor(dictionary=True)

    logger.debug("[DEBUG] generate_classification_dictionary")
    classification_dict = "Classification Dictionary:\n"

    # 🔹 Récupérer toutes les catégories et sous-catégories
    cursor.execute("SELECT id, name, description FROM obsidian_categories WHERE parent_id IS NULL")
    categories = cursor.fetchall()

    for category in categories:
        description = category["description"] or "No description available."
        classification_dict += f'- "{category["name"]}": {description}\n'
        
        # 🔹 Récupérer les sous-catégories associées
        cursor.execute("SELECT name, description FROM obsidian_categories WHERE parent_id = %s", (category["id"],))
        subcategories = cursor.fetchall()

        for subcategory in subcategories:
            sub_description = subcategory["description"] or "No description available."
            classification_dict += f'  - "{subcategory["name"]}": {sub_description}\n'

    conn.close()
    return classification_dict

def generate_optional_subcategories():
    """
    Génère uniquement la liste des sous-catégories disponibles, 
    en excluant les catégories sans sous-catégories.
    
    :return: Texte formaté avec les sous-catégories optionnelles.
    """
    conn = get_db_connection()
    if not conn:
        return ""
    cursor = conn.cursor(dictionary=True)

    logger.debug("[DEBUG] generate_optional_subcategories")
    subcateg_dict = "Optional Subcategories:\n"

    # 🔹 Récupérer toutes les catégories ayant des sous-catégories
    cursor.execute("""
        SELECT c1.name AS category_name, c2.name AS subcategory_name
        FROM obsidian_categories c1 
        JOIN obsidian_categories c2 ON c1.id = c2.parent_id
        ORDER BY c1.name, c2.name
    """)
    results = cursor.fetchall()

    # 🔹 Organisation des données
    categories_with_subcategories = {}
    for row in results:
        category = row["category_name"]
        subcategory = row["subcategory_name"]

        if category not in categories_with_subcategories:
            categories_with_subcategories[category] = []
        categories_with_subcategories[category].append(subcategory)

    # 🔹 Construire le dictionnaire final
    for category, subcategories in categories_with_subcategories.items():
        subcateg_dict += f'- "{category}": {", ".join(sorted(subcategories))}\n'

    conn.close()
    return subcateg_dict if subcateg_dict != "Optional Subcategories:\n" else ""

def generate_categ_dictionary():
    """
    Génère la liste de toutes les catégories avec leurs descriptions, 
    qu'elles aient des sous-catégories ou non.
    
    :return: Texte formaté avec toutes les catégories.
    """
    conn = get_db_connection()
    if not conn:
        return ""
    cursor = conn.cursor(dictionary=True)

    logger.debug("[DEBUG] generate_categ_dictionary")
    categ_dict = "Categ Dictionary:\n"

    # 🔹 Récupérer toutes les catégories
    cursor.execute("SELECT name, description FROM obsidian_categories WHERE parent_id IS NULL")
    categories = cursor.fetchall()

    for category in categories:
        explanation = category["description"] or "No description available."
        categ_dict += f'- "{category["name"]}": {explanation}\n'

    conn.close()
    return categ_dict

# Trouver ou créer un chemin
def get_path_safe(note_type, filepath):
    """
    Vérifie et crée les chemins si besoin pour une note importée.
    - Vérifie si la catégorie et la sous-catégorie existent.
    - Si non, elles sont créées automatiquement.
    - Vérifie aussi si une catégorie similaire existe avant d’en créer une nouvelle.
    """
    logger.debug("Entrée get_path_safe avec note_type: %s", note_type)

    try:
        category, subcategory = note_type.split("/")
        
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor(dictionary=True)

        # 🔹 Vérifier si la catégorie existe
        cursor.execute("SELECT id FROM obsidian_categories WHERE name = %s AND parent_id IS NULL", (category,))
        category_result = cursor.fetchone()
        logger.debug("get_path_safe category_result: %s", category_result)
        if not category_result:
            logger.info(f"[INFO] Catégorie absente : {category}. Création en cours...")
            category_id = add_dynamic_category(category)
        else:
            category_id = category_result["id"]

        # 🔹 Vérifier si la sous-catégorie existe
        cursor.execute("SELECT id FROM obsidian_categories WHERE name = %s AND parent_id = %s", (subcategory, category_id))
        subcategory_result = cursor.fetchone()

        if not subcategory_result:
            logger.info(f"[INFO] Sous-catégorie absente : {subcategory}. Création en cours...")
            subcategory_id = add_dynamic_subcategory(category, subcategory)
        else:
            subcategory_id = subcategory_result["id"]

        conn.close()
        return get_path_from_classification(category, subcategory)

    except ValueError:
        logger.error("Format inattendu du résultat Llama : %s", note_type)
        handle_uncategorized(filepath, note_type, llama_proposition="Invalid format")
        return None




# Ajouter une sous-catégorie dynamiquement
def add_dynamic_subcategory(category, subcategory):
    """
    Ajoute une sous-catégorie dans la base de données.
    """
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    # 🔹 Récupérer l'ID de la catégorie parent
    cursor.execute("SELECT id FROM obsidian_categories WHERE name = %s AND parent_id IS NULL", (category,))
    category_result = cursor.fetchone()

    if not category_result:
        logger.warning(f"[WARN] Impossible d'ajouter la sous-catégorie {subcategory}, la catégorie {category} est absente.")
        conn.close()
        return None

    category_id = category_result[0]

    logger.info(f"[INFO] Création de la sous-catégorie : {subcategory} sous {category}")

    # 🔹 Création de la sous-catégorie
    cursor.execute("""
        INSERT INTO obsidian_categories (name, parent_id, description, prompt_name) 
        VALUES (%s, %s, %s, %s)
    """, (subcategory, category_id, f"Note about {subcategory.lower()}", "divers"))

    subcategory_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return subcategory_id


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
    Ajoute une nouvelle catégorie dans la base de données si elle n'existe pas.
    """
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    logger.info(f"[INFO] Création de la nouvelle catégorie : {category}")

    # 🔹 Création dans la base
    cursor.execute("""
        INSERT INTO obsidian_categories (name, description, prompt_name) 
        VALUES (%s, %s, %s)
    """, (category, f"Note about {category.lower()}", "divers"))

    category_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return category_id
