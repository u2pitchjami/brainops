"""
Ce module extrait les en-têtes YAML des fichiers de notes Obsidian.
"""
from logger_setup import setup_logger
import logging
import re
import yaml

setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")
def extract_yaml_header(content):
    """
    Extrait l'entête YAML d'un texte s'il existe.
    
    Args:
        text (str): Le texte à analyser.
    
    Returns:
        tuple: (header_lines, content_lines)
            - header_lines : Liste contenant les lignes de l'entête YAML.
            - content_lines : Liste contenant le reste du texte sans l'entête.
    """
    logger.debug("[DEBUG] entrée extract_yaml_header")
    lines = content.strip().split("\n")  # Découpe le contenu en lignes
    if lines[0].strip() == "---":  # Vérifie si la première ligne est une délimitation YAML
        logger.debug("[DEBUG] extract_yaml_header line 0 : ---")
        yaml_start = 0
        yaml_end = next((i for i, line in enumerate(lines[1:], start=1)
                         if line.strip() == "---"), -1)
        logger.debug("[DEBUG] extract_yaml_header yalm_end : %s ", yaml_end)
        header_lines = lines[yaml_start:yaml_end + 1]  # L'entête YAML
        content_lines = lines[yaml_end + 1:]  # Le reste du contenu
    else:
        header_lines = []
        content_lines = lines  # Tout le contenu est traité comme texte

    logger.debug("[DEBUG] extract_yaml_header header : %s ", repr(header_lines))
    logger.debug("[DEBUG] extract_yaml_header content : %s ", content_lines[:5])
    # Rejoindre content_lines pour retourner une chaîne
    return header_lines, "\n".join(content_lines)

def extract_category_and_subcategory(filepath):
    """
    Lit l'entête d'un fichier pour extraire la catégorie et la sous-catégorie.
    On suppose que les lignes sont au format :
    category: valeur
    subcategory: valeur
    """
    logger.debug("[DEBUG] extract_category_and_subcategory %s", filepath)
    category = None
    subcategory = None
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith("category:"):
                    category = line.split(":")[1].strip()
                    logger.debug("[DEBUG] extract_category_and_subcategory %s", category)
                elif line.startswith("sub category:"):
                    subcategory = line.split(":")[1].strip()
            return category, subcategory
    except ValueError as e:
        logger.error("[ERREUR] Impossible de lire l'entête du fichier %s : %s", filepath, e)
        return None, None

def extract_status(filepath):
    """
    Lit l'entête d'un fichier pour extraire la catégorie et la sous-catégorie.
    On suppose que les lignes sont au format :
    category: valeur
    subcategory: valeur
    """
    status = None
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith("status:"):
                    status = line.split(":")[1].strip()
            return status
    except FileNotFoundError as e:
        logger.error("[ERREUR] Impossible de lire l'entête du fichier %s : %s", filepath, e)
        return None

def extract_tags(yaml_header):
    tags_existants = []
    in_tags = False

    for line in yaml_header:
        stripped_line = line.strip()
        logger.debug(f"[DEBUG] Tags : {stripped_line}")

        if stripped_line.startswith("tags:") and "[" in stripped_line:
            logger.debug(f"[DEBUG] Tags 1")
            tags_str = stripped_line.replace("tags:", "").strip()
            tags_str = tags_str.strip("[]")
            tags_existants = [tag.strip() for tag in tags_str.split(",")]
            in_tags = False

        elif stripped_line.startswith("tags:") and "[" not in stripped_line:
            logger.debug(f"[DEBUG] Tags 2")
            in_tags = True
            tags_existants = []

        elif in_tags:
            clean_line = line.lstrip()
            logger.debug(f"[DEBUG] Tags 3")
            if clean_line.startswith("- "):
                tag = clean_line.replace("- ", "").strip()
                tags_existants.append(tag)
            elif stripped_line == "" or re.match(r"^\w+:.*$", stripped_line):
                in_tags = False

    logger.debug(f"[DEBUG] Tags extraits : {tags_existants}")
    return tags_existants

def extract_summary(yaml_header):
    resume_existant = []
    in_summary = False

    for line in yaml_header:
        stripped_line = line.strip()

        if stripped_line.startswith("summary:"):
            in_summary = True
            summary_content = stripped_line.replace("summary:", "").strip()

            if summary_content and summary_content != "|":  # Si résumé en ligne unique
                resume_existant.append(summary_content)
                in_summary = False
            elif summary_content == "|":  # Détection du résumé en bloc multi-lignes
                resume_existant = []
            else:
                in_summary = False

        elif in_summary:
            if stripped_line == "" or re.match(r"^\w+:.*$", stripped_line):  # Fin du bloc summary
                in_summary = False
            else:
                resume_existant.append(stripped_line)

    resume_existant = "\n".join(resume_existant).strip()
    logger.debug(f"[DEBUG] Résumé extrait : {resume_existant}")
    return resume_existant

def extract_metadata(yaml_header, key_to_extract=None):
    """
    Extrait les métadonnées de l'entête YAML.
    
    :param yaml_header: Liste des lignes de l'entête YAML.
    :param key_to_extract: Si spécifié, retourne uniquement la valeur de cette clé.
    :return: Dictionnaire des métadonnées ou la valeur de la clé spécifiée.
    """
    logger.debug(f"[DEBUG] extract_metadata : {yaml_header}")
    metadata = {}
    for line in yaml_header:
        stripped_line = line.strip()

        if ":" in stripped_line:
            key, value = stripped_line.split(":", 1)
            key = key.strip()
            value = value.strip()
            metadata[key] = value

    if key_to_extract:
        result = metadata.get(key_to_extract, None)
        logger.debug(f"[DEBUG] Métadonnée extraite pour '{key_to_extract}' : {result}")
        return result

    logger.debug(f"[DEBUG] Métadonnées extraites : {metadata}")
    return metadata

def extract_note_metadata(filepath, old_metadata=None):
    """
    Extrait toutes les métadonnées d'une note en une seule lecture.

    :param filepath: Chemin absolu du fichier Markdown.
    :param old_metadata: Métadonnées précédentes si elles existent (ex: en cas de déplacement).
    :return: Dictionnaire avec `title`, `category`, `subcategory`, `tags`, `status`
    """
    logger.debug(f"[DEBUG] extract_note_metadata : {filepath}")
    with open(filepath, "r", encoding="utf-8") as file:
            content = file.read()
    
    logger.debug(f"[DEBUG] extract_note_metadata content : {content}")
    
    metadata = {
        "title": None,
        "category": None,
        "subcategory": None,
        "tags": [],
        "status": None,
        "created_at": None,
        "modified_at": None
    }

    # Lire l'entête YAML
    yaml_header, _ = extract_yaml_header(content)
    logger.debug(f"[DEBUG] extract_note_metadata yaml_header : {yaml_header}")
    # 🔥 Convertir `yaml_header` en chaîne si c'est une liste
    #if isinstance(yaml_header, list):
    #    yaml_header = "\n".join(yaml_header)  # ✅ Transformer la liste en une seule chaîne
    
    logger.debug(f"[DEBUG] extract_note_metadata yaml_header type : {type(yaml_header)}")
    if yaml_header:
        metadata["title"] = extract_title(yaml_header)
        metadata["tags"] = extract_tags_from_yaml(yaml_header) or []
        metadata["status"] = extract_status_from_yaml(yaml_header) or "draft"
        metadata["category"], metadata["subcategory"] = extract_category_and_subcategory_from_yaml(yaml_header)
        metadata["created_at"] = extract_created_from_yaml(yaml_header)
        metadata["modified_at"] = extract_modified_at_from_yaml(yaml_header)

    # Si certaines valeurs sont absentes, récupérer les anciennes valeurs (ex: après un déplacement)
    if old_metadata:
        metadata["title"] = metadata["title"] or old_metadata.get("title")
        metadata["category"] = metadata["category"] or old_metadata.get("category")
        metadata["subcategory"] = metadata["subcategory"] or old_metadata.get("subcategory")
        metadata["tags"] = metadata["tags"] or old_metadata.get("tags", [])
        metadata["status"] = metadata["status"] or old_metadata.get("status", "draft")
        metadata["created_at"] = metadata["created_at"] or old_metadata.get("created_at") or "unknown"
        metadata["modified_at"] = metadata["modified_at"] or old_metadata.get("modified_at") or "unknown"

    logger.debug(f"[DEBUG] Métadonnées extraites : {metadata}")
    return metadata

def get_yaml_value(yaml_header, key, default=None):
    """ Récupère une valeur dans le YAML en évitant les erreurs. """
    for line in yaml_header:
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()  # 🔹 Récupère la valeur après `:` proprement

    return default  # 🔹 Si non trouvé, retourne la valeur par défaut


def extract_title(yaml_header):
    """
    Extrait le `title` depuis l'entête YAML.
    """
    logger.debug(f"[DEBUG] extract_title : {yaml_header}")
    title = None
   
    for line in yaml_header:
        if line.startswith("title:"):
            title = line.split(":")[1].strip()
            logger.debug(f"[DEBUG]  extract_title title : {title}")
            break
    return title or get_title_from_filename(filepath)  # ✅ Utilise le nom de fichier si YAML vide
   
    
def get_title_from_filename(filepath):
    """
    Extrait le titre à partir du nom de fichier en retirant la date s'il y en a une.
    Ex: `250130_Titre.md` → `Titre`
    """
    logger.debug(f"[DEBUG]  get_title_from_filename : {filepath}")
    filename = Path(filepath).stem  # Enlève l'extension `.md`
    return re.sub(r"^\d{6}_", "", filename).replace("_", " ")  # Supprime la date si présente

def extract_modified_at_from_yaml(yaml_header):
    """
    Lit l'entête d'un fichier pour extraire la catégorie et la sous-catégorie.
    On suppose que les lignes sont au format :
    category: valeur
    subcategory: valeur
    """
    return get_yaml_value(yaml_header, "last_modified")

def extract_created_from_yaml(yaml_header):
    """
    Lit l'entête d'un fichier pour extraire la catégorie et la sous-catégorie.
    On suppose que les lignes sont au format :
    category: valeur
    subcategory: valeur
    """
    return get_yaml_value(yaml_header, "created")

def extract_status_from_yaml(yaml_header):
    """ Extrait le `status` depuis l'entête YAML, retourne `"unknown"` si absent. """
    return get_yaml_value(yaml_header, "status", "unknown")

def extract_category_and_subcategory_from_yaml(yaml_header):
    """
    Lit l'entête d'un fichier pour extraire la catégorie et la sous-catégorie.
    On suppose que les lignes sont au format :
    category: valeur
    subcategory: valeur
    """
    category = get_yaml_value(yaml_header, "category")
    subcategory = get_yaml_value(yaml_header, "sub category")
    logger.debug(f"[DEBUG] extract_category_and_subcategory_from_yaml subcategory: {subcategory}")
    return category, subcategory

def extract_tags_from_yaml(yaml_header):
    logger.debug(f"[DEBUG] extract_tags_from_yaml : {type(yaml_header)}")
    try:
        # 🔹 Assurer que yaml_header est bien une chaîne de texte
        if isinstance(yaml_header, list):
            yaml_header = "\n".join(yaml_header)  # Convertir la liste en texte
            logger.debug(f"[DEBUG] extract_tags_from_yaml type 2 : {type(yaml_header)}")
        
        if yaml_header.startswith('---'):
            yaml_part = yaml_header.split('---')[1]
            yaml_data = yaml.safe_load(yaml_part)
            tags = yaml_data.get('tags', [])
            logger.debug(f"[DEBUG] extract_tags_from_yaml tags : {tags}")

            if isinstance(tags, list):
                return tags

            if isinstance(tags, str):
                try:
                    parsed_tags = json.loads(tags)
                    if isinstance(parsed_tags, list):
                        return parsed_tags
                except json.JSONDecodeError:
                    return [tags.strip()]
        return []
    except Exception as e:
        print(f"[ERREUR] Impossible de lire les tags YAML de {yaml_header}: {e}")
        return []