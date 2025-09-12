"""
# handlers/process/get_type.py
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import shutil

from Levenshtein import ratio

from brainops.models.classification import ClassificationResult
from brainops.models.exceptions import BrainOpsError, ErrCode
from brainops.ollama.ollama_call import call_ollama_with_retry
from brainops.ollama.prompts import PROMPTS
from brainops.process_import.utils.divers import (
    prompt_name_and_model_selection,
)
from brainops.process_import.utils.paths import ensure_folder_exists
from brainops.sql.categs.db_categ import get_path_safe
from brainops.sql.categs.db_dictionary_categ import (
    generate_categ_dictionary,
    generate_optional_subcategories,
)
from brainops.sql.folders.db_folder_utils import (
    get_path_from_classification,
)
from brainops.sql.get_linked.db_get_linked_folders_utils import (
    get_folder_id,
)
from brainops.sql.notes.db_update_notes import update_obsidian_note
from brainops.utils.config import (
    MODEL_GET_TYPE,
    SIMILARITY_WARNINGS_LOG,
    UNCATEGORIZED_JSON,
    UNCATEGORIZED_PATH,
)
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger

# ---------- Parse & nettoyage --------------------------------------------------


def parse_category_response(llama_proposition: str) -> str:
    """
    Extrait "Category/Subcategory" d'une réponse LLM.
    """
    match = re.search(r"([A-Za-z0-9_ ]+)/([A-Za-z0-9_ ]+)", llama_proposition or "")
    if match:
        return f"{match.group(1).strip()}/{match.group(2).strip()}"
    raise BrainOpsError("Parse Categ KO", code=ErrCode.METADATA, ctx={"llama_proposition": llama_proposition})


def clean_note_type(parse_category: str) -> str:
    """
    Nettoyage: guillemets -> off, espaces -> _, interdits -> off, pas de '.' final.
    """
    clean_str = parse_category.strip().replace('"', "").replace("'", "")
    clean_str = clean_str.replace(" ", "_")
    clean_str = re.sub(r'[\:*?"<>|]', "", clean_str)
    clean_str = re.sub(r"\.$", "", clean_str)
    return clean_str


# ---------- Similarité (inchangé) ---------------------------------------------


def find_similar_levenshtein(
    name: str,
    existing_names: list[str],
    threshold_low: float = 0.7,
    entity_type: str = "subcategory",
) -> list[tuple[str, float]]:
    """
    find_similar_levenshtein _summary_

    _extended_summary_

    Args:
        name (str): _description_
        existing_names (list[str]): _description_
        threshold_low (float, optional): _description_. Defaults to 0.7.
        entity_type (str, optional): _description_. Defaults to "subcategory".

    Returns:
        _type_: _description_
    """
    similar: list[tuple[str, float]] = []
    try:
        for existing in existing_names:
            similarity = ratio(name, existing)
            # logger.debug(...) → logger injecté + décorateur dans les call sites
            if similarity >= threshold_low:
                similar.append((existing, similarity))
    except Exception as exc:
        raise BrainOpsError("similar_levenshtein KO", code=ErrCode.METADATA, ctx={"name": name}) from exc
    return sorted(similar, key=lambda x: x[1], reverse=True)


def check_and_handle_similarity(
    name: str,
    existing_names: list[str],
    threshold_low: float = 0.7,
    entity_type: str = "subcategory",
) -> str | None:
    """
    check_and_handle_similarity _summary_

    _extended_summary_

    Args:
        name (str): _description_
        existing_names (list[str]): _description_
        threshold_low (float, optional): _description_. Defaults to 0.7.
        entity_type (str, optional): _description_. Defaults to "subcategory".

    Returns:
        Optional[str]: _description_
    """
    threshold_high = 0.9
    similar = find_similar_levenshtein(name, existing_names, threshold_low, entity_type)
    if similar:
        closest, score = similar[0]
        if score >= threshold_high:
            # Fusion auto
            return closest
        if threshold_low <= score < threshold_high:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = (
                f"[{current_time}] Doute sur {entity_type}: '{name}' proche de '{closest}' (score: {score:.2f})\n"
            )
            # On log dans le fichier prévu
            with open(SIMILARITY_WARNINGS_LOG, "a", encoding="utf-8") as log_file:
                log_file.write(log_message)
            return None
    return name


# ---------- Gestion UNCATEGORIZED ---------------------------------------------


@with_child_logger
def handle_uncategorized(
    note_id: int,
    filepath: str | Path,
    note_type: str,
    llama_proposition: str,
    *,
    logger: LoggerProtocol | None = None,
) -> None:
    """
    Déplace la note vers UNCATEGORIZED_PATH et journalise pour reprocessing.
    """
    logger = ensure_logger(logger, __name__)
    src = Path(str(filepath)).expanduser().resolve()
    try:
        ensure_folder_exists(Path(UNCATEGORIZED_PATH), logger=logger)
        dest = Path(UNCATEGORIZED_PATH) / src.name

        shutil.move(src.as_posix(), dest.as_posix())
        logger.warning("[WARNING] 🚨 Note déplacée vers 'uncategorized' : %s", dest.as_posix())

        # MAJ DB avec le vrai folder_id de UNCATEGORIZED_PATH
        unc_folder_id = get_folder_id(Path(UNCATEGORIZED_PATH).as_posix(), logger=logger)
        updates = {"folder_id": unc_folder_id, "file_path": dest.as_posix()}
        update_obsidian_note(note_id, updates, logger=logger)

        # Journal JSON
        data = {}
        if Path(UNCATEGORIZED_JSON).exists():
            with open(UNCATEGORIZED_JSON, encoding="utf-8") as f:
                data = json.load(f)
        data[dest.as_posix()] = {
            "original_type": note_type,
            "llama_proposition": llama_proposition or "",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(UNCATEGORIZED_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    except Exception as exc:
        logger.exception("[ERREUR] handle_uncategorized(%s) : %s", src.as_posix(), exc)
        raise BrainOpsError("déplacement uncategorized KO", code=ErrCode.METADATA, ctx={"note_id": note_id}) from exc


# ---------- Classification & déplacement --------------------------------------


def _classify_with_llm(note_id: int, content: str, *, logger: LoggerProtocol | None = None) -> str:
    """
    Construit le prompt et appelle Ollama.

    Retourne la chaîne brute (ex: "Dev/Python").
    """
    logger = ensure_logger(logger, __name__)
    try:
        # dictionnaires pour guider le LLM
        subcateg_dict = generate_optional_subcategories(logger=logger)
        logger.debug("[DEBUG] subcateg_dict _classify_with_llm : %s", subcateg_dict)
        categ_dict = generate_categ_dictionary(logger=logger)
        logger.debug("[DEBUG] categ_dict _classify_with_llm : %s", categ_dict)

        prompt_name, _ = prompt_name_and_model_selection(note_id, key="type", logger=logger)  # note_id pas requis ici
        logger.debug("[DEBUG] prompt_name _classify_with_llm : %s", prompt_name)
        model_ollama = MODEL_GET_TYPE
        prompt = PROMPTS[prompt_name].format(
            categ_dict=categ_dict,
            subcateg_dict=subcateg_dict,
            content=content[:1500],
        )
        logger.debug("[DEBUG] prompt _classify_with_llm : %s", prompt)
        return call_ollama_with_retry(prompt, model_ollama, logger=logger)
    except Exception as exc:
        raise BrainOpsError("_classify_with_llm KO", code=ErrCode.OLLAMA, ctx={"status": "ollama"}) from exc


@with_child_logger
def _resolve_destination(
    note_type: str, note_id: int, filepath: str, *, logger: LoggerProtocol | None = None
) -> ClassificationResult:
    """
    À partir du note_type "Cat/Sub", calcule ids + dossier cible.
    """
    logger = ensure_logger(logger, __name__)
    try:
        cat_id = None
        subcat_id = None
        path_result = get_path_safe(note_type, filepath, note_id, logger=logger)

        cat_id, subcat_id = path_result
        res = get_path_from_classification(cat_id, subcat_id, logger=logger)
        folder_id, dest_folder = res

    except Exception as exc:
        raise BrainOpsError("Ollama KO", code=ErrCode.OLLAMA, ctx={"note_id": note_id}) from exc
    return ClassificationResult(
        note_type=note_type,
        category_id=cat_id,
        subcategory_id=subcat_id,
        folder_id=folder_id,
        dest_folder=dest_folder,
        status="archive",
    )
