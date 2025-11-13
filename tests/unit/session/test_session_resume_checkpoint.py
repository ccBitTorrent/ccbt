"""Tests for resume_from_checkpoint functionality."""

import pytest
from pathlib import Path

from ccbt.models import TorrentCheckpoint


@pytest.mark.asyncio
async def test_resume_from_checkpoint_with_explicit_file_path(monkeypatch, tmp_path):
    """Test resume_from_checkpoint uses explicit torrent_path when provided."""
    from ccbt.session import session as sess_mod
    from ccbt.session.session import AsyncSessionManager

    checkpoint_loaded = []
    add_torrent_called = []

    class _CPM:
        async def load_checkpoint(self, ih):
            checkpoint_loaded.append(ih)
            cp = TorrentCheckpoint(
                info_hash=b"1" * 20,
                torrent_name="test",
                total_pieces=1,
                piece_length=16384,
                total_length=16384,
                verified_pieces=[],
                piece_states={},
                created_at=0.0,
                updated_at=0.0,
                output_dir=str(tmp_path),
            )
            return cp

    class _Model:
        def __init__(self):
            self.name = "test"
            self.info_hash = b"1" * 20
            self.pieces = []
            self.piece_length = 16384
            self.num_pieces = 1
            self.total_length = 16384

    class _Parser:
        def parse(self, path):
            return _Model()

    monkeypatch.setattr(sess_mod, "TorrentParser", lambda: _Parser())

    # Mock checkpoint manager
    import ccbt.storage.checkpoint
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())

    # Mock validate_checkpoint
    async def _validate(cp):
        return True

    mgr = AsyncSessionManager(str(tmp_path))

    # Create a dummy torrent file
    torrent_file = tmp_path / "test.torrent"
    torrent_file.write_bytes(b"dummy")

    # Mock add_torrent to track calls
    async def _mock_add(path, resume=False):
        add_torrent_called.append((path, resume))
        return (b"1" * 20).hex()

    monkeypatch.setattr(mgr, "add_torrent", _mock_add)
    monkeypatch.setattr(mgr, "validate_checkpoint", _validate)

    ih = await mgr.resume_from_checkpoint(b"1" * 20, await _CPM().load_checkpoint(b"1" * 20), str(torrent_file))

    assert len(add_torrent_called) == 1
    assert add_torrent_called[0][0] == str(torrent_file)
    assert add_torrent_called[0][1] is True


@pytest.mark.asyncio
async def test_resume_from_checkpoint_with_stored_file_path(monkeypatch, tmp_path):
    """Test resume_from_checkpoint uses stored torrent_file_path from checkpoint."""
    from ccbt.session import session as sess_mod
    from ccbt.session.session import AsyncSessionManager

    add_torrent_called = []

    torrent_file = tmp_path / "stored.torrent"
    torrent_file.write_bytes(b"dummy")

    class _CPM:
        async def load_checkpoint(self, ih):
            cp = TorrentCheckpoint(
                info_hash=b"1" * 20,
                torrent_name="test",
                total_pieces=1,
                piece_length=16384,
                total_length=16384,
                verified_pieces=[],
                piece_states={},
                created_at=0.0,
                updated_at=0.0,
                output_dir=str(tmp_path),
                torrent_file_path=str(torrent_file),
            )
            return cp

    class _Model:
        def __init__(self):
            self.name = "test"
            self.info_hash = b"1" * 20
            self.pieces = []
            self.piece_length = 16384
            self.num_pieces = 1
            self.total_length = 16384

    class _Parser:
        def parse(self, path):
            return _Model()

    monkeypatch.setattr(sess_mod, "TorrentParser", lambda: _Parser())

    import ccbt.storage.checkpoint
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())

    async def _validate(cp):
        return True

    mgr = AsyncSessionManager(str(tmp_path))

    async def _mock_add(path, resume=False):
        add_torrent_called.append((path, resume))
        return (b"1" * 20).hex()

    monkeypatch.setattr(mgr, "add_torrent", _mock_add)
    monkeypatch.setattr(mgr, "validate_checkpoint", _validate)

    cp = await _CPM().load_checkpoint(b"1" * 20)
    await mgr.resume_from_checkpoint(b"1" * 20, cp)

    assert len(add_torrent_called) == 1
    assert add_torrent_called[0][0] == str(torrent_file)


@pytest.mark.asyncio
async def test_resume_from_checkpoint_with_magnet_uri(monkeypatch):
    """Test resume_from_checkpoint uses magnet_uri from checkpoint."""
    from ccbt.session.session import AsyncSessionManager

    add_magnet_called = []

    class _CPM:
        async def load_checkpoint(self, ih):
            cp = TorrentCheckpoint(
                info_hash=b"1" * 20,
                torrent_name="test",
                total_pieces=1,
                piece_length=16384,
                total_length=16384,
                verified_pieces=[],
                piece_states={},
                created_at=0.0,
                updated_at=0.0,
                output_dir=".",
                magnet_uri="magnet:?xt=urn:btih:" + ("1" * 40),
            )
            return cp

    import ccbt.storage.checkpoint
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())

    async def _validate(cp):
        return True

    mgr = AsyncSessionManager(".")

    async def _mock_add_magnet(uri, resume=False):
        add_magnet_called.append((uri, resume))
        return (b"1" * 20).hex()

    monkeypatch.setattr(mgr, "add_magnet", _mock_add_magnet)
    monkeypatch.setattr(mgr, "validate_checkpoint", _validate)

    cp = await _CPM().load_checkpoint(b"1" * 20)
    await mgr.resume_from_checkpoint(b"1" * 20, cp)

    assert len(add_magnet_called) == 1
    assert "magnet:" in add_magnet_called[0][0]


@pytest.mark.asyncio
async def test_resume_from_checkpoint_no_source_raises_valueerror(monkeypatch):
    """Test resume_from_checkpoint raises ValueError when no source available."""
    from ccbt.session.session import AsyncSessionManager

    class _CPM:
        async def load_checkpoint(self, ih):
            # Checkpoint with no torrent_file_path or magnet_uri
            cp = TorrentCheckpoint(
                info_hash=b"1" * 20,
                torrent_name="test",
                total_pieces=1,
                piece_length=16384,
                total_length=16384,
                verified_pieces=[],
                piece_states={},
                created_at=0.0,
                updated_at=0.0,
                output_dir=".",
            )
            return cp

    import ccbt.storage.checkpoint
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())

    async def _validate(cp):
        return True

    mgr = AsyncSessionManager(".")
    monkeypatch.setattr(mgr, "validate_checkpoint", _validate)

    cp = await _CPM().load_checkpoint(b"1" * 20)

    with pytest.raises(ValueError, match="No valid torrent source"):
        await mgr.resume_from_checkpoint(b"1" * 20, cp)


@pytest.mark.asyncio
async def test_resume_from_checkpoint_info_hash_mismatch_raises(monkeypatch, tmp_path):
    """Test resume_from_checkpoint raises ValueError on info hash mismatch."""
    from ccbt.session import session as sess_mod
    from ccbt.session.session import AsyncSessionManager

    class _Model:
        def __init__(self):
            self.name = "test"
            self.info_hash = b"2" * 20  # Different hash
            self.pieces = []
            self.piece_length = 16384
            self.num_pieces = 1
            self.total_length = 16384

    class _Parser:
        def parse(self, path):
            return _Model()

    monkeypatch.setattr(sess_mod, "TorrentParser", lambda: _Parser())

    class _CPM:
        async def load_checkpoint(self, ih):
            cp = TorrentCheckpoint(
                info_hash=b"1" * 20,  # Checkpoint is for hash "1"
                torrent_name="test",
                total_pieces=1,
                piece_length=16384,
                total_length=16384,
                verified_pieces=[],
                piece_states={},
                created_at=0.0,
                updated_at=0.0,
                output_dir=str(tmp_path),
                torrent_file_path=str(tmp_path / "test.torrent"),
            )
            return cp

    import ccbt.storage.checkpoint
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())

    torrent_file = tmp_path / "test.torrent"
    torrent_file.write_bytes(b"dummy")

    async def _validate(cp):
        return True

    mgr = AsyncSessionManager(str(tmp_path))
    monkeypatch.setattr(mgr, "validate_checkpoint", _validate)

    cp = await _CPM().load_checkpoint(b"1" * 20)

    with pytest.raises(ValueError, match="Info hash mismatch"):
        await mgr.resume_from_checkpoint(b"1" * 20, cp, str(torrent_file))


@pytest.mark.asyncio
async def test_resume_from_checkpoint_invalid_checkpoint_raises_validationerror(monkeypatch):
    """Test resume_from_checkpoint raises ValidationError for invalid checkpoint."""
    from ccbt.session.session import AsyncSessionManager
    from ccbt.utils.exceptions import ValidationError

    class _CPM:
        async def load_checkpoint(self, ih):
            cp = TorrentCheckpoint(
                info_hash=b"1" * 20,
                torrent_name="test",
                total_pieces=1,
                piece_length=16384,
                total_length=16384,
                verified_pieces=[],
                piece_states={},
                created_at=0.0,
                updated_at=0.0,
                output_dir=".",
                magnet_uri="magnet:?xt=urn:btih:" + ("1" * 40),
            )
            return cp

    import ccbt.storage.checkpoint
    monkeypatch.setattr(ccbt.storage.checkpoint, "CheckpointManager", lambda *a, **k: _CPM())

    async def _validate(cp):
        return False  # Invalid checkpoint

    mgr = AsyncSessionManager(".")
    monkeypatch.setattr(mgr, "validate_checkpoint", _validate)

    cp = await _CPM().load_checkpoint(b"1" * 20)

    with pytest.raises(ValidationError, match="Invalid checkpoint"):
        await mgr.resume_from_checkpoint(b"1" * 20, cp)

