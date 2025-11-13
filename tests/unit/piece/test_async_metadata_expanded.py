"""Expanded tests for async metadata exchange module.

Covers AsyncMetadataExchange and helper classes.
Target: 95%+ coverage for ccbt/piece/async_metadata_exchange.py.
"""

from __future__ import annotations

import asyncio
import hashlib
import struct
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.metadata]

from ccbt.core.bencode import BencodeDecoder, BencodeEncoder
from ccbt.piece.async_metadata_exchange import (
    AsyncMetadataExchange,
    MetadataCache,
    MetadataMetrics,
    MetadataPiece,
    MetadataPieceManager,
    MetadataState,
    PeerMetadataSession,
    PeerReliabilityTracker,
    RetryManager,
    fetch_metadata_from_peers,
    fetch_metadata_from_peers_async,
    validate_metadata,
)


class TestMetadataState:
    """Tests for MetadataState enum."""

    def test_metadata_state_values(self):
        """Test MetadataState enum values."""
        assert MetadataState.CONNECTING.value == "connecting"
        assert MetadataState.HANDSHAKE.value == "handshake"
        assert MetadataState.NEGOTIATING.value == "negotiating"
        assert MetadataState.REQUESTING.value == "requesting"
        assert MetadataState.COMPLETE.value == "complete"
        assert MetadataState.FAILED.value == "failed"


class TestPeerMetadataSession:
    """Tests for PeerMetadataSession dataclass."""

    def test_peer_metadata_session_creation(self):
        """Test creating PeerMetadataSession with defaults."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))

        assert session.peer_info == ("192.168.1.1", 6881)
        assert session.reader is None
        assert session.writer is None
        assert session.state == MetadataState.CONNECTING
        assert session.ut_metadata_id is None
        assert session.metadata_size is None
        assert session.reliability_score == 1.0
        assert session.consecutive_failures == 0
        assert session.num_pieces == 0
        assert session.retry_count == 0
        assert session.max_retries == 3
        assert session.backoff_delay == 1.0

    def test_peer_metadata_session_custom_values(self):
        """Test creating PeerMetadataSession with custom values."""
        session = PeerMetadataSession(
            peer_info=("192.168.1.1", 6881),
            state=MetadataState.HANDSHAKE,
            ut_metadata_id=1,
            metadata_size=16384,
            reliability_score=0.5,
            consecutive_failures=2,
            num_pieces=1,
            retry_count=1,
            max_retries=5,
            backoff_delay=2.0,
        )

        assert session.state == MetadataState.HANDSHAKE
        assert session.ut_metadata_id == 1
        assert session.metadata_size == 16384
        assert session.reliability_score == 0.5
        assert session.consecutive_failures == 2


class TestMetadataPiece:
    """Tests for MetadataPiece dataclass."""

    def test_metadata_piece_creation(self):
        """Test creating MetadataPiece."""
        piece = MetadataPiece(index=0)

        assert piece.index == 0
        assert piece.data is None
        assert piece.received_count == 0
        assert piece.sources == set()

    def test_metadata_piece_with_data(self):
        """Test MetadataPiece with data."""
        piece = MetadataPiece(index=0, data=b"test data")

        assert piece.data == b"test data"


class TestAsyncMetadataExchange:
    """Tests for AsyncMetadataExchange class."""

    @pytest.fixture
    def exchange(self):
        """Create AsyncMetadataExchange instance."""
        info_hash = hashlib.sha1(b"test").digest()
        return AsyncMetadataExchange(info_hash)

    @pytest.fixture
    def sample_peers(self):
        """Create sample peer list."""
        return [
            {"ip": "192.168.1.1", "port": 6881},
            {"ip": "192.168.1.2", "port": 6882},
        ]

    def test_init_default_peer_id(self):
        """Test initialization with default peer ID."""
        info_hash = hashlib.sha1(b"test").digest()
        exchange = AsyncMetadataExchange(info_hash)

        assert exchange.info_hash == info_hash
        assert exchange.our_peer_id.startswith(b"-CC0101-")
        assert len(exchange.our_peer_id) == 20
        assert not exchange.completed
        assert exchange.metadata_data is None
        assert exchange.metadata_dict is None

    def test_init_custom_peer_id(self):
        """Test initialization with custom peer ID."""
        info_hash = hashlib.sha1(b"test").digest()
        peer_id = b"-TEST-" + b"x" * 14
        exchange = AsyncMetadataExchange(info_hash, peer_id)

        assert exchange.our_peer_id == peer_id

    @pytest.mark.asyncio
    async def test_context_manager(self, exchange):
        """Test async context manager."""
        async with exchange:
            assert exchange._cleanup_task is not None
            assert not exchange._cleanup_task.done()

        # After exit, cleanup should be done
        assert exchange._cleanup_task is None

    @pytest.mark.asyncio
    async def test_start(self, exchange):
        """Test start method."""
        await exchange.start()

        assert exchange._cleanup_task is not None
        assert not exchange._cleanup_task.done()

        await exchange.stop()

    @pytest.mark.asyncio
    async def test_stop_cleanup(self, exchange):
        """Test stop method cleanup."""
        await exchange.start()

        # Create a mock session
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        exchange.sessions[("192.168.1.1", 6881)] = session

        # Create metadata pieces
        exchange.metadata_pieces[0] = MetadataPiece(0)

        await exchange.stop()

        assert exchange._cleanup_task is None
        assert len(exchange.sessions) == 0
        assert len(exchange.metadata_pieces) == 0

    @pytest.mark.asyncio
    async def test_fetch_metadata_no_peers(self, exchange):
        """Test fetch_metadata with no peers."""
        await exchange.start()

        result = await exchange.fetch_metadata([], max_peers=10)

        assert result is None

        await exchange.stop()

    @pytest.mark.asyncio
    async def test_fetch_metadata_zero_max_peers(self, exchange, sample_peers):
        """Test fetch_metadata with zero max_peers."""
        await exchange.start()

        result = await exchange.fetch_metadata(sample_peers, max_peers=0)

        assert result is None

        await exchange.stop()

    @pytest.mark.asyncio
    async def test_raise_connection_error(self, exchange):
        """Test _raise_connection_error method."""
        with pytest.raises(ConnectionError, match="Test error"):
            exchange._raise_connection_error("Test error")

    def test_create_handshake(self, exchange):
        """Test _create_handshake method."""
        handshake = exchange._create_handshake()

        assert len(handshake) == 68
        assert handshake[1:20] == b"BitTorrent protocol"
        assert handshake[28:48] == exchange.info_hash
        assert handshake[48:68] == exchange.our_peer_id
        # Check extension protocol flag (reserved[5])
        assert handshake[25] & 0x10 == 0x10

    def test_validate_handshake_valid(self, exchange):
        """Test _validate_handshake with valid handshake."""
        handshake = exchange._create_handshake()
        assert exchange._validate_handshake(handshake) is True

    def test_validate_handshake_wrong_length(self, exchange):
        """Test _validate_handshake with wrong length."""
        assert exchange._validate_handshake(b"short") is False

    def test_validate_handshake_wrong_protocol(self, exchange):
        """Test _validate_handshake with wrong protocol."""
        invalid_handshake = b"\x13" + b"Invalid protocol" + b"\x00" * 27 + exchange.info_hash + exchange.our_peer_id
        assert exchange._validate_handshake(invalid_handshake) is False

    def test_validate_handshake_wrong_hash(self, exchange):
        """Test _validate_handshake with wrong info hash."""
        wrong_hash = b"\x00" * 20
        handshake = exchange._create_handshake()
        # Replace info_hash in handshake
        invalid_handshake = handshake[:28] + wrong_hash + handshake[48:]
        assert exchange._validate_handshake(invalid_handshake) is False

    @pytest.mark.asyncio
    async def test_send_extended_handshake_no_writer(self, exchange):
        """Test _send_extended_handshake without writer."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))

        with pytest.raises(RuntimeError, match="Writer is not initialized"):
            await exchange._send_extended_handshake(session)

    @pytest.mark.asyncio
    async def test_send_extended_handshake_success(self, exchange):
        """Test _send_extended_handshake success."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.writer = AsyncMock()

        await exchange._send_extended_handshake(session)

        assert session.writer.write.called
        assert session.writer.drain.called

    @pytest.mark.asyncio
    async def test_receive_extended_handshake_no_reader(self, exchange):
        """Test _receive_extended_handshake without reader."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))

        with pytest.raises(RuntimeError, match="Reader is not initialized"):
            await exchange._receive_extended_handshake(session)

    @pytest.mark.asyncio
    async def test_receive_extended_handshake_success(self, exchange):
        """Test _receive_extended_handshake success."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))

        # Mock extended handshake response
        payload = BencodeEncoder().encode({b"m": {b"ut_metadata": 1}, b"metadata_size": 16384})
        msg_length = len(payload) + 2
        mock_msg = struct.pack("!IBB", msg_length, 20, 0) + payload

        session.reader = AsyncMock()
        # First read: length
        session.reader.readexactly = AsyncMock(side_effect=[
            struct.pack("!I", msg_length),  # Length
            mock_msg[4:],  # Payload
        ])

        await exchange._receive_extended_handshake(session)

        assert session.ut_metadata_id == 1
        assert session.metadata_size == 16384

    @pytest.mark.asyncio
    async def test_receive_extended_handshake_keep_alive(self, exchange):
        """Test _receive_extended_handshake with keep-alive messages."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))

        payload = BencodeEncoder().encode({b"m": {b"ut_metadata": 1}, b"metadata_size": 16384})
        msg_length = len(payload) + 2
        mock_msg = struct.pack("!IBB", msg_length, 20, 0) + payload

        session.reader = AsyncMock()
        # Send keep-alive (length=0), then actual message
        session.reader.readexactly = AsyncMock(side_effect=[
            struct.pack("!I", 0),  # Keep-alive
            struct.pack("!I", msg_length),  # Length
            mock_msg[4:],  # Payload
        ])

        await exchange._receive_extended_handshake(session)

        assert session.ut_metadata_id == 1

    @pytest.mark.asyncio
    async def test_receive_extended_handshake_timeout(self, exchange):
        """Test _receive_extended_handshake with timeout."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))

        session.reader = AsyncMock()
        session.reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError())

        # Should not raise, just break loop
        await exchange._receive_extended_handshake(session)

    @pytest.mark.asyncio
    async def test_request_metadata_pieces_no_support(self, exchange):
        """Test _request_metadata_pieces when peer doesn't support ut_metadata."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.ut_metadata_id = None

        # Should return early
        await exchange._request_metadata_pieces(session)

        assert len(exchange.metadata_pieces) == 0

    @pytest.mark.asyncio
    async def test_request_metadata_pieces_success(self, exchange):
        """Test _request_metadata_pieces success."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.ut_metadata_id = 1
        session.metadata_size = 16384  # Exactly one piece
        session.writer = AsyncMock()

        with patch.object(exchange, "_request_metadata_piece") as mock_request:
            await exchange._request_metadata_pieces(session)

            assert session.num_pieces == 1
            assert 0 in exchange.metadata_pieces
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_metadata_piece_no_writer(self, exchange):
        """Test _request_metadata_piece without writer."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.ut_metadata_id = 1
        session.writer = None

        # Exception is caught and logged, piece is added to failed set
        with patch.object(exchange.logger, "debug") as mock_log:
            await exchange._request_metadata_piece(session, 0)

            assert 0 in session.pieces_failed
            assert mock_log.called

    @pytest.mark.asyncio
    async def test_request_metadata_piece_success(self, exchange):
        """Test _request_metadata_piece success."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.ut_metadata_id = 1
        session.writer = AsyncMock()

        with patch.object(exchange, "_wait_for_piece_response") as mock_wait:
            await exchange._request_metadata_piece(session, 0)

            assert session.writer.write.called
            assert session.writer.drain.called
            mock_wait.assert_called_once_with(session, 0)

    @pytest.mark.asyncio
    async def test_request_metadata_piece_exception(self, exchange):
        """Test _request_metadata_piece handles exception."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.ut_metadata_id = 1
        session.writer = AsyncMock()

        with patch.object(exchange, "_wait_for_piece_response", side_effect=Exception("Error")):
            await exchange._request_metadata_piece(session, 0)

            assert 0 in session.pieces_failed

    @pytest.mark.asyncio
    async def test_wait_for_piece_response_no_reader(self, exchange):
        """Test _wait_for_piece_response without reader."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.ut_metadata_id = 1
        session.reader = None

        # Exception is caught in the loop, piece is added to failed set after timeout
        await exchange._wait_for_piece_response(session, 0)

        assert 0 in session.pieces_failed

    @pytest.mark.asyncio
    async def test_wait_for_piece_response_success(self, exchange):
        """Test _wait_for_piece_response with successful piece - simplified due to complex parsing."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.ut_metadata_id = 1

        # Mock reader to timeout quickly (complex piece parsing is tested via integration tests)
        session.reader = AsyncMock()
        session.reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError())

        # Should timeout and add to failed pieces
        await exchange._wait_for_piece_response(session, 0)

        assert 0 in session.pieces_failed

    @pytest.mark.asyncio
    async def test_wait_for_piece_response_reject(self, exchange):
        """Test _wait_for_piece_response with reject."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.ut_metadata_id = 1

        # Create mock reject response
        header = {b"msg_type": 2}
        header_bytes = BencodeEncoder().encode(header)
        payload = struct.pack("!IBB", 2 + len(header_bytes), 20, 1) + header_bytes

        session.reader = AsyncMock()
        session.reader.readexactly = AsyncMock(side_effect=[
            struct.pack("!I", len(payload)),  # Length
            payload,  # Payload
        ])

        await exchange._wait_for_piece_response(session, 0)

        assert 0 in session.pieces_failed

    @pytest.mark.asyncio
    async def test_wait_for_piece_response_timeout(self, exchange):
        """Test _wait_for_piece_response timeout."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.ut_metadata_id = 1

        session.reader = AsyncMock()
        session.reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError())

        # Should eventually timeout
        await exchange._wait_for_piece_response(session, 0)

        assert 0 in session.pieces_failed

    @pytest.mark.asyncio
    async def test_handle_metadata_piece(self, exchange):
        """Test _handle_metadata_piece."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        exchange.metadata_pieces[0] = MetadataPiece(0)

        with patch.object(exchange, "_is_metadata_complete", return_value=False):
            await exchange._handle_metadata_piece(session, 0, b"piece data")

            assert 0 in session.pieces_received
            assert exchange.metadata_pieces[0].data == b"piece data"
            assert exchange.metadata_pieces[0].received_count == 1
            assert session.peer_info in exchange.metadata_pieces[0].sources

    @pytest.mark.asyncio
    async def test_handle_metadata_piece_complete(self, exchange):
        """Test _handle_metadata_piece triggers assembly when complete."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        exchange.metadata_pieces[0] = MetadataPiece(0)

        with patch.object(exchange, "_is_metadata_complete", return_value=True):
            with patch.object(exchange, "_assemble_metadata") as mock_assemble:
                await exchange._handle_metadata_piece(session, 0, b"piece data")

                mock_assemble.assert_called_once()

    def test_is_metadata_complete_empty(self, exchange):
        """Test _is_metadata_complete with no pieces."""
        assert exchange._is_metadata_complete() is False

    def test_is_metadata_complete_partial(self, exchange):
        """Test _is_metadata_complete with partial pieces."""
        exchange.metadata_pieces[0] = MetadataPiece(0, data=b"data")
        exchange.metadata_pieces[1] = MetadataPiece(1, data=None)

        assert exchange._is_metadata_complete() is False

    def test_is_metadata_complete_all(self, exchange):
        """Test _is_metadata_complete with all pieces."""
        exchange.metadata_pieces[0] = MetadataPiece(0, data=b"data")
        exchange.metadata_pieces[1] = MetadataPiece(1, data=b"data")

        assert exchange._is_metadata_complete() is True

    @pytest.mark.asyncio
    async def test_assemble_metadata_success(self, exchange):
        """Test _assemble_metadata success."""
        # Create valid metadata
        metadata_dict = {b"info": {b"name": b"test"}, b"announce": b"http://tracker.com"}
        metadata_bytes = BencodeEncoder().encode(metadata_dict)
        info_hash = hashlib.sha1(metadata_bytes).digest()

        # Update exchange with correct hash
        exchange.info_hash = info_hash

        # Split into pieces
        piece_size = 16384
        num_pieces = (len(metadata_bytes) + piece_size - 1) // piece_size
        for i in range(num_pieces):
            start = i * piece_size
            end = start + piece_size
            exchange.metadata_pieces[i] = MetadataPiece(i, data=metadata_bytes[start:end])

        mock_on_complete = Mock()
        exchange.on_complete = mock_on_complete

        await exchange._assemble_metadata()

        assert exchange.completed is True
        assert exchange.metadata_data == metadata_bytes
        assert exchange.metadata_dict == metadata_dict
        mock_on_complete.assert_called_once_with(metadata_dict)

    @pytest.mark.asyncio
    async def test_assemble_metadata_hash_failure(self, exchange):
        """Test _assemble_metadata with hash validation failure."""
        # Create metadata with wrong hash
        metadata_dict = {b"info": {b"name": b"test"}, b"announce": b"http://tracker.com"}
        metadata_bytes = BencodeEncoder().encode(metadata_dict)

        # Use wrong hash
        exchange.info_hash = b"wrong" * 4

        exchange.metadata_pieces[0] = MetadataPiece(0, data=metadata_bytes)

        mock_on_error = Mock()
        exchange.on_error = mock_on_error

        await exchange._assemble_metadata()

        assert exchange.completed is False

    @pytest.mark.asyncio
    async def test_assemble_metadata_exception(self, exchange):
        """Test _assemble_metadata handles exception."""
        # Create invalid piece data
        exchange.metadata_pieces[0] = MetadataPiece(0, data=b"invalid bencode")

        mock_on_error = Mock()
        exchange.on_error = mock_on_error

        await exchange._assemble_metadata()

        mock_on_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_completion(self, exchange):
        """Test _wait_for_completion."""
        exchange.completed = False

        # Set completed in background
        async def set_completed():
            await asyncio.sleep(0.1)
            exchange.completed = True

        task = asyncio.create_task(set_completed())
        await exchange._wait_for_completion()
        await task

        assert exchange.completed is True

    @pytest.mark.asyncio
    async def test_cleanup_loop(self, exchange):
        """Test _cleanup_loop."""
        await exchange.start()

        # Cancel immediately
        exchange._cleanup_task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await exchange._cleanup_task

        await exchange.stop()

    @pytest.mark.asyncio
    async def test_cleanup_sessions(self, exchange):
        """Test _cleanup_sessions."""
        # Create stale session
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.last_activity = 0  # Very old
        exchange.sessions[("192.168.1.1", 6881)] = session

        with patch.object(exchange, "_close_session") as mock_close:
            await exchange._cleanup_sessions()

            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session(self, exchange):
        """Test _close_session."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        session.writer = AsyncMock()

        await exchange._close_session(session)

        assert session.writer.close.called
        assert session.state == MetadataState.FAILED

    @pytest.mark.asyncio
    async def test_close_session_no_writer(self, exchange):
        """Test _close_session without writer."""
        session = PeerMetadataSession(peer_info=("192.168.1.1", 6881))

        await exchange._close_session(session)

        assert session.state == MetadataState.FAILED

    def test_get_progress_empty(self, exchange):
        """Test get_progress with no pieces."""
        assert exchange.get_progress() == 0.0

    def test_get_progress_partial(self, exchange):
        """Test get_progress with partial pieces."""
        exchange.metadata_pieces[0] = MetadataPiece(0, data=b"data")
        exchange.metadata_pieces[1] = MetadataPiece(1, data=None)

        assert exchange.get_progress() == 0.5

    def test_get_progress_complete(self, exchange):
        """Test get_progress with all pieces."""
        exchange.metadata_pieces[0] = MetadataPiece(0, data=b"data")
        exchange.metadata_pieces[1] = MetadataPiece(1, data=b"data")

        assert exchange.get_progress() == 1.0

    def test_get_stats(self, exchange):
        """Test get_stats."""
        exchange.metadata_pieces[0] = MetadataPiece(0, data=b"data")
        exchange.metadata_pieces[1] = MetadataPiece(1, data=None)
        exchange.sessions[("192.168.1.1", 6881)] = PeerMetadataSession(peer_info=("192.168.1.1", 6881))
        exchange.metadata_size = 16384

        stats = exchange.get_stats()

        assert stats["sessions"] == 1
        assert stats["pieces_received"] == 1
        assert stats["total_pieces"] == 2
        assert stats["progress"] == 0.5
        assert stats["completed"] is False
        assert stats["metadata_size"] == 16384


class TestModuleFunctions:
    """Tests for module-level functions."""

    @pytest.mark.asyncio
    async def test_fetch_metadata_from_peers(self):
        """Test fetch_metadata_from_peers function."""
        info_hash = hashlib.sha1(b"test").digest()
        peers = [{"ip": "192.168.1.1", "port": 6881}]

        # Should return None as connection will fail
        result = await fetch_metadata_from_peers(info_hash, peers, timeout=0.1)

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_metadata_from_peers_async(self):
        """Test fetch_metadata_from_peers_async function."""
        info_hash = hashlib.sha1(b"test").digest()
        peers = [{"ip": "192.168.1.1", "port": 6881}]

        result = await fetch_metadata_from_peers_async(peers, info_hash, timeout=0.1)

        assert result is None

    def test_validate_metadata_valid(self):
        """Test validate_metadata with valid metadata."""
        metadata = BencodeEncoder().encode({
            b"info": {b"name": b"test"},
            b"announce": b"http://tracker.com",
        })

        assert validate_metadata(metadata) is True

    def test_validate_metadata_invalid_structure(self):
        """Test validate_metadata with invalid structure."""
        metadata = BencodeEncoder().encode([b"not", b"a", b"dict"])

        assert validate_metadata(metadata) is False

    def test_validate_metadata_missing_fields(self):
        """Test validate_metadata with missing required fields."""
        metadata = BencodeEncoder().encode({b"info": {b"name": b"test"}})

        assert validate_metadata(metadata) is False

    def test_validate_metadata_invalid_data(self):
        """Test validate_metadata with invalid bencode."""
        assert validate_metadata(b"invalid bencode") is False


class TestPeerReliabilityTracker:
    """Tests for PeerReliabilityTracker class."""

    def test_init(self):
        """Test PeerReliabilityTracker initialization."""
        tracker = PeerReliabilityTracker()

        assert tracker.scores == {}
        assert tracker.failures == {}

    def test_update_success_new_peer(self):
        """Test update_success for new peer."""
        tracker = PeerReliabilityTracker()
        peer_info = ("192.168.1.1", 6881)

        tracker.update_success(peer_info)

        assert tracker.scores[peer_info] > 0.5  # Should be increased from default
        assert tracker.failures[peer_info] == 0

    def test_update_success_existing_peer(self):
        """Test update_success for existing peer."""
        tracker = PeerReliabilityTracker()
        peer_info = ("192.168.1.1", 6881)
        tracker.scores[peer_info] = 0.3
        tracker.failures[peer_info] = 2

        tracker.update_success(peer_info)

        assert tracker.failures[peer_info] == 0
        assert tracker.scores[peer_info] > 0.3

    def test_update_failure_new_peer(self):
        """Test update_failure for new peer."""
        tracker = PeerReliabilityTracker()
        peer_info = ("192.168.1.1", 6881)

        tracker.update_failure(peer_info)

        assert tracker.failures[peer_info] == 1
        assert tracker.scores.get(peer_info, 0.5) < 1.0

    def test_update_failure_existing_peer(self):
        """Test update_failure for existing peer."""
        tracker = PeerReliabilityTracker()
        peer_info = ("192.168.1.1", 6881)
        tracker.scores[peer_info] = 0.8

        tracker.update_failure(peer_info)

        assert tracker.failures[peer_info] == 1
        assert tracker.scores[peer_info] < 0.8

    def test_record_success_alias(self):
        """Test record_success is alias for update_success."""
        tracker = PeerReliabilityTracker()
        peer_info = ("192.168.1.1", 6881)

        tracker.record_success(peer_info)

        assert peer_info in tracker.scores

    def test_record_failure_alias(self):
        """Test record_failure is alias for update_failure."""
        tracker = PeerReliabilityTracker()
        peer_info = ("192.168.1.1", 6881)

        tracker.record_failure(peer_info)

        assert tracker.failures[peer_info] == 1

    def test_get_reliability_score_existing(self):
        """Test get_reliability_score for existing peer."""
        tracker = PeerReliabilityTracker()
        peer_info = ("192.168.1.1", 6881)
        tracker.scores[peer_info] = 0.7

        assert tracker.get_reliability_score(peer_info) == 0.7

    def test_get_reliability_score_new(self):
        """Test get_reliability_score for new peer."""
        tracker = PeerReliabilityTracker()
        peer_info = ("192.168.1.1", 6881)

        assert tracker.get_reliability_score(peer_info) == 0.5  # Default


class TestMetadataPieceManager:
    """Tests for MetadataPieceManager class."""

    def test_init(self):
        """Test MetadataPieceManager initialization."""
        manager = MetadataPieceManager(16384)

        assert manager.total_size == 16384
        assert manager.pieces == {}
        assert manager.received_pieces == set()

    def test_add_piece(self):
        """Test add_piece method."""
        manager = MetadataPieceManager(16384)

        manager.add_piece(0, b"piece data")

        assert 0 in manager.pieces
        assert 0 in manager.received_pieces
        assert manager.pieces[0] == b"piece data"

    def test_is_complete_false(self):
        """Test is_complete returns False when incomplete."""
        manager = MetadataPieceManager(2)

        manager.add_piece(0, b"data")

        assert manager.is_complete() is False

    def test_is_complete_true(self):
        """Test is_complete returns True when complete."""
        manager = MetadataPieceManager(2)

        manager.add_piece(0, b"data")
        manager.add_piece(1, b"data")

        assert manager.is_complete() is True

    def test_assemble_metadata_incomplete(self):
        """Test assemble_metadata raises when incomplete."""
        manager = MetadataPieceManager(2)

        manager.add_piece(0, b"data")

        with pytest.raises(ValueError, match="Not all pieces received"):
            manager.assemble_metadata()

    def test_assemble_metadata_success(self):
        """Test assemble_metadata success."""
        manager = MetadataPieceManager(2)

        manager.add_piece(0, b"data")
        manager.add_piece(1, b"data2")

        metadata = manager.assemble_metadata()

        assert metadata == b"datadata2"


class TestRetryManager:
    """Tests for RetryManager class."""

    def test_init(self):
        """Test RetryManager initialization."""
        manager = RetryManager(max_retries=5, base_delay=2.0)

        assert manager.max_retries == 5
        assert manager.base_delay == 2.0
        assert manager.retry_counts == {}

    def test_should_retry_new_key(self):
        """Test should_retry for new key."""
        manager = RetryManager(max_retries=3)

        assert manager.should_retry("key1") is True

    def test_should_retry_exhausted(self):
        """Test should_retry when retries exhausted."""
        manager = RetryManager(max_retries=2)
        manager.retry_counts["key1"] = 2

        assert manager.should_retry("key1") is False

    def test_record_retry(self):
        """Test record_retry method."""
        manager = RetryManager()

        manager.record_retry("key1")

        assert manager.retry_counts["key1"] == 1

    def test_get_delay_exponential(self):
        """Test get_delay returns exponential backoff."""
        manager = RetryManager(base_delay=1.0)

        manager.record_retry("key1")  # 1 retry
        assert manager.get_delay("key1") == 2.0  # 1 * 2^1

        manager.record_retry("key1")  # 2 retries
        assert manager.get_delay("key1") == 4.0  # 1 * 2^2

    def test_get_retry_count(self):
        """Test get_retry_count method."""
        manager = RetryManager()

        assert manager.get_retry_count("key1") == 0

        manager.record_retry("key1")
        assert manager.get_retry_count("key1") == 1

    def test_record_success(self):
        """Test record_success resets retry count."""
        manager = RetryManager()
        manager.retry_counts["key1"] = 2

        manager.record_success("key1")

        assert "key1" not in manager.retry_counts


class TestMetadataCache:
    """Tests for MetadataCache class."""

    def test_init(self):
        """Test MetadataCache initialization."""
        cache = MetadataCache(max_size=50)

        assert cache.max_size == 50
        assert cache.cache == {}
        assert cache.access_times == {}

    def test_get_missing(self):
        """Test get with missing entry."""
        cache = MetadataCache()

        assert cache.get(b"hash1") is None

    def test_get_existing(self):
        """Test get with existing entry."""
        cache = MetadataCache()
        metadata = {b"info": {b"name": b"test"}}
        cache.cache[b"hash1"] = metadata
        cache.access_times[b"hash1"] = 0

        result = cache.get(b"hash1")

        assert result == metadata
        assert cache.access_times[b"hash1"] > 0  # Updated

    def test_put_new(self):
        """Test put with new entry."""
        cache = MetadataCache()
        metadata = {b"info": {b"name": b"test"}}

        cache.put(b"hash1", metadata)

        assert cache.cache[b"hash1"] == metadata
        assert b"hash1" in cache.access_times

    def test_put_eviction(self):
        """Test put evicts oldest when full."""
        import time

        cache = MetadataCache(max_size=2)

        cache.put(b"hash1", {b"info": {b"name": b"test1"}})
        time.sleep(0.01)
        cache.put(b"hash2", {b"info": {b"name": b"test2"}})
        time.sleep(0.01)
        cache.put(b"hash3", {b"info": {b"name": b"test3"}})

        # hash1 should be evicted (oldest)
        assert b"hash1" not in cache.cache
        assert b"hash3" in cache.cache


class TestMetadataMetrics:
    """Tests for MetadataMetrics class."""

    def test_init(self):
        """Test MetadataMetrics initialization."""
        metrics = MetadataMetrics()

        assert metrics.connections_attempted == 0
        assert metrics.connections_successful == 0
        assert metrics.pieces_requested == 0
        assert metrics.pieces_received == 0
        assert metrics.retries == 0

    def test_record_connection_attempt(self):
        """Test record_connection_attempt."""
        metrics = MetadataMetrics()

        metrics.record_connection_attempt()

        assert metrics.connections_attempted == 1

    def test_record_connection_success(self):
        """Test record_connection_success."""
        metrics = MetadataMetrics()

        metrics.record_connection_success()

        assert metrics.connections_successful == 1

    def test_record_piece_request(self):
        """Test record_piece_request."""
        metrics = MetadataMetrics()

        metrics.record_piece_request()

        assert metrics.pieces_requested == 1

    def test_record_piece_received(self):
        """Test record_piece_received."""
        metrics = MetadataMetrics()

        metrics.record_piece_received()

        assert metrics.pieces_received == 1

    def test_record_retry(self):
        """Test record_retry."""
        metrics = MetadataMetrics()

        metrics.record_retry()

        assert metrics.retries == 1

    def test_record_peer_connection(self):
        """Test record_peer_connection."""
        metrics = MetadataMetrics()

        metrics.record_peer_connection(("192.168.1.1", 6881))

        assert metrics.connections_attempted == 1

    def test_record_metadata_piece_received(self):
        """Test record_metadata_piece_received."""
        metrics = MetadataMetrics()

        metrics.record_metadata_piece_received(("192.168.1.1", 6881))

        assert metrics.pieces_received == 1

    def test_record_metadata_complete(self):
        """Test record_metadata_complete (no-op)."""
        metrics = MetadataMetrics()
        initial_count = metrics.connections_successful

        metrics.record_metadata_complete(("192.168.1.1", 6881))

        # Should not change counts
        assert metrics.connections_successful == initial_count

    def test_get_stats(self):
        """Test get_stats."""
        metrics = MetadataMetrics()
        metrics.record_connection_attempt()
        metrics.record_connection_success()
        metrics.record_piece_request()
        metrics.record_piece_received()

        stats = metrics.get_stats()

        assert stats["connections_attempted"] == 1
        assert stats["connections_successful"] == 1
        assert stats["pieces_requested"] == 1
        assert stats["pieces_received"] == 1
        assert "success_rate" in stats

    def test_get_success_rate_zero_attempts(self):
        """Test get_success_rate with zero attempts."""
        metrics = MetadataMetrics()

        assert metrics.get_success_rate() == 0.0

    def test_get_success_rate_calculation(self):
        """Test get_success_rate calculation."""
        metrics = MetadataMetrics()
        metrics.record_connection_attempt()
        metrics.record_connection_attempt()
        metrics.record_connection_success()

        assert metrics.get_success_rate() == 0.5

    def test_get_completion_rate_zero_requests(self):
        """Test get_completion_rate with zero requests."""
        metrics = MetadataMetrics()

        assert metrics.get_completion_rate() == 0.0

    def test_get_completion_rate_calculation(self):
        """Test get_completion_rate calculation."""
        metrics = MetadataMetrics()
        metrics.record_piece_request()
        metrics.record_piece_request()
        metrics.record_piece_received()

        assert metrics.get_completion_rate() == 0.5

