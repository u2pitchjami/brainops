import logging

from brainops.obsidian_scripts.handlers.sql.db_connection import get_db_connection
from brainops.obsidian_scripts.handlers.sql.db_utils import safe_execute

# setup_logger("db_categs_utils", logging.DEBUG)
logger = logging.getLogger("db_categs_utils")


def categ_extract(base_folder):
    """
    Extrait la catégorie et sous-catégorie d'une note selon son emplacement.

    Utilise MySQL au lieu de note_paths.json.
    """
    logger.debug("entrée categ_extract pour : %s", base_folder)
    base_folder = str(base_folder)
    conn = get_db_connection()
    if not conn:
        return None, None
    cursor = conn.cursor()

    # 🔹 Récupérer les `category_id` et `subcategory_id` depuis `obsidian_folders`
    result = safe_execute(
        cursor,
        "SELECT category_id, subcategory_id FROM obsidian_folders WHERE path = %s",
        (base_folder,),
    ).fetchone()

    if not result:
        logger.warning(
            "[WARN] Aucun dossier correspondant trouvé pour : %s", base_folder
        )
        conn.close()
        return None, None

    category_id, subcategory_id = result
    category_name = subcategory_name = None

    # 🔹 Convertir `category_id` et `subcategory_id` en noms de catégories
    if category_id:
        result = safe_execute(
            cursor, "SELECT name FROM obsidian_categories WHERE id = %s", (category_id,)
        ).fetchone()
        category_name = result[0] if result else None

    if subcategory_id:
        result = safe_execute(
            cursor,
            "SELECT name FROM obsidian_categories WHERE id = %s",
            (subcategory_id,),
        ).fetchone()
        subcategory_name = result[0] if result else None

    conn.close()

    logger.debug(
        "[DEBUG] Dossier trouvé - Catégorie: %s, Sous-catégorie: %s",
        category_name,
        subcategory_name,
    )
    return category_name, subcategory_name, category_id, subcategory_id


def get_prompt_name(category, subcategory=None):
    """
    Récupère le nom du prompt basé sur la catégorie et la sous-catégorie depuis MySQL.
    """
    logger.debug(
        "[DEBUG] get_prompt_name() pour catégorie: %s, sous-catégorie: %s",
        category,
        subcategory,
    )
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()

    # 🔹 Vérifier d'abord si la sous-catégorie a un `prompt_name`
    if subcategory:
        result = safe_execute(
            cursor,
            "SELECT prompt_name FROM obsidian_categories WHERE name = %s AND\
                parent_id = (SELECT id FROM obsidian_categories WHERE name = %s LIMIT 1) LIMIT 1",
            (subcategory, category),
        ).fetchone()

        if result and result[0]:
            conn.close()
            return result[0]

    # 🔹 Si pas de `prompt_name` pour la sous-catégorie, récupérer celui de la catégorie
    result = safe_execute(
        cursor,
        "SELECT prompt_name FROM obsidian_categories WHERE name = %s AND parent_id IS NULL LIMIT 1",
        (category,),
    ).fetchone()

    conn.close()

    return result[0] if result else None


def generate_classification_dictionary():
    """
    Génère la section 'Classification Dictionary' du prompt à partir de la base MySQL.

    :return: Texte formaté pour le dictionnaire
    """
    conn = get_db_connection()
    if not conn:
        return ""
    cursor = conn.cursor(dictionary=True)

    logger.debug("[DEBUG] generate_classification_dictionary")
    classification_dict = "Classification Dictionary:\n"

    # 🔹 Récupérer toutes les catégories et sous-catégories
    cursor.execute(
        "SELECT id, name, description FROM obsidian_categories WHERE parent_id IS NULL"
    )
    categories = cursor.fetchall()

    for category in categories:
        description = category["description"] or "No description available."
        classification_dict += f'- "{category["name"]}": {description}\n'

        # 🔹 Récupérer les sous-catégories associées
        cursor.execute(
            "SELECT name, description FROM obsidian_categories WHERE parent_id = %s",
            (category["id"],),
        )
        subcategories = cursor.fetchall()

        for subcategory in subcategories:
            sub_description = subcategory["description"] or "No description available."
            classification_dict += f'  - "{subcategory["name"]}": {sub_description}\n'

    conn.close()
    return classification_dict


def generate_optional_subcategories():
    """
    Génère uniquement la liste des sous-catégories disponibles, en excluant les catégories sans sous-catégories.

    :return: Texte formaté avec les sous-catégories optionnelles.
    """
    conn = get_db_connection()
    if not conn:
        return ""
    cursor = conn.cursor(dictionary=True)

    logger.debug("[DEBUG] generate_optional_subcategories")
    subcateg_dict = "Optional Subcategories:\n"

    # 🔹 Récupérer toutes les catégories ayant des sous-catégories
    cursor.execute(
        """
        SELECT c1.name AS category_name, c2.name AS subcategory_name
        FROM obsidian_categories c1
        JOIN obsidian_categories c2 ON c1.id = c2.parent_id
        ORDER BY c1.name, c2.name
    """
    )
    results = cursor.fetchall()

    # 🔹 Organisation des données
    categories_with_subcategories = {}
    for row in results:
        category = row["category_name"]
        subcategory = row["subcategory_name"]

        if category not in categories_with_subcategories:
            categories_with_subcategories[category] = []
        categories_with_subcategories[category].append(subcategory)

    # 🔹 Construire le dictionnaire final
    for category, subcategories in categories_with_subcategories.items():
        subcateg_dict += f'- "{category}": {", ".join(sorted(subcategories))}\n'

    conn.close()
    return subcateg_dict if subcateg_dict != "Optional Subcategories:\n" else ""


def generate_categ_dictionary():
    """
    Génère la liste de toutes les catégories avec leurs descriptions, qu'elles aient des sous-catégories ou non.

    :return: Texte formaté avec toutes les catégories.
    """
    conn = get_db_connection()
    if not conn:
        return ""
    cursor = conn.cursor(dictionary=True)

    logger.debug("[DEBUG] generate_categ_dictionary")
    categ_dict = "Categ Dictionary:\n"

    # 🔹 Récupérer toutes les catégories
    cursor.execute(
        "SELECT name, description FROM obsidian_categories WHERE parent_id IS NULL"
    )
    categories = cursor.fetchall()

    for category in categories:
        explanation = category["description"] or "No description available."
        categ_dict += f'- "{category["name"]}": {explanation}\n'

    conn.close()
    return categ_dict


def get_or_create_category(name: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()

    result = safe_execute(
        cursor,
        "SELECT id FROM obsidian_categories WHERE name = %s AND parent_id IS NULL",
        (name,),
    ).fetchone()

    if result:
        conn.close()
        return result[0]

    cursor.execute(
        """
        INSERT INTO obsidian_categories (name, description, prompt_name)
        VALUES (%s, %s, %s)
    """,
        (name, f"Note about {name}", "divers"),
    )

    conn.commit()
    category_id = cursor.lastrowid
    conn.close()

    return category_id


def get_or_create_subcategory(name: str, parent_id: int) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()

    result = safe_execute(
        cursor,
        "SELECT id FROM obsidian_categories WHERE name = %s AND parent_id = %s",
        (name, parent_id),
    ).fetchone()

    if result:
        conn.close()
        return result[0]

    cursor.execute(
        """
        INSERT INTO obsidian_categories (name, parent_id, description, prompt_name)
        VALUES (%s, %s, %s, %s)
    """,
        (name, parent_id, f"Note about {name}", "divers"),
    )

    conn.commit()
    subcategory_id = cursor.lastrowid
    conn.close()

    return subcategory_id


def remove_unused_category(category_id: int) -> bool:
    """
    Supprime une catégorie si elle n'est plus utilisée par aucun dossier.

    Retourne True si la catégorie a été supprimée, False sinon.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM obsidian_folders WHERE category_id = %s",
            (category_id,),
        )
        count = cursor.fetchone()[0]

        if count == 0:
            cursor.execute(
                "DELETE FROM obsidian_categories WHERE id = %s", (category_id,)
            )
            conn.commit()
            logger.info(
                f"[CLEAN] Catégorie ID {category_id} supprimée car plus utilisée."
            )
            return True
        else:
            logger.debug(
                f"[CLEAN] Catégorie ID {category_id} conservée (encore utilisée)."
            )
            return False

    except Exception as e:
        logger.error(f"[ERROR] remove_unused_category({category_id}) : {e}")
        return False

    finally:
        if conn:
            conn.close()
