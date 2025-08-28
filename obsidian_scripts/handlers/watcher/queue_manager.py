from queue import Queue
import logging
from threading import Lock
from brainops.obsidian_scripts.handlers.sql.db_notes_utils import file_path_exists_in_db
from brainops.obsidian_scripts.handlers.sql.db_notes import delete_note_from_db
from brainops.obsidian_scripts.handlers.header.yaml_read import test_title
from brainops.obsidian_scripts.handlers.process.new_note import new_note
from brainops.obsidian_scripts.handlers.process.update_note import update_note
from brainops.obsidian_scripts.handlers.utils.files import wait_for_file
from brainops.obsidian_scripts.handlers.watcher.queue_utils import PendingNoteLockManager, get_lock_key

logger = logging.getLogger("obsidian_notes." + __name__)
# Création de la file d'attente unique
event_queue = Queue()
pending_note_ids = set()
pending_lock = Lock()
lock_mgr = PendingNoteLockManager()

def enqueue_event(event) -> None:
    if event['type'] == 'file':
        note_id = None
        file_path = event.get("path")
        src_path = event.get("src_path")
        logger.debug(f"[CHECK] Enrichi note_id: {note_id}, set: {pending_note_ids}, key_type: {type(note_id)}")
        note_id = file_path_exists_in_db(file_path, src_path)

        event["note_id"] = note_id  # enrichit l’event dynamiquement

        key = get_lock_key(note_id, file_path)

        if not lock_mgr.acquire(key):
            logger.debug(f"[QUEUE] 🚫 Ignoré, déjà en file : {key}")
            return

    event_queue.put(event)
   
def process_queue() -> None:
    from brainops.obsidian_scripts.handlers.start.process_single_note import process_single_note
    from brainops.obsidian_scripts.handlers.start.process_folder_event import process_folder_event
    
    log_event_queue()
    while True:
        try:
            psn = None
            note_id = None
            event = event_queue.get()
            logger.debug(f"[DEBUG] ===== PROCESS QUEUE EVENT RECUP : {event}")
            file_path = event.get("path")
            src_path = event.get("src_path")
            
            # Vérifier si le fichier existe
            if not wait_for_file(file_path) and (event['action'] != "deleted"):
                logger.warning(f"⚠️ Fichier introuvable, suppression de l'événement : {file_path}")
                continue  # Passe à l'événement suivant sans erreur

            # Si le fichier existe, on l'ajoute en file d'attente réelle
            logger.debug(f"✅ Fichier détecté, traitement en cours : {file_path}")
            if event['type'] == 'file':
                if event['action'] in ['deleted']:
                    logger.debug(f"[DEBUG] ===== Event deleted")
                    delete_note_from_db(file_path)
                    continue
                                                
                if not note_id:
                    note_id = file_path_exists_in_db(file_path, src_path)
                    if not note_id:
                        logger.debug(f"[DEBUG] ===== Test Title")
                        test_title(file_path)
                        logger.debug(f"[DEBUG] {file_path} innexistant dans obsidian_notes")
                        note_id = new_note(file_path)  # 🔥 Gère les événements des notes
                                                       
                if note_id:                                                                        
                    if event['action'] in ['created', 'modified']:
                        logger.debug(f"[BUSY] Notes en cours : {list(pending_note_ids)}")
                        logger.debug(f"[DEBUG] ===== Event created, modified : {event['action']}")
                        psn = process_single_note(event['path'], note_id)
                        if not psn:
                            logger.debug(f"[DEBUG] note_id : {note_id}")
                            update_note(note_id, file_path)
                        continue
                            
                    elif event['action'] == 'moved':
                        logger.debug(f"[DEBUG] ===== Event moved")
                        logger.debug(f"[BUSY] Notes en cours : {list(pending_note_ids)}")
                        process_single_note(event['path'], note_id, event['src_path'])
                        if not psn:
                            update_note(note_id, file_path, src_path)
                            logger.debug(f"[DEBUG] Sortie process_note_event moved note_id : {note_id}")
                        continue
                continue
                      
            elif event['type'] == 'directory':
                if event['action'] == 'moved':
                    # ⚡ Traite le déplacement en une seule transaction
                    logger.debug(f"📂 [DEBUG] Action: {event['action']} | Path: {event['path']}")
                    process_folder_event({'action': 'created', 'path': event['path']})
                    logger.debug(f"[DEBUG] Sortie Created, entrée Deleted")
                    process_folder_event({'action': 'deleted', 'path': event['src_path']})
                    logger.debug(f"[DEBUG] fini")
                else:
                    process_folder_event(event)

            if event:
                logger.debug(f"[DEBUG] Traitement terminé pour {event['type']} - {event['action']}")
            else:
                logger.error("[ERREUR] Event vide récupéré, suppression forcée.")
            
            log_event_queue()
            
        except Exception as e:
            logger.error(f"[ERREUR] Erreur dans le traitement de la file d'attente : {e}")
            #time.sleep(1)  # Attente pour éviter une boucle infinie en cas d'erreur
        finally:
            if event['type'] == 'file':
                key = get_lock_key(note_id, file_path)
                lock_mgr.release(key)
            event_queue.task_done()

def log_event_queue() -> None:
    """Affiche le contenu de la file d'attente"""
    logger.debug(f"[DEBUG] Contenu de la file d'attente : {list(event_queue.queue)}")
