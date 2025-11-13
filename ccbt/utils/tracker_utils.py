"""Tracker helpers (HTTP/UDP) and list manipulation utilities."""

from __future__ import annotations


def ensure_http_fallback(
    tracker_urls: list[str], enable_http_fallback: bool = True
) -> list[str]:
    """Append a small curated HTTP/HTTPS tracker set if no HTTP(S) trackers provided."""
    if not enable_http_fallback:
        return tracker_urls
    has_http = any((u or "").startswith(("http://", "https://")) for u in tracker_urls)
    if has_http:
        return tracker_urls
    fallback_http_trackers = [
        "https://tracker.opentrackr.org:443/announce",
        "https://tracker.torrent.eu.org:443/announce",
        "https://tracker.openbittorrent.com:443/announce",
        "http://tracker.opentrackr.org:1337/announce",
        "http://tracker.openbittorrent.com:80/announce",
    ]
    existing = set(tracker_urls)
    added = [u for u in fallback_http_trackers if u not in existing]
    return tracker_urls + added
