"""
    fonctions en lien avec l'entête
    """
from datetime import datetime
from logger_setup import setup_logger
import logging
from pathlib import Path
from handlers.sql.db_update_notes import update_obsidian_note, update_obsidian_tags
from handlers.sql.db_get_linked_data import get_note_linked_data
from handlers.sql.db_get_linked_notes_utils import get_category_and_subcategory_names, get_synthesis_metadata, get_note_tags
from handlers.ollama.ollama import get_summary_from_ollama, get_tags_from_ollama
from handlers.utils.files import count_words, safe_write, read_note_content
from handlers.header.extract_yaml_header import extract_yaml_header, extract_metadata
from handlers.utils.normalization import sanitize_created, sanitize_yaml_title
from handlers.header.header_utils import clean_yaml_spacing_in_file

setup_logger("obsidian_headers", logging.DEBUG)
logger = logging.getLogger("obsidian_headers")

# Fonction pour ajouter ou mettre à jour les tags, résumés et commandes dans le front matter YAML
def add_metadata_to_yaml(note_id, filepath, tags=None, summary=None, status=None, synthesis_id=None):
    """
    Ajoute ou met à jour l'entête YAML d'un fichier Markdown.
    """

    try:
        logger.debug("[DEBUG] add_yaml : démarrage pour %s", filepath)
        logger.debug(f"[DEBUG] synthesis_id : {synthesis_id}")     
        # 🔥 Extraction rapide des métadonnées entête
        metadata = extract_metadata(filepath)
        title_yaml = metadata.get("title", Path(filepath).stem)
        source_yaml = metadata.get("source", "")
        author_yaml = metadata.get("author", "ChatGPT" if "ChatGPT" in title_yaml else "")
        project_yaml = metadata.get("project", "")
        created = metadata.get("created", "")
        created_yaml = sanitize_created(created)
        category_yaml = metadata.get("category", None)
        subcategory_yaml = metadata.get("sub category", None)
        nombre_mots = count_words(open(filepath, "r", encoding="utf-8").read())
        
        # 🔥 Extraction rapide des métadonnées table obsidian_notes
        data = get_note_linked_data(note_id, "note")
        logger.debug(f"[DEBUG] data : {data}")
        # Vérification si data existe avant d'utiliser .get() pour éviter une erreur
        title = sanitize_yaml_title(data.get("title") if data else title_yaml)
        category_id = data.get("category_id") if data else None
        subcategory_id = data.get("subcategory_id") if data else None
        status = data.get("status") if data else status
        summary = data.get("summary") if data else summary
        source = data.get("source") if data else source_yaml
        author = data.get("author") if data else author_yaml
        project = data.get("project") if data else project_yaml
        word_count = data.get("word_count") if data else None
        created = data.get("created_at") if data else created_yaml

        tags = tags or get_note_tags(note_id) or metadata.get("tags", [])
        tags = tags if isinstance(tags, list) else []
 
        logger.debug(f"[DEBUG] category_id, subcategory_id {category_id}, {subcategory_id}")
        category, subcategory = get_category_and_subcategory_names(note_id)
        logger.debug(f"[DEBUG] category, subcategory {category}, {subcategory}")
        
        if synthesis_id:
            logger.debug(f"[SYNC] Archive liée à la synthesis {synthesis_id}, synchronisation des métadonnées")

            title_syn, source_syn, author_syn, created_syn, category_id_syn, sub_category_id_syn = get_synthesis_metadata(synthesis_id)
            logger.debug(f"[DEBUG] author_syn : {author_syn}")
            title = title_syn or title
            source_yaml = source_syn or source_yaml
            author = author_syn or author
            created = created_syn or created

        # 🔥 Suppression de l'ancienne entête YAML
        content = read_note_content(filepath)
        lines = content.splitlines(True)  # conserve les sauts de ligne
        
        yaml_start, yaml_end = -1, -1
        if lines and lines[0].strip() == "---":
            yaml_start = 0
            yaml_end = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), -1)

        if yaml_start != -1 and yaml_end != -1:
            logger.debug("[DEBUG] Suppression de l'ancienne entête YAML")
            lines = lines[yaml_end + 1:]  # Supprime l'entête YAML existante

        # 🔥 Création de la nouvelle entête YAML
        yaml_block = [
            "---\n",
            f"title: {title}\n",
            f"tags: [{', '.join(tag.replace(' ', '_') for tag in tags)}]\n",
            f"summary: |\n  {summary.replace('\n', '\n  ')}\n",
            f"word_count: {nombre_mots}\n",
            f"category: {category}\n",
            f"sub category: {subcategory}\n",
            f"created: {created}\n",
            f"last_modified: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"source: {source_yaml}\n",
            f"author: {author}\n",
            f"status: {status}\n",
            f"project: {project}\n",
            "---\n\n"
        ]

        # 🔥 Sauvegarde sécurisée dans un fichier temporaire
        success = safe_write(filepath, content=yaml_block + lines)
        if not success:
            logger.error(f"[main] Problème lors de l’écriture sécurisée de {filepath}")
       
        clean_yaml_spacing_in_file(filepath)
        logger.info("[INFO] Génération de l'entête terminée avec succès pour %s", filepath)

    except FileNotFoundError as e:
        logger.error("Erreur : fichier non trouvé %s", filepath)
    except Exception as e:
        logger.error("[ERREUR] Problème lors de l'ajout du YAML : %s", e, exc_info=True)

def make_properties(filepath, note_id, status):
    """
    Génère les entêtes et met à jour les métadonnées.
    """
    logger.debug("[DEBUG] make_pro : Entrée de la fonction")
    
    
    # Extraction de l'entête YAML
    _, content_lines = extract_yaml_header(filepath)
    content = content_lines

    # Récupération des tags et du résumé
    logger.debug("[DEBUG] make_pro : Récupération des tags et résumé")
    tags = get_tags_from_ollama(content)
    summary = get_summary_from_ollama(content)

    updates = {
    'status': status,    # Récupéré via make_properties
    'summary': summary   # Récupéré via make_properties
    }
    update_obsidian_note(note_id, updates)
    update_obsidian_tags(note_id, tags)
    # Mise à jour des métadonnées YAML
    logger.debug("[DEBUG] make_pro : Mise à jour du YAML")
    add_metadata_to_yaml(note_id, filepath, tags, summary, status)

    # Lecture et mise à jour en une seule passe
    with open(filepath, "r+", encoding="utf-8") as file:
        lines = file.readlines()

        # Recalcule du nombre de mots après mise à jour complète
        updated_content = "".join(lines)
        nombre_mots_actuels = count_words(updated_content)
        logger.debug("[DEBUG] make_pro : Recalcul du nombre de mots")

        # Mise à jour de la ligne `word_count`
        word_count_updated = False
        for i, line in enumerate(lines):
            if line.startswith("word_count:"):
                lines[i] = f"word_count: {nombre_mots_actuels}\n"
                word_count_updated = True
                logger.debug("[DEBUG] make_pro : Mise à jour de word_count existant")
                break

        if not word_count_updated:
            # Ajout du champ `word_count` s'il n'existe pas
            logger.debug("[DEBUG] make_pro : Ajout du champ word_count pour")
            lines.insert(3, f"word_count: {nombre_mots_actuels}\n")

        # Retour au début du fichier et écriture des modifications
        file.seek(0)
        file.writelines(lines)
        file.truncate()  # Supprime tout contenu restant si le nouveau contenu est plus court

    logger.debug("[DEBUG] make_pro : Écriture réussie et fichier mis à jour")
    updates = {
    'word_count': nombre_mots_actuels
    }
    update_obsidian_note(note_id, updates)

def check_type_header(filepath):
    """
    récupération du type synthèse ou archive.
    """
    try:
        logger.debug("[DEBUG] check_type démarrage fonction")
        with open(filepath, "r", encoding="utf-8") as file:
            lines = file.readlines()
        # Vérification de l'entête YAML
        yaml_start, yaml_end = -1, -1
        if lines[0].strip() == "---":
            yaml_start = 0
            yaml_end = next((i for i, line in enumerate(lines[1:], start=1)
                             if line.strip() == "---"), -1)
            if yaml_end != -1:
                logger.debug("[DEBUG] add_yaml : entête détectée %s à %s", yaml_start, yaml_end)
                yaml_header = lines[1:yaml_end]
                # Récupérer les données existantes
                for line in yaml_header:
                    if line.startswith("type:"):
                        note_type = line.split(":", 1)[1].strip()
                        return note_type
    except FileNotFoundError as e:
        logger.error("Erreur lors du traitement de l'entête YAML pour %s : %s",filepath, e)
    return None

# Fonction pour lire l'entête d'un fichier et récupérer category/subcategory
def extract_category_and_subcategory(filepath):
    """
    Lit l'entête d'un fichier pour extraire la catégorie et la sous-catégorie.
    On suppose que les lignes sont au format :
    category: valeur
    subcategory: valeur
    """
    category = None
    subcategory = None
    try:
        with open(filepath, 'r', encoding="utf-8") as file:
            for line in file:
                if line.startswith("category:"):
                    category = line.split(":")[1].strip()
                elif line.startswith("subcategory:"):
                    subcategory = line.split(":")[1].strip()
            return category, subcategory
    except FileNotFoundError as e:
        logger.error("[ERREUR] Impossible de lire l'entête du fichier %s : %s",filepath, e)
        return None, None

