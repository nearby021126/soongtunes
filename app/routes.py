from flask import Blueprint, render_template, jsonify, request, current_app
from app.services.recognition import recognize_audio
from app.services.response import final_response

main_bp = Blueprint("main", __name__)

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            # text
            recommendation = final_response(message)
            return render_template('result.html', message=message, recommendation=recommendation)
    return render_template('index.html')  

# @main_bp.route("/recognition", methods=["POST"])
# def recognition():
#     try:
#         text = recognize_audio()
#         graph_response = final_response(text)
#         return jsonify({"input_text": text, "graph_response": graph_response})
#     except Exception as e:
#         return jsonify({"input_text": str(e), "graph_response": str(e)})
    
@main_bp.route("/test_neo4j")
def test_neo4j():
    try:
        driver = current_app.driver
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN COUNT(n) AS count")
            count = result.single()["count"]
            return f"Neo4j connection successful, Number of nodes: {count}"
    except Exception as e:
        return f"Neo4j connection failed: {str(e)}"