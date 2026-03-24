"""Deduplicate tracker announce URLs that target the same host:port endpoint.

Multiple schemes (https/http/udp) to the same endpoint create redundant announces
and multiply load on the shared UDP tracker client. We keep the highest-priority
scheme per endpoint while preserving first-seen ordering of endpoints.
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


def tracker_endpoint_key(url: str) -> Optional[Tuple[str, int]]:
    """Return (host_lower, port) for deduplication, or None if not dedupeable."""
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
        return (host, int(port))
    except (TypeError, ValueError):
        return None


def dedupe_tracker_urls_by_host_port(urls: list[str]) -> list[str]:
    """Collapse URLs that share the same host:port, preferring https > http > udp.

    Order: first occurrence of each endpoint in ``urls`` defines output position.
    Unparseable URLs are appended in original order (string-deduped).
    """
    if not urls:
        return []

    best_by_endpoint: dict[tuple[str, int], tuple[int, str]] = {}
    order: list[tuple[str, int]] = []
    seen_ep: set[tuple[str, int]] = set()
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
