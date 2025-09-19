"""
# process/embeddings_utils.py
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def build_summary_prompt(blocks: Sequence[str] | Sequence[dict[str, Any]], structure: str = "simple") -> str:
    """
    Construit un prompt de synthèse à partir d'une liste de blocs sélectionnés.

    Accepte soit une liste de strings, soit une liste de dicts {"text": ..., "score": ...}.
    """
    intro = (
        "Voici une série d’extraits issus d'un article web réparti en « blocks embeddings »\
            (chaque bloc est un paragraphe ou une section thématique).\n\n"
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
        "\nFais une synthèse claire, structurée et concise de l’ensemble, en identifiant pour chaque point-clé :\n"
        "- les arguments majeurs,\n"
        "- les consensus, et les divergences éventuelles entre les sources.\n"
        "- Précise les faits, chiffres ou données importantes,\n"
        "- et évite les redites.\n"
        "La sortie doit être en **français** et lisible dans **Obsidian**.\n"
        "N'ajoute aucune introduction ni conclusion superflue."
        if structure == "simple"
        else "\nFournis une synthèse en plusieurs parties (par thème) si pertinent."
    )

    return f"{intro}{content}{end}"
