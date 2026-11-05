from __future__ import annotations

import email.utils
import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

from .fetch import fetch_limited, reject_dtd
from .safety import md_inline, md_url, safe_log

try:  # optional: use the certifi CA bundle when installed (e.g. Windows/MSYS2)
    import certifi
except ImportError:
    certifi = None
if certifi is not None:
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())

UA = "DigitalFrontierResearchBot/0.1"
MAX_TITLE = 300
MAX_URL = 2048

def clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

def parse_date(value: str) -> str | None:
    if not value:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None

def parse_iso_date(value: str | None) -> str | None:
    """Normalise an Atom/ISO-8601 timestamp to UTC ISO format, or None if invalid."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()

def safe_url(value: str | None) -> str | None:
    """Return the URL only if it is a plain http(s) URL with a host; otherwise None."""
    value = (value or "").strip()
    if not value or len(value) > MAX_URL or re.search(r"[\x00-\x20\x7f]", value):
        return None
    try:
        parts = urllib.parse.urlsplit(value)
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not host or parts.username or parts.password:
        return None
    return value

def fetch_feed(url: str, name: str, pillar: str, trust: str, timeout: int = 20) -> list[dict]:
    raw = fetch_limited(url, headers={"User-Agent": UA}, timeout=timeout)
    reject_dtd(raw)
    root = ET.fromstring(raw)
    out = []
    for node in root.findall(".//item"):
        title = clean_html(node.findtext("title", ""))[:MAX_TITLE]
        link = safe_url(node.findtext("link", ""))
        if title and link:
            out.append({"title": title, "url": link, "summary": clean_html(node.findtext("description", ""))[:1200],
                        "published_at": parse_date(node.findtext("pubDate", "")), "source": name,
                        "pillar": pillar, "source_trust": trust})
    if not out:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for node in root.findall("a:entry", ns):
            title = clean_html(node.findtext("a:title", "", ns))[:MAX_TITLE]
            link_node = node.find("a:link", ns)
            link = safe_url(link_node.attrib.get("href", "")) if link_node is not None else None
            if title and link:
                out.append({"title": title, "url": link, "summary": clean_html(node.findtext("a:summary", "", ns))[:1200],
                            "published_at": parse_iso_date(node.findtext("a:updated", "", ns)), "source": name,
                            "pillar": pillar, "source_trust": trust})
    return out

def _timestamp(item: dict) -> float:
    """Parsed publication time (0 when missing/invalid, so such items sort last)."""
    iso = parse_iso_date(item.get("published_at"))
    return datetime.fromisoformat(iso).timestamp() if iso else 0

def discover(root: Path, days: int = 7) -> dict:
    config = json.loads((Path(__file__).parent / "config" / "sources.json").read_text(encoding="utf-8"))
    items, errors = [], []
    for feed in config.get("feeds", []):
        try:
            items.extend(fetch_feed(feed["url"], feed["name"], feed["pillar"], feed.get("trust", "secondary")))
        except Exception as exc:
            errors.append({"source": feed.get("name", feed["url"]), "error": safe_log(exc, 300)})
    for query in config.get("google_news_queries", []):
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query["query"]) + "&hl=en-US&gl=US&ceid=US:en"
        try:
            items.extend(fetch_feed(url, "Google News RSS", query["pillar"], "discovery_only"))
        except Exception as exc:
            errors.append({"source": "Google News RSS", "error": safe_log(exc, 300)})
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    seen, unique = set(), []
    for item in items:
        key = item["url"].split("?")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        stamp = _timestamp(item)
        if stamp and stamp < cutoff:
            continue
        item["freshness"] = "recent" if stamp else "undated"
        unique.append(item)
    unique.sort(key=_timestamp, reverse=True)
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "window_days": days,
           "discovery_note": "Discovery leads only. Verify every claim against original sources.", "items": unique, "errors": errors}
    folder = root / "research" / "trends"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (folder / f"{stamp}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# Trend discovery: {stamp}", "", "> Discovery leads only. Do not publish claims until independently verified.", ""]
    for i, item in enumerate(unique, 1):
        lines.extend([f"## {i}. {md_inline(item['title'])}", f"- Pillar: {md_inline(item['pillar'])}", f"- Source: {md_inline(item['source'])}",
                      f"- Published: {item.get('published_at') or 'Unknown'}", f"- URL: {md_url(item['url']) or 'invalid'}", f"- Summary: {md_inline(item['summary'])}", ""])
    (folder / f"{stamp}.md").write_text("\n".join(lines), encoding="utf-8")
    return out
