# """
# # process/gpt_imports.py
# """

# from __future__ import annotations

# from dataclasses import dataclass
# from pathlib import Path
# import re
# import shutil

# from brainops.io.note_writer import safe_write
# from brainops.io.paths import to_abs
# from brainops.ollama.ollama_utils import large_or_standard_note
# from brainops.process_folders.folders import ensure_folder_exists
# from brainops.process_import.synthese.embeddings import make_embeddings_synthesis
# from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger

# TURN_RE = re.compile(r"^\[T(?P<idx>\d+)\]\[(?P<role>user|assistant)\]:\s*(?P<text>.+)$")

# # Patterns possibles dans ta sortie "clean"
# RE_BRACKETED = re.compile(r"^\[T(?P<idx>\d+)\]\[(?P<role>user|assistant)\]:\s*(?P<text>.+)$", re.I)
# RE_LABELED = re.compile(r"^(?P<label>Utilisateur|User|Assistant|IA|Bot)\s*:\s*(?P<text>.+)$", re.I)


# def parse_turns_from_clean_text(
#     cleaned_text: str,
#     *,
#     start_idx: int = 1,
#     logger: LoggerProtocol | None = None,
# ) -> list[Turn]:
#     """
#     Convertit un texte 'clean' (retourné par large_or_standard_note en mode nettoyage)

#     en liste de Turn(idx, role, text).
#     - Supporte deux formats: [T#][role]: ...  OU  'Utilisateur :' / 'Assistant :'
#     - Assigne des idx croissants si manquants.
#     """
#     logger = ensure_logger(logger, __name__)
#     turns: list[Turn] = []
#     next_idx = start_idx

#     for raw in (cleaned_text or "").splitlines():
#         line = raw.strip()
#         if not line:
#             continue

#         m = RE_BRACKETED.match(line)
#         if m:
#             role = m.group("role").lower()
#             idx = int(m.group("idx"))
#             text = m.group("text").strip()
#             turns.append(Turn(idx=idx, role="user" if role == "user" else "assistant", text=text))
#             next_idx = max(next_idx, idx + 1)
#             continue

#         m = RE_LABELED.match(line)
#         if m:
#             label = m.group("label").lower()
#             text = m.group("text").strip()
#             role = "user" if label in {"utilisateur", "user"} else "assistant"
#             turns.append(Turn(idx=next_idx, role=role, text=text))
#             next_idx += 1
#             continue

#         # Ligne orpheline : on l'accole au dernier tour si possible
#         if turns:
#             turns[-1].text = f"{turns[-1].text}\n{line}"
#         else:
#             # Sinon, on crée un tour 'user' par défaut (rare)
#             turns.append(Turn(idx=next_idx, role="user", text=line))
#             next_idx += 1

#     if not turns:
#         logger.warning("parse_turns_from_clean_text: aucune ligne reconnue.")
#     else:
#         logger.info("parse_turns_from_clean_text: %d tours (idx %s..%s)", len(turns), turns[0].idx, turns[-1].idx)
#     return turns


# @dataclass
# class Turn:
#     idx: int
#     role: str
#     text: str


# def parse_turns(cleaned: str) -> list[Turn]:
#     turns: list[Turn] = []
#     for line in cleaned.splitlines():
#         m = TURN_RE.match(line.strip())
#         if m:
#             turns.append(Turn(idx=int(m.group("idx")), role=m.group("role"), text=m.group("text")))
#     return turns


# def pair_chunks(
#     turns: list[Turn],
#     target_chars: int = 1200,
#     hard_cap: int = 1600,
#     min_chars: int = 500,
#     overlap_chars: int = 180,
# ) -> list[str]:
#     """
#     Regroupe (user + assistant) en chunks conversationnels avec découpe propre et overlap.
#     """

#     def sentences(txt: str) -> list[str]:
#         lines = [ln for ln in txt.splitlines() if ln.strip()]
#         codeish = sum(1 for ln in lines if any(t in ln for t in
#             (";", "def ", "Traceback", "ERROR", "docker ", "pip ")))
#         if lines and codeish / len(lines) > 0.4:
#             return [txt]
#         parts = re.split(r"(?<=[\.\!\?])\s+(?=[A-ZÀ-ÖØ-Þ0-9])", txt.strip())
#         return [p.strip() for p in parts if p.strip()]

#     def pack(text: str, room: int) -> list[str]:
#         segs, buf = [], ""
#         for s in sentences(text):
#             if not buf:
#                 buf = s
#             elif len(buf) + 1 + len(s) <= room:
#                 buf = f"{buf} {s}"
#             else:
#                 segs.append(buf)
#                 buf = s
#         if buf:
#             segs.append(buf)
#         return segs

#     chunks: list[str] = []
#     i = 0
#     tail = ""
#     while i < len(turns):
#         if i + 1 < len(turns) and turns[i].role == "user" and turns[i + 1].role == "assistant":
#             u, a = turns[i], turns[i + 1]
#             i += 2
#             user_hdr, asst_hdr = f"[T{u.idx}][user]: ", f"[T{a.idx}][assistant]: "
#             base_len = len(user_hdr) + len(u.text) + 1 + len(asst_hdr)

#             if base_len + len(a.text) <= hard_cap:
#                 group = f"{user_hdr}{u.text}\n{asst_hdr}{a.text}"
#                 if len(group) < min_chars and i < len(turns):
#                     nxt = turns[i]
#                     nxt_line = f"\n[T{nxt.idx}][{nxt.role}]: {nxt.text}"
#                     if len(group) + len(nxt_line) <= hard_cap:
#                         group += nxt_line
#                         i += 1
#                 if tail:
#                     group = tail + group
#                 chunks.append(group[:hard_cap])
#                 tail = group[-overlap_chars:] if overlap_chars else ""
#                 continue

#             # découper réponse assistant
#             room = max(min_chars, hard_cap - base_len)
#             for seg in pack(a.text, room):
#                 group = f"{user_hdr}{u.text}\n{asst_hdr}{seg}"
#                 if tail:
#                     group = tail + group
#                 chunks.append(group[:hard_cap])
#                 tail = group[-overlap_chars:] if overlap_chars else ""
#         else:
#             t = turns[i]
#             i += 1
#             group = f"[T{t.idx}][{t.role}]: {t.text}"
#             if tail:
#                 group = tail + group
#             chunks.append(group[:hard_cap])
#             tail = group[-overlap_chars:] if overlap_chars else ""
#     return chunks


# def _sentences_safe(text: str) -> list[str]:
#     lines = [ln for ln in text.splitlines() if ln.strip()]
#     codeish = sum(1 for ln in lines if any(t in ln for t in (";", "def ", "Traceback", "ERROR", "docker ", "pip ")))
#     if lines and codeish / len(lines) > 0.4:
#         return [text]  # code/log: ne pas couper en phrases
#     parts = re.split(r"(?<=[\.\!\?])\s+(?=[A-ZÀ-ÖØ-Þ0-9])", text.strip())
#     return [p.strip() for p in parts if p.strip()]


# @with_child_logger
# def enforce_embed_budget(
#     chunks: list[str],
#     *,
#     max_chars: int = 1600,  # budget cible par chunk pour l'embedding
#     min_chars: int = 500,
#     overlap_chars: int = 120,  # petit chevauchement
#     logger: LoggerProtocol | None = None,
# ) -> list[str]:
#     """
#     Re-slice les chunks trop longs pour respecter le budget embeddings.

#     - Coupe aux frontières de phrase si possible.
#     - Ajoute un léger overlap pour la continuité.
#     """
#     logger = ensure_logger(logger, __name__)
#     fixed: list[str] = []
#     tail = ""

#     for raw in chunks:
#         if len(raw) <= max_chars:
#             grp = (tail + raw) if (tail and fixed) else raw
#             fixed.append(grp[:max_chars])
#             tail = grp[-overlap_chars:] if overlap_chars else ""
#             continue

#         # Repack par phrases dans la partie assistant si possible; sinon sur l'ensemble
#         parts = _sentences_safe(raw)
#         buf = ""
#         for s in parts:
#             cand = f"{buf} {s}".strip() if buf else s
#             if len(cand) <= max_chars:
#                 buf = cand
#                 continue
#             # flush
#             grp = (tail + buf) if (tail and fixed) else buf
#             fixed.append(grp[:max_chars])
#             tail = grp[-overlap_chars:] if overlap_chars else ""
#             buf = s
#         if buf:
#             grp = (tail + buf) if (tail and fixed) else buf
#             fixed.append(grp[:max_chars])
#             tail = grp[-overlap_chars:] if overlap_chars else ""

#     if logger:
#         logger.info("[EMBED_BUDGET] in=%d, out=%d, max_chars=%d", len(chunks), len(fixed), max_chars)
#     return fixed


# def write_qr_file(chunks: list[str]) -> str:
#     import tempfile

#     text = "\n\n".join(s.strip() for s in chunks)
#     tmp = tempfile.NamedTemporaryFile(prefix="brainops_conv_", suffix=".txt", delete=False)
#     tmp.write(text.encode("utf-8"))
#     tmp.close()
#     return tmp.name


# @with_child_logger
# def process_class_gpt_test(filepath: str | Path, note_id: int, *, logger: LoggerProtocol | None = None) -> None:
#     """
#     Variante de test :
#       - duplique le fichier pour différents modèles,
#       - reformulation,
#       - génère une synthèse via embeddings,
#       - sauvegarde la synthèse dans le fichier.
#     """
#     logger = ensure_logger(logger, __name__)
#     src = Path(str(filepath))
#     dest_dir = to_abs("/Z_technical/test_output_gpt/")
#     ensure_folder_exists(dest_dir, logger=logger)

#     models = ["llama3.1:8b-instruct-q8_0"]  # liste de modèles à tester

#     for model in models:
#         safe_model = re.sub(r'[\/:*?"<>|]', "_", model)
#         first_copy = Path(dest_dir) / f"{src.stem}_{safe_model}{src.suffix}"
#         # second_copy = dest_dir / f"{src.stem}_{safe_model}_suite{src.suffix}"
#         third_copy = Path(dest_dir) / f"{src.stem}_{safe_model}_suite2{src.suffix}"
#         four_copy = Path(dest_dir) / f"{src.stem}_{safe_model}_suite3{src.suffix}"
#         five_copy = Path(dest_dir) / f"{src.stem}_{safe_model}_suite4{src.suffix}"
#         try:
#             copied_1 = shutil.copy(to_abs(Path(src).as_posix()), Path(to_abs(first_copy.as_posix())))
#             logger.debug("[DEBUG] Copie 1 : %s", copied_1)
#             # 0) Nettoyage fenêtré (au lieu d'envoyer toute la conv)
#             cleaned_text: str = large_or_standard_note(
#                 note_id=note_id,
#                 filepath=first_copy.as_posix(),
#                 prompt_name="test_tags_gpt",
#                 model_ollama=model,
#                 source="window_gpt",
#                 split_method="split_windows_by_paragraphs",
#                 logger=logger,
#             )

#             logger.debug("TEST nb cleaned_text : %s", len(cleaned_text))
#             logger.debug("TEST cleaned_text : %s", cleaned_text[:1300])
#             # 2) str → list[Turn] (parse)
#             turns: list[Turn] = parse_turns_from_clean_text(cleaned_text, logger=logger)
#             logger.debug("turns : %s", turns[:1300])
#             logger.debug("len turns : %s", len(turns))
#             # safe_write(second_copy.as_posix(), content=turns or "", logger=logger)

#             # 3) list[Turn] → list[str] (Q→R)
#             qr_chunks: list[str] = pair_chunks(
#                 turns, target_chars=1200, hard_cap=1600, min_chars=500, overlap_chars=180
#             )
#             logger.debug("qr_chunks : %s", qr_chunks[:1300])
#             logger.debug("qr_chunks : %s", len(qr_chunks))
#             safe_write(third_copy.as_posix(), content=qr_chunks or "", logger=logger)
#             # Garde-fou embeddings (si besoin)
#             embed_ready = enforce_embed_budget(
#                 qr_chunks, max_chars=1600, min_chars=500, overlap_chars=120, logger=logger
#             )
#             logger.debug("embed_ready : %s", embed_ready[:1300])
#             logger.debug("embed_ready : %s", len(embed_ready))
#             safe_write(four_copy.as_posix(), content=embed_ready or "", logger=logger)
#             # 4) écrire un fichier Q/R (1 paragraphe = 1 chunk)
#             prepared_path = write_qr_file(qr_chunks)  # petite fonction util qui fait "\n\n".join(...)
#             logger.debug("prepared_path : %s", prepared_path[:1300])
#             # 2) Embeddings : conv_chunks → large_or_standard_note(... persist_blocks=True) ou direct vers ton index
#             # copied_2 = shutil.copy(first_copy.as_posix(), second_copy.as_posix())
#             # logger.debug("[DEBUG] Copie 2 : %s", copied_2)

#             # 4) Embeddings + persistance DB via TON flow (1 paragraphe = 1 bloc)

#             final_response = make_embeddings_synthesis(
#                 note_id=note_id,
#                 filepath=first_copy.as_posix(),
#                 split_method="split_windows_by_paragraphs",
#                 mode="gpt",
#                 source="gpt",
#                 logger=logger,
#             )
#             logger.debug("[DEBUG] final response : %s", final_response)
#             safe_write(five_copy.as_posix(), content=final_response or "", logger=logger)

#         except Exception as exc:  # pylint: disable=broad-except
#             logger.exception("[ERROR] process_class_gpt_test(%s, %s) : %s", src, model, exc)
