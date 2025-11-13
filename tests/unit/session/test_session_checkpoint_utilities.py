"""Tests for session checkpoint utility methods."""

import pytest
import time
from pathlib import Path

from ccbt.models import TorrentCheckpoint, CheckpointFormat
from ccbt.storage.checkpoint import CheckpointFileInfo


@pytest.mark.asyncio
async def test_list_resumable_checkpoints_filters_by_source(monkeypatch, tmp_path):
    """Test list_resumable_checkpoints returns only checkpoints with source."""
    from ccbt.session.session import AsyncSessionManager

    class _CPM:
        async def list_checkpoints(self):
            return [
                CheckpointFileInfo(
                    path=Path("/checkpoint1"),
                    info_hash=b"1" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
                CheckpointFileInfo(
                    path=Path("/checkpoint2"),
                    info_hash=b"2" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
                CheckpointFileInfo(
                    path=Path("/checkpoint3"),
                    info_hash=b"3" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
            ]

        async def load_checkpoint(self, ih):
            if ih == b"1" * 20:
                return TorrentCheckpoint(
                    info_hash=b"1" * 20,
                    torrent_name="has_file",
                    total_pieces=1,
                    piece_length=16384,
                    total_length=16384,
                    verified_pieces=[],
                    piece_states={},
                    created_at=time.time(),
                    updated_at=time.time(),
                    output_dir=str(tmp_path),
                    torrent_file_path=str(tmp_path / "test.torrent"),
                )
            elif ih == b"2" * 20:
                return TorrentCheckpoint(
                    info_hash=b"2" * 20,
                    torrent_name="has_magnet",
                    total_pieces=1,
                    piece_length=16384,
                    total_length=16384,
                    verified_pieces=[],
                    piece_states={},
                    created_at=time.time(),
                    updated_at=time.time(),
                    output_dir=str(tmp_path),
                    magnet_uri="magnet:?xt=urn:btih:" + ("2" * 40),
                )
            elif ih == b"3" * 20:
                return TorrentCheckpoint(
                    info_hash=b"3" * 20,
                    torrent_name="no_source",
                    total_pieces=1,
                    piece_length=16384,
                    total_length=16384,
                    verified_pieces=[],
                    piece_states={},
                    created_at=time.time(),
                    updated_at=time.time(),
                    output_dir=str(tmp_path),
                )

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    mgr = AsyncSessionManager(str(tmp_path))
    resumable = await mgr.list_resumable_checkpoints()

    assert len(resumable) == 2
    assert any(cp.info_hash == b"1" * 20 for cp in resumable)
    assert any(cp.info_hash == b"2" * 20 for cp in resumable)
    assert not any(cp.info_hash == b"3" * 20 for cp in resumable)


@pytest.mark.asyncio
async def test_list_resumable_checkpoints_handles_load_errors(monkeypatch, tmp_path):
    """Test list_resumable_checkpoints continues on checkpoint load errors."""
    from ccbt.session.session import AsyncSessionManager

    class _CPM:
        async def list_checkpoints(self):
            return [
                CheckpointFileInfo(
                    path=Path("/good"),
                    info_hash=b"1" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
                CheckpointFileInfo(
                    path=Path("/bad"),
                    info_hash=b"2" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
            ]

        async def load_checkpoint(self, ih):
            if ih == b"1" * 20:
                return TorrentCheckpoint(
                    info_hash=b"1" * 20,
                    torrent_name="good",
                    total_pieces=1,
                    piece_length=16384,
                    total_length=16384,
                    verified_pieces=[],
                    piece_states={},
                    created_at=time.time(),
                    updated_at=time.time(),
                    output_dir=str(tmp_path),
                    torrent_file_path=str(tmp_path / "good.torrent"),
                )
            raise RuntimeError("load failed")

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    mgr = AsyncSessionManager(str(tmp_path))
    resumable = await mgr.list_resumable_checkpoints()

    assert len(resumable) == 1
    assert resumable[0].info_hash == b"1" * 20


@pytest.mark.asyncio
async def test_find_checkpoint_by_name_returns_match(monkeypatch, tmp_path):
    """Test find_checkpoint_by_name returns matching checkpoint."""
    from ccbt.session.session import AsyncSessionManager

    class _CPM:
        async def list_checkpoints(self):
            return [
                CheckpointFileInfo(
                    path=Path("/test"),
                    info_hash=b"1" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
                CheckpointFileInfo(
                    path=Path("/other"),
                    info_hash=b"2" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
            ]

        async def load_checkpoint(self, ih):
            if ih == b"1" * 20:
                return TorrentCheckpoint(
                    info_hash=b"1" * 20,
                    torrent_name="test-torrent",
                    total_pieces=1,
                    piece_length=16384,
                    total_length=16384,
                    verified_pieces=[],
                    piece_states={},
                    created_at=time.time(),
                    updated_at=time.time(),
                    output_dir=str(tmp_path),
                )
            elif ih == b"2" * 20:
                return TorrentCheckpoint(
                    info_hash=b"2" * 20,
                    torrent_name="other-torrent",
                    total_pieces=1,
                    piece_length=16384,
                    total_length=16384,
                    verified_pieces=[],
                    piece_states={},
                    created_at=time.time(),
                    updated_at=time.time(),
                    output_dir=str(tmp_path),
                )

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    mgr = AsyncSessionManager(str(tmp_path))
    cp = await mgr.find_checkpoint_by_name("test-torrent")

    assert cp is not None
    assert cp.torrent_name == "test-torrent"


@pytest.mark.asyncio
async def test_find_checkpoint_by_name_returns_none_when_not_found(monkeypatch, tmp_path):
    """Test find_checkpoint_by_name returns None when no match."""
    from ccbt.session.session import AsyncSessionManager

    class _CPM:
        async def list_checkpoints(self):
            return []

        async def load_checkpoint(self, ih):
            return None

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    mgr = AsyncSessionManager(str(tmp_path))
    cp = await mgr.find_checkpoint_by_name("nonexistent")

    assert cp is None


@pytest.mark.asyncio
async def test_get_checkpoint_info_returns_summary(monkeypatch, tmp_path):
    """Test get_checkpoint_info returns complete summary dictionary."""
    from ccbt.session.session import AsyncSessionManager

    class _CPM:
        async def load_checkpoint(self, ih):
            return TorrentCheckpoint(
                info_hash=b"1" * 20,
                torrent_name="test",
                total_pieces=10,
                piece_length=16384,
                total_length=163840,
                verified_pieces=[0, 1, 2],
                piece_states={},
                created_at=1000.0,
                updated_at=2000.0,
                output_dir=str(tmp_path),
                torrent_file_path=str(tmp_path / "test.torrent"),
            )

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    mgr = AsyncSessionManager(str(tmp_path))
    info = await mgr.get_checkpoint_info(b"1" * 20)

    assert info is not None
    assert info["info_hash"] == (b"1" * 20).hex()
    assert info["name"] == "test"
    assert info["progress"] == 0.3  # 3/10
    assert info["verified_pieces"] == 3
    assert info["total_pieces"] == 10
    assert info["total_size"] == 163840
    assert info["can_resume"] is True
    assert info["torrent_file_path"] == str(tmp_path / "test.torrent")


@pytest.mark.asyncio
async def test_get_checkpoint_info_returns_none_when_missing(monkeypatch):
    """Test get_checkpoint_info returns None for missing checkpoint."""
    from ccbt.session.session import AsyncSessionManager

    class _CPM:
        async def load_checkpoint(self, ih):
            return None

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    mgr = AsyncSessionManager(".")
    info = await mgr.get_checkpoint_info(b"1" * 20)

    assert info is None


@pytest.mark.asyncio
async def test_get_checkpoint_info_handles_zero_pieces(monkeypatch, tmp_path):
    """Test get_checkpoint_info handles zero total_pieces correctly."""
    from ccbt.session.session import AsyncSessionManager

    class _CPM:
        async def load_checkpoint(self, ih):
            return TorrentCheckpoint(
                info_hash=b"1" * 20,
                torrent_name="test",
                total_pieces=0,
                piece_length=16384,  # Must be > 0
                total_length=0,
                verified_pieces=[],
                piece_states={},
                created_at=time.time(),
                updated_at=time.time(),
                output_dir=str(tmp_path),
            )

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    mgr = AsyncSessionManager(str(tmp_path))
    info = await mgr.get_checkpoint_info(b"1" * 20)

    assert info is not None
    assert info["progress"] == 0


@pytest.mark.asyncio
async def test_cleanup_completed_checkpoints_removes_completed(monkeypatch, tmp_path):
    """Test cleanup_completed_checkpoints removes completed download checkpoints."""
    from ccbt.session.session import AsyncSessionManager

    deleted_hashes = []

    class _CPM:
        async def list_checkpoints(self):
            return [
                CheckpointFileInfo(
                    path=Path("/complete"),
                    info_hash=b"1" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
                CheckpointFileInfo(
                    path=Path("/incomplete"),
                    info_hash=b"2" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
            ]

        async def load_checkpoint(self, ih):
            if ih == b"1" * 20:
                # Complete: all pieces verified
                return TorrentCheckpoint(
                    info_hash=b"1" * 20,
                    torrent_name="complete",
                    total_pieces=10,
                    piece_length=16384,
                    total_length=163840,
                    verified_pieces=list(range(10)),  # All 10 pieces verified
                    piece_states={},
                    created_at=time.time(),
                    updated_at=time.time(),
                    output_dir=str(tmp_path),
                )
            elif ih == b"2" * 20:
                # Incomplete: only 5 pieces verified
                return TorrentCheckpoint(
                    info_hash=b"2" * 20,
                    torrent_name="incomplete",
                    total_pieces=10,
                    piece_length=16384,
                    total_length=163840,
                    verified_pieces=list(range(5)),  # Only 5 pieces verified
                    piece_states={},
                    created_at=time.time(),
                    updated_at=time.time(),
                    output_dir=str(tmp_path),
                )

        async def delete_checkpoint(self, ih):
            deleted_hashes.append(ih)

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    mgr = AsyncSessionManager(str(tmp_path))
    cleaned = await mgr.cleanup_completed_checkpoints()

    assert cleaned == 1
    assert len(deleted_hashes) == 1
    assert deleted_hashes[0] == b"1" * 20


@pytest.mark.asyncio
async def test_cleanup_completed_checkpoints_handles_errors(monkeypatch, tmp_path):
    """Test cleanup_completed_checkpoints continues on processing errors."""
    from ccbt.session.session import AsyncSessionManager

    class _CPM:
        async def list_checkpoints(self):
            return [
                CheckpointFileInfo(
                    path=Path("/error"),
                    info_hash=b"1" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
                CheckpointFileInfo(
                    path=Path("/complete"),
                    info_hash=b"2" * 20,
                    created_at=time.time(),
                    updated_at=time.time(),
                    size=1000,
                    checkpoint_format=CheckpointFormat.JSON,
                ),
            ]

        async def load_checkpoint(self, ih):
            if ih == b"1" * 20:
                raise RuntimeError("load failed")
            elif ih == b"2" * 20:
                return TorrentCheckpoint(
                    info_hash=b"2" * 20,
                    torrent_name="complete",
                    total_pieces=10,
                    piece_length=16384,
                    total_length=163840,
                    verified_pieces=list(range(10)),
                    piece_states={},
                    created_at=time.time(),
                    updated_at=time.time(),
                    output_dir=str(tmp_path),
                )

        async def delete_checkpoint(self, ih):
            pass

    import ccbt.storage.checkpoint
    import ccbt.session.session as sess_mod
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())
    monkeypatch.setattr(sess_mod, "CheckpointManager", lambda *a, **k: _CPM())

    mgr = AsyncSessionManager(str(tmp_path))
    cleaned = await mgr.cleanup_completed_checkpoints()

    assert cleaned == 1  # Only the second one was cleaned

