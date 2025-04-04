import os
import re
import shutil
from datetime import datetime
from logger_setup import setup_logger
import logging
import hashlib
import time


setup_logger("files", logging.DEBUG)
logger = logging.getLogger("files")

def wait_for_file(file_path, timeout=3):
    """Attend que le fichier existe avant de le traiter"""
    start_time = time.time()
    while not os.path.exists(file_path):
        if time.time() - start_time > timeout:
            return False  # Fichier toujours absent après le timeout
        time.sleep(0.5)  # Vérifie toutes les 0.5 sec

    return True

def hash_file_content(filepath):
    try:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        logger.error(f"Erreur hashing fichier : {e}")
        return None

def safe_write(file_path: str, content, verify_contains: list[str] = None) -> bool:
    """
    Écrit du contenu dans un fichier de manière sécurisée.
    Gère les strings et les listes de chaînes, avec logs et vérification facultative.

    Args:
        file_path (str): Chemin du fichier à écrire.
        content (str or list[str]): Contenu à écrire.
        verify_contains (list[str], optional): Champs à vérifier après écriture.

    Returns:
        bool: True si tout est ok, False sinon.
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            if isinstance(content, list):
                f.writelines(content)
                logger.debug(f"[safe_write] Écriture par writelines() - {len(content)} lignes dans {file_path}")
            else:
                f.write(content)
                logger.debug(f"[safe_write] Écriture par write() - {len(content)} caractères dans {file_path}")

            f.flush()
            os.fsync(f.fileno())
            logger.debug(f"[safe_write] flush + fsync effectués pour {file_path}")

        # Vérification post-écriture
        if verify_contains:
            with open(file_path, "r", encoding="utf-8") as f:
                written = f.read()

            for entry in verify_contains:
                if entry not in written:
                    logger.warning(f"[safe_write] Champ manquant : '{entry}' dans {file_path}")
                    return False

        return True

    except Exception as e:
        logger.error(f"[safe_write] Erreur d'écriture dans {file_path} : {e}")
        return False

def copy_file_with_date(filepath, destination_folder):
    """
    Copie un fichier en ajoutant la date au nom.
    """
    try:
        # Obtenir le nom de base du fichier
        filename = os.path.basename(filepath)
        
        # Extraire le nom et l'extension du fichier
        name, ext = os.path.splitext(filename)
        
        # Obtenir la date actuelle au format souhaité
        date_str = datetime.now().strftime("%y%m%d")  # Exemple : '250112'
        
        # Construire le nouveau nom avec la date
        new_filename = f"{date_str}_{name}{ext}"
        
        # Construire le chemin complet de destination
        destination_path = os.path.join(destination_folder, new_filename)
        
        # Déplacer le fichier
        shutil.copy(filepath, destination_path)
        
        print(f"Fichier copié avec succès : {destination_path}")
    except Exception as e:
        print(f"Erreur lors de la copie du fichier : {e}")
        
def move_file_with_date(filepath, destination_folder):
    """
    déplace un fichier en ajoutant la date au nom.
    """
    try:
        # Obtenir le nom de base du fichier
        filename = os.path.basename(filepath)
        
        # Extraire le nom et l'extension du fichier
        name, ext = os.path.splitext(filename)
        
        # Obtenir la date actuelle au format souhaité
        date_str = datetime.now().strftime("%y%m%d")  # Exemple : '250112'
        
        # Construire le nouveau nom avec la date
        new_filename = f"{date_str}_{name}{ext}"
        
        # Construire le chemin complet de destination
        destination_path = os.path.join(destination_folder, new_filename)
        
        # Déplacer le fichier
        shutil.move(filepath, destination_path)
        
        print(f"Fichier déplacé avec succès : {destination_path}")
    except Exception as e:
        print(f"Erreur lors du déplacement du fichier : {e}")

def count_words(content):
    logger.debug(f"[DEBUG] def count_word")
    return len(content.split())

def maybe_clean(content, force: bool = False) -> str:
    """
    Nettoie le contenu *si nécessaire*.
    - Si content est une liste → join + clean
    - Si content contient du HTML suspect (ex: <svg>) → clean
    - Sinon, retourne tel quel sauf si force=True

    :param content: texte ou liste de lignes
    :param force: si True, on passe toujours par clean_content()
    """
    if force:
        return clean_content(content)

    if isinstance(content, list):
        return clean_content(content)

    if isinstance(content, str):
        if "<svg" in content or "<iframe" in content:
            return clean_content(content)

    return content

def clean_content(content):
    logger.debug(f"[DEBUG] clean_content : {content[:500]}")
    """
    Nettoie le contenu avant de l'envoyer au modèle.
    - Conserve les blocs de code Markdown (``` ou ~~~).
    - Supprime les balises SVG ou autres éléments non pertinents.
    - Élimine les lignes vides ou répétitives inutiles.
    """
    # Sécurité : si content est une liste, on la join proprement
    if isinstance(content, list):
        content = "\n".join(str(line).strip() for line in content)

    # Nettoyage HTML / Markdown / Sauts
    content = re.sub(r'<svg[^>]*>.*?</svg>', '', content, flags=re.DOTALL)
    content = re.sub(r"^- .*\n?", "", content, flags=re.MULTILINE)
    content = re.sub(r'\n\s*\n+', '\n\n', content)

    logger.debug(f"[DEBUG] Après nettoyage : {type(content)}, longueur = {len(content)}")

    return content.strip()

def read_note_content(filepath):
    """Lit le contenu d'une note depuis le fichier."""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            logger.debug(f"[DEBUG] lecture du fichier {filepath}")
            
            return file.read()
    except Exception as e:
        logger.error(f"[ERREUR] Impossible de lire le fichier {filepath} : {e}")
        return None

def join_yaml_and_body(header_lines: list[str], body: str) -> str:
    """
    Reconstitue une note complète avec entête YAML et corps :
    - Encadre l'entête avec `---`
    - Garde une seule ligne vide entre YAML et corps
    - Assure un seul saut de ligne final
    """
    logger.debug(f"[DEBUG] entrée join_yaml_and_body")
    if not header_lines:
        return body.strip() + "\n"

    yaml_header = "\n".join(header_lines).strip()
    logger.debug(f"[DEBUG] yaml_header : {yaml_header}")
    body_clean = body.strip()
    logger.debug(f"[DEBUG] body_clean : {body_clean}")

    if yaml_header.count('---') < 2:
        # On entoure manuellement le YAML
        full_note = f"---\n{yaml_header}\n---\n\n{body_clean}\n"
    else:
        # YAML déjà complet avec ses ---
        full_note = f"{yaml_header}\n\n{body_clean}\n"
    logger.debug(f"[DEBUG] full_note : {full_note}")
    return full_note
