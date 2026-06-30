import subprocess
import sys

BROWSERS = {
    "google-chrome", "chrome", "chromium", "chromium-browser",
    "firefox", "mozilla-firefox",
    "brave", "brave-browser",
    "opera", "vivaldi", "microsoft-edge", "edge",
}

_KNOWN_APPS = {
    # browsers
    "google-chrome": "chrome", "chrome": "chrome",
    "chromium-browser": "chrome", "chromium": "chrome",
    "mozilla-firefox": "firefox", "firefox": "firefox",
    "brave-browser": "brave", "brave": "brave",
    "microsoft-edge": "edge",
    # terminals
    "kitty": "terminal",
    "gnome-terminal": "terminal",
    "konsole": "terminal",
    "alacritty": "terminal",
    "wezterm": "terminal",
    "windows-terminal": "terminal",
    # editors / IDEs
    "code": "vscode",
    "code-oss": "vscode",
    "sublime_text": "sublime",
    "subl": "sublime",
    "idea": "intellij",
    "pycharm": "pycharm",
    # communication
    "slack": "slack",
    "discord": "discord",
    "telegram": "telegram",
    "telegram-desktop": "telegram",
    # file mgmt
    "thunar": "files",
    "nautilus": "files",
    "dolphin": "files",
    "explorer": "files",
    "explorer.exe": "files",
}

_SUFFIXES = [
    " — Mozilla Firefox", " — Firefox",
    " - Mozilla Firefox", " - Firefox",
    " - Google Chrome", " - Chromium", " - Brave",
    " - Opera", " - Vivaldi", " - Microsoft Edge",
    " - Google Chrome™",
    # Windows-specific
    " - Microsoft​Edge", " - Internet Explorer",
    " - Firefox Developer Edition",
    " - Chromium",
    " — Chromium",
]


def _normalize_app(app_name):
    """Normalize app names across platforms and recognize known apps."""
    if not app_name:
        return app_name
    name = app_name.lower().replace(" ", "-")
    if name.endswith(".exe"):
        name = name[:-4]
    return _KNOWN_APPS.get(name, app_name)


def _extract_browser_site(app_name, window_title):
    """For browser windows, extract the site from the window title."""
    if not window_title:
        return app_name, window_title

    # Normalize for browser check (strip .exe etc.)
    name = app_name.lower().replace(" ", "-")
    if name.endswith(".exe"):
        name = name[:-4]

    if name not in BROWSERS:
        return app_name, window_title

    title = window_title
    for suffix in _SUFFIXES:
        if title.endswith(suffix):
            title = title[: -len(suffix)]
            break

    title = title.strip()
    if not title:
        return app_name, window_title

    # Remove common prefixes that aren't site names
    for prefix in ["Google Search - "]:
        if title.startswith(prefix):
            title = title[len(prefix) :]
            break

    # Truncate very long titles (usually page descriptions, not site names)
    if len(title) > 60:
        # Try to find a separator that indicates the real site name
        # Many titles are "SiteName - Page Description" or "SiteName: Page"
        for sep in [" - ", " | ", " :: ", " — "]:
            if sep in title:
                title = title.split(sep)[0].strip()
                break
        else:
            title = title[:57] + "..."

    combined = f"{app_name} ({title})"
    return combined, window_title


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

        if app_name:
            app_name = _normalize_app(app_name)
            app_name, window_title = _extract_browser_site(app_name, window_title)

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
        app_name, win_title = proc.name(), title or None
        app_name = _normalize_app(app_name)
        app_name, win_title = _extract_browser_site(app_name, win_title)
        return app_name, win_title
    except Exception:
        return None, None


def get_active_window():
    if sys.platform == "win32":
        return _win_get_active_window()
    return _linux_get_active_window()
