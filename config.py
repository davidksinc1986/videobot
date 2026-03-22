import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.abspath(os.path.expanduser(os.environ.get("VIDEOBOT_DATA_DIR", "~/.videobot_data")))

USUARIOS_DIR = os.path.join(DATA_ROOT, "usuarios")
VIDEOS_DIR = os.path.join(DATA_ROOT, "videos")
TEMP_DIR = os.path.join(DATA_ROOT, "temp")
DB_PATH = os.path.join(DATA_ROOT, "videobot.sqlite3")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(USUARIOS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _env_flag(name: str, default: bool = False) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


APP_SECRET_KEY = _env("APP_SECRET_KEY")
SUPERUSER_EMAIL = _env("SUPERUSER_EMAIL").lower()
SUPERUSER_PASSWORD = _env("SUPERUSER_PASSWORD")

# Defaults opcionales para integraciones externas.
DEFAULT_PEXELS_API_KEY = _env("DEFAULT_PEXELS_API_KEY")
PIXABAY_API_KEY = _env("PIXABAY_API_KEY")
DEFAULT_ELEVEN_API_KEY = _env("DEFAULT_ELEVEN_API_KEY")
DEFAULT_ELEVEN_VOICE_ID = _env("DEFAULT_ELEVEN_VOICE_ID")

# Scheduler embebido desactivado por defecto; producción debe usar scheduler.py
EMBEDDED_SCHEDULER_ENABLED = _env_flag("VIDEOBOT_RUN_EMBEDDED_SCHEDULER", default=False)


def validate_runtime_config() -> None:
    missing = [
        name
        for name, value in {
            "APP_SECRET_KEY": APP_SECRET_KEY,
            "SUPERUSER_EMAIL": SUPERUSER_EMAIL,
            "SUPERUSER_PASSWORD": SUPERUSER_PASSWORD,
        }.items()
        if not value
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Faltan variables críticas de entorno: {joined}. "
            "Configúralas en tu entorno o en un archivo .env local no versionado."
        )

# Puerto dashboard (puedes cambiarlo)
APP_PORT = int(os.environ.get("APP_PORT", "5000"))
