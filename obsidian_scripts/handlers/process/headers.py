"""
    fonctions en lien avec l'entête
    """
import os
from datetime import datetime
from logger_setup import setup_logger
import logging
from pathlib import Path
from handlers.process.ollama import get_summary_from_ollama, get_tags_from_ollama
from handlers.utils.files import count_words
from handlers.utils.extract_yaml_header import extract_yaml_header

setup_logger("obsidian_notes", logging.INFO)
logger = logging.getLogger("obsidian_notes")

# Fonction pour ajouter ou mettre à jour les tags, résumés et commandes dans le front matter YAML
def add_metadata_to_yaml(filepath, tags, summary, category, subcategory, status):
    """
    génère l'entête
    """
    try:
        logger.debug("[DEBUG] add_yaml : démarrage fonction : %s %s",filepath, status)
        logger.debug("[DEBUG] add_yaml : démarrage fonction : %s / %s", category, subcategory)

        with open(filepath, "r", encoding="utf-8") as file:
            lines = file.readlines()
        # Initialisation des données
        title = Path(filepath).stem
        source_yaml = ""
        author = ""
        project = ""
        date_creation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nombre_mots = count_words("".join(lines))
        if "ChatGPT" in title:
            author = "ChatGPT"

        # Recherche des données dans tout le document
        for line in lines:
            if line.startswith("created:"):
                date_creation = line.split(":", 1)[1].strip()
            elif line.startswith("source:"):
                source_yaml = line.split(":", 1)[1].strip()
            elif line.startswith("author:"):
                author = line.split(":", 1)[1].strip()
            elif line.startswith("project:"):
                project = line.split(":", 1)[1].strip()
            elif line.startswith("title:"):
                title = line.split(":", 1)[1].strip()
        # Vérification de l'entête YAML
        yaml_start, yaml_end = -1, -1
        if lines[0].strip() == "---":
            yaml_start = 0
            yaml_end = next((i for i, line in enumerate(lines[1:], start=1)
                             if line.strip() == "---"), -1)
        # Supprimer l'ancienne entête YAML si présente
        if yaml_start != -1 and yaml_end != -1:
            logger.debug("[DEBUG] add_yaml : suppression de l'ancienne entête YAML")
            lines = lines[yaml_end + 1:]  # Supprime tout jusqu'à la fin de l'entête YAML
            logger.debug("[DEBUG] add_yaml lines %s", lines)

        if not title:
            title = os.path.basename(filepath).replace(".md", "")

        logger.debug(f"[DEBUG] make_properties() - Données extraites : Status={status}, Tags={tags}, Source={source_yaml}, Author={author}")

        # Créer une nouvelle entête YAML complète
        yaml_block = [
            "---\n",
            f"title: {title}\n",
            f"tags: [{', '.join(f'{tag.replace(" ", "_")}' for tag in tags)}]\n",
            f"summary: |\n  {summary.replace('\n', '\n  ')}\n",
            f"word_count: {nombre_mots}\n",
            f"category: {category}\n",
            f"sub category: {subcategory}\n",
            f"created: {date_creation}\n",
            f"last_modified: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"source: {source_yaml}\n",
            f"author: {author}\n",
            f"status: {status}\n",
            f"project: {project}\n",
            "---\n\n"
        ]
        
        # Insérer la nouvelle entête
        lines = yaml_block + lines
        try:
            logger.debug("[DEBUG] add_yaml : nouvelle entête : %s / %s",category, subcategory)
            logger.debug("Add_Metadata_to_yaml : Préparation à écrire : %s",yaml_block)
            # Sauvegarde dans le fichier
            with open(filepath, "w", encoding="utf-8") as file:
                file.writelines(lines)
            logger.info("[INFO] Génération de l'entête terminée")
            logger.debug("Add_Metadata_to_yaml Écriture réussie dans le fichier")
        except FileNotFoundError as e:
            logger.error("Erreur lors de l'écriture dans le fichier : %s",e, exc_info=True)
    except Exception as e:  # nosec: catch-all
        logger.error("[ERROR]Fichier non trouvé : %s", e)

def make_properties(content, filepath, category, subcategory, status):
    """
    Génère les entêtes et met à jour les métadonnées.
    """
    logger.debug("[DEBUG] make_pro : Entrée de la fonction")

    # Extraction de l'entête YAML
    _, content_lines = extract_yaml_header(content)
    content = content_lines

    # Récupération des tags et du résumé
    logger.debug("[DEBUG] make_pro : Récupération des tags et résumé")
    tags = get_tags_from_ollama(content)
    summary = get_summary_from_ollama(content)

    # Mise à jour des métadonnées YAML
    logger.debug("[DEBUG] make_pro : Mise à jour du YAML")
    add_metadata_to_yaml(filepath, tags, summary, category, subcategory, status)

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
