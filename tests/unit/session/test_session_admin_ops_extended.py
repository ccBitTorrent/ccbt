"""Extended tests for session admin operations."""

import pytest

from ccbt.models import PieceState


@pytest.mark.asyncio
async def test_refresh_pex_invalid_hex_returns_false():
    """Test refresh_pex returns False for invalid hex."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    result = await mgr.refresh_pex("invalid")
    assert result is False


@pytest.mark.asyncio
async def test_refresh_pex_missing_session_returns_false():
    """Test refresh_pex returns False when session not found."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    result = await mgr.refresh_pex("aa" * 20)
    assert result is False


@pytest.mark.asyncio
async def test_refresh_pex_no_pex_manager_returns_false(monkeypatch):
    """Test refresh_pex returns False when session has no pex_manager."""
    from ccbt.session.session import AsyncSessionManager

    class _Session:
        def __init__(self):
            self.pex_manager = None

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.refresh_pex(ih_bytes.hex())
    assert result is False


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
async def test_refresh_pex_exception_returns_false(monkeypatch):
    """Test refresh_pex returns False when refresh raises exception."""
    from ccbt.session.session import AsyncSessionManager

    class _PEX:
        async def refresh(self):
            raise RuntimeError("refresh failed")

    class _Session:
        def __init__(self):
            self.pex_manager = _PEX()

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.refresh_pex(ih_bytes.hex())
    assert result is False


@pytest.mark.asyncio
async def test_force_announce_invalid_hex_returns_false():
    """Test force_announce returns False for invalid hex."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    result = await mgr.force_announce("invalid")
    assert result is False


@pytest.mark.asyncio
async def test_force_announce_missing_session_returns_false():
    """Test force_announce returns False when session not found."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")
    result = await mgr.force_announce("aa" * 20)
    assert result is False


@pytest.mark.asyncio
async def test_force_announce_with_dict_torrent_data(monkeypatch):
    """Test force_announce uses dict torrent_data when available."""
    from ccbt.session.session import AsyncSessionManager

    announce_called = []
    announce_data = []

    class _Tracker:
        async def announce(self, td):
            announce_called.append(1)
            announce_data.append(td)

    class _Info:
        def __init__(self):
            self.info_hash = b"1" * 20
            self.name = "test"

    class _Session:
        def __init__(self):
            self.torrent_data = {
                "info_hash": b"1" * 20,
                "announce": "http://tracker.example.com/announce",
                "name": "test",
            }
            self.info = _Info()
            self.tracker = _Tracker()

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.force_announce(ih_bytes.hex())
    assert result is True
    assert len(announce_called) == 1
    assert announce_data[0]["info_hash"] == b"1" * 20


@pytest.mark.asyncio
async def test_force_announce_with_model_torrent_data(monkeypatch):
    """Test force_announce builds dict from model torrent_data."""
    from ccbt.session.session import AsyncSessionManager

    announce_called = []
    announce_data = []

    class _Tracker:
        async def announce(self, td):
            announce_called.append(1)
            announce_data.append(td)

    class _Info:
        def __init__(self):
            self.info_hash = b"2" * 20
            self.name = "model-test"

    class _Model:
        def __init__(self):
            self.info_hash = b"2" * 20
            self.name = "model-test"

    class _Session:
        def __init__(self):
            self.torrent_data = _Model()  # Model, not dict
            self.info = _Info()
            self.tracker = _Tracker()

    mgr = AsyncSessionManager(".")
    ih_bytes = b"2" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.force_announce(ih_bytes.hex())
    assert result is True
    assert len(announce_called) == 1
    assert announce_data[0]["info_hash"] == b"2" * 20
    assert announce_data[0]["name"] == "model-test"


@pytest.mark.asyncio
async def test_force_announce_exception_returns_false(monkeypatch):
    """Test force_announce returns False when announce raises exception."""
    from ccbt.session.session import AsyncSessionManager

    class _Tracker:
        async def announce(self, td):
            raise RuntimeError("announce failed")

    class _Info:
        def __init__(self):
            self.info_hash = b"1" * 20
            self.name = "test"

    class _Session:
        def __init__(self):
            self.torrent_data = {"info_hash": b"1" * 20, "announce": "", "name": "test"}
            self.info = _Info()
            self.tracker = _Tracker()

    mgr = AsyncSessionManager(".")
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    result = await mgr.force_announce(ih_bytes.hex())
    assert result is False


@pytest.mark.asyncio
async def test_checkpoint_backup_torrent_success(monkeypatch, tmp_path):
    """Test checkpoint_backup_torrent successfully backs up checkpoint."""
    from ccbt.session.session import AsyncSessionManager
    from pathlib import Path

    backup_called = []

    class _CPM:
        async def backup_checkpoint(self, ih, dest, *, compress=True, encrypt=False):
            backup_called.append((ih, dest))
            return dest

    class _Info:
        def __init__(self):
            self.info_hash = b"1" * 20
            self.name = "test"

    class _Session:
        def __init__(self):
            self.info = _Info()
            self.checkpoint_manager = _CPM()

    mgr = AsyncSessionManager(str(tmp_path))
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    dest = tmp_path / "backup.json"
    result = await mgr.checkpoint_backup_torrent(ih_bytes.hex(), dest)

    assert result is True
    assert len(backup_called) == 1
    assert backup_called[0][0] == ih_bytes


@pytest.mark.asyncio
async def test_checkpoint_backup_torrent_invalid_hex_returns_false():
    """Test checkpoint_backup_torrent returns False for invalid hex."""
    from ccbt.session.session import AsyncSessionManager
    from pathlib import Path

    mgr = AsyncSessionManager(".")
    dest = Path("backup.json")
    result = await mgr.checkpoint_backup_torrent("invalid", dest)
    assert result is False


@pytest.mark.asyncio
async def test_checkpoint_backup_torrent_missing_session_returns_false(tmp_path):
    """Test checkpoint_backup_torrent returns False when session not found."""
    from ccbt.session.session import AsyncSessionManager
    from pathlib import Path

    mgr = AsyncSessionManager(str(tmp_path))
    dest = tmp_path / "backup.json"
    result = await mgr.checkpoint_backup_torrent("aa" * 20, dest)
    assert result is False


@pytest.mark.asyncio
async def test_checkpoint_backup_torrent_exception_returns_false(monkeypatch, tmp_path):
    """Test checkpoint_backup_torrent returns False when backup raises exception."""
    from ccbt.session.session import AsyncSessionManager
    from pathlib import Path

    class _CPM:
        async def backup_checkpoint(self, ih, dest):
            raise RuntimeError("backup failed")

    class _Info:
        def __init__(self):
            self.info_hash = b"1" * 20
            self.name = "test"

    class _Session:
        def __init__(self):
            self.info = _Info()
            self.checkpoint_manager = _CPM()

    mgr = AsyncSessionManager(str(tmp_path))
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    dest = tmp_path / "backup.json"
    result = await mgr.checkpoint_backup_torrent(ih_bytes.hex(), dest)
    assert result is False

