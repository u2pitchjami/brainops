from queue import Queue
from logger_setup import setup_logger
import logging
import os
import time
import re
import yaml

setup_logger("process_queue", logging.DEBUG)
logger = logging.getLogger("process_queue")

# Création de la file d'attente unique
event_queue = Queue()

def wait_for_file(file_path, timeout=3):
    """Attend que le fichier existe avant de le traiter"""
    start_time = time.time()
    while not os.path.exists(file_path):
        if time.time() - start_time > timeout:
            return False  # Fichier toujours absent après le timeout
        time.sleep(0.5)  # Vérifie toutes les 0.5 sec

    return True
def test_note_id(file_path):
    
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    test_note_id = None
    yaml_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)

    if yaml_match:
        metadata = yaml.safe_load(yaml_match.group(1)) or {}

        yaml_note_id = metadata.get("note_id")
        if yaml_note_id:
            logger.debug(f"🔍 [DEBUG] note_id présent")
            return True

        logger.debug(f"🔍 [DEBUG] pas de note_id ")
    logger.debug(f"🔍 [DEBUG] pas d'entête) ")
    
def process_queue():
    from handlers.start.process_single_note import process_single_note, resume_import_normal, resume_import_synthesis
    from handlers.start.process_note_event import process_note_event
    from handlers.start.process_folder_event import process_folder_event

    while True:
        try:
            event = event_queue.get()
            logger.debug(f"[DEBUG] ===== PROCESS QUEUE EVENT RECUP : {event}")
            file_path = event.get("path")
            # Vérifier si le fichier existe
            if not wait_for_file(file_path) and (event['action'] != "deleted"):
                logger.warning(f"⚠️ Fichier introuvable, suppression de l'événement : {file_path}")
                continue  # Passe à l'événement suivant sans erreur

            # Si le fichier existe, on l'ajoute en file d'attente réelle
            logger.debug(f"✅ Fichier détecté, traitement en cours : {file_path}")
            if event['type'] == 'file':
                if event['action'] in ['deleted']:
                    logger.debug(f"[DEBUG] ===== Event deleted")
                    process_note_event(event)
                    continue
                    
                logger.debug(f"[DEBUG] ===== Test Note_ID")
                if not test_note_id(file_path):
                    note_id = process_note_event(event)  # 🔥 Gère les événements des notes
                    
                if event['action'] in ['created', 'modified']:
                    logger.debug(f"[DEBUG] ===== Event created, modified")
                        
                    note_id = process_note_event(event)  # 🔥 Gère les événements des notes
                    if note_id:
                        process_single_note(event['path'], note_id)
                    else:
                        logger.warning(f"[⚠️] Aucun note_id retourné pour {event['path']}")
                    
                elif event['action'] == 'moved':
                    logger.debug(f"[DEBUG] ===== Event moved")
                    
                    note_id = process_note_event({'path': event["path"], 'src_path': event["src_path"], 'action': 'moved'})
                    logger.debug(f"[DEBUG] Sortie process_note_event moved note_id : {note_id}")
                    if note_id:
                        process_single_note(event['path'], note_id, event['src_path'])
                    else:
                        logger.warning(f"[⚠️] Aucun note_id retourné pour {event['path']}")
                elif event["action"] == "resume_import_normal":
                    logger.debug(f"[DEBUG] ===== resume_import_normal")
                    resume_import_normal(event["path"], event["category"], event["subcategory"])
                    
                elif event["action"] == "resume_import_synthesis":
                    logger.debug(f"[DEBUG] ===== resume_import_synthesis")
                    resume_import_synthesis(event["path"], event["category"], event["subcategory"])

            elif event['type'] == 'directory':
                if event['action'] == 'moved':
                    # ⚡ Traite le déplacement en une seule transaction
                    process_folder_event({'action': 'created', 'path': event['path']})
                    process_folder_event({'action': 'deleted', 'path': event['src_path']})
                else:
                    process_folder_event(event)

            if event:
                logger.debug("[DEBUG] L'événement est bien détecté, traitement en cours...")
            else:
                logger.error("[ERREUR] Event vide récupéré, suppression forcée.")
            
            log_event_queue()
            event_queue.task_done()
        except Exception as e:
            logger.error(f"[ERREUR] Erreur dans le traitement de la file d'attente : {e}")
            #time.sleep(1)  # Attente pour éviter une boucle infinie en cas d'erreur


def log_event_queue():
    """Affiche le contenu de la file d'attente"""
    logger.debug(f"[DEBUG] Contenu de la file d'attente : {list(event_queue.queue)}")
