import os
import json
import time
import traceback
from datetime import datetime

from config import USUARIOS_DIR, TEMP_DIR
from generador import generar_video_usuario

from subir_youtube import subir_youtube
from subir_tiktok import subir_tiktok
from subir_instagram import subir_instagram
from subir_facebook import subir_facebook

TICK_SECONDS = 5

LOCK_DIR = os.path.join(TEMP_DIR, "locks")
os.makedirs(LOCK_DIR, exist_ok=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)


def _now():
    return datetime.now()


def _now_str():
    return _now().strftime("%Y-%m-%d %H:%M:%S")


def _today_str():
    return _now().strftime("%Y-%m-%d")


def user_path(nombre: str) -> str:
    return os.path.join(USUARIOS_DIR, f"{nombre}.json")


def load_user_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user(user: dict) -> None:
    with open(user_path(user["nombre"]), "w", encoding="utf-8") as f:
        json.dump(user, f, ensure_ascii=False, indent=2)


def ensure_defaults(user: dict) -> dict:
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
        "videos_hoy_fecha": _today_str(),

        "ventana_inicio": "08:00",
        "ventana_fin": "22:00",

        "idioma": "es",
        "nicho": "motivacion",
        "hook_final": "Suscríbete para más 🔥",

        "youtube_activo": True,
        "tiktok_activo": False,
        "instagram_activo": False,
        "facebook_activo": False,

        "continuar_si_falla": True,

        "youtube_auth_method": "legacy",  # David legacy
        "youtube_backend": "api",
        "tiktok_backend": "selenium",
        "instagram_backend": "selenium",
        "facebook_backend": "selenium",

        "credenciales": {
            "pexels_api_key": "",
            "elevenlabs_api_key": "",
            "eleven_voice_id": "",

            "tiktok_client_key": "",
            "tiktok_client_secret": "",
            "tiktok_access_token": "",
            "tiktok_refresh_token": "",

            "meta_app_id": "",
            "meta_app_secret": "",
            "ig_user_id": "",
            "fb_page_id": "",
            "meta_long_lived_token": "",
        },

        "ultimo_upload": {},
    }

    changed = False
    for k, v in defaults.items():
        if k not in user:
            user[k] = v
            changed = True

    if "credenciales" not in user or not isinstance(user["credenciales"], dict):
        user["credenciales"] = defaults["credenciales"]
        changed = True
    else:
        for ck, cv in defaults["credenciales"].items():
            if ck not in user["credenciales"]:
                user["credenciales"][ck] = cv
                changed = True

    if "ultimo_upload" not in user or not isinstance(user["ultimo_upload"], dict):
        user["ultimo_upload"] = {}
        changed = True

    if changed and user.get("nombre"):
        save_user(user)

    return user


def lock_file(nombre: str) -> str:
    return os.path.join(LOCK_DIR, f"{nombre}.lock")


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


def _parse_hhmm(s: str):
    try:
        h, m = s.strip().split(":")
        return int(h), int(m)
    except:
        return 8, 0


def _in_window(start_hm: str, end_hm: str) -> bool:
    now = _now()
    sh, sm = _parse_hhmm(start_hm)
    eh, em = _parse_hhmm(end_hm)

    start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = now.replace(hour=eh, minute=em, second=0, microsecond=0)

    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def _short_error(tb: str, max_chars: int = 1400) -> str:
    tb = tb.strip()
    if len(tb) <= max_chars:
        return tb
    return tb[-max_chars:]


def _reset_daily_if_needed(user: dict) -> dict:
    today = _today_str()
    if user.get("videos_hoy_fecha") != today:
        user["videos_hoy_fecha"] = today
        user["videos_hoy"] = 0
    return user


def _user_platform_profile(nombre: str, plataforma: str) -> str:
    base = os.path.join(SESSIONS_DIR, nombre, plataforma)
    os.makedirs(base, exist_ok=True)
    prof = os.path.join(base, "chrome_profile")
    os.makedirs(prof, exist_ok=True)
    return prof


def _log_upload(user: dict, platform: str, ok: bool, error: str = "") -> None:
    up = user.get("ultimo_upload", {}) or {}
    up[platform] = {"ok": bool(ok), "ts": _now_str(), "error": (error or "")[:1500]}
    user["ultimo_upload"] = up


def publish_for_user(user: dict, video_path: str) -> None:
    nombre = user.get("nombre", "")
    continuar = bool(user.get("continuar_si_falla", True))

    nicho = (user.get("nicho") or "video").strip()
    idioma = (user.get("idioma") or "es").strip()
    titulo = f"{nicho} • {idioma} #shorts"

    # YouTube
    if user.get("youtube_activo", True):
        try:
            ok = bool(subir_youtube(video_path, titulo, user=user))
            _log_upload(user, "youtube", ok, "" if ok else "subir_youtube devolvió False")
        except Exception:
            err = _short_error(traceback.format_exc())
            _log_upload(user, "youtube", False, err)
            if not continuar:
                raise

    # TikTok
    if user.get("tiktok_activo", False):
        try:
            backend = (user.get("tiktok_backend", "selenium") or "selenium").lower()
            if backend != "selenium":
                raise RuntimeError(f"TikTok backend '{backend}' aún no implementado. Usa selenium por ahora.")
            profile_dir = _user_platform_profile(nombre, "tiktok")
            subir_tiktok(video_path, titulo, profile_dir=profile_dir)
            _log_upload(user, "tiktok", True, "")
        except Exception:
            err = _short_error(traceback.format_exc())
            _log_upload(user, "tiktok", False, err)
            if not continuar:
                raise

    # Instagram
    if user.get("instagram_activo", False):
        try:
            backend = (user.get("instagram_backend", "selenium") or "selenium").lower()
            if backend != "selenium":
                raise RuntimeError(f"Instagram backend '{backend}' aún no implementado. Usa selenium por ahora.")
            profile_dir = _user_platform_profile(nombre, "instagram")
            subir_instagram(video_path, titulo, profile_dir=profile_dir)
            _log_upload(user, "instagram", True, "")
        except Exception:
            err = _short_error(traceback.format_exc())
            _log_upload(user, "instagram", False, err)
            if not continuar:
                raise

    # Facebook
    if user.get("facebook_activo", False):
        try:
            backend = (user.get("facebook_backend", "selenium") or "selenium").lower()
            if backend != "selenium":
                raise RuntimeError(f"Facebook backend '{backend}' aún no implementado. Usa selenium por ahora.")
            profile_dir = _user_platform_profile(nombre, "facebook")
            subir_facebook(video_path, titulo, profile_dir=profile_dir)
            _log_upload(user, "facebook", True, "")
        except Exception:
            err = _short_error(traceback.format_exc())
            _log_upload(user, "facebook", False, err)
            if not continuar:
                raise


def run_job(user: dict) -> None:
    nombre = user.get("nombre", "")
    if not nombre:
        return

    if not try_acquire_lock(nombre):
        return

    try:
        user = ensure_defaults(user)
        user = _reset_daily_if_needed(user)

        user["estado"] = "generando"
        user["ultimo_error"] = ""
        user["ultimo_run"] = _now_str()
        user["last_run_ts"] = int(time.time())
        save_user(user)

        video_path = generar_video_usuario(user)

        user = ensure_defaults(load_user_file(user_path(nombre)))
        user = _reset_daily_if_needed(user)

        try:
            publish_for_user(user, video_path)
        finally:
            save_user(user)  # guarda logs de uploads aunque fallen

        user = ensure_defaults(load_user_file(user_path(nombre)))
        user = _reset_daily_if_needed(user)
        user["estado"] = "completado"
        user["ultimo_video"] = video_path
        user["ultimo_error"] = ""
        user["ultimo_run"] = _now_str()
        user["last_run_ts"] = int(time.time())
        user["videos_hoy"] = int(user.get("videos_hoy", 0)) + 1
        save_user(user)

    except Exception:
        tb = traceback.format_exc()
        try:
            user = ensure_defaults(load_user_file(user_path(nombre)))
            user = _reset_daily_if_needed(user)
            user["estado"] = "error"
            user["ultimo_error"] = _short_error(tb)
            user["ultimo_run"] = _now_str()
            user["last_run_ts"] = int(time.time())
            save_user(user)
        except:
            pass
    finally:
        release_lock(nombre)


def main():
    print("🕒 Scheduler multinicho + multiusuario iniciado")
    print(f"📌 Tick: cada {TICK_SECONDS}s")
    print(f"📌 Usuarios: {USUARIOS_DIR}")
    print(f"📌 Sessions: {SESSIONS_DIR}")

    while True:
        try:
            if not os.path.exists(USUARIOS_DIR):
                time.sleep(TICK_SECONDS)
                continue

            for fn in os.listdir(USUARIOS_DIR):
                if not fn.endswith(".json"):
                    continue

                path = os.path.join(USUARIOS_DIR, fn)
                try:
                    user = ensure_defaults(load_user_file(path))
                except:
                    continue

                if not user.get("activo_scheduler", True):
                    continue

                nombre = user.get("nombre")
                if not nombre:
                    continue

                if is_locked(nombre):
                    continue

                user = _reset_daily_if_needed(user)
                save_user(user)

                if not _in_window(user.get("ventana_inicio", "08:00"), user.get("ventana_fin", "22:00")):
                    continue

                max_dia = int(user.get("max_videos_dia", 24))
                videos_hoy = int(user.get("videos_hoy", 0))
                if max_dia > 0 and videos_hoy >= max_dia:
                    continue

                interval_min = int(user.get("intervalo_minutos", 60))
                if interval_min < 5:
                    interval_min = 5

                last_ts = int(user.get("last_run_ts", 0))
                now_ts = int(time.time())

                if now_ts - last_ts >= interval_min * 60:
                    print(f"🚀 Scheduler job: {nombre} | nicho={user.get('nicho')} | idioma={user.get('idioma')} | hoy={videos_hoy}/{max_dia}")
                    run_job(user)

        except Exception as e:
            print("❌ Error en scheduler loop:", str(e))

        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()