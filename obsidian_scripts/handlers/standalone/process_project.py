from handlers.utils.extract_yaml_header import extract_yaml_header
from logger_setup import setup_logger
import logging
from pathlib import Path
import shutil
import os

setup_logger("obsidian_notes:process_project", logging.INFO)
logger = logging.getLogger("obsidian_notes:process_project")

base_path = os.getenv('BASE_PATH')
project_path = os.getenv('PROJECT_PATH')

def scan_notes_and_update_projects(file):
    """
    Vérifie si un fichier a une ligne `project:` dans son entête YAML
    et met à jour la note globale correspondante.
    """
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()

    # Extraction de l'entête YAML
    header_lines, _ = extract_yaml_header(content)

    # Rechercher la ligne `project:`
    project_field = None
    for line in header_lines:
        if line.strip().startswith("project:"):
            # Récupère la valeur après `project:`
            project_field = line.split(":", 1)[1].strip()
            break

    if project_field:
        # Gestion des projets multiples (séparés par des virgules ou des espaces)
        projects = [p.strip() for p in project_field.split(",")]

        for project_name in projects:
            # Génère le chemin vers la note globale du projet
            project_file = os.path.join(project_path, f"{project_name}.md")

            # Crée un lien relatif vers la note actuelle
            relative_path = os.path.relpath(file, project_path)
            link = f"- [[{relative_path}]]\n"

            # Ajoute le lien à la note globale du projet
            update_project_note(project_file, link)
    else:
        logger.info(f"Aucun champ `project` trouvé dans : {file}")

def update_project_note(project_file, link):
    """
    Met à jour la note globale du projet en ajoutant un lien vers une note.
    """
    if not os.path.exists(project_file):
        # Si la note n'existe pas encore, la créer
        with open(project_file, "w", encoding="utf-8") as f:
            f.write(f"# Notes pour le projet : {os.path.basename(project_file).replace('.md', '')}\n\n")
    
    # Vérifier si le lien est déjà présent
    with open(project_file, "r", encoding="utf-8") as f:
        content = f.read()

    if link not in content:
        # Ajouter le lien à la note globale du projet
        with open(project_file, "a", encoding="utf-8") as f:
            f.write(link)

        print(f"Lien ajouté à {project_file} : {link.strip()}")
