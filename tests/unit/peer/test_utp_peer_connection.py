"""Tests for uTP Peer Connection lifecycle (lines 162-338 of utp_peer.py).

Covers:
- UTPPeerConnection initialization
- Connection establishment and error handling
- Disconnect and cleanup
- Message receiving loop
- Statistics updates
- Connection state checks
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.peer.async_peer_connection import ConnectionState
from ccbt.peer.peer import PeerState
from ccbt.peer.utp_peer import UTPPeerConnection, UTPStreamReader, UTPStreamWriter
from ccbt.transport.utp import UTPConnection, UTPConnectionState

pytestmark = [pytest.mark.unit, pytest.mark.peer]


@pytest.fixture
def peer_info():
    """Create test peer info."""
    from ccbt.models import PeerInfo

    return PeerInfo(ip="127.0.0.1", port=6881)


@pytest.fixture
def mock_torrent_data():
    """Create mock torrent data."""
    return {
        "info_hash": b"test_info_hash_20byt",  # 20 bytes
        "pieces_info": {"num_pieces": 100},
    }


@pytest.fixture
def mock_utp_connection():
    """Create a mock uTP connection."""
    conn = MagicMock(spec=UTPConnection)
    conn.state = UTPConnectionState.CONNECTED
    conn.bytes_received = 1024
    conn.bytes_sent = 512
    conn.last_recv_time = time.perf_counter()
    conn.receive = AsyncMock(return_value=b"")
    conn.send = AsyncMock()
    conn.close = AsyncMock()
    conn.initialize_transport = AsyncMock()
    conn.connect = AsyncMock()
    return conn


class TestUTPPeerConnectionInit:
    """Tests for UTPPeerConnection initialization (lines 158-180)."""

    def test_post_init_sets_defaults(self, peer_info, mock_torrent_data):
        """Test __post_init__ sets default attributes (lines 158-169)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        assert isinstance(conn.peer_state, PeerState)
        assert conn.stats is not None
        assert conn.message_decoder is not None
        assert conn.state == ConnectionState.DISCONNECTED
        assert conn.utp_connection is None

    def test_post_init_state_map(self, peer_info, mock_torrent_data):
        """Test state map is created (lines 172-180)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        assert UTPConnectionState.IDLE in conn._state_map
        assert UTPConnectionState.CONNECTED in conn._state_map
        assert UTPConnectionState.FIN_SENT in conn._state_map
        assert UTPConnectionState.CLOSED in conn._state_map
        assert UTPConnectionState.RESET in conn._state_map


class TestUTPPeerConnectionConnect:
    """Tests for UTPPeerConnection.connect() (lines 182-241)."""

    @pytest.mark.asyncio
    async def test_connect_success(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test successful connection (lines 182-231)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        # Mock UTPConnection class
        with patch("ccbt.peer.utp_peer.UTPConnection", return_value=mock_utp_connection):
            # Mock the connection to become CONNECTED quickly
            async def mock_connect():
                await asyncio.sleep(0.01)
                mock_utp_connection.state = UTPConnectionState.CONNECTED

            mock_utp_connection.connect = AsyncMock(side_effect=mock_connect)

            await conn.connect()

            assert conn.state == ConnectionState.CONNECTED
            assert conn.utp_connection is not None
            assert isinstance(conn.reader, UTPStreamReader)
            assert isinstance(conn.writer, UTPStreamWriter)
            assert conn.connection_task is not None
            assert conn.stats.last_activity > 0

    @pytest.mark.asyncio
    async def test_connect_timeout(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test connection timeout (lines 204-214)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        # Mock UTPConnection class
        with patch("ccbt.peer.utp_peer.UTPConnection", return_value=mock_utp_connection):
            # Mock the connection to stay in SYN_SENT
            mock_utp_connection.state = UTPConnectionState.SYN_SENT
            mock_utp_connection.connect = AsyncMock()

            with pytest.raises(ConnectionError, match="uTP connection failed to establish"):
                await conn.connect()

            assert conn.state == ConnectionState.ERROR
            assert conn.error_message is not None

    @pytest.mark.asyncio
    async def test_connect_exception(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test connection exception handling (lines 233-241)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        # Mock UTPConnection to raise exception
        with patch("ccbt.peer.utp_peer.UTPConnection", return_value=mock_utp_connection):
            mock_utp_connection.initialize_transport = AsyncMock(
                side_effect=OSError("Network error")
            )

            with pytest.raises(OSError):
                await conn.connect()

            assert conn.state == ConnectionState.ERROR
            assert "Network error" in conn.error_message


class TestUTPPeerConnectionDisconnect:
    """Tests for UTPPeerConnection.disconnect() (lines 243-258)."""

    @pytest.mark.asyncio
    async def test_disconnect_with_connection(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test disconnect with uTP connection (lines 245-249)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = mock_utp_connection

        await conn.disconnect()

        mock_utp_connection.close.assert_called_once()
        assert conn.state == ConnectionState.DISCONNECTED
        assert conn.reader is None
        assert conn.writer is None

    @pytest.mark.asyncio
    async def test_disconnect_with_connection_task(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test disconnect with connection task (lines 251-254)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = mock_utp_connection
        conn.connection_task = asyncio.create_task(asyncio.sleep(10))

        await conn.disconnect()

        assert conn.connection_task.cancelled() or conn.connection_task.done()
        assert conn.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_disconnect_connection_close_error(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test disconnect handles connection close error (lines 248-249)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        mock_utp_connection.close = AsyncMock(side_effect=Exception("Close error"))
        conn.utp_connection = mock_utp_connection

        # Should not raise, just log warning
        await conn.disconnect()

        assert conn.state == ConnectionState.DISCONNECTED


class TestUTPPeerConnectionReceiveMessages:
    """Tests for UTPPeerConnection._receive_messages() (lines 260-294)."""

    @pytest.mark.asyncio
    async def test_receive_messages_no_reader(self, peer_info, mock_torrent_data):
        """Test receive messages with no reader (lines 262-263)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.reader = None
        conn.state = ConnectionState.CONNECTED

        # Should return immediately
        await conn._receive_messages()

    @pytest.mark.asyncio
    async def test_receive_messages_keep_alive(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test receive messages handles keep-alive (lines 273-275)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        # Create mock reader with keep-alive message (length 0)
        mock_reader = MagicMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[
                (0).to_bytes(4, "big"),  # Keep-alive message
                asyncio.CancelledError(),  # Cancel after first message
            ]
        )
        conn.reader = mock_reader
        conn.state = ConnectionState.CONNECTED

        with pytest.raises(asyncio.CancelledError):
            await conn._receive_messages()

    @pytest.mark.asyncio
    async def test_receive_messages_empty_length_data(self, peer_info, mock_torrent_data):
        """Test receive messages handles empty length data (line 269-270)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        # Create mock reader that returns empty data (defensive check)
        mock_reader = MagicMock()
        mock_reader.readexactly = AsyncMock(return_value=b"")  # Empty bytes
        conn.reader = mock_reader
        conn.state = ConnectionState.CONNECTED

        # Should break out of loop
        await conn._receive_messages()

        assert conn.state == ConnectionState.CONNECTED  # State unchanged

    @pytest.mark.asyncio
    async def test_receive_messages_empty_message_data(self, peer_info, mock_torrent_data):
        """Test receive messages handles empty message data (line 279-280)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        # Create mock reader with length but empty message
        message_length = 5
        mock_reader = MagicMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[
                message_length.to_bytes(4, "big"),  # Message length
                b"",  # Empty message data
            ]
        )
        conn.reader = mock_reader
        conn.state = ConnectionState.CONNECTED

        # Should break out of loop
        await conn._receive_messages()

        assert conn.state == ConnectionState.CONNECTED  # State unchanged

    @pytest.mark.asyncio
    async def test_receive_messages_normal(self, peer_info, mock_torrent_data):
        """Test receive messages normal flow (lines 267-286)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        # Create mock reader with message data
        message_length = 5
        message_data = b"hello"
        mock_reader = MagicMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[
                message_length.to_bytes(4, "big"),  # Message length
                message_data,  # Message data
                asyncio.CancelledError(),  # Cancel after first message
            ]
        )
        conn.reader = mock_reader
        conn.state = ConnectionState.CONNECTED
        conn.message_decoder = MagicMock()
        conn.message_decoder.feed_data = AsyncMock()

        with pytest.raises(asyncio.CancelledError):
            await conn._receive_messages()

        # Verify message decoder was fed
        conn.message_decoder.feed_data.assert_called_once()
        assert conn.stats.last_activity > 0

    @pytest.mark.asyncio
    async def test_receive_messages_eof_error(self, peer_info, mock_torrent_data):
        """Test receive messages handles EOFError (lines 288-290)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        mock_reader = MagicMock()
        mock_reader.readexactly = AsyncMock(side_effect=EOFError("Connection closed"))
        conn.reader = mock_reader
        conn.state = ConnectionState.CONNECTED

        await conn._receive_messages()

        assert conn.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_receive_messages_connection_error(self, peer_info, mock_torrent_data):
        """Test receive messages handles ConnectionError (lines 288-290)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        mock_reader = MagicMock()
        mock_reader.readexactly = AsyncMock(side_effect=ConnectionError("Connection lost"))
        conn.reader = mock_reader
        conn.state = ConnectionState.CONNECTED

        await conn._receive_messages()

        assert conn.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_receive_messages_general_exception(self, peer_info, mock_torrent_data):
        """Test receive messages handles general exception (lines 291-294)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )

        mock_reader = MagicMock()
        mock_reader.readexactly = AsyncMock(side_effect=ValueError("Unexpected error"))
        conn.reader = mock_reader
        conn.state = ConnectionState.CONNECTED

        await conn._receive_messages()

        assert conn.state == ConnectionState.ERROR
        assert conn.error_message is not None


class TestUTPPeerConnectionStats:
    """Tests for UTPPeerConnection.update_stats() (lines 296-320)."""

    def test_update_stats_no_connection(self, peer_info, mock_torrent_data):
        """Test update_stats with no connection (line 298)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = None

        # Should not raise
        conn.update_stats()

    def test_update_stats_with_connection(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test update_stats with connection (lines 298-320)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = mock_utp_connection
        conn.stats.last_activity = time.time() - 1.0  # 1 second ago
        conn.state = ConnectionState.CONNECTED

        conn.update_stats()

        assert conn.stats.bytes_downloaded == 1024
        assert conn.stats.bytes_uploaded == 512
        assert conn.stats.download_rate > 0
        assert conn.stats.upload_rate > 0

    def test_update_stats_state_mapping(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test update_stats maps uTP state (lines 313-320)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = mock_utp_connection
        conn.utp_connection.state = UTPConnectionState.RESET
        conn.state = ConnectionState.CONNECTED
        conn.stats.last_activity = time.time()

        conn.update_stats()

        assert conn.state == ConnectionState.ERROR


class TestUTPPeerConnectionStateChecks:
    """Tests for UTPPeerConnection state check methods (lines 322-338)."""

    def test_is_connected_no_connection(self, peer_info, mock_torrent_data):
        """Test is_connected with no connection (lines 324-325)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = None

        assert conn.is_connected() is False

    def test_is_connected_connected_state(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test is_connected when connected (lines 326)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = mock_utp_connection
        conn.utp_connection.state = UTPConnectionState.CONNECTED

        assert conn.is_connected() is True

    def test_is_connected_not_connected_state(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test is_connected when not connected (line 326)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = mock_utp_connection
        conn.utp_connection.state = UTPConnectionState.CLOSED

        assert conn.is_connected() is False

    def test_has_timed_out_no_connection(self, peer_info, mock_torrent_data):
        """Test has_timed_out with no connection (lines 330-331)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = None

        assert conn.has_timed_out() is True

    def test_has_timed_out_with_recent_activity(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test has_timed_out with recent activity (lines 333-336)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = mock_utp_connection
        conn.utp_connection.last_recv_time = time.perf_counter()  # Recent

        assert conn.has_timed_out(timeout=60.0) is False

    def test_has_timed_out_with_old_activity(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test has_timed_out with old activity (lines 333-336)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = mock_utp_connection
        conn.utp_connection.last_recv_time = time.perf_counter() - 70.0  # 70 seconds ago

        assert conn.has_timed_out(timeout=60.0) is True

    def test_has_timed_out_no_last_recv_time(self, peer_info, mock_torrent_data, mock_utp_connection):
        """Test has_timed_out when last_recv_time is 0 (line 338)."""
        conn = UTPPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
        )
        conn.utp_connection = mock_utp_connection
        conn.utp_connection.last_recv_time = 0
        conn.stats.last_activity = time.time() - 70.0  # Old activity

        # Should fall back to super().has_timed_out()
        assert conn.has_timed_out(timeout=60.0) is True

