import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Asegúrate de que las variables de entorno para Redis están cargadas
# Por ejemplo, REDIS_URL=redis://localhost:6379/0
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Inicialización de la aplicación Celery
celery = Celery(
    "videobot",
    broker=redis_url,
    backend=redis_url,
    include=["tasks"]
)

celery.conf.update(
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)

if __name__ == "__main__":
    celery.start()
