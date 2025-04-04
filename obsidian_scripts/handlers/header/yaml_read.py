from logger_setup import setup_logger
import logging
import time
from handlers.utils.normalization import sanitize_yaml_title
from handlers.utils.files import safe_write, hash_file_content, read_note_content
from handlers.header.extract_yaml_header import extract_yaml_header
from handlers.header.header_utils import patch_yaml_line, merge_yaml_header

setup_logger("yaml_read", logging.DEBUG)
logger = logging.getLogger("yaml_read")


def test_title(file_path):
    try:
        # 1. Séparation header + body
        header_lines, body = extract_yaml_header(file_path)
        yaml_text = "\n".join(header_lines)
        logger.debug(f"[DEBUG] test_title yaml_text : {yaml_text}")
        # 2. Patch ciblé du champ "title"
        corrected_yaml_text = patch_yaml_line(yaml_text, "title", sanitize_yaml_title)
        logger.debug(f"[DEBUG] test_title corrected_yaml_text : {corrected_yaml_text}")
        # 3. Si modifié → on remplace
        if corrected_yaml_text != yaml_text:
            new_content = f"{corrected_yaml_text}\n{body}"
            success = safe_write(file_path, new_content)
            if not success:
                logger.error(f"[main] Problème lors de l’écriture sécurisée de {file_path}")
            logger.info(f"[INFO] Titre corrigé dans : {file_path}")

    except Exception as e:
        logger.error(f"❌ [ERREUR] Erreur dans test_title : {e}")

     
def ensure_status_in_yaml(file_path: str, status: str = "draft") -> None:
    """
    Vérifie et insère ou met à jour le champ 'note_id' dans le YAML d'un fichier Markdown.
    - Ne modifie rien si le note_id est déjà correct.
    - Gère proprement l'ajout et la mise à jour du frontmatter.
    """
    
    content = read_note_content(file_path)
    
    
    new_content = merge_yaml_header(content, {"status": status})

        
    if content == new_content:
        logger.debug("🔄 [DEBUG] Le fichier %s est déjà à jour, pas d'écriture", file_path)
        return

    logger.debug("💾 [DEBUG] Écriture du fichier %s (status mis à jour)", file_path)
    success = safe_write(file_path, content=new_content, verify_contains="note_id:")

    if not success:
        logger.error("[main] Problème lors de l’écriture sécurisée de %s", file_path)
        return

    logger.info("[INFO] Lien mis à jour pour : %s", file_path)

    post_write_hash = hash_file_content(file_path)
    time.sleep(1)
    post_sleep_hash = hash_file_content(file_path)

    if post_write_hash != post_sleep_hash:
        logger.critical("⚠️ Contenu du fichier modifié entre écriture et vérification : %s", file_path)
        logger.debug("Hash écrit : %s", post_write_hash)
        logger.debug("Hash 1s après : %s", post_sleep_hash)
    else:
        logger.debug("✅ Intégrité du fichier confirmée post-écriture")
