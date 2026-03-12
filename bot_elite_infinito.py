import os
import random
import time
import requests
import schedule

from moviepy.editor import *
from generador import generar_texto

# ============================================
# CONFIG
# ============================================

PEXELS_API_KEY = "Qptl9I17ONeRrG6w4F3L3FOGlwnDxUgSYqB7Ew8ggq6BHOg36QKe8agx"

ELEVEN_API_KEY = "sk_9dd131528a66bd44aed9066c6041ea6ba259ee570f6e073d"

VOICE_ID = "18GZPpJvaVG53Nt3H52N"

VIDEOS_CADA_MINUTOS = 90

os.makedirs("temp", exist_ok=True)
os.makedirs("videos", exist_ok=True)

# ============================================
# VOZ ELEVENLABS
# ============================================

def generar_voz(texto):

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

    headers = {

        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json"
    }

    data = {

        "text": texto,
        "model_id": "eleven_multilingual_v2"
    }

    response = requests.post(url, headers=headers, json=data)

    with open("temp/audio.mp3", "wb") as f:

        f.write(response.content)

    return AudioFileClip("temp/audio.mp3")


# ============================================
# VIDEO PEXELS
# ============================================

def descargar_video():

    temas = [

        "cyberpunk",
        "space",
        "ai",
        "technology",
        "abstract",
        "universe",
        "future",
        "nature"
    ]

    url = "https://api.pexels.com/videos/search"

    headers = {

        "Authorization": PEXELS_API_KEY
    }

    params = {

        "query": random.choice(temas),
        "orientation": "portrait",
        "per_page": 10
    }

    r = requests.get(url, headers=headers, params=params)

    data = r.json()

    if "videos" not in data:

        raise Exception(data)

    video_url = random.choice(

        data["videos"]

    )["video_files"][0]["link"]

    video_bytes = requests.get(video_url).content

    with open("temp/bg.mp4", "wb") as f:

        f.write(video_bytes)

    return VideoFileClip("temp/bg.mp4")


# ============================================
# CREAR VIDEO
# ============================================

def crear_video():

    texto = generar_texto()

    print("Generando:", texto)

    audio = generar_voz(texto)

    background = descargar_video()

    background = background.loop(duration=audio.duration)

    background = background.resize(height=1920)

    background = background.crop(

        width=720,
        height=1280,
        x_center=background.w/2,
        y_center=background.h/2
    )


    txt = TextClip(

        texto,
        fontsize=60,
        color="white",
        method="caption",
        size=(680,None)

    ).set_position(("center","bottom")).set_duration(audio.duration)


    final = CompositeVideoClip([

        background,
        txt

    ])


    final = final.set_audio(audio)


    nombre = f"videos/video_{int(time.time())}.mp4"


    final.write_videofile(

        nombre,
        fps=30,
        codec="libx264",
        audio_codec="aac"
    )


    print("VIDEO CREADO:", nombre)


# ============================================
# LOOP INFINITO
# ============================================

schedule.every(VIDEOS_CADA_MINUTOS).minutes.do(crear_video)

crear_video()

print("BOT ELITE INICIADO")

while True:

    schedule.run_pending()

    time.sleep(10)
    