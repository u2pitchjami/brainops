import unicodedata
import os
import re
from datetime import datetime, date
import logging
logger = logging.getLogger("obsidian_notes." + __name__)

def normalize_full_path(path):
    """ Nettoie un chemin de fichier (slashs, accents, espaces, etc.) """
    path = unicodedata.normalize("NFC", path)
    path = path.strip()
    return os.path.normpath(path)

def sanitize_created(created):
    try:
        if isinstance(created, (datetime, date)):
            return created.strftime('%Y-%m-%d')
        elif isinstance(created, str) and created.strip():
            try:
                parsed_date = datetime.fromisoformat(created.strip())
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                logging.warning(f"Format de date invalide : {created}")
                return datetime.now().strftime('%Y-%m-%d')
        else:
            return datetime.now().strftime('%Y-%m-%d')
    except Exception as e:
        logging.error(f"Erreur dans sanitize_created : {e}")
        return datetime.now().strftime('%Y-%m-%d')
    
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

def sanitize_filename(filename):
    # Remplace les caractères interdits par des underscores
    try:
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)  # Pour Windows
        sanitized = sanitized.replace(' ', '_')  # Remplace les espaces par des underscores
        return sanitized
    except Exception as e:
            logger.error(f"[ERREUR] Anomalie lors du sanitized : {e}")
            return

def is_probably_code(block: str) -> bool:
    """Heuristique simple pour détecter un vrai bloc de code (multiligne)."""
    code_chars = r'[=;{}()<>]|(def |class |import |from )|#!/bin/'
    if re.search(code_chars, block):
        return True
    if len(block.splitlines()) >= 3 and all(len(line) > 20 for line in block.splitlines()):
        return True
    return False

def is_probably_inline_code(text: str) -> bool:
    """Heuristique pour détecter si un bloc `inline` est du vrai code."""
    code_keywords = ['=', ';', '{', '}', '(', ')', '<', '>', 'def', 'class', 'import', 'from', 'lambda']
    return any(kw in text for kw in code_keywords)

def clean_inline_code(text: str) -> str:
    """Supprime les backticks `...` si ce n'est pas du code probable."""
    return re.sub(
        r'`([^`\n]+?)`',
        lambda m: m.group(1) if not is_probably_inline_code(m.group(1)) else m.group(0),
        text
    )
def clean_indented_code_lines(text: str) -> str:
    """
    Corrige les lignes indentées (4 espaces ou tab) qui ne devraient pas être du code.
    - Si une ligne est indentée mais n'est pas précédée d'une ligne vide ni dans un bloc ```
    - Et que son contenu ne ressemble pas à du vrai code, on la désindente
    """
    lines = text.splitlines()
    cleaned_lines = []
    in_code_block = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            cleaned_lines.append(line)
            continue

        if not in_code_block:
            prev_line = lines[i - 1] if i > 0 else ""
            is_indented = line.startswith("    ") or line.startswith("\t")

            if is_indented and not prev_line.strip():  # faux bloc ?
                if not is_probably_code(line):  # heuristique
                    cleaned_lines.append(line.lstrip())  # on nettoie
                    continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)

def clean_fake_code_blocks(text: str) -> str:
    """
    Nettoie les blocs ```...``` non-code + les `inline` non-code.
    """
    parts = re.split(r'(```(?:\w+)?\n.*?\n```)', text, flags=re.DOTALL)
    result = []

    for part in parts:
        if part.startswith("```"):
            lines = part.splitlines()
            lang_line = lines[0]
            code_block = "\n".join(lines[1:-1])  # sans les ```
            if is_probably_code(code_block):
                result.append(part)
            else:
                cleaned = "\n".join(line.lstrip() for line in code_block.splitlines())
                result.append(cleaned)
        else:
            result.append(part)

    clean_text = "\n".join(result)
    clean_text = clean_inline_code(clean_text)
    clean_text = clean_indented_code_lines(clean_text)
    return clean_text
