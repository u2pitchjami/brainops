import logging
import os
import re

import yaml

from brainops.obsidian_scripts.handlers.header.extract_yaml_header import (
    extract_yaml_header,
)

logger = logging.getLogger("obsidian_notes." + __name__)

# Variables globales pour les mots-clés et leur dernier horodatage
keywords_file = os.getenv("KEYWORDS_FILE")
TAG_KEYWORDS = {}

if os.path.exists(keywords_file):
    logger.debug("Fichier trouvé : %s", keywords_file)
else:
    logger.warning("Fichier introuvable : %s", keywords_file)

# Initialisation sécurisée
try:
    LAST_MODIFIED_TIME = os.path.getmtime(keywords_file)
except FileNotFoundError:
    LAST_MODIFIED_TIME = 0  # Valeur par défaut si le fichier n'existe pas encore


def load_keywords(file_path):
    try:
        with open(file_path, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)

        # Transformer les mots-clés en listes
        keywords = {
            tag: [word.strip() for word in words.split(",")]
            for tag, words in raw_data.items()
        }
        return keywords
    except Exception as e:
        logger.warning(f"Erreur lors du chargement des mots-clés : {e}")
        raise


def process_and_update_file(filepath):
    global LAST_MODIFIED_TIME, TAG_KEYWORDS
    # Vérifier si le fichier de mots-clés a changé
    logger.debug(
        "[DEBUG] process_and_update_file : vérif du fichier de mots clés is_file_update "
    )
    file_updated, new_modified_time = is_file_updated(keywords_file, LAST_MODIFIED_TIME)
    if file_updated:
        print("[INFO] Rechargement des mots-clés...")
        logger.debug(
            "[DEBUG] process_and_update_file : fichier modifié : rechargement des  mots clés"
        )
        TAG_KEYWORDS = load_keywords(keywords_file)
        LAST_MODIFIED_TIME = new_modified_time

    # Charger le contenu du fichier

    header_lines, content_lines = extract_yaml_header(filepath)
    {repr(header_lines)}
    logger.debug(f"[DEBUG] Contenu brut après extract_yaml_header : {header_lines[:5]}")
    logger.debug(
        f"[DEBUG] Contenu brut après extract_yaml_header : {repr(header_lines[:5])}"
    )
    logger.debug(
        f"[DEBUG] Contenu brut après extract_yaml_header CONTENT : {content_lines[:5]}"
    )

    # Charger les mots-clés depuis le fichier
    TAG_KEYWORDS = load_keywords(keywords_file)
    # data = yaml.safe_load(f)
    logger.debug(
        f"[DEBUG] process_and_update_file : Contenu du fichier YAML chargé : {TAG_KEYWORDS}"
    )
    # Analyser les sections et générer des tags
    logger.debug("[DEBUG] process_and_update_file : envoie vers tag_sections")
    tagged_sections = tag_sections(content_lines)

    # Réécrire le contenu dans le fichier
    logger.debug("[DEBUG] process_and_update_file : envoie vers integrate_tags_in_file")
    integrate_tags_in_file(filepath, tagged_sections, header_lines)


# Surveillance des modifications du fichier
def is_file_updated(file_path, last_modified_time):
    logger.debug("[DEBUG] entrée dans is_file_updated")
    try:
        current_modified_time = os.path.getmtime(file_path)
        logger.debug(
            f"[DEBUG] is_file_updated : nouvelle date : {current_modified_time}"
        )
        return current_modified_time != last_modified_time, current_modified_time
    except FileNotFoundError:
        logger.error(f"[ERREUR] Fichier introuvable : {file_path}")
        return False, last_modified_time


def extract_sections(content_lines):
    """
    Divise le texte en sections basées sur les titres Markdown.
    """
    logger.debug("[DEBUG] entrée fonction : extract_sections")
    sections = re.split(r"(?=^#{1,3}\s)", content_lines, flags=re.MULTILINE)
    logger.debug(f"[DEBUG] extract_sections : {sections[:5]}")
    return [section.strip() for section in sections if section.strip()]


def detect_tags_in_text(content_lines, TAG_KEYWORDS):
    logger.debug("[DEBUG] entrée fonction : detect_tags_in_text")
    """
    Détecte les tags dans un texte.
    """
    tags = set()  # Initialisation de la variable 'tags' comme un ensemble vide
    for tag, keywords in TAG_KEYWORDS.items():  # Parcourt chaque catégorie
        for keyword in keywords:  # Parcourt chaque mot-clé dans la catégorie
            if (
                keyword.lower() in content_lines.lower()
            ):  # Recherche insensible à la casse
                tags.add(f"#{tag}")  # Ajoute un # devant chaque tag
    return tags


def tag_sections(content_lines):
    logger.debug("[DEBUG] entrée fonction : tag_sections")
    """
    Analyse chaque section et génère des tags basés sur le titre et le contenu.
    """
    logger.debug("[DEBUG] tag_sections : envoie vers extract_sections")
    sections = extract_sections(content_lines)
    tagged_sections = []

    for section in sections:
        # Séparer le titre de la section du contenu
        logger.debug("[DEBUG] tag_sections : Séparer le titre de la section du contenu")
        title_match = re.match(r"^#{1,3}\s(.+)", section)
        title = title_match.group(1) if title_match else "Untitled Section"
        logger.debug(f"[DEBUG] tag_sections : title : {title}")
        content = section[len(title_match.group(0)) :] if title_match else section

        # Chercher des tags dans le titre et le contenu
        logger.debug(
            "[DEBUG] tag_sections : envoie vers detect_tags_in_text pour title_tags"
        )
        title_tags = detect_tags_in_text(title, TAG_KEYWORDS)
        # logger.debug(f"[DEBUG] tag_sections : title_tags : {title_tags}")
        logger.debug(
            "[DEBUG] tag_sections : envoie vers detect_tags_in_text pour content"
        )
        content_tags = detect_tags_in_text(content, TAG_KEYWORDS)
        logger.debug(f"[DEBUG] tag_sections : content_tags : {content_tags}")
        all_tags = title_tags.union(content_tags)
        logger.debug(f"[DEBUG] tag_sections : all_tags : {all_tags}")

        # Stocker le résultat
        tagged_sections.append(
            {
                "title": title,
                "tags": sorted(all_tags),  # Tags triés pour la lisibilité
                "content": content.strip(),
            }
        )

    return tagged_sections


def integrate_tags_in_file(filepath, tagged_sections, header_lines):
    logger.debug(f"[DEBUG] entrée fonction : integrate_tags_in_file : {filepath}")
    """
    Réécrit le fichier en ajoutant les tags au début de chaque section.
    """
    logger.debug(f"[DEBUG] entrée fonction : integrate_tags_in_file : {filepath}")

    # Ouvre le fichier en écriture
    with open(filepath, "w", encoding="utf-8") as file:
        # Écrire l'entête YAML si elle existe
        if header_lines:  # Vérifie que l'entête n'est pas vide
            for line in header_lines:
                file.write(line if line.endswith("\n") else line + "\n")
            logger.debug(
                f"[DEBUG] integrate_tags_in_file : Entête YAML correctement écrite : {''.join(header_lines)}"
            )

        # Écrire les sections avec leurs titres, tags et contenu
        for section in tagged_sections:
            # Ajoute le titre de la section
            file.write(f"## {section['title']}\n")
            logger.debug(
                f"[DEBUG] integrate_tags_in_file : title : {section['title']} : {filepath}"
            )
            # Ajoute les tags associés
            tags_line = " ".join(section["tags"])
            file.write(f"{tags_line}\n\n")
            logger.debug(f"[DEBUG] integrate_tags_in_file : tags : {tags_line}")
            # Ajoute le contenu de la section
            file.write(f"{section['content']}\n\n")
            logger.debug(
                f"[DEBUG] integrate_tags_in_file : section content : {section['content']}"
            )

    logger.info(f"[INFO] Génération des mots clés terminée pour {filepath}")
