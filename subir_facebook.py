# subir_facebook.py
import os
import time
import random
import traceback
from typing import Dict, Any

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")


def _safe_name(name: str) -> str:
    return "".join(c for c in (name or "").strip() if c.isalnum() or c in ("_", "-", ".")).strip(".")


def _sessions_platform_dir(user_name: str, platform: str) -> str:
    user_name = _safe_name(user_name)
    platform = _safe_name(platform)
    p = os.path.join(SESSIONS_DIR, user_name, platform)
    os.makedirs(p, exist_ok=True)
    return p


def _nap(a=0.4, b=1.2):
    time.sleep(random.uniform(a, b))


def subir_facebook(video_path: str, user: Dict[str, Any]) -> bool:
    """
    Firma estándar para tu app.py:
      subir_facebook(video_path: str, user: dict) -> bool
    """
    user_name = (user or {}).get("nombre", "user")
    abs_video = os.path.abspath(video_path)
    if not os.path.exists(abs_video):
        print(f"❌ Video no existe: {abs_video}")
        return False

    base = _sessions_platform_dir(user_name, "facebook")
    storage_path = os.path.join(base, "storage_state.json")
    if not os.path.exists(storage_path):
        print(f"❌ Falta sesión FB: {storage_path}")
        print("👉 Usa el botón 🔐 Facebook en el panel para crearla.")
        return False

    nicho = (user or {}).get("nicho", "video")
    caption = f"{nicho} • {user_name}"

    print(f"🚀 Facebook Playwright para {user_name}")
    print(f"📎 Video: {abs_video}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"],)
        context = browser.new_context(storage_state=storage_path, viewport=None)
        page = context.new_page()

        try:
            page.goto("https://www.facebook.com/reels/create", wait_until="domcontentloaded", timeout=60000)
            _nap(1, 2)

            if "login" in page.url.lower():
                print("🔐 Sesión expirada: FB redirigió a login.")
                return False

            # Buscar input file
            file_selectors = [
                'input[type="file"]',
                'input[accept*="video"]',
            ]
            file_input = None
            for sel in file_selectors:
                loc = page.locator(sel).first
                try:
                    if loc.count() > 0:
                        loc.wait_for(state="attached", timeout=8000)
                        file_input = loc
                        break
                except Exception:
                    continue

            if file_input is None:
                # fallback: ir a home e intentar abrir composer
                page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=60000)
                _nap(1.0, 2.0)

                if "login" in page.url.lower():
                    print("🔐 Sesión expirada: FB redirigió a login.")
                    return False

                # Intentar abrir "Photo/Video" (varía)
                open_candidates = [
                    'div[role="button"]:has-text("Photo/video")',
                    'div[role="button"]:has-text("Foto/video")',
                    'span:has-text("Photo/video")',
                    'span:has-text("Foto/video")',
                ]
                opened = False
                for sel in open_candidates:
                    try:
                        b = page.locator(sel).first
                        if b.count() > 0 and b.is_visible():
                            b.click()
                            opened = True
                            _nap(1.0, 2.0)
                            break
                    except Exception:
                        continue

                # buscar file input otra vez
                for sel in file_selectors:
                    loc = page.locator(sel).first
                    try:
                        if loc.count() > 0:
                            loc.wait_for(state="attached", timeout=8000)
                            file_input = loc
                            break
                    except Exception:
                        continue

            if file_input is None:
                print("❌ No encontré input file en FB.")
                page.screenshot(path=os.path.join(base, "fb_no_file_input.png"))
                return False

            # Subir video
            file_input.set_input_files(abs_video)
            print("📤 Video enviado a FB. Esperando procesamiento...")
            _nap(6, 10)

            # Caption si aparece (best-effort)
            caption_candidates = [
                'div[role="textbox"]',
                'textarea',
            ]
            for sel in caption_candidates:
                try:
                    box = page.locator(sel).first
                    if box.count() > 0 and box.is_visible():
                        box.click()
                        _nap(0.2, 0.6)
                        for ch in caption:
                            page.keyboard.type(ch, delay=random.randint(25, 75))
                        break
                except Exception:
                    continue

            # Publicar / Post
            post_candidates = [
                'div[role="button"]:has-text("Post")',
                'div[role="button"]:has-text("Publicar")',
                'span:has-text("Post")',
                'span:has-text("Publicar")',
                'button:has-text("Post")',
                'button:has-text("Publicar")',
            ]

            posted = False
            for _ in range(14):
                for sel in post_candidates:
                    try:
                        btn = page.locator(sel).first
                        if btn.count() > 0 and btn.is_visible():
                            btn.click()
                            posted = True
                            break
                    except Exception:
                        continue
                if posted:
                    break
                _nap(1.0, 1.6)

            if not posted:
                print("❌ No encontré botón Post/Publicar.")
                page.screenshot(path=os.path.join(base, "fb_no_post_btn.png"))
                return False

            print("✅ FB: Click en Post/Publicar realizado.")
            _nap(8, 12)

            try:
                context.storage_state(path=storage_path)
            except Exception:
                pass

            return True

        except Exception as e:
            print("❌ Error Facebook:", str(e))
            print(traceback.format_exc())
            try:
                page.screenshot(path=os.path.join(base, "fb_upload_error.png"))
                print(f"🧾 Screenshot: {os.path.join(base, 'fb_upload_error.png')}")
            except Exception:
                pass
            return False
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass


# Alias opcional
upload = subir_facebook
main = subir_facebook