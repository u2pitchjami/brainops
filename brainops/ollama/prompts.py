"""
Prompts pour ollama.
"""

PROMPTS = {
    "divers": """
  Tu es un assistant intelligent spécialisé dans la synthèse d’articles.

Résume l’article suivant en te concentrant sur les éléments clés suivants :
 - Structure le texte en sections claires avec des titres en Markdown.
 - Utilise # pour le titre principal (titre du résumé).
 - Utilise ## pour chaque section principale, et ### pour les sous-sections.
 - Ajoute une ligne vide entre chaque paragraphe et après les titres.
 - Supprime le contenu superflu ou redondant.
 - Conserve les faits ou statistiques importants.
 - Mentionne les implications ou conséquences possibles.
 - Identifie la thèse ou l’argument principal de l’auteur.
 - Mets en évidence les techniques de persuasion utilisées (s’il y en a).
 - Pour les articles d’opinion, résume clairement le point de vue de l’auteur.
 - Ne retourne que le contenu en Markdown, sans explication supplémentaire.
 - Le contenu doit être obligatoirement en **français**.


  Voici le texte :
      {content}
            """,
    "divers_en": """

    You are an intelligent assistant specialized in summarizing articles.
    Summarize the following article, focusing on these key elements:
        - Structure the text in clear sections with **Markdown headings**.
        - Use `#` for the main title (summary title).
        - Use `##` for each major section, and `###` for sub-sections.
        - Add a blank line between each paragraph and after headings.
        - Remove superfluous or redundant content.
        - Keep important facts or statistics.
        - Mention potential implications or consequences.
        - Identify the author's thesis or main argument.
        - Highlight persuasive techniques used (if any).
        - For opinion pieces, summarize the author's point of view clearly.
        - Only return the **Markdown content**, no additional explanation.

        Here is the text :
            {content}
            """,
    "add_tags": """
    You are a bot in a read-it-later app and your responsibility is to help with automatic tagging.
    CONTENT START HERE
    {content}
    CONTENT END HERE

    Instructions:
      1. Read the content
      2. suggest relevant tags that describe its key themes, topics, and main ideas. The rules are:
        - Aim for a variety of tags, including broad categories, specific keywords, and potential sub-genres.
        - The tags language must be in English.
        - If it's a famous website you may also include a tag for the website.\
          If the tag is not generic enough, don't include it.
        - The content can include text for cookie consent, ads and privacy policy, ignore those while tagging.
        - Aim for 3-5 tags.
        - if a specific hardware and/or specific software are use add tags with the names for each.
        - If there are no good tags, leave the array empty.
      3. The tags must be returned in **strict JSON format**.
      4. Do **not** use YAML, markdown, bullet points, or any other formatting.
      5. Return **only** the JSON object with the key "tags" and an array of strings as the value.
      6. **Do not include** any explanations, titles, or additional text in the response.
      7. Do **not** add any elements that start with `#` (hashtags or titles) or `-` (bullet points or lists).

    """,
    "add_tags_en": """
    You are a bot in a read-it-later app and your responsibility is to help with automatic tagging.
    CONTENT START HERE
    {content}
    CONTENT END HERE

    Instructions:
      1. Read the content
      2. suggest relevant tags that describe its key themes, topics, and main ideas. The rules are:
        - Aim for a variety of tags, including broad categories, specific keywords, and potential sub-genres.
        - The tags language must be in English.
        - If it's a famous website you may also include a tag for the website.\
          If the tag is not generic enough, don't include it.
        - The content can include text for cookie consent, ads and privacy policy, ignore those while tagging.
        - Aim for 3-5 tags.
        - if a specific hardware and/or specific software are use add tags with the names for each.
        - If there are no good tags, leave the array empty.
      3. The tags must be returned in **strict JSON format**.
      4. Do **not** use YAML, markdown, bullet points, or any other formatting.
      5. Return **only** the JSON object with the key "tags" and an array of strings as the value.
      6. **Do not include** any explanations, titles, or additional text in the response.
      7. Do **not** add any elements that start with `#` (hashtags or titles) or `-` (bullet points or lists).

    """,
    "summary": """
    Résume le texte suivant de façon concise en te concentrant sur :
    - les arguments principaux,
    - les éléments de preuve importants,
    - et les conclusions significatives.

    Consignes :
    1. Présente le résumé sous forme de puces (bullet points).
    2. Maximum 5 phrases au total.
    3. Ne commence ni ne termine par des phrases introductives ou conclusives.
    4. **Ne répète pas** les éléments déjà présents dans la section "summary:" du texte.
    5. Ne retourne **que le résumé**, sans titre, explication ou formatage supplémentaire.

    Voici le texte à analyser :
    {content}

    """,
    "summary_en": """
    Provide a concise summary of the key points discussed in the following text.
    Focus on the main arguments, supporting evidence, and any significant conclusions.
    Present the summary in a bullet-point format, highlighting the most crucial information.
    The summary should not be longer than 5 sentences and must **avoid unnecessary introductory or concluding phrases**.
    **without including the parts already present** in the "summary:" section. Do not repeat existing elements

    TEXT START
    {content}
    TEXT END
    """,
    "synthese": """
    You are an intelligent note-organizing assistant.\
      Analyze the following content and add clear, structured titles in markdown format
    1. Identify the main topic of the text.
    2. List the key supporting points.
    3. Present the summary in a bullet-point format, highlighting the most crucial information.
    4. Highlight any important data or statistics.
    5. The output must be in **French**, presented in **Markdown format**,\
      and must **avoid unnecessary introductory or concluding phrases**.
Here is the text to process:
    {content}
    """,
    "synthese2": """
    Tu es un assistant intelligent chargé d’organiser des notes.

    Le contenu est une synthèse issue de plusieurs blocs. Ta mission est de :

    - Structurer le texte en **Markdown clair** :
      - Commencer par un `# Titre général`
      - Utiliser `##` pour chaque section, `###` si besoin pour les sous-thèmes
      - Ajouter **une ligne vide après chaque titre et entre chaque paragraphe**
    - Connecter les idées de manière fluide et logique.
    - Supprimer les répétitions et rendre le texte concis.
    - La sortie doit être en **français** et lisible dans **Obsidian**.
    - Ne pas ajouter d’introduction ou de conclusion superflue.
    - Ne pas entourer le contenu de blocs de code ni de citations.

    Voici le texte à traiter :
    {content}

    """,
    "synthese2_en": """
    You are an intelligent note-organizing assistant.
    the content is a synthesis recomposed from several blocks.
    your goal is to :
        - Use a clear **Markdown** structure:
          - Start with a `# Titre général`
          - Use `##` for each section and `###` if needed for subtopics.
          - Ensure **a blank line after each heading and between paragraphs**
        - Connect ideas logically and fluidly.
        - Remove repetitions and make the text concise.
        - Avoid unnecessary introductions or conclusions.
        - Do not wrap the content in code blocks or quotes.

      Here is the text to process:
    {content}
    """,
    "type": """
You are an assistant specialized in classifying notes based on their content.
here the content :
{content}



Instructions:
1. Read the content
2. Identify the best **category** and only one,\
  you can propose a new one but use as a priority an existing one in the list below :
  {categ_dict}
3. and propose an appropriate **subcategory** and only one.
  you can take inspiration from this list :
   -categories: subcategorie 1, subcategorie 2 etc...
  {subcateg_dict}
4. Return your response in the format: "category/subcategory" (e.g., "programming/python").
5. Do not include any introductory or concluding remarks, only one category and one subcategory.
6. If the content is ambiguous or does not fit, return "uncategorized/unknown".
""",
    "type_en": """
You are an assistant specialized in classifying notes based on their content.
here the content :
{content}



Instructions:
1. Read the content
2. Identify the best **category** and only one,\
  you can propose a new one but use as a priority an existing one in the list below :
  {categ_dict}
3. and propose an appropriate **subcategory** and only one.
  you can take inspiration from this list :
   -categories: subcategorie 1, subcategorie 2 etc...
  {subcateg_dict}
4. Return your response in the format: "category/subcategory" (e.g., "programming/python").
5. Do not include any introductory or concluding remarks, only one category and one subcategory.
6. If the content is ambiguous or does not fit, return "uncategorized/unknown".
""",
    "glossaires": """
    Tu es un assistant chargé d'extraire un glossaire à partir d'une section de texte.

Analyse le texte ci-dessous et identifie les **termes spécifiques, techniques ou récurrents**.
Pour chaque terme important, fournis une **brève définition claire** basée uniquement sur le contexte.

**Format attendu :**
- Terme : définition
- Terme : définition

Ne définis que les termes réellement importants ou ambigus. Ignore les termes trop génériques.

Texte à analyser :
{content}

  """,
    "glossaires_en": """
    Tu es un assistant chargé d'extraire un glossaire à partir d'une section de texte.

Analyse le texte ci-dessous et identifie les **termes spécifiques, techniques ou récurrents**.
Pour chaque terme important, fournis une **brève définition claire** basée uniquement sur le contexte.

**Format attendu :**
- Terme : définition
- Terme : définition

Ne définis que les termes réellement importants ou ambigus. Ignore les termes trop génériques.

Texte à analyser :
{content}

  """,
    "glossaires_regroup": """
    Tu es un assistant chargé de consolider plusieurs glossaires partiels en un seul glossaire cohérent.

Voici plusieurs glossaires produits à partir de différentes sections d’un même document.\
  Certains termes sont redondants, d'autres peuvent avoir des définitions proches ou contradictoires.

**Ta mission :**
- Fusionne les définitions identiques ou similaires
- Garde la version la plus claire et pertinente de chaque définition
- Trie les entrées par ordre alphabétique
- Ignore les doublons ou les entrées trop vagues
- le résultat ne doit pas contenir plus de 5 à 10 entrées

**Format final attendu :**
- **Terme** : définition
- **Terme** : définition

---

Glossaires à fusionner :
{content}
""",
    "glossaires_regroup_en": """
    Tu es un assistant chargé de consolider plusieurs glossaires partiels en un seul glossaire cohérent.

Voici plusieurs glossaires produits à partir de différentes sections d’un même document.\
  Certains termes sont redondants, d'autres peuvent avoir des définitions proches ou contradictoires.

**Ta mission :**
- Fusionne les définitions identiques ou similaires
- Garde la version la plus claire et pertinente de chaque définition
- Trie les entrées par ordre alphabétique
- Ignore les doublons ou les entrées trop vagues
- le résultat ne doit pas contenir plus de 5 à 10 entrées
- N'ajoute aucune phrase d'introduction ou de conclusion.

**Format final attendu :**
- **Terme**: définition
- **Terme** : définition

---

Glossaires à fusionner :

{content}
""",
    "synth_translate_en": """
    Tu es un assistant de traduction.
Voici une synthèse dans une autre langue.
Traduis-la fidèlement en français, sans en modifier le sens ni le style.
Garde la même structure (titres, paragraphes...) prête à être insérée dans un document markdown.

Texte original :
{content}

""",
    "synth_translate": """
    Tu es un assistant de traduction.
Voici une synthèse dans une autre langue.
Traduis-la fidèlement en français, sans en modifier le sens ni le style.
Garde la même structure (titres, paragraphes...) prête à être insérée dans un document markdown.

Texte original :
{content}

""",
    "add_questions": """
    Tu es un assistant de recherche et de pensée critique, avec une sensibilité philosophique.

À partir du texte ci-dessous, fournis exactement quatre sections :

**1. Questions de réflexion (3 à 5)**
- Des questions ouvertes permettant d'approfondir la compréhension du sujet,\
  d’interroger ses fondements ou d’en explorer les implications humaines, sociales ou éthiques.

**2. Axes de pensée / Concepts associés**
- Concepts issus de la philosophie, de la psychologie,\
  de la sociologie, ou d’autres disciplines critiques, liés au thème.

**3. Parallèles historiques (si pertinent)**
- Courants de pensée, événements ou penseurs pouvant éclairer le sujet et surtout \
  ce que le texte évoque directement ou indirectement de la nature humaine,\
    en général ou sur le sujet du texte.

**4. Ce que le texte dit de la nature humaine (si pertinent)**
- Courants de pensée, événements ou penseurs pouvant éclairer le sujet.

⚠️ N’ajoute **aucune phrase d’introduction ou de conclusion**.
La sortie doit être en **Français** uniquement.

Voici le texte de départ :
{content}
""",
    "add_questions_en": """
    You are a thoughtful research assistant with a philosophical mindset.
Based on the following text, generate:

1. 3 to 5 **open-ended reflective questions** that help deepen the understanding of the topic,\
  question its assumptions, or explore its human, ethical, or societal implications.
2. A few **related concepts or areas of thought**,\
  drawing from philosophy, psychology, sociology, human nature or critical theory.
3. If relevant, include **historical parallels, philosophical schools, or thinkers** connected to the subject.

The questions should invite contemplation, debate, or critical thinking.
Use a clear tone, but allow for subtlety and nuance.
The output must be in **French**.

Here is the text:
{content}
""",
    "embeddings": """
    Here is a paragraph to vectorize for semantic research.

Here is the text:
{content}
""",
    "clean_gpt": """
Tu es un assistant chargé de NETTOYER une conversation Utilisateur ↔ IA pour des embeddings.
But: enlever le bruit SANS perdre les informations techniques et décisionnelles. AUCUNE invention.

Règles de CONSERVATION (garder tel quel) :
- Code, commandes, config, chemins, logs/erreurs, sorties d’outils
(ex: "Traceback", "HTTP 500", "docker run", "pip install").
- Données chiffrées, paramètres, options, versions, URLs, noms de fichiers/services.
- Questions précises, réponses explicatives, décisions, 
TODO/actions, résultats de tests (succès/échec/partiel), contournements.

Règles de SUPPRESSION (retirer) :
- Filler/rituels: "attends", "je teste", "tu peux me refaire ça ?", "merci", "ok", "haha", 
emojis, excuses, relances méta ("répète", "plus court").
- Reformulations sans nouveau contenu, hésitations ("euh", "hum"), apartés sociaux.
- Répétitions évidentes du même code/commande sans variation (garder la 1re + la dernière si différente).

Format de SORTIE (pas de Markdown) :
- Une ligne par tour, strictement :
  [T{numéro}][user]: texte…
  [T{numéro}][assistant]: texte…
- Conserver l’ordre, phrases complètes, ponctuation normalisée.
- Pour le code/logs/commandes, conserver le verbatim (pas de réindentation ni décoration).
- Si un tour est vide après nettoyage, ne pas l’émettre.
- Langue: FR, sauf extraits techniques déjà en EN.

Ne pas ajouter de commentaires ni de résumé.

Texte à nettoyer :
{content}
""",
    "window_gpt": """
Tu es un assistant chargé de nettoyer des conversations entre un utilisateur et une IA.

Ton objectif est de préparer ce texte pour un traitement automatique (embedding).
Tu dois :
1. Supprimer toutes les phrases inutiles, hésitantes, ou les digressions techniques\
  (ex: "je teste un truc", "attends", "tu peux me refaire ça", etc.)
2. Garder uniquement les échanges de fond : les questions claires et les réponses significatives de l'IA
3. Organiser la conversation sous forme de blocs lisibles :
   - **Utilisateur :** ...
   - **Assistant :** ...
4. Ne pas ajouter de commentaire ni de résumé.
5. Le texte doit être clair, logique et auto-suffisant (comprendre sans voir les échanges en temps réel).
6. La sortie doit être en **Français** et sans mise en forme Markdown.

Voici la conversation à nettoyer :
{content}
""",
    "test_tags_gpt": """
    Tu es un assistant de structuration de journaux de développement.

Ton rôle est de lire un échange de discussion brute (entre développeur et assistant IA),\
  et de produire un journal clair en format Markdown structuré.

Voici ce que tu dois faire :

1. Analyse la conversation ligne par ligne.
2. Regroupe les lignes en blocs cohérents autour d’un sujet\
  (ex : discussion sur un bug, une solution, une amélioration…).
3. Pour chaque bloc, ajoute un titre Markdown adapté parmi :
   - ## 🔍 Contexte
   - ## 🐛 Problème
   - ## ✅ Solution
   - ## 🚀 Amélioration possible
   - ## 📌 À faire

4. À la fin de chaque bloc, ajoute une ligne `_tags: #...` avec 1 à 3 tags pertinents.
   (ex : `#bug`, `#note_id`, `#prompt`, `#watcher`, `#refacto`, `#obsidian`, `#todo`...)

5. N’invente rien, ne reformule pas. Structure uniquement.

Format de sortie : Markdown Obsidian directement utilisable.

Commence directement par le contenu Markdown structuré.



        contenu à traiter :
        {content}
  """,
}
