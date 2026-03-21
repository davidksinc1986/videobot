import os
import pickle
import traceback
import time

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request


def _clean_title(titulo: str) -> str:
    # 1) limpiar espacios/saltos/tab
    titulo_limpio = " ".join((titulo or "").split())

    # 2) max 100 chars (me dejo margen)
    if len(titulo_limpio) > 95:
        titulo_limpio = titulo_limpio[:92] + "..."

    # 3) fallback si queda vacío
    if not titulo_limpio:
        titulo_limpio = f"Video Automático - {int(time.time())}"

    return titulo_limpio


def _resolve_token_path(user: dict | None, token_path: str | None) -> str:
    """
    Reglas:
    - Si token_path viene explícito -> usarlo
    - Si user es David (nombre == 'david') -> ./token.pickle (legacy)
    - Si no -> ./sessions/<nombre>/youtube/token.pickle
    - Si no hay user -> ./token.pickle
    """
    if token_path:
        return token_path

    base_dir = os.path.dirname(os.path.abspath(__file__))

    if user and isinstance(user, dict):
        nombre = (user.get("nombre") or "").strip()
        if nombre.lower() == "david":
            return os.path.join(base_dir, "token.pickle")
        if nombre:
            return os.path.join(base_dir, "sessions", nombre, "youtube", "token.pickle")

    return os.path.join(base_dir, "token.pickle")


def _load_credentials(token_file: str):
    credentials = None

    if os.path.exists(token_file):
        with open(token_file, "rb") as f:
            credentials = pickle.load(f)

    # refrescar token si expiró
    if credentials and (not credentials.valid):
        if getattr(credentials, "expired", False) and getattr(credentials, "refresh_token", None):
            credentials.refresh(Request())

    return credentials


def subir_youtube(video_path: str, titulo: str, user: dict | None = None, token_path: str | None = None) -> bool:
    """
    Uploader oficial YouTube (API).
    - David usa ./token.pickle (legacy)
    - Otros: ./sessions/<user>/youtube/token.pickle
    - Si token_path se pasa explícito, lo respeta.
    """
    try:
        print("📤 Subiendo a YouTube vía API (oficial)...")

        titulo_limpio = _clean_title(titulo)
        token_file = _resolve_token_path(user, token_path)

        credentials = _load_credentials(token_file)

        if not credentials or not credentials.valid:
            print(f"❌ Error: token no válido o no existe: {token_file}")
            print("   - Para David: asegúrate de tener ./token.pickle")
            print("   - Para otros: sube token a ./sessions/<usuario>/youtube/token.pickle")
            return False

        youtube = build("youtube", "v3", credentials=credentials)

        body = {
            "snippet": {
                "title": titulo_limpio,
                "description": "Video generado automáticamente por mi bot.\n#shorts #automation",
                "tags": ["bot", "automation", "shorts"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True
        )

        print(f"📎 Archivo: {video_path}")
        print(f"🏷️  Título: {titulo_limpio}")
        print(f"🔑 Token: {token_file}")

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"⏳ Progreso: {int(status.progress() * 100)}%")

        if response and "id" in response:
            print(f"✅ ¡VIDEO SUBIDO! ID: {response['id']}")
            return True

        print("❌ Error inesperado: No se recibió ID del video.")
        return False

    except Exception:
        print("❌ ERROR API YOUTUBE:")
        traceback.print_exc()
        return False