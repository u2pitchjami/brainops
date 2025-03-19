from queue import Queue
from logger_setup import setup_logger
import logging
import os
import time
import re
import yaml
from handlers.utils.sql_helpers import file_path_exists_in_db

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

def test_title(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        yaml_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        
        if yaml_match:
            yaml_content = yaml_match.group(1)
            body_content = content[len(yaml_match.group(0)):]

            # 🔍 Extraction du `note_id`
            note_id_match = re.search(r"^note_id:\s*(.+)", yaml_content, re.MULTILINE)
            note_id = note_id_match.group(1).strip() if note_id_match else None

            # 🔍 Extraction et correction du `title`
            title_match = re.search(r"^title:\s*(.+)", yaml_content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else None

            if title:
                # Remplacement du titre directement dans le fichier
                corrected_yaml_content = re.sub(r'^(title:\s*)(.+)$', lambda m: f"{m.group(1)}{m.group(2).replace(':', ' ')}", yaml_content, flags=re.MULTILINE)

                # Vérifie si une correction a été faite avant d'écrire
                if corrected_yaml_content != yaml_content:
                    with open(file_path, "w", encoding="utf-8") as file:
                        file.write(f"---\n{corrected_yaml_content}\n---\n{body_content}")
                    logger.info(f"💾 [INFO] Fichier corrigé : {file_path}")

            # if note_id:
            #     logger.debug(f"🔍 [DEBUG] note_id trouvé: {note_id}")
            #     return True

            # logger.debug(f"🔍 [DEBUG] pas de note_id ")

    except Exception as e:
        logger.error(f"❌ [ERREUR] Erreur dans test_note_id : {e}")

    #return False  # Retourne False par défaut si pas de note_id
    
def process_queue():
    from handlers.start.process_single_note import process_single_note, resume_import_normal, resume_import_synthesis
    from handlers.start.process_note_event import process_note_event
    from handlers.start.process_folder_event import process_folder_event

    while True:
        try:
            event = event_queue.get()
            logger.debug(f"[DEBUG] ===== PROCESS QUEUE EVENT RECUP : {event}")
            file_path = event.get("path")
            trigger = True
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
                test_title(file_path)
                if not file_path_exists_in_db(str(file_path)):
                    event["action"] = "created"
                    note_id = process_note_event(event)  # 🔥 Gère les événements des notes
                    trigger = False
                    
                if event['action'] in ['created', 'modified']:
                    logger.debug(f"[DEBUG] ===== Event created, modified")
                    if trigger:    
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
