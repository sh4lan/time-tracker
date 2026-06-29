import sqlite3
import time
from config import DB_PATH


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _connect()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY,
            app_name TEXT NOT NULL,
            window_title TEXT,
            started_at REAL NOT NULL,
            ended_at REAL,
            duration_seconds REAL DEFAULT 0
        )"""
    )
    conn.commit()
    conn.close()


def start_session(app_name, window_title):
    conn = _connect()
    now = time.time()
    cur = conn.execute(
        "INSERT INTO sessions (app_name, window_title, started_at, duration_seconds) VALUES (?, ?, ?, 0)",
        (app_name, window_title, now),
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def extend_session(session_id, duration):
    conn = _connect()
    conn.execute(
        "UPDATE sessions SET duration_seconds = duration_seconds + ? WHERE id = ?",
        (duration, session_id),
    )
    conn.commit()
    conn.close()


def end_session(session_id):
    conn = _connect()
    now = time.time()
    conn.execute(
        "UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
        (now, session_id),
    )
    conn.commit()
    conn.close()


def get_active_session():
    conn = _connect()
    cur = conn.execute(
        "SELECT id, app_name, window_title, started_at FROM sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "app_name": row[1], "window_title": row[2], "started_at": row[3]}
    return None


def get_summary():
    conn = _connect()
    today_start = int(time.time() - 86400)
    week_start = int(time.time() - 7 * 86400)

    rows = conn.execute(
        """SELECT app_name, SUM(duration_seconds) as total_seconds
         FROM sessions WHERE duration_seconds > 0
         GROUP BY app_name ORDER BY total_seconds DESC"""
    ).fetchall()
    all_time = {app: secs for app, secs in rows}

    rows = conn.execute(
        """SELECT app_name, SUM(duration_seconds)
         FROM sessions WHERE duration_seconds > 0 AND started_at >= ?
         GROUP BY app_name ORDER BY SUM(duration_seconds) DESC""",
        (today_start,),
    ).fetchall()
    today = {app: secs for app, secs in rows}

    rows = conn.execute(
        """SELECT app_name, SUM(duration_seconds)
         FROM sessions WHERE duration_seconds > 0 AND started_at >= ?
         GROUP BY app_name ORDER BY SUM(duration_seconds) DESC""",
        (week_start,),
    ).fetchall()
    week = {app: secs for app, secs in rows}

    conn.close()
    return {"today": today, "week": week, "all_time": all_time}
