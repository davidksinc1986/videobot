import os
import time
import requests

from config import TEMP_DIR, DEFAULT_ELEVEN_API_KEY, DEFAULT_ELEVEN_VOICE_ID


class QuotaExceededError(Exception):
    pass


def generar_audio(texto: str, api_key: str | None = None, voice_id: str | None = None) -> str:
    api_key = (api_key or DEFAULT_ELEVEN_API_KEY or "").strip()
    voice_id = (voice_id or DEFAULT_ELEVEN_VOICE_ID or "").strip()

    if not api_key or not voice_id:
        raise Exception("Faltan credenciales ElevenLabs (api_key o voice_id).")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }

    data = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.35,
            "similarity_boost": 0.85,
            "style": 0.7,
            "use_speaker_boost": True
        }
    }

    resp = requests.post(url, json=data, headers=headers, timeout=60)

    if resp.status_code != 200:
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text}

        print("❌ Error ElevenLabs:", payload)

        # detectar quota
        msg = str(payload)
        if "quota_exceeded" in msg or "credits" in msg or "insufficient" in msg:
            raise QuotaExceededError("Cuota agotada en ElevenLabs")

        raise Exception("Error ElevenLabs")

    os.makedirs(TEMP_DIR, exist_ok=True)
    file_path = os.path.join(TEMP_DIR, f"audio_{int(time.time())}.mp3")

    with open(file_path, "wb") as f:
        f.write(resp.content)

    return file_path