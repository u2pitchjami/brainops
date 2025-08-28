#!/usr/bin/env python3
# semantic_search.py

import argparse
import json
from brainops.obsidian_scripts.handlers.sql.db_temp_blocs import get_blocks_and_embeddings_by_note
from brainops.obsidian_scripts.handlers.process.embeddings_utils import get_embedding
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def search_blocks_by_semantic(query_text: str, note_id: int = None, top_n: int = 5):
    if note_id:
        blocks, embeddings = get_blocks_and_embeddings_by_note(note_id)
    else:
        # 👉 Ici, tu peux ajouter plus tard un mode multi-note
        print("[ERROR] Recherche globale non encore implémentée.")
        return []

    if not blocks or not embeddings:
        print("[INFO] Aucun bloc ou embedding trouvé.")
        return []

    query_embedding = get_embedding(query_text)
    similarities = cosine_similarity([query_embedding], embeddings)[0]
    top_indices = similarities.argsort()[-top_n:][::-1]

    results = [{"text": blocks[i], "score": similarities[i]} for i in top_indices]
    return results


def main():
    parser = argparse.ArgumentParser(description="Recherche sémantique IA locale sur Obsidian")
    parser.add_argument("--query", required=True, help="Texte ou question à chercher")
    parser.add_argument("--note_id", type=int, required=True, help="ID de la note cible")
    parser.add_argument("--top", type=int, default=5, help="Nombre de blocs à retourner")
    parser.add_argument("--out", type=str, help="Fichier de sortie (.md ou .json)")
    args = parser.parse_args()

    results = search_blocks_by_semantic(args.query, args.note_id, args.top)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            if args.out.endswith(".json"):
                json.dump(results, f, indent=2, ensure_ascii=False)
            else:
                for i, r in enumerate(results):
                    f.write(f"## Bloc {i+1} (score {r['score']:.2f})\n{r['text']}\n\n")
        print(f"[OK] Résultats écrits dans : {args.out}")
    else:
        for r in results:
            print(f"\n[Score {r['score']:.2f}]")
            print(r["text"])


if __name__ == "__main__":
    main()
