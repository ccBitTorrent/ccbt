"""Focused readiness and zero-node rebootstrap behavior tests."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.discovery.dht import AsyncDHTClient
from ccbt.session.dht_setup import DHTDiscoverySetup


def _make_stub_client() -> AsyncDHTClient:
    client = AsyncDHTClient.__new__(AsyncDHTClient)
    client.logger = SimpleNamespace(
        debug=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
    )
    client.routing_table = SimpleNamespace(nodes={})
    client.last_bootstrap_state = "idle"
    client.last_bootstrap_failure_reason = ""
    client._empty_table_rebootstrap_attempts = 0
    client._max_empty_table_rebootstrap_attempts = 3
    client._last_empty_table_rebootstrap_at = 0.0
    client._empty_table_rebootstrap_backoff = 1.0
    client._empty_table_backoff_factor = 1.5
    client._zero_node_rebootstrap_task = None
    return client


@pytest.mark.asyncio
async def test_wait_for_bootstrap_respects_min_nodes_and_partial_flag() -> None:
    client = _make_stub_client()
    client.routing_table.nodes = {("198.51.100.1", 6881): object()}

    strict_result = await client.wait_for_bootstrap(
        timeout=0.02,
        min_nodes=8,
        allow_partial=False,
    )
    partial_result = await client.wait_for_bootstrap(
        timeout=0.02,
        min_nodes=8,
        allow_partial=True,
    )

    assert strict_result is False
    assert partial_result is True


@pytest.mark.asyncio
async def test_zero_node_rebootstrap_suppresses_duplicate_inflight() -> None:
    client = _make_stub_client()

    async def _rebootstrap() -> None:
        await asyncio.sleep(0.05)

    client.rebootstrap = _rebootstrap

    first = client._schedule_zero_node_rebootstrap(reason="unit:first")
    second = client._schedule_zero_node_rebootstrap(reason="unit:duplicate")

    assert first is True
    assert second is False
    assert client.last_bootstrap_state == "suppressed:rebootstrap_inflight"
    assert "inflight" in client.last_bootstrap_failure_reason

    await asyncio.sleep(0.08)
    assert client._zero_node_rebootstrap_task is None


@pytest.mark.asyncio
async def test_bootstrap_lock_serializes_concurrent_bootstrap_calls() -> None:
    client = _make_stub_client()
    client._bootstrap_lock = asyncio.Lock()
    active = 0
    max_active = 0
    call_reasons: list[str] = []

    async def _bootstrap_core(reason: str = "bootstrap") -> None:
        nonlocal active, max_active
        call_reasons.append(reason)
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1

    client._bootstrap_core = _bootstrap_core  # type: ignore[method-assign]

    await asyncio.gather(
        client._bootstrap(reason="unit:first"),
        client._bootstrap(reason="unit:second"),
    )

    assert max_active == 1
    assert sorted(call_reasons) == ["unit:first", "unit:second"]


@pytest.mark.asyncio
async def test_refresh_loop_empty_routing_uses_bounded_scheduler() -> None:
    client = AsyncDHTClient()
    client.routing_table.nodes.clear()

    with patch.object(
        client,
        "_calculate_adaptive_interval",
        return_value=0.01,
    ), patch.object(
        client,
        "_schedule_zero_node_rebootstrap",
        return_value=True,
    ) as schedule_mock, patch.object(
        client,
        "rebootstrap",
        new_callable=AsyncMock,
    ) as rebootstrap_mock:
        task = asyncio.create_task(client._refresh_loop())
        await asyncio.sleep(0.03)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    assert schedule_mock.called
    rebootstrap_mock.assert_not_awaited()


def test_bootstrap_outer_wait_budget_uses_client_wall_clock() -> None:
    disc = SimpleNamespace(dht_bootstrap_timeout_s=40.0)
    session = SimpleNamespace(
        info=SimpleNamespace(name="t1"),
        logger=logging.getLogger("test_dht_bootstrap"),
        config=SimpleNamespace(discovery=disc),
    )
    setup = DHTDiscoverySetup(session)
    client = SimpleNamespace(_dht_bootstrap_timeout_s=30.0)
    assert setup._bootstrap_outer_wait_budget_s(client, 5.0) == 32.0
    assert setup._bootstrap_outer_wait_budget_s(client, 50.0) == 50.0


@pytest.mark.asyncio
async def test_send_query_clamps_timeout_to_bootstrap_wall_remaining() -> None:
    client = AsyncDHTClient.__new__(AsyncDHTClient)
    client.logger = logging.getLogger("test_dht_send_query")
    client.config = MagicMock()
    client.config.network.dht_timeout = 120.0
    client.peer_manager = None
    client._timeout_calculator = None
    client.pending_queries = {}
    client.transport = MagicMock()
    client.routing_table = MagicMock()
    client.routing_table.nodes = {}
    client._bootstrap_query_deadline = time.time() + 0.4
    captured: dict[str, float] = {}

    real_wait_for = asyncio.wait_for

    async def _capturing_wait_for(
        coro: object, timeout: float | None = None
    ) -> dict[bytes, bytes]:
        captured["timeout"] = float(timeout or 0.0)
        return await real_wait_for(coro, timeout=timeout)  # type: ignore[arg-type]

    with patch.object(
        AsyncDHTClient,
        "_calculate_adaptive_query_timeout",
        return_value=60.0,
    ), patch.object(
        AsyncDHTClient,
        "_wait_for_response",
        new_callable=AsyncMock,
        return_value={b"y": b"r", b"r": {b"id": b"x" * 20}},
    ), patch(
        "ccbt.discovery.dht.is_shutting_down",
        return_value=False,
    ), patch(
        "ccbt.discovery.dht.asyncio.wait_for",
        side_effect=_capturing_wait_for,
    ):
        await AsyncDHTClient._send_query(
            client,
            ("203.0.113.1", 6881),
            "ping",
            {b"id": b"test"},
        )

    assert captured["timeout"] <= 0.5
