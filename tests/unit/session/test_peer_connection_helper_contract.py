"""Contracts for PeerConnectionHelper submit-status handling."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.session.peers import PeerConnectionHelper

pytestmark = [pytest.mark.unit, pytest.mark.session]


@pytest.mark.asyncio
async def test_connect_peers_skips_delayed_sampling_for_queued_reentrant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queued reentrant submit should not run delayed no-progress sampling."""
    peer_manager = MagicMock()
    peer_manager.connect_to_peers = AsyncMock(
        return_value=SimpleNamespace(status="queued_reentrant", queue_depth_after=3)
    )
    peer_manager.connections = {}
    peer_manager.get_connection_summary = AsyncMock(
        return_value={"active_connections": 0}
    )

    session = SimpleNamespace(
        logger=logging.getLogger("test_peer_connection_helper_contract"),
        info=SimpleNamespace(name="contract-torrent"),
        download_manager=SimpleNamespace(peer_manager=peer_manager),
        _queued_peers=[],
        _peer_discovery_metrics={
            "connection_attempts": 0,
            "last_peer_discovery_time": 0.0,
            "peers_converted_to_attempts_by_source": {"tracker": 0, "unknown": 0},
        },
        record_peer_connection_batch_metrics=MagicMock(),
    )
    helper = PeerConnectionHelper(session)
    monkeypatch.setattr(helper, "_rank_peers_by_quality", lambda peers: peers)
    sleep_spy = AsyncMock()
    monkeypatch.setattr("ccbt.session.peers.asyncio.sleep", sleep_spy)

    await helper.connect_peers_to_download(
        [{"ip": "192.0.2.50", "port": 6881, "peer_source": "tracker"}]
    )

    sleep_spy.assert_not_awaited()
    peer_manager.get_connection_summary.assert_not_awaited()
    session.record_peer_connection_batch_metrics.assert_not_called()
