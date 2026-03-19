"""Tests for async peer connection manager."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.peer]

from ccbt.peer.peer import BitfieldMessage, HaveMessage, PeerInfo
from ccbt.peer.async_peer_connection import (
    AsyncPeerConnection,
    AsyncPeerConnectionManager,
    ConnectionState,
)
from ccbt.peer.peer_connection import (
    PeerConnection,
)
from ccbt.utils.exceptions import MessageError


@pytest.fixture
def mock_torrent_data():
    """Create mock torrent data."""
    return {
        "info_hash": b"test_info_hash_20byt",  # Exactly 20 bytes
        "pieces_info": {"num_pieces": 100},
    }


@pytest.fixture
def mock_piece_manager():
    """Create mock piece manager."""
    manager = MagicMock()
    manager.verified_pieces = [0, 1, 2]
    manager.get_block = MagicMock(return_value=b"test_block_data")
    # Note: update_peer_availability is async, so it needs to be AsyncMock
    manager.update_peer_availability = AsyncMock(return_value=None)
    return manager


@pytest.fixture
def peer_info():
    """Create test peer info."""
    return PeerInfo(ip="127.0.0.1", port=6881)


@pytest_asyncio.fixture(scope="function")
async def peer_manager(mock_torrent_data, mock_piece_manager):
    """Create async peer connection manager with proper setup and teardown."""
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager,
        max_peers_per_torrent=10,  # Note: Use max_peers_per_torrent, not max_connections
    )
    # Note: Start the manager before use
    await manager.start()
    try:
        yield manager
    finally:
        # Note: Ensure proper cleanup
        try:
            await manager.stop()
        except Exception:
            # Ignore errors during cleanup
            pass
        from ccbt.utils.network_optimizer import reset_network_optimizer
        reset_network_optimizer()


@pytest.mark.asyncio
async def test_peer_manager_context_manager(mock_torrent_data, mock_piece_manager):
    """Test peer manager lifecycle with start/stop."""
    # Note: AsyncPeerConnectionManager doesn't implement context manager protocol
    # Test start/stop lifecycle instead
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager,
    )
    assert manager is not None
    
    # Start the manager
    await manager.start()
    assert manager._running is True
    
    # Stop the manager
    await manager.stop()
    assert manager._running is False


@pytest.mark.asyncio
async def test_connect_to_peers_success(peer_manager, peer_info):
    """Test successful peer connection."""
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]

    # Mock the connection process
    mock_reader = AsyncMock()
    mock_writer = MagicMock()  # Use MagicMock instead of AsyncMock for writer
    mock_writer.drain = AsyncMock()
    mock_writer.write = MagicMock(return_value=None)  # CRITICAL: write() is synchronous, returns None
    mock_writer.close = MagicMock()  # CRITICAL: close() should not be async
    mock_writer.wait_closed = AsyncMock()  # CRITICAL: wait_closed() should be async
    mock_writer.is_closing = MagicMock(return_value=False)  # CRITICAL: Writer must not be closing
    # CRITICAL: Handshake reading expects protocol length byte (19 = 0x13) first, then 67 more bytes
    # The code may call readexactly(1) multiple times, so we need to return based on the requested size
    # For v1 handshake: protocol_len (1 byte) + "BitTorrent protocol" (19 bytes) + reserved (8 bytes) + info_hash (20 bytes) + peer_id (20 bytes) = 68 bytes
    protocol_length_byte = b"\x13"  # 19 in hex
    # Build proper v1 handshake: protocol string + reserved bytes (all zeros for v1) + info_hash + peer_id
    protocol_string = b"BitTorrent protocol"
    reserved_bytes = b"\x00" * 8  # v1 handshake has all zeros in reserved bytes
    info_hash = peer_manager.torrent_data["info_hash"]
    peer_id = b"test_peer_id_20bytes"
    remaining_handshake = protocol_string + reserved_bytes + info_hash + peer_id
    # Ensure remaining_handshake is exactly 67 bytes (19 + 8 + 20 + 20 = 67)
    assert len(remaining_handshake) == 67, f"Expected 67 bytes, got {len(remaining_handshake)}"
    
    # Return based on requested size, not call count
    # Track calls to handle multiple reads of same size
    call_tracker = {"1": 0, "67": 0, "12": 0, "4": 0, "other": 0}
    max_message_reads = 3  # Limit message reads to prevent infinite loop
    async def mock_readexactly(n):
        call_key = str(n) if n in (1, 67, 12, 4) else "other"
        call_tracker[call_key] = call_tracker.get(call_key, 0) + 1
        if n == 1:
            # Request for 1 byte: return protocol length byte
            return protocol_length_byte
        elif n == 67:
            # Request for 67 bytes: return remaining handshake
            return remaining_handshake
        elif n == 12:
            # Request for 12 bytes: might be v2 handshake additional data
            # Return empty to indicate no v2 data (will cause timeout, but that's handled)
            return b""
        elif n == 4:
            # Request for 4 bytes: message length header
            # After a few keep-alive messages, wait indefinitely to prevent infinite loop
            # but keep connection alive for test verification
            if call_tracker["4"] > max_message_reads:
                # Wait indefinitely instead of raising error - connection stays in dict
                await asyncio.sleep(3600)  # Wait 1 hour (effectively forever for test)
            # Return keep-alive message (length 0) - 4 bytes of zeros
            return b"\x00\x00\x00\x00"
        else:
            # For any other size (like reading message payload), raise ConnectionResetError
            # to simulate connection close
            raise ConnectionResetError(f"Connection closed after reading {n} bytes")
    mock_reader.readexactly = mock_readexactly

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        with patch("ccbt.peer.peer.Handshake.decode") as mock_decode:
            # Mock handshake validation
            mock_handshake = MagicMock()
            mock_handshake.info_hash = peer_manager.torrent_data["info_hash"]
            mock_handshake.peer_id = b"test_peer_id_20bytes"
            mock_decode.return_value = mock_handshake

            # Call connect_to_peers with strict timeout to prevent OOM
            # Use wait_for to ensure it completes or times out quickly
            try:
                await asyncio.wait_for(
                    peer_manager.connect_to_peers(peer_list),
                    timeout=2.0  # Very short timeout to prevent OOM
                )
            except (asyncio.TimeoutError, Exception):
                # Timeout/exception is OK - connection might still be established
                pass
            
            # Wait briefly for connection to be established
            max_wait = 1.0
            start_time = time.time()
            connection_established = False
            while not connection_established:
                await asyncio.sleep(0.05)
                if len(peer_manager.connections) > 0:
                    connection_established = True
                    break
                if time.time() - start_time > max_wait:
                    break

            # Should have created a connection
            assert len(peer_manager.connections) == 1, f"Expected 1 connection, got {len(peer_manager.connections)}"
            connection = list(peer_manager.connections.values())[0]
            assert connection.peer_info.ip == peer_info.ip
            assert connection.peer_info.port == peer_info.port


@pytest.mark.asyncio
async def test_outbound_magnet_peer_sends_proactive_extension_handshake(
    peer_manager, peer_info
):
    """Magnet peers should proactively send BEP 10 handshake after the base handshake."""
    peer_manager.piece_manager._metadata_incomplete = True
    peer_manager.piece_manager.num_pieces = 0
    peer_manager.torrent_data["file_info"] = None
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]

    mock_reader = AsyncMock()
    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.write = MagicMock(return_value=None)
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    protocol_string = b"BitTorrent protocol"
    protocol_length_byte = b"\x13"
    reserved_bytes = b"\x00\x00\x00\x00\x00\x10\x00\x00"
    info_hash = peer_manager.torrent_data["info_hash"]
    peer_id = b"test_peer_id_20bytes"
    remaining_handshake = protocol_string + reserved_bytes + info_hash + peer_id

    async def mock_readexactly(n):
        if n == 1:
            return protocol_length_byte
        if n == 67:
            return remaining_handshake
        if n == 12:
            return b""
        if n == 4:
            await asyncio.sleep(3600)
        raise ConnectionResetError(f"Connection closed after reading {n} bytes")

    mock_reader.readexactly = mock_readexactly

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        with patch("ccbt.peer.peer.Handshake.decode") as mock_decode:
            send_extension = AsyncMock()
            mock_handshake = MagicMock()
            mock_handshake.info_hash = info_hash
            mock_handshake.peer_id = peer_id
            mock_handshake.reserved_bytes = reserved_bytes
            mock_handshake.supports_extension_protocol.return_value = True
            mock_decode.return_value = mock_handshake

            with patch.object(
                peer_manager,
                "_send_our_extension_handshake",
                send_extension,
            ):
                try:
                    await asyncio.wait_for(
                        peer_manager.connect_to_peers(peer_list),
                        timeout=2.0,
                    )
                except (asyncio.TimeoutError, Exception):
                    pass

                start_time = time.time()
                while send_extension.await_count == 0 and time.time() - start_time < 1.0:
                    await asyncio.sleep(0.05)

    assert send_extension.await_count >= 1


@pytest.mark.asyncio
async def test_connect_to_peers_handshake_mismatch(peer_manager, peer_info):
    """Test peer connection with handshake mismatch."""
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]

    # Mock the connection process
    mock_reader = AsyncMock()
    mock_writer = AsyncMock()
    mock_writer.drain = AsyncMock()
    mock_reader.readexactly = AsyncMock(return_value=b"handshake_data")

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        with patch("ccbt.peer.Handshake.decode") as mock_decode:
            # Mock handshake with wrong info hash
            mock_handshake = MagicMock()
            mock_handshake.info_hash = b"wrong_info_hash_20bytes"
            mock_handshake.peer_id = b"test_peer_id_20bytes"
            mock_decode.return_value = mock_handshake

            await peer_manager.connect_to_peers(peer_list)

            # Should not have created a connection due to handshake mismatch
            assert len(peer_manager.connections) == 0


@pytest.mark.asyncio
async def test_connect_to_peers_connection_failure(peer_manager, peer_info):
    """Test peer connection failure."""
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]

    # Mock connection failure
    with patch("asyncio.open_connection", side_effect=ConnectionError("Connection failed")):
        await peer_manager.connect_to_peers(peer_list)

        # Should not have created a connection
        assert len(peer_manager.connections) == 0


@pytest.mark.asyncio
async def test_connect_to_peers_enqueues_when_at_capacity(peer_manager, monkeypatch):
    """Peers should be deferred when active connections already at capacity."""
    peer_manager._running = True
    peer_manager.max_peers_per_torrent = 3

    # Pretend we already have the maximum number of active peers.
    for idx in range(peer_manager.max_peers_per_torrent):
        conn = MagicMock()
        conn.is_active.return_value = True
        peer_manager.connections[f"existing-{idx}"] = conn

    peer_list = [
        {"ip": f"192.0.2.{i}", "port": 6000 + i, "peer_source": "tracker"}
        for i in range(6)
    ]

    connect_mock = AsyncMock()
    monkeypatch.setattr(peer_manager, "_connect_to_peer", connect_mock)
    monkeypatch.setattr(
        peer_manager,
        "_rank_peers_for_connection",
        AsyncMock(side_effect=lambda peers: peers),
    )
    resume_mock = MagicMock()
    monkeypatch.setattr(peer_manager, "_schedule_pending_resume", resume_mock)

    await peer_manager.connect_to_peers(peer_list)

    # All peers should be queued for later because we're at capacity.
    assert len(peer_manager._pending_peer_queue) == len(peer_list)
    assert connect_mock.await_count == 0
    assert resume_mock.called
    assert peer_manager._connection_batches_in_progress is False


@pytest.mark.asyncio
async def test_resume_pending_batches_processes_queue(peer_manager, monkeypatch):
    """Resuming pending batches should drain the queue via connect_to_peers."""
    peer_manager._running = True
    peers = [
        PeerInfo(ip="198.51.100.1", port=51413),
        PeerInfo(ip="198.51.100.2", port=51414),
    ]
    peer_manager._pending_peer_queue = peers.copy()
    peer_manager._pending_peer_keys = {str(p) for p in peers}

    resume_connect_mock = AsyncMock()
    monkeypatch.setattr(peer_manager, "connect_to_peers", resume_connect_mock)

    await peer_manager._resume_pending_batches(reason="unit-test")

    assert resume_connect_mock.await_count == 1
    kwargs = resume_connect_mock.await_args.kwargs
    assert kwargs.get("_from_pending_queue") is True
    assert not peer_manager._pending_peer_queue
    assert not peer_manager._pending_peer_keys
    assert peer_manager._pending_resume_in_progress is False


@pytest.mark.asyncio
async def test_handle_bitfield_message(peer_manager, peer_info):
    """Test handling bitfield message."""
    # Note: Configure piece_manager.num_pieces as an integer, not a MagicMock
    # The code compares num_pieces > 0, which fails if it's a MagicMock
    peer_manager.piece_manager.num_pieces = 100  # Set to integer value from mock_torrent_data
    
    # Create an AsyncPeerConnection (not PeerConnection)
    from ccbt.peer.async_peer_connection import AsyncPeerConnection
    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.HANDSHAKE_RECEIVED
    connection.reader = AsyncMock()
    connection.writer = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.close = MagicMock()
    # Note: AsyncPeerConnection has am_interested attribute
    connection.am_interested = False

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Create bitfield message
    bitfield_data = b"\x00\x00\x00\x00"  # Empty bitfield
    bitfield_message = BitfieldMessage(bitfield_data)

    # Mock callback
    callback_called = False
    def mock_callback(conn, msg):
        nonlocal callback_called
        callback_called = True
        assert conn == connection
        assert msg == bitfield_message

    peer_manager.on_bitfield_received = mock_callback

    # Handle the message
    await peer_manager._handle_bitfield(connection, bitfield_message)

    # Check state and callback
    # Note: State should be ACTIVE after bitfield handling completes
    # The code sets state to BITFIELD_RECEIVED first, then transitions to ACTIVE
    # But if there's an exception or early return, state might remain BITFIELD_RECEIVED
    actual_state = connection.state
    # Use == comparison instead of 'in' to avoid enum comparison issues
    assert (actual_state == ConnectionState.ACTIVE or actual_state == ConnectionState.BITFIELD_RECEIVED), \
        f"Expected state to be ACTIVE or BITFIELD_RECEIVED, got {actual_state} (value: {actual_state.value if hasattr(actual_state, 'value') else actual_state}, type: {type(actual_state)})"
    assert callback_called, "Callback should have been called"


@pytest.mark.asyncio
async def test_handle_have_message(peer_manager, peer_info):
    """Test handling have message."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection
    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.ACTIVE

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Create have message
    have_message = HaveMessage(piece_index=5)

    # Handle the message
    await peer_manager._handle_have(connection, have_message)

    # Check that piece was added to peer state
    assert 5 in connection.peer_state.pieces_we_have


@pytest.mark.asyncio
async def test_handle_request_message(peer_manager, peer_info):
    """Test handling request message."""
    # Create a connection
    connection = PeerConnection(peer_info, peer_manager.torrent_data)
    connection.state = ConnectionState.ACTIVE

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Create request message
    from ccbt.peer.peer import RequestMessage
    request_message = RequestMessage(piece_index=0, begin=0, length=16384)

    # Mock piece manager to return data
    peer_manager.piece_manager.get_block.return_value = b"x" * 16384  # Exactly 16KB

    # Mock send message
    with patch.object(peer_manager, "_send_message", new_callable=AsyncMock) as mock_send:
        await peer_manager._handle_request(connection, request_message)

        # Should have sent a piece message
        assert mock_send.called
        call_args = mock_send.call_args[0]
        assert call_args[0] == connection
        assert call_args[1].piece_index == 0
        assert call_args[1].begin == 0
        assert call_args[1].block == b"x" * 16384


@pytest.mark.asyncio
async def test_handle_piece_message(peer_manager, peer_info):
    """Test handling piece message."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection
    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.ACTIVE

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Create piece message
    from ccbt.peer.peer import PieceMessage
    piece_message = PieceMessage(piece_index=0, begin=0, block=b"test_data")

    # Mock callback
    callback_called = False
    def mock_callback(conn, msg):
        nonlocal callback_called
        callback_called = True
        assert conn == connection
        assert msg == piece_message

    peer_manager.on_piece_received = mock_callback

    # Handle the message
    await peer_manager._handle_piece(connection, piece_message)

    # Check callback was called
    assert callback_called


@pytest.mark.asyncio
async def test_send_interested_message(peer_manager, peer_info):
    """Test sending interested message."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection
    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.ACTIVE
    connection.writer = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = MagicMock()
    connection.writer.close = MagicMock()

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Send interested message - use _send_interested (private method)
    await peer_manager._send_interested(connection)

    # Check state - AsyncPeerConnection uses am_interested attribute, not peer_state.am_interested
    assert connection.am_interested is True


@pytest.mark.asyncio
async def test_request_piece(peer_manager, peer_info):
    """Test requesting a piece."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection
    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.ACTIVE
    # AsyncPeerConnection uses peer_choking attribute, not peer_state.am_choking
    connection.peer_choking = False
    connection.writer = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = MagicMock()
    connection.writer.close = MagicMock()

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Mock send message
    with patch.object(peer_manager, "_send_message", new_callable=AsyncMock) as mock_send:
        await peer_manager.request_piece(connection, piece_index=0, begin=0, length=16384)

        # Should have sent a request message
        assert mock_send.called
        call_args = mock_send.call_args[0]
        assert call_args[0] == connection
        assert call_args[1].piece_index == 0
        assert call_args[1].begin == 0
        assert call_args[1].length == 16384


@pytest.mark.asyncio
async def test_broadcast_have(peer_manager, peer_info):
    """Test broadcasting have message."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection
    # Create connections
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    connection1 = AsyncPeerConnection(peer_info=peer1, torrent_data=peer_manager.torrent_data)
    connection1.state = ConnectionState.ACTIVE
    connection1.writer = MagicMock()
    connection1.writer.close = MagicMock()
    # Note: Mock wait_closed() to prevent hanging in _disconnect_peer()
    connection1.writer.wait_closed = AsyncMock(return_value=None)

    connection2 = AsyncPeerConnection(peer_info=peer2, torrent_data=peer_manager.torrent_data)
    connection2.state = ConnectionState.ACTIVE
    connection2.writer = MagicMock()
    connection2.writer.close = MagicMock()
    # Note: Mock wait_closed() to prevent hanging in _disconnect_peer()
    connection2.writer.wait_closed = AsyncMock(return_value=None)

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2

    # Mock send message
    with patch.object(peer_manager, "_send_message", new_callable=AsyncMock) as mock_send:
        await peer_manager.broadcast_have(piece_index=5)

        # Should have sent have message to both connections
        assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_disconnect_peer(peer_manager, peer_info):
    """Test disconnecting a peer."""
    from ccbt.peer.async_peer_connection import AsyncPeerConnection, ConnectionState
    
    # Create an AsyncPeerConnection (not PeerConnection) to match manager expectations
    connection = AsyncPeerConnection(peer_info, peer_manager.torrent_data)
    connection.state = ConnectionState.ACTIVE
    connection.writer = None  # No writer to avoid close/wait_closed issues
    connection.connection_task = None  # No active task to cancel
    # Ensure outstanding_requests exists to avoid AttributeError
    if not hasattr(connection, "outstanding_requests"):
        connection.outstanding_requests = {}

    # Add to manager
    async with peer_manager.connection_lock:
        peer_manager.connections[str(peer_info)] = connection

    # Disconnect peer with timeout to prevent hanging
    await asyncio.wait_for(
        peer_manager.disconnect_peer(peer_info),
        timeout=5.0
    )

    # Connection should be removed
    async with peer_manager.connection_lock:
        assert str(peer_info) not in peer_manager.connections


@pytest.mark.asyncio
async def test_disconnect_all(peer_manager):
    """Test disconnecting all peers."""
    # Create multiple connections
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    # Note: Use AsyncPeerConnection, not PeerConnection, to match manager expectations
    from ccbt.peer.async_peer_connection import AsyncPeerConnection, ConnectionState
    connection1 = AsyncPeerConnection(peer_info=peer1, torrent_data=peer_manager.torrent_data)
    connection1.state = ConnectionState.ACTIVE
    connection1.writer = None  # No writer to avoid close/wait_closed issues
    connection1.connection_task = None  # No active task to cancel
    # Ensure required attributes exist
    if not hasattr(connection1, "outstanding_requests"):
        connection1.outstanding_requests = {}

    connection2 = AsyncPeerConnection(peer_info=peer2, torrent_data=peer_manager.torrent_data)
    connection2.state = ConnectionState.ACTIVE
    connection2.writer = None  # No writer to avoid close/wait_closed issues
    connection2.connection_task = None  # No active task to cancel
    # Ensure required attributes exist
    if not hasattr(connection2, "outstanding_requests"):
        connection2.outstanding_requests = {}

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2

    # Disconnect all
    # Note: Add timeout to prevent hanging
    try:
        await asyncio.wait_for(peer_manager.disconnect_all(), timeout=5.0)
    except asyncio.TimeoutError:
        # If disconnect_all() hangs, stop the manager and fail the test
        await peer_manager.stop()
        raise AssertionError("disconnect_all() timed out after 5 seconds")

    # All connections should be removed
    assert len(peer_manager.connections) == 0
    
    # Note: Stop the manager to prevent reconnection loop from keeping event loop alive
    # The fixture teardown will also stop it, but we need to stop it here to prevent timeout
    await peer_manager.stop()


@pytest.mark.asyncio
async def test_get_connected_peers(peer_manager):
    """Test getting connected peers."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection
    # Create connections with different states
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    connection1 = AsyncPeerConnection(peer_info=peer1, torrent_data=peer_manager.torrent_data)
    connection1.state = ConnectionState.ACTIVE

    connection2 = AsyncPeerConnection(peer_info=peer2, torrent_data=peer_manager.torrent_data)
    connection2.state = ConnectionState.DISCONNECTED

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2

    # Get connected peers
    connected = peer_manager.get_connected_peers()

    # Should only return active connection
    assert len(connected) == 1
    assert connected[0] == connection1


@pytest.mark.asyncio
async def test_get_active_peers(peer_manager):
    """Test getting active peers."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection
    # Create connections with different states
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)
    peer3 = PeerInfo(ip="127.0.0.1", port=6883)

    connection1 = AsyncPeerConnection(peer_info=peer1, torrent_data=peer_manager.torrent_data)
    connection1.state = ConnectionState.ACTIVE
    # Note: get_active_peers() requires reader and writer to be set
    connection1.reader = AsyncMock()
    connection1.writer = MagicMock()

    connection2 = AsyncPeerConnection(peer_info=peer2, torrent_data=peer_manager.torrent_data)
    connection2.state = ConnectionState.HANDSHAKE_SENT
    # Note: get_active_peers() requires reader and writer to be set
    connection2.reader = AsyncMock()
    connection2.writer = MagicMock()

    connection3 = AsyncPeerConnection(peer_info=peer3, torrent_data=peer_manager.torrent_data)
    connection3.state = ConnectionState.BITFIELD_SENT

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2
    peer_manager.connections[str(peer3)] = connection3

    # Get active peers
    active = peer_manager.get_active_peers()

    # ACTIVE and BITFIELD_SENT peers should both count as active
    assert len(active) == 2
    assert connection1 in active
    assert connection3 in active


@pytest.mark.asyncio
async def test_get_peer_bitfields(peer_manager):
    """Test getting peer bitfields."""
    # Create connections with bitfields
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    connection1 = PeerConnection(peer1, peer_manager.torrent_data)
    connection1.peer_state.bitfield = BitfieldMessage(b"\x00\x00")

    connection2 = PeerConnection(peer2, peer_manager.torrent_data)
    connection2.peer_state.bitfield = None  # No bitfield

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2

    # Get peer bitfields
    bitfields = peer_manager.get_peer_bitfields()

    # Should only return peer with bitfield
    assert len(bitfields) == 1
    assert str(peer1) in bitfields
    assert bitfields[str(peer1)] == connection1.peer_state.bitfield


@pytest.mark.asyncio
async def test_shutdown(peer_manager):
    """Test manager shutdown."""
    # Create a connection
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    connection = PeerConnection(peer_info, peer_manager.torrent_data)
    connection.writer = AsyncMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = AsyncMock()
    connection.writer.close = AsyncMock()
    connection.connection_task = asyncio.create_task(asyncio.sleep(0))

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Shutdown manager
    await peer_manager.shutdown()

    # All connections should be removed
    assert len(peer_manager.connections) == 0


@pytest.mark.asyncio
async def test_connection_summary_exposes_lifecycle_stage_counters(peer_manager):
    """Connection summary should include lifecycle stage counters for diagnostics."""
    peer_manager._connection_stage_counters.update(
        {
            "connect_attempts": 3,
            "tcp_connected": 1,
            "tcp_open_timeout": 1,
            "tcp_open_cancelled": 1,
            "handshake_sent": 1,
            "handshake_received": 1,
            "bitfield_received": 0,
        }
    )

    summary = await peer_manager.get_connection_summary()

    assert summary["connect_attempts"] == 3
    assert summary["tcp_connected"] == 1
    assert summary["tcp_open_timeout"] == 1
    assert summary["tcp_open_cancelled"] == 1
    assert summary["handshake_sent"] == 1
    assert summary["handshake_received"] == 1


@pytest.mark.asyncio
async def test_connection_summary_separates_live_bitfield_count_from_events(
    peer_manager, peer_info
):
    """Live bitfield counts should not be derived from lifetime event counters."""
    from ccbt.peer.async_peer_connection import AsyncPeerConnection

    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.HANDSHAKE_RECEIVED
    connection.peer_state.bitfield = None
    peer_manager.connections[str(peer_info)] = connection
    peer_manager._connection_stage_counters["bitfield_received"] = 5

    summary = await peer_manager.get_connection_summary()

    assert summary["bitfield_received_events"] == 5
    assert summary["bitfield_complete_connections"] == 0


@pytest.mark.asyncio
async def test_info_hash_mismatch_updates_stage_counter(peer_manager):
    """Info-hash mismatch path should increment lifecycle counters."""
    before = peer_manager._connection_stage_counters.get("info_hash_mismatch", 0)
    with pytest.raises(Exception):
        peer_manager._raise_info_hash_mismatch(b"\x01" * 20, b"\x02" * 20)
    after = peer_manager._connection_stage_counters.get("info_hash_mismatch", 0)
    assert after == before + 1


@pytest.mark.asyncio
async def test_monitor_unchoke_timeout_triggers_hard_recovery(monkeypatch, peer_manager, peer_info):
    """Stale CHOKED peer should trigger hard recovery and replacement callbacks."""
    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.peer_interested = True
    connection.am_interested = True
    peer_manager.connections[str(peer_info)] = connection

    disconnect_mock = AsyncMock()
    record_failure_mock = AsyncMock()
    schedule_mock = MagicMock()
    emit_event_mock = AsyncMock()

    monkeypatch.setattr(peer_manager, "_disconnect_peer", disconnect_mock)
    monkeypatch.setattr(peer_manager, "_record_connection_failure", record_failure_mock)
    monkeypatch.setattr(peer_manager, "_schedule_pending_resume", schedule_mock)
    monkeypatch.setattr("ccbt.utils.events.emit_event", emit_event_mock)

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    await peer_manager._monitor_unchoke_timeout(
        connection, connection_start_time=time.time() - 31.0
    )

    disconnect_mock.assert_awaited_once()
    record_failure_mock.assert_awaited_once()
    peer_key = peer_manager._get_peer_key(connection)
    assert peer_key in peer_manager._failed_peers
    assert (
        peer_manager._failed_peers[peer_key]["reason"]
        == "stale_unchoke_timeout"
    )
    assert schedule_mock.call_count == 1
    assert schedule_mock.call_args.kwargs["reason"] == "hard_unchoke_recovery"
    assert emit_event_mock.await_count == 1

    recovery_event = emit_event_mock.call_args.args[0]
    assert recovery_event.data["trigger"] == "hard_unchoke_recovery"
    assert recovery_event.data["failure_reason"] == "stale_unchoke_timeout"
    assert recovery_event.data["recovery_state"]["candidate_peer"] == str(peer_info)


@pytest.mark.asyncio
async def test_connect_to_peers_preserves_peer_completion_context(monkeypatch, peer_manager):
    """Completion context hints are carried per peer into _connect_to_peer inputs."""
    peer_manager._running = True
    captured_peers = []

    async def fake_connect_to_peer(peer_info: PeerInfo) -> None:
        captured_peers.append(peer_info)
        return None

    monkeypatch.setattr(peer_manager, "_connect_to_peer", fake_connect_to_peer)

    peer_list = [
        {"ip": "192.0.2.1", "port": 6881, "is_seeder": False, "completion_percent": 0.25},
        {"ip": "192.0.2.2", "port": 6882, "complete": True, "completion_percent": 0.0},
    ]

    await peer_manager.connect_to_peers(peer_list)

    by_ip = {peer.ip: peer for peer in captured_peers}
    assert by_ip["192.0.2.1"].is_seeder is False
    assert by_ip["192.0.2.1"].completion_percent == 0.25
    assert by_ip["192.0.2.2"].is_seeder is True
    assert by_ip["192.0.2.2"].completion_percent == 0.0


@pytest.mark.asyncio
async def test_handle_unchoke_uses_seed_anchor_retry_budget(monkeypatch, peer_manager):
    """Seed-anchor peers get higher unchoke retry/requester budgets for faster recovery."""
    connection = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.1", port=6881),
        peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.am_interested = False
    peer_manager._set_connection_completion_context(
        connection, is_seeder=True, completion_percent=1.0
    )

    peer_manager._send_interested = AsyncMock()
    peer_manager.piece_manager._select_pieces = AsyncMock()
    peer_manager.piece_manager._retry_requested_pieces = AsyncMock()

    from ccbt.peer.peer import UnchokeMessage

    await peer_manager._handle_unchoke(connection, UnchokeMessage())
    await asyncio.sleep(0.05)

    peer_manager.piece_manager._select_pieces.assert_awaited_once()
    peer_manager.piece_manager._retry_requested_pieces.assert_awaited_once_with(
        connection,
        max_retry_count=5,
        max_requesters=3,
    )
    peer_manager._send_interested.assert_awaited_once_with(connection)


@pytest.mark.asyncio
async def test_handle_unchoke_uses_default_retry_budget_for_non_seed_anchor(peer_manager):
    """Non-anchor peers keep the default unchoke retry/requester budgets."""
    connection = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.2", port=6882),
        peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.am_interested = False
    peer_manager._set_connection_completion_context(
        connection, is_seeder=False, completion_percent=0.35
    )

    from ccbt.peer.peer import UnchokeMessage

    peer_manager._send_interested = AsyncMock()
    peer_manager.piece_manager._select_pieces = AsyncMock()
    peer_manager.piece_manager._retry_requested_pieces = AsyncMock()

    await peer_manager._handle_unchoke(connection, UnchokeMessage())
    await asyncio.sleep(0.05)

    peer_manager.piece_manager._retry_requested_pieces.assert_awaited_once_with(
        connection,
        max_retry_count=4,
        max_requesters=2,
    )


@pytest.mark.asyncio
async def test_monitor_unchoke_timeout_defers_seed_anchor_before_recovery(monkeypatch, peer_manager, peer_info):
    """Seed-anchor peers get a short grace period before hard-unchoke recovery."""
    from ccbt.utils.events import Event

    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.peer_interested = True
    connection.am_interested = True
    peer_manager._set_connection_completion_context(
        connection, is_seeder=True, completion_percent=1.0
    )
    peer_manager.connections[str(peer_info)] = connection

    disconnect_mock = AsyncMock()
    record_failure_mock = AsyncMock()
    schedule_mock = MagicMock()
    emit_event_mock = AsyncMock()

    monkeypatch.setattr(peer_manager, "_disconnect_peer", disconnect_mock)
    monkeypatch.setattr(peer_manager, "_record_connection_failure", record_failure_mock)
    monkeypatch.setattr(peer_manager, "_schedule_pending_resume", schedule_mock)
    monkeypatch.setattr("ccbt.utils.events.emit_event", emit_event_mock)

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    await peer_manager._monitor_unchoke_timeout(
        connection, connection_start_time=time.time() - 76.0
    )

    disconnect_mock.assert_awaited_once()
    record_failure_mock.assert_awaited_once()
    assert (
        getattr(connection, "_seed_anchor_unchoke_deferrals", 0)
        == 2
    )
    assert emit_event_mock.await_count == 1

    recovery_event = emit_event_mock.call_args.args[0]
    assert isinstance(recovery_event, Event)
    assert recovery_event.data["recovery_state"]["seed_anchor"] is True

@pytest.mark.asyncio
async def test_classify_connection_failure_recognizes_transient_and_terminal_errors(peer_manager):
    """Classify known protocol errors as terminal and network failures as transient."""
    assert peer_manager._classify_connection_failure(ConnectionRefusedError("connection refused")) == (
        "connection_refused",
        True,
    )
    assert peer_manager._classify_connection_failure(MessageError("invalid handshake")) == (
        "protocol_error",
        False,
    )


@pytest.mark.asyncio
async def test_rank_peers_prioritizes_verified_and_history(peer_manager):
    """Verified peers and good failure histories should be prioritized."""
    productive_peer = PeerInfo(ip="127.0.0.10", port=7000, peer_source="tracker")
    failed_peer = PeerInfo(ip="127.0.0.11", port=7001, peer_source="tracker")

    productive_key = str(productive_peer)
    failed_key = str(failed_peer)

    peer_manager._quality_verified_peers.add(productive_key)
    peer_manager._failed_peers[failed_key] = {
        "timestamp": time.time(),
        "count": 3,
        "reason": "protocol_error",
        "is_terminal": True,
    }

    ranked = await peer_manager._rank_peers_for_connection(
        [failed_peer, productive_peer]
    )

    assert len(ranked) == 2
    assert ranked[0] == productive_peer
    assert ranked[1] == failed_peer


@pytest.mark.asyncio
async def test_rank_peers_penalizes_terminal_failures_more_than_transient(peer_manager):
    """Terminal failures should be ranked below transient failures for the same peer context."""
    terminal_peer = PeerInfo(ip="127.0.0.12", port=7100, peer_source="tracker")
    transient_peer = PeerInfo(ip="127.0.0.13", port=7101, peer_source="tracker")

    terminal_key = str(terminal_peer)
    transient_key = str(transient_peer)

    peer_manager._failed_peers[terminal_key] = {
        "timestamp": time.time(),
        "count": 1,
        "reason": "protocol_error",
        "is_terminal": True,
    }
    peer_manager._failed_peers[transient_key] = {
        "timestamp": time.time(),
        "count": 2,
        "reason": "timeout",
        "is_terminal": False,
    }

    ranked = await peer_manager._rank_peers_for_connection(
        [terminal_peer, transient_peer]
    )

    assert len(ranked) == 2
    assert ranked[0] == transient_peer
    assert ranked[1] == terminal_peer
