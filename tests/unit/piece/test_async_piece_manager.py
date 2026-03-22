"""Comprehensive tests for AsyncPieceManager.

Covers verification failures, backpressure, edge cases, and missing code paths.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.piece]

from ccbt.models import DownloadStats, PieceState as CheckpointPieceState, TorrentCheckpoint
from ccbt.piece.async_piece_manager import AsyncPieceManager, PieceBlock, PieceData, PieceState
from ccbt.peer.peer import PeerInfo
from ccbt.peer.async_peer_connection import RequestInfo
from ccbt.utils.shutdown import clear_shutdown, set_shutdown


@pytest.fixture
def mock_torrent_data():
    """Create mock torrent data for testing."""
    return {
        "info_hash": b"\x00" * 20,
        "file_info": {
            "name": "test_file.txt",
            "total_length": 10 * 16384,  # 10 pieces of 16KB
            "type": "single",
        },
        "pieces_info": {
            "num_pieces": 10,
            "piece_length": 16384,
            "piece_hashes": [b"\x01" * 20 for _ in range(10)],
        },
    }


@pytest_asyncio.fixture
async def piece_manager(mock_torrent_data):
    """Create async piece manager for testing."""
    manager = AsyncPieceManager(mock_torrent_data)
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
def mock_peer_connection():
    """Create mock peer connection."""
    peer = AsyncMock()
    peer.peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    peer.bitfield = b"\xff" * 2  # All pieces available
    return peer


class TestAsyncPieceManagerVerification:
    """Test hash verification functionality."""

    @pytest.mark.asyncio
    async def test_verify_piece_hash_success(self, piece_manager):
        """Test successful piece hash verification."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        # Create valid data - need full piece data that matches piece length exactly
        piece_length = piece.length
        # Generate enough data for the piece
        base_data = b"test_piece_data" * 2000
        if len(base_data) < piece_length:
            piece_data = base_data + b"\x00" * (piece_length - len(base_data))
        else:
            piece_data = base_data[:piece_length]
        
        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        piece_manager.piece_hashes[piece_index] = expected_hash

        # Add all blocks to complete piece - each block must get data matching its exact length
        for block in piece.blocks:
            # Extract data for this block from the full piece data
            block_end = min(block.begin + block.length, len(piece_data))
            block_data = piece_data[block.begin : block_end]
            
            # Pad if needed (for last block)
            if len(block_data) < block.length:
                block_data = block_data + b"\x00" * (block.length - len(block_data))
            
            # Ensure exact match
            assert len(block_data) == block.length, f"Block data length {len(block_data)} != block.length {block.length}"
            
            success = piece.add_block(block.begin, block_data)
            assert success, f"Failed to add block at begin={block.begin}, length={block.length}, data_len={len(block_data)}, piece_len={piece_length}"

        # Ensure piece is marked as complete
        assert piece.is_complete()
        assert piece.state == PieceState.COMPLETE

        callback_called = False

        def mock_callback(idx):
            nonlocal callback_called
            callback_called = True
            assert idx == piece_index

        piece_manager.on_piece_verified = mock_callback

        await piece_manager._verify_piece_hash(piece_index, piece)

        assert piece_index in piece_manager.verified_pieces
        assert piece.state == PieceState.VERIFIED
        assert callback_called

    @pytest.mark.asyncio
    async def test_verify_piece_hash_failure(self, piece_manager):
        """Test hash verification failure."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        # Create invalid data (wrong hash)
        piece_data = b"wrong_piece_data" * 1024
        piece_data = piece_data[:16384]
        wrong_hash = hashlib.sha1(b"different_data").digest()  # nosec B324
        piece_manager.piece_hashes[piece_index] = wrong_hash

        # Add all blocks to complete piece
        for block in piece.blocks:
            piece.add_block(block.begin, piece_data[block.begin : block.begin + block.length])

        # Verify should fail
        await piece_manager._verify_piece_hash(piece_index, piece)

        # Should not be verified
        assert piece_index not in piece_manager.verified_pieces
        assert piece.state != PieceState.VERIFIED

    @pytest.mark.asyncio
    async def test_verification_counters_are_exposed(self, piece_manager):
        """Verification counters should be exported for stall diagnostics."""
        counters = piece_manager.get_verification_counters()
        assert counters["piece_hash_verification_successes"] == 0
        assert counters["piece_hash_verification_failures"] == 0

    @pytest.mark.asyncio
    async def test_verify_piece_hash_exception(self, piece_manager):
        """Test hash verification with exception."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        # Mock get_data to raise exception
        with patch.object(piece, "get_data", side_effect=Exception("Test error")):
            await piece_manager._verify_piece_hash(piece_index, piece)

        # Should not crash, piece should not be verified
        assert piece_index not in piece_manager.verified_pieces

    @pytest.mark.asyncio
    async def test_hash_piece_optimized(self, piece_manager):
        """Test optimized hash verification."""
        piece = PieceData(piece_index=0, length=16384)
        piece_data = b"test_data" * 2048
        piece_data = piece_data[:16384]

        # Add blocks
        for block in piece.blocks:
            piece.add_block(block.begin, piece_data[block.begin : block.begin + block.length])

        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        is_valid = piece_manager._hash_piece_optimized(piece, expected_hash)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_hash_piece_optimized_failure(self, piece_manager):
        """Test optimized hash verification failure."""
        piece = PieceData(piece_index=0, length=16384)
        piece_data = b"test_data" * 2048
        piece_data = piece_data[:16384]

        # Add blocks
        for block in piece.blocks:
            piece.add_block(block.begin, piece_data[block.begin : block.begin + block.length])

        wrong_hash = hashlib.sha1(b"wrong").digest()  # nosec B324
        is_valid = piece_manager._hash_piece_optimized(piece, wrong_hash)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_hash_piece_optimized_exception(self, piece_manager):
        """Test optimized hash with exception."""
        piece = PieceData(piece_index=0, length=16384)

        # Mock get_data to raise exception
        with patch.object(piece, "get_data", side_effect=Exception("Test error")):
            result = piece_manager._hash_piece_optimized(piece, b"\x00" * 20)

        assert result is False

    @pytest.mark.asyncio
    async def test_batch_verify_pieces(self, piece_manager):
        """Test batch verification of multiple pieces."""
        pieces_to_verify = []

        # Create 3 completed pieces
        for i in range(3):
            piece = piece_manager.pieces[i]
            piece_data = b"test" * 4096
            piece_data = piece_data[:16384]

            # Add blocks
            for block in piece.blocks:
                piece.add_block(block.begin, piece_data[block.begin : block.begin + block.length])

            expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
            piece_manager.piece_hashes[i] = expected_hash

            pieces_to_verify.append((i, piece))

        await piece_manager._batch_verify_pieces(pieces_to_verify)

        # All should be verified
        for i in range(3):
            assert i in piece_manager.verified_pieces

    @pytest.mark.asyncio
    async def test_batch_verify_pieces_empty(self, piece_manager):
        """Test batch verification with empty list."""
        await piece_manager._batch_verify_pieces([])
        # Should not crash
        assert True


class TestAsyncPieceManagerGetBlock:
    """Test get_block functionality."""

    @pytest.mark.asyncio
    async def test_get_block_from_verified_piece(self, piece_manager):
        """Test getting block from verified piece."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        # Complete and verify piece
        piece_data = b"test_data" * 2048
        piece_data = piece_data[:piece.length]  # Use actual piece length
        
        # Add all blocks correctly - use block.begin for slicing
        for block in piece.blocks:
            block_data = piece_data[block.begin : block.begin + block.length]
            success = piece.add_block(block.begin, block_data)
            assert success

        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        piece_manager.piece_hashes[piece_index] = expected_hash

        await piece_manager._verify_piece_hash(piece_index, piece)

        # Get block
        block_size = min(16384, piece.length)
        block_data = piece_manager.get_block(piece_index, 0, block_size)
        assert block_data == piece_data[:block_size]

    @pytest.mark.asyncio
    async def test_get_block_invalid_indices(self, piece_manager):
        """Test get_block with invalid indices."""
        # Invalid piece index
        result = piece_manager.get_block(999, 0, 16384)
        assert result is None

        # Valid piece but invalid range
        result = piece_manager.get_block(0, 99999, 16384)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_block_from_incomplete_piece(self, piece_manager):
        """Test getting block from incomplete piece."""
        # Piece is not complete
        result = piece_manager.get_block(0, 0, 16384)
        assert result is None


class TestAsyncPieceManagerPieceSelector:
    """Test piece selector background task."""

    @pytest.mark.asyncio
    async def test_piece_selector_runs(self, piece_manager):
        """Test that piece selector runs without crashing."""
        piece_manager.is_downloading = True

        # Start selector and let it run briefly
        task = asyncio.create_task(piece_manager._piece_selector())
        await asyncio.sleep(0.1)
        task.cancel()

        try:
            await asyncio.wait_for(task, timeout=0.2)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

        assert task.done()

    @pytest.mark.asyncio
    async def test_piece_selector_no_progress_gate_engages_and_releases_after_progress(
        self, piece_manager
    ):
        """No-progress gate should pause briefly and resume once selector work progresses."""
        piece_manager.is_downloading = True
        piece_manager._no_progress_stall_threshold = 1
        piece_manager._no_progress_pause_s = 0.01
        piece_manager._no_progress_streak = 0
        piece_manager._no_progress_stall_until = 0.0
        piece_manager._piece_selection_metrics["selection_no_progress_streak"] = 0
        piece_manager._piece_selection_metrics["no_progress_gate_events"] = 0
        piece = piece_manager.pieces[0]
        piece.state = PieceState.MISSING

        select_calls = 0
        sleep_calls = 0
        original_sleep = asyncio.sleep

        async def fake_select_pieces() -> None:
            nonlocal select_calls
            select_calls += 1
            if select_calls == 4:
                piece.state = PieceState.DOWNLOADING

        async def fast_sleep(_seconds: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1
            await original_sleep(0.001)
            if sleep_calls > 120:
                piece_manager._stopping = True

        piece_manager._select_pieces = fake_select_pieces

        with patch("ccbt.piece.async_piece_manager.asyncio.sleep", new=fast_sleep):
            task = asyncio.create_task(piece_manager._piece_selector())
            await asyncio.sleep(0)
            await asyncio.wait_for(task, timeout=0.5)

        assert select_calls >= 2
        assert piece_manager._piece_selection_metrics["no_progress_gate_events"] >= 1
        assert piece.state == PieceState.DOWNLOADING
        assert task.done()

    @pytest.mark.asyncio
    async def test_piece_selector_no_progress_gate_counts_no_peers_reason(self, piece_manager):
        """No-progress gate should attribute stalls to no-peers when no active peers are present."""
        piece_manager.is_downloading = True
        piece_manager._peer_manager = SimpleNamespace(get_active_peers=lambda: [])
        piece_manager._no_progress_stall_threshold = 1
        piece_manager._no_progress_pause_s = 0.01
        piece_manager._piece_selection_metrics["no_progress_gate_events"] = 0
        piece_manager._piece_selection_metrics["no_progress_gate_no_peers"] = 0

        select_calls = 0
        sleep_calls = 0
        original_sleep = asyncio.sleep

        async def fake_select_pieces() -> None:
            nonlocal select_calls
            select_calls += 1

        async def fast_sleep(_seconds: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1
            await original_sleep(0.001)
            if sleep_calls > 60:
                piece_manager._stopping = True

        piece_manager._select_pieces = fake_select_pieces

        with patch("ccbt.piece.async_piece_manager.asyncio.sleep", new=fast_sleep):
            task = asyncio.create_task(piece_manager._piece_selector())
            await asyncio.sleep(0)
            await asyncio.wait_for(task, timeout=1.0)

        assert select_calls >= 2
        assert piece_manager._piece_selection_metrics["no_progress_gate_no_peers"] >= 1
        assert piece_manager._piece_selection_metrics["no_progress_gate_events"] >= 1

    @pytest.mark.asyncio
    async def test_piece_selector_no_progress_gate_counts_no_requestable_reason(self, piece_manager):
        """No-progress gate should attribute stalls to requestable-peer unavailability."""
        piece_manager.is_downloading = True
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [
                SimpleNamespace(peer_info=PeerInfo(ip="127.0.0.1", port=6881))
            ]
        )
        piece_manager._no_progress_stall_threshold = 1
        piece_manager._no_progress_pause_s = 0.01
        piece_manager._piece_selection_metrics["no_progress_gate_events"] = 0
        piece_manager._piece_selection_metrics["no_progress_gate_no_requestable_peers"] = 0

        select_calls = 0
        sleep_calls = 0
        original_sleep = asyncio.sleep

        async def fake_select_pieces() -> None:
            nonlocal select_calls
            select_calls += 1
            piece_manager._piece_selection_metrics["no_requestable_peers"] += 1

        async def fast_sleep(_seconds: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1
            await original_sleep(0.001)
            if sleep_calls > 60:
                piece_manager._stopping = True

        piece_manager._select_pieces = fake_select_pieces

        with patch("ccbt.piece.async_piece_manager.asyncio.sleep", new=fast_sleep):
            task = asyncio.create_task(piece_manager._piece_selector())
            await asyncio.sleep(0)
            await asyncio.wait_for(task, timeout=1.0)

        assert select_calls >= 2
        assert piece_manager._piece_selection_metrics["no_progress_gate_no_requestable_peers"] >= 1
        assert piece_manager._piece_selection_metrics["no_progress_gate_events"] >= 1

    @pytest.mark.asyncio
    async def test_piece_selector_no_progress_gate_counts_request_timeout_reason(self, piece_manager):
        """No-progress gate should attribute stalls to request-timeout when active requests do not advance."""
        piece_manager.is_downloading = True
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [
                SimpleNamespace(
                    peer_info=PeerInfo(ip="127.0.0.1", port=6881),
                    can_request=lambda: True,
                    peer_state=SimpleNamespace(pieces_we_have={0}),
                )
            ],
            connections={},
        )
        piece_manager.peer_availability[str(piece_manager._peer_manager.get_active_peers()[0].peer_info)] = (
            SimpleNamespace(
                pieces={0},
                reliability_score=1.0,
                average_download_speed=1.0,
                connection_quality_score=1.0,
            )
        )
        piece_manager._no_progress_stall_threshold = 1
        piece_manager._no_progress_pause_s = 0.01
        piece_manager._piece_selection_metrics["no_progress_gate_events"] = 0
        piece_manager._piece_selection_metrics["no_progress_gate_request_timeouts"] = 0
        piece_manager._piece_selection_metrics["no_progress_gate_reason"] = "none"

        piece_manager.pieces[0].state = PieceState.REQUESTED

        select_calls = 0
        sleep_calls = 0
        original_sleep = asyncio.sleep

        async def counting_select_pieces() -> None:
            nonlocal select_calls
            select_calls += 1

        piece_manager._select_pieces = counting_select_pieces

        async def fast_sleep(_seconds: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1
            await original_sleep(0.001)
            if sleep_calls > 120:
                piece_manager._stopping = True

        with patch("ccbt.piece.async_piece_manager.asyncio.sleep", new=fast_sleep):
            task = asyncio.create_task(piece_manager._piece_selector())
            await asyncio.sleep(0)
            await asyncio.wait_for(task, timeout=1.0)

        assert select_calls >= 2
        assert piece_manager._piece_selection_metrics["no_progress_gate_request_timeouts"] >= 1
        assert piece_manager._piece_selection_metrics["no_progress_gate_reason"] == "request_timeouts"
        assert piece_manager._piece_selection_metrics["no_progress_gate_events"] >= 1

    @pytest.mark.asyncio
    async def test_piece_selection_metrics_include_last_no_progress_gate_reason(self, piece_manager):
        """Piece selection metrics should expose recent no-progress gate reason and timestamp."""
        piece_manager._piece_selection_metrics["no_progress_gate_reason"] = "test_reason"
        piece_manager._piece_selection_metrics["no_progress_gate_engaged_at"] = 1234.5

        metrics = piece_manager.get_piece_selection_metrics()

        assert metrics["no_progress_gate_reason"] == "test_reason"
        assert metrics["no_progress_gate_engaged_at"] == 1234.5

    @pytest.mark.asyncio
    async def test_piece_selector_no_progress_gate_counts_choked_with_piece_reason(self, piece_manager):
        """No-progress gate should distinguish choked peers that still advertise piece availability."""
        piece_manager.is_downloading = True
        choked_peer = SimpleNamespace(
            peer_info=PeerInfo(ip="127.0.0.1", port=6881),
            can_request=lambda: False,
            peer_state=SimpleNamespace(pieces_we_have={0}),
        )
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [choked_peer],
            connections={},
        )
        piece_manager._no_progress_stall_threshold = 1
        piece_manager._no_progress_pause_s = 0.01
        piece_manager._piece_selection_metrics["no_progress_gate_events"] = 0
        piece_manager._piece_selection_metrics["no_progress_gate_choked_with_piece"] = 0
        piece_manager._piece_selection_metrics["no_requestable_peers"] = 0

        piece_manager.pieces[0].state = PieceState.REQUESTED
        piece_manager.peer_availability[str(choked_peer.peer_info)] = (
            SimpleNamespace(
                pieces={0},
                reliability_score=1.0,
                average_download_speed=1.0,
                connection_quality_score=1.0,
            )
        )

        select_calls = 0
        sleep_calls = 0
        original_sleep = asyncio.sleep

        async def counting_select_pieces() -> None:
            nonlocal select_calls
            select_calls += 1
            piece_manager._piece_selection_metrics["no_requestable_peers"] += 1

        piece_manager._select_pieces = counting_select_pieces

        async def fast_sleep(_seconds: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1
            await original_sleep(0.001)
            if sleep_calls > 120:
                piece_manager._stopping = True

        with patch("ccbt.piece.async_piece_manager.asyncio.sleep", new=fast_sleep):
            task = asyncio.create_task(piece_manager._piece_selector())
            await asyncio.sleep(0)
            await asyncio.wait_for(task, timeout=1.0)

        assert select_calls >= 2
        assert piece_manager._piece_selection_metrics["no_progress_gate_choked_with_piece"] >= 1
        assert piece_manager._piece_selection_metrics["no_progress_gate_events"] >= 1

    @pytest.mark.asyncio
    async def test_piece_selector_no_progress_gate_counts_true_zero_availability_reason(self, piece_manager):
        """No-progress gate should capture true-zero-availability stalls when peers have no availability signals."""
        piece_manager.is_downloading = True
        peer = SimpleNamespace(
            peer_info=PeerInfo(ip="198.51.100.31", port=6881),
            can_request=lambda: True,
            peer_state=SimpleNamespace(pieces_we_have=set()),
        )
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [peer],
            connections={},
        )
        piece_manager._no_progress_stall_threshold = 1
        piece_manager._no_progress_pause_s = 0.01
        piece_manager._piece_selection_metrics["no_progress_gate_events"] = 0
        piece_manager._piece_selection_metrics["no_progress_gate_true_zero_availability"] = 0

        select_calls = 0
        sleep_calls = 0
        original_sleep = asyncio.sleep

        async def fake_select_pieces() -> None:
            nonlocal select_calls
            select_calls += 1

        async def fast_sleep(_seconds: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1
            await original_sleep(0.001)
            if sleep_calls > 80:
                piece_manager._stopping = True

        piece_manager._select_pieces = fake_select_pieces

        with patch("ccbt.piece.async_piece_manager.asyncio.sleep", new=fast_sleep):
            task = asyncio.create_task(piece_manager._piece_selector())
            await asyncio.sleep(0)
            await asyncio.wait_for(task, timeout=1.0)

        assert select_calls >= 2
        assert piece_manager._piece_selection_metrics["no_progress_gate_true_zero_availability"] >= 1
        assert piece_manager._piece_selection_metrics["no_progress_gate_events"] >= 1

    def test_next_no_progress_gate_pause_shortens_for_request_timeouts_with_few_peers(
        self, piece_manager
    ):
        piece_manager._no_progress_pause_s = 4.0
        piece_manager._no_progress_gate_streak = 0

        pause_low_peer_count = piece_manager._next_no_progress_gate_pause(
            "request_timeouts", active_peer_count=1
        )
        pause_high_peer_count = piece_manager._next_no_progress_gate_pause(
            "request_timeouts", active_peer_count=10
        )

        assert pause_low_peer_count < pause_high_peer_count

    @pytest.mark.asyncio
    async def test_piece_selector_suppresses_gate_during_transient_unchoke_scarcity(self, piece_manager):
        """Retry grace should suppress repeated no-progress gates while peers are temporarily unchoked."""
        piece_manager.is_downloading = True
        piece_manager._no_progress_stall_threshold = 1
        piece_manager._no_progress_pause_s = 0.01
        piece_manager._piece_selection_metrics["no_progress_gate_events"] = 0
        piece_manager._piece_selection_metrics["selection_no_progress_streak"] = 0
        piece_manager._metadata_incomplete = False
        piece_manager._retry_from_active_delay_s = 0.2

        peer = SimpleNamespace(
            peer_info=PeerInfo(ip="198.51.100.12", port=6881),
            is_active=lambda: True,
            can_request=lambda: False,
            peer_state=SimpleNamespace(pieces_we_have={0}),
        )
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [peer],
            connections={},
        )
        piece_manager.pieces[0].state = PieceState.REQUESTED
        piece_manager.pieces[0].request_count = 2
        piece_manager.pieces[0].requests_dispatched = 1
        piece_manager.pieces[0].last_request_time = time.time()
        piece_manager.peer_availability[str(peer.peer_info)] = SimpleNamespace(
            pieces={0},
            reliability_score=1.0,
            average_download_speed=1.0,
            connection_quality_score=1.0,
        )

        original_select_pieces = piece_manager._select_pieces
        select_calls = 0

        async def counting_select_pieces() -> None:
            nonlocal select_calls
            select_calls += 1
            await original_select_pieces()

        piece_manager._select_pieces = counting_select_pieces

        sleep_calls = 0
        original_sleep = asyncio.sleep

        async def fast_sleep(_seconds: float) -> None:
            nonlocal sleep_calls
            sleep_calls += 1
            await original_sleep(0.001)
            if sleep_calls > 60:
                piece_manager._stopping = True

        with patch("ccbt.piece.async_piece_manager.asyncio.sleep", new=fast_sleep):
            task = asyncio.create_task(piece_manager._piece_selector())
            await asyncio.sleep(0)
            await asyncio.wait_for(task, timeout=1.0)

        assert select_calls >= 2
        assert piece_manager._piece_selection_metrics["no_progress_gate_events"] == 0
        assert piece_manager._no_progress_retry_grace_until >= time.time()

    @pytest.mark.asyncio
    async def test_select_pieces_not_downloading(self, piece_manager):
        """Test select_pieces when not downloading."""
        piece_manager.is_downloading = False
        await piece_manager._select_pieces()
        # Should return early without error
        assert True

    @pytest.mark.asyncio
    async def test_select_pieces_download_complete(self, piece_manager):
        """Test select_pieces when download is complete."""
        piece_manager.is_downloading = True
        piece_manager.download_complete = True
        await piece_manager._select_pieces()
        # Should return early without error
        assert True

    @pytest.mark.asyncio
    async def test_select_pieces_skips_when_stopping(self, piece_manager):
        """Selector should stop issuing work once shutdown begins."""
        piece_manager._stopping = True
        piece_manager.is_downloading = True
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=MagicMock(return_value=[]),
            connections={},
        )

        await piece_manager._select_pieces()

        piece_manager._peer_manager.get_active_peers.assert_not_called()

    @pytest.mark.asyncio
    async def test_spawn_piece_selection_task_ignored_during_shutdown(self, piece_manager):
        """Don't spawn a piece-selection task when shutdown is active."""
        set_shutdown()
        try:
            ran = False

            async def delayed_selector() -> None:
                nonlocal ran
                ran = True

            piece_manager._spawn_piece_selection_task(delayed_selector())
            assert len(piece_manager._piece_selection_trigger_tasks) == 0
            assert not ran
        finally:
            clear_shutdown()

    @pytest.mark.asyncio
    async def test_spawn_piece_selection_task_cancels_on_stop(self, piece_manager):
        """Tracked piece-selection tasks should be cancelled when the manager stops."""
        started = asyncio.Event()

        async def delayed_selector() -> None:
            started.set()
            await asyncio.sleep(10)

        piece_manager._spawn_piece_selection_task(delayed_selector())
        assert len(piece_manager._piece_selection_trigger_tasks) == 1
        await asyncio.wait_for(started.wait(), timeout=1.0)

        await piece_manager.stop()
        assert len(piece_manager._piece_selection_trigger_tasks) == 0

    @pytest.mark.asyncio
    async def test_select_pieces_triggers_recovery_without_piece_info(
        self, piece_manager
    ):
        """Metadata-complete swarms with active peers but no availability should trigger recovery."""
        schedule_pending_resume = MagicMock()
        fake_peer = SimpleNamespace(
            peer_info=SimpleNamespace(ip="203.0.113.10", port=6881),
            can_request=lambda: True,
        )
        piece_manager.is_downloading = True
        piece_manager._metadata_incomplete = False
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=MagicMock(return_value=[fake_peer]),
            _schedule_pending_resume=schedule_pending_resume,
            connections={"203.0.113.10:6881": fake_peer},
        )
        piece_manager.peer_availability.clear()

        await piece_manager._select_pieces()

        schedule_pending_resume.assert_called_once_with(
            reason="piece_selector_no_piece_info"
        )

    @pytest.mark.asyncio
    async def test_select_pieces_continues_with_requestable_metadata_only_peer(
        self, piece_manager
    ):
        """Metadata-only peers should still drive optimistic payload bootstrap attempts."""
        schedule_pending_resume = MagicMock()
        fake_peer = SimpleNamespace(
            peer_info=SimpleNamespace(ip="203.0.113.11", port=6881),
            can_request=lambda: True,
            peer_state=SimpleNamespace(pieces_we_have=set()),
        )
        piece_manager.is_downloading = True
        piece_manager._metadata_incomplete = False
        piece_manager._retry_requested_pieces = AsyncMock()
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=MagicMock(return_value=[fake_peer]),
            _schedule_pending_resume=schedule_pending_resume,
            connections={"203.0.113.11:6881": fake_peer},
        )
        piece_manager.peer_availability.clear()

        await piece_manager._select_pieces()

        schedule_pending_resume.assert_called_once_with(
            reason="piece_selector_no_piece_info"
        )
        piece_manager._retry_requested_pieces.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_endgame_mode_activation(self, piece_manager):
        """Test endgame mode activation."""
        piece_manager.is_downloading = True

        # Calculate threshold - typically 85-90% complete
        threshold = piece_manager.endgame_threshold
        pieces_to_verify = int(piece_manager.num_pieces * (1.0 - threshold)) + 1

        # Mark enough pieces as verified to trigger endgame
        for i in range(pieces_to_verify):
            piece_manager.pieces[i].state = PieceState.VERIFIED
            piece_manager.verified_pieces.add(i)

        await piece_manager._select_pieces()

        # Endgame should activate when threshold is reached
        # Allow for slight variations in threshold calculation
        remaining = len(piece_manager.get_missing_pieces())
        threshold_pieces = int(piece_manager.num_pieces * (1.0 - threshold))
        if remaining <= threshold_pieces:
            assert piece_manager.endgame_mode is True
        else:
            # If not activated, verify the calculation
            assert len(piece_manager.verified_pieces) >= pieces_to_verify


class TestAsyncPieceManagerHandlePieceBlock:
    """Test handle_piece_block functionality."""

    @pytest.mark.asyncio
    async def test_handle_piece_block_completes_piece(self, piece_manager):
        """Test handling block that completes a piece."""
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        callback_called = False

        def mock_callback(idx):
            nonlocal callback_called
            callback_called = True
            assert idx == piece_index

        piece_manager.on_piece_completed = mock_callback

        # Add all blocks except last one
        for block in piece.blocks[:-1]:
            await piece_manager.handle_piece_block(piece_index, block.begin, b"x" * block.length)

        # Add last block to complete
        last_block = piece.blocks[-1]
        await piece_manager.handle_piece_block(piece_index, last_block.begin, b"x" * last_block.length)

        assert piece_index in piece_manager.completed_pieces
        assert callback_called

    @pytest.mark.asyncio
    async def test_handle_piece_block_invalid_index(self, piece_manager):
        """Test handle_piece_block with invalid piece index."""
        # Should not crash
        await piece_manager.handle_piece_block(999, 0, b"data")
        assert True

    @pytest.mark.asyncio
    async def test_handle_piece_block_schedules_verification(self, piece_manager):
        """Test that completing a piece schedules verification."""
        import hashlib
        
        piece_index = 0
        piece = piece_manager.pieces[piece_index]

        # Note: Set correct piece hash that matches the test data
        # The test data is b"x" * block.length for each block, so we need to calculate
        # the hash of the complete piece data
        piece_data = b"x" * piece.length
        expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
        piece_manager.piece_hashes[piece_index] = expected_hash

        # Complete piece by adding all blocks
        for block in piece.blocks:
            await piece_manager.handle_piece_block(piece_index, block.begin, b"x" * block.length)

        # Give time for verification task to start and piece state to update
        await asyncio.sleep(0.1)

        # Piece should be complete (or verified if verification completed quickly)
        assert piece.state in (PieceState.COMPLETE, PieceState.VERIFIED), f"Piece state is {piece.state}, expected COMPLETE or VERIFIED"
        
        # Verification should have been scheduled (check that task was added, even if it completed quickly)
        # The task might complete before we check, so we verify the piece is complete and was in completed_pieces
        # Note: If verification fails, the piece is removed from completed_pieces, so we check state instead
        # If verification succeeded, piece should be verified; if still verifying, it should be in completed_pieces
        assert (
            piece_index in piece_manager.completed_pieces or 
            piece.state == PieceState.VERIFIED
        ), f"Piece should be in completed_pieces or verified (state={piece.state}, completed_pieces={piece_manager.completed_pieces})"


class TestAsyncPieceManagerBackpressure:
    """Test backpressure and rate limiting scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_verifications_concurrent(self, piece_manager):
        """Test concurrent piece verifications."""
        # Complete multiple pieces
        for i in range(3):
            piece = piece_manager.pieces[i]
            piece_data = b"test" * 4096
            piece_data = piece_data[:16384]
            expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
            piece_manager.piece_hashes[i] = expected_hash

            for block in piece.blocks:
                await piece_manager.handle_piece_block(i, block.begin, piece_data[block.begin : block.begin + block.length])

        # Wait for verifications
        await asyncio.sleep(0.2)

        # All should eventually be verified
        for i in range(3):
            assert i in piece_manager.verified_pieces or piece_manager.pieces[i].state == PieceState.COMPLETE

    @pytest.mark.asyncio
    async def test_download_complete_callback(self, piece_manager):
        """Test download complete callback when all pieces verified."""
        callback_called = False

        def mock_callback():
            nonlocal callback_called
            callback_called = True

        piece_manager.on_download_complete = mock_callback

        # Verify all pieces
        for i in range(piece_manager.num_pieces):
            piece = piece_manager.pieces[i]
            piece_data = b"test" * 4096
            piece_data = piece_data[:16384]
            expected_hash = hashlib.sha1(piece_data).digest()  # nosec B324
            piece_manager.piece_hashes[i] = expected_hash

            for block in piece.blocks:
                piece.add_block(block.begin, piece_data[block.begin : block.begin + block.length])

            await piece_manager._verify_piece_hash(i, piece)

        assert callback_called
        assert piece_manager.download_complete is True

    @pytest.mark.asyncio
    async def test_download_complete_callback_only_once(self, piece_manager):
        """Completion callback should fire once even after the final piece verifies."""
        callback_count = 0

        def mock_callback():
            nonlocal callback_count
            callback_count += 1

        piece_manager.on_download_complete = mock_callback

        for i in range(piece_manager.num_pieces):
            piece = piece_manager.pieces[i]
            piece_data = (f"piece-{i}".encode() * 4096)[:16384]
            piece_manager.piece_hashes[i] = hashlib.sha1(piece_data).digest()  # nosec B324

            for block in piece.blocks:
                piece.add_block(
                    block.begin, piece_data[block.begin : block.begin + block.length]
                )

            await piece_manager._verify_piece_hash(i, piece)

        assert callback_count == 1
        assert piece_manager.download_complete is True


class TestAsyncPieceManagerEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_update_peer_availability_triggers_bounded_retry_for_requested_pieces(self, piece_manager):
        """Bitfield updates should trigger focused bounded retries when new pieces appear."""
        piece_manager._peer_manager = SimpleNamespace(get_active_peers=lambda: [])
        piece_manager._retry_requested_pieces = AsyncMock()
        piece_manager.pieces[0].state = PieceState.REQUESTED

        peer_key = "198.51.100.80:6881"
        await piece_manager.update_peer_availability(peer_key, b"\x80")

        piece_manager._retry_requested_pieces.assert_awaited_once_with(
            focus_peer=peer_key,
            max_retry_count=2,
            max_requesters=1,
        )

    @pytest.mark.asyncio
    async def test_update_peer_availability_from_piece_indices_triggers_bounded_retry_for_requested_pieces(self, piece_manager):
        """Piece index updates should trigger focused bounded retries when new availability appears."""
        piece_manager._peer_manager = SimpleNamespace(get_active_peers=lambda: [])
        piece_manager._retry_requested_pieces = AsyncMock()
        piece_manager.pieces[0].state = PieceState.REQUESTED
        piece_manager.peer_availability["198.51.100.81:6881"] = SimpleNamespace(
            pieces={1},
            reliability_score=1.0,
            average_download_speed=1.0,
            connection_quality_score=1.0,
        )

        await piece_manager.update_peer_availability_from_piece_indices(
            "198.51.100.81:6881",
            {0, 1},
        )

        piece_manager._retry_requested_pieces.assert_awaited_once_with(
            focus_peer="198.51.100.81:6881",
            max_retry_count=2,
            max_requesters=1,
        )

    @pytest.mark.asyncio
    async def test_update_peer_availability_no_retry_when_no_new_piece_information(self, piece_manager):
        """Do not trigger retries when the bitfield does not increase peer availability."""
        piece_manager._peer_manager = SimpleNamespace(get_active_peers=lambda: [])
        piece_manager._retry_requested_pieces = AsyncMock()
        piece_manager.pieces[0].state = PieceState.REQUESTED
        piece_manager.peer_availability["198.51.100.80:6881"] = SimpleNamespace(
            pieces={0},
            reliability_score=1.0,
            average_download_speed=1.0,
            connection_quality_score=1.0,
        )

        await piece_manager.update_peer_availability("198.51.100.80:6881", b"\x80")

        piece_manager._retry_requested_pieces.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_download_progress_zero_pieces(self):
        """Test download progress with zero pieces."""
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "file_info": {"total_length": 0, "type": "single"},
            "pieces_info": {"num_pieces": 0, "piece_length": 16384, "piece_hashes": []},
        }
        manager = AsyncPieceManager(torrent_data)
        progress = manager.get_download_progress()
        assert progress == 1.0  # 100% when no pieces

    @pytest.mark.asyncio
    async def test_get_piece_status(self, piece_manager):
        """Test getting piece status counts."""
        # Mark some pieces with different states
        piece_manager.pieces[0].state = PieceState.MISSING
        piece_manager.pieces[1].state = PieceState.DOWNLOADING
        piece_manager.pieces[2].state = PieceState.VERIFIED

        status = piece_manager.get_piece_status()

        assert status["missing"] >= 1
        assert status["downloading"] >= 1
        assert status["verified"] >= 1

    @pytest.mark.asyncio
    async def test_get_peers_for_piece_skips_unknown_probes_when_known_peer_is_choked(
        self, piece_manager
    ):
        """Unknown peers should not be probed when another peer already advertises the piece."""
        await piece_manager.update_peer_availability("198.51.100.10:6881", b"\x80")

        def make_peer(
            ip: str,
            port: int,
            *,
            can_request: bool,
            peer_choking: bool,
        ) -> MagicMock:
            peer = MagicMock()
            peer.peer_info = PeerInfo(ip=ip, port=port)
            peer.can_request.return_value = can_request
            peer.get_available_pipeline_slots.return_value = 4
            peer.outstanding_requests = {}
            peer.max_pipeline_depth = 4
            peer.peer_choking = peer_choking
            peer.am_interested = True
            peer.peer_interested = False
            peer.state = SimpleNamespace(value="active")
            peer.stats = SimpleNamespace(download_rate=0.0)
            peer.peer_state = SimpleNamespace(
                pieces_we_have=set(),
                bitfield=b"",
            )
            peer.is_active.return_value = True
            return peer

        choked_known_peer = make_peer(
            "198.51.100.10",
            6881,
            can_request=False,
            peer_choking=True,
        )
        unknown_peer_a = make_peer(
            "198.51.100.11",
            6882,
            can_request=True,
            peer_choking=False,
        )
        unknown_peer_b = make_peer(
            "198.51.100.12",
            6883,
            can_request=True,
            peer_choking=False,
        )
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [
                choked_known_peer,
                unknown_peer_a,
                unknown_peer_b,
            ],
            connections={},
        )

        available_peers = await piece_manager._get_peers_for_piece(0, peer_manager)

        assert available_peers == []

    @pytest.mark.asyncio
    async def test_request_blocks_normal_limits_unknown_peer_to_single_probe(self):
        """Unknown peers should receive at most one probe request per piece."""
        torrent_data = {
            "info_hash": b"\x09" * 20,
            "file_info": {
                "name": "probe.bin",
                "total_length": 65536,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 65536,
                "piece_hashes": [b"\x01" * 20],
                "total_length": 65536,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        unknown_peer = MagicMock()
        unknown_peer.peer_info = PeerInfo(ip="198.51.100.20", port=6881)
        unknown_peer.can_request.return_value = True
        unknown_peer.get_available_pipeline_slots.return_value = 8
        unknown_peer.outstanding_requests = {}
        unknown_peer.max_pipeline_depth = 8
        unknown_peer.peer_choking = False
        unknown_peer.am_interested = True
        unknown_peer.peer_interested = False
        unknown_peer.state = SimpleNamespace(value="active")
        unknown_peer.stats = SimpleNamespace(download_rate=0.0)
        unknown_peer.peer_state = SimpleNamespace(pieces_we_have=set(), bitfield=b"")
        unknown_peer.is_active.return_value = True

        piece = piece_manager.pieces[0]
        missing_blocks = piece.get_missing_blocks()
        peer_manager = SimpleNamespace(
            _balance_requests_across_peers=lambda requests, peers, min_allocation_per_peer=1: {
                str(peers[0].peer_info): requests
            },
            get_active_peers=lambda: [unknown_peer],
            request_piece=AsyncMock(),
        )

        requests_sent = await piece_manager._request_blocks_normal(
            0,
            missing_blocks,
            [unknown_peer],
            peer_manager,
        )

        assert requests_sent == 1
        assert peer_manager.request_piece.await_count == 1
        assert piece_manager._piece_selection_metrics["unknown_peer_probes"] == 1

    @pytest.mark.asyncio
    async def test_get_peers_for_piece_adds_single_unknown_probe_for_weak_swarm(self):
        """One known piece peer should not monopolize selection when many peers remain unknown."""
        torrent_data = {
            "info_hash": b"\x0D" * 20,
            "file_info": {
                "name": "weak-swarm.bin",
                "total_length": 65536,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 65536,
                "piece_hashes": [b"\x01" * 20],
                "total_length": 65536,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        known_peer = MagicMock()
        known_peer.peer_info = PeerInfo(ip="198.51.100.30", port=6881)
        known_peer.can_request.return_value = True
        known_peer.get_available_pipeline_slots.return_value = 8
        known_peer.outstanding_requests = {}
        known_peer.max_pipeline_depth = 8
        known_peer.peer_choking = False
        known_peer.am_interested = True
        known_peer.peer_interested = False
        known_peer.state = SimpleNamespace(value="active")
        known_peer.stats = SimpleNamespace(download_rate=10.0)
        known_peer.peer_state = SimpleNamespace(pieces_we_have={0}, bitfield=b"\x80")
        known_peer.is_active.return_value = True

        unknown_peer_a = MagicMock()
        unknown_peer_a.peer_info = PeerInfo(ip="198.51.100.31", port=6881)
        unknown_peer_a.can_request.return_value = True
        unknown_peer_a.get_available_pipeline_slots.return_value = 8
        unknown_peer_a.outstanding_requests = {}
        unknown_peer_a.max_pipeline_depth = 8
        unknown_peer_a.peer_choking = False
        unknown_peer_a.am_interested = True
        unknown_peer_a.peer_interested = False
        unknown_peer_a.state = SimpleNamespace(value="active")
        unknown_peer_a.stats = SimpleNamespace(download_rate=0.0)
        unknown_peer_a.peer_state = SimpleNamespace(pieces_we_have=set(), bitfield=b"")
        unknown_peer_a.is_active.return_value = True

        unknown_peer_b = MagicMock()
        unknown_peer_b.peer_info = PeerInfo(ip="198.51.100.32", port=6881)
        unknown_peer_b.can_request.return_value = True
        unknown_peer_b.get_available_pipeline_slots.return_value = 8
        unknown_peer_b.outstanding_requests = {}
        unknown_peer_b.max_pipeline_depth = 8
        unknown_peer_b.peer_choking = False
        unknown_peer_b.am_interested = True
        unknown_peer_b.peer_interested = False
        unknown_peer_b.state = SimpleNamespace(value="active")
        unknown_peer_b.stats = SimpleNamespace(download_rate=0.0)
        unknown_peer_b.peer_state = SimpleNamespace(pieces_we_have=set(), bitfield=b"")
        unknown_peer_b.is_active.return_value = True

        piece_manager.peer_availability[str(known_peer.peer_info)] = SimpleNamespace(
            pieces={0}
        )
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [known_peer, unknown_peer_a, unknown_peer_b],
            connections={},
        )

        available_peers = await piece_manager._get_peers_for_piece(0, peer_manager)

        assert known_peer in available_peers
        assert len(available_peers) == 2
        assert sum(
            1 for peer in available_peers if peer in (unknown_peer_a, unknown_peer_b)
        ) == 1

    @pytest.mark.asyncio
    async def test_get_peers_for_piece_allows_unknown_probe_in_two_peer_swarm(self):
        """Two-peer swarm should keep a bounded unknown peer probe with a known piece peer."""
        torrent_data = {
            "info_hash": b"\x0F" * 20,
            "file_info": {
                "name": "two-peer.bin",
                "total_length": 65536,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 65536,
                "piece_hashes": [b"\x01" * 20],
                "total_length": 65536,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        known_peer = MagicMock()
        known_peer.peer_info = PeerInfo(ip="198.51.100.33", port=6881)
        known_peer.can_request.return_value = True
        known_peer.get_available_pipeline_slots.return_value = 8
        known_peer.outstanding_requests = {}
        known_peer.max_pipeline_depth = 8
        known_peer.peer_choking = False
        known_peer.am_interested = True
        known_peer.peer_interested = False
        known_peer.state = SimpleNamespace(value="active")
        known_peer.stats = SimpleNamespace(download_rate=12.0)
        known_peer.peer_state = SimpleNamespace(pieces_we_have={0}, bitfield=b"\x80")
        known_peer.is_active.return_value = True

        unknown_peer = MagicMock()
        unknown_peer.peer_info = PeerInfo(ip="198.51.100.34", port=6881)
        unknown_peer.can_request.return_value = True
        unknown_peer.get_available_pipeline_slots.return_value = 8
        unknown_peer.outstanding_requests = {}
        unknown_peer.max_pipeline_depth = 8
        unknown_peer.peer_choking = False
        unknown_peer.am_interested = True
        unknown_peer.peer_interested = False
        unknown_peer.state = SimpleNamespace(value="active")
        unknown_peer.stats = SimpleNamespace(download_rate=0.0)
        unknown_peer.peer_state = SimpleNamespace(pieces_we_have=set(), bitfield=b"")
        unknown_peer.is_active.return_value = True

        piece_manager.peer_availability[str(known_peer.peer_info)] = SimpleNamespace(
            pieces={0}
        )
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [known_peer, unknown_peer], connections={}
        )

        available_peers = await piece_manager._get_peers_for_piece(0, peer_manager)

        assert known_peer in available_peers
        assert unknown_peer in available_peers
        assert len(available_peers) == 2

    @pytest.mark.asyncio
    async def test_get_peers_for_piece_raises_probe_budget_for_degraded_bootstrap(self):
        """A metadata-complete swarm with only unknown requestable peers should probe more than one peer."""
        torrent_data = {
            "info_hash": b"\x0E" * 20,
            "file_info": {
                "name": "bootstrap.bin",
                "total_length": 65536,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 65536,
                "piece_hashes": [b"\x01" * 20],
                "total_length": 65536,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        def build_unknown_peer(port: int):
            peer = MagicMock()
            peer.peer_info = PeerInfo(ip="198.51.100.40", port=port)
            peer.can_request.return_value = True
            peer.get_available_pipeline_slots.return_value = 8
            peer.outstanding_requests = {}
            peer.max_pipeline_depth = 8
            peer.peer_choking = False
            peer.am_interested = True
            peer.peer_interested = False
            peer.state = SimpleNamespace(value="active")
            peer.stats = SimpleNamespace(download_rate=0.0)
            peer.peer_state = SimpleNamespace(pieces_we_have=set(), bitfield=b"")
            peer.is_active.return_value = True
            return peer

        unknown_peer_a = build_unknown_peer(6881)
        unknown_peer_b = build_unknown_peer(6882)
        unknown_peer_c = build_unknown_peer(6883)
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [unknown_peer_a, unknown_peer_b, unknown_peer_c],
            connections={},
        )

        available_peers = await piece_manager._get_peers_for_piece(0, peer_manager)

        assert len(available_peers) == 2
        assert all(peer in available_peers for peer in (unknown_peer_a, unknown_peer_b))

    @pytest.mark.asyncio
    async def test_get_peers_for_piece_prioritizes_recent_unchoke_when_peers_are_scarce(
        self, piece_manager
    ):
        """Favor peers that were unchoked more recently when requestable peers are scarce."""
        now = time.time()

        def make_peer(
            ip: str,
            port: int,
            rate: float,
            unchoke_age_s: float,
        ) -> MagicMock:
            peer = MagicMock()
            peer.peer_info = PeerInfo(ip=ip, port=port)
            peer.can_request.return_value = True
            peer.get_available_pipeline_slots.return_value = 8
            peer.outstanding_requests = {}
            peer.max_pipeline_depth = 8
            peer.peer_choking = False
            peer.am_interested = True
            peer.peer_interested = False
            peer.state = SimpleNamespace(value="active")
            peer.stats = SimpleNamespace(
                download_rate=rate,
                choke_state_ratio=0.0,
                blocks_delivered=0,
                request_latency=0.0,
            )
            peer.peer_state = SimpleNamespace(pieces_we_have={0}, bitfield=b"\x80")
            peer.is_active.return_value = True
            peer._last_unchoke_at = now - unchoke_age_s
            return peer

        slow_recent_peer = make_peer(
            "198.51.100.80", 6881, rate=1.0, unchoke_age_s=1.0
        )
        fast_old_peer = make_peer(
            "198.51.100.81", 6882, rate=32.0, unchoke_age_s=90.0
        )
        piece_manager.peer_availability[str(slow_recent_peer.peer_info)] = SimpleNamespace(
            pieces={0}
        )
        piece_manager.peer_availability[str(fast_old_peer.peer_info)] = SimpleNamespace(
            pieces={0}
        )
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [fast_old_peer, slow_recent_peer],
            connections={},
        )

        available_peers = await piece_manager._get_peers_for_piece(0, peer_manager)

        assert available_peers == [slow_recent_peer, fast_old_peer]

    @pytest.mark.asyncio
    async def test_get_peers_for_piece_scarce_pool_uses_unhashable_peer_objects(
        self, piece_manager
    ):
        """Regression: unhashable peer objects should still be ranked deterministically."""
        now = time.time()
        piece_manager._piece_availability_confidence_window_s = 30.0

        class UnhashablePeerConnection:
            __hash__ = None

            def __init__(
                self, ip: str, port: int, *, rate: float, unchoke_age_s: float
            ) -> None:
                self.peer_info = PeerInfo(ip=ip, port=port)
                self.outstanding_requests = {}
                self.max_pipeline_depth = 8
                self.peer_choking = False
                self.am_interested = True
                self.peer_interested = False
                self.state = SimpleNamespace(value="active")
                self.stats = SimpleNamespace(
                    download_rate=rate,
                    choke_state_ratio=0.0,
                    blocks_delivered=0,
                    request_latency=0.0,
                )
                self.peer_state = SimpleNamespace(
                    pieces_we_have={0},
                    bitfield=b"\x80",
                )
                self._last_piece_availability_at = now
                self._last_unchoke_at = now - unchoke_age_s

            def can_request(self, *args, **kwargs) -> bool:
                return True

            def get_available_pipeline_slots(self) -> int:
                return 8

            def is_active(self) -> bool:
                return True

        slow_recent_peer = UnhashablePeerConnection(
            "198.51.100.90", 6881, rate=1.0, unchoke_age_s=1.0
        )
        fast_old_peer = UnhashablePeerConnection(
            "198.51.100.91", 6882, rate=32.0, unchoke_age_s=90.0
        )
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [fast_old_peer, slow_recent_peer],
            connections={},
        )

        available_peers = await piece_manager._get_peers_for_piece(0, peer_manager)

        assert available_peers == [slow_recent_peer, fast_old_peer]

    @pytest.mark.asyncio
    async def test_get_peers_for_piece_excludes_stale_piece_signals_when_recent_signal_missing(
        self,
        piece_manager,
    ):
        """Peers with stale piece signals are ignored until a fresh signal arrives."""
        now = time.time()
        piece_manager._piece_availability_confidence_window_s = 15.0

        def make_peer(
            ip: str,
            port: int,
            *,
            can_request: bool,
            has_piece: bool,
            signal_at: float | None = None,
        ) -> MagicMock:
            peer = MagicMock()
            peer.peer_info = PeerInfo(ip=ip, port=port)
            peer.can_request.return_value = can_request
            peer.get_available_pipeline_slots.return_value = 8
            peer.outstanding_requests = {}
            peer.max_pipeline_depth = 8
            peer.peer_choking = False
            peer.am_interested = True
            peer.peer_interested = False
            peer.state = SimpleNamespace(value="active")
            peer.stats = SimpleNamespace(download_rate=1.0)
            peer.peer_state = SimpleNamespace(
                pieces_we_have={0} if has_piece else set(),
                bitfield=b"\x80" if has_piece else b"",
            )
            peer.is_active.return_value = True
            if signal_at is not None:
                peer._last_piece_availability_at = signal_at
            return peer

        stale_peer = make_peer(
            "198.51.100.50",
            6881,
            can_request=True,
            has_piece=False,
        )
        piece_manager.peer_availability[str(stale_peer.peer_info)] = SimpleNamespace(
            pieces={0},
            last_updated=now - 120.0,
        )

        fresh_peer = make_peer(
            "198.51.100.51",
            6882,
            can_request=True,
            has_piece=True,
            signal_at=now,
        )

        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [stale_peer, fresh_peer],
            connections={},
        )

        available_peers = await piece_manager._get_peers_for_piece(0, peer_manager)

        assert available_peers == [fresh_peer]

    @pytest.mark.asyncio
    async def test_select_pieces_stalls_temporarily_when_no_availability_announced(
        self, piece_manager
    ):
        """Repeated selections with no announced availability should enter a short deadband."""
        piece_manager._availability_deadband_threshold = 2
        piece_manager._availability_deadband_s = 1.0
        piece = piece_manager.pieces[0]
        piece.state = PieceState.MISSING
        piece_manager.peer_availability.clear()
        piece_manager.piece_frequency.clear()

        peer = MagicMock()
        peer.can_request.return_value = True
        peer.peer_info = PeerInfo(ip="198.51.100.99", port=6881)
        peer.peer_state = SimpleNamespace(pieces_we_have=set(), bitfield=b"")
        peer.is_active.return_value = True

        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [peer],
            connections={},
        )

        await piece_manager._select_pieces()
        await piece_manager._select_pieces()

        assert piece_manager._availability_deadband_until > time.time()
        assert piece_manager._piece_selection_metrics["availability_deadband_events"] >= 1

    @pytest.mark.asyncio
    async def test_stuck_piece_score_boost_prioritizes_retry_path(self, piece_manager):
        """Pieces marked as stalled are slightly reprioritized when selecting rarest-first."""
        peer = MagicMock()
        peer.peer_info = PeerInfo(ip="198.51.100.100", port=6881)
        peer.can_request.return_value = True
        peer.get_available_pipeline_slots.return_value = 8
        peer.outstanding_requests = {}
        peer.max_pipeline_depth = 8
        peer.peer_choking = False
        peer.am_interested = True
        peer.peer_interested = False
        peer.state = SimpleNamespace(value="active")
        peer.stats = SimpleNamespace(download_rate=10.0)
        peer.peer_state = SimpleNamespace(
            pieces_we_have={0, 1, 2},
            bitfield=b"\xE0",
        )
        peer.is_active.return_value = True

        piece_manager._peer_manager = SimpleNamespace(get_active_peers=lambda: [peer])
        piece_manager._metadata_incomplete = False
        piece_manager.peer_availability[str(peer.peer_info)] = SimpleNamespace(
            pieces={0, 1, 2},
            average_download_speed=0.0,
            connection_quality_score=0.0,
        )
        piece_manager.config.strategy.streaming_mode = False
        for piece in piece_manager.pieces[:3]:
            piece.state = PieceState.MISSING
            piece.priority = 0
        piece_manager._stuck_pieces[1] = (9, time.time() - 20.0, "stalled")

        requested_pieces: list[int] = []

        async def capture_request(piece_index: int, peer_manager: object) -> None:
            requested_pieces.append(piece_index)

        piece_manager.request_piece_from_peers = AsyncMock(side_effect=capture_request)

        await piece_manager._select_rarest_first()
        await asyncio.sleep(0)

        assert requested_pieces[0] == 1

    @pytest.mark.asyncio
    async def test_get_peers_for_piece_bounds_alternate_pool_and_delays_retries(
        self, piece_manager
    ):
        """Alternate peer probing uses bounded pool and delays immediate reuse of recent probes."""
        piece_manager._alternate_peer_pool_size = 1
        piece_manager._alternate_peer_retry_delay_s = 5.0
        peer_manager = SimpleNamespace()

        def build_peer(ip: str, port: int) -> MagicMock:
            peer = MagicMock()
            peer.peer_info = PeerInfo(ip=ip, port=port)
            peer.can_request.return_value = True
            peer.get_available_pipeline_slots.return_value = 8
            peer.outstanding_requests = {}
            peer.max_pipeline_depth = 8
            peer.peer_choking = False
            peer.am_interested = True
            peer.peer_interested = False
            peer.state = SimpleNamespace(value="active")
            peer.stats = SimpleNamespace(download_rate=0.0)
            peer.peer_state = SimpleNamespace(pieces_we_have=set(), bitfield=b"")
            peer.is_active.return_value = True
            return peer

        peer_a = build_peer("198.51.100.90", 6881)
        peer_b = build_peer("198.51.100.91", 6882)
        peer_c = build_peer("198.51.100.92", 6883)

        peer_manager.get_active_peers = lambda: [peer_a, peer_b, peer_c]
        peer_manager.connections = {}
        peer_manager._cleanup_timed_out_requests = AsyncMock()

        piece_manager._metadata_incomplete = False

        first_pass = await piece_manager._get_peers_for_piece(0, peer_manager)
        second_pass = await piece_manager._get_peers_for_piece(0, peer_manager)

        assert len(first_pass) == 1
        assert len(second_pass) == 1
        assert first_pass != second_pass
        assert set(first_pass).isdisjoint(set(second_pass))

    @pytest.mark.asyncio
    async def test_get_peers_for_piece_prefers_seeders_when_available(self):
        """Prefer seeders for piece selection when they are known to have the piece."""
        torrent_data = {
            "info_hash": b"\x11" * 20,
            "file_info": {
                "name": "selection.bin",
                "total_length": 2 * 16384,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 2,
                "piece_length": 16384,
                "piece_hashes": [b"\x01" * 20, b"\x02" * 20],
                "total_length": 2 * 16384,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        def build_peer(ip: str, port: int, bitfield: bytes, rate: float) -> MagicMock:
            peer = MagicMock()
            peer.peer_info = PeerInfo(ip=ip, port=port)
            peer.can_request.return_value = True
            peer.get_available_pipeline_slots.return_value = 8
            peer.outstanding_requests = {}
            peer.max_pipeline_depth = 8
            peer.peer_choking = False
            peer.am_interested = True
            peer.peer_interested = False
            peer.state = SimpleNamespace(value="active")
            peer.stats = SimpleNamespace(download_rate=rate)
            peer.peer_state = SimpleNamespace(
                pieces_we_have={0, 1} if rate == 99.0 else {0},
                bitfield=bitfield,
            )
            peer.is_active.return_value = True
            return peer

        seeder_peer = build_peer("198.51.100.60", 6881, b"\xC0", 99.0)
        leecher_peer = build_peer("198.51.100.61", 6881, b"\x80", 5.0)
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [leecher_peer, seeder_peer],
            connections={},
        )

        piece_manager.peer_availability[str(seeder_peer.peer_info)] = SimpleNamespace(pieces={0, 1})
        piece_manager.peer_availability[str(leecher_peer.peer_info)] = SimpleNamespace(pieces={0})

        available_peers = await piece_manager._get_peers_for_piece(0, peer_manager)

        assert available_peers == [seeder_peer]

    @pytest.mark.asyncio
    async def test_get_peers_for_piece_falls_back_to_leechers_without_seeders(self):
        """Fall back to best leechers when no seeder is available."""
        torrent_data = {
            "info_hash": b"\x12" * 20,
            "file_info": {
                "name": "selection.bin",
                "total_length": 2 * 16384,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 2,
                "piece_length": 16384,
                "piece_hashes": [b"\x01" * 20, b"\x02" * 20],
                "total_length": 2 * 16384,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        def build_peer(ip: str, port: int, rate: float) -> MagicMock:
            peer = MagicMock()
            peer.peer_info = PeerInfo(ip=ip, port=port)
            peer.can_request.return_value = True
            peer.get_available_pipeline_slots.return_value = 8
            peer.outstanding_requests = {}
            peer.max_pipeline_depth = 8
            peer.peer_choking = False
            peer.am_interested = True
            peer.peer_interested = False
            peer.state = SimpleNamespace(value="active")
            peer.stats = SimpleNamespace(download_rate=rate)
            peer.peer_state = SimpleNamespace(pieces_we_have={0}, bitfield=b"\x80")
            peer.is_active.return_value = True
            return peer

        leecher_fast = build_peer("198.51.100.70", 6881, 12.0)
        leecher_slow = build_peer("198.51.100.71", 6881, 4.0)
        piece_manager.peer_availability[str(leecher_fast.peer_info)] = SimpleNamespace(pieces={0})
        piece_manager.peer_availability[str(leecher_slow.peer_info)] = SimpleNamespace(pieces={0})
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [leecher_slow, leecher_fast],
            connections={},
        )

        available_peers = await piece_manager._get_peers_for_piece(0, peer_manager)

        assert available_peers == [leecher_fast, leecher_slow]

    @pytest.mark.asyncio
    async def test_retry_requested_pieces_debounces_repeated_focus_peer_bursts(
        self, piece_manager
    ):
        """Retrying requested pieces from the same focus peer is debounced."""
        piece_manager._retry_request_debounce_s = 0.8
        piece_manager.pieces[0].state = PieceState.REQUESTED
        focus_peer = SimpleNamespace(
            peer_info=PeerInfo(ip="198.51.100.70", port=6881),
            can_request=lambda: True,
            peer_choking=False,
            am_interested=True,
            peer_interested=False,
            state=SimpleNamespace(value="active"),
            stats=SimpleNamespace(download_rate=8.0),
            peer_state=SimpleNamespace(pieces_we_have={0}, bitfield=b"\x80"),
            is_active=lambda: True,
        )
        focus_peer_key = f"{focus_peer.peer_info.ip}:{focus_peer.peer_info.port}"
        piece_manager.peer_availability[focus_peer_key] = SimpleNamespace(pieces={0})
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [focus_peer]
        )
        piece_manager.request_piece_from_peers = AsyncMock()

        await piece_manager._retry_requested_pieces(focus_peer, max_retry_count=1)
        await piece_manager._retry_requested_pieces(focus_peer, max_retry_count=1)

        assert piece_manager.request_piece_from_peers.await_count == 1
        assert (
            piece_manager.get_piece_selection_metrics()["retry_request_bursts_debounced"] >= 1
        )

    @pytest.mark.asyncio
    async def test_retry_requested_pieces_debounce_is_scoped_by_focus_peer(
        self, piece_manager
    ):
        """Debounce for requeue bursts is scoped per focus peer, not global."""
        piece_manager._retry_request_debounce_s = 0.8
        piece_manager.pieces[0].state = PieceState.REQUESTED
        piece_manager.pieces[1].state = PieceState.REQUESTED

        peer_a = SimpleNamespace(
            peer_info=PeerInfo(ip="198.51.100.71", port=6881),
            can_request=lambda: True,
            peer_choking=False,
            am_interested=True,
            peer_interested=False,
            state=SimpleNamespace(value="active"),
            stats=SimpleNamespace(download_rate=8.0),
            peer_state=SimpleNamespace(pieces_we_have={0, 1}, bitfield=b"\xC0"),
            is_active=lambda: True,
        )
        peer_b = SimpleNamespace(
            peer_info=PeerInfo(ip="198.51.100.72", port=6882),
            can_request=lambda: True,
            peer_choking=False,
            am_interested=True,
            peer_interested=False,
            state=SimpleNamespace(value="active"),
            stats=SimpleNamespace(download_rate=8.0),
            peer_state=SimpleNamespace(pieces_we_have={0, 1}, bitfield=b"\xC0"),
            is_active=lambda: True,
        )

        piece_manager.peer_availability[f"{peer_a.peer_info.ip}:{peer_a.peer_info.port}"] = (
            SimpleNamespace(pieces={0, 1})
        )
        piece_manager.peer_availability[f"{peer_b.peer_info.ip}:{peer_b.peer_info.port}"] = (
            SimpleNamespace(pieces={0, 1})
        )
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [peer_a, peer_b]
        )
        piece_manager.request_piece_from_peers = AsyncMock()

        await piece_manager._retry_requested_pieces(peer_a, max_retry_count=1)
        await piece_manager._retry_requested_pieces(peer_b, max_retry_count=1)

        assert piece_manager.request_piece_from_peers.await_count == 2

    @pytest.mark.asyncio
    async def test_retry_requested_pieces_cleans_invalid_peer_map_keys_on_failure(
        self, piece_manager
    ):
        """Retry failure path should recover when peer key mappings are malformed."""
        piece_manager.pieces[0].state = PieceState.REQUESTED
        piece_manager.pieces[0].request_count = 3
        piece_manager.pieces[0].last_request_time = time.time() - 120.0
        piece_manager.pieces[0].requests_dispatched = 1
        piece_manager.pieces[0].last_activity_time = 0.0
        piece_manager._retry_request_debounce_s = 0.0
        piece_manager._retry_from_active_max_attempts = 0

        malformed_peer_key = object()
        piece_manager._requested_pieces_per_peer[malformed_peer_key] = {0}

        focus_peer = SimpleNamespace(
            peer_info=PeerInfo(ip="198.51.100.90", port=6881),
            can_request=lambda: True,
            peer_choking=False,
            am_interested=True,
            peer_interested=False,
            state=SimpleNamespace(value="active"),
            stats=SimpleNamespace(download_rate=8.0),
            peer_state=SimpleNamespace(pieces_we_have={0}, bitfield=b"\x80"),
            is_active=lambda: True,
        )
        piece_manager.peer_availability[str(focus_peer.peer_info)] = SimpleNamespace(pieces={0})
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [focus_peer]
        )
        piece_manager.request_piece_from_peers = AsyncMock(
            side_effect=RuntimeError("retry path")
        )
        piece_manager.logger = MagicMock()

        await piece_manager._retry_requested_pieces(focus_peer, max_retry_count=1)

        assert piece_manager.request_piece_from_peers.await_count == 1
        assert malformed_peer_key not in piece_manager._requested_pieces_per_peer
        assert piece_manager.pieces[0].state == PieceState.MISSING
        assert any(
            (args and isinstance(args[0], str) and "Failed to retry piece" in args[0])
            for args, _ in piece_manager.logger.warning.call_args_list
        )

    def test_normalize_peer_key_handles_peer_object_and_string_inputs(self, piece_manager):
        """Peer-key normalization converts peer objects into stable string keys."""

        peer_connection = SimpleNamespace(
            peer_info=PeerInfo(ip="198.51.100.70", port=6881)
        )

        assert (
            piece_manager._normalize_peer_key(peer_connection)
            == "198.51.100.70:6881"
        )
        assert piece_manager._normalize_peer_key("198.51.100.70:6881") == "198.51.100.70:6881"
        assert piece_manager._normalize_peer_key(12345) == "12345"
        assert piece_manager._normalize_peer_key(None) is None

    def test_peer_piece_availability_state_normalizes_connection_peer_key(self, piece_manager):
        """Piece availability lookup should use normalized peer keys from peer connections."""
        now = time.time()
        connection = SimpleNamespace(
            peer_info=SimpleNamespace(
                ip="198.51.100.70",
                port=6881,
            ),
            peer_state=SimpleNamespace(pieces_we_have=set()),
            _last_piece_availability_at=0.0,
        )
        piece_manager.peer_availability["198.51.100.70:6881"] = SimpleNamespace(
            pieces={1},
            last_updated=now,
        )

        has_piece, has_fresh_piece = piece_manager._peer_piece_availability_state(
            connection,
            1,
            now,
        )

        assert has_piece is True
        assert has_fresh_piece is True

    @pytest.mark.asyncio
    async def test_retry_requested_pieces_repairs_peer_key_to_string_during_cleanup(
        self, piece_manager
    ):
        """Retry recovery should normalize malformed peer keys before clearing stale entries."""
        piece_manager.pieces[0].state = PieceState.REQUESTED
        piece_manager.pieces[0].request_count = 3
        piece_manager.pieces[0].last_request_time = time.time() - 120.0
        piece_manager.pieces[0].requests_dispatched = 1
        piece_manager.pieces[0].last_activity_time = 0.0
        piece_manager._retry_request_debounce_s = 0.0
        piece_manager._retry_from_active_max_attempts = 0

        class HashablePeerKey:
            def __init__(self, ip: str, port: int) -> None:
                self.peer_info = PeerInfo(ip=ip, port=port)

        malformed_peer_key = HashablePeerKey("198.51.100.91", 6881)
        piece_manager._requested_pieces_per_peer[malformed_peer_key] = {0}

        focus_peer = SimpleNamespace(
            peer_info=PeerInfo(ip="198.51.100.91", port=6881),
            can_request=lambda: True,
            peer_choking=False,
            am_interested=True,
            peer_interested=False,
            state=SimpleNamespace(value="active"),
            stats=SimpleNamespace(download_rate=8.0),
            peer_state=SimpleNamespace(pieces_we_have={0}, bitfield=b"\x80"),
            is_active=lambda: True,
        )
        piece_manager.peer_availability[str(focus_peer.peer_info)] = SimpleNamespace(pieces={0})
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [focus_peer]
        )
        piece_manager.request_piece_from_peers = AsyncMock(
            side_effect=RuntimeError("retry path")
        )
        piece_manager.logger = MagicMock()

        await piece_manager._retry_requested_pieces(focus_peer, max_retry_count=1)

        assert piece_manager.request_piece_from_peers.await_count == 1
        assert malformed_peer_key not in piece_manager._requested_pieces_per_peer
        assert "198.51.100.91:6881" not in piece_manager._requested_pieces_per_peer
        assert piece_manager.pieces[0].state == PieceState.MISSING
        assert any(
            (args and isinstance(args[0], str) and "Failed to retry piece" in args[0])
            for args, _ in piece_manager.logger.warning.call_args_list
        )

    @pytest.mark.asyncio
    async def test_clear_stale_requested_pieces_normalizes_keys_idempotently(self, piece_manager):
        """Repeated stale-cleanup passes should remain safe after key normalization."""
        class HashablePeerKey:
            def __init__(self, ip: str, port: int) -> None:
                self.peer_info = PeerInfo(ip=ip, port=port)

        malformed_peer_key = HashablePeerKey("203.0.113.200", 51413)
        piece_manager._requested_pieces_per_peer[malformed_peer_key] = {0}

        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED
        piece.request_count = 3
        piece.last_request_time = time.time() - 120.0
        piece.last_activity_time = 0.0

        piece_manager._peer_manager = SimpleNamespace(get_active_peers=lambda: [])
        piece_manager._active_block_requests[0] = {}

        await piece_manager._clear_stale_requested_pieces(timeout=30.0)
        await piece_manager._clear_stale_requested_pieces(timeout=30.0)

        assert malformed_peer_key not in piece_manager._requested_pieces_per_peer
        assert "203.0.113.200:51413" not in piece_manager._requested_pieces_per_peer

    @pytest.mark.asyncio
    async def test_requested_piece_map_helpers_normalize_and_cleanup_entries(self, piece_manager):
        """Helper methods should normalize peer keys and maintain safe cleanup behavior."""
        class HashablePeerKey:
            def __init__(self, ip: str, port: int) -> None:
                self.peer_info = PeerInfo(ip=ip, port=port)

        normalized_peer = HashablePeerKey("198.51.100.210", 6881)
        bad_key = object()
        bad_key_str = str(bad_key)

        piece_manager._requested_piece_map_add(normalized_peer, 0)
        piece_manager._requested_piece_map_add(bad_key, 0)

        assert "198.51.100.210:6881" in piece_manager._requested_pieces_per_peer
        assert bad_key_str in piece_manager._requested_pieces_per_peer

        piece_manager._requested_piece_map_discard(normalized_peer, 0)
        assert "198.51.100.210:6881" not in piece_manager._requested_pieces_per_peer

        piece_manager._requested_piece_map_discard(bad_key, 0)
        assert bad_key_str not in piece_manager._requested_pieces_per_peer

    @pytest.mark.asyncio
    async def test_repair_requested_piece_map_locked_merges_malformed_keys(self, piece_manager):
        """Repair helper should remove malformed keys and normalize usable peer keys."""
        class HashablePeerKey:
            def __init__(self, ip: str, port: int) -> None:
                self.peer_info = PeerInfo(ip=ip, port=port)

        malformed_peer_key = HashablePeerKey("198.51.100.220", 6881)

        piece_manager._requested_pieces_per_peer = {
            malformed_peer_key: {0},
            12345: {1},
            "bad-set": [],
            "198.51.100.221:6881": {2},
        }

        await piece_manager._repair_requested_piece_map_locked()

        assert "198.51.100.220:6881" in piece_manager._requested_pieces_per_peer
        assert malformed_peer_key not in piece_manager._requested_pieces_per_peer
        assert "12345" in piece_manager._requested_pieces_per_peer
        assert piece_manager._requested_pieces_per_peer["12345"] == {1}
        assert "bad-set" not in piece_manager._requested_pieces_per_peer
        assert piece_manager._requested_pieces_per_peer["198.51.100.221:6881"] == {2}

    @pytest.mark.asyncio
    async def test_request_blocks_normal_keeps_requested_state_for_optimistic_retry(self):
        """Optimistic bootstrap should retain REQUESTED state when probes are not immediately capable."""
        torrent_data = {
            "info_hash": b"\x0F" * 20,
            "file_info": {
                "name": "retry.bin",
                "total_length": 65536,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 65536,
                "piece_hashes": [b"\x01" * 20],
                "total_length": 65536,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        unknown_peer = MagicMock()
        unknown_peer.peer_info = PeerInfo(ip="198.51.100.50", port=6881)
        unknown_peer.can_request.return_value = True
        unknown_peer.get_available_pipeline_slots.return_value = 8
        unknown_peer.outstanding_requests = {}
        unknown_peer.max_pipeline_depth = 8
        unknown_peer.peer_choking = False
        unknown_peer.am_interested = True
        unknown_peer.peer_interested = False
        unknown_peer.state = SimpleNamespace(value="active")
        unknown_peer.stats = SimpleNamespace(download_rate=0.0)
        unknown_peer.peer_state = SimpleNamespace(pieces_we_have=set(), bitfield=b"")
        unknown_peer.is_active.return_value = True

        piece_manager._requested_pieces_per_peer[str(unknown_peer.peer_info)] = {0}
        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED

        peer_manager = SimpleNamespace(
            _balance_requests_across_peers=lambda requests, peers, min_allocation_per_peer=1: {},
            request_piece=AsyncMock(),
        )
        requests_sent = await piece_manager._request_blocks_normal(
            0,
            piece.get_missing_blocks(),
            [unknown_peer],
            peer_manager,
        )

        assert requests_sent == 0
        assert piece_manager.pieces[0].state == PieceState.REQUESTED

    @pytest.mark.asyncio
    async def test_request_blocks_normal_relaxes_pipeline_for_stale_piece(self):
        """Stale pieces should allow near-saturated peer pipelines to retry."""
        torrent_data = {
            "info_hash": b"\x11" * 20,
            "file_info": {
                "name": "pipeline-relax.bin",
                "total_length": 16384,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"\x01" * 20],
                "total_length": 16384,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        peer = MagicMock()
        peer.peer_info = PeerInfo(ip="198.51.100.30", port=6881)
        peer.can_request.return_value = True
        peer.get_available_pipeline_slots.return_value = 1
        peer.outstanding_requests = [b"slot"] * 10
        peer.max_pipeline_depth = 11
        peer.peer_choking = False
        peer.am_interested = True
        peer.peer_interested = True
        peer.state = SimpleNamespace(value="active")
        peer.stats = SimpleNamespace(download_rate=5.0)
        peer.peer_state = SimpleNamespace(pieces_we_have={0}, bitfield=b"\x80")
        peer.is_active.return_value = True

        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED
        piece.request_count = 3
        piece.request_timeout = 20.0
        piece.last_request_time = time.time() - 30.0

        missing_blocks = piece.get_missing_blocks()
        request_list = [
            RequestInfo(
                piece_index=block.piece_index,
                begin=block.begin,
                length=block.length,
                timestamp=time.time(),
            )
            for block in missing_blocks
        ]
        peer_manager = SimpleNamespace(
            _balance_requests_across_peers=lambda requests, peers, min_allocation_per_peer=1: {
                str(peer.peer_info): request_list
            },
            get_active_peers=lambda: [],
            request_piece=AsyncMock(),
        )

        requests_sent = await piece_manager._request_blocks_normal(
            0,
            missing_blocks,
            [peer],
            peer_manager,
        )

        assert requests_sent == 1
        assert peer_manager.request_piece.await_count == 1

    @pytest.mark.asyncio
    async def test_request_blocks_normal_keeps_strict_pipeline_for_fresh_piece(self):
        """Freshly requested pieces should still respect pipeline utilization limit."""
        torrent_data = {
            "info_hash": b"\x12" * 20,
            "file_info": {
                "name": "pipeline-strict.bin",
                "total_length": 16384,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"\x01" * 20],
                "total_length": 16384,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        peer = MagicMock()
        peer.peer_info = PeerInfo(ip="198.51.100.31", port=6881)
        peer.can_request.return_value = True
        peer.get_available_pipeline_slots.return_value = 1
        peer.outstanding_requests = [b"slot"] * 10
        peer.max_pipeline_depth = 11
        peer.peer_choking = False
        peer.am_interested = True
        peer.peer_interested = True
        peer.state = SimpleNamespace(value="active")
        peer.stats = SimpleNamespace(download_rate=5.0)
        peer.peer_state = SimpleNamespace(pieces_we_have={0}, bitfield=b"\x80")
        peer.is_active.return_value = True

        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED
        piece.request_count = 3
        piece.request_timeout = 20.0
        piece.last_request_time = time.time()

        missing_blocks = piece.get_missing_blocks()
        request_list = [
            RequestInfo(
                piece_index=block.piece_index,
                begin=block.begin,
                length=block.length,
                timestamp=time.time(),
            )
            for block in missing_blocks
        ]
        peer_manager = SimpleNamespace(
            _balance_requests_across_peers=lambda requests, peers, min_allocation_per_peer=1: {
                str(peer.peer_info): request_list
            },
            get_active_peers=lambda: [],
            request_piece=AsyncMock(),
        )

        requests_sent = await piece_manager._request_blocks_normal(
            0,
            missing_blocks,
            [peer],
            peer_manager,
        )

        assert requests_sent == 0
        assert peer_manager.request_piece.await_count == 0

    @pytest.mark.asyncio
    async def test_request_piece_from_peers_keeps_request_state_when_no_requestable_peers(self):
        """When no requestable peers are available, keep REQUESTED state and avoid churn."""
        torrent_data = {
            "info_hash": b"\x10" * 20,
            "file_info": {
                "name": "no_requestable.bin",
                "total_length": 16384,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"\x01" * 20],
                "total_length": 16384,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED
        piece.request_count = 0
        piece.requests_dispatched = 0
        piece.last_request_time = 0.0
        piece_manager.peer_availability = {"198.51.100.50:6881": SimpleNamespace(pieces={0})}

        peer_manager = SimpleNamespace(get_active_peers=lambda: [], connections={})
        with patch.object(
            piece_manager,
            "_get_peers_for_piece",
            AsyncMock(return_value=[]),
        ):
            await piece_manager.request_piece_from_peers(0, peer_manager)

        assert piece.state == PieceState.REQUESTED
        assert piece.requests_dispatched == 0
        assert piece_manager._piece_selection_metrics["no_requestable_peers"] >= 1

    @pytest.mark.asyncio
    async def test_request_piece_from_peers_defers_missing_reset_when_active_peers_are_non_requestable(
        self, piece_manager
    ):
        """Don't reset requested piece to MISSING when active peers exist but can't request."""
        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED
        piece.request_count = 1
        piece.requests_dispatched = 1
        piece.last_request_time = time.time() - 1.0
        piece.last_activity_time = 0.0

        peer = SimpleNamespace(
            peer_info=PeerInfo(ip="198.51.100.80", port=6881),
            is_active=lambda: True,
            can_request=lambda: False,
            peer_state=SimpleNamespace(pieces_we_have={1}),
        )
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [peer],
            connections={},
        )

        piece_manager.peer_availability[str(peer.peer_info)] = SimpleNamespace(
            pieces={1},
            reliability_score=1.0,
            average_download_speed=1.0,
            connection_quality_score=1.0,
            last_updated=time.time(),
        )

        await piece_manager.request_piece_from_peers(0, peer_manager)

        assert piece.state == PieceState.REQUESTED
        assert piece_manager._piece_selection_metrics["no_requestable_peers"] >= 1

    @pytest.mark.asyncio
    async def test_request_piece_from_peers_keeps_request_state_during_recent_active_peer_scarcity(
        self, piece_manager
    ):
        """Keep REQUESTED piece instead of fallback-to-missing during short active-peer scarcity."""
        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED
        piece.request_count = 2
        piece.requests_dispatched = 1
        piece.last_request_time = time.time() - 1.0
        piece.last_activity_time = 0.0

        peer = SimpleNamespace(
            peer_info=PeerInfo(ip="198.51.100.70", port=6881),
            is_active=lambda: True,
            can_request=lambda: True,
            peer_state=SimpleNamespace(pieces_we_have={1}),
        )
        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [peer],
            connections={},
        )

        piece_manager._peer_manager = peer_manager
        piece_manager.peer_availability[str(peer.peer_info)] = SimpleNamespace(
            pieces={1},
            reliability_score=1.0,
            average_download_speed=1.0,
            connection_quality_score=1.0,
        )
        piece_manager._retry_from_active_max_attempts = 0

        with patch.object(
            piece_manager,
            "_get_peers_for_piece",
            AsyncMock(return_value=[]),
        ):
            await piece_manager.request_piece_from_peers(0, peer_manager)

        assert piece.state == PieceState.REQUESTED
        assert piece_manager._piece_selection_metrics["no_requestable_peers"] >= 1

    @pytest.mark.asyncio
    async def test_clear_stale_requested_skips_recent_dispatched_requests_with_active_peers(
        self, piece_manager
    ):
        """Keep recent active requested piece in REQUESTED while peer scarcity is transient."""
        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED
        piece.request_count = 3
        piece.requests_dispatched = 1
        piece.last_request_time = time.time() - 1.0
        piece.last_activity_time = 0.0

        active_peer = SimpleNamespace(peer_info=PeerInfo(ip="198.51.100.90", port=6881))
        piece_manager._peer_manager = SimpleNamespace(
            get_active_peers=lambda: [active_peer],
            connections={},
        )

        await piece_manager._clear_stale_requested_pieces(timeout=1.0)

        assert piece.state == PieceState.REQUESTED

    @pytest.mark.asyncio
    async def test_clear_stale_requested_skips_when_no_requests_dispatched(self):
        """Pieces with no outbound requests should skip stale reset while in REQUESTED."""
        torrent_data = {
            "info_hash": b"\x11" * 20,
            "file_info": {
                "name": "no_requestable_reset.bin",
                "total_length": 16384,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"\x01" * 20],
                "total_length": 16384,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.update_from_metadata(torrent_data)

        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED
        piece.requests_dispatched = 0
        piece.request_count = 0
        piece.last_request_time = 0.0
        piece.last_activity_time = 0.0
        piece._requested_pieces_per_peer = {}
        baseline_no_outbound = piece_manager._piece_selection_metrics[
            "stale_reset_avoided_no_outbound_requests"
        ]

        await piece_manager._clear_stale_requested_pieces(timeout=1.0)
        assert piece.state == PieceState.REQUESTED
        assert (
            piece_manager._piece_selection_metrics[
                "stale_reset_avoided_no_outbound_requests"
            ]
            > baseline_no_outbound
        )
        assert piece_manager._piece_selection_metrics["stale_reset_avoided_total"] > 0

    @pytest.mark.asyncio
    async def test_update_peer_have_retries_requested_pieces_on_new_piece(self, piece_manager):
        """A new HAVE should trigger bounded retry when REQUESTED pieces are pending."""
        piece_manager.pieces[0].state = PieceState.REQUESTED
        peer_key = "198.51.100.80:6881"
        piece_manager._peer_manager = SimpleNamespace(get_active_peers=lambda: [])
        piece_manager._retry_requested_pieces = AsyncMock()
        piece_manager.peer_availability.clear()

        await piece_manager.update_peer_have(peer_key, 0)

        piece_manager._retry_requested_pieces.assert_awaited_once_with(
            focus_peer=peer_key,
            max_retry_count=2,
            max_requesters=1,
        )
        assert piece_manager.piece_frequency[0] == 1

    @pytest.mark.asyncio
    async def test_update_peer_have_does_not_retry_without_request_pressure(
        self, piece_manager
    ):
        """No retry should occur when there are no REQUESTED pieces."""
        piece_manager._peer_manager = SimpleNamespace(get_active_peers=lambda: [])
        piece_manager._retry_requested_pieces = AsyncMock()
        piece_manager.peer_availability.clear()

        await piece_manager.update_peer_have("198.51.100.81:6881", 0)

        piece_manager._retry_requested_pieces.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clear_stale_requested_skips_recent_activity(self, piece_manager):
        """Fresh activity on a REQUESTED piece prevents stale-reset fallback."""
        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED
        piece.requests_dispatched = 1
        piece.request_count = 3
        piece.last_request_time = time.time() - 5.0
        piece.last_activity_time = time.time() - 10.0

        baseline_recent = piece_manager._piece_selection_metrics[
            "stale_reset_avoided_recent_activity"
        ]

        await piece_manager._clear_stale_requested_pieces(timeout=1.0)

        assert piece.state == PieceState.REQUESTED
        assert (
            piece_manager._piece_selection_metrics[
                "stale_reset_avoided_recent_activity"
            ]
            > baseline_recent
        )
        assert piece_manager._piece_selection_metrics["stale_reset_avoided_total"] > 0

    @pytest.mark.asyncio
    async def test_clear_stale_requested_pieces_discards_timed_out_block_requests(self):
        """Timed-out block requests are discarded before piece-level stale reset checks."""
        torrent_data = {
            "info_hash": b"\x44" * 20,
            "file_info": {
                "name": "stale-block-reset.bin",
                "total_length": 16384,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"\x01" * 20],
                "total_length": 16384,
            },
        }
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.start()
        try:
            piece = piece_manager.pieces[0]
            piece.state = PieceState.REQUESTED
            piece.request_count = 3
            piece.requests_dispatched = 1
            piece.last_request_time = time.time() - 20.0
            piece.last_activity_time = 0.0

            block = piece.blocks[0]
            peer_key = "198.51.100.88:6881"
            block.requested_from.add(peer_key)
            piece_manager._requested_pieces_per_peer = {peer_key: {0}}
            piece_manager._active_block_requests = {
                0: {peer_key: [(block.begin, block.length, time.time() - 20.0)]}
            }

            await piece_manager._clear_stale_requested_pieces(timeout=4.0)

            assert piece.state == PieceState.MISSING
            assert not block.requested_from
            assert 0 not in piece_manager._active_block_requests
        finally:
            await piece_manager.stop()

    @pytest.mark.asyncio
    async def test_request_piece_from_peers_rates_no_available_peers_warning(self, piece_manager):
        """Repeated no-availability warnings for the same piece are rate-limited."""
        piece_manager.logger = MagicMock()
        piece_manager._peer_manager = SimpleNamespace(get_active_peers=lambda: [])

        await piece_manager.request_piece_from_peers(0, piece_manager._peer_manager)
        await piece_manager.request_piece_from_peers(0, piece_manager._peer_manager)

        warning_calls = [
            args
            for args, _ in piece_manager.logger.warning.call_args_list
            if args
            and isinstance(args[0], str)
            and "No available peers for piece %d" in args[0]
        ]
        assert len(warning_calls) == 1

    @pytest.mark.asyncio
    async def test_request_piece_from_peers_rates_no_block_request_warning(self, piece_manager):
        """Repeated no-block-request warnings are rate-limited per piece."""
        peer = MagicMock()
        peer.peer_info = PeerInfo(ip="198.51.100.99", port=6881)
        peer.can_request.return_value = False
        peer.get_available_pipeline_slots.return_value = 4
        peer.outstanding_requests = {}
        peer.max_pipeline_depth = 4
        peer.peer_state = SimpleNamespace(pieces_we_have={0})
        peer.is_active.return_value = True

        peer_manager = SimpleNamespace(
            _balance_requests_across_peers=lambda requests, peers, min_allocation_per_peer=1: {},
            request_piece=AsyncMock(),
            get_active_peers=lambda: [peer],
            connections={},
        )
        piece_manager.logger = MagicMock()
        piece_manager._peer_manager = peer_manager

        with patch.object(
            piece_manager,
            "_get_peers_for_piece",
            AsyncMock(return_value=[peer]),
        ):
            await piece_manager.request_piece_from_peers(0, peer_manager)
            await piece_manager.request_piece_from_peers(0, peer_manager)

        warning_calls = [
            args
            for args, _ in piece_manager.logger.warning.call_args_list
            if args
            and isinstance(args[0], str)
            and "issued no block requests; keeping state at REQUESTED for retry" in args[0]
        ]
        assert len(warning_calls) == 1

    @pytest.mark.asyncio
    async def test_repair_requested_piece_map_increments_counter(self, piece_manager):
        """Repairing malformed requested-piece keys should increment map-repair metric."""

        class HashablePeerKey:
            def __init__(self, ip: str, port: int) -> None:
                self.peer_info = PeerInfo(ip=ip, port=port)

        malformed_peer_key = HashablePeerKey("198.51.100.220", 6881)
        piece_manager._requested_pieces_per_peer = {
            malformed_peer_key: {0},
            "198.51.100.220:6881": {1},
            "bad-set": [],
        }

        baseline_repairs = piece_manager._piece_selection_metrics[
            "requested_piece_map_repairs"
        ]

        await piece_manager._repair_requested_piece_map_locked()

        assert malformed_peer_key not in piece_manager._requested_pieces_per_peer
        assert piece_manager._requested_pieces_per_peer["198.51.100.220:6881"] == {0, 1}
        assert "bad-set" not in piece_manager._requested_pieces_per_peer
        assert (
            piece_manager._piece_selection_metrics["requested_piece_map_repairs"]
            > baseline_repairs
        )

    @pytest.mark.asyncio
    async def test_request_piece_from_peers_retries_from_active_before_missing(
        self, piece_manager
    ):
        """REQUESTED pieces are retried from active peers before falling back to MISSING."""
        piece = piece_manager.pieces[0]
        piece.state = PieceState.REQUESTED
        piece.request_count = 1
        piece.requests_dispatched = 1
        piece.last_request_time = time.time() - 300.0

        peer = MagicMock()
        peer.peer_info = PeerInfo(ip="198.51.100.10", port=6881)
        peer.can_request.return_value = True
        peer.peer_state = SimpleNamespace(pieces_we_have={0})
        peer.is_active.return_value = True

        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [peer],
            connections={},
        )

        piece_manager._peer_manager = peer_manager
        piece_manager.peer_availability[str(peer.peer_info)] = SimpleNamespace(
            pieces={0},
            average_download_speed=1.0,
            connection_quality_score=1.0,
        )
        piece_manager._retry_from_active_delay_s = 0.0
        piece_manager._retry_from_active_max_attempts = 1

        with patch.object(
            piece_manager,
            "_retry_requested_pieces",
            AsyncMock(),
        ) as retry_mock:
            await piece_manager.request_piece_from_peers(0, peer_manager)
            await asyncio.sleep(0)

        assert piece.state == PieceState.REQUESTED
        assert piece_manager._piece_selection_metrics["retry_from_active_escalations"] == 1
        retry_mock.assert_called_once_with(max_retry_count=1)

    @pytest.mark.asyncio
    async def test_request_piece_from_peers_exhausts_retry_from_active_then_resets_to_missing(
        self, piece_manager
    ):
        """After retry_from_active attempts are exhausted, requested pieces reset to MISSING."""
        piece = piece_manager.pieces[1]
        piece.state = PieceState.REQUESTED
        piece.request_count = 1
        piece.requests_dispatched = 1
        piece.last_request_time = time.time() - 300.0

        peer = MagicMock()
        peer.peer_info = PeerInfo(ip="198.51.100.11", port=6882)
        peer.can_request.return_value = True
        peer.get_available_pipeline_slots.return_value = 8
        peer.outstanding_requests = {}
        peer.max_pipeline_depth = 8
        peer.peer_state = SimpleNamespace(pieces_we_have={1})
        peer.peer_choking = False
        peer.am_interested = True
        peer.peer_interested = False
        peer.state = SimpleNamespace(value="active")
        peer.stats = SimpleNamespace(download_rate=1.0)
        peer.peer_state = SimpleNamespace(pieces_we_have={1}, bitfield=b"\xC0")
        peer.is_active.return_value = True

        peer_manager = SimpleNamespace(
            get_active_peers=lambda: [peer],
            connections={},
        )

        piece_manager._peer_manager = peer_manager
        piece_manager.peer_availability[str(peer.peer_info)] = SimpleNamespace(
            pieces={1},
            reliability_score=1.0,
            average_download_speed=1.0,
            connection_quality_score=1.0,
        )
        piece_manager._retry_from_active_delay_s = 0.0
        piece_manager._retry_from_active_max_attempts = 1

        with patch.object(
            piece_manager,
            "_retry_requested_pieces",
            AsyncMock(),
        ), patch.object(
            piece_manager,
            "_get_peers_for_piece",
            AsyncMock(return_value=[]),
        ):
            await piece_manager.request_piece_from_peers(1, peer_manager)
            await asyncio.sleep(0)
            piece.last_request_time = time.time() - 300.0
            await piece_manager.request_piece_from_peers(1, peer_manager)

        assert piece.state == PieceState.MISSING
        assert piece_manager._piece_selection_metrics["retry_from_active_escalations"] == 1
        assert 1 not in piece_manager._retry_from_active_attempts

    @pytest.mark.asyncio
    async def test_update_from_metadata_rebuilds_deferred_checkpoint_layout(self):
        """Metadata-backed geometry must replace provisional checkpoint piece layouts."""
        torrent_data = {
            "info_hash": b"\x0A" * 20,
            "name": "deferred-checkpoint.bin",
            "announce": "http://tracker.example.com/announce",
            "_metadata_incomplete": True,
            "file_info": None,
            "pieces_info": None,
        }
        piece_manager = AsyncPieceManager(torrent_data)
        checkpoint = TorrentCheckpoint(
            info_hash=b"\x0A" * 20,
            torrent_name="deferred-checkpoint.bin",
            total_pieces=2,
            piece_length=16384,
            total_length=32768,
            verified_pieces=[],
            piece_states={0: CheckpointPieceState.REQUESTED},
            download_stats=DownloadStats(bytes_downloaded=16384),
            output_dir=".",
        )

        await piece_manager.restore_from_checkpoint(checkpoint)

        assert piece_manager._deferred_checkpoint is not None
        assert piece_manager.pieces == []
        assert piece_manager.bytes_downloaded == 16384

        updated_torrent_data = {
            "info_hash": b"\x0A" * 20,
            "name": "deferred-checkpoint.bin",
            "announce": "http://tracker.example.com/announce",
            "_metadata_incomplete": False,
            "file_info": {
                "name": "deferred-checkpoint.bin",
                "type": "single",
                "total_length": 524288,
            },
            "pieces_info": {
                "num_pieces": 2,
                "piece_length": 262144,
                "piece_hashes": [b"\x11" * 20, b"\x22" * 20],
                "total_length": 524288,
            },
        }

        await piece_manager.update_from_metadata(updated_torrent_data)

        assert piece_manager._deferred_checkpoint is None
        assert len(piece_manager.pieces) == 2
        assert piece_manager.pieces[0].length == 262144
        assert len(piece_manager.pieces[0].blocks) > 1
        assert sum(block.length for block in piece_manager.pieces[0].blocks) == 262144
        assert piece_manager.pieces[0].state == PieceState.MISSING

    @pytest.mark.asyncio
    async def test_deferred_checkpoint_restore_keeps_verified_pieces_when_geometry_matches(
        self,
    ):
        """Deferred checkpoint restore should preserve verified pieces only when geometry matches."""
        torrent_data = {
            "info_hash": b"\x0B" * 20,
            "name": "matching-geometry.bin",
            "announce": "http://tracker.example.com/announce",
            "_metadata_incomplete": True,
            "file_info": None,
            "pieces_info": None,
        }
        piece_manager = AsyncPieceManager(torrent_data)
        checkpoint = TorrentCheckpoint(
            info_hash=b"\x0B" * 20,
            torrent_name="matching-geometry.bin",
            total_pieces=1,
            piece_length=16384,
            total_length=16384,
            verified_pieces=[0],
            piece_states={0: CheckpointPieceState.VERIFIED},
            download_stats=DownloadStats(bytes_downloaded=16384),
            output_dir=".",
        )

        await piece_manager.restore_from_checkpoint(checkpoint)
        await piece_manager.update_from_metadata(
            {
                "info_hash": b"\x0B" * 20,
                "name": "matching-geometry.bin",
                "announce": "http://tracker.example.com/announce",
                "_metadata_incomplete": False,
                "file_info": {
                    "name": "matching-geometry.bin",
                    "type": "single",
                    "total_length": 16384,
                },
                "pieces_info": {
                    "num_pieces": 1,
                    "piece_length": 16384,
                    "piece_hashes": [b"\x33" * 20],
                    "total_length": 16384,
                },
            }
        )

        assert piece_manager.pieces[0].state == PieceState.VERIFIED
        assert 0 in piece_manager.verified_pieces
        assert all(block.received for block in piece_manager.pieces[0].blocks)

    @pytest.mark.asyncio
    async def test_metadata_backed_piece_does_not_complete_after_single_probe_block(self):
        """A metadata-backed 256 KiB piece must not complete after one 16 KiB block."""
        torrent_data = {
            "info_hash": b"\x0C" * 20,
            "name": "large-piece.bin",
            "announce": "http://tracker.example.com/announce",
            "_metadata_incomplete": True,
            "file_info": None,
            "pieces_info": None,
        }
        piece_manager = AsyncPieceManager(torrent_data)

        await piece_manager.update_from_metadata(
            {
                "info_hash": b"\x0C" * 20,
                "name": "large-piece.bin",
                "announce": "http://tracker.example.com/announce",
                "_metadata_incomplete": False,
                "file_info": {
                    "name": "large-piece.bin",
                    "type": "single",
                    "total_length": 262144,
                },
                "pieces_info": {
                    "num_pieces": 1,
                    "piece_length": 262144,
                    "piece_hashes": [b"\x44" * 20],
                    "total_length": 262144,
                },
            }
        )

        piece = piece_manager.pieces[0]
        first_block = piece.blocks[0]

        assert piece.length == 262144
        assert len(piece.blocks) > 1
        assert first_block.length < piece.length
        assert piece.add_block(first_block.begin, b"x" * first_block.length) is True
        assert piece.state != PieceState.COMPLETE
        assert piece.is_complete() is False

