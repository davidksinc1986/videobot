import json
import os
import sqlite3
import threading
from typing import Optional

from config import DB_PATH, USUARIOS_DIR

_DB_LOCK = threading.Lock()


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA foreign_keys=ON;")
    return c


def init_db() -> None:
    with _DB_LOCK:
        with _conn() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    name TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )


def save_user(user: dict) -> None:
    name = (user or {}).get("nombre", "").strip()
    if not name:
        raise ValueError("User payload must include 'nombre'")

    init_db()
    payload = json.dumps(user, ensure_ascii=False)

    with _DB_LOCK:
        with _conn() as con:
            con.execute(
                """
                INSERT INTO users(name, payload, updated_at)
                VALUES(?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (name, payload),
            )


def load_user(name: str) -> dict:
    init_db()
    with _conn() as con:
        row = con.execute("SELECT payload FROM users WHERE name = ?", (name,)).fetchone()
    if not row:
        raise FileNotFoundError(name)
    return json.loads(row[0])


def list_users() -> list[dict]:
    init_db()
    with _conn() as con:
        rows = con.execute("SELECT payload FROM users ORDER BY LOWER(name) ASC").fetchall()
    users = []
    for (payload,) in rows:
        try:
            users.append(json.loads(payload))
        except Exception:
            continue
    return users


def user_exists(name: str) -> bool:
    init_db()
    with _conn() as con:
        row = con.execute("SELECT 1 FROM users WHERE name = ?", (name,)).fetchone()
    return bool(row)


def delete_user(name: str) -> None:
    init_db()
    with _conn() as con:
        con.execute("DELETE FROM users WHERE name = ?", (name,))


def migrate_json_users_if_needed() -> int:
    """Import legacy users/*.json into SQLite if they don't exist there."""
    init_db()
    if not os.path.isdir(USUARIOS_DIR):
        return 0

    imported = 0
    for fn in os.listdir(USUARIOS_DIR):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(USUARIOS_DIR, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = (data or {}).get("nombre", "").strip()
            if not name or user_exists(name):
                continue
            save_user(data)
            imported += 1
        except Exception:
            continue
    return imported


def export_user_json(name: str, dest_path: Optional[str] = None) -> str:
    """Compatibility helper for modules that still need a JSON file path."""
    user = load_user(name)
    final_path = dest_path or os.path.join(USUARIOS_DIR, f"{name}.json")
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    with open(final_path, "w", encoding="utf-8") as f:
        json.dump(user, f, ensure_ascii=False, indent=2)
    return final_path
