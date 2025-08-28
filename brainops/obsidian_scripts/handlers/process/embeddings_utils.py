import logging

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from brainops.obsidian_scripts.handlers.ollama.ollama_call import call_ollama_with_retry
from brainops.obsidian_scripts.handlers.ollama.ollama_utils import (
    large_or_standard_note,
)
from brainops.obsidian_scripts.handlers.sql.db_temp_blocs import (
    get_blocks_and_embeddings_by_note,
)

logger = logging.getLogger("obsidian_notes." + __name__)


def make_embeddings_synthesis(note_id: int, filepath: str) -> None:

    large_or_standard_note(
        filepath=filepath,
        source="embeddings",
        process_mode="large_note",
        prompt_name="embeddings",
        model_ollama="nomic-embed-text:latest",
        write_file=False,
        split_method="words",
        word_limit=100,
        note_id=note_id,
    )

    top_blocks = select_top_blocks(note_id=note_id, ratio=0.3, return_scores=True)
    for bloc in top_blocks:
        logger.debug(f"🧠 Score {bloc['score']:.4f} → {bloc['text'][:80]}...")

    prompt = build_summary_prompt(top_blocks)
    final_response = call_ollama_with_retry(
        prompt, model_ollama="llama3.1:8b-instruct-q8_0"
    )
    return final_response


def select_top_blocks(
    note_id: int, N: int | None = None, ratio: float = 0.3, return_scores: bool = False
):
    """
    Sélectionne les N blocs les plus proches pour une note donnée (via note_id).

    Embeddings récupérés depuis la base via get_blocks_and_embeddings_by_note().
    """
    logger.debug("[DEBUG] select_top_blocks")
    blocks, embeddings = get_blocks_and_embeddings_by_note(note_id)
    # logger.debug(f"[DEBUG] embeddings : {embeddings[:200]}")

    if not blocks or not embeddings:
        logger.warning("[SELECT] Aucun bloc ou embedding trouvé.")
        return []

    total_blocks = len(blocks)

    if N is None:
        N = max(1, int(total_blocks * ratio))

    try:
        target_embedding = np.mean(embeddings, axis=0)
        logger.debug(f"[DEBUG] target_embedding : {target_embedding[:200]}")
    except Exception as e:
        logger.error(f"[SELECT] Erreur calcul moyenne embedding : {e}")
        return []

    try:
        similarities = cosine_similarity([target_embedding], embeddings)[0]
        logger.debug(f"[DEBUG] similarities : {similarities[:200]}")
        top_indices = similarities.argsort()[-N:][::-1]
        logger.debug(f"[DEBUG] top_indices : {top_indices[:200]}")
    except Exception as e:
        logger.error(f"[SELECT] Erreur lors du calcul de similarité : {e}")
        return []

    selected_blocks = [blocks[i] for i in top_indices]
    logger.debug(f"[DEBUG] selected_blocks : {selected_blocks[:200]}")

    if return_scores:
        return [{"text": blocks[i], "score": similarities[i]} for i in top_indices]
    else:
        return [blocks[i] for i in top_indices]


def build_summary_prompt(blocks, structure="simple") -> str:
    """
    Construit un prompt de synthèse à partir d'une liste de blocs sélectionnés.
    """
    logger.debug("[DEBUG] build_summary_prompt")
    intro = (
        "Voici des extraits importants d'une note. Résume-les de façon concise et claire.\n\n"
        if structure == "simple"
        else "Voici plusieurs extraits pertinents issus d'une note.\
            Organise les idées par thème, puis fais une synthèse claire.\n\n"
    )
    content = "\n".join([f"Bloc {i + 1}:\n{b}\n" for i, b in enumerate(blocks)])
    end = (
        "\nFais une synthèse complète et compréhensive.\n"
        "\nLa sortie doit être en **français** et lisible dans **Obsidian**\n"
        "N'ajoute auc d’introduction ou de conclusion superflue"
        if structure == "simple"
        else "\nFournis une synthèse en plusieurs parties (par thème) si pertinent."
    )
    logger.debug(f"[DEBUG] {intro}{content}{end}")
    return f"{intro}{content}{end}"
