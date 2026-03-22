import os
import json
import time
import traceback
import threading
import shutil
import subprocess
import re
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

from flask import Flask, render_template, request, redirect, jsonify, abort, make_response, session, flash, g

from config import (
    USUARIOS_DIR,
    TEMP_DIR,
    VIDEOS_DIR,
    APP_PORT,
    DB_PATH,
    APP_SECRET_KEY,
    SUPERUSER_EMAIL,
    SUPERUSER_PASSWORD,
    EMBEDDED_SCHEDULER_ENABLED,
    validate_runtime_config,
)
from storage import init_db, migrate_json_users_if_needed, load_user as db_load_user, save_user as db_save_user, list_users as db_list_users, user_exists, delete_user
from generador import generar_video_usuario, NICHOS as NICHOS_DICT

validate_runtime_config()


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

BRANDING_DIR = os.path.join(BASE_DIR, "static", "branding")
os.makedirs(BRANDING_DIR, exist_ok=True)
BRANDING_META_PATH = os.path.join(BASE_DIR, "branding_assets.json")
APP_EVENTS_PATH = os.path.join(TEMP_DIR, "app_events.jsonl")

DEFAULT_BRANDING_ASSETS = {
    "brand_logo": "/static/snake-mafia-logo.svg",
    "admin_icon": "/static/bot1.png",
    "login_slide_1": "https://image.pollinations.ai/prompt/ai%20generated%20short%20video%20thumbnail%20motivation%20dark%20cinematic%20neon",
    "login_slide_2": "https://image.pollinations.ai/prompt/ai%20generated%20short%20video%20thumbnail%20finance%20charts%20dark%20luxury",
    "login_slide_3": "https://image.pollinations.ai/prompt/ai%20generated%20short%20video%20thumbnail%20hairstyle%20beauty%20studio%20dark",
    "login_slide_4": "https://image.pollinations.ai/prompt/ai%20generated%20short%20video%20thumbnail%20haircare%20salon%20dark%20premium",
    "login_slide_5": "https://image.pollinations.ai/prompt/ai%20generated%20short%20video%20thumbnail%20bridal%20makeup%20editorial%20dark%20style",
    "user_hero_1": "https://images.unsplash.com/photo-1611162618071-b39a2ec055fb?auto=format&fit=crop&w=900&q=80",
    "user_hero_2": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=900&q=80",
    "user_hero_3": "https://images.unsplash.com/photo-1611605698323-b1e99cfd37ea?auto=format&fit=crop&w=900&q=80",
}


def _load_branding_overrides() -> dict:
    if not os.path.exists(BRANDING_META_PATH):
        return {}
    try:
        with open(BRANDING_META_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_branding_overrides(data: dict) -> None:
    with open(BRANDING_META_PATH, "w", encoding="utf-8") as f:
        json.dump(data or {}, f, ensure_ascii=False, indent=2)


def get_branding_assets() -> dict:
    assets = dict(DEFAULT_BRANDING_ASSETS)
    overrides = _load_branding_overrides()
    for k, v in overrides.items():
        if k in assets and isinstance(v, str) and v.strip():
            assets[k] = v.strip()
    return assets

import sentry_sdk

# Inicialización de Sentry
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            sentry_sdk.integrations.flask.FlaskIntegration(),
            sentry_sdk.integrations.celery.CeleryIntegration(),
        ],
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        profiles_sample_rate=1.0,
    )

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = APP_SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

from models import db
db.init_app(app)

# En un entorno de producción, la creación de la base de datos y las migraciones
# se manejarían con herramientas como Alembic. Para este proyecto, realizamos
# la inicialización aquí para asegurar que todo esté listo al arrancar.
with app.app_context():
    _migrated = migrate_json_users_if_needed()
    if _migrated:
        print(f"✅ Migrados {_migrated} usuarios JSON a la base de datos.")

SCHEDULER_TICK_SECONDS = 15
_scheduler_started = False
_scheduler_lock = threading.Lock()


@app.context_processor
def inject_branding_assets():
    return {"branding_assets": get_branding_assets()}


@app.before_request
def _track_request_start():
    g._request_started_at = time.time()


@app.after_request
def _track_request_end(response):
    try:
        path = request.path or ""
        if not path.startswith("/static") and not path.startswith("/favicon"):
            duration_ms = int((time.time() - getattr(g, "_request_started_at", time.time())) * 1000)
            user_name = session.get("auth", {}).get("user") if isinstance(session.get("auth"), dict) else None
            _append_global_event(
                "request",
                f"{request.method} {path} → {response.status_code}",
                user_name,
                {
                    "duration_ms": duration_ms,
                    "query": request.query_string.decode("utf-8", errors="ignore")[:200],
                },
            )
    except Exception:
        pass
    return response


# ----------------------------
# i18n (ES/EN) simple con cookie
# ----------------------------

TRANSLATIONS = {
    "es": {
        "app_title": "Media by Snake Mafia",
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
        "save_ok": "Configuración guardada correctamente.",
        "save_error": "No se pudo guardar la configuración.",
        "save_banner_ok": "✅ Cambios guardados.",
        "save_banner_error": "❌ Error al guardar. Revisa los campos e intenta nuevamente.",
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
        "help": "Guía",
        "welcome_excited": "¡Bienvenid@! 🚀",
        "welcome_tabs_hint": "En estos tabs está toda tu configuración para crear y publicar más rápido.",
        "hero_user_title": "Tu estudio de automatización está listo",
        "hero_user_subtitle": "Configura IA, subidas y redes en un solo lugar con flujo claro por pestañas.",
        "tab_profile": "Perfil",
        "tab_content": "Contenido",
        "tab_youtube": "YouTube",
        "tab_tiktok": "TikTok",
        "tab_instagram": "Instagram",
        "tab_facebook": "Facebook",
        "content_files_title": "Textos base (máx 3)",
        "content_files_desc": "Sube archivos con ideas/guiones. Puedes reemplazar o borrar versiones.",
        "replace_existing": "Reemplazar existentes",
        "upload_file": "Subir archivo",
        "no_files_uploaded": "Sin archivos cargados.",
        "premium_bg_title": "Fondos premium",
        "allowance_current": "Allowance actual",
        "enable_premium_bg": "Activar fondos premium",
        "allowance_editable": "Allowance editable",
        "upload_premium_bg": "Subir fondo premium",
        "no_premium_uploaded": "Sin fondos premium cargados.",
        "api_mode_hint": "Si eliges backend API, pega credenciales o carga token desde archivo.",
        "session_upload": "Subida de sesión/credencial",
        "yt_upload_desc": "Sube token.pickle cuando uses Token Upload en YouTube.",
        "social_upload_desc": "Sube cookies.json o storage_state.json para esta red cuando uses automatización web.",
        "stats_panel": "Resumen de actividad",
        "stats_desc": "Aquí ves progreso, estado de subidas y últimas confirmaciones.",
        "videos_today_label": "Videos hoy",
        "daily_limit_label": "Límite diario",
        "last_update": "Última actualización",
        "upload_status_title": "Estado de subidas",
        "details": "Detalle",
        "api_help_title": "Cómo obtener API keys y secretos",
        "api_help_body": "Pexels/Pixabay: crea cuenta > API. ElevenLabs/OpenAI: crea API key desde dashboard. TikTok/Meta: crea app de desarrollador, configura permisos de publicación y genera tokens.",
        "ai_help_title": "Guía rápida de IA",
        "ai_help_body": "Voz: gTTS (gratis), ElevenLabs (calidad), OpenAI/Azure/Coqui (alternativas). Video: Pixabay/Pexels (stock), Library (local), Runway/Pika (experimental).",
        "target_seconds_label": "Duración objetivo (20-45s)",
        "password_keep_hint": "Contraseña (vacío = no cambiar)",
        "tenant_id_label": "Tenant ID",
        "plan_label": "Plan",
        "plan_starter": "starter",
        "plan_growth": "growth",
        "plan_scale": "scale",
        "confirm_replace_limit": "Ya llegaste al límite. ¿Deseas reemplazar existentes?",
        "confirm_add_version": "Ya hay archivos cargados. ¿Quieres agregar otra versión?",
        "confirm_replace_premium": "Ya llegaste al allowance premium. ¿Reemplazar actuales?",
        "none": "Ninguno",
        "app_subtitle": "AI generated videos for monetization.",
        "hero_admin_title": "Escala canales con IA y estrategia",
        "hero_admin_subtitle": "Configura nicho, duración, voz, redes y publica en automático con control de plan por tenant.",
        "user_type": "Tipo de usuario",
        "role_admin": "admin",
        "role_user": "user",
        "tenant_plan": "Tenant / Plan",
        "scheduler": "scheduler",
        "interval": "intervalo",
        "recent_error": "error reciente",
        "content_file_optional": "Archivo base (opcional)",
        "quick_panel_title": "Panel rápido",
        "quick_panel_desc": "Gestiona usuarios, genera contenido y opera uploads por red social desde un solo lugar.",
        "clear_videos_btn": "Vaciar Videos",
        "clear_temp_btn": "Vaciar Audios",
        "no_users_yet": "No hay usuarios todavía.",
        "email_login": "Correo login",
        "password_login": "Contraseña login",
        "delete_confirm": "¿Eliminar usuario {name}?",
    },
    "en": {
        "app_title": "Media by Snake Mafia",
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
        "save_ok": "Settings were saved successfully.",
        "save_error": "Could not save settings.",
        "save_banner_ok": "✅ Changes saved.",
        "save_banner_error": "❌ Could not save changes. Check your fields and try again.",
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
        "help": "Guide",
        "welcome_excited": "Welcome! 🚀",
        "welcome_tabs_hint": "These tabs contain all your configuration to create and publish faster.",
        "hero_user_title": "Your automation studio is ready",
        "hero_user_subtitle": "Configure AI, uploads and platforms in one place with a clear tab flow.",
        "tab_profile": "Profile",
        "tab_content": "Content",
        "tab_youtube": "YouTube",
        "tab_tiktok": "TikTok",
        "tab_instagram": "Instagram",
        "tab_facebook": "Facebook",
        "content_files_title": "Base texts (max 3)",
        "content_files_desc": "Upload idea/script files. You can replace or delete versions.",
        "replace_existing": "Replace existing",
        "upload_file": "Upload file",
        "no_files_uploaded": "No files uploaded.",
        "premium_bg_title": "Premium backgrounds",
        "allowance_current": "Current allowance",
        "enable_premium_bg": "Enable premium backgrounds",
        "allowance_editable": "Editable allowance",
        "upload_premium_bg": "Upload premium background",
        "no_premium_uploaded": "No premium backgrounds uploaded.",
        "api_mode_hint": "If you choose API backend, paste credentials or load token from file.",
        "session_upload": "Session/credential upload",
        "yt_upload_desc": "Upload token.pickle when using YouTube Token Upload mode.",
        "social_upload_desc": "Upload cookies.json or storage_state.json for this platform when using web automation.",
        "stats_panel": "Activity summary",
        "stats_desc": "Here you can see progress, upload statuses and latest confirmations.",
        "videos_today_label": "Videos today",
        "daily_limit_label": "Daily limit",
        "last_update": "Last update",
        "upload_status_title": "Upload status",
        "details": "Details",
        "api_help_title": "How to get API keys and secrets",
        "api_help_body": "Pexels/Pixabay: create account > API. ElevenLabs/OpenAI: create API key from dashboard. TikTok/Meta: create developer app, set publishing permissions and generate tokens.",
        "ai_help_title": "Quick AI guide",
        "ai_help_body": "Voice: gTTS (free), ElevenLabs (quality), OpenAI/Azure/Coqui (alternatives). Video: Pixabay/Pexels (stock), Library (local), Runway/Pika (experimental).",
        "target_seconds_label": "Target duration (20-45s)",
        "password_keep_hint": "Password (empty = keep current)",
        "tenant_id_label": "Tenant ID",
        "plan_label": "Plan",
        "plan_starter": "starter",
        "plan_growth": "growth",
        "plan_scale": "scale",
        "confirm_replace_limit": "You reached the limit. Replace existing files?",
        "confirm_add_version": "Files already exist. Add another version?",
        "confirm_replace_premium": "You reached premium allowance. Replace current files?",
        "none": "None",
        "app_subtitle": "AI generated videos for monetization.",
        "hero_admin_title": "Scale channels with AI and strategy",
        "hero_admin_subtitle": "Set niche, duration, voice, platforms, and auto-publish with tenant plan control.",
        "user_type": "User type",
        "role_admin": "admin",
        "role_user": "user",
        "tenant_plan": "Tenant / Plan",
        "scheduler": "scheduler",
        "interval": "interval",
        "recent_error": "recent error",
        "content_file_optional": "Base file (optional)",
        "quick_panel_title": "Quick panel",
        "quick_panel_desc": "Manage users, generate content, and operate social uploads from one place.",
        "clear_videos_btn": "Clear Videos",
        "clear_temp_btn": "Clear Audios",
        "no_users_yet": "There are no users yet.",
        "email_login": "Login email",
        "password_login": "Login password",
        "delete_confirm": "Delete user {name}?",
    }
}

PT_OVERRIDES = {
    "app_title": "Media by Snake Mafia",
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
    "save_ok": "Configuração salva com sucesso.",
    "save_error": "Não foi possível salvar a configuração.",
    "save_banner_ok": "✅ Alterações salvas.",
    "save_banner_error": "❌ Erro ao salvar. Revise os campos e tente novamente.",
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
    "welcome_excited": "Bem-vindo(a)! 🚀",
    "welcome_tabs_hint": "Nestas abas está toda a sua configuração para criar e publicar mais rápido.",
    "hero_user_title": "Seu estúdio de automação está pronto",
    "hero_user_subtitle": "Configure IA, uploads e redes em um só lugar com fluxo claro por abas.",
    "tab_profile": "Perfil",
    "tab_content": "Conteúdo",
    "stats_panel": "Resumo de atividade",
    "stats_desc": "Veja progresso, status de uploads e últimas confirmações.",
    "upload_status_title": "Status de uploads",
    "session_upload": "Upload de sessão/credencial",
    "target_seconds_label": "Duração alvo (20-45s)",
    "password_keep_hint": "Senha (vazio = manter)",
    "tenant_id_label": "Tenant ID",
    "plan_label": "Plano",
    "plan_starter": "starter",
    "plan_growth": "growth",
    "plan_scale": "scale",
    "confirm_replace_limit": "Você chegou ao limite. Deseja substituir os existentes?",
    "confirm_add_version": "Já existem arquivos. Deseja adicionar outra versão?",
    "confirm_replace_premium": "Você chegou ao limite premium. Substituir os arquivos atuais?",
}
TRANSLATIONS["pt"] = {**TRANSLATIONS["en"], **PT_OVERRIDES}

NICHE_LABELS = {
    "es": {
        "haircare": "Cuidado del cabello",
        "hairstyle": "Estilo de cabello",
        "maquillaje_social": "Maquillaje social",
        "maquillaje_novias": "Maquillaje para novias",
        "maquillaje_editorial": "Maquillaje editorial",
        "unas": "Arte de uñas",
        "skincare": "Cuidado de la piel",
    },
    "en": {
        "haircare": "Haircare",
        "hairstyle": "Hairstyle",
        "maquillaje_social": "Social makeup",
        "maquillaje_novias": "Bridal makeup",
        "maquillaje_editorial": "Editorial makeup",
        "unas": "Nail art",
        "skincare": "Skincare",
    },
    "pt": {
        "haircare": "Cuidados capilares",
        "hairstyle": "Penteados",
        "maquillaje_social": "Maquiagem social",
        "maquillaje_novias": "Maquiagem para noivas",
        "maquillaje_editorial": "Maquiagem editorial",
        "unas": "Nail art",
        "skincare": "Cuidados com a pele",
    },
}


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
    return {"email": SUPERUSER_EMAIL, "password": SUPERUSER_PASSWORD}


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
        return render_template("login.html", lang=get_lang(), t=tr(), error="", niche_label=niche_label)

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

    return render_template("login.html", lang=get_lang(), t=tr(), error="Credenciales inválidas", niche_label=niche_label)


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
    return db_load_user(_safe_name(nombre))


def save_user(user: dict) -> None:
    db_save_user(user)


def list_users() -> list:
    return db_list_users()


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


def niche_label(niche_key: str, lang: str) -> str:
    key = (niche_key or "").strip().lower()
    selected_lang = lang if lang in ("es", "en", "pt") else "es"
    by_lang = NICHE_LABELS.get(selected_lang, {})
    if key in by_lang:
        return by_lang[key]
    return key.replace("_", " ").title()


def _short_error(tb: str, max_chars: int = 1400) -> str:
    tb = (tb or "").strip()
    if len(tb) <= max_chars:
        return tb
    return tb[-max_chars:]


def _append_global_event(kind: str, message: str, user: str | None = None, extra=None):
    ev = {
        "ts": int(time.time()),
        "at": _now_str(),
        "kind": kind,
        "message": message,
    }
    if user:
        ev["user"] = user
    if extra and isinstance(extra, dict):
        ev["extra"] = extra
    try:
        with open(APP_EVENTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _load_global_events(limit: int = 300) -> list[dict]:
    if not os.path.exists(APP_EVENTS_PATH):
        return []
    rows = []
    try:
        with open(APP_EVENTS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if isinstance(ev, dict):
                    rows.append(ev)
    except Exception:
        return []
    rows = rows[-limit:]
    rows.sort(key=lambda e: int(e.get("ts", 0)), reverse=True)
    return rows


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
    _append_global_event(kind, message, user.get("nombre"), extra)


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
        "schedule_mode": "always",

        "idioma": "es",
        "tenant_id": "default",
        "plan": "starter",
        "nicho": valid_nichos[0] if valid_nichos else "motivacion",
        "target_seconds": 30,
        "hook_final": "Suscríbete para más 🔥",
        "content_source": "ai",
        "content_file_path": "",
        "speech_history": [],
        "generation_learning": {
            "success": 0,
            "fail": 0,
            "last_error": "",
            "last_success_at": "",
        },
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

        "tiktok_backend": "auto",
        "instagram_backend": "auto",
        "facebook_backend": "auto",

        "upload_status": {
            "youtube": {"ok": None, "at": "", "detail": ""},
            "tiktok": {"ok": None, "at": "", "detail": ""},
            "instagram": {"ok": None, "at": "", "detail": ""},
            "facebook": {"ok": None, "at": "", "detail": ""},
        },

        "events": [],
        "title_counter": 0,

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

    # Compat legacy: algunos payloads históricos usan frecuencia_minutos
    if "intervalo_minutos" not in user and "frecuencia_minutos" in user:
        try:
            user["intervalo_minutos"] = max(5, int(user.get("frecuencia_minutos") or 60))
        except Exception:
            user["intervalo_minutos"] = 60
        changed = True

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


from locks import is_locked, try_acquire_lock, release_lock


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
        return bool(subir_youtube(video_path, titulo, user=user))

    method = (user.get("youtube_auth_method") or "token_upload").strip()
    if method != "token_upload":
        raise RuntimeError("YouTube auth_method=oath_web aún no implementado")

    user_token = os.path.join(SESSIONS_DIR, _safe_name(user["nombre"]), "youtube", "token.pickle")
    if not os.path.exists(user_token):
        raise FileNotFoundError(f"Falta token.pickle del usuario en: {user_token}")

    return bool(subir_youtube(video_path, titulo, user=user))


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
    titulo = _next_video_title(user)

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




def _generation_requirements_missing(user: dict) -> list[str]:
    missing = []
    cred = user.get("credenciales", {}) or {}

    voice = (user.get("voice_provider") or "gtts").strip().lower()
    video = (user.get("video_provider") or "pixabay").strip().lower()
    script_provider = (user.get("script_provider") or "local").strip().lower()
    content_source = (user.get("content_source") or "ai").strip().lower()

    if voice == "elevenlabs":
        if not (cred.get("elevenlabs_api_key") or "").strip():
            missing.append("elevenlabs_api_key")
        if not (cred.get("eleven_voice_id") or "").strip():
            missing.append("eleven_voice_id")

    if video == "pexels" and not (cred.get("pexels_api_key") or "").strip():
        missing.append("pexels_api_key")

    if video == "pixabay" and not (cred.get("pixabay_api_key") or "").strip():
        # hay clave por defecto en config, por eso solo warning si no hay user key
        _append_event(user, "config_warning", "Usando Pixabay API key global por falta de clave por usuario")

    if script_provider == "openai" and content_source != "file":
        if not (cred.get("openai_api_key") or "").strip():
            missing.append("openai_api_key")

    return missing


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hh, mm = (value or "08:00").strip().split(":", 1)
        return int(hh), int(mm)
    except Exception:
        return 8, 0


def _in_window(start_hm: str, end_hm: str) -> bool:
    now = datetime.now()
    sh, sm = _parse_hhmm(start_hm)
    eh, em = _parse_hhmm(end_hm)

    start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = now.replace(hour=eh, minute=em, second=0, microsecond=0)

    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def _next_video_title(user: dict) -> str:
    """
    Título estilo marketing con secuencia persistente por usuario.
    Ejemplo: "Consejo de Liderazgo por David #12"
    """
    sequence = max(1, int(user.get("title_counter", 0) or 0) + 1)
    niche_raw = (user.get("nicho") or "contenido").replace("_", " ").strip().lower()
    niche_map = {
        "liderazgo": "Consejo de Liderazgo",
        "motivacion": "Impulso de Motivación",
        "dinero": "Tip de Dinero Inteligente",
        "psicologia": "Idea de Psicología Práctica",
        "relaciones": "Consejo de Relaciones",
    }
    base = niche_map.get(niche_raw, f"Tip de {niche_raw.title()}")
    creator = (user.get("nombre") or "Creator").strip().title()
    return f"{base} por {creator} #{sequence}"


def _scheduler_due(user: dict, now_ts: int) -> bool:
    if not bool(user.get("activo_scheduler", True)):
        return False

    interval_min = max(5, int(user.get("intervalo_minutos", 60) or 60))
    last_ts = int(user.get("last_run_ts", 0) or 0)
    if now_ts - last_ts < interval_min * 60:
        return False

    max_dia = max(0, int(user.get("max_videos_dia", 24) or 24))
    videos_hoy = int(user.get("videos_hoy", 0) or 0)
    if max_dia > 0 and videos_hoy >= max_dia:
        return False

    schedule_mode = (user.get("schedule_mode") or "always").strip().lower()
    if schedule_mode == "always":
        return True

    return _in_window(user.get("ventana_inicio", "08:00"), user.get("ventana_fin", "22:00"))


def scheduler_loop() -> None:
    """
    Este loop ya no ejecuta los trabajos directamente. En su lugar, actúa como un
    despachador, enviando tareas a la cola de Celery para su procesamiento asíncrono.
    """
    print("🚀 Starting Celery-based scheduler loop...")
    while True:
        try:
            now_ts = int(time.time())
            with app.app_context():
                users = list_users()
            for u in users:
                user = ensure_defaults(u)
                nombre = _safe_name(user.get("nombre", ""))
                if not nombre:
                    continue

                # La lógica de 'is_locked' ahora está dentro de la tarea Celery para
                # mayor atomicidad, pero podemos hacer una comprobación rápida aquí
                # para evitar despachar trabajos innecesarios a la cola.
                if is_locked(nombre):
                    continue

                if _scheduler_due(user, now_ts):
                    try:
                        from tasks import process_user_video_job
                        process_user_video_job.delay(nombre)
                        print(f"✅ Job dispatched to Celery for user: {nombre}")
                    except Exception as e:
                        print(f"❌ Failed to dispatch job for {nombre}: {e}")

        except Exception as e:
            print(f"‼️ ERROR in scheduler loop: {e}")
            traceback.print_exc()

        time.sleep(SCHEDULER_TICK_SECONDS)


def start_scheduler_once() -> None:
    if not EMBEDDED_SCHEDULER_ENABLED:
        return
    global _scheduler_started
    if _scheduler_started:
        return
    with _scheduler_lock:
        if _scheduler_started:
            return
        th = threading.Thread(target=scheduler_loop, daemon=True, name="videobot-scheduler")
        th.start()
        _scheduler_started = True


@app.before_request
def _ensure_scheduler_running():
    start_scheduler_once()




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

    if not user_exists(nombre):
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

from flask import send_from_directory

@app.route("/videos/<path:filename>")
@login_required
def ver_video(filename):
    # Validar acceso básico asegurando que solo los admins o dueños puedan verlo
    auth = current_auth()
    if auth.get("role") == "tenant":
        user_name = auth.get("user", "")
        # Asume que los videos empiezan con el nombre del usuario
        if not filename.startswith(_safe_name(user_name) + "_"):
            abort(403, "No puedes ver videos de otros usuarios")
    
    return send_from_directory(VIDEOS_DIR, filename)


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
        auth=auth,
        niche_label=niche_label
    )


def _extract_traceback_hint(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    m = re.search(r'File "([^"]+)", line (\d+)', raw)
    if m:
        return f"Archivo {m.group(1)} (línea {m.group(2)})"
    return ""


def _event_to_alarm(event: dict) -> dict:
    kind = str(event.get("kind") or "evento").strip().lower()
    message = str(event.get("message") or "Sin mensaje").strip()
    user = event.get("user") or "sistema"
    severity = "info"
    where = "Panel de monitoreo"

    msg_l = message.lower()
    if kind.endswith("_error") or "error" in kind or "fall" in msg_l:
        severity = "error"
    elif kind.endswith("_warning") or "warning" in kind:
        severity = "warning"

    if kind == "request":
        status = None
        m = re.search(r'→\s*(\d+)', message)
        if m:
            status = int(m.group(1))
        if status and status >= 500:
            severity = "error"
            where = "Logs del servidor Flask (endpoint con error 5xx)"
        elif status and status >= 400:
            severity = "warning"
            where = "Ruta solicitada y permisos de sesión"
        else:
            severity = "info"
            where = "Tráfico normal de la app"
    elif kind.startswith("upload"):
        where = f"Usuario {user} → pestaña de la red social y credenciales"
    elif kind.startswith("login"):
        where = f"Usuario {user} → sesión/login social (cookies o storage_state)"
    elif kind.startswith("job") or kind.startswith("generate"):
        where = f"Usuario {user} → generador y scheduler"
    elif kind == "config":
        where = f"Usuario {user} → formulario de configuración"

    return {
        "ts": int(event.get("ts", 0) or 0),
        "at": event.get("at") or "-",
        "user": user,
        "kind": kind,
        "severity": severity,
        "title": f"{kind.replace('_', ' ').title()} · {user}",
        "message": message,
        "where_to_check": where,
    }


def _build_monitor_alerts(usuarios: list[dict], events: list[dict], limit: int = 12) -> list[dict]:
    alerts = []

    for u in usuarios:
        err = (u.get("ultimo_error") or "").strip()
        if not err:
            continue
        alerts.append({
            "ts": int(u.get("last_run_ts") or 0),
            "at": u.get("ultimo_run") or "-",
            "user": u.get("nombre") or "usuario",
            "kind": "ultimo_error",
            "severity": "error",
            "title": f"Error activo · {u.get('nombre')}",
            "message": _short_error(err, 240),
            "where_to_check": _extract_traceback_hint(err) or f"Usuario {u.get('nombre')} → pestaña de plataforma / credenciales",
        })

    for ev in events[:250]:
        alarm = _event_to_alarm(ev)
        if alarm["severity"] in ("error", "warning"):
            alerts.append(alarm)

    seen = set()
    unique = []
    for a in sorted(alerts, key=lambda x: x.get("ts", 0), reverse=True):
        key = (a.get("user"), a.get("kind"), a.get("message"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(a)
        if len(unique) >= limit:
            break
    return unique


@app.route("/monitor")
@login_required
@superuser_required
def monitor():
    lang = get_lang()
    usuarios = [ensure_defaults(u) for u in list_users()]

    raw_events = _load_global_events(limit=400)
    events = [_event_to_alarm(ev) for ev in raw_events]
    alerts = _build_monitor_alerts(usuarios, raw_events, limit=12)

    return render_template("monitor.html", usuarios=usuarios, events=events, alerts=alerts, lang=lang, t=tr())


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
        "voice_provider": _pick_allowed(request.form.get("voice_provider", "gtts"), ["auto", "elevenlabs", "gtts", "openai_tts", "azure_tts", "coqui_tts"], "gtts"),
        "video_provider": _pick_allowed(request.form.get("video_provider", "pixabay"), ["auto", "library", "pexels", "pixabay", "fallback", "pika", "runway", "mixkit"], "pixabay"),
        "script_provider": _pick_allowed(request.form.get("script_provider", "local"), ["local", "openai"], "local"),
        "email": email_login,
        "password_hash": generate_password_hash(raw_pw),
    })

    if not user_exists(nombre):
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
    if not user_exists(nombre):
        abort(404, f"Usuario no existe: {nombre}")

    # Despachar la tarea a Celery en lugar de crear un hilo
    try:
        from tasks import process_user_video_job
        process_user_video_job.delay(nombre)
        # Opcional: añadir un flash message si se desea feedback en la UI
        # flash(f"✅ Trabajo para {nombre} enviado a la cola.", "success")
    except Exception as e:
        print(f"❌ Error al despachar trabajo para {nombre}: {e}")
        # Opcional: flash(f"❌ Error al enviar el trabajo: {e}", "error")

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

    save_status = (request.args.get("saved") or "").strip().lower()

    return render_template(
        "user.html",
        user=user,
        nichos=nichos,
        lang=lang,
        t=tr(),
        auth=current_auth(),
        niche_label=niche_label,
        save_status=save_status
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
    user["voice_provider"] = _pick_allowed(request.form.get("voice_provider", user.get("voice_provider", "gtts")), ["auto", "elevenlabs", "gtts", "openai_tts", "azure_tts", "coqui_tts"], "gtts")
    user["video_provider"] = _pick_allowed(request.form.get("video_provider", user.get("video_provider", "pixabay")), ["auto", "library", "pexels", "pixabay", "fallback", "pika", "runway", "mixkit"], "pixabay")
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
    user["schedule_mode"] = _pick_allowed(request.form.get("schedule_mode", user.get("schedule_mode", "always")), ["always", "window"], "always")

    user["activo_scheduler"] = bool(request.form.get("activo_scheduler"))
    user["continuar_si_falla"] = bool(request.form.get("continuar_si_falla"))

    if is_super:
        user["tenant_id"] = _safe_name(request.form.get("tenant_id", user.get("tenant_id", "default"))) or "default"
        user["plan"] = _pick_plan(request.form.get("plan", user.get("plan", "starter")))

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

    if is_admin_legacy_user(user):
        user["youtube_auth_method"] = "legacy"
    else:
        user["youtube_auth_method"] = _pick_allowed(
            request.form.get("youtube_auth_method", user.get("youtube_auth_method", "token_upload")),
            ["legacy", "token_upload", "oauth_web"],
            "token_upload"
        )

    allowed_backends = ["auto", "api", "playwright", "selenium"]
    user["youtube_backend"] = _pick_allowed(request.form.get("youtube_backend", user.get("youtube_backend", "api")), allowed_backends, "api")
    user["tiktok_backend"] = _pick_allowed(request.form.get("tiktok_backend", user.get("tiktok_backend", "auto")), allowed_backends, "auto")
    user["instagram_backend"] = _pick_allowed(request.form.get("instagram_backend", user.get("instagram_backend", "auto")), allowed_backends, "auto")
    user["facebook_backend"] = _pick_allowed(request.form.get("facebook_backend", user.get("facebook_backend", "auto")), allowed_backends, "auto")

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
    try:
        save_user(user)
        flash(tr().get("save_ok", "Configuración guardada correctamente."), "success")
        return redirect(f"/usuario/{user['nombre']}?saved=1")
    except Exception:
        flash(tr().get("save_error", "No se pudo guardar la configuración."), "error")
        return redirect(f"/usuario/{user['nombre']}?saved=0")


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
        delete_user(nombre)
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

    if not user_exists(nombre):
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

    if not user_exists(nombre):
        abort(404, f"Usuario no existe: {nombre}")

    user_cfg = ensure_defaults(load_user(nombre))
    backend_key = f"{plataforma}_backend"
    backend = (user_cfg.get(backend_key) or "auto").strip().lower()
    candidates = [backend] if backend in ("playwright", "selenium") else ["playwright", "selenium"]

    started = False
    last_error = ""
    for candidate in candidates:
        script_name = "social_login.py" if candidate == "playwright" else "social_login_selenium.py"
        script = os.path.join(BASE_DIR, script_name)
        if not os.path.exists(script):
            last_error = f"Falta {script_name}"
            continue
        try:
            subprocess.Popen(
                ["python3", script, "--user", nombre, "--platform", plataforma],
                cwd=BASE_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            user = ensure_defaults(load_user(nombre))
            _append_event(user, "login_start", f"Login iniciado: {plataforma} ({candidate})")
            save_user(user)
            started = True
            break
        except Exception as e:
            last_error = str(e)

    if not started:
        user = ensure_defaults(load_user(nombre))
        _append_event(user, "login_error", f"Login no pudo iniciar: {plataforma}", {"error": last_error or "sin backend disponible"})
        save_user(user)

    return redirect(f"/usuario/{nombre}")




@app.route("/usuario/<nombre>/foto", methods=["POST"])
@login_required
def usuario_subir_foto(nombre):
    if not can_access_user(nombre):
        abort(403, "Sin acceso a este usuario")
    nombre = _safe_name(nombre)
    if not user_exists(nombre):
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
@app.route("/admin/branding/upload/<slot>", methods=["POST"])
@login_required
@superuser_required
def admin_branding_upload(slot):
    slot = (slot or "").strip().lower()
    if slot not in DEFAULT_BRANDING_ASSETS:
        abort(400, "Slot de imagen inválido")

    f = request.files.get("file")
    if not f or not f.filename:
        abort(400, "Debes subir una imagen")

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
        abort(400, "Formato inválido. Usa png/jpg/jpeg/webp/gif/svg")

    safe_slot = "".join(ch for ch in slot if ch.isalnum() or ch == "_")
    filename = f"{safe_slot}_{int(time.time())}{ext}"
    dest_path = os.path.join(BRANDING_DIR, filename)
    f.save(dest_path)

    url = f"/static/branding/{filename}"
    overrides = _load_branding_overrides()
    overrides[slot] = url
    _save_branding_overrides(overrides)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "slot": slot, "url": url})
    return redirect("/")


@app.route("/admin/branding/reset/<slot>", methods=["POST"])
@login_required
@superuser_required
def admin_branding_reset(slot):
    slot = (slot or "").strip().lower()
    overrides = _load_branding_overrides()
    if slot in overrides:
        overrides.pop(slot, None)
        _save_branding_overrides(overrides)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "slot": slot, "url": get_branding_assets().get(slot, "")})
    return redirect("/")


@app.route("/admin/branding/assets")
@login_required
@superuser_required
def admin_branding_assets():
    return jsonify(get_branding_assets())


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
    start_scheduler_once()
    print("✅ Flask usando templates en:", os.path.abspath("templates"))
    print("✅ Static en:", os.path.abspath("static"))
    print("✅ Sessions dir:", SESSIONS_DIR)
    print("✅ Nichos desde generador.py:", len(list_nichos()))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", APP_PORT)), debug=False, use_reloader=False)
