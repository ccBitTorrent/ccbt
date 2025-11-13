"""Tests for validate_checkpoint method."""

import pytest
import time

from ccbt.models import TorrentCheckpoint, PieceState


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_true_for_valid(monkeypatch, tmp_path):
    """Test validate_checkpoint returns True for valid checkpoint."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(str(tmp_path))

    cp = TorrentCheckpoint(
        info_hash=b"1" * 20,
        torrent_name="valid",
        total_pieces=10,
        piece_length=16384,
        total_length=163840,
        verified_pieces=[0, 1, 2],
        piece_states={3: PieceState.DOWNLOADING, 4: PieceState.VERIFIED},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is True


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_for_invalid_hash_length(monkeypatch):
    """Test validate_checkpoint returns False for invalid hash length."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")

    cp = TorrentCheckpoint.model_construct(
        info_hash=b"1" * 19,  # 19 bytes, should be 20
        torrent_name="invalid",
        total_pieces=10,
        piece_length=16384,
        total_length=163840,
        verified_pieces=[],
        piece_states={},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=".",
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is False


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_for_empty_hash(monkeypatch):
    """Test validate_checkpoint returns False for empty hash."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")

    cp = TorrentCheckpoint.model_construct(
        info_hash=b"",  # Empty hash
        torrent_name="invalid",
        total_pieces=10,
        piece_length=16384,
        total_length=163840,
        verified_pieces=[],
        piece_states={},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=".",
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is False


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_for_zero_pieces(monkeypatch, tmp_path):
    """Test validate_checkpoint returns False for zero total_pieces."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(str(tmp_path))

    cp = TorrentCheckpoint.model_construct(
        info_hash=b"1" * 20,
        torrent_name="invalid",
        total_pieces=0,  # Invalid
        piece_length=16384,
        total_length=163840,
        verified_pieces=[],
        piece_states={},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is False


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_for_zero_piece_length(monkeypatch, tmp_path):
    """Test validate_checkpoint returns False for zero piece_length."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(str(tmp_path))

    cp = TorrentCheckpoint.model_construct(
        info_hash=b"1" * 20,
        torrent_name="invalid",
        total_pieces=10,
        piece_length=0,  # Invalid
        total_length=163840,
        verified_pieces=[],
        piece_states={},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is False


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_for_zero_total_length(monkeypatch, tmp_path):
    """Test validate_checkpoint returns False for zero total_length."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(str(tmp_path))

    cp = TorrentCheckpoint.model_construct(
        info_hash=b"1" * 20,
        torrent_name="invalid",
        total_pieces=10,
        piece_length=16384,
        total_length=0,  # Invalid
        verified_pieces=[],
        piece_states={},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is False


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_for_verified_piece_out_of_bounds(monkeypatch, tmp_path):
    """Test validate_checkpoint returns False for verified piece index out of bounds."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(str(tmp_path))

    cp = TorrentCheckpoint.model_construct(
        info_hash=b"1" * 20,
        torrent_name="invalid",
        total_pieces=10,
        piece_length=16384,
        total_length=163840,
        verified_pieces=[0, 1, 10],  # 10 is >= total_pieces (10)
        piece_states={},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is False


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_for_verified_piece_negative(monkeypatch, tmp_path):
    """Test validate_checkpoint returns False for negative verified piece index."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(str(tmp_path))

    cp = TorrentCheckpoint(
        info_hash=b"1" * 20,
        torrent_name="invalid",
        total_pieces=10,
        piece_length=16384,
        total_length=163840,
        verified_pieces=[0, 1, -1],  # -1 is negative
        piece_states={},
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is False


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_for_piece_state_out_of_bounds(monkeypatch, tmp_path):
    """Test validate_checkpoint returns False for piece state index out of bounds."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(str(tmp_path))

    cp = TorrentCheckpoint(
        info_hash=b"1" * 20,
        torrent_name="invalid",
        total_pieces=10,
        piece_length=16384,
        total_length=163840,
        verified_pieces=[],
        piece_states={10: PieceState.VERIFIED},  # 10 is >= total_pieces (10)
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is False


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_for_piece_state_negative(monkeypatch, tmp_path):
    """Test validate_checkpoint returns False for negative piece state index."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(str(tmp_path))

    cp = TorrentCheckpoint(
        info_hash=b"1" * 20,
        torrent_name="invalid",
        total_pieces=10,
        piece_length=16384,
        total_length=163840,
        verified_pieces=[],
        piece_states={-1: PieceState.VERIFIED},  # -1 is negative
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is False


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_for_invalid_piece_state_type(monkeypatch, tmp_path):
    """Test validate_checkpoint returns False for invalid piece state type."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(str(tmp_path))

    # Use model_construct to bypass validation and create invalid state
    cp = TorrentCheckpoint.model_construct(
        info_hash=b"1" * 20,
        torrent_name="invalid",
        total_pieces=10,
        piece_length=16384,
        total_length=163840,
        verified_pieces=[],
        piece_states={0: "invalid"},  # Not a PieceState enum
        created_at=time.time(),
        updated_at=time.time(),
        output_dir=str(tmp_path),
    )

    result = await mgr.validate_checkpoint(cp)
    assert result is False


@pytest.mark.asyncio
async def test_validate_checkpoint_returns_false_on_exception(monkeypatch):
    """Test validate_checkpoint returns False when exception occurs."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")

    # Create a checkpoint that will cause an exception when accessed
    class _BrokenCP:
        @property
        def info_hash(self):
            raise RuntimeError("broken")

    cp = _BrokenCP()

    result = await mgr.validate_checkpoint(cp)
    assert result is False

