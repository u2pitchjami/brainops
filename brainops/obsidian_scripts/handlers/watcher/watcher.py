from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timezone
import time
from logging.handlers import TimedRotatingFileHandler
from brainops.obsidian_scripts.handlers.utils.normalization import normalize_full_path
from brainops.obsidian_scripts.handlers.watcher.queue_manager import process_queue, enqueue_event, log_event_queue
from brainops.obsidian_scripts.handlers.watcher.queue_utils import PendingNoteLockManager
import os
import logging


logger = logging.getLogger("obsidian_notes." + __name__)
lock_mgr = PendingNoteLockManager()

obsidian_notes_folder = os.getenv('BASE_PATH')
print(f"🔍 BASE_PATH défini comme : {obsidian_notes_folder}")
# Lancement du watcher pour surveiller les modifications dans le dossier Obsidian
def start_watcher() -> None:
    last_purge = time.time()
    path = obsidian_notes_folder
    observer = PollingObserver()
    observer.schedule(NoteHandler(), path, recursive=True)
    observer.start()
    logger.info(f"[INFO] Démarrage du script, actif sur : {obsidian_notes_folder}")
        
    try:
        process_queue()  # Lancement de la boucle de traitement de la file d’attente
    except KeyboardInterrupt:
        observer.stop()
    
    
    observer.join()
    
    last_rollover_date = datetime.now().date()
   
    while True:
        today = datetime.now().date()
        now = time.time()
        # 🔁 Purge + log toutes les heures
        if now - last_purge > 3600:
            logger.info(f"[INFO] - 🪵 Etat Horaire : ")
            log_event_queue
            # 🪵 Log du détail des locks restants
            locks = lock_mgr.get_all_locks()
            logger.info(f"[INFO] 🔒 Locks actifs : {len(locks)}")
            for key, ts in locks.items():
                age = int(now - ts)
                logger.info(f"  - {key} | actif depuis {age} secondes")
                
            logger.info("[MAINTENANCE] Lancement de la purge des locks expirés (timeout=7200s)")
            lock_mgr.purge_expired(timeout=7200)
            
            last_purge = now
        if today != last_rollover_date:
            for handler in logger.handlers:
                if isinstance(handler, TimedRotatingFileHandler):
                    logger.info("🌀 Rollover log déclenché automatiquement dans watcher.")
                    handler.doRollover()
            last_rollover_date = today

class NoteHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not self.is_hidden(event.src_path):
            event_type = 'directory' if event.is_directory else 'file'
            logger.info(f"[INFO] [CREATION] {event_type.upper()} → {event.src_path}")
            
            enqueue_event({'type': event_type, 'action': 'created', 'path': normalize_full_path(event.src_path)})
            
            
    def on_deleted(self, event):
        if not self.is_hidden(event.src_path):
            event_type = 'directory' if event.is_directory else 'file'
            logger.info(f"[INFO] [SUPPRESSION] {event_type.upper()} → {event.src_path}")
            
            enqueue_event({'type': event_type, 'action': 'deleted', 'path': normalize_full_path(event.src_path)})

    def on_modified(self, event):
        if not event.is_directory and not self.is_hidden(event.src_path):
            logger.info(f"[INFO] [MODIFICATION] FILE → {event.src_path}")
            
            enqueue_event({'type': 'file', 'action': 'modified', 'path': normalize_full_path(event.src_path)})

    def on_moved(self, event):
        if not self.is_hidden(event.src_path) and not self.is_hidden(event.dest_path):
            event_type = 'directory' if event.is_directory else 'file'
            logger.info(f"[INFO] [DÉPLACEMENT] {event_type.upper()} → {event.src_path} -> {event.dest_path}")
            
            # ⚡ Ajout en file d’attente pour un traitement structuré
            enqueue_event({
                'type': event_type,
                'action': 'moved',
                'src_path': normalize_full_path(event.src_path),
                'path': normalize_full_path(event.dest_path)
            })

    @staticmethod
    def is_hidden(path):
        return any(part.startswith('.') for part in path.split(os.sep))
