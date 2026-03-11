from gtts import gTTS
import os

def generar_audio_gtts(texto):

    os.makedirs("temp", exist_ok=True)

    file_path = "temp/audio.mp3"

    tts = gTTS(text=texto, lang="es")
    tts.save(file_path)

    print("🔁 Usando voz fallback (gTTS)")

    return file_path