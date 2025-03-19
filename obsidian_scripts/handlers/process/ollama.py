import re
import os
import time
import requests
from handlers.process.prompts import PROMPTS
import json
from logger_setup import setup_logger
import logging

setup_logger("ollama", logging.DEBUG)
logger = logging.getLogger("ollama")

TIMEOUT = 10

class OllamaError(Exception):
    """Exception spécifique pour les erreurs Ollama"""
    pass

# Fonction pour interroger Ollama et générer des tags à partir du contenu d'une note
def get_tags_from_ollama(content):
    logger.debug(f"[DEBUG] tags ollama : lancement fonction")
    model_ollama = os.getenv('MODEL_TAGS')
    
    try:
        prompt = PROMPTS["tags"].format(content=content)
    except Exception as e:
            logger.error(f"[ERREUR] prompt : {e}")
            prompt = None
    if prompt:
        try:
            logger.debug(f"[DEBUG] tags ollama : recherche et lancement du prompt")
            response = call_ollama_with_retry(prompt, model_ollama)
            logger.debug(f"[DEBUG] tags ollama : réponse récupérée : {response}")

            # EXTRACTION DES TAGS VIA REGEX
            match = re.search(r'\{.*?\}', response, re.DOTALL)  # Tente de capturer un objet JSON complet

            if match:
                try:
                    tags_data = json.loads(match.group(0))
                    tags = tags_data.get("tags", [])
                except json.JSONDecodeError as e:
                    logger.error(f"[ERREUR] Impossible de décoder le JSON complet : {e}")
                    tags = ["Error parsing JSON"]
            else:
                # Capture uniquement le tableau
                match = re.search(r'\[.*?\]', response, re.DOTALL)
                if match:
                    try:
                        tags = json.loads(match.group(0))
                    except json.JSONDecodeError as e:
                        logger.error(f"[ERREUR] Impossible de décoder le tableau : {e}")
                        tags = ["Error parsing JSON"]
                else:
                    logger.warning("[WARN] Aucun JSON ou tableau trouvé dans la réponse.")
                    tags = ["No tags found"]

            logger.debug(f"[DEBUG] tags ollama : tags extraits : {tags}")
            return tags
        except OllamaError:
            logger.error("[ERROR] Import annulé.")
            
    else:
        logger.error("[ERREUR] prompt est invalide, impossible d'appeler Ollama")
            
# Fonction pour générer un résumé automatique avec Ollama
def get_summary_from_ollama(content):
    logger.debug(f"[DEBUG] résumé ollama : lancement fonction")
    model_ollama = os.getenv('MODEL_SUMMARY')
    prompt = PROMPTS["summary"].format(content=content)
    logger.debug(f"[DEBUG] résumé ollama : recherche et lancement du prompt")
    
    try:
        response = call_ollama_with_retry(prompt, model_ollama)
        
        
        logger.debug(f"[DEBUG] summary ollama : reponse récupéré")
    # Nettoyage au cas où Ollama ajoute du texte autour
        match = re.search(r'TEXT START(.*?)TEXT END', response, re.DOTALL)
        logger.debug(f"[DEBUG] summary ollama : Nettoyage au cas où Ollama ajoute du texte autour : {match}")
        if match:
            summary = match.group(1).strip()
            logger.debug(f"[DEBUG] summary ollama : Nettoyage : {summary}")
        else:
            summary = response  # Si pas de balise trouvée, retourne la réponse complète
            logger.debug(f"[DEBUG] summary ollama : Nettoyage : pas de balise trouvée")
        
        # Nettoyage des artefacts
        #summary = clean_summary(summary)
        
        return summary
    except OllamaError:
        logger.error("[ERROR] Import annulé.")
    

def simplify_note_with_ai(content):
    logger.debug(f"[DEBUG] démarrage du simplify_note_with_ai")
    """
    Reformule et simplifie une note en utilisant Ollama.
    """
        
    prompt = PROMPTS["reformulation"].format(content=content)
    # Appel à Ollama pour simplifier la note
    logger.debug(f"[DEBUG] simplify_note_with_ai : recherche et lancement du prompt")
    response = ollama_generate(prompt)
    
    return response.strip()

def enforce_titles(response):
    sections = re.split(r'\n(?=##|\n\n)', response)  # Split par titre Markdown ou paragraphes
    processed_sections = []
    for idx, section in enumerate(sections):
        if not section.startswith("TITLE:"):
            title = f"TITLE: Section {idx + 1}"  # Titre par défaut
            section = f"{title}\n{section.strip()}"
        processed_sections.append(section)
    return "\n\n".join(processed_sections)

def call_ollama_with_retry(prompt, model_ollama, retries=5, delay=100):
    """Appelle Ollama avec 3 essais avant d'abandonner."""
    logger.debug(f"[DEBUG] entrée call_ollama_with_retry model : {model_ollama}")
    for i in range(retries):
        try:
            return ollama_generate(prompt, model_ollama)  # 🔥 On essaie de contacter Ollama

        except OllamaError as e:
            logger.debug(f"[WARNING] Tentative {i+1}/{retries} échouée : {e}")
            if i < retries - 1:
                logger.info(f"[INFO] Nouvelle tentative dans {delay} secondes...")
                time.sleep(delay)
            else:
                logger.error("[ERREUR] Ollama ne répond pas après plusieurs tentatives.")
                raise

# Traitement pour réponse d'ollama
def ollama_generate(prompt, model_ollama):
    logger.debug(f"[DEBUG] entrée fonction : ollama_generate")
    ollama_url_generate = os.getenv('OLLAMA_URL_GENERATE')
    logger.debug(f"[DEBUG] ollama_generate, prompt : {prompt}")
    logger.debug(f"[DEBUG] ollama_generate, model_ollama : {model_ollama}")
    logger.debug(f"[DEBUG] ollama_generate, ollama_url_generate : {ollama_url_generate}")
        
    try:
    
        payload = {
            "model": model_ollama,
            "prompt": prompt,
            "options": {
                "num_predict": -1,
                "num_ctx": 8192
            }
        }
        
        response = requests.post(ollama_url_generate, json=payload, stream=True)
        logger.debug(f"[DEBUG] ollama_generate, response : {response}")
        
        if response.status_code == 200:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        json_line = json.loads(line)
                        full_response += json_line.get("response", "")
                        
                    except json.JSONDecodeError as e:
                        print(f"Erreur de décodage JSON : {e}")
            
            logger.debug(f"[DEBUG] ollama_generate, full_response : {full_response}")
            return full_response.strip()
        
        elif response.status_code in (500, 503):
                raise OllamaError("[ERREUR] Ollama semble planté ou indisponible.")

        elif response.status_code == 404:
            raise OllamaError("[ERREUR] Modèle introuvable sur Ollama.")

        else:
            raise OllamaError(f"[ERREUR] Réponse inattendue d'Ollama : {response.status_code}")

    except requests.exceptions.Timeout:
        raise OllamaError("[ERREUR] Ollama ne répond pas (timeout).")

    except requests.exceptions.ConnectionError:
        raise OllamaError("[ERREUR] Impossible de se connecter à Ollama (Docker HS ?).")