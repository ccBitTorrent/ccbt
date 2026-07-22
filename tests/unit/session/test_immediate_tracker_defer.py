"""Tests for deferred tracker immediate peer enqueue and session wiring."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.session.session import AsyncTorrentSession

pytestmark = [pytest.mark.unit]


def _session_config() -> SimpleNamespace:
    return SimpleNamespace(
        discovery=SimpleNamespace(tracker_immediate_pending_budget_max=400),
    )


@pytest.mark.asyncio
async def test_defer_immediate_tracker_peers_to_pending_enqueues() -> None:
    """Burst-circuit path should enqueue peers on the peer manager pending queue."""
    peers = [{"ip": "10.0.0.1", "port": 6881, "peer_source": "tracker"}]
    mock_pm = MagicMock()
    mock_pm.enqueue_peer_dicts_pending = AsyncMock(return_value=1)
    mock_pm.request_pending_resume = MagicMock()
    mock_pm._schedule_pending_resume = MagicMock()

    session = SimpleNamespace(
        info=SimpleNamespace(name="test-torrent"),
        download_manager=SimpleNamespace(peer_manager=mock_pm),
        logger=logging.getLogger("test_immediate_defer"),
        config=_session_config(),
        _peer_discovery_metrics={},
    )
    session._refresh_outbound_pending_peer_queue_metric = AsyncMock(return_value=0)
    recorded: list[tuple[list[dict], str]] = []

    def record_discovered_peers(pl: list[dict], source: str = "tracker") -> None:
        recorded.append((pl, source))

    session.record_discovered_peers = record_discovered_peers

    n = await AsyncTorrentSession._defer_immediate_tracker_peers_to_pending(
        session,
        peers,
        reason="immediate_circuit_breaker_burst",
        tracker_url="udp://tracker.example:1337",
    )
    assert n == 1
    mock_pm.enqueue_peer_dicts_pending.assert_awaited_once()
    mock_pm.request_pending_resume.assert_called_once_with(
        reason="immediate_circuit_breaker_burst"
    )
    mock_pm._schedule_pending_resume.assert_not_called()
    assert len(recorded) == 1
    assert recorded[0][0] == peers
    assert recorded[0][1] == "tracker"


@pytest.mark.asyncio
async def test_defer_immediate_tracker_peers_no_peer_manager() -> None:
    """Without peer_manager, defer returns 0 and does not raise."""
    session = SimpleNamespace(
        info=SimpleNamespace(name="x"),
        download_manager=SimpleNamespace(peer_manager=None),
        logger=logging.getLogger("test_immediate_defer"),
        config=_session_config(),
    )
    session.record_discovered_peers = MagicMock()

    n = await AsyncTorrentSession._defer_immediate_tracker_peers_to_pending(
        session,
        [{"ip": "1.1.1.1", "port": 1}],
        reason="immediate_circuit_breaker_burst",
        tracker_url="u",
    )
    assert n == 0
