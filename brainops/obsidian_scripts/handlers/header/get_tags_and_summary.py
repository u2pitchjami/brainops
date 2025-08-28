import json
import logging
import re

from brainops.obsidian_scripts.handlers.ollama.ollama_call import call_ollama_with_retry
from brainops.obsidian_scripts.handlers.ollama.prompts import PROMPTS
from brainops.obsidian_scripts.handlers.utils.divers import (
    prompt_name_and_model_selection,
)

logger = logging.getLogger("obsidian_notes." + __name__)


# Define OllamaError if not already imported
class OllamaError(Exception):
    pass


# Fonction pour interroger Ollama et générer des tags à partir du contenu d'une note
def get_tags_from_ollama(content: str, note_id: int) -> None:
    logger.debug("[DEBUG] tags ollama : lancement fonction")

    try:
        prompt_name, model_ollama = prompt_name_and_model_selection(
            note_id, key="add_tags"
        )
        logger.debug(f"[DEBUG] prompt_name : {prompt_name}")
        logger.debug(f"[DEBUG] PROMPTS[prompt_name] : {PROMPTS[prompt_name]}")
        prompt = PROMPTS[prompt_name].format(content=content)

    except Exception as e:
        logger.error(f"[ERREUR] prompt : {e}")
        prompt = None
    if prompt:
        try:
            logger.debug("[DEBUG] tags ollama : recherche et lancement du prompt")
            response = call_ollama_with_retry(prompt, model_ollama)
            logger.debug(f"[DEBUG] tags ollama : réponse récupérée : {response}")

            # EXTRACTION DES TAGS VIA REGEX
            match = re.search(
                r"\{.*?\}", response, re.DOTALL
            )  # Tente de capturer un objet JSON complet

            if match:
                try:
                    tags_data = json.loads(match.group(0))
                    tags = tags_data.get("tags", [])
                except json.JSONDecodeError as e:
                    logger.error(
                        f"[ERREUR] Impossible de décoder le JSON complet : {e}"
                    )
                    tags = ["Error parsing JSON"]
            else:
                # Capture uniquement le tableau
                match = re.search(r"\[.*?\]", response, re.DOTALL)

                if match:
                    try:
                        tags = json.loads(match.group(0))
                        # tags = re.sub(r'[:*?"<>#|\'\\]', '', tags)
                        logger.debug(f"Match après nettoyage : {tags}")
                    except json.JSONDecodeError as e:
                        logger.error(f"[ERREUR] Impossible de décoder le tableau : {e}")
                        tags = ["Error parsing JSON"]
                else:
                    logger.warning(
                        "[WARN] Aucun JSON ou tableau trouvé dans la réponse."
                    )
        except OllamaError:
            logger.error("[ERROR] Import annulé.")
            return None
            logger.debug(f"[DEBUG] tags ollama : tags extraits : {tags}")
            return tags
        except OllamaError:
            logger.error("[ERROR] Import annulé.")

    else:
        logger.error("[ERREUR] prompt est invalide, impossible d'appeler Ollama")


# Fonction pour générer un résumé automatique avec Ollama
def get_summary_from_ollama(content: str, note_id: int) -> str | None:
    logger.debug("[DEBUG] résumé ollama : lancement fonction")
    prompt_name, _ = prompt_name_and_model_selection(note_id, key="summary")
    model_ollama = "cognitivetech/obook_summary:latest"
    prompt = PROMPTS[prompt_name].format(content=content)
    logger.debug("[DEBUG] résumé ollama : recherche et lancement du prompt")

    try:
        response = call_ollama_with_retry(prompt, model_ollama)

        logger.debug("[DEBUG] summary ollama : reponse récupéré")
        # Nettoyage au cas où Ollama ajoute du texte autour
        match = re.search(r"TEXT START(.*?)TEXT END", response, re.DOTALL)
        logger.debug(
            f"[DEBUG] summary ollama : Nettoyage au cas où Ollama ajoute du texte autour : {match}"
        )
        if match:
            summary = match.group(1).strip()
            logger.debug(f"[DEBUG] summary ollama : Nettoyage : {summary}")
        else:
            summary = response  # Si pas de balise trouvée, retourne la réponse complète
            logger.debug("[DEBUG] summary ollama : Nettoyage : pas de balise trouvée")

        # Nettoyage des artefacts
        # summary = clean_summary(summary)

        return summary
    except OllamaError:
        logger.error("[ERROR] Import annulé.")
