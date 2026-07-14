"""Deduplicate tracker announce URLs that target the same host:port endpoint.

HTTP and HTTPS to the same host:port are redundant; prefer HTTPS. UDP (BEP 15)
uses a different wire protocol than HTTP(S) even on the same host:port, so UDP
URLs are never collapsed against HTTP/HTTPS.
"""

from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import urlparse

# Prefer TLS-capable HTTP when the same host:port is reachable as both.
_SCHEME_PRIORITY: dict[str, int] = {
    "https": 3,
    "http": 2,
    "udp": 1,
}


def _default_port_for_scheme(scheme: str) -> Optional[int]:
    s = scheme.lower()
    if s == "http":
        return 80
    if s == "https":
        return 443
    return None


def _scheme_family(scheme: str) -> str:
    """Group schemes for dedupe: UDP is distinct from HTTP/HTTPS."""
    normalized = scheme.lower()
    if normalized == "udp":
        return "udp"
    if normalized in {"http", "https"}:
        return "http"
    return normalized


def tracker_endpoint_key(url: str) -> Optional[Tuple[str, int, str]]:
    """Return (host_lower, port, scheme_family) for deduplication."""
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
        if not host:
            return None
        port = parsed.port
        if port is None:
            port = _default_port_for_scheme(parsed.scheme or "")
        if port is None:
            return None
        return (host, int(port), _scheme_family(parsed.scheme or ""))
    except (TypeError, ValueError):
        return None


def dedupe_tracker_urls_by_host_port(urls: list[str]) -> list[str]:
    """Collapse redundant HTTP/HTTPS URLs on the same host:port.

    UDP announces are kept alongside HTTP(S) on the same host:port because BEP 15
    is a separate protocol. Within HTTP/HTTPS, prefer https > http.

    Order: first occurrence of each endpoint in ``urls`` defines output position.
    Unparseable URLs are appended in original order (string-deduped).
    """
    if not urls:
        return []

    best_by_endpoint: dict[tuple[str, int, str], tuple[int, str]] = {}
    order: list[tuple[str, int, str]] = []
    seen_ep: set[tuple[str, int, str]] = set()
    unparsed: list[str] = []
    unparsed_seen: set[str] = set()

    for raw in urls:
        if not isinstance(raw, str):
            continue
        u = raw.strip()
        if not u:
            continue
        key = tracker_endpoint_key(u)
        if key is None:
            if u not in unparsed_seen:
                unparsed_seen.add(u)
                unparsed.append(u)
            continue
        scheme = (urlparse(u).scheme or "").lower()
        pri = _SCHEME_PRIORITY.get(scheme, 0)
        if key not in seen_ep:
            seen_ep.add(key)
            order.append(key)
            best_by_endpoint[key] = (pri, u)
        else:
            old_pri, _old_url = best_by_endpoint[key]
            if pri > old_pri:
                best_by_endpoint[key] = (pri, u)

    out = [best_by_endpoint[k][1] for k in order]
    out.extend(unparsed)
    return out
