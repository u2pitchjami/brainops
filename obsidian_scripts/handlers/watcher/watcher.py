from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timezone
from handlers.utils.normalization import normalize_full_path
from handlers.watcher.queue_manager import process_queue, enqueue_event
import os
from logger_setup import setup_logger
import logging

print("setup_logger watcher")
setup_logger("watcher", logging.INFO)
logger = logging.getLogger("watcher")

obsidian_notes_folder = os.getenv('BASE_PATH')
print(f"🔍 BASE_PATH défini comme : {obsidian_notes_folder}")
# Lancement du watcher pour surveiller les modifications dans le dossier Obsidian
def start_watcher():
    path = obsidian_notes_folder
    observer = PollingObserver()
    observer.schedule(NoteHandler(), path, recursive=True)
    observer.start()
    logger.info(f"[INFO] Démarrage du script, actif sur : {obsidian_notes_folder}")
    print("Watcher démarré à :", datetime.now(timezone.utc))
    
    try:
        process_queue()  # Lancement de la boucle de traitement de la file d’attente
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

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
