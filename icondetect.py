"""Cross-platform application icon lookup.

Finds the icon file for a given app name and returns it as PNG bytes.
On Linux: searches freedesktop icon themes, then .desktop file mappings.
On Windows: uses win32gui.ExtractIconEx.
Falls back to a generated SVG with the app's first letter if nothing found.
"""

import io
import os
import sys
import struct
from pathlib import Path
from xml.sax.saxutils import escape

try:
    from PIL import Image
except ImportError:
    Image = None

_CACHE: dict[str, bytes | None] = {}
_DESKTOP_MAP: dict[str, str] | None = None  # normalized app name → icon name
_THEME_DIRS: list[Path] = []


def _build_desktop_map():
    """Parse .desktop files and build normalized_name → icon_name mapping."""
    mapping = {}

    desktop_dirs = [
        Path.home() / ".local" / "share" / "applications",
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        Path("/var/lib/snapd/desktop/applications"),
    ]

    for dd in desktop_dirs:
        if not dd.exists():
            continue
        for f in sorted(dd.iterdir()):
            if not f.name.endswith(".desktop"):
                continue
            try:
                lines = f.read_text("utf-8", errors="replace").split("\n")
                icon = ""
                wm_class = ""
                name = ""
                in_entry = False
                for line in lines:
                    stripped = line.strip()
                    if stripped == "[Desktop Entry]":
                        in_entry = True
                    elif stripped.startswith("[") and stripped != "[Desktop Entry]":
                        in_entry = False
                    elif in_entry:
                        if stripped.startswith("Icon="):
                            icon = stripped[5:].strip()
                        elif stripped.startswith("Name="):
                            name = stripped[5:].strip()
                        elif stripped.startswith("StartupWMClass="):
                            wm_class = stripped[15:].strip().lower()

                base = f.stem.lower()

                # Normalized basename lookup
                srcs = [base, name.lower().replace(" ", "-"), wm_class]
                # Also add the raw name
                if name:
                    srcs.append(name.lower())

                if icon:
                    for src in srcs:
                        if src and src not in mapping:
                            mapping[src] = icon
            except Exception:
                continue

    return mapping


def _init_theme_dirs():
    """Find all icon theme directories to search."""
    dirs = set()
    base = Path("/usr/share/icons")
    if base.exists():
        for entry in base.iterdir():
            if entry.is_dir():
                dirs.add(entry)

    local = Path.home() / ".icons"
    if local.exists():
        for entry in local.iterdir():
            if entry.is_dir():
                dirs.add(entry)

    return sorted(dirs, key=lambda p: p.name != "hicolor")  # prefer non-hicolor themes


def _find_icon_file(icon_name: str) -> Path | None:
    """Search icon theme directories for an icon file. Returns path or None."""
    if not icon_name:
        return None

    extensions = [".png", ".svg"]
    sizes = ["48x48", "64x64", "32x32", "256x256", "128x128", "scalable"]
    subdirs = ["apps", "places", "devices", "categories", "emblems"]

    # First check pixmaps for PNG
    pixmap = Path(f"/usr/share/pixmaps/{icon_name}.png")
    if pixmap.exists():
        return pixmap

    # Search theme directories
    for theme_dir in _THEME_DIRS:
        for size in sizes:
            for ext in extensions:
                for sub in subdirs:
                    path = theme_dir / size / sub / f"{icon_name}{ext}"
                    if path.exists():
                        return path

    return None


def _desktop_icon_lookup(app_name: str) -> str | None:
    """Use desktop file mappings to find an icon name."""
    global _DESKTOP_MAP
    if _DESKTOP_MAP is None:
        _DESKTOP_MAP = _build_desktop_map()
    return _DESKTOP_MAP.get(app_name.lower())


def _svg_fallback_icon(app_name: str) -> bytes:
    """Generate an SVG icon with the first letter of the app name."""
    letter = app_name[0].upper() if app_name else "?"
    # Deterministic color from app name
    h = 0
    for c in app_name:
        h = ((h << 5) - h) + ord(c)
    colors = ["#d48c6b","#7aa89f","#b892c4","#c48a7a","#8fb0c7","#c4a57a","#9ab87a","#c47a94","#7ab8a8","#b8a07a"]
    color = colors[abs(h) % len(colors)]

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <rect width="48" height="48" rx="10" fill="{color}" opacity="0.15"/>
  <text x="24" y="30" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,sans-serif" font-size="22" font-weight="600" fill="{color}">{escape(letter)}</text>
</svg>'''
    return svg.encode("utf-8")


def _icon_to_png_bytes(path: Path) -> bytes | None:
    """Convert an icon file to PNG bytes. Handles PNG and SVG inputs."""
    if not path.exists():
        return None

    ext = path.suffix.lower()
    data = path.read_bytes()

    if ext == ".png":
        return data

    if ext == ".svg" and Image is not None:
        try:
            import cairosvg
            png_data = cairosvg.svg2png(data, output_width=48, output_height=48)
            return png_data
        except ImportError:
            # Return SVG as-is — browser can render it
            return data

    if ext == ".xpm" and Image is not None:
        img = Image.open(path)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # For anything else try PIL
    if Image is not None:
        try:
            img = Image.open(path)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            pass

    return None


def _extract_win32_icon(app_name: str) -> bytes | None:
    """Extract icon from a Windows executable."""
    if sys.platform != "win32":
        return None

    try:
        import win32gui
        import win32api
        import win32con
    except ImportError:
        return None

    try:
        # Try common exe locations
        base = app_name.lower().replace(" ", "")
        search_paths = [
            base,
            f"C:\\Program Files\\{base}\\{base}.exe",
            f"C:\\Program Files (x86)\\{base}\\{base}.exe",
        ]
        exe_path = None
        for sp in search_paths:
            if os.path.exists(sp):
                exe_path = sp
                break

        if not exe_path:
            return None

        large, small = win32gui.ExtractIconEx(exe_path, 0)
        if not large:
            return None

        hicon = large[0]

        # Convert HICON to PIL Image
        import win32ui
        import win32gui as wg

        icon_info = wg.GetIconInfo(hicon)
        hbm_color = icon_info[4]
        hbm_mask = icon_info[5]

        bmp = win32ui.CreateBitmapFromHandle(hbm_color)
        bmp_info = bmp.GetInfo()
        width, height = bmp_info['bmWidth'], bmp_info['bmHeight']

        # Convert to PIL
        from PIL import Image as PILImage
        hdc = win32ui.CreateDCFromHandle(wg.GetDC(0))
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(hdc, width, height)
        mdc = hdc.CreateCompatibleDC()
        mdc.SelectObject(bitmap)
        mdc.DrawIcon((0, 0), hicon)

        bits = bitmap.GetBitmapBits(True)
        img = PILImage.frombuffer("RGBA", (width, height), bits, "raw", "BGRA", 0, 1)
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        wg.DeleteObject(hicon)
        wg.DeleteObject(hbm_color)
        wg.DeleteObject(hbm_mask)
        win32ui.DeleteObject(bitmap)
        win32ui.DeleteDC(mdc)
        win32ui.DeleteDC(hdc)

        return buf.getvalue()
    except Exception:
        return None


def get_app_icon_png(app_name: str) -> bytes:
    """Return PNG bytes for the given app name."""
    if not app_name:
        return _svg_fallback_icon("?")

    cached = _CACHE.get(app_name)
    if cached is not None:
        return cached

    # 1. Try direct icon file (Linux / macOS)
    if sys.platform != "win32":
        if not _THEME_DIRS:
            _init()
        icon_name = None
        # First try as-is
        path = _find_icon_file(app_name.lower())
        if path:
            png = _icon_to_png_bytes(path)
            if png:
                _CACHE[app_name] = png
                return png

        # Then try desktop file mapping
        mapped = _desktop_icon_lookup(app_name)
        if mapped:
            path = _find_icon_file(mapped)
            if path:
                png = _icon_to_png_bytes(path)
                if png:
                    _CACHE[app_name] = png
                    return png

    # 2. Try Windows icon extraction
    if sys.platform == "win32":
        png_data = _extract_win32_icon(app_name)
        if png_data:
            _CACHE[app_name] = png_data
            return png_data

    # 3. Fallback: generated SVG
    fallback = _svg_fallback_icon(app_name)
    _CACHE[app_name] = fallback
    return fallback


def _init():
    global _THEME_DIRS
    _THEME_DIRS = _init_theme_dirs()


# Initialize at import time
_init()
