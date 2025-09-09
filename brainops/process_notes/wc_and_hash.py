"""
process_note.wc_and_hash.py.
"""

from __future__ import annotations

import codecs
import hashlib
from pathlib import Path
import re

CHUNK_SIZE = 1024 * 1024  # 1 Mo


def compute_wc_and_hash(fp: Path) -> tuple[int, str | None]:
    """
    Calcule word_count (pour .md/.txt) et sha256 en un seul passage disque.

    - Pour les autres extensions: word_count=0, hash quand même.
    """
    is_text = fp.suffix.lower() in {".md", ".txt"}
    h = hashlib.sha256()
    word_count = 0

    # décodeur texte incrémental (permet de compter les mots sans relire)
    decoder = codecs.getincrementaldecoder("utf-8")(errors="ignore") if is_text else None
    tail = ""  # dernier token potentiel coupé entre deux chunks

    with fp.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)

            if decoder is not None:
                # on décode ce chunk en texte
                text = decoder.decode(chunk)
                if not text:
                    continue
                buf = tail + text

                # si le buffer se termine par un espace, aucun mot coupé
                if buf[-1].isspace():
                    word_count += len(re.findall(r"\S+", buf))
                    tail = ""
                else:
                    tokens = re.findall(r"\S+", buf)
                    if tokens:
                        word_count += max(0, len(tokens) - 1)
                        tail = tokens[-1]
                    else:
                        # que des espaces/contrôles → rien à compter, tail inchangé
                        pass

        # flush du décodeur pour le dernier fragment (si besoin)
        if decoder is not None:
            rest = decoder.decode(b"", final=True)
            if rest:
                buf = tail + rest
                word_count += len(re.findall(r"\S+", buf))
            elif tail:
                # s'il restait un token partiel non suivi d'espace, on le compte
                word_count += 1
            tail = ""

    return word_count, h.hexdigest()
