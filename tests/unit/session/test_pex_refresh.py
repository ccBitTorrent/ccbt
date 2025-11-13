"""Tests for PEX refresh functionality in session manager."""

from __future__ import annotations

import pytest

from ccbt.session.session import AsyncSessionManager


@pytest.mark.asyncio
async def test_refresh_pex_success(monkeypatch):
    """Test refresh_pex returns True when refresh succeeds."""
    from ccbt.session.session import AsyncSessionManager

    refresh_called = []

    class _PEX:
        async def refresh(self):
            refresh_called.append(1)

    class _Session:
        def __init__(self):
            self.pex_manager = _PEX()

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.refresh_pex(ih_bytes.hex())
    assert result is True
    assert len(refresh_called) == 1


@pytest.mark.asyncio
async def test_refresh_pex_no_pex_manager_returns_false(monkeypatch):
    """Test refresh_pex returns False when PEX manager doesn't exist."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    class _Session:
        def __init__(self):
            self.pex_manager = None

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.refresh_pex(ih_bytes.hex())
    assert result is False


@pytest.mark.asyncio
async def test_refresh_pex_invalid_info_hash(monkeypatch):
    """Test refresh_pex returns False with invalid info hash."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")

    result = await mgr.refresh_pex("invalid")
    assert result is False


@pytest.mark.asyncio
async def test_refresh_pex_torrent_not_found(monkeypatch):
    """Test refresh_pex returns False when torrent doesn't exist."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    result = await mgr.refresh_pex(ih_bytes.hex())
    assert result is False


@pytest.mark.asyncio
async def test_refresh_pex_exception_returns_false(monkeypatch):
    """Test refresh_pex returns False when refresh raises exception."""
    from ccbt.session.session import AsyncSessionManager

    class _PEX:
        async def refresh(self):
            raise Exception("Test error")

    class _Session:
        def __init__(self):
            self.pex_manager = _PEX()

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.refresh_pex(ih_bytes.hex())
    assert result is False

