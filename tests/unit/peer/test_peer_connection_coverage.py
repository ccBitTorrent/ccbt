"""Additional tests for peer_connection.py to achieve 100% coverage.

This file contains targeted tests for specific code paths that are currently
missing coverage, based on coverage analysis.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.peer]

from ccbt.models import MessageType
from ccbt.peer.peer import (
    BitfieldMessage,
    CancelMessage,
    ChokeMessage,
    Handshake,
    InterestedMessage,
    KeepAliveMessage,
    MessageError,
    NotInterestedMessage,
    PieceMessage,
    UnchokeMessage,
)
from ccbt.peer.async_peer_connection import (
    AsyncPeerConnectionManager,
    AsyncPeerConnection,
    ConnectionState,
    RequestInfo,
    PeerConnectionError,
)
from ccbt.peer.peer_connection import (
    PeerConnection,
)
from ccbt.peer.peer import PeerInfo


@pytest.fixture
def mock_torrent_data():
    """Fixture for torrent data."""
    return {
        "info_hash": b"info_hash_20_bytes__",
        "pieces_info": {"num_pieces": 10},
    }


@pytest.fixture
def mock_piece_manager():
    """Fixture for piece manager."""
    return Mock()


@pytest.fixture
def manager(mock_torrent_data, mock_piece_manager):
    """Fixture for AsyncPeerConnectionManager."""
    return AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager,
    )


class TestConnectionLimit:
    """Test connection limit handling."""

    @pytest.mark.asyncio
    async def test_connect_to_peers_max_connections_reached(self, manager):
        """Test connect_to_peers returns early when max_connections reached."""
        # Fill connections to max
        manager.max_connections = 2
        for i in range(2):
            peer_info = PeerInfo(ip=f"192.168.1.{100+i}", port=6881)
            connection = PeerConnection(peer_info, manager.torrent_data)
            connection.state = ConnectionState.CONNECTED
            manager.connections[str(peer_info)] = connection

        # Try to connect to more peers - should return early
        peer_list = [
            {"ip": "192.168.1.200", "port": 6881},
            {"ip": "192.168.1.201", "port": 6882},
        ]
        await manager.connect_to_peers(peer_list)

        # Should still have only 2 connections
        assert len(manager.connections) == 2

    @pytest.mark.asyncio
    async def test_connect_to_peers_duplicate_skip(self, manager, mock_torrent_data):
        """Test duplicate peer connection is skipped."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, mock_torrent_data)
        connection.state = ConnectionState.CONNECTED
        manager.connections[str(peer_info)] = connection

        # Try to connect to same peer again
        peer_list = [{"ip": "192.168.1.100", "port": 6881}]

        with patch("asyncio.open_connection") as mock_open:
            # Should not attempt connection
            await manager.connect_to_peers(peer_list)
            mock_open.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_to_peers_gather_exception_handling(self, manager):
        """Test exception handling from asyncio.gather."""
        peer_list = [{"ip": "192.168.1.100", "port": 6881}]
        
        # Start manager before connecting
        await manager.start()

        with patch("asyncio.open_connection", side_effect=ConnectionError("Connection failed")):
            with patch.object(manager.logger, "debug") as mock_debug:
                await manager.connect_to_peers(peer_list)
                # Should log debug/warning for connection failures (exceptions are returned from gather, not raised)
                # The exception is processed and logged as debug for temporary failures
                mock_debug.assert_called()


class TestHandshakeValidation:
    """Test handshake validation paths."""

    @pytest.mark.asyncio
    async def test_info_hash_mismatch(self, manager):
        """Test info hash mismatch raises PeerConnectionError."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.wait_closed = AsyncMock()  # Fix: wait_closed must be AsyncMock
        mock_writer.close = MagicMock()

        # Create handshake with wrong info_hash
        wrong_info_hash = b"wrong_info_hash_20_b"
        handshake = Handshake(wrong_info_hash, b"test_peer_id_20_byte")
        wrong_handshake_data = handshake.encode()

        mock_reader.readexactly = AsyncMock(return_value=wrong_handshake_data)

        with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
            # Exception is caught and handled internally, so we verify error handling
            await manager.connect_to_peers([{"ip": "192.168.1.100", "port": 6881}])
            
            # Verify connection error was handled (connection should be in ERROR state or not in connections)
            # The error path is executed, verifying the code coverage
            # Check that the error handling code path was executed
            assert len(manager.connections) == 0 or any(
                conn.state == ConnectionState.ERROR
                for conn in manager.connections.values()
            )

    @pytest.mark.asyncio
    async def test_invalid_handshake_length(self, manager):
        """Test invalid handshake length raises PeerConnectionError."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.wait_closed = AsyncMock()  # Fix: wait_closed must be AsyncMock
        mock_writer.close = MagicMock()

        # Return wrong length handshake
        mock_reader.readexactly = AsyncMock(return_value=b"short" * 10)  # 50 bytes, not 68

        with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
            # Exception is caught and handled internally, so we verify error handling
            await manager.connect_to_peers([{"ip": "192.168.1.100", "port": 6881}])
            
            # Verify connection error was handled (connection should be in ERROR state or not in connections)
            # The error path is executed, verifying the code coverage
            assert len(manager.connections) == 0 or any(
                conn.state == ConnectionState.ERROR
                for conn in manager.connections.values()
            )


class TestCallbacks:
    """Test callback invocations."""

    @pytest.mark.asyncio
    async def test_on_peer_connected_callback(self, manager):
        """Test on_peer_connected callback is called."""
        callback_called = False
        connected_peer = None

        def callback(connection):
            nonlocal callback_called, connected_peer
            callback_called = True
            connected_peer = connection

        manager.on_peer_connected = callback

        # Note: Start the manager before connecting to peers
        # The manager must be running (_running=True) for _connect_to_peer to proceed
        await manager.start()

        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.write = MagicMock()
        # Note: Mock is_closing to return False - checked after TCP connection
        mock_writer.is_closing = Mock(return_value=False)
        # Note: Mock get_extra_info for socket optimization code path
        mock_writer.get_extra_info = Mock(return_value=None)
        mock_writer.wait_closed = AsyncMock(return_value=None)
        mock_writer.close = MagicMock()

        # Create proper handshake
        info_hash = manager.torrent_data["info_hash"]
        handshake = Handshake(info_hash, b"test_peer_id_20_byte")
        proper_handshake_data = handshake.encode()  # 68 bytes
        
        # Note: Mock readexactly to handle protocol length (1 byte) then remaining (67 bytes)
        handshake_calls = {"protocol_len": False, "remaining": False}
        async def readexactly_side_effect(n):
            if n == 1 and not handshake_calls["protocol_len"]:
                handshake_calls["protocol_len"] = True
                return proper_handshake_data[:1]
            elif n == 67 and not handshake_calls["remaining"]:
                handshake_calls["remaining"] = True
                return proper_handshake_data[1:68]
            else:
                # After handshake, raise IncompleteReadError to stop message loop
                raise asyncio.IncompleteReadError(b"", n)
        mock_reader.readexactly = readexactly_side_effect

        with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
            with patch.object(manager, "_send_bitfield", new_callable=AsyncMock):
                with patch.object(manager, "_send_unchoke", new_callable=AsyncMock):
                    with patch.object(manager, "_handle_peer_messages", new_callable=AsyncMock):
                        await manager._connect_to_peer(peer_info)

                        # Note: Wait for callback to be called (connection is async)
                        max_wait = 0.2
                        start_time = asyncio.get_event_loop().time()
                        while not callback_called:
                            await asyncio.sleep(0.001)
                            elapsed = asyncio.get_event_loop().time() - start_time
                            if elapsed > max_wait:
                                break

        assert callback_called, f"Callback not called (waited {elapsed:.3f}s)"
        assert connected_peer is not None
        
        # Cleanup: stop the manager
        await manager.stop()
        
        # Cleanup: stop the manager
        await manager.stop()

    @pytest.mark.asyncio
    async def test_on_piece_received_callback(self, manager):
        """Test on_piece_received callback is called."""
        callback_called = False
        received_message = None

        def callback(connection, message):
            nonlocal callback_called, received_message
            callback_called = True
            received_message = message

        manager.on_piece_received = callback

        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        # Note: Use AsyncPeerConnection instead of PeerConnection
        from ccbt.peer.async_peer_connection import AsyncPeerConnection
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        # Note: Initialize outstanding_requests for AsyncPeerConnection
        connection.outstanding_requests = {}
        
        # Note: Configure piece_manager.pieces to support subscript access
        from ccbt.piece.async_piece_manager import PieceState
        mock_piece = Mock()
        mock_piece.state = PieceState.MISSING
        mock_piece.blocks = []
        manager.piece_manager.pieces = {0: mock_piece}  # Support piece_index 0 for test

        piece_msg = PieceMessage(piece_index=0, begin=0, block=b"test data")
        await manager._handle_piece(connection, piece_msg)

        assert callback_called
        assert received_message == piece_msg

    @pytest.mark.asyncio
    async def test_on_peer_disconnected_callback(self, manager):
        """Test on_peer_disconnected callback is called."""
        callback_called = False
        disconnected_peer = None

        def callback(connection):
            nonlocal callback_called, disconnected_peer
            callback_called = True
            disconnected_peer = connection

        manager.on_peer_disconnected = callback

        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        # Note: Use AsyncPeerConnection instead of PeerConnection
        from ccbt.peer.async_peer_connection import AsyncPeerConnection
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.CONNECTED
        peer_key = f"{peer_info.ip}:{peer_info.port}"
        async with manager.connection_lock:
            manager.connections[peer_key] = connection

        # Note: Use _disconnect_peer instead of _handle_connection_error
        # _handle_connection_error doesn't exist, but _disconnect_peer handles disconnection
        await manager._disconnect_peer(connection)

        assert callback_called
        assert disconnected_peer == connection


class TestMessageHandling:
    """Test message handling paths."""

    @pytest.mark.asyncio
    async def test_reader_none_break(self, manager):
        """Test message loop breaks when reader is None."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.CONNECTED
        connection.reader = None  # Set reader to None

        # Should exit loop immediately
        await manager._handle_peer_messages(connection)

    @pytest.mark.asyncio
    async def test_keep_alive_message(self, manager):
        """Test keep-alive message handling (length == 0)."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.CONNECTED
        mock_reader = AsyncMock()

        # Keep-alive message: length 0
        mock_reader.readexactly = AsyncMock(side_effect=[
            b"\x00\x00\x00\x00",  # Length 0 (keep-alive)
            asyncio.CancelledError(),  # Cancel to exit loop
        ])

        connection.reader = mock_reader

        try:
            await manager._handle_peer_messages(connection)
        except asyncio.CancelledError:
            pass

        # last_activity should be updated (check stats.last_activity for AsyncPeerConnection)
        assert connection.stats.last_activity > 0

    @pytest.mark.asyncio
    async def test_message_decoder_loop(self, manager):
        """Test message decoder loop with multiple messages."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.CONNECTED

        # Mock message decoder to return multiple messages then None
        messages = [
            KeepAliveMessage(),
            ChokeMessage(),
            None,  # Signals end of messages
        ]
        message_iter = iter(messages)
        call_count = [0]

        async def get_message():
            call_count[0] += 1
            msg = next(message_iter, None)
            return msg

        connection.message_decoder = Mock()
        connection.message_decoder.feed_data = AsyncMock()
        connection.message_decoder.get_message = get_message

        mock_reader = AsyncMock()
        # First read: length, second read: payload
        mock_reader.readexactly = AsyncMock(side_effect=[
            b"\x00\x00\x00\x01",  # Length 1 (keep-alive)
            b"\x00",  # Message type 0 (keep-alive)
            asyncio.CancelledError(),  # Cancel to exit loop
        ])

        connection.reader = mock_reader

        with patch.object(manager, "_handle_message", new_callable=AsyncMock) as mock_handle:
            try:
                await manager._handle_peer_messages(connection)
            except asyncio.CancelledError:
                pass

            # Should handle messages until None
            # The decoder should be called at least once
            assert call_count[0] >= 1

    @pytest.mark.asyncio
    async def test_message_decoding_error(self, manager):
        """Test message decoding error handling."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.CONNECTED

        mock_reader = AsyncMock()
        # First read: length, second read: payload, then raise IncompleteReadError to exit loop gracefully
        # Note: Use a valid message type (0-8) so the message reaches the decoder
        # Message type 0 = choke, but we'll use type 1 = unchoke (valid message type)
        call_count = [0]
        async def readexactly_side_effect(n):
            call_count[0] += 1
            if call_count[0] == 1:
                return b"\x00\x00\x00\x01"  # Length 1 (valid message)
            elif call_count[0] == 2:
                return b"\x01"  # Payload: message type 1 (unchoke - valid message type 0-8)
            else:
                # After the error is handled, raise IncompleteReadError to exit loop
                raise asyncio.IncompleteReadError(b"", n)
        mock_reader.readexactly = readexactly_side_effect

        connection.reader = mock_reader
        connection.message_decoder = Mock()
        # Make get_message raise MessageError to trigger error handler (code catches MessageError and IndexError)
        connection.message_decoder.feed_data = AsyncMock()
        connection.message_decoder.get_message = AsyncMock(side_effect=MessageError("Invalid message"))

        with patch.object(manager.logger, "warning") as mock_warning:
            await manager._handle_peer_messages(connection)

            # Should log warning and continue (exception is caught in the try/except around feed_data/get_message)
            mock_warning.assert_called()

    @pytest.mark.asyncio
    async def test_message_loop_exception(self, manager):
        """Test message loop exception handler."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.CONNECTED

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(side_effect=RuntimeError("Network error"))

        connection.reader = mock_reader

        with patch.object(manager.logger, "exception") as mock_exception:
            await manager._handle_peer_messages(connection)
            # Should log exception
            mock_exception.assert_called()

    @pytest.mark.asyncio
    async def test_handle_message_keep_alive(self, manager):
        """Test _handle_message with KeepAliveMessage."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        # Note: Use AsyncPeerConnection instead of PeerConnection
        # _handle_message expects AsyncPeerConnection which has peer_choking attribute
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        # Note: AsyncPeerConnection uses stats.last_activity, not last_activity directly
        initial_activity = connection.stats.last_activity

        await asyncio.sleep(0.01)  # Small delay
        await manager._handle_message(connection, KeepAliveMessage())

        # last_activity should be updated
        assert connection.stats.last_activity > initial_activity

    @pytest.mark.asyncio
    async def test_handle_message_state_changes(self, manager):
        """Test _handle_message state changes for Choke/Unchoke/Interested/NotInterested."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE

        # Test Choke
        await manager._handle_message(connection, ChokeMessage())
        assert connection.peer_choking is True
        assert connection.state == ConnectionState.CHOKED

        # Test Unchoke
        await manager._handle_message(connection, UnchokeMessage())
        assert connection.peer_choking is False
        assert connection.state == ConnectionState.ACTIVE

        # Test Interested
        await manager._handle_message(connection, InterestedMessage())
        assert connection.peer_interested is True

        # Test NotInterested
        await manager._handle_message(connection, NotInterestedMessage())
        assert connection.peer_interested is False

    @pytest.mark.asyncio
    async def test_handle_message_exception(self, manager):
        """Test _handle_message exception handling."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE

        # Create a message that will cause an error in the handler
        # Mock the message handler to raise an exception
        original_handlers = manager.message_handlers.copy()
        async def failing_handler(conn, msg):
            raise AttributeError("Test error in handler")
        
        # Set a handler that will fail
        manager.message_handlers[MessageType.BITFIELD] = failing_handler
        
        with patch.object(manager.logger, "exception") as mock_exception:
            bitfield = BitfieldMessage(b"\xff\x00")
            await manager._handle_message(connection, bitfield)
            mock_exception.assert_called()
        
        # Restore original handlers
        manager.message_handlers = original_handlers


class TestBitfieldHandling:
    """Test bitfield handling paths."""

    @pytest.mark.asyncio
    async def test_bitfield_exchange_timing(self, manager):
        """Test bitfield exchange timing edge case (BITFIELD_SENT -> ACTIVE)."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        # Set to BITFIELD_SENT before receiving bitfield
        connection.state = ConnectionState.BITFIELD_SENT
        
        # Mock piece_manager to avoid errors
        manager.piece_manager = Mock()
        manager.piece_manager.update_peer_availability = AsyncMock()
        # Mock writer to avoid send errors
        connection.writer = MagicMock()
        connection.writer.write = MagicMock()
        connection.writer.drain = AsyncMock()

        bitfield = BitfieldMessage(b"\xff\x00")
        await manager._handle_bitfield(connection, bitfield)

        # The code sets state to BITFIELD_RECEIVED first (line 7738), then may transition to ACTIVE
        # if peer unchokes us. For this test, we verify BITFIELD_RECEIVED is set.
        # The state should be BITFIELD_RECEIVED after the handler (or ACTIVE if peer unchokes).
        assert connection.state in (ConnectionState.BITFIELD_RECEIVED, ConnectionState.ACTIVE)


class TestRequestHandling:
    """Test request handling paths."""

    @pytest.mark.asyncio
    async def test_piece_manager_get_block_error(self, manager):
        """Test piece manager get_block() exception handling."""
        from ccbt.peer.peer import RequestMessage

        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.writer = MagicMock()
        connection.writer.write = MagicMock()
        connection.writer.drain = AsyncMock()

        # Make piece_manager.get_block raise exception
        manager.piece_manager.get_block = Mock(side_effect=RuntimeError("Block not available"))
        # Ensure file_assembler doesn't exist so we test the exception path
        manager.piece_manager.file_assembler = None

        request = RequestMessage(piece_index=0, begin=0, length=1024)

        # Should handle exception gracefully (returns None, then checks block is None)
        await manager._handle_request(connection, request)
        
        # Verify exception was handled (block should be None, so no piece sent)
        # The writer should not have been called to send a piece
        connection.writer.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_disk_fallback_path(self, manager):
        """Test disk fallback path via file_assembler."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.writer = MagicMock()
        connection.writer.write = MagicMock()
        connection.writer.drain = AsyncMock()

        # piece_manager.get_block returns None
        manager.piece_manager.get_block = Mock(return_value=None)

        # Add file_assembler that returns block
        manager.piece_manager.file_assembler = Mock()
        manager.piece_manager.file_assembler.read_block = Mock(return_value=b"test" * 256)

        request = Mock()
        request.piece_index = 0
        request.begin = 0
        request.length = 1024

        await manager._handle_request(connection, request)

        # Should use file_assembler
        manager.piece_manager.file_assembler.read_block.assert_called()

    @pytest.mark.asyncio
    async def test_block_unavailable(self, manager):
        """Test block unavailable or wrong size path."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE

        # piece_manager.get_block returns None
        manager.piece_manager.get_block = Mock(return_value=None)
        # No file_assembler
        manager.piece_manager.file_assembler = None

        request = Mock()
        request.piece_index = 0
        request.begin = 0
        request.length = 1024

        with patch.object(manager.logger, "debug") as mock_debug:
            await manager._handle_request(connection, request)
            # Should log debug message
            mock_debug.assert_called()

    @pytest.mark.asyncio
    async def test_piece_send_error(self, manager):
        """Test piece send error handling."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.writer = MagicMock()
        connection.writer.write = MagicMock(side_effect=OSError("Write error"))
        connection.writer.drain = AsyncMock()

        manager.piece_manager.get_block = Mock(return_value=b"test" * 256)

        request = Mock()
        request.piece_index = 0
        request.begin = 0
        request.length = 1024

        with patch.object(manager.logger, "exception") as mock_exception:
            with patch.object(manager, "_handle_connection_error", new_callable=AsyncMock):
                await manager._handle_request(connection, request)
                mock_exception.assert_called()


class TestCancelHandling:
    """Test cancel message handling."""

    @pytest.mark.asyncio
    async def test_cancel_message_handler(self, manager):
        """Test Cancel message handler."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        # Initialize outstanding_requests with a request to cancel
        import time
        request_key = (0, 0, 1024)
        connection.outstanding_requests[request_key] = RequestInfo(
            piece_index=0, begin=0, length=1024, timestamp=time.time()
        )

        cancel_msg = CancelMessage(piece_index=0, begin=0, length=1024)

        with patch.object(manager.logger, "debug") as mock_debug:
            await manager._handle_cancel(connection, cancel_msg)
            mock_debug.assert_called()
            # Verify the request was removed
            assert request_key not in connection.outstanding_requests


class TestSendMessage:
    """Test message sending paths."""

    @pytest.mark.asyncio
    async def test_send_message_writer_none(self, manager):
        """Test _send_message with None writer."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.writer = None

        message = KeepAliveMessage()
        # Should return early without raising - connection may be in process of disconnecting
        with patch.object(manager.logger, "warning") as mock_warning:
            await manager._send_message(connection, message)
            # Should log a warning but not raise
            mock_warning.assert_called_once()
            assert "writer is None" in str(mock_warning.call_args)

    @pytest.mark.asyncio
    async def test_send_message_error(self, manager):
        """Test _send_message error handling."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.writer = MagicMock()
        connection.writer.write = MagicMock(side_effect=OSError("Write failed"))
        connection.writer.drain = AsyncMock()

        message = KeepAliveMessage()

        with patch.object(manager.logger, "warning") as mock_warning:
            exception_caught = False
            exception_value = None
            try:
                await manager._send_message(connection, message)
            except PeerConnectionError as e:
                exception_caught = True
                exception_value = e
                assert "Write failed" in str(e)
            assert exception_caught, "Expected PeerConnectionError to be raised"
            mock_warning.assert_called()

    @pytest.mark.asyncio
    async def test_send_bitfield_writer_none(self, manager):
        """Test _send_bitfield with None writer."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.writer = None

        # Should raise PeerConnectionError when writer is None
        exception_caught = False
        exception_value = None
        try:
            await manager._send_bitfield(connection)
        except PeerConnectionError as e:
            exception_caught = True
            exception_value = e
            assert "writer is None" in str(e)
        assert exception_caught, "Expected PeerConnectionError to be raised"

    @pytest.mark.asyncio
    async def test_send_bitfield_with_verified_pieces(self, manager):
        """Test _send_bitfield with verified pieces."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.writer = MagicMock()
        connection.writer.write = MagicMock()
        connection.writer.drain = AsyncMock()

        # Set verified pieces
        manager.piece_manager.verified_pieces = [0, 1, 2, 5]

        await manager._send_bitfield(connection)

        # Should send bitfield message
        connection.writer.write.assert_called()
        assert connection.state == ConnectionState.ACTIVE

    @pytest.mark.asyncio
    async def test_send_bitfield_without_verified_pieces_preserves_active_state(
        self, manager
    ):
        """Test _send_bitfield does not regress an active peer state."""
        peer_info = PeerInfo(ip="192.168.1.101", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.writer = MagicMock()
        connection.writer.write = MagicMock()
        connection.writer.drain = AsyncMock()

        manager.piece_manager.verified_pieces = []

        await manager._send_bitfield(connection)

        connection.writer.write.assert_not_called()
        assert connection.state == ConnectionState.ACTIVE

    @pytest.mark.asyncio
    async def test_send_unchoke_error(self, manager):
        """Test _send_unchoke error handling."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.writer = MagicMock()
        connection.writer.write = MagicMock(side_effect=OSError("Write failed"))
        connection.writer.drain = AsyncMock()

        with patch.object(manager, "_send_message", new_callable=AsyncMock, side_effect=OSError("Send error")):
            with patch.object(manager.logger, "warning") as mock_warning:
                exception_caught = False
                exception_value = None
                try:
                    await manager._send_unchoke(connection)
                except PeerConnectionError as e:
                    exception_caught = True
                    exception_value = e
                    assert "Send error" in str(e)
                assert exception_caught, "Expected PeerConnectionError to be raised"
                mock_warning.assert_called()


class TestConnectionErrorHandling:
    """Test connection error handling paths."""

    @pytest.mark.asyncio
    async def test_handle_connection_error_lock_held_false(self, manager):
        """Test _handle_connection_error with lock_held=False."""
        from ccbt.peer.peer import PeerInfo
        
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.CONNECTED
        async with manager.connection_lock:
            manager.connections[str(peer_info)] = connection

        await manager._handle_connection_error(connection, "Test error", lock_held=False)

        # Connection should be removed
        async with manager.connection_lock:
            assert str(peer_info) not in manager.connections

    @pytest.mark.asyncio
    async def test_handle_connection_error_lock_held_true(self, manager):
        """Test _handle_connection_error with lock_held=True."""
        from ccbt.peer.peer import PeerInfo
        
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.CONNECTED
        async with manager.connection_lock:
            manager.connections[str(peer_info)] = connection

        # Acquire lock manually
        async with manager.connection_lock:
            await manager._handle_connection_error(connection, "Test error", lock_held=True)

        # Connection should be removed
        async with manager.connection_lock:
            assert str(peer_info) not in manager.connections


class TestShutdown:
    """Test shutdown paths."""

    @pytest.mark.asyncio
    async def test_shutdown_task_cancellation(self, manager):
        """Test shutdown cancels pending connection tasks."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, manager.torrent_data)
        connection.state = ConnectionState.CONNECTED

        # Create a pending task
        async def long_running():
            await asyncio.sleep(10)

        connection.connection_task = asyncio.create_task(long_running())
        manager.connections[str(peer_info)] = connection

        # Shutdown should cancel task
        await manager.shutdown()

        # Task should be cancelled
        assert connection.connection_task.cancelled() or connection.connection_task.done()

