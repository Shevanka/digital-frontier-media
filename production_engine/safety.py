"""Helpers for handling untrusted text: Markdown escaping and secret redaction."""

from __future__ import annotations

import os
import re

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_MD_SPECIAL = re.compile(r"([\\`*_\[\]()<>#|~!])")
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=\-]{8,}"),
)


def md_inline(value: object) -> str:
    """Escape text for a single Markdown line (headings, list items, table cells)."""
    text = _CONTROL.sub(" ", str(value if value is not None else ""))
    text = re.sub(r"\s+", " ", text).strip()
    return _MD_SPECIAL.sub(r"\\\1", text)


def md_block(value: object) -> str:
    """Escape multi-line prose: neutralise HTML and link syntax but keep line breaks."""
    text = _CONTROL.sub(" ", str(value if value is not None else ""))
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("[", "\\[").replace("]", "\\]")


def md_url(value: object) -> str:
    """Return a link target that is safe inside Markdown, or '' if the URL is not plain http(s)."""
    from .rss import safe_url

    url = safe_url(str(value) if value is not None else "")
    if url is None:
        return ""
    return (
        url.replace("(", "%28")
        .replace(")", "%29")
        .replace("<", "%3C")
        .replace(">", "%3E")
    )


def safe_log(text: object, limit: int = 500) -> str:
    """Redact secrets, strip terminal control characters and cap the length of a log line."""
    cleaned = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", redact(text))
    return cleaned if len(cleaned) <= limit else cleaned[:limit] + "..."


def redact(text: object) -> str:
    """Remove API-key-looking strings, bearer tokens and the configured key from text."""
    out = str(text)
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if len(key) >= 8:
        out = out.replace(key, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out
