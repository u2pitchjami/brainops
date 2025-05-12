import os
import time
import requests
import json
import logging

logger = logging.getLogger("obsidian_notes." + __name__)

TIMEOUT = 10

class OllamaError(Exception):
    """Exception spécifique pour les erreurs Ollama"""
    pass


    
def call_ollama_with_retry(prompt, model_ollama, retries=5, delay=10):
    """Appelle Ollama avec 3 essais avant d'abandonner."""
    logger.debug(f"[DEBUG] entrée call_ollama_with_retry model : {model_ollama}")
    for i in range(retries):
        try:
            if model_ollama != "nomic-embed-text:latest":
                return ollama_generate(prompt, model_ollama)
            else:
                return get_embedding(prompt, model_ollama)

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
  
        
        
    #logger.debug(f"[DEBUG] ollama_generate, prompt : {prompt}")
    logger.debug(f"[DEBUG] ollama_generate, model_ollama : {model_ollama}")
    logger.debug(f"[DEBUG] ollama_generate, ollama_url_generate : {ollama_url_generate}")
        
    try:
    
        payload = {
            "model": model_ollama,
            "prompt": prompt,
            "options": {
                "num_predict": -1,
                "num_ctx": 4096
            }
        }
        
        response = requests.post(ollama_url_generate, json=payload, stream=True)
        #logger.debug(f"[DEBUG] ollama_generate, response : {response}")
        
        if response.status_code == 200:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        json_line = json.loads(line)
                        full_response += json_line.get("response", "")
                        
                    except json.JSONDecodeError as e:
                        print(f"Erreur de décodage JSON : {e}")
            
            #logger.debug(f"[DEBUG] ollama_generate, full_response : {full_response}")
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

def get_embedding(prompt, model_ollama):
    logger.debug(f"[DEBUG] get_embedding : {model_ollama}")
    ollama_url_embeddings = os.getenv('OLLAMA_URL_EMBEDDINGS')
    logger.debug(f"[DEBUG] get_embedding : {ollama_url_embeddings}")
    payload = {
            "model": model_ollama,
            "prompt": prompt,
            "options": {
                "num_predict": -1,
                "num_ctx": 4096
            }
        }

    try:
        res = requests.post(ollama_url_embeddings, json=payload)
        #logger.debug(f"[DEBUG] get_embedding res: {res}")
        res.raise_for_status()
        data = res.json()
        embedding = data.get("embedding", [])
        #logger.debug(f"[DEBUG] get_embedding embedding: {embedding}")
        if not embedding:
            logger.debug("❌ Embedding vide !")
        return embedding

    except Exception as e:
        logger.debug(f"Erreur lors de l'appel Ollama : {e}")
        return None