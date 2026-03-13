import os
import json
import time
import traceback
import threading
import shutil
import subprocess
import unicodedata
from datetime import datetime
from functools import wraps


def _load_local_env(path: str = ".env"):
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


_load_local_env()
from werkzeug.security import generate_password_hash, check_password_hash

from flask import Flask, render_template, request, redirect, jsonify, abort, make_response, session

from config import USUARIOS_DIR, TEMP_DIR, VIDEOS_DIR, APP_PORT
from generador import generar_video_usuario, NICHOS as NICHOS_DICT


# ----------------------------
# Paths / Dirs
# ----------------------------

LOCK_DIR = os.path.join(TEMP_DIR, "locks")
os.makedirs(LOCK_DIR, exist_ok=True)
os.makedirs(USUARIOS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("APP_SECRET_KEY", "change-me-in-production")


# ----------------------------
# i18n (ES/EN) simple con cookie
# ----------------------------

TRANSLATIONS = {
    "es": {
        "app_title": "Video-Bot • SaaS",
        "admin_panel": "Panel admin",
        "monitor": "Monitoreo",
        "language": "Idioma",
        "spanish": "Español",
        "english": "English",
        "portuguese": "Português",
        "switch_to_pt": "PT",
        "switch_to_es": "ES",
        "switch_to_en": "EN",
        "login": "Login",
        "logout": "Logout",
        "email": "Email",
        "password": "Password",
        "superuser": "Superuser",
        "login": "Iniciar sesión",
        "logout": "Salir",
        "email": "Correo",
        "password": "Contraseña",
        "superuser": "Superusuario",

        "create_user": "Crear usuario",
        "name_id": "Nombre (id)",
        "niche": "Nicho",
        "user_language": "Idioma",
        "create": "Crear",

        "quick_actions": "Acciones rápidas",
        "clear_videos": "Vaciar /videos",
        "clear_temp": "Vaciar audios /temp",

        "users": "Usuarios",
        "user": "Usuario",
        "status": "Estado",
        "last_video": "Último video",
        "today": "Hoy",
        "actions": "Acciones",
        "edit": "Editar",
        "generate": "Generar",
        "delete": "Eliminar",

        "user_page_title": "Configuración de Usuario",
        "config_general": "Configuración general",
        "interval_min": "Intervalo (min)",
        "max_per_day": "Máximo videos por día",
        "window_start": "Ventana inicio (HH:MM)",
        "window_end": "Ventana fin (HH:MM)",
        "final_hook": "Hook final (texto)",

        "scheduler_active": "Programador (Scheduler) activo",
        "continue_if_fail": "Continuar si una plataforma falla",

        "api_creds_optional": "Credenciales API (opcional)",
        "api_creds_hint": "Estas credenciales son para servicios externos (Pexels/ElevenLabs). No afectan el login de redes sociales.",
        "pexels_key": "Pexels API key",
        "eleven_key": "ElevenLabs API key",
        "eleven_voice": "ID de Voz ElevenLabs",
        "content_source": "Fuente de guion",
        "content_ai": "IA generada",
        "content_file": "Archivo de textos",
        "content_file_path": "Ruta de archivo de textos",
        "content_file_help": "Ejemplo: nichos/motivacion.txt (1 idea por línea)",
        "voice_provider": "Proveedor de voz",
        "video_provider": "Proveedor de video",
        "script_provider": "Proveedor de guion IA",
        "openai_key": "OpenAI API key",
        "pixabay_key": "Pixabay API key (opcional)",

        "platforms": "Plataformas (Activar + Método)",
        "active": "Activo",
        "yt_backend": "YouTube Backend",
        "yt_auth": "Método de Auth YouTube",
        "yt_legacy": "Legacy (token.pickle global)",
        "yt_token_upload": "Token Upload (por usuario)",
        "yt_oauth_web": "Login por navegador (Próximamente)",
        "yt_token_hint": "Si usas 'token_upload', sube tu archivo token.pickle en el panel derecho.",

        "tt_backend": "TikTok Backend",
        "ig_backend": "Instagram Backend",
        "fb_backend": "Facebook Backend",
        "meta_creds": "Credenciales Meta / TikTok API",
        "meta_app_id": "Meta App ID",
        "meta_app_secret": "Meta App Secret",
        "ig_user_id": "Instagram User ID",
        "fb_page_id": "Facebook Page ID",
        "meta_token": "Meta Long Lived Token",

        "note": "Nota",
        "recommended_pw": "Recomendado: Playwright (más estable para evitar bloqueos).",
        "session": "Sesión",

        "save": "Guardar cambios",
        "back": "Volver al inicio",

        "upload_creds_sessions": "Archivos de Sesión / Credenciales",
        "david_legacy_info": "El usuario 'David' usa el token global del sistema.",
        "yt_upload_info": "Sube aquí el token.pickle generado para este usuario.",
        "upload_to_youtube": "Subir a YouTube",
        "social_upload_info": "Sube aquí archivos cookies.json o storage_state.json para Playwright/Selenium.",
        "upload_to_tiktok": "Subir a TikTok",
        "upload_to_instagram": "Subir a Instagram",
        "upload_to_facebook": "Subir a Facebook",

        "login_start": "Iniciar login manual",
        "login_help": "Esto abrirá una ventana para capturar la sesión del navegador.",

        "last_run": "Última ejecución",
        "last_error": "Último error registrado",
        "videos_today": "Videos generados hoy",

        "uploads": "Historial de Subidas",
        "last_uploads": "Últimos intentos",
        "platform": "Plataforma",
        "result": "Resultado",
        "when": "Fecha/Hora",
        "error": "Detalle Error",
        "ok": "EXITOSO",
        "fail": "FALLIDO",
        "none": "Ninguno",
    },
    "en": {
        "app_title": "Video-Bot • SaaS",
        "admin_panel": "Admin panel",
        "monitor": "Monitoring",
        "language": "Language",
        "spanish": "Español",
        "english": "English",
        "portuguese": "Português",
        "switch_to_pt": "PT",
        "switch_to_es": "ES",
        "switch_to_en": "EN",
        "login": "Iniciar sesión",
        "logout": "Salir",
        "email": "Correo",
        "password": "Contraseña",
        "superuser": "Superusuario",

        "create_user": "Create user",
        "name_id": "Name (id)",
        "niche": "Niche",
        "user_language": "Language",
        "create": "Create",

        "quick_actions": "Quick actions",
        "clear_videos": "Clear /videos",
        "clear_temp": "Clear audio /temp",

        "users": "Users",
        "user": "User",
        "status": "Status",
        "last_video": "Last video",
        "today": "Today",
        "actions": "Actions",
        "edit": "Edit",
        "generate": "Generate",
        "delete": "Delete",

        "user_page_title": "User Configuration",
        "config_general": "General settings",
        "interval_min": "Interval (min)",
        "max_per_day": "Max videos per day",
        "window_start": "Window start (HH:MM)",
        "window_end": "Window end (HH:MM)",
        "final_hook": "Final hook (text)",

        "scheduler_active": "Scheduler active",
        "continue_if_fail": "Continue if a platform fails",

        "api_creds_optional": "API credentials (optional)",
        "api_creds_hint": "These credentials are for external services (Pexels/ElevenLabs). Social logins are not affected.",
        "pexels_key": "Pexels API key",
        "eleven_key": "ElevenLabs API key",
        "eleven_voice": "ElevenLabs Voice ID",
        "content_source": "Script source",
        "content_ai": "AI generated",
        "content_file": "Text file",
        "content_file_path": "Text file path",
        "content_file_help": "Example: nichos/motivacion.txt (1 idea per line)",
        "voice_provider": "Voice provider",
        "video_provider": "Video provider",
        "script_provider": "AI script provider",
        "openai_key": "OpenAI API key",
        "pixabay_key": "Pixabay API key (optional)",

        "platforms": "Platforms (Enable + Method)",
        "active": "Active",
        "yt_backend": "YouTube Backend",
        "yt_auth": "YouTube Auth Method",
        "yt_legacy": "Legacy (global token.pickle)",
        "yt_token_upload": "Token Upload (per user)",
        "yt_oauth_web": "Browser login (Coming Soon)",
        "yt_token_hint": "If using 'token_upload', upload the token.pickle file in the right panel.",

        "tt_backend": "TikTok Backend",
        "ig_backend": "Instagram Backend",
        "fb_backend": "Facebook Backend",
        "meta_creds": "Meta / TikTok API Credentials",
        "meta_app_id": "Meta App ID",
        "meta_app_secret": "Meta App Secret",
        "ig_user_id": "Instagram User ID",
        "fb_page_id": "Facebook Page ID",
        "meta_token": "Meta Long Lived Token",

        "note": "Note",
        "recommended_pw": "Recommended: Playwright (more stable to avoid blocks).",
        "session": "Session",

        "save": "Save changes",
        "back": "Back to home",

        "upload_creds_sessions": "Session Files / Credentials",
        "david_legacy_info": "User 'David' uses the system's global token.",
        "yt_upload_info": "Upload the token.pickle generated for this user here.",
        "upload_to_youtube": "Upload to YouTube",
        "social_upload_info": "Upload cookies.json or storage_state.json for Playwright/Selenium here.",
        "upload_to_tiktok": "Upload to TikTok",
        "upload_to_instagram": "Upload to Instagram",
        "upload_to_facebook": "Upload to Facebook",

        "login_start": "Start manual login",
        "login_help": "This will open a browser window to capture the session.",

        "last_run": "Last run",
        "last_error": "Last recorded error",
        "videos_today": "Videos generated today",

        "uploads": "Upload History",
        "last_uploads": "Latest attempts",
        "platform": "Platform",
        "result": "Result",
        "when": "Date/Time",
        "error": "Error Details",
        "ok": "SUCCESS",
        "fail": "FAILED",
        "none": "None",
    }
}

PT_OVERRIDES = {
    "app_title": "Video-Bot • SaaS",
    "admin_panel": "Painel admin",
    "monitor": "Monitoramento",
    "create_user": "Criar usuário",
    "name_id": "Nome (id)",
    "niche": "Nicho",
    "user_language": "Idioma",
    "quick_actions": "Ações rápidas",
    "users": "Usuários",
    "edit": "Editar",
    "generate": "Gerar",
    "delete": "Excluir",
    "save": "Salvar alterações",
    "back": "Voltar",
    "status": "Status",
    "language": "Idioma",
    "spanish": "Español",
    "english": "English",
    "portuguese": "Português",
    "login": "Entrar",
    "logout": "Sair",
    "email": "Email",
    "password": "Senha",
    "content_source": "Fonte de roteiro",
    "content_ai": "IA gerada",
    "content_file": "Arquivo de textos",
    "content_file_path": "Caminho do arquivo",
    "voice_provider": "Provedor de voz",
    "video_provider": "Provedor de vídeo",
    "script_provider": "Provedor de roteiro IA",
}
TRANSLATIONS["pt"] = {**TRANSLATIONS["en"], **PT_OVERRIDES}


def get_lang() -> str:
    q = (request.args.get("lang") or "").strip().lower()
    if q in ("es", "en", "pt"):
        return q
    c = (request.cookies.get("lang") or "").strip().lower()
    if c in ("es", "en", "pt"):
        return c
    return "es"


def tr() -> dict:
    lang = get_lang()
    return TRANSLATIONS.get(lang, TRANSLATIONS["es"])


@app.route("/set-lang/<lang>")
def set_lang(lang):
    lang = (lang or "").strip().lower()
    if lang not in ("es", "en", "pt"):
        lang = "es"

    next_url = request.args.get("next") or "/"
    resp = make_response(redirect(next_url))
    resp.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp



# ----------------------------
# Auth / Roles
# ----------------------------

def _superuser_config() -> dict:
    email = (os.getenv("SUPERUSER_EMAIL") or "davidksinc@gmail.com").strip().lower()
    pwd = os.getenv("SUPERUSER_PASSWORD") or "M@davi19!"
    return {"email": email, "password": pwd}


def current_auth() -> dict:
    role = (session.get("role") or "").strip()
    if role == "superuser":
        return {"role": "superuser", "email": session.get("email", "")}
    if role == "tenant":
        return {"role": "tenant", "email": session.get("email", ""), "user": session.get("user", "")}
    return {"role": "anon"}


def login_required(fn):
    @wraps(fn)
    def _w(*args, **kwargs):
        if current_auth().get("role") == "anon":
            return redirect("/login")
        return fn(*args, **kwargs)
    return _w


def superuser_required(fn):
    @wraps(fn)
    def _w(*args, **kwargs):
        if current_auth().get("role") != "superuser":
            abort(403, "Solo superusuario")
        return fn(*args, **kwargs)
    return _w


def can_access_user(nombre: str) -> bool:
    auth = current_auth()
    if auth.get("role") == "superuser":
        return True
    return auth.get("role") == "tenant" and _safe_name(auth.get("user", "")) == _safe_name(nombre)


def _coerce_email(email: str) -> str:
    return (email or "").strip().lower()


def _pick_allowed(value: str, allowed: list[str], default: str) -> str:
    v = (value or "").strip().lower()
    return v if v in allowed else default


def _find_user_by_email(email: str):
    email = _coerce_email(email)
    if not email:
        return None
    for u in list_users():
        if _coerce_email(u.get("email", "")) == email:
            return ensure_defaults(u)
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", lang=get_lang(), t=tr(), error="")

    email = _coerce_email(request.form.get("email", ""))
    password = request.form.get("password", "")

    su = _superuser_config()
    if email == su["email"] and password == su["password"]:
        session["role"] = "superuser"
        session["email"] = email
        session.pop("user", None)
        return redirect("/")

    user = _find_user_by_email(email)
    if user and (user.get("password_hash") or "") and check_password_hash(user.get("password_hash"), password):
        session["role"] = "tenant"
        session["email"] = email
        session["user"] = user.get("nombre", "")
        return redirect(f"/usuario/{user.get('nombre','')}")

    return render_template("login.html", lang=get_lang(), t=tr(), error="Credenciales inválidas")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ----------------------------
# Helpers
# ----------------------------

def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_name(nombre: str) -> str:
    return "".join(c for c in (nombre or "").strip() if c.isalnum() or c in ("_", "-", ".")).strip(".")


def user_path(nombre: str) -> str:
    nombre = _safe_name(nombre)
    return os.path.join(USUARIOS_DIR, f"{nombre}.json")


def user_data_dir(nombre: str) -> str:
    nombre = _safe_name(nombre)
    p = os.path.join(SESSIONS_DIR, nombre)
    os.makedirs(p, exist_ok=True)
    return p


def platform_dir(nombre: str, plataforma: str) -> str:
    plataforma = _safe_name(plataforma)
    p = os.path.join(user_data_dir(nombre), plataforma)
    os.makedirs(p, exist_ok=True)
    return p


def content_sources_dir(nombre: str) -> str:
    p = os.path.join(user_data_dir(nombre), "content_sources")
    os.makedirs(p, exist_ok=True)
    return p


def premium_backgrounds_dir(nombre: str) -> str:
    p = os.path.join(user_data_dir(nombre), "premium_backgrounds")
    os.makedirs(p, exist_ok=True)
    return p


def _list_uploaded_files(path: str) -> list[str]:
    if not os.path.isdir(path):
        return []
    files = []
    for fn in sorted(os.listdir(path)):
        full = os.path.join(path, fn)
        if os.path.isfile(full):
            files.append(fn)
    return files


def _save_uploaded_file(file_obj, dest_dir: str, replace: bool = False) -> str:
    filename = _safe_name(getattr(file_obj, "filename", "") or "")
    if not filename:
        raise ValueError("Archivo inválido")

    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, filename)
    if os.path.exists(dest_path) and not replace:
        raise FileExistsError(filename)

    file_obj.save(dest_path)
    try:
        os.chmod(dest_path, 0o600)
    except Exception:
        pass
    return filename


def load_user(nombre: str) -> dict:
    p = user_path(nombre)
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user(user: dict) -> None:
    up = user_path(user["nombre"])
    with open(up, "w", encoding="utf-8") as f:
        json.dump(user, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(up, 0o600)
    except Exception:
        pass


def list_users() -> list:
    users = []
    if not os.path.exists(USUARIOS_DIR):
        return users
    for fn in os.listdir(USUARIOS_DIR):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(USUARIOS_DIR, fn), "r", encoding="utf-8") as f:
                    users.append(json.load(f))
            except:
                pass
    users.sort(key=lambda x: x.get("nombre", "").lower())
    return users


def is_admin_legacy_user(user: dict) -> bool:
    return (user.get("nombre", "").strip().lower() == "david")


def list_nichos() -> list:
    try:
        if not isinstance(NICHOS_DICT, dict):
            print("⚠️ NICHOS_DICT no es dict. Revisar generador.py")
            return ["motivacion"]

        keys = [
            k.strip()
            for k in NICHOS_DICT.keys()
            if isinstance(k, str) and k.strip()
        ]

        if not keys:
            print("⚠️ NICHOS_DICT vacío en generador.py")
            return ["motivacion"]

        print(f"✅ Nichos cargados desde generador.py: {len(keys)}")
        return sorted(set(keys), key=lambda s: s.lower())

    except Exception as e:
        print("❌ Error cargando nichos desde generador.py:", str(e))
        return ["motivacion"]


def _short_error(tb: str, max_chars: int = 1400) -> str:
    tb = (tb or "").strip()
    if len(tb) <= max_chars:
        return tb
    return tb[-max_chars:]


def _append_event(user: dict, kind: str, message: str, extra=None):
    ev = {
        "ts": int(time.time()),
        "at": _now_str(),
        "kind": kind,
        "message": message,
    }
    if extra and isinstance(extra, dict):
        ev["extra"] = extra

    events = user.get("events", [])
    if not isinstance(events, list):
        events = []
    events.append(ev)

    if len(events) > 200:
        events = events[-200:]
    user["events"] = events


# ✅ FIX NICHO: normalizar + validar contra lista real
def _strip_accents(s: str) -> str:
    s = s or ""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _normalize_nicho(raw: str) -> str:
    """
    Convierte valores tipo:
      "Afiliados" -> "afiliados"
      "Negocios Online" -> "negocios_online"
      "Finanzas Personales" -> "finanzas_personales"
      "product reviews" -> "product_reviews"
    """
    s = (raw or "").strip()
    s = _strip_accents(s)
    s = s.replace("-", " ")
    s = s.replace("/", " ")
    s = s.replace(".", " ")
    s = s.replace("__", "_")
    s = s.lower()
    # espacios -> underscore
    s = "_".join([p for p in s.split() if p])
    s = s.replace("__", "_").strip("_")
    return s


def _coerce_valid_nicho(raw: str, valid_nichos: list[str], fallback: str) -> str:
    """
    Intenta hacer match:
    - exacto
    - normalizado
    - normalizado comparando con normalizados
    """
    valid = [v for v in valid_nichos if isinstance(v, str) and v.strip()]
    if not valid:
        return fallback or "motivacion"

    raw_s = (raw or "").strip()
    if raw_s in valid:
        return raw_s

    norm = _normalize_nicho(raw_s)
    if norm in valid:
        return norm

    # mapa normalizado -> original
    norm_map = {_normalize_nicho(v): v for v in valid}
    if norm in norm_map:
        return norm_map[norm]

    return fallback if (fallback in valid) else valid[0]


def ensure_defaults(user: dict) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    valid_nichos = list_nichos()

    defaults = {
        "estado": "inactivo",
        "ultimo_run": "",
        "ultimo_video": "",
        "ultimo_error": "",
        "last_run_ts": 0,

        "intervalo_minutos": 60,
        "activo_scheduler": True,

        "max_videos_dia": 24,
        "videos_hoy": 0,
        "videos_hoy_fecha": today,

        "ventana_inicio": "08:00",
        "ventana_fin": "22:00",

        "idioma": "es",
        "tenant_id": "default",
        "plan": "starter",
        "nicho": valid_nichos[0] if valid_nichos else "motivacion",
        "target_seconds": 30,
        "hook_final": "Suscríbete para más 🔥",
        "content_source": "ai",
        "content_file_path": "",
        "speech_history": [],
        "voice_provider": "gtts",
        "video_provider": "pixabay",
        "premium_backgrounds_enabled": False,
        "premium_backgrounds_dir": "",
        "premium_backgrounds_allowance": 0,
        "script_provider": "local",
        "email": "",
        "password_hash": "",
        "avatar_mode": "none",
        "avatar_prompt": "",
        "avatar_image_path": "",

        "youtube_activo": True,
        "tiktok_activo": False,
        "instagram_activo": False,
        "facebook_activo": False,

        "continuar_si_falla": True,

        "youtube_auth_method": "legacy",
        "youtube_backend": "api",

        "tiktok_backend": "playwright",
        "instagram_backend": "playwright",
        "facebook_backend": "playwright",

        "upload_status": {
            "youtube": {"ok": None, "at": "", "detail": ""},
            "tiktok": {"ok": None, "at": "", "detail": ""},
            "instagram": {"ok": None, "at": "", "detail": ""},
            "facebook": {"ok": None, "at": "", "detail": ""},
        },

        "events": [],

        "credenciales": {
            "pexels_api_key": "",
            "pixabay_api_key": "",
            "elevenlabs_api_key": "",
            "eleven_voice_id": "",
            "openai_api_key": "",

            "tiktok_client_key": "",
            "tiktok_client_secret": "",
            "tiktok_access_token": "",
            "tiktok_refresh_token": "",

            "meta_app_id": "",
            "meta_app_secret": "",
            "ig_user_id": "",
            "fb_page_id": "",
            "meta_long_lived_token": "",
        }
    }

    changed = False

    for k, v in defaults.items():
        if k not in user:
            user[k] = v
            changed = True

    cred_defaults = defaults["credenciales"]
    cred = user.get("credenciales")
    if not isinstance(cred, dict):
        user["credenciales"] = dict(cred_defaults)
        changed = True
    else:
        for ck, cv in cred_defaults.items():
            if ck not in cred:
                cred[ck] = cv
                changed = True

    # ✅ FIX NICHO (no reventar selección por mayúsculas/espacios/tildes)
    current = user.get("nicho", "")
    coerced = _coerce_valid_nicho(current, valid_nichos, defaults["nicho"])
    if current != coerced:
        print(f"⚠️ Nicho ajustado: '{current}' -> '{coerced}'")
        user["nicho"] = coerced
        changed = True

    # reset diario
    if user.get("videos_hoy_fecha") != today:
        user["videos_hoy_fecha"] = today
        user["videos_hoy"] = 0
        changed = True

    if changed and user.get("nombre"):
        try:
            save_user(user)
        except:
            pass

    return user


PLAN_PLATFORM_RULES = {
    "starter": ["youtube"],
    "growth": ["youtube", "tiktok", "instagram"],
    "scale": ["youtube", "tiktok", "instagram", "facebook"],
}


def _pick_plan(raw: str) -> str:
    p = (raw or "").strip().lower()
    return p if p in PLAN_PLATFORM_RULES else "starter"


def _plan_allowed_platforms(plan: str) -> set[str]:
    return set(PLAN_PLATFORM_RULES.get(_pick_plan(plan), PLAN_PLATFORM_RULES["starter"]))


# ----------------------------
# Locks
# ----------------------------

def lock_file(nombre: str) -> str:
    return os.path.join(LOCK_DIR, f"{_safe_name(nombre)}.lock")


def is_locked(nombre: str) -> bool:
    return os.path.exists(lock_file(nombre))


def try_acquire_lock(nombre: str) -> bool:
    lf = lock_file(nombre)
    try:
        fd = os.open(lf, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(time.time()).encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_lock(nombre: str) -> None:
    lf = lock_file(nombre)
    try:
        if os.path.exists(lf):
            os.remove(lf)
    except:
        pass


# ----------------------------
# Cleanup helpers
# ----------------------------

def clear_videos_dir() -> dict:
    deleted = 0
    errors = 0
    for name in os.listdir(VIDEOS_DIR):
        p = os.path.join(VIDEOS_DIR, name)
        try:
            if os.path.isfile(p):
                os.remove(p)
                deleted += 1
            elif os.path.isdir(p):
                shutil.rmtree(p)
                deleted += 1
        except:
            errors += 1
    return {"deleted": deleted, "errors": errors}


def clear_temp_audio() -> dict:
    audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
    deleted = 0
    errors = 0
    for name in os.listdir(TEMP_DIR):
        p = os.path.join(TEMP_DIR, name)
        try:
            if os.path.isdir(p):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in audio_exts:
                os.remove(p)
                deleted += 1
        except:
            errors += 1
    return {"deleted": deleted, "errors": errors}


# ----------------------------
# Uploaders + monitoring
# ----------------------------

def _set_upload_status(user: dict, plataforma: str, ok: bool, detail: str):
    if "upload_status" not in user or not isinstance(user["upload_status"], dict):
        user["upload_status"] = {}
    if plataforma not in user["upload_status"] or not isinstance(user["upload_status"][plataforma], dict):
        user["upload_status"][plataforma] = {"ok": None, "at": "", "detail": ""}

    user["upload_status"][plataforma]["ok"] = bool(ok)
    user["upload_status"][plataforma]["at"] = _now_str()
    user["upload_status"][plataforma]["detail"] = (detail or "")[:800]


def _call_youtube_uploader(video_path: str, titulo: str, user: dict) -> bool:
    from subir_youtube import subir_youtube

    if is_admin_legacy_user(user):
        return bool(subir_youtube(video_path, titulo))

    method = (user.get("youtube_auth_method") or "token_upload").strip()
    if method != "token_upload":
        raise RuntimeError("YouTube auth_method=oath_web aún no implementado")

    user_token = os.path.join(SESSIONS_DIR, _safe_name(user["nombre"]), "youtube", "token.pickle")
    if not os.path.exists(user_token):
        raise FileNotFoundError(f"Falta token.pickle del usuario en: {user_token}")

    global_token = os.path.join(BASE_DIR, "token.pickle")
    backup_token = os.path.join(BASE_DIR, "token.pickle.bak_user")
    had_global = os.path.exists(global_token)

    if had_global:
        shutil.copy2(global_token, backup_token)
    shutil.copy2(user_token, global_token)

    try:
        return bool(subir_youtube(video_path, titulo))
    finally:
        try:
            if os.path.exists(global_token):
                os.remove(global_token)
        except:
            pass
        try:
            if had_global and os.path.exists(backup_token):
                shutil.copy2(backup_token, global_token)
                os.remove(backup_token)
        except:
            pass


def _call_social_uploader(module_name: str, func_candidates: list[str], video_path: str, user: dict) -> bool:
    mod = __import__(module_name, fromlist=["*"])
    fn = None
    for name in func_candidates:
        if hasattr(mod, name):
            fn = getattr(mod, name)
            break
    if not fn:
        raise RuntimeError(f"No encontré función upload en {module_name}. Probé: {func_candidates}")

    try:
        return bool(fn(video_path, user))
    except TypeError:
        return bool(fn(video_path))


def run_uploads_for_user(user: dict, video_path: str) -> dict:
    results = {}
    titulo = f"{user.get('nicho','video')}-{user.get('nombre','user')}-{int(time.time())}"

    def do_platform(name: str, active: bool, runner):
        if not active:
            results[name] = {"skipped": True}
            return True

        _append_event(user, "upload_start", f"Iniciando upload: {name}", {"video": video_path})
        try:
            ok = runner()
            results[name] = {"ok": bool(ok)}
            _set_upload_status(user, name, bool(ok), "OK" if ok else "Falló (sin detalle)")
            _append_event(user, "upload_done", f"Upload {name}: {'OK' if ok else 'FALLÓ'}")
            return bool(ok)
        except Exception:
            tb = _short_error(traceback.format_exc())
            results[name] = {"ok": False, "error": tb}
            _set_upload_status(user, name, False, tb)
            _append_event(user, "upload_error", f"Upload {name}: ERROR", {"error": tb})
            return False

    ok_y = do_platform(
        "youtube",
        bool(user.get("youtube_activo")),
        lambda: _call_youtube_uploader(video_path, titulo, user)
    )
    if not ok_y and not user.get("continuar_si_falla", True):
        return results

    ok_tt = do_platform(
        "tiktok",
        bool(user.get("tiktok_activo")),
        lambda: _call_social_uploader("subir_tiktok", ["subir_tiktok", "upload", "main"], video_path, user)
    )
    if not ok_tt and not user.get("continuar_si_falla", True):
        return results

    ok_ig = do_platform(
        "instagram",
        bool(user.get("instagram_activo")),
        lambda: _call_social_uploader("subir_instagram", ["subir_instagram", "upload", "main"], video_path, user)
    )
    if not ok_ig and not user.get("continuar_si_falla", True):
        return results

    ok_fb = do_platform(
        "facebook",
        bool(user.get("facebook_activo")),
        lambda: _call_social_uploader("subir_facebook", ["subir_facebook", "upload", "main"], video_path, user)
    )
    if not ok_fb and not user.get("continuar_si_falla", True):
        return results

    return results


# ----------------------------
# Background job (generar + subir)
# ----------------------------

def run_job_for_user(nombre: str) -> None:
    if not try_acquire_lock(nombre):
        return

    try:
        user = ensure_defaults(load_user(nombre))

        user["estado"] = "generando"
        user["ultimo_error"] = ""
        user["ultimo_run"] = _now_str()
        user["last_run_ts"] = int(time.time())
        _append_event(user, "job_start", "Job iniciado")
        save_user(user)

        _append_event(user, "generate_start", "Generación de video iniciada")
        out = generar_video_usuario(user)
        save_user(user)
        video_path = out.get("video_path") if isinstance(out, dict) else str(out)

        if not video_path:
            raise RuntimeError("generar_video_usuario no devolvió video_path válido")

        _append_event(user, "generate_done", "Generación completada", {"video": video_path})

        user = ensure_defaults(load_user(nombre))
        user["estado"] = "subiendo"
        user["ultimo_video"] = video_path
        user["ultimo_error"] = ""
        user["ultimo_run"] = _now_str()
        user["last_run_ts"] = int(time.time())
        save_user(user)

        user = ensure_defaults(load_user(nombre))
        upload_results = run_uploads_for_user(user, video_path)
        save_user(user)

        user = ensure_defaults(load_user(nombre))
        user["estado"] = "completado"
        user["ultimo_video"] = video_path
        user["ultimo_error"] = ""
        user["ultimo_run"] = _now_str()
        user["last_run_ts"] = int(time.time())

        today = datetime.now().strftime("%Y-%m-%d")
        if user.get("videos_hoy_fecha") != today:
            user["videos_hoy_fecha"] = today
            user["videos_hoy"] = 0
        user["videos_hoy"] = int(user.get("videos_hoy", 0)) + 1

        _append_event(user, "job_done", "Job completado", {"uploads": upload_results})
        save_user(user)

    except Exception:
        tb = _short_error(traceback.format_exc())
        try:
            user = ensure_defaults(load_user(nombre))
            user["estado"] = "error"
            user["ultimo_error"] = tb
            user["ultimo_run"] = _now_str()
            user["last_run_ts"] = int(time.time())
            _append_event(user, "job_error", "Job falló", {"error": tb})
            save_user(user)
        except:
            pass
    finally:
        release_lock(nombre)


# ----------------------------
# Routes
# ----------------------------

@app.route("/usuario/<nombre>/reset/<plataforma>", methods=["POST"])
@login_required
def usuario_reset(nombre, plataforma):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    nombre = _safe_name(nombre)
    plataforma = _safe_name(plataforma)

    if plataforma not in ("youtube", "tiktok", "instagram", "facebook"):
        abort(400, "Plataforma inválida")

    if not os.path.exists(user_path(nombre)):
        abort(404, f"Usuario no existe: {nombre}")

    base_user = os.path.join(SESSIONS_DIR, nombre)

    deleted = []
    def rm(p):
        try:
            if os.path.exists(p):
                os.remove(p)
                deleted.append(p)
        except:
            pass

    if plataforma == "youtube":
        rm(os.path.join(base_user, "youtube", "token.pickle"))
        rm(os.path.join(base_user, "youtube", "token.json"))
    else:
        rm(os.path.join(base_user, plataforma, "storage_state.json"))
        rm(os.path.join(base_user, plataforma, "cookies.json"))

    try:
        user = ensure_defaults(load_user(nombre))
        _append_event(user, "reset_creds", f"Credenciales eliminadas: {plataforma}", {"deleted": deleted})
        save_user(user)
    except:
        pass

    return redirect(f"/usuario/{nombre}")


@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "time": _now_str(),
        "usuarios_dir": USUARIOS_DIR,
        "videos_dir": VIDEOS_DIR,
        "temp_dir": TEMP_DIR,
        "sessions_dir": SESSIONS_DIR,
        "nichos_count": len(list_nichos()),
        "static_dir": os.path.abspath("static"),
        "templates_dir": os.path.abspath("templates"),
    })


@app.route("/")
@login_required
def home():
    lang = get_lang()
    auth = current_auth()
    usuarios = [ensure_defaults(u) for u in list_users()]
    if auth.get("role") == "tenant":
        usuarios = [u for u in usuarios if _safe_name(u.get("nombre","")) == _safe_name(auth.get("user",""))]
    nichos = list_nichos()

    return render_template(
        "index.html",
        usuarios=usuarios,
        nichos=nichos,
        lang=lang,
        t=tr(),
        auth=auth
    )


@app.route("/monitor")
@login_required
@superuser_required
def monitor():
    lang = get_lang()
    usuarios = [ensure_defaults(u) for u in list_users()]

    events = []
    for u in usuarios:
        name = u.get("nombre")
        evs = u.get("events", [])
        if isinstance(evs, list):
            for ev in evs[-50:]:
                e = dict(ev)
                e["user"] = name
                events.append(e)

    events.sort(key=lambda e: int(e.get("ts", 0)), reverse=True)
    events = events[:200]

    return render_template("monitor.html", usuarios=usuarios, events=events, lang=lang, t=tr())


@app.route("/crear", methods=["POST"])
@login_required
@superuser_required
def crear():
    nombre = _safe_name(request.form.get("nombre", "").strip())
    idioma = request.form.get("idioma", "es").strip().lower()

    valid_nichos = list_nichos()
    raw_nicho = request.form.get("nicho", "motivacion")
    nicho = _coerce_valid_nicho(raw_nicho, valid_nichos, "motivacion")  # ✅ FIX NICHO

    if not nombre:
        return redirect("/")

    email_login = _coerce_email(request.form.get("email", ""))
    raw_pw = request.form.get("password", "").strip()
    if not email_login or not raw_pw:
        abort(400, "Debes definir correo y contraseña para el usuario")

    try:
        target_seconds = int(request.form.get("target_seconds", 30) or 30)
    except Exception:
        target_seconds = 30

    user = ensure_defaults({
        "nombre": nombre,
        "tenant_id": _safe_name(request.form.get("tenant_id", "default")) or "default",
        "plan": _pick_plan(request.form.get("plan", "starter")),
        "nicho": nicho,
        "idioma": idioma if idioma in ("es", "en", "pt") else "es",
        "target_seconds": max(20, min(45, target_seconds)),
        "content_source": _pick_allowed(request.form.get("content_source", "ai"), ["ai", "file"], "ai"),
        "content_file_path": "",
        "voice_provider": _pick_allowed(request.form.get("voice_provider", "gtts"), ["auto", "elevenlabs", "gtts"], "gtts"),
        "video_provider": _pick_allowed(request.form.get("video_provider", "pixabay"), ["auto", "library", "pexels", "pixabay", "fallback"], "pixabay"),
        "script_provider": _pick_allowed(request.form.get("script_provider", "local"), ["local", "openai"], "local"),
        "email": email_login,
        "password_hash": generate_password_hash(raw_pw),
    })

    if not os.path.exists(user_path(nombre)):
        save_user(user)

    content_file = request.files.get("content_file")
    if content_file and content_file.filename:
        try:
            saved = _save_uploaded_file(content_file, content_sources_dir(nombre), replace=True)
            user = ensure_defaults(load_user(nombre))
            user["content_source"] = "file"
            user["content_file_path"] = f"sessions/{nombre}/content_sources/{saved}"
            save_user(user)
        except Exception:
            pass

    return redirect("/")


@app.route("/generar/<nombre>")
@login_required
def generar(nombre):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    if not os.path.exists(user_path(nombre)):
        abort(404, f"Usuario no existe: {nombre}")

    th = threading.Thread(target=run_job_for_user, args=(nombre,), daemon=True)
    th.start()
    return redirect("/")


@app.route("/usuario/<nombre>")
@login_required
def usuario(nombre):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    lang = get_lang()

    try:
        user = ensure_defaults(load_user(nombre))
    except FileNotFoundError:
        abort(404, f"Usuario no existe: {nombre}")

    user["_is_david_legacy"] = is_admin_legacy_user(user)
    user["_user_sessions_dir"] = user_data_dir(user["nombre"])
    user["_content_source_files"] = _list_uploaded_files(content_sources_dir(user["nombre"]))
    user["_premium_background_files"] = _list_uploaded_files(premium_backgrounds_dir(user["nombre"]))
    nichos = list_nichos()

    return render_template(
        "user.html",
        user=user,
        nichos=nichos,
        lang=lang,
        t=tr(),
        auth=current_auth()
    )


@app.route("/usuario/<nombre>/guardar", methods=["POST"])
@login_required
def usuario_guardar(nombre):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    auth = current_auth()
    is_super = auth.get("role") == "superuser"
    user = ensure_defaults(load_user(nombre))

    valid_nichos = list_nichos()
    raw_nicho = request.form.get("nicho", user.get("nicho", "motivacion"))
    user["nicho"] = _coerce_valid_nicho(raw_nicho, valid_nichos, user.get("nicho", "motivacion"))  # ✅ FIX NICHO

    idioma = request.form.get("idioma", user.get("idioma", "es")).lower()
    user["idioma"] = idioma if idioma in ("es", "en", "pt") else "es"

    user["hook_final"] = request.form.get("hook_final", user.get("hook_final", "Suscríbete para más 🔥")).strip()
    user["content_source"] = _pick_allowed(request.form.get("content_source", user.get("content_source", "ai")), ["ai", "file"], "ai")
    user["content_file_path"] = request.form.get("content_file_path", user.get("content_file_path", "")).strip()
    user["voice_provider"] = _pick_allowed(request.form.get("voice_provider", user.get("voice_provider", "gtts")), ["auto", "elevenlabs", "gtts"], "gtts")
    user["video_provider"] = _pick_allowed(request.form.get("video_provider", user.get("video_provider", "pixabay")), ["auto", "library", "pexels", "pixabay", "fallback"], "pixabay")
    user["script_provider"] = _pick_allowed(request.form.get("script_provider", user.get("script_provider", "local")), ["local", "openai"], "local")
    user["premium_backgrounds_enabled"] = bool(request.form.get("premium_backgrounds_enabled"))
    user["premium_backgrounds_dir"] = request.form.get("premium_backgrounds_dir", user.get("premium_backgrounds_dir", "")).strip()
    try:
        user["premium_backgrounds_allowance"] = max(0, int(request.form.get("premium_backgrounds_allowance", user.get("premium_backgrounds_allowance", 0)) or 0))
    except Exception:
        user["premium_backgrounds_allowance"] = max(0, int(user.get("premium_backgrounds_allowance", 0) or 0))
    user["email"] = _coerce_email(request.form.get("email", user.get("email", "")))
    new_pw = request.form.get("password", "").strip()
    if new_pw:
        user["password_hash"] = generate_password_hash(new_pw)
    user["avatar_mode"] = request.form.get("avatar_mode", user.get("avatar_mode", "none")).strip().lower()
    user["avatar_prompt"] = request.form.get("avatar_prompt", user.get("avatar_prompt", "")).strip()

    def _int(name, default):
        try:
            return int(request.form.get(name, str(default)))
        except:
            return default

    user["target_seconds"] = max(20, min(45, _int("target_seconds", user.get("target_seconds", 30))))
    user["intervalo_minutos"] = max(5, _int("intervalo_minutos", user.get("intervalo_minutos", 60)))
    user["max_videos_dia"] = max(0, _int("max_videos_dia", user.get("max_videos_dia", 24)))

    user["ventana_inicio"] = request.form.get("ventana_inicio", user.get("ventana_inicio", "08:00")).strip()
    user["ventana_fin"] = request.form.get("ventana_fin", user.get("ventana_fin", "22:00")).strip()

    user["activo_scheduler"] = bool(request.form.get("activo_scheduler"))
    user["continuar_si_falla"] = bool(request.form.get("continuar_si_falla"))

    if is_super:
        user["tenant_id"] = _safe_name(request.form.get("tenant_id", user.get("tenant_id", "default"))) or "default"
        user["plan"] = _pick_plan(request.form.get("plan", user.get("plan", "starter")))

    if is_super:
        user["youtube_activo"] = bool(request.form.get("youtube_activo"))
        user["tiktok_activo"] = bool(request.form.get("tiktok_activo"))
        user["instagram_activo"] = bool(request.form.get("instagram_activo"))
        user["facebook_activo"] = bool(request.form.get("facebook_activo"))

    allowed = _plan_allowed_platforms(user.get("plan", "starter"))
    if "youtube" not in allowed:
        user["youtube_activo"] = False
    if "tiktok" not in allowed:
        user["tiktok_activo"] = False
    if "instagram" not in allowed:
        user["instagram_activo"] = False
    if "facebook" not in allowed:
        user["facebook_activo"] = False

    if is_super:
        if is_admin_legacy_user(user):
            user["youtube_auth_method"] = "legacy"
        else:
            user["youtube_auth_method"] = request.form.get(
                "youtube_auth_method",
                user.get("youtube_auth_method", "token_upload")
            ).strip()

        user["youtube_backend"] = request.form.get("youtube_backend", user.get("youtube_backend", "api")).strip()
        user["tiktok_backend"] = request.form.get("tiktok_backend", user.get("tiktok_backend", "playwright")).strip()
        user["instagram_backend"] = request.form.get("instagram_backend", user.get("instagram_backend", "playwright")).strip()
        user["facebook_backend"] = request.form.get("facebook_backend", user.get("facebook_backend", "playwright")).strip()

    cred = user.get("credenciales", {}) or {}
    cred["pexels_api_key"] = request.form.get("pexels_api_key", cred.get("pexels_api_key", "")).strip()
    cred["pixabay_api_key"] = request.form.get("pixabay_api_key", cred.get("pixabay_api_key", "")).strip()
    cred["elevenlabs_api_key"] = request.form.get("elevenlabs_api_key", cred.get("elevenlabs_api_key", "")).strip()
    cred["eleven_voice_id"] = request.form.get("eleven_voice_id", cred.get("eleven_voice_id", "")).strip()
    cred["openai_api_key"] = request.form.get("openai_api_key", cred.get("openai_api_key", "")).strip()

    cred["tiktok_client_key"] = request.form.get("tiktok_client_key", cred.get("tiktok_client_key", "")).strip()
    cred["tiktok_client_secret"] = request.form.get("tiktok_client_secret", cred.get("tiktok_client_secret", "")).strip()
    cred["tiktok_access_token"] = request.form.get("tiktok_access_token", cred.get("tiktok_access_token", "")).strip()
    cred["tiktok_refresh_token"] = request.form.get("tiktok_refresh_token", cred.get("tiktok_refresh_token", "")).strip()

    cred["meta_app_id"] = request.form.get("meta_app_id", cred.get("meta_app_id", "")).strip()
    cred["meta_app_secret"] = request.form.get("meta_app_secret", cred.get("meta_app_secret", "")).strip()
    cred["ig_user_id"] = request.form.get("ig_user_id", cred.get("ig_user_id", "")).strip()
    cred["fb_page_id"] = request.form.get("fb_page_id", cred.get("fb_page_id", "")).strip()
    cred["meta_long_lived_token"] = request.form.get("meta_long_lived_token", cred.get("meta_long_lived_token", "")).strip()

    user["credenciales"] = cred
    _append_event(user, "config", "Configuración guardada")
    save_user(user)

    return redirect(f"/usuario/{user['nombre']}")


@app.route("/usuario/<nombre>/eliminar", methods=["POST"])
@login_required
@superuser_required
def usuario_eliminar(nombre):
    nombre = _safe_name(nombre)
    try:
        user = ensure_defaults(load_user(nombre))
        if is_admin_legacy_user(user):
            abort(403, "No se puede eliminar el usuario admin legacy (David) desde el panel.")
    except FileNotFoundError:
        return redirect("/")

    try:
        p = user_path(nombre)
        if os.path.exists(p):
            os.remove(p)
    except:
        pass

    try:
        release_lock(nombre)
    except:
        pass

    try:
        ud = os.path.join(SESSIONS_DIR, nombre)
        if os.path.isdir(ud):
            shutil.rmtree(ud)
    except:
        pass

    return redirect("/")


@app.route("/usuario/<nombre>/upload/<plataforma>", methods=["POST"])
@login_required
def usuario_upload_archivo(nombre, plataforma):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    nombre = _safe_name(nombre)
    plataforma = _safe_name(plataforma)

    if not os.path.exists(user_path(nombre)):
        abort(404, f"Usuario no existe: {nombre}")

    f = request.files.get("file")
    if not f or not f.filename:
        return redirect(f"/usuario/{nombre}")

    filename = _safe_name(f.filename)
    dest_dir = platform_dir(nombre, plataforma)
    dest_path = os.path.join(dest_dir, filename)

    try:
        f.save(dest_path)
        try:
            os.chmod(dest_path, 0o600)
        except Exception:
            pass
    except Exception as e:
        abort(500, f"No se pudo guardar archivo: {e}")

    try:
        user = ensure_defaults(load_user(nombre))
        uploads = user.get("uploads", {}) or {}
        plat = uploads.get(plataforma, {}) or {}
        plat["last_uploaded_file"] = filename
        plat["last_uploaded_at"] = _now_str()
        uploads[plataforma] = plat
        user["uploads"] = uploads
        _append_event(user, "upload_file", f"Archivo subido a {plataforma}", {"file": filename})
        save_user(user)
    except:
        pass

    return redirect(f"/usuario/{nombre}")


@app.route("/usuario/<nombre>/upload/content-source", methods=["POST"])
@login_required
def usuario_upload_content_source(nombre):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    nombre = _safe_name(nombre)
    user = ensure_defaults(load_user(nombre))

    f = request.files.get("file")
    if not f or not f.filename:
        return redirect(f"/usuario/{nombre}")

    replace = bool(request.form.get("replace_existing"))
    files = _list_uploaded_files(content_sources_dir(nombre))
    if len(files) >= 3 and not replace:
        return redirect(f"/usuario/{nombre}")

    try:
        if replace:
            for old in files:
                try:
                    os.remove(os.path.join(content_sources_dir(nombre), old))
                except Exception:
                    pass
        saved = _save_uploaded_file(f, content_sources_dir(nombre), replace=replace)
        user["content_source"] = "file"
        user["content_file_path"] = f"sessions/{nombre}/content_sources/{saved}"
        save_user(user)
    except Exception:
        pass

    return redirect(f"/usuario/{nombre}")


@app.route("/usuario/<nombre>/delete/content-source/<filename>", methods=["POST"])
@login_required
def usuario_delete_content_source(nombre, filename):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    nombre = _safe_name(nombre)
    filename = _safe_name(filename)
    if filename:
        try:
            os.remove(os.path.join(content_sources_dir(nombre), filename))
        except Exception:
            pass
    return redirect(f"/usuario/{nombre}")


@app.route("/usuario/<nombre>/upload/premium-background", methods=["POST"])
@login_required
def usuario_upload_premium_background(nombre):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    nombre = _safe_name(nombre)
    user = ensure_defaults(load_user(nombre))

    f = request.files.get("file")
    if not f or not f.filename:
        return redirect(f"/usuario/{nombre}")

    allowance = int(user.get("premium_backgrounds_allowance", 0) or 0)
    files = _list_uploaded_files(premium_backgrounds_dir(nombre))
    replace = bool(request.form.get("replace_existing"))
    if allowance > 0 and len(files) >= allowance and not replace:
        return redirect(f"/usuario/{nombre}")

    try:
        if replace:
            for old in files:
                try:
                    os.remove(os.path.join(premium_backgrounds_dir(nombre), old))
                except Exception:
                    pass
        _save_uploaded_file(f, premium_backgrounds_dir(nombre), replace=replace)
        user["premium_backgrounds_dir"] = f"sessions/{nombre}/premium_backgrounds"
        save_user(user)
    except Exception:
        pass
    return redirect(f"/usuario/{nombre}")


@app.route("/usuario/<nombre>/delete/premium-background/<filename>", methods=["POST"])
@login_required
def usuario_delete_premium_background(nombre, filename):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    nombre = _safe_name(nombre)
    filename = _safe_name(filename)
    if filename:
        try:
            os.remove(os.path.join(premium_backgrounds_dir(nombre), filename))
        except Exception:
            pass
    return redirect(f"/usuario/{nombre}")


@app.route("/usuario/<nombre>/login/<plataforma>", methods=["POST"])
@login_required
def usuario_login(nombre, plataforma):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    nombre = _safe_name(nombre)
    plataforma = _safe_name(plataforma)

    if plataforma not in ("tiktok", "instagram", "facebook"):
        abort(400, "Plataforma inválida")

    if not os.path.exists(user_path(nombre)):
        abort(404, f"Usuario no existe: {nombre}")

    user_cfg = ensure_defaults(load_user(nombre))
    backend_key = f"{plataforma}_backend"
    backend = (user_cfg.get(backend_key) or "playwright").strip().lower()
    script_name = "social_login_selenium.py" if backend == "selenium" else "social_login.py"
    script = os.path.join(BASE_DIR, script_name)
    if not os.path.exists(script):
        abort(500, f"Falta {script_name}")

    try:
        subprocess.Popen(
            ["python3", script, "--user", nombre, "--platform", plataforma],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        user = ensure_defaults(load_user(nombre))
        _append_event(user, "login_start", f"Login iniciado: {plataforma}")
        save_user(user)
    except Exception as e:
        user = ensure_defaults(load_user(nombre))
        _append_event(user, "login_error", f"Login no pudo iniciar: {plataforma}", {"error": str(e)})
        save_user(user)

    return redirect(f"/usuario/{nombre}")




@app.route("/usuario/<nombre>/foto", methods=["POST"])
@login_required
def usuario_subir_foto(nombre):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    nombre = _safe_name(nombre)
    if not os.path.exists(user_path(nombre)):
        abort(404, f"Usuario no existe: {nombre}")

    f = request.files.get("file")
    if not f or not f.filename:
        return redirect(f"/usuario/{nombre}")

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        abort(400, "Formato inválido. Usa png/jpg/jpeg/webp")

    dest_dir = platform_dir(nombre, "profile")
    dest_path = os.path.join(dest_dir, f"avatar{ext}")
    f.save(dest_path)
    try:
        os.chmod(dest_path, 0o600)
    except Exception:
        pass

    user = ensure_defaults(load_user(nombre))
    user["avatar_image_path"] = dest_path
    _append_event(user, "profile_photo", "Foto de perfil subida", {"file": dest_path})
    save_user(user)
    return redirect(f"/usuario/{nombre}")
@app.route("/admin/limpiar/videos", methods=["POST"])
@login_required
@superuser_required
def admin_limpiar_videos():
    clear_videos_dir()
    return redirect("/")


@app.route("/admin/limpiar/temp", methods=["POST"])
@login_required
@superuser_required
def admin_limpiar_temp():
    clear_temp_audio()
    return redirect("/")


@app.route("/api/usuarios")
@login_required
@superuser_required
def api_usuarios():
    auth = current_auth()
    usuarios = [ensure_defaults(u) for u in list_users()]
    if auth.get("role") == "tenant":
        usuarios = [u for u in usuarios if _safe_name(u.get("nombre","")) == _safe_name(auth.get("user",""))]
    for u in usuarios:
        u["locked"] = is_locked(u["nombre"])
        u["_is_david_legacy"] = is_admin_legacy_user(u)
        u.pop("password_hash", None)
        cred = u.get("credenciales") or {}
        if isinstance(cred, dict):
            for k in list(cred.keys()):
                if "key" in k or "secret" in k or "token" in k:
                    cred[k] = "***" if cred.get(k) else ""
    return jsonify(usuarios)


if __name__ == "__main__":
    print("✅ Flask usando templates en:", os.path.abspath("templates"))
    print("✅ Static en:", os.path.abspath("static"))
    print("✅ Sessions dir:", SESSIONS_DIR)
    print("✅ Nichos desde generador.py:", len(list_nichos()))
    app.run(host="127.0.0.1", port=APP_PORT, debug=True, use_reloader=False)
