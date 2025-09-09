"""queue."""

# watcher/queue_manager.py
from __future__ import annotations

from queue import Queue
from typing import Literal, NotRequired, Optional, TypedDict

from brainops.header.yaml_read import test_title
from brainops.process_folders.process_folder_event import process_folder_event
from brainops.process_notes.new_note import new_note
from brainops.process_notes.process_single_note import process_single_note
from brainops.process_notes.update_note import update_note
from brainops.sql.notes.db_notes import delete_note_by_path
from brainops.sql.notes.db_notes_utils import file_path_exists_in_db
from brainops.utils.files import wait_for_file
from brainops.utils.logger import get_logger
from brainops.watcher.queue_utils import PendingNoteLockManager, get_lock_key

logger = get_logger("Brainops Watcher")

# ---- Typage des événements -----------------------------------------------------
EventAction = Literal["created", "deleted", "modified", "moved"]
EventType = Literal["file", "directory"]


class DirEvent(TypedDict, total=True):
    """
    DirEvent _summary_

    _extended_summary_

    Args:
        TypedDict (_type_): _description_
        total (bool, optional): _description_. Defaults to True.
    """

    type: Literal["directory"]
    action: EventAction
    path: str
    src_path: NotRequired[str]


class Event(TypedDict, total=True):
    """
    Event _summary_

    _extended_summary_

    Args:
        TypedDict (_type_): _description_
        total (bool, optional): _description_. Defaults to True.
    """

    type: EventType
    action: EventAction
    path: str
    # Clés optionnelles selon action/type
    src_path: NotRequired[str]
    note_id: NotRequired[Optional[int]]


# File d’attente unique et lock manager
event_queue: "Queue[Event]" = Queue()
lock_mgr = PendingNoteLockManager()


def enqueue_event(event: Event) -> None:
    """
    Enrichit et enfile un événement.
    - Pour les fichiers, pose un lock logique (note_id ou path).
    - Si le lock existe déjà, l'événement est ignoré (dé-bounce de travail).
    """
    if event["type"] == "file":
        file_path: str = event.get("path")  # always present (TypedDict total)
        src_path: Optional[str] = event.get("src_path")

        note_id: Optional[int] = file_path_exists_in_db(
            file_path, src_path, logger=logger
        )
        event["note_id"] = note_id  # enrichit l’événement

        key = get_lock_key(note_id, file_path)
        if not lock_mgr.acquire(key):
            logger.debug("[QUEUE] 🚫 Ignoré, déjà en file : %s", key)
            return

    event_queue.put(event)


def process_queue() -> None:
    """
    Boucle de consommation des événements.
    - Traite fichiers et dossiers.
    - Relâche toujours les locks en fin de traitement.
    """
    log_event_queue()
    while True:
        event: Optional[Event] = None
        file_path: Optional[str] = None
        src_path: Optional[str] = None
        note_id: Optional[int] = None
        locked: bool = False

        try:
            event = event_queue.get()

            logger.debug("[DEBUG] ===== PROCESS QUEUE EVENT RECUP : %s", event)
            file_path = event.get("path")
            src_path = event.get("src_path")
            note_id = event.get("note_id")  # peut être déjà renseigné par enqueue_event

            etype = event["type"]
            action = event["action"]

            # Fichiers: attendre la présence (sauf 'deleted')
            if etype == "file":
                if action != "deleted":
                    if not wait_for_file(file_path, logger=logger):  # type: ignore[arg-type]
                        logger.warning("⚠️ Fichier introuvable, skip : %s", file_path)
                        continue  # passe à l'événement suivant

                # Assure un note_id si absent
                if note_id is None:
                    note_id = file_path_exists_in_db(file_path, src_path, logger=logger)  # type: ignore[arg-type]
                    if not note_id:
                        logger.debug("[DEBUG] ===== Test Title")
                        test_title(file_path, logger=logger)  # type: ignore[arg-type]
                        logger.debug(
                            f"[DEBUG] {file_path} innexistant dans obsidian_notes"
                        )
                        note_id = new_note(
                            file_path, logger=logger
                        )  # 🔥 Gère les événements des notes
                        logger.info(
                            "[INFO] Note créée : (id=%s) %s", note_id, file_path
                        )

                # Pose le lock si pas encore fait par enqueue_event
                key = get_lock_key(note_id, file_path)
                if lock_mgr.acquire(key):
                    locked = True

                if action == "deleted":
                    deleted = delete_note_by_path(file_path, logger=logger)  # type: ignore[arg-type]
                    if deleted:
                        logger.info(
                            "[SUPPR] ✅ Note Supprimée: (id=%s) %s", note_id, file_path
                        )
                    else:
                        logger.warning("[SUPPR] Rien à supprimer pour: %s", file_path)
                    continue

                # created / modified / moved
                if action in ("created", "modified"):
                    processed = process_single_note(file_path, note_id, logger=logger)  # type: ignore[arg-type]
                    if not processed:
                        logger.warning("[IMPORT] Echec de l'import : (id=%s)", note_id)
                        update_note(note_id, file_path, logger=logger)  # type: ignore[arg-type]
                    continue

                if action == "moved":
                    logger.debug(
                        "[BUSY] Déplacement fichier : %s -> %s", src_path, file_path
                    )
                    processed = process_single_note(file_path, note_id, src_path=src_path, logger=logger)  # type: ignore[arg-type]
                    if not processed:
                        update_note(note_id, file_path, src_path)  # type: ignore[arg-type]
                    continue

            # Dossiers: déléguer au gestionnaire de dossiers
            if etype == "directory":
                if action == "moved":
                    dir_ev: DirEvent = {
                        "type": "directory",
                        "action": "moved",
                        "src_path": event["src_path"],
                        "path": event["path"],
                    }
                else:
                    dir_ev = {
                        "type": "directory",
                        "action": event["action"],
                        "path": event["path"],
                    }

                # si ton hub est décoré @with_child_logger / ensure_logger, tu peux lui passer logger
                process_folder_event(dir_ev, logger=logger)

            logger.debug("[DEBUG] Fini: %s - %s", etype, action)
            log_event_queue()

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("[ERREUR] File d'attente: %s", exc)
        finally:
            # Release lock si un lock est posé pour les fichiers
            if (event is not None) and (event.get("type") == "file"):
                # On reconstruit la clé de manière robuste
                key = get_lock_key(note_id, file_path)
                if key and (locked or lock_mgr.is_locked(key)):
                    lock_mgr.release(key)
            event_queue.task_done()


def log_event_queue() -> None:
    """Logge un aperçu de la file en DEBUG."""
    try:
        items = list(event_queue.queue)  # type: ignore[attr-defined]
        logger.debug("[DEBUG] Contenu file d'attente : %s", items)
    except Exception:  # queue interne peut changer pendant l’itération
        logger.debug("[DEBUG] Contenu file d'attente : <non disponible>")
