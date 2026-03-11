import os
import time
import random
import traceback
from typing import Dict, Any

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.chrome.service import Service

def _crear_driver(profile_dir: str) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()

    # Perfil dedicado del bot (persistente)
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")

    # Estabilidad
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-allow-origins=*")  # ayuda en varios Macs/Chromes

    # IMPORTANTE:
    # Service() sin ruta => Selenium Manager consigue el chromedriver correcto
    service = Service()

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(90)
    return driver


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")


def _safe_name(name: str) -> str:
    return "".join(c for c in (name or "").strip() if c.isalnum() or c in ("_", "-", ".", "-")).strip(".")


def _sessions_platform_dir(user_name: str, platform: str) -> str:
    user_name = _safe_name(user_name)
    platform = _safe_name(platform)
    p = os.path.join(SESSIONS_DIR, user_name, platform)
    os.makedirs(p, exist_ok=True)
    return p


def _crear_driver(profile_dir: str) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()

    # PERFIL DEDICADO (NO TU CHROME DEFAULT)
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")

    # ESTABILIDAD
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-extensions")

    service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(90)
    return driver


def _upload_tiktok_selenium(video_path: str, titulo: str, user_name: str) -> bool:
    print(f"🚀 TikTok Selenium para {user_name}")

    abs_video = os.path.abspath(video_path)
    if not os.path.exists(abs_video):
        print(f"❌ Video no existe: {abs_video}")
        return False

    base = _sessions_platform_dir(user_name, "tiktok")
    profile_dir = os.path.join(base, "chrome_profile")
    os.makedirs(profile_dir, exist_ok=True)

    driver = _crear_driver(profile_dir)
    wait = WebDriverWait(driver, 60)

    try:
        # 1) IR A UPLOAD
        driver.get("https://www.tiktok.com/upload")
        time.sleep(4)

        # 2) SI TE MANDA A LOGIN, SOLO LOGIN MANUAL (NO AUTOMATIZAR)
        if "login" in driver.current_url.lower():
            print("🔐 TikTok pidió login. Haz login MANUAL en esta ventana.")
            print("⏳ Esperando 90 segundos...")
            time.sleep(90)
            driver.get("https://www.tiktok.com/upload")
            time.sleep(4)

        # 3) DETECTAR BLOQUEO "TOO MANY ATTEMPTS"
        page_text = driver.page_source.lower()
        if "maximum number of attempts reached" in page_text or "too many attempts" in page_text:
            print("⛔ TikTok bloqueó por intentos. Debes esperar (6–24h) y NO reintentar seguido.")
            return False

        # 4) SUBIR ARCHIVO
        file_input = wait.until(
            EC.presence_of_element_located((By.XPATH, '//input[@type="file"]'))
        )
        file_input.send_keys(abs_video)
        print("📤 Video enviado...")

        # 5) ESCRIBIR CAPTION
        caption = wait.until(
            EC.presence_of_element_located((By.XPATH, '(//div[@contenteditable="true"])[1]'))
        )
        time.sleep(2)
        caption.click()
        time.sleep(0.5)

        # limpiar caption
        caption.send_keys(Keys.COMMAND, "a")  # Mac
        caption.send_keys(Keys.BACKSPACE)

        # escribir
        caption.send_keys(titulo)
        print("✏️ Caption listo")

        # 6) CLICK PUBLICAR (puede variar el texto)
        xpaths = [
            '//button[contains(@data-e2e,"post-video-button")]',
            '//button[contains(., "Publicar")]',
            '//button[contains(., "Post")]'
        ]

        publish_btn = None
        for xp in xpaths:
            try:
                publish_btn = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, xp))
                )
                if publish_btn:
                    break
            except:
                pass

        if not publish_btn:
            print("❌ No encontré botón Publicar/Post. Puede que el video aún esté procesando.")
            return False

        time.sleep(random.uniform(1.0, 2.0))
        publish_btn.click()
        print("✅ Click publicar")

        time.sleep(10)
        return True

    except Exception as e:
        print("❌ Error TikTok Selenium:", str(e))
        print(traceback.format_exc())
        return False

    finally:
        try:
            driver.quit()
        except:
            pass


# ✅ ESTA ES LA FUNCIÓN QUE TU SCHEDULER IMPORTA
def subir_tiktok(video_path: str, user: Dict[str, Any]) -> bool:
    user_name = (user or {}).get("nombre", "user")
    titulo = f"{(user or {}).get('nicho', 'video')} · {user_name}"
    return _upload_tiktok_selenium(video_path, titulo, user_name)