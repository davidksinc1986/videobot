from celery_app import celery
from locks import try_acquire_lock, release_lock
from generador import generar_video_usuario
from app_context import create_app_for_worker
import time
import traceback
from datetime import datetime
import sentry_sdk

@celery.task(name="process_user_video_job", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_user_video_job(self, user_name: str):
    """
    Tarea Celery para procesar de forma robusta la generación y subida de video.
    Esta tarea es idempotente y segura ante concurrencia gracias al sistema de 'locks'.
    El decorador `autoretry_for` reintentará la tarea en caso de cualquier excepción.
    """
    app = create_app_for_worker()
    with app.app_context():
        from storage import load_user, save_user
        from app import (
            ensure_defaults, _generation_requirements_missing, _now_str,
            _append_event, run_uploads_for_user, _short_error
        )

        if not try_acquire_lock(user_name):
            print(f"User {user_name} is already locked. Skipping job.")
            return {"status": "skipped", "reason": "locked"}

        user = None
        try:
            print(f"Starting Celery job for user: {user_name} (task_id: {self.request.id}, retries: {self.request.retries})")
            user = ensure_defaults(load_user(user_name))

            missing = _generation_requirements_missing(user)
            if missing:
                # No reintentar si faltan credenciales, es un error de configuración.
                raise RuntimeError(f"Faltan credenciales/configuración: {', '.join(missing)}")

            user.update({
                "estado": "generando", "ultimo_error": "",
                "ultimo_run": _now_str(), "last_run_ts": int(time.time())
            })
            _append_event(user, "job_start", f"Job iniciado (task: {self.request.id})")
            save_user(user)

            out = generar_video_usuario(user)
            video_path = str(out)
            if not video_path:
                raise RuntimeError("generar_video_usuario no devolvió una ruta de video válida")

            _append_event(user, "generate_done", "Generación completada", {"video": video_path})
            
            user = ensure_defaults(load_user(user_name))
            user.update({"estado": "subiendo", "ultimo_video": video_path})
            save_user(user)

            upload_results = run_uploads_for_user(user, video_path)

            user = ensure_defaults(load_user(user_name))
            user.update({
                "estado": "completado", "ultimo_error": "",
                "last_run_ts": int(time.time()),
                "videos_hoy": int(user.get("videos_hoy", 0)) + 1,
                "title_counter": int(user.get("title_counter", 0) or 0) + 1,
            })
            if user.get("videos_hoy_fecha") != datetime.now().strftime("%Y-%m-%d"):
                user["videos_hoy_fecha"] = datetime.now().strftime("%Y-%m-%d")
                user["videos_hoy"] = 1

            _append_event(user, "job_done", "Job completado", {"uploads": upload_results})
            
            learning = user.get("generation_learning", {})
            learning.update({"success": int(learning.get("success", 0)) + 1, "last_success_at": _now_str(), "last_error": ""})
            user["generation_learning"] = learning
            save_user(user)

            print(f"Job for {user_name} completed successfully.")
            return {"status": "success", "user": user_name}

        except Exception as e:
            tb_str = _short_error(traceback.format_exc())
            print(f"Job for {user_name} FAILED on attempt {self.request.retries + 1 if self.request.retries else 1}/{self.max_retries}: {tb_str}")
            sentry_sdk.capture_exception(e)

            if user:
                user.update({"estado": "error", "ultimo_error": tb_str, "ultimo_run": _now_str()})
                learning = user.get("generation_learning", {})
                learning.update({"fail": int(learning.get("fail", 0)) + 1, "last_error": tb_str})
                user["generation_learning"] = learning
                save_user(user)
            raise
        finally:
            # Asegurarse de que el lock se libera siempre
            release_lock(user_name)
