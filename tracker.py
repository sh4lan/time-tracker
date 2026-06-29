import os
import signal
import sys
import time

from config import POLL_INTERVAL, PID_PATH
from detector import get_active_window
from storage import (
    init_db,
    start_session,
    extend_session,
    end_session,
    get_active_session,
)

_running = True
_last_app = None
_session_id = None


def _signal_handler(signum, frame):
    global _running
    _running = False


def _write_pid():
    PID_PATH.write_text(str(os.getpid()))


def _remove_pid():
    if PID_PATH.exists():
        PID_PATH.unlink()


def start_tracking():
    init_db()
    _write_pid()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    global _last_app, _session_id

    existing = get_active_session()
    if existing:
        _last_app = existing["app_name"]
        _session_id = existing["id"]

    while _running:
        app_name, window_title = get_active_window()

        if app_name:
            if app_name != _last_app:
                if _session_id is not None:
                    end_session(_session_id)
                _session_id = start_session(app_name, window_title)
                _last_app = app_name
            elif _session_id is not None:
                extend_session(_session_id, POLL_INTERVAL)

        time.sleep(POLL_INTERVAL)

    if _session_id is not None:
        end_session(_session_id)
    _remove_pid()


def is_tracking():
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        PID_PATH.unlink(missing_ok=True)
        return False


def stop_tracking():
    if not PID_PATH.exists():
        return
    try:
        pid = int(PID_PATH.read_text().strip())
        os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError):
        PID_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    start_tracking()
