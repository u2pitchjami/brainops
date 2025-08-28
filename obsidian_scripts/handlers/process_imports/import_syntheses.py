from brainops.obsidian_scripts.handlers.ollama.ollama_utils import large_or_standard_note
from brainops.obsidian_scripts.handlers.process.embeddings_utils import make_embeddings_synthesis
from brainops.obsidian_scripts.handlers.process.divers import copy_to_archive
from brainops.obsidian_scripts.handlers.header.extract_yaml_header import extract_yaml_header
from brainops.obsidian_scripts.handlers.process.headers import make_properties
from brainops.obsidian_scripts.handlers.sql.db_get_linked_notes_utils import get_subcategory_prompt, get_note_lang, get_parent_id, get_file_path
from brainops.obsidian_scripts.handlers.utils.files import safe_write, join_yaml_and_body
from brainops.obsidian_scripts.handlers.utils.divers import make_relative_link, prompt_name_and_model_selection
from brainops.obsidian_scripts.handlers.utils.normalization import clean_fake_code_blocks
import logging
import os

logger = logging.getLogger("obsidian_notes." + __name__)

def process_import_syntheses(filepath, note_id):
    logger.info(f"[INFO] Génération de la synthèse pour : {filepath}")
    logger.debug(f"[DEBUG] +++ ▶️ SYNTHESE pour {filepath}")
    try:
        parent_id = None
        parent_id = get_parent_id(note_id)
        if not parent_id:
            logger.debug(f"[DEBUG] process_import_syntheses lancement copy_to_archives")
            archive_path = copy_to_archive(filepath, note_id)
            final_response = make_embeddings_synthesis(note_id, filepath)
        else:
            archive_path = get_file_path(parent_id)
            final_response = make_embeddings_synthesis(note_id, archive_path)
        
        original_path = make_relative_link(archive_path, filepath)
        logger.debug(f"[DEBUG] process_import_syntheses : original_path {original_path}")
        
        logger.debug(f"[DEBUG] Génération du glossaire")
        glossary = None
        glossary = make_glossary(archive_path, note_id)
              
        logger.debug("[DEBUG] process Add_questions")
        questions = make_questions(filepath=archive_path, note_id=note_id, content=final_response)
        logger.debug(f"[DEBUG] questions : {questions}")
        
        translate_synth = None
        if get_note_lang(note_id) != "fr":
            logger.debug("[DEBUG] Translate")
            translate_synth =make_translate(filepath, note_id)
        
        logger.debug("[DEBUG] process : Make_syntheses")
        make_syntheses(filepath=filepath, note_id=note_id, original_path=original_path, translate_synth=translate_synth, glossary=glossary, questions=questions, content_lines=final_response)        
        logger.debug(f"[DEBUG] process_import_syntheses : envoi vers make_properties {filepath} ")
        make_properties(filepath, note_id, status = "synthesis")
        logger.debug(f"[DEBUG] === ⏹️ FIN SYNTHESE pour {filepath}")
        logger.info(f"[INFO] Synthèse terminée pour {filepath}")
        return
    except Exception as e:
        print(f"[ERREUR] Impossible de traiter {filepath} : {e}")    

def make_translate(filepath, note_id):
    prompt_key = "synth_translate" 
    translate_synth = large_or_standard_note(
        filepath=filepath, 
        source="synth_translate", 
        process_mode="standard_note", 
        prompt_key=prompt_key, 
        note_id=note_id, 
        write_file=False
        )
    return translate_synth

def make_questions(filepath, note_id, content):
    prompt_key = "add_questions"
    questions = large_or_standard_note(
        filepath=filepath,
        content=content, 
        source="add_questions", 
        process_mode="standard_note", 
        prompt_key=prompt_key, 
        note_id=note_id, 
        write_file=False
        )
    return questions

def make_glossary(filepath, note_id):
    prompt_key = "glossaires"

    glossary_sections = large_or_standard_note(
        filepath=filepath,
        note_id=note_id,
        source="glossary",
        process_mode="large_note",
        prompt_key=prompt_key,
        write_file=False
    )
    if not glossary_sections:
        logger.error("[ERREUR] Glossaire initial vide. Abandon du regroupement.")
        return ""

    logger.debug(f"[DEBUG] Glossaire brut : {glossary_sections[:500]}...")

    prompt_key = "glossaires_regroup"
    final_glossary = large_or_standard_note(
        filepath=filepath,
        note_id=note_id,
        content=glossary_sections,
        source="glossary_regroup",
        process_mode="standard_note",
        prompt_key=prompt_key,
        write_file=False
    )

    logger.debug(f"[DEBUG] Glossaire regroupé : {final_glossary[:500]}...")

    return final_glossary

        
def make_syntheses(filepath: str, note_id: str, original_path, translate_synth=None, glossary=None, questions=None, header_lines=None, content_lines=None):
    logger.debug(f"[DEBUG] Démarrage de make_syntheses pour {filepath}")

    try:
        if not content_lines and header_lines:
            # Lecture + séparation header / contenu
            header_lines, content_lines = extract_yaml_header(filepath)
        elif not header_lines:
            header_lines, _ = extract_yaml_header(filepath)    
                
        # Construction du lien vers la note originale
        original_link = f"[[{original_path}|Voir la note originale]]"
        logger.debug(f"[DEBUG] Lien original : {original_link}")

        # Construction du glossaire et de la traduction
        translate_synth = format_optional_block("Traduction française", translate_synth)
        logger.debug(f"[DEBUG] translate_synth : {translate_synth[:2000]}")
        glossary = format_optional_block("Glossaire", glossary)
        logger.debug(f"[DEBUG] glossary : {glossary[:2000]}")
        questions = format_optional_block("Questions", questions)
        logger.debug(f"[DEBUG] questions : {questions[:2000]}")
        # Recomposition du contenu final
        if translate_synth:
            body_content = f"{original_link}\n\n{content_lines.strip()}\n\n---\n\n{translate_synth}\n\n---\n\n{glossary}\n\n---\n\n{questions}"
        else:
            body_content = f"{original_link}\n\n{content_lines.strip()}\n\n---\n\n{glossary}\n\n---\n\n{questions}"
        
        final_body_content = clean_fake_code_blocks(body_content)
        final_content = join_yaml_and_body(header_lines, final_body_content)
        logger.debug(f"[DEBUG] Contenu final généré : {final_content}...")

        # Écriture du fichier
        success = safe_write(filepath, content=final_content)
        if not success:
            logger.error(f"[ERROR] Échec de l’écriture du fichier : {filepath}")
            return

        logger.info(f"[INFO] Note synthétisée enregistrée : {filepath}")
    except Exception as e:
        logger.exception(f"[ERREUR] Échec dans make_syntheses pour {filepath} : {e}")
   
def format_optional_block(title: str, content: str | None) -> str:
    """Ajoute un titre markdown si le contenu est présent et non vide"""
    if content and content.strip():
        return f"## {title}\n\n{content.strip()}"
    return ""
