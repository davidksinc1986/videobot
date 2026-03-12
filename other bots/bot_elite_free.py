import os
import pickle
import random
import requests
import time
import schedule
import textwrap

from moviepy.editor import *
from gtts import gTTS

import googleapiclient.discovery
import googleapiclient.http

from PIL import Image, ImageDraw, ImageFont
import numpy as np


# =====================================
# CONFIG
# =====================================

PEXELS_API_KEY = "Qptl9I17ONeRrG6w4F3L3FOGlwnDxUgSYqB7Ew8ggq6BHOg36QKe8agx"

VIDEOS_PER_DAY = 10

INTERVAL = int(1440 / VIDEOS_PER_DAY)

CATEGORY = "27"

TEMAS = [

"space",
"ai",
"money",
"success",
"technology",
"future",
"universe",
"psychology",
"mystery",
"cyberpunk",
"luxury",
"mind"

]


# =====================================
# CARGAR DATOS UNA SOLA VEZ
# =====================================

with open("datos.txt", encoding="utf-8") as f:

    DATOS = [d.strip() for d in f.readlines() if d.strip()]


# =====================================
# GENERADOR TEXTO VIRAL (CORREGIDO)
# =====================================

def generar_texto():

    dato = random.choice(DATOS)

    tipo = random.choice([1,2,3,4])


    if tipo == 1:

        return dato


    if tipo == 2:

        return f"Nadie te dice esto: {dato}"


    if tipo == 3:

        return f"Esto cambiará tu forma de ver el mundo: {dato}"


    if tipo == 4:

        return f"El {random.choice(['90%','95%','99%'])} de las personas no sabe que {dato}"


# =====================================
# AUTH YOUTUBE
# =====================================

def get_youtube():

    with open("token.pickle","rb") as f:

        credentials = pickle.load(f)

    return googleapiclient.discovery.build(

        "youtube",
        "v3",
        credentials=credentials

    )

youtube = get_youtube()


# =====================================
# VIDEO
# =====================================

def generar():

    try:

        texto = generar_texto()
        
        if not texto:
         texto = "Dato curioso increíble"

        texto = texto.strip()

        texto = texto.replace("\n", " ")

        texto = texto.replace("\r", "")

        # limitar a 100 caracteres
        texto = texto[:100]

        # seguridad extra
        if texto == "":
            texto = "Dato curioso viral"

        print("Generando:", texto)


        # AUDIO

        tts = gTTS(texto, lang="es")

        tts.save("audio.mp3")

        audio = AudioFileClip("audio.mp3")


        # VIDEO

        tema = random.choice(TEMAS)

        headers = {"Authorization":PEXELS_API_KEY}

        url = f"https://api.pexels.com/videos/search?query={tema}&orientation=portrait"

        r = requests.get(url,headers=headers).json()

        video_url = random.choice(

            r["videos"]

        )["video_files"][0]["link"]


        open("bg.mp4","wb").write(

            requests.get(video_url).content

        )


        background = VideoFileClip("bg.mp4")


        if background.duration < audio.duration:

            background = background.loop(

                duration=audio.duration

            )


        background = background.subclip(

            0,
            audio.duration

        )


        background = background.resize(height=1920)


        background = background.crop(

            width=720,
            height=1280,
            x_center=background.w/2,
            y_center=background.h/2

        )


        # TEXTO

        img = Image.new("RGBA",(720,1280),(0,0,0,0))

        draw = ImageDraw.Draw(img)

        font = ImageFont.load_default()


        texto_wrap = textwrap.fill(texto, width=20)


        draw.text(

            (80,900),
            texto_wrap,
            font=font,
            fill="white"

        )


        txt = ImageClip(

            np.array(img)

        ).set_duration(audio.duration)


        final = CompositeVideoClip(

            [background,txt]

        )


        final = final.set_audio(audio)


        file = f"video_{int(time.time())}.mp4"


        final.write_videofile(

            file,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast"

        )


        final.close()
        audio.close()
        background.close()


        # SUBIR

        request = youtube.videos().insert(

            part="snippet,status",

            body={

                "snippet":{

                    "title": str(texto),
                    
                    "description":"Suscríbete",

                    "categoryId":CATEGORY

                },

                "status":{

                    "privacyStatus":"public"

                }

            },

            media_body=googleapiclient.http.MediaFileUpload(file)

        )


        response = request.execute()


        print("SUBIDO:",response["id"])


        os.remove(file)
        os.remove("audio.mp3")
        os.remove("bg.mp4")


    except Exception as e:

        print("ERROR:",e)


# LOOP

schedule.every(INTERVAL).minutes.do(generar)

print("BOT ACTIVO")

generar()

while True:

    schedule.run_pending()
    time.sleep(5)