"""Tests for async peer connection manager."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.peer]

from ccbt.peer.peer import BitfieldMessage, HaveMessage, PeerInfo
from ccbt.peer.peer_connection import (
    AsyncPeerConnectionManager,
    ConnectionState,
    PeerConnection,
)


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
    return manager


@pytest.fixture
def peer_info():
    """Create test peer info."""
    return PeerInfo(ip="127.0.0.1", port=6881)


@pytest.fixture
async def peer_manager(mock_torrent_data, mock_piece_manager):
    """Create async peer connection manager."""
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager,
        max_connections=10,
    )
    return manager


@pytest.mark.asyncio
async def test_peer_manager_context_manager(mock_torrent_data, mock_piece_manager):
    """Test peer manager as context manager."""
    async with AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager,
    ) as manager:
        assert manager is not None
        # Manager should be ready for use


@pytest.mark.asyncio
async def test_connect_to_peers_success(peer_manager, peer_info):
    """Test successful peer connection."""
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]

    # Mock the connection process
    mock_reader = AsyncMock()
    mock_writer = AsyncMock()
    mock_writer.drain = AsyncMock()
    mock_reader.readexactly = AsyncMock(return_value=b"handshake_data" + b"x" * 54)  # 68 bytes total

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        with patch("ccbt.peer.Handshake.decode") as mock_decode:
            # Mock handshake validation
            mock_handshake = MagicMock()
            mock_handshake.info_hash = peer_manager.torrent_data["info_hash"]
            mock_handshake.peer_id = b"test_peer_id_20bytes"
            mock_decode.return_value = mock_handshake

            await peer_manager.connect_to_peers(peer_list)

            # Should have created a connection
            assert len(peer_manager.connections) == 1
            connection = list(peer_manager.connections.values())[0]
            assert connection.peer_info.ip == peer_info.ip
            assert connection.peer_info.port == peer_info.port


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
async def test_handle_bitfield_message(peer_manager, peer_info):
    """Test handling bitfield message."""
    # Create a connection
    connection = PeerConnection(peer_info, peer_manager.torrent_data)
    connection.state = ConnectionState.HANDSHAKE_RECEIVED
    connection.reader = AsyncMock()
    connection.writer = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.close = MagicMock()

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
    assert connection.state == ConnectionState.BITFIELD_RECEIVED
    assert callback_called


@pytest.mark.asyncio
async def test_handle_have_message(peer_manager, peer_info):
    """Test handling have message."""
    # Create a connection
    connection = PeerConnection(peer_info, peer_manager.torrent_data)
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
    # Create a connection
    connection = PeerConnection(peer_info, peer_manager.torrent_data)
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
    # Create a connection
    connection = PeerConnection(peer_info, peer_manager.torrent_data)
    connection.state = ConnectionState.ACTIVE
    connection.writer = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.close = MagicMock()

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Send interested message
    await peer_manager.send_interested(connection)

    # Check state
    assert connection.peer_state.am_interested is True


@pytest.mark.asyncio
async def test_request_piece(peer_manager, peer_info):
    """Test requesting a piece."""
    # Create a connection
    connection = PeerConnection(peer_info, peer_manager.torrent_data)
    connection.state = ConnectionState.ACTIVE
    connection.peer_state.am_choking = False
    connection.writer = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = MagicMock()
    connection.writer.drain = AsyncMock()
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
    # Create connections
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    connection1 = PeerConnection(peer1, peer_manager.torrent_data)
    connection1.state = ConnectionState.ACTIVE
    connection1.writer = AsyncMock()

    connection2 = PeerConnection(peer2, peer_manager.torrent_data)
    connection2.state = ConnectionState.ACTIVE
    connection2.writer = AsyncMock()

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
    # Create a connection without writer to avoid complex mocking
    connection = PeerConnection(peer_info, peer_manager.torrent_data)
    connection.state = ConnectionState.ACTIVE
    connection.writer = None  # No writer to avoid close/wait_closed issues
    connection.connection_task = None  # No active task to cancel

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Disconnect peer
    await peer_manager.disconnect_peer(peer_info)

    # Connection should be removed
    assert str(peer_info) not in peer_manager.connections


@pytest.mark.asyncio
async def test_disconnect_all(peer_manager):
    """Test disconnecting all peers."""
    # Create multiple connections
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    connection1 = PeerConnection(peer1, peer_manager.torrent_data)
    connection1.writer = None  # No writer to avoid close/wait_closed issues
    connection1.connection_task = None  # No active task to cancel

    connection2 = PeerConnection(peer2, peer_manager.torrent_data)
    connection2.writer = None  # No writer to avoid close/wait_closed issues
    connection2.connection_task = None  # No active task to cancel

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2

    # Disconnect all
    await peer_manager.disconnect_all()

    # All connections should be removed
    assert len(peer_manager.connections) == 0


@pytest.mark.asyncio
async def test_get_connected_peers(peer_manager):
    """Test getting connected peers."""
    # Create connections with different states
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    connection1 = PeerConnection(peer1, peer_manager.torrent_data)
    connection1.state = ConnectionState.ACTIVE

    connection2 = PeerConnection(peer2, peer_manager.torrent_data)
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
    # Create connections with different states
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    connection1 = PeerConnection(peer1, peer_manager.torrent_data)
    connection1.state = ConnectionState.ACTIVE

    connection2 = PeerConnection(peer2, peer_manager.torrent_data)
    connection2.state = ConnectionState.HANDSHAKE_SENT

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2

    # Get active peers
    active = peer_manager.get_active_peers()

    # Should only return active connection
    assert len(active) == 1
    assert active[0] == connection1


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
