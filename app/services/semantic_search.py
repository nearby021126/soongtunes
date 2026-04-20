from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
# from neo4j_graphrag.llm import OpenAILLM
from py2neo import Graph
from flask import current_app
from collections import defaultdict
import openai
from .utils import *
from config import config

openai.api_key = config.OPENAI_API_KEY

def make_embedding(json_data):
    """
    Args:
        json_data: Response of openaiAPI, json_format {key: LABEL, value:[string1, string2, ..], ..}
    return:
        results_embedding(dict): {key: LABEL, value:[embedding1, embedding2, ..], ..}
    """
    results_embedding=defaultdict(list)
    label_info=json_data.dict()
    embedder = OpenAIEmbeddings(model="text-embedding-ada-002")
    for label, info_list in label_info.items():
        for info in info_list:
            embedding=embedder.embed_query(info)
            results_embedding[label].append(embedding)
    return results_embedding


def get_semantic_query(label, limit):
    label_condition = f"{label}" if label else ""
    query = f"""
    WITH $userEmbedding AS userEmbeddingVector
    MATCH (n:{label_condition})
    WHERE n.embedding IS NOT NULL
    WITH n, gds.similarity.cosine(n.embedding, userEmbeddingVector) AS similarity
    RETURN properties(n) AS node_properties, similarity
    ORDER BY similarity DESC
    LIMIT {limit};
    """
    return query

def get_usr_results(label, results):
    """
    Args:
        label(str): node LABEL
        results: results of semantic search
                list[{"node_properties":{"property_name1": value_1,
                                            "property_name1": value_2, ...}, ..}]
    return:
         cleansing_results: dict{"LABEL":{"property1":[value1, value2, ..]}}    
    """
    graph_label_info = {
        "Song": ["song_name", "issue_date"],
        "Album": ["album_name"],
        "Artist": ["artist_name"],
        "Genre": ["detail"],
        "Playlist": ["plylst_title", "like_cnt", "updt_date"],
        "Tag": ["tag_name"]
    }
    cleansing_results = defaultdict(lambda: defaultdict(list))
    for result in results:
        node_properties = result['node_properties']
        for inner_key in graph_label_info[label]:
            cleansing_results[label][inner_key].append(node_properties[inner_key])
    return cleansing_results
        
def run_query(query, params):
    with current_app.driver.session() as session:  
        result = session.run(query, params)  
        return [record.data() for record in result]  

def semantic_search(json_data, limit=2):
    """
    Args:
        json_data: Response of user_input
        limit(int) : num of Top-k
    Returns:
        results_semantic: List for each labels(dict) 
            {
                "Song": ["노래제목1", "노래제목2", ...],
                "Album": ["앨범명1", "앨범명2", ...],
                "Artist": ["가수명1", "가수명2", ...],
                "Genre": ["장르1", "장르2", ...],
                "Tag": ["태그1", "태그2", ...]
            }
    """
    results_embedding = make_embedding(json_data)
    results_semantic={}
    for label, embedding_list in results_embedding.items():
        if not embedding_list:
            continue
        for embedding in embedding_list:
            semantic_query = get_semantic_query(label, limit=1)
            # results = graph.run(semantic_query, userEmbedding=embedding).data()
            query_params = {"userEmbedding": embedding}
            results = run_query(semantic_query, query_params)
            cleansing_results = get_usr_results(label, results)
            results_semantic |= cleansing_results
    return results_semantic