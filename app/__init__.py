from flask import Flask
from flask import current_app
from neo4j import GraphDatabase
from config import Config
from config import config
import markdown
from markupsafe import Markup


def create_app():
    app = Flask(__name__)
    app.config.update(config.dict())
    try:
        app.driver = GraphDatabase.driver(
            app.config['NEO4J_URI'],
            auth=(app.config['NEO4J_USER'], app.config['NEO4J_PASSWORD'])
        )
    except Exception as e:
        print(f"Error connecting Neo4j driver: {e}")

    from .routes import main_bp
    app.register_blueprint(main_bp)
    @app.template_filter('markdown')
    def render_markdown(text):
        return Markup(markdown.markdown(text, extensions=['nl2br', 'sane_lists']))
    
    @app.teardown_appcontext
    def close_driver(exception):
        driver = getattr(app, 'driver', None)
        if driver is not None:
            driver.close()

    return app