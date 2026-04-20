from pydantic import BaseModel
import openai
from neo4j import GraphDatabase
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.retrievers import Text2CypherRetriever, HybridCypherRetriever

from .utils import *
from .semantic_search import semantic_search
from config import config
from flask import current_app

MODEL_MAX_TOKENS = {
    'gpt-3.5-turbo': 4096,
    'gpt-3.5-turbo-16k': 16384,
    'gpt-4': 8192,
    'gpt-4-32k': 32768,
    'gpt-4o-mini': 16384,
    'gpt-4o-mini-2024-07-18': 16384,
}

NEO4J_URI = config.NEO4J_URI
MODEL_NAME = config.MODEL_NAME
NEO4J_USER = config.NEO4J_USER
NEO4J_PASSWORD = config.NEO4J_PASSWORD

openai.api_key = config.OPENAI_API_KEY
llm = OpenAILLM(model_name=MODEL_NAME)

def FC_openai_api(prompt: str, input_text: str, format: BaseModel):
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": input_text}
    ]
    functions = [
        {
            "name": "user_label_data",
            "parameters": format.schema()
        }
    ]
    response_max_tokens = 3000
    
    total_tokens = count_tokens(MODEL_NAME, messages, functions, max_tokens=response_max_tokens)
    max_context_tokens = MODEL_MAX_TOKENS[MODEL_NAME]

    safety_margin = int(max_context_tokens * 0.95)

    if total_tokens > safety_margin:
        # print(f"토큰 수 초과. (total_tokens: {total_tokens}, safety_margin: {safety_margin})")
        print("TOKEN_None")
        return None  
    try:
        response = openai.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=messages,
        functions=functions,
        function_call={"name": "user_label_data"},
        temperature=0,
        max_tokens=response_max_tokens
        )    
        function_args = response.choices[0].message.function_call.arguments
        if function_args.strip().lower() == 'false':
            return False
        label_response = format.parse_raw(function_args)
        return label_response

    except Exception as e:
        if type(e) == openai.LengthFinishReasonError:
            print(f"An error occurred: {e}")
            print("Too many tokens: ", e)
            pass
        else:
            print(f"An error occurred: {e}")
            print(e)
            pass   
        
def get_response(set_prompt,call_API,input_text,format:BaseModel):
    """
    Args:
        set_prompt: function
        call_API: function 
    Return: 
        format:BaseModel
    """
    prompt=set_prompt()
    return call_API(prompt, input_text, format)


def text2cypher(user_input):
    """
    Args:
        user_input: str
    """
    # driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver = current_app.driver
    schema = DB_schema()
    retriever = Text2CypherRetriever(
        llm=llm,
        driver=driver,
        neo4j_schema=schema
    )
    json_data = get_response(cleansing_prompt, FC_openai_api, user_input, UserData)
    results_semantic = semantic_search(json_data, limit=1)
    prompt = query_prompt(schema, results_semantic, user_input)
    search_result = retriever.get_search_results(prompt)
    records=search_result.records
    # cypher_query=search_result.metadata["cypher"]
    return records2str(records)


def final_response(user_input):
    """
    Generate a final response using OpenAI LLM
    Args:
        user_input(str): The user's original question
    Returns:
        str: The generated response from OpenAI LLM
    """
    query_results = text2cypher(user_input)
    input_context = f"The following data was retrieved from the database:\n{query_results}"
    try:
        prompt = final_prompt(input_context, user_input)
        response = llm.invoke(prompt).content
        # print(f"LLM 응답:\n{response}")
        return format_response(response)
    except Exception as e:
        print(f"Error generating response: {e}")
        return str(e)