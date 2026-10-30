import sqlite3
import time
from datetime import datetime, timedelta, timezone
from config import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    # The tracker process writes this database continuously while a live view
    # polls it. Under the default rollback journal a concurrent read can hit
    # "database is locked", so switch to WAL, which lets readers and the writer
    # proceed without blocking each other.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def get_last_poll():
    """Return the started_at of the most recent session, or None."""
    conn = _connect()
    row = conn.execute("SELECT MAX(started_at) FROM sessions").fetchone()
    conn.close()
    return row[0] if row else None


def _day_cutoff():
    """Return unix timestamp for 6am today (or yesterday 6am if before 6am)."""
    now = datetime.now()
    target = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now < target:
        target -= timedelta(days=1)
    return target.timestamp()


def _yesterday_cutoff():
    """Return unix timestamp for yesterday 6am (start of previous focus day)."""
    now = datetime.now()
    today = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now < today:
        today -= timedelta(days=1)
    return (today - timedelta(days=1)).timestamp()


def _week_cutoff():
    """Return unix timestamp for the most recent Monday at 6am."""
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    cutoff = monday.replace(hour=6, minute=0, second=0, microsecond=0)
    if now < cutoff:
        cutoff -= timedelta(days=7)
    return cutoff.timestamp()


def _fortnight_cutoff():
    """Return unix timestamp for 14 days ago at 6am."""
    now = datetime.now()
    cutoff = now.replace(hour=6, minute=0, second=0, microsecond=0)
    return (cutoff - timedelta(days=14)).timestamp()


def _month_cutoff():
    """Return unix timestamp for the 1st of this month at 6am."""
    now = datetime.now()
    cutoff = now.replace(day=1, hour=6, minute=0, second=0, microsecond=0)
    if now < cutoff:
        cutoff = (cutoff - timedelta(days=1)).replace(day=1)
    return cutoff.timestamp()


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


def get_today_start():
    """Return unix timestamp of the first tracking session today, or None."""
    conn = _connect()
    row = conn.execute(
        "SELECT MIN(started_at) FROM sessions WHERE started_at >= ?",
        (_day_cutoff(),),
    ).fetchone()
    conn.close()
    return row[0]


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
    today_start = _day_cutoff()
    yesterday_start = _yesterday_cutoff()
    week_start = _week_cutoff()
    fortnight_start = _fortnight_cutoff()
    month_start = _month_cutoff()

    def _agg(cutoff, until=None):
        params = ()
        cond = "duration_seconds > 0"
        if cutoff is True:
            rows = conn.execute(
                f"SELECT app_name, COALESCE(SUM(duration_seconds),0) FROM sessions WHERE {cond} GROUP BY app_name"
            ).fetchall()
            return {app: round(secs) for app, secs in rows}
        if cutoff is not None:
            params += (cutoff,)
            cond += " AND started_at >= ?"
        if until is not None:
            params += (until,)
            cond += " AND started_at < ?"
        rows = conn.execute(
            f"SELECT app_name, COALESCE(SUM(duration_seconds),0) FROM sessions WHERE {cond} GROUP BY app_name",
            params,
        ).fetchall()
        return {app: round(secs) for app, secs in rows}

    return {
        "today": _agg(today_start),
        "yesterday": _agg(yesterday_start, until=today_start),
        "fortnight": _agg(fortnight_start),
        "week": _agg(week_start),
        "month": _agg(month_start),
        "all_time": _agg(True),
    }


def get_daily_breakdown(days=7):
    conn = _connect()
    cutoff = time.time() - days * 86400
    rows = conn.execute(
        """SELECT date(started_at, 'unixepoch') as day, app_name, SUM(duration_seconds)
         FROM sessions WHERE duration_seconds > 0 AND started_at >= ?
         GROUP BY day, app_name ORDER BY day DESC, SUM(duration_seconds) DESC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [(day, app, round(secs)) for day, app, secs in rows]
