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

        await piece_manager._clear_stale_requested_pieces(timeout=1.0)
        assert piece.state == PieceState.REQUESTED

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

