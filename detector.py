import subprocess
import sys


def _linux_get_active_window():
    try:
        win_id = subprocess.run(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        if not win_id:
            return None, None
        win_id = win_id.split()[-1]

        wm_class = subprocess.run(
            ["xprop", "-id", win_id, "WM_CLASS"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        name = subprocess.run(
            ["xprop", "-id", win_id, "_NET_WM_NAME"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()

        app_name = None
        if wm_class:
            parts = wm_class.split('"')
            if len(parts) >= 4:
                app_name = parts[3]

        window_title = None
        if name and "=" in name:
            title_part = name.split("=", 1)[1].strip().strip('"')
            if title_part:
                window_title = title_part

        return app_name, window_title
    except (subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        return None, None


def _win_get_active_window():
    try:
        import win32gui
        import win32process
        import psutil
    except ImportError:
        return None, None

    try:
        hwnd = win32gui.GetForegroundWindow()
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        proc = psutil.Process(pid)
        title = win32gui.GetWindowText(hwnd)
        return proc.name(), title or None
    except Exception:
        return None, None


def get_active_window():
    if sys.platform == "win32":
        return _win_get_active_window()
    return _linux_get_active_window()
