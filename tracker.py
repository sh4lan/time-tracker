import ctypes
import os
import signal
import subprocess
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

_PROCESS_TERMINATE = 0x0001
_SYNCHRONIZE = 0x00100000
_WAIT_TIMEOUT = 0x00000102


def _signal_handler(signum, frame):
    global _running
    _running = False


def _read_pid():
    try:
        return int(PID_PATH.read_text().strip())
    except (OSError, ValueError):
        return None


def _is_running(pid):
    """Check liveness via OpenProcess. os.kill(pid, 0) does not work on Windows."""
    if pid is None:
        return False
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == _WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def _terminate(pid):
    if pid is None:
        return False
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_PROCESS_TERMINATE, False, pid)
    if not handle:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return False
    try:
        return bool(kernel32.TerminateProcess(handle, 0))
    finally:
        kernel32.CloseHandle(handle)


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
    pid = _read_pid()
    if pid is None:
        return False
    if _is_running(pid):
        return True
    PID_PATH.unlink(missing_ok=True)
    return False


def stop_tracking():
    pid = _read_pid()
    if pid is None:
        return
    if not _terminate(pid):
        PID_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    start_tracking()
