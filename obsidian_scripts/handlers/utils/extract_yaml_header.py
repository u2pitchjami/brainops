"""
Ce module extrait les en-têtes YAML des fichiers de notes Obsidian.
"""
from logger_setup import setup_logger
from handlers.utils.sql_helpers import link_notes_parent_child
from handlers.utils.files import safe_write
import logging
import re
import os
import yaml

setup_logger("extract_yaml_header", logging.DEBUG)
logger = logging.getLogger("extract_yaml_header")
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

def extract_metadata(filepath):
    """
    Extrait toutes les métadonnées YAML d'une note.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            content = file.read()

        logger.debug(f"[DEBUG] extract_metadata : {content}")
        yaml_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        metadata = yaml.safe_load(yaml_match.group(1)) if yaml_match else {}

        return metadata or {}

    except Exception as e:
        logger.error(f"[ERREUR] Impossible de lire l'entête du fichier {filepath} : {e}")
        return {}

def extract_note_metadata(filepath, old_metadata=None):
    """
    Extrait toutes les métadonnées d'une note en une seule lecture,
    en fusionnant avec d'anciennes métadonnées si nécessaire.

    :param filepath: Chemin absolu du fichier Markdown.
    :param old_metadata: Métadonnées précédentes (ex: en cas de déplacement).
    :return: Dictionnaire avec `title`, `category`, `subcategory`, `tags`, `status`, etc.
    """
    logger.debug(f"[DEBUG] extract_note_metadata : {filepath}")

    # 🔥 Récupération directe des métadonnées avec `extract_metadata()`
    metadata = extract_metadata(filepath)

    # 🔥 Définition des valeurs par défaut si absentes
    default_values = {
        "title": None,
        "category": None,
        "sub category": None,
        "tags": [],
        "status": "draft",
        "created": None,
        "last_modified": None,
        "project": None,
        "note_id": None
    }

    # 🔥 Fusion avec `old_metadata` et application des valeurs par défaut
    if old_metadata:
        default_values.update(old_metadata)  # 🔄 Priorité aux anciennes valeurs si existantes
    default_values.update({k: v for k, v in metadata.items() if v})  # 🔄 Ajout des nouvelles valeurs si elles existent

    logger.debug(f"[DEBUG] Métadonnées finales : {default_values}")
    return default_values

def get_yaml_value(yaml_header, key, default=None):
    """ Récupère une valeur dans le YAML en évitant les erreurs. """
    for line in yaml_header:
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()  # 🔹 Récupère la valeur après `:` proprement

    return default  # 🔹 Si non trouvé, retourne la valeur par défaut

def extract_note_id(yaml_header):
    """
    Extrait le `title` depuis l'entête YAML.
    """
    logger.debug(f"[DEBUG] extract_note_id : {yaml_header}")
    note_id = None
   
    for line in yaml_header:
        if line.startswith("note_id:"):
            note_id = line.split(":")[1].strip()
            logger.debug(f"[DEBUG]  extract_note_id : {note_id}")
            break
    return note_id

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
    
def ensure_note_id_in_yaml(file_path, incoming_note_id, status="draft"):
    """
    Vérifie et insère le note_id dans l'entête YAML si nécessaire.
    - Évite d'écrire inutilement si le note_id est déjà correct.
    - Garde note_id en entier sans guillemets.
    """
    try:
        incoming_note_id = int(incoming_note_id)
    except ValueError:
        logger.error(f"❌ [ERROR] incoming_note_id invalide : {incoming_note_id}")
        return

    logger.debug(f"[DEBUG] Entrée ensure_note_id_in_yaml incoming_note_id={incoming_note_id}")

    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
        logger.debug(f"[DEBUG] Contenu AVANT traitement :\n{content[:500]}...")  # on évite de logguer 5k lignes

    yaml_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)

    if yaml_match:
        metadata = yaml.safe_load(yaml_match.group(1)) or {}
        yaml_note_id = metadata.get("note_id")

        logger.debug(f"🔍 [DEBUG] note_id récupéré depuis le YAML : {yaml_note_id}")

        if isinstance(yaml_note_id, str):
            yaml_note_id = yaml_note_id.strip('"').strip("'").strip()

        try:
            yaml_note_id = int(yaml_note_id) if yaml_note_id is not None else None
        except ValueError:
            logger.warning(f"⚠️ [WARNING] Conversion en int impossible pour note_id : {yaml_note_id}")
            yaml_note_id = None

        if yaml_note_id == incoming_note_id:
            logger.debug(f"🔄 [DEBUG] Le note_id est déjà correct ({incoming_note_id}), pas d'écriture")
            return

        metadata["note_id"] = incoming_note_id
        logger.debug(f"[DEBUG] Mise à jour du note_id : {incoming_note_id}")
        logger.debug(f"[DEBUG] status : {status}")

        new_yaml = f"---\n{yaml.dump(metadata, default_flow_style=False)}---\n"
        new_content = new_yaml + content[len(yaml_match.group(0)):]
        if status == "archive":
            link_notes_parent_child(incoming_note_id, yaml_note_id)

    else:
        logger.warning(f"❗ [WARNING] Entête YAML absente ou mal formée dans : {file_path}")
        new_content = f"---\nnote_id: {incoming_note_id}\n---\n{content}"

    # Vérification avant écriture
    with open(file_path, "r", encoding="utf-8") as file:
        existing_content = file.read()

    if existing_content == new_content:
        logger.debug(f"🔄 [DEBUG] Le fichier {file_path} est déjà à jour, pas d'écriture")
        return

    logger.debug(f"💾 [DEBUG] Écriture du fichier {file_path} (note_id mis à jour)")
    success = safe_write(file_path, content=new_content, verify_contains="note_id:")
    if not success:
        logger.error(f"[main] Problème lors de l’écriture sécurisée de {file_path}")
    
    logger.info(f"[INFO] Lien mis à jour pour : {file_path}")
    
    
    with open(file_path, "r", encoding="utf-8") as file:
        after_write = file.read()
        logger.debug(f"[DEBUG] DEBUG NOTE_ID (post-écriture) : {after_write[:500]}...")
