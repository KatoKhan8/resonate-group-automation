"""Local, content-hashed frontend assets. No CDN or runtime dependencies.

Only named files are exposed by the HTTP layer; request paths are never
joined to the filesystem. ``src.web.build`` checks these same bytes.
"""
import hashlib
from pathlib import Path

STATIC = Path(__file__).with_name('static')


def digest(text):
    data = text.encode('utf-8') if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()[:12]


CSS = (STATIC / 'app.css').read_text(encoding='utf-8')
JS = (STATIC / 'app.js').read_text(encoding='utf-8')
LOGO = (STATIC / 'resonate-logo.png').read_bytes()
CSS_VERSION = digest(CSS)
JS_VERSION = digest(JS)
LOGO_VERSION = digest(LOGO)
