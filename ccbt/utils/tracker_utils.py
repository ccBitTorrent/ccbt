"""Utilities for tracker URL transport classification."""

from __future__ import annotations

from urllib.parse import urlparse


def tracker_url_scheme(url: str) -> str:
    """Return normalized tracker URL scheme in lower-case."""
    parsed = urlparse(url)
    return (parsed.scheme or "").lower()


def tracker_url_uses_https(url: str) -> bool:
    """Return True when the tracker URL is HTTPS, and therefore TLS applies."""
    return tracker_url_scheme(url) == "https"


def tracker_url_implies_tls(url: str) -> bool:
    """Return True when tracker URL transport is expected to use TLS."""
    return tracker_url_uses_https(url)


def tracker_url_is_udp(url: str) -> bool:
    """Return True when the tracker URL is a UDP tracker URL."""
    return tracker_url_scheme(url) == "udp"


def tracker_url_transport_tier(url: str) -> str:
    """Return tracker transport tier tag for a URL."""
    scheme = tracker_url_scheme(url)
    if scheme in {"http", "https"}:
        return scheme.upper()
    if scheme == "udp":
        return "UDP"
    return "UNKNOWN"
