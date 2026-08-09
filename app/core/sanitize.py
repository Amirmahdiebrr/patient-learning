"""
app/core/sanitize.py
"""

import bleach

ALLOWED_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "blockquote", "a", "span",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "target", "rel"],
    "span": ["style"],
}


def sanitize_html(raw_html: str | None) -> str | None:
    if raw_html is None:
        return None
    return bleach.clean(raw_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)