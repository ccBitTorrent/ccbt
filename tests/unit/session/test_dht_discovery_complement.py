"""PEX/LSD complement behavior when DHT queries are throttled or deferred."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.session.dht_setup import DHTDiscoverySetup
from ccbt.session.peers import run_discovery_complements


@pytest.mark.asyncio
async def test_run_discovery_complements_invokes_pex_refresh() -> None:
    """PEX refresh runs when complements are invoked on a public torrent."""
    pex = SimpleNamespace()
    pex.refresh = AsyncMock()
    session = SimpleNamespace(
        stopped=False,
        is_private=False,
        pex_manager=pex,
        logger=logging.getLogger("test_complement"),
    )
    session._is_discovery_component_disabled = lambda _c: False  # noqa: SLF001
    await run_discovery_complements(session, reason="test")
    pex.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_discovery_complements_skips_pex_when_policy_disables() -> None:
    """Strict discovery mode that disables PEX skips PEX complement."""
    pex = SimpleNamespace()
    pex.refresh = AsyncMock()
    session = SimpleNamespace(
        stopped=False,
        is_private=False,
        pex_manager=pex,
        logger=logging.getLogger("test_complement"),
    )
    session._is_discovery_component_disabled = lambda c: c == "pex"  # noqa: SLF001
    await run_discovery_complements(session, reason="test")
    pex.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_run_discovery_complements_skips_when_private() -> None:
    """Private torrents skip PEX/LSD complements."""
    pex = SimpleNamespace()
    pex.refresh = AsyncMock()
    session = SimpleNamespace(
        stopped=False,
        is_private=True,
        pex_manager=pex,
        logger=logging.getLogger("test_complement"),
    )
    await run_discovery_complements(session, reason="test")
    pex.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_run_discovery_complements_invokes_lpd_discover() -> None:
    """Running LPD discover_peers when a local client is attached."""
    lpd = MagicMock()
    lpd.running = True
    lpd.discover_peers = AsyncMock(return_value=[])
    session = SimpleNamespace(
        stopped=False,
        is_private=False,
        pex_manager=None,
        local_peer_discovery=lpd,
        logger=logging.getLogger("test_complement"),
    )
    session._is_discovery_component_disabled = lambda _c: False  # noqa: SLF001
    await run_discovery_complements(session, reason="test")
    lpd.discover_peers.assert_awaited_once_with(timeout=2.0)


@pytest.mark.asyncio
async def test_maybe_run_discovery_complements_throttled() -> None:
    """Debounce prevents complement storms from tight DHT loops."""
    session = SimpleNamespace(
        info=SimpleNamespace(name="t1", info_hash=b"\x01" * 20),
        logger=logging.getLogger("test_dht_complement_throttle"),
        config=SimpleNamespace(discovery=SimpleNamespace()),
        is_private=False,
    )
    setup = DHTDiscoverySetup(session)
    with patch(
        "ccbt.session.peers.run_discovery_complements",
        new_callable=AsyncMock,
    ) as comp:
        await setup._maybe_run_discovery_complements("a")  # noqa: SLF001
        await setup._maybe_run_discovery_complements("b")  # noqa: SLF001
    assert comp.await_count == 1
