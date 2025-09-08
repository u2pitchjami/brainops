# /watcher/start.py
from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from watchdog.events import FileMovedEvent, FileSystemEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from brainops.utils.config import (
    BASE_PATH,
    WATCHDOG_DEBOUNCE_WINDOW,
    WATCHDOG_POLL_INTERVAL,
)
from brainops.utils.logger import LoggerProtocol, ensure_logger, with_child_logger
from brainops.utils.normalization import normalize_full_path
from brainops.watcher.queue_manager import (
    enqueue_event,
    get_logger,
    log_event_queue,
    process_queue,
)
from brainops.watcher.queue_utils import PendingNoteLockManager

logger = get_logger("Brainops Watcher")

_TEMP_NAME_RE = re.compile(
    r"""^(
        untitled
      | sans[\s_-]*titre
      | new[\s_-]*note
      | nouvelle[\s_-]*note
      | new[\s_-]*folder
      | nouveau[\s_-]*dossier
    )(?:[\s_-]*\d+|\s*\(\d+\))?$""",
    re.IGNORECASE | re.VERBOSE,
)

LOCK_MGR = PendingNoteLockManager()


def _start_queue_thread() -> threading.Thread:
    """Lance process_queue() dans un thread daemon pour ne pas bloquer la boucle principale."""
    thread = threading.Thread(target=process_queue, name="queue-worker", daemon=True)
    thread.start()
    return thread


def start_watcher(*, logger: Optional[LoggerProtocol] = None) -> None:
    """
    Démarre la surveillance du vault Obsidian (PollingObserver).

    Lit la config via .env :
      - BASE_PATH (obligatoire, chemin existant)
      - WATCHDOG_POLL_INTERVAL (float, défaut 1.0)
      - WATCHDOG_DEBOUNCE_WINDOW (float, défaut 0.5)
    """
    logger = ensure_logger(logger, __name__)
    logger.info(
        "Watcher démarré (PollingObserver, interval=%.2fs) sur %s",
        WATCHDOG_POLL_INTERVAL,
        BASE_PATH,
    )

    observer = PollingObserver(timeout=WATCHDOG_POLL_INTERVAL)
    handler = NoteHandler(logger=logger, debounce_window=WATCHDOG_DEBOUNCE_WINDOW)
    observer.schedule(handler, BASE_PATH, recursive=True)
    observer.start()

    worker = _start_queue_thread()

    last_maintenance = time.monotonic()
    try:
        while True:
            time.sleep(0.5)
            now = time.monotonic()
            if now - last_maintenance >= 3600:
                logger.info("🪵 Etat Horaire")
                log_event_queue()
                locks = LOCK_MGR.get_all_locks()
                logger.info("🔒 Locks actifs : %d", len(locks))
                for key, ts in locks.items():
                    age = int(time.time() - ts)  # ts = epoch seconds
                    logger.info("  - %s | actif depuis %d s", key, age)
                logger.info("🧹 Purge des locks expirés (timeout=7200s)")
                LOCK_MGR.purge_expired(timeout=7200)
                last_maintenance = now
    except KeyboardInterrupt:
        logger.info("Arrêt demandé (CTRL+C).")
    finally:
        observer.stop()
        observer.join(timeout=10)
        if worker.is_alive():
            logger.info("Arrêt du worker de queue…")
        logger.info("Watcher arrêté proprement.")


class NoteHandler(FileSystemEventHandler):
    """Émet des payloads normalisés dans la queue à partir des événements FS."""

    def __init__(
        self, *, logger: Optional[LoggerProtocol], debounce_window: float
    ) -> None:
        self._logger = logger
        self._debounce_window = WATCHDOG_DEBOUNCE_WINDOW
        self._last_event: Dict[Tuple[str, str], float] = {}

    # ---- helpers ---------------------------------------------------------------

    @staticmethod
    def _is_hidden_or_temp(path: str) -> bool:
        parts = path.split(os.sep)
        if any(p.startswith(".") for p in parts):
            return True
        basename = parts[-1] if parts else path
        return basename.endswith(("~", ".swp", ".tmp"))

    def _should_emit(self, path: str, action: str, etype: str) -> bool:
        """Anti-rafale: évite les doublons dans une fenêtre courte."""
        key = (path, f"{action}:{etype}")
        now = time.monotonic()
        last = self._last_event.get(key, 0.0)
        if now - last < self._debounce_window:
            return False
        self._last_event[key] = now
        return True

    # ---- events ---------------------------------------------------------------

    def on_created(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if self._is_hidden_or_temp(event.src_path):
            return
        etype = "directory" if event.is_directory else "file"
        path = normalize_full_path(event.src_path)
        if self._should_emit(path, "created", etype):
            if self._logger is not None:
                self._logger.info("[CREATION] %s → %s", etype.upper(), path)
            enqueue_event({"type": etype, "action": "created", "path": path})

    def on_deleted(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if self._is_hidden_or_temp(event.src_path):
            return
        etype = "directory" if event.is_directory else "file"
        path = normalize_full_path(event.src_path)
        if self._should_emit(path, "deleted", etype):
            if self._logger is not None:
                self._logger.info("[SUPPRESSION] %s → %s", etype.upper(), path)
            enqueue_event({"type": etype, "action": "deleted", "path": path})

    def on_modified(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if event.is_directory or self._is_hidden_or_temp(event.src_path):
            return
        etype = "file"
        path = normalize_full_path(event.src_path)
        if self._should_emit(path, "modified", etype):
            if self._logger is not None:
                self._logger.info("[MODIFICATION] FILE → %s", path)
            enqueue_event({"type": "file", "action": "modified", "path": path})

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore[override]
        if self._is_hidden_or_temp(event.src_path) or self._is_hidden_or_temp(
            event.dest_path
        ):
            return
        etype = "directory" if event.is_directory else "file"
        src = normalize_full_path(event.src_path)
        dst = normalize_full_path(event.dest_path)
        if self._should_emit(dst, "moved", etype):
            if self._logger is not None:
                self._logger.info(
                    "[DEPLACEMENT] %s → %s -> %s", etype.upper(), src, dst
                )
                enqueue_event(
                    {"type": etype, "action": "moved", "src_path": src, "path": dst}
                )
