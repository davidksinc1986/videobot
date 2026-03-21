import os
import time

# Usamos un directorio dentro de temp/ para los locks, que es más efímero
# y menos propenso a dejar basura entre reinicios de contenedor/máquina.
LOCK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp", "locks"))
os.makedirs(LOCK_DIR, exist_ok=True)

def _safe_name(name: str) -> str:
    # Esta función es necesaria aquí para evitar dependencias circulares con app.py
    return "".join(c for c in (name or "").strip() if c.isalnum() or c in ("_", "-", ".")).strip(".")

def lock_file(nombre: str) -> str:
    return os.path.join(LOCK_DIR, f"{_safe_name(nombre)}.lock")

def is_locked(nombre: str) -> bool:
    return os.path.exists(lock_file(nombre))

def try_acquire_lock(nombre: str) -> bool:
    lf = lock_file(nombre)
    try:
        # Usamos os.open con O_CREAT y O_EXCL para una operación atómica de "crear si no existe".
        # Si el archivo ya existe, FilaExistsError es lanzado, indicando que el lock está tomado.
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
    except Exception as e:
        print(f"Error releasing lock for {nombre}: {e}")
        pass
