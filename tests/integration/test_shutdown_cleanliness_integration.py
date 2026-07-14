"""Integration-style shutdown cleanliness tests."""

from __future__ import annotations

import pytest

from ccbt.session.session import AsyncSessionManager


class _MockSession:
    def __init__(self) -> None:
        self.quiesced = False
        self.stop_called = False

    async def begin_shutdown_quiesce(self) -> None:
        self.quiesced = True

    def begin_shutdown_quiesce_sync(self) -> None:
        self.quiesced = True

    async def stop(self) -> None:
        self.stop_called = True
        raise TimeoutError("simulated stop timeout")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_manager_stop_prequiesces_before_per_session_stop() -> None:
    """Manager stop should pre-quiesce sessions before heavy stop awaits."""
    manager = AsyncSessionManager()
    session = _MockSession()
    manager.torrents = {b"\x01" * 20: session}

    await manager.stop()

    assert session.quiesced is True
    assert session.stop_called is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_begin_shutdown_quiesce_async_awaits_sessions() -> None:
    """Async quiesce should await per-session begin_shutdown_quiesce coroutines."""
    manager = AsyncSessionManager()
    session = _MockSession()
    manager.torrents = {b"\x02" * 20: session}

    await manager.begin_shutdown_quiesce_async()

    assert session.quiesced is True
    assert session.stop_called is False
