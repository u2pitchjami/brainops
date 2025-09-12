"""
# ollama/ollama_call.py
"""

from __future__ import annotations

import json
from typing import Any

import requests

from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.utils.config import (
    OLLAMA_TIMEOUT,
    OLLAMA_URL_EMBEDDINGS,
    OLLAMA_URL_GENERATE,
)
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


class OllamaError(Exception):
    """
    Exception spécifique pour les erreurs Ollama.
    """


@with_child_logger
def call_ollama_with_retry(
    prompt: str,
    model_ollama: str,
    retries: int = 5,
    delay: int = 10,
    *,
    logger: LoggerProtocol | None = None,
) -> str:
    """
    Appelle Ollama avec 'retries' essais.

    - Pour les modèles d'embedding ('nomic-embed-text:latest'), bascule sur get_embedding()
      mais retourne une string JSONifiée de l'embedding par compat, ou None si échec.
    """
    import time

    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] call_ollama_with_retry model=%s", model_ollama)

    for attempt in range(retries):
        try:
            if model_ollama == "nomic-embed-text:latest":
                emb = get_embedding(prompt, model_ollama, logger=logger)
                return json.dumps(emb)
            return ollama_generate(prompt, model_ollama, logger=logger)
        except OllamaError as exc:
            logger.warning("[WARNING] Tentative %d/%d échouée : %s", attempt + 1, retries, exc)
            if attempt < retries - 1:
                logger.info("[INFO] Nouvelle tentative dans %d secondes…", delay)
                time.sleep(delay)
            else:
                logger.error("[ERREUR] Ollama ne répond pas après %d tentatives.", retries)
                raise BrainOpsError(
                    "KO récup ou création subcatg", code=ErrCode.DB, ctx={"name": "call_ollama_with_retry"}
                ) from exc
    raise BrainOpsError("KO récup ou création subcatg", code=ErrCode.DB, ctx={"name": "call_ollama_with_retry"})


@with_child_logger
def ollama_generate(prompt: str, model_ollama: str, *, logger: LoggerProtocol | None = None) -> str:
    """
    Appel texte → texte sur le endpoint GENERATE (stream).

    Concatène les fragments 'response' du flux JSONL.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] ollama_generate model=%s url=%s", model_ollama, OLLAMA_URL_GENERATE)

    payload: dict[str, Any] = {
        "model": model_ollama,
        "prompt": prompt,
        "options": {"num_predict": -1, "num_ctx": 4096},
    }

    try:
        with requests.post(
            OLLAMA_URL_GENERATE,
            json=payload,
            stream=True,
            timeout=OLLAMA_TIMEOUT,
        ) as resp:
            if resp.status_code == 404:
                raise BrainOpsError(
                    "Modèle introuvable sur Ollama (404)", code=ErrCode.OLLAMA, ctx={"status": resp.status_code}
                )
            if resp.status_code in (500, 503):
                raise BrainOpsError("Ollama indisponible)", code=ErrCode.OLLAMA, ctx={"status": resp.status_code})
            resp.raise_for_status()

            full: list[str] = []
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                    piece = obj.get("response", "")
                    if piece:
                        full.append(piece)
                except json.JSONDecodeError:
                    # tolérant : parfois la ligne n'est pas JSON, on concatène brut
                    full.append(str(raw))

            text = "".join(full).strip()
            if not text:
                logger.warning("[WARNING] 🚨 Réponse Ollame vide")
                raise BrainOpsError("Ollama indisponible)", code=ErrCode.OLLAMA, ctx={"status": resp.status_code})
    except requests.exceptions.Timeout as exc:
        raise BrainOpsError(
            "Timeout sur l'appel generate", code=ErrCode.OLLAMA, ctx={"status": resp.status_code}
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise BrainOpsError(
            "Connexion à Ollama impossible (Docker HS ?)", code=ErrCode.OLLAMA, ctx={"status": resp.status_code}
        ) from exc
    except requests.HTTPError as exc:
        raise BrainOpsError("HTTPError Ollama", code=ErrCode.OLLAMA, ctx={"status": resp.status_code}) from exc
    return text


@with_child_logger
def get_embedding(prompt: str, model_ollama: str, *, logger: LoggerProtocol | None = None) -> list[float]:
    """
    Appel texte → embedding sur le endpoint EMBEDDINGS.

    Retourne la liste des floats, ou None en cas d'échec.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] get_embedding model=%s url=%s", model_ollama, OLLAMA_URL_EMBEDDINGS)

    payload: dict[str, Any] = {
        "model": model_ollama,
        "prompt": prompt,
        "options": {"num_predict": -1, "num_ctx": 4096},
    }

    try:
        resp = requests.post(OLLAMA_URL_EMBEDDINGS, json=payload, timeout=OLLAMA_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # format attendu: {"embedding": [...]}
        emb = data.get("embedding", [])
        if not emb:
            logger.warning("[WARNING] 🚨 Embedding vide !")
            raise BrainOpsError("Embedding vide)", code=ErrCode.OLLAMA, ctx={"status": resp.status_code})
        # S'assurer que c'est bien une liste de floats
        return [float(x) for x in emb]
    except requests.exceptions.Timeout as exc:
        raise BrainOpsError(
            "Timeout sur l'appel generate", code=ErrCode.OLLAMA, ctx={"status": resp.status_code}
        ) from exc
    except Exception as exc:
        raise BrainOpsError("Ollama KO", code=ErrCode.OLLAMA, ctx={"status": resp.status_code}) from exc
