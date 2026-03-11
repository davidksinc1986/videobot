import os
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import BASE_DIR

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def subir_a_youtube(video_path, titulo, descripcion):

    try:
        # 🔥 Ruta absoluta correcta
        token_path = os.path.join(BASE_DIR, "token.pickle")

        if not os.path.exists(token_path):
            print("❌ token.pickle no encontrado en:", token_path)
            return

        with open(token_path, "rb") as token:
            creds = pickle.load(token)

        youtube = build("youtube", "v3", credentials=creds)

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": titulo,
                    "description": descripcion,
                    "tags": ["motivacion", "shorts"],
                    "categoryId": "22"
                },
                "status": {
                    "privacyStatus": "public"
                }
            },
            media_body=MediaFileUpload(video_path)
        )

        response = request.execute()

        print("✅ Subido a YouTube:", response["id"])

    except Exception as e:
        print("❌ Error subiendo a YouTube:", str(e))