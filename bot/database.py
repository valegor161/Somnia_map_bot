import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "dreams.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                first_seen TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dreams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                dream_text TEXT NOT NULL,
                interpretation_text TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        conn.commit()

def user_exists(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row is not None

def save_user(user_id: int, username: str, first_name: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, first_seen)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()

def save_dream(user_id: int, dream_text: str, interpretation_text: str, dream_id: int | None = None) -> int:
    with get_conn() as conn:
        if dream_id is not None:
            conn.execute("""
                UPDATE dreams SET interpretation_text = ? WHERE id = ?
            """, (interpretation_text, dream_id))
            conn.commit()
            return dream_id
        else:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            cursor = conn.execute("""
                INSERT INTO dreams (user_id, dream_text, interpretation_text, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_id, dream_text, interpretation_text, ts))
            conn.commit()
            return cursor.lastrowid

def get_dreams(user_id: int, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, dream_text, interpretation_text, timestamp
            FROM dreams
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

def clear_dreams(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM dreams WHERE user_id = ?", (user_id,))
        conn.commit()

def get_all_dreams_text(user_id: int) -> str:
    dreams = get_dreams(user_id, limit=1000)
    if not dreams:
        return ""
    lines = ["ДНЕВНИК СНОВ\n" + "="*40 + "\n"]
    for i, d in enumerate(dreams, 1):
        lines.append(f"Сон #{i} — {d['timestamp']}")
        lines.append(f"Описание:\n{d['dream_text']}")
        if d["interpretation_text"]:
            lines.append(f"\nАнализ:\n{d['interpretation_text']}")
        lines.append("\n" + "-"*40 + "\n")
    return "\n".join(lines)
