import os
import sqlite3
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor

DB_PATH = os.path.join(os.path.dirname(__file__), "dreams.db")


# ── PostgreSQL ────────────────────────────────────────────────────────────────

def _pg_conn():
    return psycopg2.connect(DATABASE_URL)

def _pg_init():
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dreams (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    dream_text TEXT NOT NULL,
                    interpretation_text TEXT DEFAULT '',
                    timestamp TEXT NOT NULL
                )
            """)
        conn.commit()

def _pg_user_exists(user_id: int) -> bool:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
            return cur.fetchone() is not None

def _pg_save_user(user_id: int, username: str, first_name: str):
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET username = EXCLUDED.username, first_name = EXCLUDED.first_name
            """, (user_id, username, first_name))
        conn.commit()

def _pg_save_dream(user_id: int, dream_text: str, interpretation_text: str, dream_id: int = None) -> int:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            if dream_id is None:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                cur.execute("""
                    INSERT INTO dreams (user_id, dream_text, interpretation_text, timestamp)
                    VALUES (%s, %s, %s, %s) RETURNING id
                """, (user_id, dream_text, interpretation_text, ts))
                new_id = cur.fetchone()[0]
            else:
                cur.execute("UPDATE dreams SET interpretation_text = %s WHERE id = %s",
                            (interpretation_text, dream_id))
                new_id = dream_id
        conn.commit()
    return new_id

def _pg_get_dreams(user_id: int, limit: int = 20) -> list[dict]:
    with _pg_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, dream_text, interpretation_text, timestamp
                FROM dreams WHERE user_id = %s
                ORDER BY id DESC LIMIT %s
            """, (user_id, limit))
            return [dict(r) for r in reversed(cur.fetchall())]

def _pg_clear_dreams(user_id: int):
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM dreams WHERE user_id = %s", (user_id,))
        conn.commit()


# ── SQLite ────────────────────────────────────────────────────────────────────

def _sqlite_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _sqlite_init():
    with _sqlite_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                first_seen TEXT
            );
            CREATE TABLE IF NOT EXISTS dreams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                dream_text TEXT NOT NULL,
                interpretation_text TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
        conn.commit()

def _sqlite_user_exists(user_id: int) -> bool:
    with _sqlite_conn() as conn:
        return conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone() is not None

def _sqlite_save_user(user_id: int, username: str, first_name: str):
    with _sqlite_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, first_seen)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()

def _sqlite_save_dream(user_id: int, dream_text: str, interpretation_text: str, dream_id: int = None) -> int:
    with _sqlite_conn() as conn:
        if dream_id is not None:
            conn.execute("UPDATE dreams SET interpretation_text = ? WHERE id = ?",
                         (interpretation_text, dream_id))
            conn.commit()
            return dream_id
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur = conn.execute("""
            INSERT INTO dreams (user_id, dream_text, interpretation_text, timestamp)
            VALUES (?, ?, ?, ?)
        """, (user_id, dream_text, interpretation_text, ts))
        conn.commit()
        return cur.lastrowid

def _sqlite_get_dreams(user_id: int, limit: int = 20) -> list[dict]:
    with _sqlite_conn() as conn:
        rows = conn.execute("""
            SELECT id, dream_text, interpretation_text, timestamp
            FROM dreams WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
        """, (user_id, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

def _sqlite_clear_dreams(user_id: int):
    with _sqlite_conn() as conn:
        conn.execute("DELETE FROM dreams WHERE user_id = ?", (user_id,))
        conn.commit()


# ── Public API ────────────────────────────────────────────────────────────────

def init_db():
    _pg_init() if USE_POSTGRES else _sqlite_init()

def user_exists(user_id: int) -> bool:
    return _pg_user_exists(user_id) if USE_POSTGRES else _sqlite_user_exists(user_id)

def save_user(user_id: int, username: str, first_name: str):
    _pg_save_user(user_id, username, first_name) if USE_POSTGRES else _sqlite_save_user(user_id, username, first_name)

def save_dream(user_id: int, dream_text: str, interpretation_text: str, dream_id: int = None) -> int:
    return _pg_save_dream(user_id, dream_text, interpretation_text, dream_id) if USE_POSTGRES \
        else _sqlite_save_dream(user_id, dream_text, interpretation_text, dream_id)

def get_dreams(user_id: int, limit: int = 20) -> list[dict]:
    return _pg_get_dreams(user_id, limit) if USE_POSTGRES else _sqlite_get_dreams(user_id, limit)

def clear_dreams(user_id: int):
    _pg_clear_dreams(user_id) if USE_POSTGRES else _sqlite_clear_dreams(user_id)

def get_all_dreams_text(user_id: int) -> str:
    dreams = get_dreams(user_id, limit=1000)
    if not dreams:
        return ""
    lines = ["ДНЕВНИК СНОВ\n" + "=" * 40 + "\n"]
    for i, d in enumerate(dreams, 1):
        lines.append(f"Сон #{i} — {d['timestamp']}")
        lines.append(f"Описание:\n{d['dream_text']}")
        if d.get("interpretation_text"):
            lines.append(f"\nАнализ:\n{d['interpretation_text']}")
        lines.append("\n" + "-" * 40 + "\n")
    return "\n".join(lines)
