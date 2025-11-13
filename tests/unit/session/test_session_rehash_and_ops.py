"""Tests for session rehash and other operations."""

import pytest


@pytest.mark.asyncio
async def test_rehash_torrent_invalid_hex_returns_false():
    """Test rehash_torrent returns False for invalid hex."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    result = await mgr.rehash_torrent("invalid")
    assert result is False


@pytest.mark.asyncio
async def test_rehash_torrent_missing_session_returns_false():
    """Test rehash_torrent returns False when session not found."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    result = await mgr.rehash_torrent("aa" * 20)
    assert result is False


@pytest.mark.asyncio
async def test_rehash_torrent_no_piece_manager_returns_false(monkeypatch):
    """Test rehash_torrent returns False when piece_manager missing."""
    from ccbt.session.session import AsyncSessionManager

    class _Session:
        def __init__(self):
            self.piece_manager = None

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.rehash_torrent(ih_bytes.hex())
    assert result is False


@pytest.mark.asyncio
async def test_rehash_torrent_no_verify_method_returns_false(monkeypatch):
    """Test rehash_torrent returns False when verify_all_pieces missing."""
    from ccbt.session.session import AsyncSessionManager

    class _PM:
        pass  # No verify_all_pieces method

    class _Session:
        def __init__(self):
            self.piece_manager = _PM()

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.rehash_torrent(ih_bytes.hex())
    assert result is False


@pytest.mark.asyncio
async def test_rehash_torrent_with_coroutine_verify(monkeypatch):
    """Test rehash_torrent calls async verify_all_pieces."""
    from ccbt.session.session import AsyncSessionManager

    verify_called = []

    class _PM:
        async def verify_all_pieces(self):
            verify_called.append(1)
            return True

    class _Session:
        def __init__(self):
            self.piece_manager = _PM()

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.rehash_torrent(ih_bytes.hex())
    assert result is True
    assert len(verify_called) == 1


@pytest.mark.asyncio
async def test_rehash_torrent_with_sync_verify(monkeypatch):
    """Test rehash_torrent calls sync verify_all_pieces."""
    from ccbt.session.session import AsyncSessionManager

    verify_called = []

    class _PM:
        def verify_all_pieces(self):
            verify_called.append(1)
            return True

    class _Session:
        def __init__(self):
            self.piece_manager = _PM()

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.rehash_torrent(ih_bytes.hex())
    assert result is True
    assert len(verify_called) == 1


@pytest.mark.asyncio
async def test_get_status_returns_all_torrents(monkeypatch):
    """Test get_status returns status for all torrents."""
    from ccbt.session.session import AsyncSessionManager

    class _Session:
        async def get_status(self):
            return {"name": "test", "progress": 0.5}

    mgr = AsyncSessionManager(".")
    ih1 = b"1" * 20
    ih2 = b"2" * 20

    async with mgr.lock:
        mgr.torrents[ih1] = _Session()
        mgr.torrents[ih2] = _Session()

    status = await mgr.get_status()

    assert isinstance(status, dict)
    assert len(status) == 2
    assert (ih1.hex() in status or ih2.hex() in status)


@pytest.mark.asyncio
async def test_get_status_with_empty_torrents():
    """Test get_status returns empty list when no torrents."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    status = await mgr.get_status()

    assert isinstance(status, dict)
    assert len(status) == 0

