import time

from generador import generar_video_usuario
from storage import init_db, migrate_json_users_if_needed, list_users

print("🔥 SISTEMA MULTIUSUARIO ACTIVO 🔥")
init_db()
migrated = migrate_json_users_if_needed()
if migrated:
    print(f"✅ Migrados {migrated} usuarios JSON a SQLite")


def cargar_usuarios():
    return list_users()


while True:
    usuarios = cargar_usuarios()

    for usuario in usuarios:
        if usuario.get("activo"):
            print(f"\n🎬 Generando para: {usuario['nombre']}")
            generar_video_usuario(usuario)

            espera = usuario.get("frecuencia_minutos", 60) * 60
            print(f"⏳ Esperando {espera} segundos...")
            time.sleep(espera)
