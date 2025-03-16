"""
    fonctions en lien avec l'entête
    """
import os
from datetime import datetime
from logger_setup import setup_logger
import logging
import yaml
import re
from pathlib import Path
import unicodedata
from handlers.process.ollama import get_summary_from_ollama, get_tags_from_ollama
from handlers.utils.files import count_words
from handlers.utils.extract_yaml_header import extract_yaml_header, extract_metadata

setup_logger("obsidian_headers", logging.DEBUG)
logger = logging.getLogger("obsidian_headers")

# Fonction pour ajouter ou mettre à jour les tags, résumés et commandes dans le front matter YAML
def add_metadata_to_yaml(filepath, tags, summary, category, subcategory, status):
    """
    Ajoute ou met à jour l'entête YAML d'un fichier Markdown.
    """

    try:
        logger.debug("[DEBUG] add_yaml : démarrage pour %s", filepath)

        # 🔥 Extraction rapide des métadonnées existantes
        metadata = extract_metadata(filepath)

        # 🔥 Définition des valeurs par défaut
        title = metadata.get("title", Path(filepath).stem)
        source_yaml = metadata.get("source", "")
        author = metadata.get("author", "ChatGPT" if "ChatGPT" in title else "")
        project = metadata.get("project", "")
        date_creation = metadata.get("created", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        note_id = metadata.get("note_id", None)
        nombre_mots = count_words(open(filepath, "r", encoding="utf-8").read())

        # 🔥 Suppression de l'ancienne entête YAML
        with open(filepath, "r", encoding="utf-8") as file:
            lines = file.readlines()
        
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
            f"created: {date_creation}\n",
            f"last_modified: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"source: {source_yaml}\n",
            f"author: {author}\n",
            f"status: {status}\n",
            f"note_id: {note_id}\n",
            f"project: {project}\n",
            "---\n\n"
        ]

        # 🔥 Sauvegarde sécurisée dans un fichier temporaire
        with open(filepath, "w", encoding="utf-8") as file:
            file.writelines(yaml_block + lines)

       
        logger.info("[INFO] Génération de l'entête terminée avec succès pour %s", filepath)

    except FileNotFoundError as e:
        logger.error("Erreur : fichier non trouvé %s", filepath)
    except Exception as e:
        logger.error("[ERREUR] Problème lors de l'ajout du YAML : %s", e, exc_info=True)

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

def sanitize_yaml_title(title: str) -> str:
    """ Nettoie le titre pour éviter les erreurs YAML """
    if not title:
        return "Untitled"

    logger.debug("[DEBUG] avant sanitize title %s", title)
    
    # 🔥 Normalise les caractères Unicode
    title = unicodedata.normalize("NFC", title)

    # 🔥 Supprime les caractères non imprimables et spéciaux
    title = re.sub(r'[^\w\s\-\']', '', title)  # Garde lettres, chiffres, espace, tiret, apostrophe
    
    # 🔥 Remplace les " par ' et les : par un espace
    title = title.replace('"', "'").replace(':', ' ')

    logger.debug("[DEBUG] après sanitize title %s", title)
    # 🔥 Vérifie si le titre est encore valide après nettoyage
    if not title.strip():
        return "Untitled"

    return title