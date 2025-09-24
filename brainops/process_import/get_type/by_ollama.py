"""
# handlers/process/get_type.py
"""

from __future__ import annotations

from brainops.models.classification import ClassificationResult
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.process_import.get_type.by_ollama_utils import (
    _classify_with_llm,
    _resolve_destination,
    clean_note_type,
    parse_category_response,
)
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def get_type_by_ollama(content: str, note_id: int, *, logger: LoggerProtocol | None = None) -> ClassificationResult:
    """
    Analyse le type via LLM → calcule dossier cible → déplace → met à jour la DB.

    Retourne le **nouveau chemin complet** ou None.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] Entrée process_get_note_type")
    llama_proposition: str = ""  # évite variable potentiellement non définie (#bug)

    try:
        # 1) LLM
        llama_proposition = _classify_with_llm(note_id, content, logger=logger)
        logger.debug("[DEBUG] LLM proposition : %s", llama_proposition)

        # 3) Parse réponse ollama
        parsed = parse_category_response(llama_proposition)
        note_type = clean_note_type(parsed, logger=logger)

        if any(term in note_type.lower() for term in ["uncategorized", "unknow"]):
            raise BrainOpsError(
                "[METADATA] ❌ Classification invalide → 'uncategorized",
                code=ErrCode.METADATA,
                ctx={
                    "step": "get_type_by_ollama",
                    "llama_proposition": llama_proposition,
                    "note_id": note_id,
                },
            )
        logger.info("[TYPE] 👌 Type de note détecté pour (ID=%s) : %s", note_id, note_type)

        # 3) Résolution dossier cible
        classification = _resolve_destination(note_type, note_id, logger=logger)

    except BrainOpsError as exc:
        exc.with_context({"step": "get_type_by_ollama", "note_id": note_id})
        raise
    except Exception as exc:
        raise BrainOpsError(
            "[METADATA] ❌ Definition du type par Ollama KO",
            code=ErrCode.UNEXPECTED,
            ctx={
                "step": "get_type_by_ollama",
                "note_id": note_id,
                "root_exc": type(exc).__name__,
                "root_msg": str(exc),
            },
        ) from exc
    return classification
