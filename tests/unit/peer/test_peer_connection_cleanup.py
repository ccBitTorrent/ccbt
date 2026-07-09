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

pytestmark = [
    pytest.mark.unit,
    pytest.mark.peer,
    pytest.mark.skip(
        reason="Deprecated legacy compatibility suite; replaced by async connection contracts."
    ),
]

from ccbt.peer.async_peer_connection import (
    AsyncPeerConnection,
    AsyncPeerConnectionManager,
    ConnectionState,
    PeerConnectionError,
)
from ccbt.peer.peer import Handshake


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

        # Note: Start the manager before connecting
        await manager.start()

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
        # Note: Configure is_closing() to return False so connection can proceed
        mock_writer.is_closing = MagicMock(return_value=False)

        with patch("asyncio.open_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            # Mock handshake response with wrong info hash
            # Note: Mock readexactly to handle protocol length (1 byte) then remaining (67 bytes)
            handshake_calls = {"protocol_len": False, "remaining": False}
            async def readexactly_side_effect(n):
                if n == 1 and not handshake_calls["protocol_len"]:
                    handshake_calls["protocol_len"] = True
                    return peer_handshake.encode()[:1]
                if n == 67 and not handshake_calls["remaining"]:
                    handshake_calls["remaining"] = True
                    return peer_handshake.encode()[1:68]
                # After handshake, raise IncompleteReadError to stop message loop
                raise asyncio.IncompleteReadError(b"", n)
            mock_reader.readexactly = readexactly_side_effect

            # Info hash mismatch should raise PeerConnectionError
            # Catch the exception manually (pytest.raises doesn't work reliably with async functions)
            exception_caught = False
            exception_value = None
            try:
                await manager._connect_to_peer(peer_info)
            except PeerConnectionError as e:
                exception_caught = True
                exception_value = e
                # Verify exception message contains expected text
                assert "Info hash mismatch" in str(e), f"Expected 'Info hash mismatch' in error message, got: {e}"

            # Verify exception was raised
            assert exception_caught, "Expected PeerConnectionError to be raised for info hash mismatch"

            # Verify connection was attempted (open_connection was called at least once)
            # Note: May be called multiple times due to reconnection attempts
            assert mock_open.call_count >= 1, f"Expected open_connection to be called at least once, got {mock_open.call_count}"

            # Verify connection is not in connections dict (exception was raised before adding)
            async with manager.connection_lock:
                assert str(peer_info) not in manager.connections

        # Note: Stop the manager to clean up
        await manager.stop()


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

        # Note: Start the manager before connecting
        await manager.start()

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
        # Note: Configure is_closing() to return False so connection can proceed
        mock_writer.is_closing = MagicMock(return_value=False)

        # Create proper handshake
        info_hash = mock_torrent_data["info_hash"]
        peer_handshake = Handshake(info_hash, b"remote_peer_id_20_by")
        proper_handshake_data = peer_handshake.encode()  # 68 bytes

        # Note: Mock readexactly to handle protocol length (1 byte) then remaining (67 bytes)
        handshake_calls = {"protocol_len": False, "remaining": False}
        async def readexactly_side_effect(n):
            if n == 1 and not handshake_calls["protocol_len"]:
                handshake_calls["protocol_len"] = True
                return proper_handshake_data[:1]
            if n == 67 and not handshake_calls["remaining"]:
                handshake_calls["remaining"] = True
                return proper_handshake_data[1:68]
            # After handshake, raise IncompleteReadError to stop message loop
            import asyncio
            raise asyncio.IncompleteReadError(b"", n)
        mock_reader.readexactly = readexactly_side_effect

        # Mock bitfield and unchoke sending
        manager._send_bitfield = AsyncMock()
        manager._send_unchoke = AsyncMock()

        # Note: Mock _handle_peer_messages to prevent hanging, but let create_task work normally
        async def mock_handle_peer_messages(connection):
            """Mock message handler that doesn't hang."""
            # Just return immediately - don't actually handle messages
            await asyncio.sleep(0.001)

        manager._handle_peer_messages = mock_handle_peer_messages

        with patch("asyncio.open_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await manager._connect_to_peer(peer_info)

            # Note: Wait for callback to be called (connection is async)
            import asyncio
            max_wait = 0.5  # Increased wait time
            start_time = asyncio.get_event_loop().time()
            elapsed = 0.0
            while len(callback_called) == 0:
                await asyncio.sleep(0.01)  # Longer sleep interval
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > max_wait:
                    break

        # Verify callback was called (may be called multiple times during connection setup)
        assert len(callback_called) >= 1, f"Callback not called (waited {elapsed:.3f}s, connections: {list(manager.connections.keys())})"
        assert callback_connection[0] is not None
        # Note: State might be BITFIELD_SENT or ACTIVE after handshake, not just HANDSHAKE_RECEIVED
        # Use .value for comparison to avoid enum comparison issues
        state_value = callback_connection[0].state.value if hasattr(callback_connection[0].state, "value") else str(callback_connection[0].state)
        valid_states = [s.value if hasattr(s, "value") else str(s) for s in (ConnectionState.HANDSHAKE_RECEIVED, ConnectionState.BITFIELD_SENT, ConnectionState.ACTIVE)]
        assert state_value in valid_states, f"Connection state {state_value} not in valid states {valid_states}"

        # Note: Stop the manager to clean up
        await manager.stop()

    @pytest.mark.asyncio
    async def test_on_peer_connected_callback_not_set(
        self, mock_torrent_data, mock_piece_manager, peer_info
    ):
        """Test that connection succeeds even when callback is not set."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        # Note: Start the manager before connecting
        await manager.start()

        # Ensure callback is None
        assert manager.on_peer_connected is None

        # Mock connection
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.is_closing = MagicMock(return_value=False)  # Note: Ensure writer is not closing

        # Create proper handshake
        info_hash = mock_torrent_data["info_hash"]
        peer_handshake = Handshake(info_hash, b"remote_peer_id_20_by")
        proper_handshake_data = peer_handshake.encode()  # 68 bytes

        # Note: Mock readexactly to handle protocol length (1 byte) then remaining (67 bytes)
        handshake_calls = {"protocol_len": False, "remaining": False}
        async def readexactly_side_effect(n):
            if n == 1 and not handshake_calls["protocol_len"]:
                handshake_calls["protocol_len"] = True
                return proper_handshake_data[:1]
            if n == 67 and not handshake_calls["remaining"]:
                handshake_calls["remaining"] = True
                return proper_handshake_data[1:68]
            # After handshake, raise IncompleteReadError to stop message loop
            import asyncio
            raise asyncio.IncompleteReadError(b"", n)
        mock_reader.readexactly = readexactly_side_effect

        # Mock bitfield and unchoke sending
        manager._send_bitfield = AsyncMock()
        manager._send_unchoke = AsyncMock()

        # Note: Mock _handle_peer_messages to prevent hanging, but let create_task work normally
        async def mock_handle_peer_messages(connection):
            """Mock message handler that doesn't hang."""
            # Just return immediately - don't actually handle messages
            await asyncio.sleep(0.001)

        manager._handle_peer_messages = mock_handle_peer_messages

        with patch("asyncio.open_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            # Should not raise error
            await manager._connect_to_peer(peer_info)

            # Note: Wait for connection to be added (similar to other tests)
            import asyncio
            max_wait = 0.5  # Increased wait time
            start_time = asyncio.get_event_loop().time()
            connection_found = False
            peer_key = f"{peer_info.ip}:{peer_info.port}"
            iterations = 0
            while not connection_found:
                async with manager.connection_lock:
                    connection_found = peer_key in manager.connections
                if connection_found:
                    break
                if iterations > 0:
                    await asyncio.sleep(0.01)  # Longer sleep interval
                iterations += 1
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > max_wait:
                    break

            # Verify connection was added
            async with manager.connection_lock:
                assert peer_key in manager.connections, f"Connection {peer_key} not found in {list(manager.connections.keys())}"

        # Note: Stop the manager to clean up
        await manager.stop()


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

        connection = AsyncPeerConnection(peer_info, mock_torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.stats.last_activity = 0.0

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
        assert connection.stats.last_activity > 0.0
        assert connection.stats.last_activity <= time.time()

    @pytest.mark.asyncio
    async def test_handle_peer_messages_keepalive_continues_loop(
        self, mock_torrent_data, mock_piece_manager, peer_info
    ):
        """Test that keep-alive messages continue the loop without processing."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        connection = AsyncPeerConnection(peer_info, mock_torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.stats.last_activity = 0.0

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
        assert connection.stats.last_activity > 0.0


class TestStopTaskCancellation:
    """Test task cancellation during stop (lines 815-818)."""

    @pytest.mark.asyncio
    async def test_stop_cancels_pending_tasks(
        self, mock_torrent_data, mock_piece_manager
    ):
        """Test that stop cancels connection tasks that are not done (lines 815-818)."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        # Create connections with pending tasks
        connections = []
        for i in range(3):
            from ccbt.peer.peer import PeerInfo

            peer_info = PeerInfo(ip=f"192.168.1.{100 + i}", port=6881 + i)
            connection = AsyncPeerConnection(peer_info, mock_torrent_data)
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
        await manager.stop()

        # Verify all tasks were cancelled
        for connection in connections:
            assert connection.connection_task.done()
            assert connection.connection_task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_handles_already_done_tasks(
        self, mock_torrent_data, mock_piece_manager
    ):
        """Test that stop handles tasks that are already done."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        # Create connections with done tasks
        from ccbt.peer.peer import PeerInfo

        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, mock_torrent_data)
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
        await manager.stop()

        # Task should still be done
        assert connection.connection_task.done()

    @pytest.mark.asyncio
    async def test_stop_handles_connections_without_tasks(
        self, mock_torrent_data, mock_piece_manager
    ):
        """Test that stop handles connections without connection_task."""
        manager = AsyncPeerConnectionManager(
            mock_torrent_data, mock_piece_manager
        )

        # Create connections without tasks
        from ccbt.peer.peer import PeerInfo

        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        connection = AsyncPeerConnection(peer_info, mock_torrent_data)
        connection.state = ConnectionState.ACTIVE
        connection.connection_task = None

        async with manager.connection_lock:
            manager.connections[str(peer_info)] = connection

        # Shutdown should not raise errors
        await manager.stop()

        # Connection should still be in error state (from disconnect_all)
        assert connection.state == ConnectionState.ERROR

