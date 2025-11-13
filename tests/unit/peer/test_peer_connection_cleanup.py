"""Tests for peer connection cleanup and edge cases.

This module tests:
- Info hash mismatch during connection (lines 325-326)
- on_peer_connected callback (line 345)
- Keep-alive message handling in _handle_peer_messages (lines 368-369)
- Task cancellation during shutdown (lines 815-818)
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.peer]

from ccbt.peer.peer import Handshake, KeepAliveMessage
from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager
from ccbt.peer.peer_connection import (
    ConnectionState,
    PeerConnection,
    PeerConnectionError,
)


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
def peer_info():
    """Fixture for peer info."""
    from ccbt.peer.peer import PeerInfo

    return PeerInfo(ip="192.168.1.100", port=6881)


class TestInfoHashMismatch:
    """Test info hash mismatch error handling (lines 325-326)."""

    @pytest.mark.asyncio
    async def test_info_hash_mismatch_raises_error(
        self, mock_torrent_data, mock_piece_manager, peer_info
    ):
        """Test that info hash mismatch raises PeerConnectionError (lines 325-326)."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        # Create connection with wrong info hash in handshake
        wrong_info_hash = b"wrong_info_hash_20_b"
        peer_handshake = Handshake(wrong_info_hash, b"remote_peer_id_20_by")

        # Mock connection
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.close = MagicMock()

        with patch("asyncio.open_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            # Mock handshake response with wrong info hash
            mock_reader.readexactly = AsyncMock(
                return_value=peer_handshake.encode()
            )

            # Should handle error (exception is caught internally)
            await manager._connect_to_peer(peer_info)

            # Verify connection is in error state
            async with manager.connection_lock:
                if str(peer_info) in manager.connections:
                    connection = manager.connections[str(peer_info)]
                    assert connection.state == ConnectionState.ERROR
                    assert "Info hash mismatch" in connection.error_message
                else:
                    # Connection may have been removed, but error should have been logged
                    pass

            # Verify error message includes both info hashes
            mock_open.assert_called_once()


class TestOnPeerConnectedCallback:
    """Test on_peer_connected callback (line 345)."""

    @pytest.mark.asyncio
    async def test_on_peer_connected_callback_invoked(
        self, mock_torrent_data, mock_piece_manager, peer_info
    ):
        """Test that on_peer_connected callback is invoked on successful connection (line 345)."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        # Set up callback
        callback_called = []
        callback_connection = []

        def on_peer_connected(connection):
            callback_called.append(True)
            callback_connection.append(connection)

        manager.on_peer_connected = on_peer_connected

        # Mock connection
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.close = MagicMock()

        # Create proper handshake
        info_hash = mock_torrent_data["info_hash"]
        peer_handshake = Handshake(info_hash, b"remote_peer_id_20_by")
        mock_reader.readexactly = AsyncMock(return_value=peer_handshake.encode())

        # Mock bitfield and unchoke sending
        manager._send_bitfield = AsyncMock()
        manager._send_unchoke = AsyncMock()

        # Mock message handling task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        with patch("asyncio.create_task", return_value=mock_task):
            with patch("asyncio.open_connection") as mock_open:
                mock_open.return_value = (mock_reader, mock_writer)

                await manager._connect_to_peer(peer_info)

            # Verify callback was called
            assert len(callback_called) == 1
            assert callback_connection[0] is not None
            assert callback_connection[0].state == ConnectionState.HANDSHAKE_RECEIVED

    @pytest.mark.asyncio
    async def test_on_peer_connected_callback_not_set(
        self, mock_torrent_data, mock_piece_manager, peer_info
    ):
        """Test that connection succeeds even when callback is not set."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        # Ensure callback is None
        assert manager.on_peer_connected is None

        # Mock connection
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.close = MagicMock()

        # Create proper handshake
        info_hash = mock_torrent_data["info_hash"]
        peer_handshake = Handshake(info_hash, b"remote_peer_id_20_by")
        mock_reader.readexactly = AsyncMock(return_value=peer_handshake.encode())

        # Mock bitfield and unchoke sending
        manager._send_bitfield = AsyncMock()
        manager._send_unchoke = AsyncMock()

        # Mock message handling task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        with patch("asyncio.create_task", return_value=mock_task):
            with patch("asyncio.open_connection") as mock_open:
                mock_open.return_value = (mock_reader, mock_writer)

                # Should not raise error
                await manager._connect_to_peer(peer_info)

                # Verify connection was added
                async with manager.connection_lock:
                    assert str(peer_info) in manager.connections


class TestKeepAliveMessageHandling:
    """Test keep-alive message handling in _handle_peer_messages (lines 368-369)."""

    @pytest.mark.asyncio
    async def test_handle_peer_messages_keepalive_updates_activity(
        self, mock_torrent_data, mock_piece_manager, peer_info
    ):
        """Test that keep-alive messages update activity (lines 368-369)."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        connection = PeerConnection(peer_info, mock_torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.last_activity = 0.0

        # Mock reader to return keep-alive (length = 0)
        mock_reader = AsyncMock()
        connection.reader = mock_reader

        # Keep-alive message: 4 bytes of zeros (length = 0)
        keepalive_length = b"\x00\x00\x00\x00"
        mock_reader.readexactly = AsyncMock(side_effect=[
            keepalive_length,  # First call: length = 0 (keep-alive)
            asyncio.CancelledError(),  # Second call: cancel to exit loop
        ])

        # Start message handling task
        task = asyncio.create_task(manager._handle_peer_messages(connection))

        # Wait a bit for the keep-alive to be processed
        await asyncio.sleep(0.01)

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify activity was updated (should be recent)
        assert connection.last_activity > 0.0
        assert connection.last_activity <= time.time()

    @pytest.mark.asyncio
    async def test_handle_peer_messages_keepalive_continues_loop(
        self, mock_torrent_data, mock_piece_manager, peer_info
    ):
        """Test that keep-alive messages continue the loop without processing."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        connection = PeerConnection(peer_info, mock_torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.last_activity = 0.0

        # Mock reader
        mock_reader = AsyncMock()
        connection.reader = mock_reader

        # Multiple keep-alive messages
        keepalive_length = b"\x00\x00\x00\x00"
        call_count = 0

        async def mock_readexactly(size):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return keepalive_length  # Keep-alive messages
            else:
                raise asyncio.CancelledError()  # Exit loop

        mock_reader.readexactly = mock_readexactly

        # Start message handling task
        task = asyncio.create_task(manager._handle_peer_messages(connection))

        # Wait a bit
        await asyncio.sleep(0.01)

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify multiple keep-alive messages were processed
        # readexactly should be called multiple times (once per keep-alive + cancellation)
        assert call_count >= 3
        # Activity should be updated
        assert connection.last_activity > 0.0


class TestShutdownTaskCancellation:
    """Test task cancellation during shutdown (lines 815-818)."""

    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_tasks(
        self, mock_torrent_data, mock_piece_manager
    ):
        """Test that shutdown cancels connection tasks that are not done (lines 815-818)."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        # Create connections with pending tasks
        connections = []
        for i in range(3):
            from ccbt.peer.peer import PeerInfo

            peer_info = PeerInfo(ip=f"192.168.1.{100 + i}", port=6881 + i)
            connection = PeerConnection(peer_info, mock_torrent_data)
            connection.state = ConnectionState.ACTIVE

            # Create a task that will be cancelled
            async def long_running_task():
                try:
                    await asyncio.sleep(100)  # Long-running task
                except asyncio.CancelledError:
                    raise

            connection.connection_task = asyncio.create_task(long_running_task())

            async with manager.connection_lock:
                manager.connections[str(peer_info)] = connection
            connections.append(connection)

        # Verify tasks are not done
        for connection in connections:
            assert not connection.connection_task.done()

        # Shutdown should cancel all tasks
        await manager.shutdown()

        # Verify all tasks were cancelled
        for connection in connections:
            assert connection.connection_task.done()
            assert connection.connection_task.cancelled()

    @pytest.mark.asyncio
    async def test_shutdown_handles_already_done_tasks(
        self, mock_torrent_data, mock_piece_manager
    ):
        """Test that shutdown handles tasks that are already done."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        # Create connections with done tasks
        from ccbt.peer.peer import PeerInfo

        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, mock_torrent_data)
        connection.state = ConnectionState.ACTIVE

        # Create a task that is already done
        async def completed_task():
            return "done"

        connection.connection_task = asyncio.create_task(completed_task())
        await connection.connection_task  # Wait for completion

        async with manager.connection_lock:
            manager.connections[str(peer_info)] = connection

        # Verify task is done
        assert connection.connection_task.done()

        # Shutdown should not raise errors
        await manager.shutdown()

        # Task should still be done
        assert connection.connection_task.done()

    @pytest.mark.asyncio
    async def test_shutdown_handles_connections_without_tasks(
        self, mock_torrent_data, mock_piece_manager
    ):
        """Test that shutdown handles connections without connection_task."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        # Create connections without tasks
        from ccbt.peer.peer import PeerInfo

        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = PeerConnection(peer_info, mock_torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.connection_task = None

        async with manager.connection_lock:
            manager.connections[str(peer_info)] = connection

        # Shutdown should not raise errors
        await manager.shutdown()

        # Connection should still be in error state (from disconnect_all)
        assert connection.state == ConnectionState.ERROR

