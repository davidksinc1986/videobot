import os
import json
import time

from generador import generar_video_usuario
from config import USUARIOS_DIR

print("🔥 SISTEMA MULTIUSUARIO ACTIVO 🔥")

def cargar_usuarios():
    usuarios = []

    for archivo in os.listdir(USUARIOS_DIR):
        if archivo.endswith(".json"):
            path = os.path.join(USUARIOS_DIR, archivo)
            with open(path, encoding="utf-8") as f:
                config = json.load(f)
                usuarios.append(config)

    return usuarios


while True:

    usuarios = cargar_usuarios()

    for usuario in usuarios:

        if usuario.get("activo"):
            print(f"\n🎬 Generando para: {usuario['nombre']}")
            generar_video_usuario(usuario)

            espera = usuario.get("frecuencia_minutos", 60) * 60
            print(f"⏳ Esperando {espera} segundos...")
            time.sleep(espera)