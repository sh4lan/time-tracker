"""Simple deterministic letter-based icon generation. No real icon lookup."""

from xml.sax.saxutils import escape


def get_app_icon_png(app_name: str) -> bytes:
    """Return an SVG with the first letter of the app name."""
    letter = app_name[0].upper() if app_name else "?"
    h = 0
    for c in app_name:
        h = ((h << 5) - h) + ord(c)
    colors = ["#d48c6b","#7aa89f","#b892c4","#c48a7a","#8fb0c7","#c4a57a","#9ab87a","#c47a94","#7ab8a8","#b8a07a"]
    color = colors[abs(h) % len(colors)]

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
        f'<rect width="48" height="48" rx="10" fill="{color}" opacity="0.15"/>'
        f'<text x="24" y="30" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,sans-serif" font-size="22" font-weight="600" fill="{color}">{escape(letter)}</text>'
        '</svg>'
    )
    return svg.encode("utf-8")
