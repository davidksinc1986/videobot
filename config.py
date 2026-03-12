import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

USUARIOS_DIR = os.path.join(BASE_DIR, "usuarios")
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(USUARIOS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Defaults (plan sencillo = usa estas)
DEFAULT_PEXELS_API_KEY = "Qptl9I17ONeRrG6w4F3L3FOGlwnDxUgSYqB7Ew8ggq6BHOg36QKe8agx".strip()
PIXABAY_API_KEY = "54838603-852045d6dde78f91aece97fa7".strip()
DEFAULT_ELEVEN_API_KEY = "sk_9dd131528a66bd44aed9066c6041ea6ba259ee570f6e073d".strip()
DEFAULT_ELEVEN_VOICE_ID = "18GZPpJvaVG53Nt3H52N".strip()

# Puerto dashboard (puedes cambiarlo)
APP_PORT = int(os.environ.get("APP_PORT", "5055"))