PROMPTS = {
    "test_gpt": """
  Context:
You are an expert assistant in synthesizing and analyzing conversations between a user and a GPT-type conversational model.
Your goal is to extract the essential points from the exchanges while structuring the content into hierarchical notes.

Carefully analyze the following conversation between a user and an AI agent.
Your task is to produce a concise and structured summary that captures the essence of the exchange.

Follow these guidelines:
  01 - Identify and summarize the main topic and objective of the conversation.
  02 - Extract key points and essential information, organizing them logically.
  03 - Highlight important steps in the process or problem resolution.
  04 - Emphasize difficulties or obstacles encountered and how they were overcome.
  05 - Identify crucial decisions or breakthrough moments in the conversation.
  06 - Ignore the following elements:
    Polite exchanges or general small talk
    Incorrect statements that were later corrected
    Redundant or repetitive information
    Digressions unrelated to the main topic
    Use a clear format with bullet points or subtitles for easy readability.
  07 - The content must be in French.

Here is the text:
        {content}
      
            """,
    "reformulation": """
    You are an intelligent and structured note organizer assistant specialized in processing and improving text.
Follow the specific instructions below:

1. Extract key ideas, rewrite the content to enhance clarity, conciseness, and logical flow while preserving the original meaning.
2. Simplify complex language, eliminate unnecessary jargon, and ensure the content is accessible to a general audience.
3. Use a professional yet approachable tone.
4. Remove redundancies and unnecessary details.
5. Preserve all original **titles and headings** in the Markdown format.
6. If the text does not contain a title, generate a relevant and concise title in Markdown format (e.g., # Introduction).
7. The output must be in **French**, presented in **Markdown format**.
8. Clean up unnecessary line breaks.
9. Remove ads and promotional content.

        Here is the text to simplify:
        {content}
            """,
    "article": """
    You are an intelligent note-organizing assistant.
    Your task is to summarize the following article.
    Provide a comprehensive summary that captures the main ideas, key findings, and essential technical details.
    Structure your summary logically, starting with an overview and progressing through the article's main sections.
    Use markdown to format your output, bolding key subject matter and potential areas that may need expanded information.
    Ensure the summary is accessible to the target audience while maintaining technical accuracy.
    Conclude with the most significant implications or applications of the article's content.
    The output must be in **French**, presented in **Markdown format**, and must **avoid unnecessary introductory or concluding phrases**.
            Here is the text :
            {content}
            """,
    "divers": """
    
    You are an intelligent assistant specialized in summarizing articles.
    Summarize the following article, focusing on these key elements:
        - structure the text logically, using clear paragraphs.
        - Connect important ideas
        - Remove superfluous or redundant details.
        - Make sure the result is fluid and readable.
        - Important facts or statistics mentioned
        - Potential implications or consequences
        - Any proposed solutions or policy recommendations
        - Identify the author's thesis statement or main argument.
        - Highlight any persuasive techniques used in the article.
        - For opinion pieces, clearly outline the author's viewpoint and key arguments
        - The output must be in **French**, presented in **Markdown format**.
        
        Here is the text :
            {content}
            """,
    "idea": """
    Provide a comprehensive summary and structured outline of [topic/project].
    Include the following elements:
        - A concise overview in 2-3 sentences
        - Key objectives or goals
        - Main ideas or components, organized into logical sections
        - Reflections on challenges, insights, and lessons learned
        - Potential next steps or areas for improvement
        - Format the response using appropriate headers, bullet points, and numbering.
        - Ensure the summary is clear, concise, and captures the essential elements without excessive detail.
        - The output must be in **French**, presented in **Markdown format**, and must **avoid unnecessary introductory or concluding phrases**.
            Here is the text :
            {content}
            """,
    "todo": """
    You are an intelligent note-organizing assistant.
    Create a comprehensive task management plan that:
        - Prioritizes tasks using a strategic approach
        - Allocates appropriate time blocks
        - Identifies potential bottlenecks
        - Suggests optimal task sequencing

        - Current tasks: [detailed task list]
        - Project goals: [specific objectives]
        - Time constraints: [available working hours]
    The output must be in **French**, presented in **Markdown format**, and must **avoid unnecessary introductory or concluding phrases**.
            Here is the text :
            {content}
            """,
    "tutorial": """
    You are an intelligent note-organizing assistant.
    Please provide a summary of this tutorial or lesson that includes:
      1. Main Learning Objectives
        - What core skills or knowledge are being taught?
        - What is the primary goal of this tutorial?

      2. Key Concepts Covered
        - List the most important theoretical or practical concepts
        - Highlight any critical technical or procedural details

      3. Step-by-Step Overview
        - Briefly outline the main stages or progression of the tutorial
        - Note any critical decision points or techniques

      4. Practical Takeaways
        - What specific skills can a learner immediately apply?
        - What are the most valuable practical insights?

      5. Potential Challenges and Solutions
        - What common difficulties might learners encounter?
        - What strategies help overcome these challenges?

      6. Next Learning Recommendations
        - What follow-up resources or advanced topics complement this tutorial?
        - Suggest potential paths for deeper exploration
    
    The output must be in **French**, presented in **Markdown format**, and must **avoid unnecessary introductory or concluding phrases**.
            Here is the text :
            {content}
            """,            
    "title": """
    You are an intelligent note-organizing assistant. Add clear, structured titles in markdown format.

    **Instructions:**
    - Use `##` for major sections.
    - Use `###` for subsections within each section.
    - Use `####` only for deeply detailed points.
    - Do not add unnecessary titles like "ChatGPT said" or "You said".
    - Titles should be short (max 8 words) and descriptive.
    - The output must be in **French**, presented in **Markdown format**, and must **avoid unnecessary introductory or concluding phrases**.
  

    Here is the text to process:
    {content}    
    """,
    "tags": """
    You are a bot in a read-it-later app and your responsibility is to help with automatic tagging.
    CONTENT START HERE
    {content}
    CONTENT END HERE
    
    Instructions:
      1. Read the content
      2. suggest relevant tags that describe its key themes, topics, and main ideas. The rules are:
        - Aim for a variety of tags, including broad categories, specific keywords, and potential sub-genres.
        - The tags language must be in English.
        - If it's a famous website you may also include a tag for the website. If the tag is not generic enough, don't include it.
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
    You are an intelligent note-organizing assistant. Analyze the following content and add clear, structured titles in markdown format
    1. Identify the main topic of the text.
    2. List the key supporting points.
    3. Present the summary in a bullet-point format, highlighting the most crucial information.
    4. Highlight any important data or statistics.
    5. The output must be in **French**, presented in **Markdown format**, and must **avoid unnecessary introductory or concluding phrases**.
Here is the text to process:
    {content}    
    """,
    "synthese2": """
    You are an intelligent note-organizing assistant.
    the content is a synthesis recomposed from several blocks.
    your goal is to :
        - structure the text logically, using clear paragraphs.
        - Connect important ideas
        - Remove superfluous or redundant details.
        - Make sure the result is fluid and readable.
        - Capture the author's conclusion or main argument.
        - Synthesize the information into a concise summary.
        - Ends with 2-3 reflection questions to explore the topic further
        - The output must be in **French**, presented in **Markdown format**, and must **avoid unnecessary introductory or concluding phrases**.
    Here is the text to process:
    {content}    
    """,
    "type": """
You are an assistant specialized in classifying notes based on their content.
here the content :
{content}



Instructions:
1. Read the content
2. Identify the best **category** and only one, you can propose a new one but use as a priority an existing one in the list below :
  {categ_dict}
3. and propose an appropriate **subcategory** and only one.
  you can take inspiration from this list :
   -categories: subcategorie 1, subcategorie 2 etc...
  {subcateg_dict}
4. Return your response in the format: "category/subcategory" (e.g., "programming/python").
5. Do not include any introductory or concluding remarks, only one category and one subcategory.
6. If the content is ambiguous or does not fit, return "uncategorized/unknown".


""",
    "watchlist": """
    You are an intelligent note-organizing assistant.
    I need help creating and organizing a comprehensive watchlist that helps me track and prioritize media I want to consume. Please help me develop a structured list with the following details for each item:

- Title
- Type of media (movie, TV show, documentary, etc.)
- Genre
- Current status (not started, in progress, completed)
- Priority level
- Personal rating (if already watched)
- Where I can watch it (streaming platform or service)
- Estimated time to watch
- Brief reason for adding to the list

Your task is to help me categorize and prioritize these items, suggesting an order based on my preferences, available time, and personal interests. Additionally, provide recommendations for managing and updating this watchlist efficiently.

- Current watchlist items: [list your current items]
- Personal preferences: [describe your viewing preferences]
    The output must be in **French**, presented in **Markdown format**, and must **avoid unnecessary introductory or concluding phrases**.
            Here is the text :
            {content}
           """,
    "political": """
    You are an intelligent assistant specialized in summarizing political articles.
    Summarize the following political article, focusing on these key elements:
        - structure the text logically, using clear paragraphs.
        - Connect important ideas
        - Remove superfluous or redundant details.
        - Make sure the result is fluid and readable.
        - Important facts or statistics mentioned
        - Potential implications or consequences
        - Any proposed solutions or policy recommendations
        - Identify the author's thesis statement or main argument.
        - Highlight any persuasive techniques used in the article.
        - For opinion pieces, clearly outline the author's viewpoint and key arguments
        - The output must be in **French**, presented in **Markdown format**.
          
          

    Here is the text:  
    {content}

           
            """,
    "geopolitical": """
    Provide a comprehensive summary of the given geopolitical article, focusing on:
    Key events or developments described
    Main actors involved (states, organizations, influential individuals)
    Underlying causes or motivations for the situation
    Potential short-term and long-term consequences
    Regional and global implications
    Any significant economic, military, or diplomatic factors
    Relevant historical context
    Current international responses or reactions
    Possible future scenarios or outcomes
    Analyze the article through the lens of hard power, soft power, and noopolitik. Highlight any shifts in global power dynamics or balance of power.
    Conclude with the most critical insights and their potential impact on international relations.
    The output must be in **French**, presented in **Markdown format**, and must **avoid unnecessary introductory or concluding phrases**.
            Here is the text :
            {content}
            """,
    "sociology": """
    Analyze and summarize the key sociological concepts, theories, and findings presented in this article.
    Focus on the main arguments, methodological approach, and societal implications.
    Highlight any significant data or statistics that support the author's conclusions.
    Conclude by discussing how this research contributes to our understanding of social structures, interactions, or phenomena
    The output must be in **French**, presented in **Markdown format**, and must **avoid unnecessary introductory or concluding phrases**.
            Here is the text :
            {content}
            """,
    "make_file_name": """
    You are an intelligent note-organizing assistant.
    Here is the content of a document:

{content}

    Based on the content, generate a filename in the following format:  
    `file_name_source_date.md`  
    - The name should describe the document's content. Replace spaces with underscores `_`. 
    - Include the source if it is mentioned in the document (e.g., for a webpage, include only the domain or site name without "http" or extensions like ".com").
    - Add the current date in the format `YYMMDD` (e.g., January 21, 2025, becomes `250121`).
    - If the content is too vague, create a generic name using the word "note".
    
    Generate only the filename, without any additional text or comments.
          """,
    "gpt_reformulation": """
    You are an intelligent and structured note-organizing assistant, specializing in text processing and enhancement.

Follow the specific instructions below:

  01 - Extract key ideas and rewrite the content to improve clarity, conciseness, and logical flow while preserving the original meaning.
  02 - Simplify complex language, eliminate unnecessary jargon, and ensure the content is accessible to a general audience.
  03 - Use a professional yet approachable tone.
  04 - Remove redundancies and unnecessary details.
  05 - Omit polite exchanges or general conversation.
  06 - Eliminate unnecessary line breaks.
  07 - Remove advertisements and promotional content.
  08 - The content must be in French.

Here is the text to process:
    {content}
  """,
    "first_block": """
    You are an intelligent and structured note-organizing assistant, specializing in text processing and enhancement.
    This text is the first part of a larger document divided into sections. Ensure logical continuity between sections and avoid repetition of previous summaries.
Follow the specific instructions below:

  01 - Extract key ideas and rewrite the content to improve clarity, conciseness, and logical flow while preserving the original meaning.
  02 - Simplify complex language, eliminate unnecessary jargon, and ensure the content is accessible to a general audience.
  03 - Ensure a clear, structured, and professional style while maintaining natural readability.
  04 - Remove redundancies and unnecessary details.
  05 - Omit polite exchanges or general conversation.
  06 - Eliminate unnecessary line breaks.
  07 - Remove advertisements and promotional content.
  08 - Preserve existing headings and subheadings (`#`, `##`, `###`) while improving their clarity if needed.
  09 - The content must be in French.

Here is the text to process:
    {content}
  """,
    "last_block": """
    You are an intelligent and structured note-organizing assistant, specializing in text processing and enhancement.
    This text is the final part of a larger document divided into sections. Ensure logical continuity between sections and avoid repetition of previous summaries.
Follow the specific instructions below:

  01 - Extract key ideas and rewrite the content to improve clarity, conciseness, and logical flow while preserving the original meaning.
  02 - Simplify complex language, eliminate unnecessary jargon, and ensure the content is accessible to a general audience.
  03 - Ensure a clear, structured, and professional style while maintaining natural readability.
  04 - Remove redundancies and unnecessary details.
  05 - Omit polite exchanges or general conversation.
  06 - Eliminate unnecessary line breaks.
  07 - Remove advertisements and promotional content.
  08 - Preserve existing headings and subheadings (`#`, `##`, `###`) while improving their clarity if needed.
  09 - The content must be in French.

Here is the summary of the previous section:
        {previous_response}

This is the final section. Ensure a coherent conclusion:
    {content}
  """,
    "middle_block": """
    You are an intelligent and structured note-organizing assistant, specializing in text processing and enhancement.
    This text is a part of a larger document divided into sections. Ensure logical continuity between sections and avoid repetition of previous summaries.
Follow the specific instructions below:

  01 - Extract key ideas and rewrite the content to improve clarity, conciseness, and logical flow while preserving the original meaning.
  02 - Simplify complex language, eliminate unnecessary jargon, and ensure the content is accessible to a general audience.
  03 - Ensure a clear, structured, and professional style while maintaining natural readability.
  04 - Remove redundancies and unnecessary details.
  05 - Omit polite exchanges or general conversation.
  06 - Eliminate unnecessary line breaks.
  07 - Remove advertisements and promotional content.
  08 - Preserve existing headings and subheadings (`#`, `##`, `###`) while improving their clarity if needed.
  09 - The content must be in French.

Here is the summary of the previous section:
        {previous_response}

        Now, process the following section:
        {content}
  """
   
   
   
   
    
    
}