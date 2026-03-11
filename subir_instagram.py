import os
import time
import random
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


# ----------------------------
# Utils
# ----------------------------

def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _nap(a=0.4, b=1.1):
    time.sleep(random.uniform(a, b))


def _safe_name(s: str) -> str:
    return "".join(c for c in (s or "").strip() if c.isalnum() or c in ("_", "-", ".")).strip(".")


def _base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _sessions_dir() -> str:
    return os.path.join(_base_dir(), "sessions")


def _ig_dir(user_name: str) -> str:
    return os.path.join(_sessions_dir(), _safe_name(user_name), "instagram")


def _storage_state_path(user_name: str) -> str:
    return os.path.join(_ig_dir(user_name), "storage_state.json")


def _save_screenshot(page, user_name: str, filename: str) -> str:
    os.makedirs(_ig_dir(user_name), exist_ok=True)
    path = os.path.join(_ig_dir(user_name), filename)
    try:
        page.screenshot(path=path, full_page=True)
    except:
        pass
    return path


def _dismiss_common_modals(page):
    buttons = [
        "Not Now", "Ahora no",
        "Cancel", "Cancelar",
        "Close", "Cerrar",
        "OK", "Ok", "Aceptar",
        "Allow all cookies", "Permitir todas las cookies",
        "Only allow essential cookies", "Permitir solo cookies esenciales",
    ]
    for txt in buttons:
        try:
            btn = page.locator(f'button:has-text("{txt}")').first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                _nap(0.3, 0.8)
        except:
            pass


def _click_ok_if_reels_modal(page, wait_ms: int = 900) -> bool:
    """
    Modal: 'Video posts are now shared as reels'
    """
    try:
        page.wait_for_timeout(wait_ms)
    except:
        pass

    ok_selectors = [
        'div[role="dialog"] button:has-text("OK")',
        'div[role="dialog"] button:has-text("Ok")',
        'div[role="dialog"] button:has-text("Aceptar")',
        'div[role="dialog"] button:has-text("Entendido")',
        'div[role="dialog"] button:has-text("De acuerdo")',
    ]

    for sel in ok_selectors:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                _nap(0.6, 1.2)
                return True
        except:
            pass

    return False


def _click_create(page) -> bool:
    # En IG web el "+" suele estar en sidebar. A veces colapsa.
    locators = [
        'a[aria-label="New post"]',
        'a[aria-label="Create"]',
        'a[aria-label="Crear"]',
        'button[aria-label="New post"]',
        'button[aria-label="Create"]',
        'button[aria-label="Crear"]',
        'div[role="button"][aria-label="New post"]',
        'div[role="button"][aria-label="Create"]',
        'div[role="button"][aria-label="Crear"]',
        'svg[aria-label="New post"]',
        'svg[aria-label="Create"]',
        'svg[aria-label="Crear"]',
    ]

    for sel in locators:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                el.click()
                _nap(0.6, 1.2)
                _dismiss_common_modals(page)
                return True
        except:
            pass

    # Fallback: si el sidebar está escondido, muchas veces hay un botón "+"
    for sel in [
        'div[role="button"]:has-text("Create")',
        'div[role="button"]:has-text("Crear")',
        'button:has-text("Create")',
        'button:has-text("Crear")',
        'div[role="button"]:has-text("+")',
    ]:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                el.click()
                _nap(0.6, 1.2)
                _dismiss_common_modals(page)
                return True
        except:
            pass

    return False


def _try_click_menu_item(page, texts: list[str]) -> bool:
    for t in texts:
        for sel in [
            f'button:has-text("{t}")',
            f'div[role="button"]:has-text("{t}")',
            f'a:has-text("{t}")',
            f'text="{t}"',
        ]:
            try:
                el = page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    el.click()
                    _nap(0.6, 1.2)
                    return True
            except:
                pass
    return False


def _find_file_input(page):
    # A veces existe, a veces NO (IG usa file chooser)
    for sel in [
        'input[type="file"]',
        'div[role="dialog"] input[type="file"]',
        'form input[type="file"]',
    ]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                return loc
        except:
            pass
    return None


def _set_file_via_chooser(page, abs_video: str) -> bool:
    """
    Si IG no muestra input[type=file], usa el botón "Select from computer"
    y captura el file chooser.
    """
    # textos comunes del botón de selección
    choose_texts = [
        "Select from computer",
        "Select from Computer",
        "Seleccionar desde la computadora",
        "Seleccionar del ordenador",
        "Seleccionar desde el ordenador",
        "Choose from computer",
        "Choose files",
        "Elegir archivos",
    ]

    # intentos por si el dialog tarda en cargar
    for _ in range(6):
        _dismiss_common_modals(page)
        _click_ok_if_reels_modal(page, wait_ms=400)

        # Busca un botón con esos textos
        btn = None
        for t in choose_texts:
            for sel in [
                f'div[role="dialog"] button:has-text("{t}")',
                f'div[role="dialog"] div[role="button"]:has-text("{t}")',
                f'button:has-text("{t}")',
                f'div[role="button"]:has-text("{t}")',
            ]:
                try:
                    loc = page.locator(sel).first
                    if loc.count() > 0 and loc.is_visible():
                        btn = loc
                        break
                except:
                    pass
            if btn:
                break

        if not btn:
            _nap(0.6, 1.1)
            continue

        # Captura file chooser y setea archivo
        try:
            with page.expect_file_chooser(timeout=5000) as fc_info:
                try:
                    btn.click()
                except:
                    btn.click(force=True)
            fc = fc_info.value
            fc.set_files(abs_video)
            _nap(1.0, 2.0)
            return True
        except:
            _nap(0.6, 1.2)
            continue

    return False


def _click_next(page, attempts=8) -> bool:
    texts = ["Next", "Siguiente", "Continue", "Continuar"]
    for _ in range(attempts):
        _dismiss_common_modals(page)
        _click_ok_if_reels_modal(page, wait_ms=500)

        for t in texts:
            for sel in [
                f'div[role="dialog"] button:has-text("{t}")',
                f'div[role="dialog"] div[role="button"]:has-text("{t}")',
                f'div[role="dialog"] a:has-text("{t}")',
                f'button:has-text("{t}")',
                f'div[role="button"]:has-text("{t}")',
                f'a:has-text("{t}")',
            ]:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        try:
                            el.click()
                        except:
                            el.click(force=True)
                        _nap(0.9, 1.6)
                        return True
                except:
                    pass

        _nap(0.8, 1.4)
    return False


def _set_caption(page, caption: str) -> bool:
    caption = (caption or "").strip()
    if not caption:
        return True

    selectors = [
        'textarea[aria-label="Write a caption…"]',
        'textarea[aria-label="Escribe un pie de foto…"]',
        'textarea[placeholder*="caption" i]',
        'textarea[placeholder*="pie de foto" i]',
        'div[role="textbox"][contenteditable="true"]',
        'div[role="textbox"]',
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                el.click()
                _nap(0.2, 0.5)
                try:
                    el.fill(caption)
                except:
                    el.type(caption, delay=10)
                _nap(0.4, 0.9)
                return True
        except:
            pass

    return False


def _locator_is_disabled(locator) -> bool:
    try:
        try:
            if hasattr(locator, "is_enabled") and not locator.is_enabled():
                return True
        except:
            pass

        aria_disabled = locator.get_attribute("aria-disabled")
        if aria_disabled and aria_disabled.lower() in ("true", "1"):
            return True

        disabled = locator.get_attribute("disabled")
        if disabled is not None:
            return True
    except:
        pass
    return False


def _click_share(page, attempts=12) -> bool:
    texts = ["Share", "Compartir", "Publish", "Publicar"]

    selectors = []
    for t in texts:
        selectors += [
            f'div[role="dialog"] a:has-text("{t}")',
            f'div[role="dialog"] button:has-text("{t}")',
            f'div[role="dialog"] div[role="button"]:has-text("{t}")',
            f'a:has-text("{t}")',
            f'button:has-text("{t}")',
            f'div[role="button"]:has-text("{t}")',
        ]

    for _ in range(attempts):
        _dismiss_common_modals(page)
        _click_ok_if_reels_modal(page, wait_ms=350)

        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.count() == 0 or not el.is_visible():
                    continue

                if _locator_is_disabled(el):
                    _nap(0.9, 1.6)
                    continue

                try:
                    el.click()
                except:
                    el.click(force=True)

                _nap(1.4, 2.4)
                return True
            except:
                pass

        _nap(1.1, 2.0)

    return False


# ----------------------------
# Main
# ----------------------------

def subir_instagram(video_path: str, user: dict) -> bool:
    user_name = _safe_name((user or {}).get("nombre", "user"))
    abs_video = os.path.abspath(video_path)

    print(f"🚀 Instagram Playwright para {user_name}")
    print(f"📎 Video: {abs_video}")

    if not os.path.exists(abs_video):
        print("❌ El archivo de video no existe.")
        return False

    ss = _storage_state_path(user_name)
    if not os.path.exists(ss):
        print(f"❌ No existe storage_state.json: {ss}")
        print("👉 Primero corre: python3 social_login.py --user <NOMBRE> --platform instagram")
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )

            context = browser.new_context(
                storage_state=ss,
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=60000)
            _nap(1.2, 2.4)
            _dismiss_common_modals(page)

            # 1) Create
            if not _click_create(page):
                shot = _save_screenshot(page, user_name, f"ig_no_create_{_now_tag()}.png")
                print("❌ No encontré botón Create/+ en IG.")
                print(f"🧾 Screenshot: {shot}")
                context.close()
                browser.close()
                return False

            # 2) Intenta seleccionar Reel/Video (si aparece)
            _try_click_menu_item(page, ["Reel", "Video", "Post", "Publicación"])
            _nap(0.8, 1.4)

            # 3) Sube archivo (input o file chooser)
            file_input = _find_file_input(page)
            if file_input:
                try:
                    file_input.set_input_files(abs_video)
                    print("📤 Video enviado al navegador (input file).")
                except:
                    file_input = None

            if not file_input:
                ok = _set_file_via_chooser(page, abs_video)
                if not ok:
                    shot = _save_screenshot(page, user_name, f"ig_no_file_input_{_now_tag()}.png")
                    print("❌ No encontré input file ni pude usar 'Select from computer'.")
                    print(f"🧾 Screenshot: {shot}")
                    context.close()
                    browser.close()
                    return False
                print("📤 Video enviado al navegador (file chooser).")

            _nap(1.4, 2.6)

            # modal opcional
            _click_ok_if_reels_modal(page, wait_ms=900)

            # 4) Next / Next
            if not _click_next(page, attempts=10):
                shot = _save_screenshot(page, user_name, f"ig_no_next_{_now_tag()}.png")
                print("⚠️ No pude encontrar el botón Next/Siguiente.")
                print(f"🧾 Screenshot: {shot}")
                context.close()
                browser.close()
                return False

            # suele haber 2do Next (crop/edit)
            _click_ok_if_reels_modal(page, wait_ms=450)
            _click_next(page, attempts=8)

            # 5) Caption
            caption = f"{(user or {}).get('nicho','video')} • {(user or {}).get('idioma','es')} #shorts"
            _set_caption(page, caption)

            # 6) Share
            if not _click_share(page, attempts=14):
                shot = _save_screenshot(page, user_name, f"ig_no_share_{_now_tag()}.png")
                print("⚠️ No pude encontrar o hacer click en Share/Compartir/Publish.")
                print(f"🧾 Screenshot: {shot}")
                context.close()
                browser.close()
                return False

            _nap(6.0, 10.0)
            _dismiss_common_modals(page)

            print("✅ Share clickeado. (Si IG no mostró error, debería estar subiendo/publicando).")
            context.close()
            browser.close()
            return True

    except PWTimeoutError as e:
        print(f"❌ Timeout Playwright: {e}")
        return False
    except Exception as e:
        print(f"❌ Error Instagram Playwright: {e}")
        return False