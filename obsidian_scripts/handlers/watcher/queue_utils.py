import logging
import time
import threading

logger = logging.getLogger("obsidian_notes." + __name__)

def get_lock_key(note_id, file_path) -> str:
    """
    Génère une clé unique pour le verrouillage de traitement d'une note.
    Si le note_id est disponible, il est prioritaire.
    Sinon, on utilise le chemin du fichier comme clé temporaire.
    """
    if note_id:
        return f"note:{note_id}"
    return f"path:{str(file_path)}"


class PendingNoteLockManager:
    """
    Gère un système de verrous (locks) logiques pour éviter
    que plusieurs traitements concurrents s'exécutent sur une même note.

    Chaque clé est horodatée à l'acquisition pour permettre une purge automatique.
    """
    
    def __init__(self):
        self._locks = {}  # stocke key: timestamp
        self._lock = threading.Lock()  # protège l'accès concurrent
        
    def acquire(self, key: str) -> bool:
        """
        Tente de poser un verrou sur la clé donnée.
        Cette méthode vérifie et crée le lock de manière atomique (protégée par un verrou threading.Lock),
        donc elle NE fait PAS appel à is_locked() pour éviter tout risque de concurrence.
        """
        with self._lock:
            if key in self._locks:
                return False
            self._locks[key] = int(time.time())
            return True

    def release(self, key: str):
        """
        Libère le verrou correspondant à la clé, s’il existe.
        """
        with self._lock:
            if key in self._locks:
                del self._locks[key]

    def is_locked(self, key: str) -> bool:
        """
        Vérifie si la clé est verrouillée.
        """
        with self._lock:
            return key in self._locks

    def purge_expired(self, timeout: int = 7200) -> None:
        """
        Supprime tous les verrous ayant dépassé le délai d'expiration (en secondes).
        """
        now = int(time.time())
        with self._lock:
            expired = [k for k, t in self._locks.items() if now - t > timeout]
            for k in expired:
                del self._locks[k]
                logger.warning(f"[LOCK] 🔥 Lock expiré supprimé : {k}")

    def count(self) -> int:
        """
        Retourne le nombre de verrous actifs.
        """
        with self._lock:
            return len(self._locks)
    
    def get_all_locks(self) -> dict:
        """
        Retourne une copie des locks actifs avec leurs timestamps.
        Utile pour les logs ou l’inspection.
        """
        with self._lock:
            return self._locks.copy()
