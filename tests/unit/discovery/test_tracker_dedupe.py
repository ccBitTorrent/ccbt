"""Tests for tracker URL deduplication by host:port."""

from __future__ import annotations

import pytest

from ccbt.discovery.tracker_dedupe import dedupe_tracker_urls_by_host_port

pytestmark = pytest.mark.unit


def test_dedupe_prefers_https_over_http_and_keeps_udp_same_port() -> None:
    urls = [
        "udp://tracker.example.com:443/announce",
        "http://tracker.example.com:443/announce",
        "https://tracker.example.com:443/announce",
    ]
    out = dedupe_tracker_urls_by_host_port(urls)
    assert out == [
        "udp://tracker.example.com:443/announce",
        "https://tracker.example.com:443/announce",
    ]


def test_dedupe_keeps_distinct_ports() -> None:
    urls = [
        "https://tracker.opentrackr.org:443/announce",
        "udp://tracker.opentrackr.org:1337/announce",
    ]
    out = dedupe_tracker_urls_by_host_port(urls)
    assert len(out) == 2


def test_dedupe_preserves_first_seen_endpoint_order() -> None:
    urls = [
        "udp://a.example:6969/announce",
        "https://b.example:443/announce",
        "http://a.example:6969/announce",
    ]
    out = dedupe_tracker_urls_by_host_port(urls)
    assert out[0] == "udp://a.example:6969/announce"
    assert out[1] == "https://b.example:443/announce"
    assert out[2] == "http://a.example:6969/announce"


def test_dedupe_keeps_udp_and_http_on_shared_port() -> None:
    urls = [
        "http://tracker.openbittorrent.com:80/announce",
        "udp://tracker.openbittorrent.com:80/announce",
    ]
    out = dedupe_tracker_urls_by_host_port(urls)
    assert out == urls
