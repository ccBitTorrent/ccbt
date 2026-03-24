"""Unit tests for DHT aggressive-mode transition handling."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from ccbt.session.dht_setup import DHTDiscoverySetup


def _build_setup() -> DHTDiscoverySetup:
    session = SimpleNamespace(
        info=SimpleNamespace(name="t1", info_hash=b"\x01" * 20, private=False),
        logger=logging.getLogger("test_dht_aggressive_transition"),
        config=SimpleNamespace(discovery=SimpleNamespace()),
        is_private=False,
    )
    return DHTDiscoverySetup(session)


@pytest.mark.asyncio
async def test_aggressive_mode_transition_no_edge_no_event() -> None:
    setup = _build_setup()
    with patch("ccbt.utils.events.emit_event", new_callable=AsyncMock) as emit_mock:
        result = await setup._handle_aggressive_mode_transition(
            current_aggressive_mode=False,
            new_aggressive_mode=False,
            requestable_stall=False,
            is_popular=False,
            is_active=False,
            current_peer_count=5,
            current_download_rate=0.0,
            dht_retry_interval=60.0,
            max_peers_per_query=50,
        )
    assert result is False
    emit_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_aggressive_mode_transition_enable_and_disable_emit_once_each() -> None:
    setup = _build_setup()
    with patch("ccbt.utils.events.emit_event", new_callable=AsyncMock) as emit_mock:
        enabled = await setup._handle_aggressive_mode_transition(
            current_aggressive_mode=False,
            new_aggressive_mode=True,
            requestable_stall=True,
            is_popular=False,
            is_active=False,
            current_peer_count=2,
            current_download_rate=0.0,
            dht_retry_interval=60.0,
            max_peers_per_query=50,
        )
        disabled = await setup._handle_aggressive_mode_transition(
            current_aggressive_mode=enabled,
            new_aggressive_mode=False,
            requestable_stall=False,
            is_popular=True,
            is_active=False,
            current_peer_count=50,
            current_download_rate=0.0,
            dht_retry_interval=60.0,
            max_peers_per_query=50,
        )
    assert enabled is True
    assert disabled is False
    assert emit_mock.await_count == 2


@pytest.mark.asyncio
async def test_aggressive_mode_transition_uses_persisted_state_to_avoid_duplicate_enable() -> None:
    setup = _build_setup()
    setup._aggressive_mode = True
    with patch("ccbt.utils.events.emit_event", new_callable=AsyncMock) as emit_mock:
        result = await setup._handle_aggressive_mode_transition(
            current_aggressive_mode=False,  # stale loop-local value after restart
            new_aggressive_mode=True,
            requestable_stall=False,
            is_popular=True,
            is_active=False,
            current_peer_count=60,
            current_download_rate=0.0,
            dht_retry_interval=60.0,
            max_peers_per_query=50,
        )
    assert result is True
    emit_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_aggressive_mode_transition_emits_disable_when_persisted_state_true() -> None:
    setup = _build_setup()
    setup._aggressive_mode = True
    with patch("ccbt.utils.events.emit_event", new_callable=AsyncMock) as emit_mock:
        result = await setup._handle_aggressive_mode_transition(
            current_aggressive_mode=False,  # stale loop-local value after restart
            new_aggressive_mode=False,
            requestable_stall=False,
            is_popular=False,
            is_active=False,
            current_peer_count=10,
            current_download_rate=0.0,
            dht_retry_interval=60.0,
            max_peers_per_query=50,
        )
    assert result is False
    assert emit_mock.await_count == 1
