"""Unit tests for authenticated-swarm discovery policy filtering helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ccbt.session.session import AsyncTorrentSession

pytestmark = [pytest.mark.unit]


def _build_session() -> SimpleNamespace:
    """Build a lightweight session object with only required discovery-policy attributes."""
    return SimpleNamespace(
        logger=MagicMock(),
        _emit_discovery_suppressed_metric=MagicMock(),
        _authenticated_discovery_mode=lambda: "trackers_only",
        _discovery_strict_mode_active=lambda: True,
    )


def test_collect_trackers_returns_empty_when_tracker_disabled():
    """When tracker component is disabled, no tracker URLs are returned."""
    session = _build_session()
    session._is_discovery_component_disabled = lambda _component: True

    td = {
        "announce": "http://tracker.example:80",
        "announce_list": [["https://primary.example/announce"], ["udp://secondary.example/6881"]],
        "trackers": ["https://magnet.example/announce"],
    }

    result = AsyncTorrentSession._collect_trackers(session, td)

    assert result == []
    assert session._emit_discovery_suppressed_metric.called


def test_collect_trackers_filters_http_in_strict_trackers_only_mode():
    """Strict strict-mode filtering should remove plain HTTP trackers."""
    session = _build_session()
    session._is_discovery_component_disabled = lambda _component: False
    session._should_filter_tracker_url_for_strict_mode = (
        lambda url: (
            session._discovery_strict_mode_active()
            and session._authenticated_discovery_mode() == "trackers_only"
            and str(url).startswith("http://")
        )
    )

    td = {
        "announce": "http://tracker.example/announce",
        "announce_list": [["https://secure.example/announce"], ["udp://udp.example/6881"]],
        "trackers": ["http://insecure.example/announce", "bad://skip.example"],
    }

    result = AsyncTorrentSession._collect_trackers(session, td)

    assert result == ["https://secure.example/announce", "udp://udp.example/6881"]


def test_collect_trackers_skips_filtering_when_strict_mode_disabled():
    """When strict mode is disabled, HTTP trackers are not suppressed."""
    session = _build_session()
    session._is_discovery_component_disabled = lambda _component: False
    session._discovery_strict_mode_active = lambda: False
    session._should_filter_tracker_url_for_strict_mode = (
        lambda _url: (
            session._discovery_strict_mode_active()
            and session._authenticated_discovery_mode() == "trackers_only"
        )
    )

    td = {
        "announce": "http://tracker.example/announce",
        "announce_list": [["http://insecure.example/announce"]],
        "trackers": ["udp://udp.example/6881"],
    }

    result = AsyncTorrentSession._collect_trackers(session, td)

    assert set(result) == {
        "http://tracker.example/announce",
        "http://insecure.example/announce",
        "udp://udp.example/6881",
    }
