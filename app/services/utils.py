from pydantic import BaseModel, Field
from typing import List, Optional
import tiktoken
import json
import markdown

# MODEL_MAX_TOKENS = {
#     'gpt-3.5-turbo': 4096,
#     'gpt-3.5-turbo-16k': 16384,
#     'gpt-4': 8192,
#     'gpt-4-32k': 32768,
#     'gpt-4o-mini': 16384,
#     'gpt-4o-mini-2024-07-18': 16384,
# }

class UserData(BaseModel):
    Song: Optional[List[str]] = Field(default_factory=list)
    Album: Optional[List[str]] = Field(default_factory=list)
    Artist: Optional[List[str]] = Field(default_factory=list)
    Genre: Optional[List[str]] = Field(default_factory=list)
    Tag: Optional[List[str]] = Field(default_factory=list)
    
def cleansing_prompt():
    prompt = f"""
    You are an AI designed to extract and organize information from the user's input text according to specified fields. 
    Analyze the user's input and return the identified information in the following format. 
    Ensure the response is provided **exclusively** in JSON format enclosed within a JSON code block.

    Required format:
    ```json
    {{
        "Song": ["SongTitle1", "SongTitle2", ...],
        "Album": ["AlbumName1", "AlbumName2", ...],
        "Artist": ["ArtistName1", "ArtistName2", ...],
        "Genre": ["Genre1", "Genre2", ...],
        "Tag": ["Tag1", "Tag2", ...]
    }}
    ```
    Notes:
    - **Only extract labels** directly from the user's input text. Do not infer or generate additional information.
    - If any field has no relevant information in the user's input, return an empty list (`[]`) for that field.
    - **Tag**: Store the user's current situation or context in word form (e.g., "studying," "traveling").
    - Ensure all identified information is concise and relevant to the given fields.
    """
    return prompt


def query_prompt(schema, semantic_results_str, question):
    prompt = f"""
    You are an AI assistant tasked with generating a Cypher query for Neo4j.
    Generate a Cypher statement to query a graph database based on the given schema, semantic search results, and question.
    Use only the provided relationship types and properties in the schema.

    #### Schema:
    {schema}

    #### Semantic Search Results:
    {semantic_results_str}

    #### Notes:
    - The query must always retrieve the following information:
      1. `song_name` from the `Song` node.
      2. `artist_name` as a list via the relationship `Song -[:PERFORMED_BY]-> Artist`.
    - Use the following query structure:
      MATCH (s:Song)-[:INCLUDED_IN]->(p:Playlist)-[:TAGGED_WITH]->(t:Tag)
      WHERE t.tag_name CONTAINS '<tag_value>'
      RETURN 
          s.song_name AS song_name,
          [(s)-[:PERFORMED_BY]->(a:Artist) | a.artist_name] AS artist_name
      ORDER BY s.issue_date DESC
      LIMIT 10
    - Ensure the generated query does not include any additional code blocks, such as ` ``` ` or comments. 
      The query must be pure Cypher syntax.
    - If the Semantic Search Results include filters for other properties (e.g., `Artist`, `Genre`), modify only the `MATCH` and `WHERE` parts of the query to include those filters. Ensure the rest of the query structure remains consistent.
    - Always filter using the semantic search results for each label's properties, incorporating them as conditions in the query.
    - If no exact matches exist for the specified filters, relax the conditions:
        - Use `CONTAINS` or `STARTS WITH` instead of `=` for partial matches.
        - Apply Full-Text Index if available to handle relaxed conditions.
    - Ensure the query is efficient, optimized for performance, and limits the output to the top N results (e.g., `LIMIT 10`).

    #### Example Adjustments:
    - If the Semantic Search Results include a `Genre`, adjust the `MATCH` part as follows:
      MATCH (s:Song)-[:BELONGS_TO]->(g:Genre)
      WHERE g.genre_name CONTAINS '<genre_value>'
    - If the Semantic Search Results include an `Artist`, adjust the `MATCH` part as follows:
      MATCH (s:Song)-[:PERFORMED_BY]->(a:Artist)
      WHERE a.artist_name CONTAINS '<artist_value>'

    #### Question:
    {question}

    #### Cypher Output example:
    MATCH (s:Song)-[:RELATIONSHIP]->(target_node)
    WHERE <conditions>
    RETURN 
        s.song_name AS song_name,
        [(s)-[:PERFORMED_BY]->(a:Artist) | a.artist_name] AS artist_name
    ORDER BY s.issue_date DESC
    LIMIT 10
    """
    return prompt
  


def final_prompt(input_context, user_question):
    prompt = f"""
    Context: {input_context}
    Question: {user_question}
    Please provide a detailed and clear answer based on the context.
    Ensure that your answer references and incorporates the context explicitly.

    - **Format your response using HTML tags.**
    - If there is no related data in the context, **do not mention to the user that data is missing.**
    - After your introductory sentence, add an empty line and start the recommendation list.
    - Use an ordered list (`<ol>`) with each item in `<li>` tags.
    - Each item should be formatted as follows: `<li><strong>"Song Title"</strong> - <em>Artist Name</em> 🎵</li>`
    - Include an empty line between each item to improve readability.
    - Use appropriate emojis to enhance visual appeal.
    - **Write your answer in Korean.**

    **Example:**

    <p>마음을 편안하게 해주는 노래들을 추천해 드릴게요:</p>

    <ol>
        <li><strong>"바람이 불어오는 곳"</strong> - <em>김광석</em> 🎸</li>

        <li><strong>"밤편지"</strong> - <em>아이유</em> 🌙</li>

        <li><strong>"봄날"</strong> - <em>방탄소년단</em> 🌼</li>
    </ol>

    Replace "Song Title" and "Artist Name" with actual songs and artists you'd like to recommend, and use appropriate emojis to make your answer more engaging.
    """
    return prompt


def count_tokens(model_name: str, messages: List[dict], functions: Optional[List[dict]] = None, max_tokens: int = 0) -> int:
    encoding = tiktoken.encoding_for_model(model_name)
    total_tokens = 0

    for message in messages:
        for key, value in message.items():
            total_tokens += len(encoding.encode(value))

    if functions:
        functions_str = json.dumps(functions)
        total_tokens += len(encoding.encode(functions_str))

    total_tokens += max_tokens

    return total_tokens


def DB_schema():
    graph_schema =f"""
    Nodes:
    - Song: Properties: song_id, song_name, issue_date
    - Album: Properties: album_id, album_name
    - Artist: Properties: artist_id, artist_name
    - Genre: Properties: genre_name
    - SubGenre: Properties: genre_name
    - Playlist: Properties: playlist_id, plylst_title, like_cnt, updt_date
    - Tag: Properties: tag_name

    Relationships:
    - Song -[:INCLUDED_IN]-> Album
    - Song -[:INCLUDED_IN]-> Playlist
    - Song -[:PERFORMED_BY]-> Artist
    - Song -[:BELONGS_TO]-> Genre
    - Genre -[:HAS_SUBGENRE]-> SubGenre
    - Playlist -[:TAGGED_WITH]-> Tag
    """
    return graph_schema

def semantic2str(results_semantic: dict):
    """
    Args:
        results_semantic (dict): Semantic search results for each label

    Returns:
        semantic_results_str(str): Combined schema and semantic search results as a single string
    """
    schema = DB_schema()
    
    semantic_results_str = "\n".join(
        [f"- {label}: {values}" for label, values in results_semantic.items()]
    )
    # combined_schema = f"{schema.strip()}\n\nSemantic Search Results:\n{semantic_results_str}"
    return semantic_results_str

def records2str(records):
    records_dict= [{
                "song_name":record["song_name"], 
                "artist_name":record["artist_name"]
                } for record in records]
    records_dict_str = str(records_dict)
    return records_dict_str


def format_response(response_text):
    import bleach
    from markupsafe import Markup

    allowed_tags = ['p', 'ol', 'li', 'strong', 'em', 'br']
    allowed_attrs = {}
    cleaned_html = bleach.clean(response_text, tags=allowed_tags, attributes=allowed_attrs)
    safe_html = Markup(cleaned_html)

    return safe_html
