# social_login.py
import os
import json
import time
import argparse

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)


def _safe_name(name: str) -> str:
    return "".join(c for c in (name or "").strip() if c.isalnum() or c in ("_", "-", ".")).strip(".")


def _platform_dir(user: str, platform: str) -> str:
    user = _safe_name(user)
    platform = _safe_name(platform)
    p = os.path.join(SESSIONS_DIR, user, platform)
    os.makedirs(p, exist_ok=True)
    return p


def _get_login_url(platform: str) -> str:
    platform = (platform or "").strip().lower()
    if platform == "instagram":
        return "https://www.instagram.com/"
    if platform == "facebook":
        return "https://www.facebook.com/"
    if platform == "tiktok":
        return "https://www.tiktok.com/"
    raise ValueError("Plataforma inválida")


def run_login(user: str, platform: str, wait_seconds: int = 180) -> bool:
    """
    Abre navegador visible para que el humano inicie sesión.
    Guarda storage_state.json en sessions/<user>/<platform>/storage_state.json
    """
    base = _platform_dir(user, platform)
    storage_path = os.path.join(base, "storage_state.json")

    url = _get_login_url(platform)

    print(f"🔐 Iniciando login manual: user={user} platform={platform}")
    print(f"📁 Guardará sesión en: {storage_path}")
    print(f"⏳ Tiempo para loguearte: {wait_seconds}s (puedes cerrar la ventana cuando termines)")

    # Usamos contexto persistente para mejorar compatibilidad con logins
    # (pero igual guardamos storage_state para que los uploaders lo reutilicen)
    profile_dir = os.path.join(base, "pw_profile")
    os.makedirs(profile_dir, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=[
                "--start-maximized",
            ],
            viewport=None,
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Espera fija: el usuario hace login manual
        t0 = time.time()
        while time.time() - t0 < wait_seconds:
            time.sleep(1.0)

        try:
            context.storage_state(path=storage_path)
            print("✅ storage_state guardado.")
        except Exception as e:
            print("❌ No se pudo guardar storage_state:", str(e))
            try:
                # debug rápido
                page.screenshot(path=os.path.join(base, f"{platform}_login_error.png"))
                print(f"🧾 Screenshot: {os.path.join(base, f'{platform}_login_error.png')}")
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            return False

        try:
            context.close()
        except Exception:
            pass

    # Validación mínima
    if os.path.exists(storage_path) and os.path.getsize(storage_path) > 200:
        return True
    return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--platform", required=True, choices=["tiktok", "instagram", "facebook"])
    ap.add_argument("--wait", type=int, default=180)
    args = ap.parse_args()

    ok = run_login(args.user, args.platform, wait_seconds=args.wait)
    print("RESULT:", ok)