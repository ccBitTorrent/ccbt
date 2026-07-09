"""Unit tests for tracker transport utility helpers."""

from __future__ import annotations

import pytest

from ccbt.utils.tracker_utils import (
    tracker_url_implies_tls,
    tracker_url_is_udp,
    tracker_url_transport_tier,
    tracker_url_uses_https,
)


class TestTrackerUtils:
    """Tracker URL transport helper behavior."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://tracker.example.com/announce", True),
            ("http://tracker.example.com/announce", False),
            ("udp://tracker.example.com:6969", False),
            ("", False),
        ],
    )
    def test_tracker_url_uses_https(self, url: str, expected: bool) -> None:
        """HTTPS detection should only be true for HTTPS URLs."""
        assert tracker_url_uses_https(url) == expected

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://tracker.example.com/announce", True),
            ("http://tracker.example.com/announce", False),
            ("udp://tracker.example.com:6969", False),
            ("", False),
        ],
    )
    def test_tracker_url_implies_tls(self, url: str, expected: bool) -> None:
        """TLS expectation should follow URL transport tier."""
        assert tracker_url_implies_tls(url) == expected

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("udp://tracker.example.com:6969", True),
            ("https://tracker.example.com/announce", False),
            ("http://tracker.example.com/announce", False),
            ("", False),
        ],
    )
    def test_tracker_url_is_udp(self, url: str, expected: bool) -> None:
        """UDP detection should only be true for UDP URLs."""
        assert tracker_url_is_udp(url) == expected

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://tracker.example.com/announce", "HTTPS"),
            ("http://tracker.example.com/announce", "HTTP"),
            ("udp://tracker.example.com:6969", "UDP"),
            ("invalid://tracker.example.com", "UNKNOWN"),
            ("", "UNKNOWN"),
        ],
    )
    def test_tracker_url_transport_tier(self, url: str, expected: str) -> None:
        """Transport tier should classify tracker URLs by URL scheme."""
        assert tracker_url_transport_tier(url) == expected

