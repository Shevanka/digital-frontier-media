"""Bounded, redirect-aware HTTP fetching for untrusted feeds."""

from __future__ import annotations

import ipaddress
import re
import socket
import time
import urllib.parse
import urllib.request

DEFAULT_MAX_BYTES = 3_000_000
DEFAULT_DEADLINE_SECONDS = 30


class UnsafeUrl(ValueError):
    """Raised when a URL (or a redirect target) is not allowed to be fetched."""


def assert_public_url(url: str) -> None:
    """Allow only http(s) URLs whose host resolves exclusively to public IP addresses.

    Limitation: the name is resolved here and again by the HTTP client, so a hostile DNS
    server could answer differently the second time (DNS rebinding). Run the tool without
    access to internal networks if that matters.
    """
    try:
        parts = urllib.parse.urlsplit(url)
        host, port = parts.hostname, parts.port
    except ValueError as exc:
        raise UnsafeUrl("invalid URL") from exc
    if parts.scheme not in ("http", "https") or not host:
        raise UnsafeUrl("only http(s) URLs with a host are allowed")
    if parts.username or parts.password:
        raise UnsafeUrl("URLs with credentials are not allowed")
    try:
        infos = socket.getaddrinfo(
            host,
            port or (443 if parts.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeUrl("host cannot be resolved") from exc
    if not infos:
        raise UnsafeUrl("host cannot be resolved")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.version == 6 and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            raise UnsafeUrl("host resolves to a non-public address")


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect hop: no downgrade from https and no non-public targets."""

    max_redirections = 3

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urljoin(req.full_url, newurl)
        if (
            urllib.parse.urlsplit(req.full_url).scheme == "https"
            and urllib.parse.urlsplit(target).scheme != "https"
        ):
            raise UnsafeUrl("redirect downgrades from https")
        assert_public_url(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


_OPENER = urllib.request.build_opener(_CheckedRedirect)


def fetch_limited(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
    max_bytes: int = DEFAULT_MAX_BYTES,
    deadline: float = DEFAULT_DEADLINE_SECONDS,
) -> bytes:
    """GET `url` and return the body, failing instead of truncating when it is too large.

    `timeout` bounds each socket operation; `deadline` bounds the time between reads, so the
    worst case is roughly deadline + timeout.
    """
    assert_public_url(url)
    request = urllib.request.Request(url, headers=headers or {})
    end = time.monotonic() + deadline
    chunks: list[bytes] = []
    total = 0
    with _OPENER.open(request, timeout=timeout) as response:
        while True:
            if time.monotonic() > end:
                raise TimeoutError("download exceeded the time limit")
            chunk = response.read(min(65536, max_bytes + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"response larger than {max_bytes} bytes")
            chunks.append(chunk)
    return b"".join(chunks)


def reject_dtd(raw: bytes) -> None:
    """Refuse XML that declares a DOCTYPE or entities (feeds never need them)."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in raw[:200]:
        raise ValueError("unsupported XML encoding")
    if re.search(rb"<!\s*(DOCTYPE|ENTITY)", raw, re.IGNORECASE):
        raise ValueError("XML DOCTYPE/ENTITY declarations are not allowed")
