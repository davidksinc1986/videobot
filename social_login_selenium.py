# social_login_selenium.py
import os
import time
import argparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")

LOGIN_URLS = {
    "tiktok": "https://www.tiktok.com/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "facebook": "https://www.facebook.com/login/",
}

def _safe_name(name: str) -> str:
    return "".join(c for c in (name or "").strip() if c.isalnum() or c in ("_", "-", ".", "-")).strip(".")

def _profile_dir(user: str, platform: str) -> str:
    user = _safe_name(user)
    platform = _safe_name(platform)
    p = os.path.join(SESSIONS_DIR, user, platform, "chrome_profile")
    os.makedirs(p, exist_ok=True)
    return p

def crear_driver(profile_dir: str):
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    # No te pases con "anti automation flags": a veces empeoran.
    # options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--platform", required=True, choices=["tiktok", "instagram", "facebook"])
    ap.add_argument("--wait", type=int, default=120)  # tiempo para que loguees
    args = ap.parse_args()

    profile_dir = _profile_dir(args.user, args.platform)
    driver = crear_driver(profile_dir)

    try:
        driver.get(LOGIN_URLS[args.platform])
        print(f"🔐 Login abierto para {args.platform} ({args.user})")
        print(f"✅ Profile persistente: {profile_dir}")
        print(f"⏳ Tienes {args.wait}s para iniciar sesión manualmente...")
        time.sleep(args.wait)
        print("✅ Cerrando navegador (sesión queda guardada en el profile).")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()