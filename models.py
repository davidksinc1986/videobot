from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy import Text

# Inicializa la base de datos sin vincularla a una app específica todavía
db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    # Columnas existentes
    name = db.Column(db.String(255), primary_key=True)
    payload = db.Column(JSON, nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        # El payload ya es un diccionario (o será deserializado como tal por SQLAlchemy)
        return self.payload

    @staticmethod
    def from_dict(data: dict):
        # Se asegura de que el nombre en el payload y en la columna principal coincidan
        name = data.get("nombre")
        if not name:
            raise ValueError("El payload del usuario debe contener un 'nombre'.")
        return User(name=name, payload=data)
