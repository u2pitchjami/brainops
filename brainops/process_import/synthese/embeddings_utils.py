"""# process/embeddings_utils.py"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics.pairwise import cosine_similarity

from brainops.ollama.ollama_call import call_ollama_with_retry
from brainops.ollama.ollama_utils import large_or_standard_note
from brainops.sql.notes.db_temp_blocs import get_blocks_and_embeddings_by_note
from brainops.utils.config import MODEL_EMBEDDINGS
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger


@with_child_logger
def make_embeddings_synthesis(note_id: int, filepath: str, *, logger: LoggerProtocol | None = None) -> str | None:
    """
    1) Génère/persiste des embeddings via 'large_or_standard_note' (mode embeddings)
    2) Sélectionne les meilleurs blocs
    3) Construit le prompt et appelle le modèle de synthèse
    Retourne le texte de synthèse ou None en cas d'échec.
    """
    logger = ensure_logger(logger, __name__)

    # 1) création des embeddings + stockage des blocs (process_large_note côté projet)
    _ = large_or_standard_note(
        filepath=filepath,
        source="embeddings",
        process_mode="large_note",
        prompt_name="embeddings",
        model_ollama=MODEL_EMBEDDINGS,
        write_file=False,
        split_method="words",
        word_limit=100,
        note_id=note_id,
        persist_blocks=True,
        send_to_model=True,
        logger=logger,
    )

    # 2) top blocs (avec score pour debug)
    top_blocks = select_top_blocks(note_id=note_id, ratio=0.3, return_scores=True, logger=logger)
    for bloc in top_blocks:
        logger.debug("🧠 Score %.4f → %s...", bloc["score"], bloc["text"][:80])

    # 3) synthèse finale
    prompt = build_summary_prompt(top_blocks)
    final_response = call_ollama_with_retry(prompt, model_ollama="llama3.1:8b-instruct-q8_0", logger=logger)
    return final_response


@with_child_logger
def select_top_blocks(
    note_id: int,
    N: int | None = None,
    ratio: float = 0.3,
    return_scores: bool = False,
    *,
    logger: LoggerProtocol | None = None,
) -> list[dict[str, Any]] | list[str]:
    """
    Sélectionne les N blocs les plus proches pour une note donnée.
    - Récupère (blocks, embeddings) depuis la DB.
    - Calcule l'embedding moyen comme 'requête'.
    - Retourne une liste de dicts {"text": str, "score": float} si return_scores=True,
      sinon une liste de textes.
    """
    logger = ensure_logger(logger, __name__)
    logger.debug("[DEBUG] select_top_blocks(note_id=%s, N=%s, ratio=%.2f)", note_id, N, ratio)

    blocks, embeddings = get_blocks_and_embeddings_by_note(note_id, logger=logger)
    if not blocks or not embeddings:
        logger.warning("[SELECT] Aucun bloc ou embedding trouvé (note_id=%s).", note_id)
        return []

    total_blocks = len(blocks)
    if N is None:
        N = max(1, int(total_blocks * ratio))

    try:
        arr: NDArray[np.float64] = np.asarray(embeddings, dtype=float)  # shape: (m, d)
        if arr.ndim != 2:
            logger.error("[SELECT] Forme embeddings invalide: %s", arr.shape)
            return []
        target: NDArray[np.float64] = np.mean(arr, axis=0)  # (d,)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[SELECT] Erreur calcul moyenne embedding : %s", exc)
        return []

    try:
        sims: NDArray[np.float64] = cosine_similarity(target.reshape(1, -1), arr)[0]
        top_idx = sims.argsort()[-N:][::-1]
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("[SELECT] Erreur lors du calcul de similarité : %s", exc)
        return []

    if return_scores:
        return [{"text": blocks[i], "score": float(sims[i])} for i in top_idx]
    return [blocks[i] for i in top_idx]


def build_summary_prompt(blocks: Sequence[str] | Sequence[dict[str, Any]], structure: str = "simple") -> str:
    """
    Construit un prompt de synthèse à partir d'une liste de blocs sélectionnés.
    Accepte soit une liste de strings, soit une liste de dicts {"text": ..., "score": ...}.
    """
    intro = (
        "Voici des extraits importants d'une note. Résume-les de façon concise et claire.\n\n"
        if structure == "simple"
        else "Voici plusieurs extraits pertinents issus d'une note. "
        "Organise les idées par thème, puis fais une synthèse claire.\n\n"
    )

    def extract_text(b: Any) -> str:
        if isinstance(b, dict) and "text" in b:
            return str(b["text"])
        return str(b)

    parts = [f"Bloc {i + 1}:\n{extract_text(b)}\n" for i, b in enumerate(blocks)]
    content = "\n".join(parts)

    end = (
        "\nFais une synthèse complète et compréhensible.\n"
        "La sortie doit être en **français** et lisible dans **Obsidian**.\n"
        "N'ajoute aucune introduction ni conclusion superflue."
        if structure == "simple"
        else "\nFournis une synthèse en plusieurs parties (par thème) si pertinent."
    )

    return f"{intro}{content}{end}"
