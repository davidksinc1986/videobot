import json
from models import db, User

# La función init_db ya no es necesaria para la creación de tablas,
# pero se mantiene por si es llamada desde código antiguo.
def init_db():
    pass

def save_user(user_data: dict):
    """
    Guarda o actualiza un usuario en la base de datos usando SQLAlchemy.
    Requiere un contexto de aplicación Flask activo.
    """
    if not isinstance(user_data, dict) or not user_data.get("nombre"):
        raise ValueError("Se requiere un diccionario con 'nombre' para guardar el usuario.")
    
    name = user_data["nombre"]
    user = db.session.get(User, name)
    
    if user:
        user.payload = user_data
    else:
        user = User.from_dict(user_data)
        db.session.add(user)
        
    db.session.commit()

def load_user(name: str) -> dict:
    """
    Carga un usuario de la base de datos usando SQLAlchemy.
    Requiere un contexto de aplicación Flask activo.
    """
    user = db.session.get(User, name)
    if user:
        return user.to_dict()
    raise FileNotFoundError(f"Usuario '{name}' no encontrado.")

def list_users() -> list[dict]:
    """
    Lista todos los usuarios de la base de datos.
    Requiere un contexto de aplicación Flask activo.
    """
    users = User.query.order_by(User.name).all()
    return [user.to_dict() for user in users]

def user_exists(name: str) -> bool:
    """
    Verifica si un usuario existe.
    Requiere un contexto de aplicación Flask activo.
    """
    return db.session.query(User.name).filter_by(name=name).first() is not None

def delete_user(name: str):
    """
    Elimina un usuario.
    Requiere un contexto de aplicación Flask activo.
    """
    user = db.session.get(User, name)
    if user:
        db.session.delete(user)
        db.session.commit()

def migrate_json_users_if_needed() -> int:
    """
    Migra usuarios de archivos JSON a la base de datos si aún no existen.
    Esta función es especial y crea su propio contexto de app, por lo que
    debe ser llamada desde el proceso principal de la aplicación al iniciar.
    """
    from app_context import create_app_for_worker
    app = create_app_for_worker()
    with app.app_context():
        db.create_all()

        from config import USUARIOS_DIR
        import os

        if not os.path.isdir(USUARIOS_DIR):
            return 0

        imported_count = 0
        for filename in os.listdir(USUARIOS_DIR):
            if filename.endswith(".json"):
                name = filename[:-5]
                if not user_exists(name):
                    try:
                        filepath = os.path.join(USUARIOS_DIR, filename)
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        data["nombre"] = name
                        save_user(data)
                        imported_count += 1
                        print(f"Migrated user '{name}' from JSON to database.")
                    except Exception as e:
                        print(f"Error migrating user {name}: {e}")
        return imported_count
