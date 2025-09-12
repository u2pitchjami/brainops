#!/usr/bin/env python3
"""
# scripts/semantic_search.py
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from brainops.ollama.ollama_call import get_embedding
from brainops.sql.temp_blocs.db_embeddings_temp_blocs import get_blocks_and_embeddings_by_note
from brainops.utils.logger import LoggerProtocol, get_logger

logger: LoggerProtocol = get_logger("semantic_search")


def _as_np2d(vectors: Sequence[Sequence[float]]) -> np.ndarray:
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr


def search_blocks_by_semantic(
    query_text: str,
    *,
    note_id: int | None,
    top_n: int = 5,
    embed_model: str = "nomic-embed-text:latest",
) -> list[dict[str, Any]]:
    """
    Recherche sémantique des blocs d'une note via embeddings + cosine similarity.

    - note_id: identifiant de la note (obligatoire pour l’instant)
    - embed_model: modèle d'embedding ollama (par défaut: nomic-embed-text:latest)
    """
    if not note_id:
        logger.error("Recherche globale non encore implémentée (note_id requis).")
        return []

    blocks, embeddings = get_blocks_and_embeddings_by_note(note_id, logger=logger)
    if not blocks or not embeddings:
        logger.info("Aucun bloc ou embedding trouvé pour note_id=%s.", note_id)
        return []

    query_vec = get_embedding(query_text, embed_model, logger=logger)
    if query_vec is None:
        logger.error("Embedding de la requête introuvable (None).")
        return []

    try:
        emb_mat = _as_np2d(embeddings)  # (N, D)
        q = _as_np2d(query_vec)  # (1, D)
        if emb_mat.shape[1] != q.shape[1]:
            logger.error(
                "Dimension embedding incohérente: blocs=%s vs query=%s",
                emb_mat.shape,
                q.shape,
            )
            return []
        sims = cosine_similarity(q, emb_mat)[0]
        top_idx = sims.argsort()[-top_n:][::-1]
        return [{"text": blocks[i], "score": float(sims[i])} for i in top_idx]
    except Exception as exc:
        logger.exception("Erreur similarity: %s", exc)
        return []


def main() -> None:
    """
    Main _summary_

    _extended_summary_
    """
    parser = argparse.ArgumentParser(description="Recherche sémantique IA locale sur Obsidian")
    parser.add_argument("--query", required=True, help="Texte ou question à chercher")
    parser.add_argument("--note_id", type=int, required=True, help="ID de la note cible")
    parser.add_argument("--top", type=int, default=5, help="Nombre de blocs à retourner")
    parser.add_argument(
        "--embed-model",
        type=str,
        default="nomic-embed-text:latest",
        help="Modèle d'embedding Ollama (default: nomic-embed-text:latest)",
    )
    parser.add_argument("--out", type=str, help="Fichier de sortie (.md ou .json)")
    args = parser.parse_args()

    results = search_blocks_by_semantic(
        args.query,
        note_id=args.note_id,
        top_n=args.top,
        embed_model=args.embed_model,
    )

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix.lower() == ".json":
            out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            lines = [f"## Bloc {i + 1} (score {r['score']:.2f})\n{r['text']}\n\n" for i, r in enumerate(results)]
            out.write_text("".join(lines), encoding="utf-8")
        logger.info("Résultats écrits dans : %s", out)
    else:
        # sortie CLI lisible
        for r in results:
            print(f"\n[Score {r['score']:.2f}]")
            print(r["text"])


if __name__ == "__main__":
    main()
