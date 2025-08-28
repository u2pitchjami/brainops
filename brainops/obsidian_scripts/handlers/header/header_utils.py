import logging
import re
import yaml
import hashlib
from typing import Callable
from handlers.utils.files import read_note_content, safe_write

logger = logging.getLogger("obsidian_notes." + __name__)

def get_yaml(content: str) -> dict:
    """
    Extrait et parse l'en-tête YAML d'un fichier Markdown Obsidian.
    Retourne un dictionnaire, ou {} si rien trouvé.
    """
    try:
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if match:
            return yaml.safe_load(match.group(1)) or {}
    except Exception as e:
        print(f"[extract_yaml_header] Erreur parsing YAML : {e}")
    return {}

def get_yaml_value(content: str, key: str, default=None):
    yaml_data = get_yaml(content)
    return yaml_data.get(key, default)

def update_yaml_header(content: str, new_metadata: dict) -> str:
    """
    Remplace l'en-tête YAML d'un fichier Obsidian par un nouveau dictionnaire.

    Args:
        content (str): Le contenu brut du fichier (Markdown complet).
        new_metadata (dict): Le nouveau dictionnaire à écrire dans l'en-tête YAML.

    Returns:
        str: Le contenu du fichier avec l'en-tête YAML mis à jour.
    """
    new_yaml = f"---\n{yaml.dump(new_metadata, default_flow_style=False)}---\n"

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if match:
        # Remplace l'en-tête existante
        content_wo_yaml = content[len(match.group(0)):]
    else:
        # Pas d'en-tête détectée → tout le contenu est conservé
        content_wo_yaml = content

    return new_yaml + content_wo_yaml

def merge_yaml_header(content: str, new_metadata: dict) -> str:
    """
    Fusionne de nouvelles métadonnées dans l'en-tête YAML du fichier.
    Conserve les champs existants non concernés.
    """
    try:
        match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
        if match:
            existing_yaml_str = match.group(1)
            existing_metadata = yaml.safe_load(existing_yaml_str) or {}
            content_wo_yaml = content[len(match.group(0)):]
        else:
            existing_metadata = {}
            content_wo_yaml = content

        merged_metadata = {**existing_metadata, **new_metadata}
        new_yaml = f"---\n{yaml.dump(merged_metadata, default_flow_style=False)}---\n"

        return new_yaml + content_wo_yaml

    except Exception as e:
        logger.exception(f"[ERROR] merge_yaml_header: problème lors de la mise à jour du YAML : {e}")
        return content


def patch_yaml_line(yaml_text: str, key: str, patch_func: Callable[[str], str]) -> str:
    """
    Applique une fonction de transformation sur une ligne 'key: value' du texte YAML brut.

    Args:
        yaml_text (str): Le bloc YAML complet (texte brut).
        key (str): La clé ciblée à modifier.
        patch_func (Callable[[str], str]): La fonction à appliquer sur la valeur.

    Returns:
        str: Le YAML modifié avec la ligne patchée, ou inchangé si clé non trouvée.
    """
    pattern = rf'^({re.escape(key)}\s*:\s*)(.+)$'
    logger.debug(f"[DEBUG] patch_yaml_line pattern : {pattern}")
    return re.sub(
        pattern,
        lambda m: f"{m.group(1)}{patch_func(m.group(2))}",
        yaml_text,
        flags=re.MULTILINE
    )

def clean_yaml_spacing_in_file(file_path: str) -> bool:
    """
    Nettoie un fichier Markdown : supprime les lignes vides en trop après le YAML.
    Écrit directement le fichier nettoyé.
    """
    try:
        logger.debug(f"[DEBUG] clean_yaml_spacing_in_file")
        content = read_note_content(file_path)
        lines = content.splitlines()
        inside_yaml = False
        yaml_end_index = None

        for i, line in enumerate(lines):
            if line.strip() == "---":
                if not inside_yaml:
                    inside_yaml = True
                else:
                    yaml_end_index = i
                    break

        if yaml_end_index is None:
            return False  # Pas de YAML détecté

        # Trouver première ligne non vide après le YAML
        body_start = yaml_end_index + 1
        while body_start < len(lines) and lines[body_start].strip() == "":
            body_start += 1

        new_lines = (
            lines[:yaml_end_index + 1] +
            [""] +
            lines[body_start:]
        )
        logger.debug(f"[DEBUG] new_lines : {new_lines}")
        new_content = "\n".join(new_lines).strip() + "\n"
        logger.debug(f"[DEBUG] new_content : {new_content}")
        return safe_write(file_path, new_content)

    except Exception as e:
        print(f"[ERREUR] clean_yaml_spacing_in_file: {e}")
        return False

def hash_source(source: str) -> str:
    return hashlib.sha256(source.strip().lower().encode("utf-8")).hexdigest()
