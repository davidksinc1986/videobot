import time
import os
import traceback

from generador import generar_video
from voz_elevenlabs import QuotaExceededError

from subir_tiktok import subir_tiktok
from subir_instagram import subir_instagram
from subir_facebook import subir_facebook
from subir_youtube import subir_youtube


print("🔥 BOT GOD MODE ACTIVO 🔥")

INTERVALO_SEGUNDOS = 3600


def borrar_video(ruta_video):
    try:
        if os.path.exists(ruta_video):
            os.remove(ruta_video)
            print(f"🗑 Video eliminado: {ruta_video}")
    except Exception as e:
        print("❌ Error borrando video:", str(e))


def job():

    resultados = {
        "youtube": False,
        "tiktok": False,
        "instagram": False,
        "facebook": False
    }

    print("\n🎬 Generando video...")

    try:
        video, titulo = generar_video("motivacion"))
        print(f"✅ Video generado: {video}")
    except Exception:
        print("❌ Error generando video:")
        print(traceback.format_exc())
        return

    # YOUTUBE
    try:
        subir_youtube(video, titulo)
        resultados["youtube"] = True
        print("✅ YouTube OK")
    except:
        print("❌ YouTube falló")
        print(traceback.format_exc())

    # TIKTOK
    try:
        subir_tiktok(video, titulo)
        resultados["tiktok"] = True
        print("✅ TikTok OK")
    except:
        print("❌ TikTok falló")
        print(traceback.format_exc())

    # INSTAGRAM
    try:
        subir_instagram(video, titulo)
        resultados["instagram"] = True
        print("✅ Instagram OK")
    except:
        print("❌ Instagram falló")
        print(traceback.format_exc())

    # FACEBOOK
    try:
        subir_facebook(video, titulo)
        resultados["facebook"] = True
        print("✅ Facebook OK")
    except:
        print("❌ Facebook falló")
        print(traceback.format_exc())

    print("\n📊 RESULTADOS:")
    for p, estado in resultados.items():
        print(f"{p.upper()}: {'OK' if estado else 'FALLÓ'}")

    borrar_video(video)


# LOOP INTELIGENTE
while True:

    try:
        job()

    except QuotaExceededError:
        print("🚨 SIN CRÉDITOS EN ELEVENLABS")
        print("⏸ Pausando 12 horas...")
        time.sleep(43200)
        continue

    except Exception:
        print("🔥 ERROR CRÍTICO:")
        print(traceback.format_exc())

    print(f"\n⏳ Esperando {INTERVALO_SEGUNDOS} segundos...\n")
    time.sleep(INTERVALO_SEGUNDOS)