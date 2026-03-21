# app_context.py
# Este módulo proporciona una función para crear una instancia de la aplicación Flask
# configurada para ser usada fuera del ciclo de vida de una petición web,
# como en un worker de Celery.

from flask import Flask
from config import DB_PATH
from models import db

def create_app_for_worker():
    """
    Crea una instancia mínima de la aplicación Flask con la configuración
    necesaria para la base de datos y el contexto de la aplicación.
    """
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app
