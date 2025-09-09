"""
Utils for queue.
"""

# watcher/queue_utils.py
from __future__ import annotations

import threading
import time

from brainops.utils.logger import get_logger

logger = get_logger("Brainops Watcher")


def get_lock_key(note_id: int | None, file_path: str | None) -> str:
    """
    Génère une clé de verrou logique.

    Priorise l'identifiant de note quand disponible, sinon le chemin.
    """
    if note_id is not None:
        return f"note:{note_id}"
    return f"path:{file_path!s}"


class PendingNoteLockManager:
    """
    Verrous logiques pour empêcher des traitements concurrents sur la même note/fichier.

    Chaque lock est horodaté pour permettre une purge.
    """

    def __init__(self) -> None:
        """
        __init__ _summary_

        _extended_summary_
        """
        self._locks: dict[str, int] = {}
        self._lock = threading.Lock()
        self._logger = logger

    def acquire(self, key: str) -> bool:
        """
        Pose un verrou atomiquement.

        Retourne False si déjà verrouillé.
        """
        with self._lock:
            if key in self._locks:
                return False
            self._locks[key] = int(time.time())
            return True

    def release(self, key: str) -> None:
        """
        Libère le verrou s’il existe.
        """
        with self._lock:
            if key in self._locks:
                del self._locks[key]

    def is_locked(self, key: str) -> bool:
        """
        Indique si la clé est verrouillée.
        """
        with self._lock:
            return key in self._locks

    def purge_expired(self, timeout: int = 7200) -> None:
        """
        Supprime les verrous plus vieux que `timeout` secondes.
        """
        now = int(time.time())
        with self._lock:
            expired = [k for k, t in self._locks.items() if now - t > timeout]
            for k in expired:
                del self._locks[k]
                if self._logger is not None:
                    self._logger.warning("[LOCK] 🔥 Lock expiré supprimé : %s", k)

    def count(self) -> int:
        """
        Nombre de verrous actifs.
        """
        with self._lock:
            return len(self._locks)

    def get_all_locks(self) -> dict[str, int]:
        """
        Copie des verrous actifs (clé → timestamp).
        """
        with self._lock:
            return dict(self._locks)
