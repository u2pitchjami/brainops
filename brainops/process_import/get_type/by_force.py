"""# process_import_get_type.by_force.py"""

from __future__ import annotations

from pathlib import Path

from brainops.process_import.utils.divers import rename_file
from brainops.sql.categs.db_categ_utils import categ_extract
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.models.exceptions import BrainOpsError


@with_child_logger
def get_type_by_force(
    filepath: str,
    note_id: int,
    *,
    logger: LoggerProtocol | None = None,
) -> str:
    """
    Force la catégorisation d'une note à partir de son chemin (sans appel IA) :
      - déduit category/subcategory via la base (categ_extract)
      - renomme le fichier (incl. note_id si ta logique le fait)
      - met à jour la ligne en base
      - relance l'import normal + synthèse
    """
    logger = ensure_logger(logger, __name__)
    try:
        path = Path(str(filepath)).resolve()
        base_folder = path.parent.as_posix()

        cat_name, subcat_name, category_id, subcategory_id = categ_extract(base_folder)
        logger.debug(
            "[FORCE_CATEG] Base=%s | cat=%s (%s) | sub=%s (%s)",
            base_folder,
            cat_name,
            category_id,
            subcat_name,
            subcategory_id,
        )

        if not category_id or not subcategory_id:
            logger.warning("[FORCE_CATEG] Sous-catégorie non détectée, annulation.")
            raise

        # Renommage
        new_path = str(rename_file(path.as_posix(), note_id))

    except BrainOpsError:
        raise
    except Exception as exc:
        logger.exception("Crash inattendu dans : %s",exc)
        raise BrainOpsError(f"Erreur inattendue: {exc}") from exc
    return new_path
