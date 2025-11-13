"""Unit tests for WebTorrent protocol implementation.

Tests connect_peer, send_message, receive_message, and connection state transitions.

Target: 95%+ code coverage.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# Try to import aiortc, skip tests if not available
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription

    HAS_AIORTC = True
except ImportError:
    HAS_AIORTC = False

pytestmark = pytest.mark.skipif(
    not HAS_AIORTC,
    reason="aiortc not installed, run: uv sync --extra webrtc",
)


@pytest.fixture
def webtorrent_protocol():
    """Create a WebTorrentProtocol instance."""
    # Import directly from module (not from __init__)
    import ccbt.protocols.webtorrent as webtorrent_module

    if webtorrent_module.WebTorrentProtocol is None:  # type: ignore[attr-defined]
        pytest.skip("WebTorrentProtocol not available (aiortc not installed)")
    
    protocol = webtorrent_module.WebTorrentProtocol()  # type: ignore[attr-defined]
    return protocol


@pytest.fixture
def mock_peer_info():
    """Create a mock PeerInfo."""
    from ccbt.models import PeerInfo

    return PeerInfo(
        ip="webrtc",
        port=0,
        peer_id=b"test_peer_id_1234567890",
    )


@pytest.fixture
def mock_rtc_peer_connection():
    """Create a mock RTCPeerConnection."""
    mock_pc = MagicMock()
    mock_pc.connectionState = "new"
    mock_pc.iceConnectionState = "new"
    mock_pc.setRemoteDescription = AsyncMock()
    mock_pc.setLocalDescription = AsyncMock()
    mock_pc.createAnswer = AsyncMock()
    mock_pc.createOffer = AsyncMock()
    mock_pc.close = AsyncMock()
    return mock_pc


@pytest.fixture
def mock_data_channel():
    """Create a mock RTCDataChannel."""
    mock_channel = MagicMock()
    mock_channel.readyState = "open"
    mock_channel.send = MagicMock()
    mock_channel.close = MagicMock()
    return mock_channel


class TestWebTorrentConnectPeer:
    """Tests for connect_peer method."""

    @pytest.mark.asyncio
    async def test_connect_peer_success(
        self,
        webtorrent_protocol,
        mock_peer_info,
        mock_rtc_peer_connection,
        mock_data_channel,
    ):
        """Test successful peer connection."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        peer_id = mock_peer_info.peer_id.hex()

        # Mock WebRTC manager
        with patch(
            "ccbt.protocols.webtorrent.WebRTCConnectionManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.create_peer_connection = AsyncMock(return_value=mock_rtc_peer_connection)
            mock_manager.create_data_channel = MagicMock(return_value=mock_data_channel)
            webtorrent_protocol.webrtc_manager = mock_manager

            # Mock createOffer
            mock_offer = MagicMock()
            mock_offer.type = "offer"
            mock_offer.sdp = "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\n"
            mock_rtc_peer_connection.createOffer = AsyncMock(return_value=mock_offer)

            # Mock WebSocket connection
            mock_ws = MagicMock()
            mock_ws.closed = False
            mock_ws.send_json = AsyncMock()
            webtorrent_protocol.websocket_connections_by_peer[peer_id] = mock_ws

            # Mock connection to become connected quickly
            connection = WebRTCConnection(
                peer_id=peer_id,
                connection_state="connecting",
            )
            webtorrent_protocol.webrtc_connections[peer_id] = connection

            # Create task to update state to connected
            async def make_connected():
                await asyncio.sleep(0.1)
                connection.connection_state = "connected"

            task = asyncio.create_task(make_connected())

            result = await webtorrent_protocol.connect_peer(mock_peer_info)

            await task

            # Should succeed
            assert result is True
            assert peer_id in webtorrent_protocol.webrtc_connections
            mock_manager.create_peer_connection.assert_called_once()
            mock_rtc_peer_connection.createOffer.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_peer_no_peer_id(self, webtorrent_protocol):
        """Test connection attempt without peer_id."""
        from ccbt.models import PeerInfo

        peer_info = PeerInfo(ip="webrtc", port=0, peer_id=None)

        result = await webtorrent_protocol.connect_peer(peer_info)

        assert result is False

    @pytest.mark.asyncio
    async def test_connect_peer_timeout(
        self,
        webtorrent_protocol,
        mock_peer_info,
        mock_rtc_peer_connection,
        mock_data_channel,
    ):
        """Test connection timeout."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        peer_id = mock_peer_info.peer_id.hex()

        # Mock config with short timeout
        with patch("ccbt.protocols.webtorrent.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.network.webtorrent.webtorrent_connection_timeout = 0.1  # 100ms timeout
            mock_get_config.return_value = mock_config

            # Mock WebRTC manager
            with patch(
                "ccbt.protocols.webtorrent.webrtc_manager.WebRTCConnectionManager"
            ) as mock_manager_class:
                mock_manager = MagicMock()
                mock_manager_class.return_value = mock_manager
                mock_manager.create_peer_connection = AsyncMock(return_value=mock_rtc_peer_connection)
                mock_manager.create_data_channel = MagicMock(return_value=mock_data_channel)
                webtorrent_protocol.webrtc_manager = mock_manager

                # Mock createOffer
                mock_offer = MagicMock()
                mock_offer.type = "offer"
                mock_offer.sdp = "test"
                mock_rtc_peer_connection.createOffer = AsyncMock(return_value=mock_offer)

                # Mock WebSocket
                mock_ws = MagicMock()
                mock_ws.closed = False
                mock_ws.send_json = AsyncMock()
                webtorrent_protocol.websocket_connections_by_peer[peer_id] = mock_ws

                # Create connection that never becomes connected
                connection = WebRTCConnection(
                    peer_id=peer_id,
                    connection_state="connecting",
                )
                webtorrent_protocol.webrtc_connections[peer_id] = connection

                result = await webtorrent_protocol.connect_peer(mock_peer_info)

                # Should fail due to timeout
                assert result is False

    @pytest.mark.asyncio
    async def test_connect_peer_exception(
        self,
        webtorrent_protocol,
        mock_peer_info,
    ):
        """Test connection with exception."""
        peer_id = mock_peer_info.peer_id.hex()

        # Mock manager to raise exception
        with patch(
            "ccbt.protocols.webtorrent.webrtc_manager.WebRTCConnectionManager",
            side_effect=Exception("Connection error"),
        ):
            result = await webtorrent_protocol.connect_peer(mock_peer_info)

            assert result is False


class TestWebTorrentSendMessage:
    """Tests for send_message method."""

    @pytest.mark.asyncio
    async def test_send_message_success(
        self,
        webtorrent_protocol,
        mock_data_channel,
    ):
        """Test successful message sending."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        peer_id = "test_peer_1"
        message = b"test message"

        connection = WebRTCConnection(
            peer_id=peer_id,
            data_channel=mock_data_channel,
        )
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        result = await webtorrent_protocol.send_message(peer_id, message)

        assert result is True
        assert connection.bytes_sent == len(message)
        mock_data_channel.send.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_message_no_connection(self, webtorrent_protocol):
        """Test sending message to non-existent connection."""
        peer_id = "nonexistent_peer"
        message = b"test message"

        result = await webtorrent_protocol.send_message(peer_id, message)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_channel_closed(
        self,
        webtorrent_protocol,
        mock_data_channel,
    ):
        """Test sending message when channel is closed."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        peer_id = "test_peer_1"
        message = b"test message"

        mock_data_channel.readyState = "closed"

        connection = WebRTCConnection(
            peer_id=peer_id,
            data_channel=mock_data_channel,
        )
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        result = await webtorrent_protocol.send_message(peer_id, message)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_error(
        self,
        webtorrent_protocol,
        mock_data_channel,
    ):
        """Test sending message with send error."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        peer_id = "test_peer_1"
        message = b"test message"

        mock_data_channel.send.side_effect = Exception("Send error")

        connection = WebRTCConnection(
            peer_id=peer_id,
            data_channel=mock_data_channel,
        )
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        result = await webtorrent_protocol.send_message(peer_id, message)

        assert result is False


class TestWebTorrentReceiveMessage:
    """Tests for receive_message method."""

    @pytest.mark.asyncio
    async def test_receive_message_success(self, webtorrent_protocol, mock_data_channel):
        """Test successful message receiving."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        peer_id = "test_peer_1"
        message = b"\x00\x00\x00\x05\x02test"  # Length 5, message type 2, payload "test"

        connection = WebRTCConnection(
            peer_id=peer_id,
            data_channel=mock_data_channel,
        )
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        # Set up message queue with message
        import asyncio as aio

        queue = aio.Queue()
        queue.put_nowait(message)
        webtorrent_protocol._message_queue[peer_id] = queue

        result = await webtorrent_protocol.receive_message(peer_id)

        assert result == message
        assert connection.bytes_received == len(message)

    @pytest.mark.asyncio
    async def test_receive_message_no_connection(self, webtorrent_protocol):
        """Test receiving message from non-existent connection."""
        peer_id = "nonexistent_peer"

        result = await webtorrent_protocol.receive_message(peer_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_receive_message_no_queue(self, webtorrent_protocol, mock_data_channel):
        """Test receiving message when no queue exists."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        peer_id = "test_peer_1"
        connection = WebRTCConnection(
            peer_id=peer_id,
            data_channel=mock_data_channel,
        )
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        result = await webtorrent_protocol.receive_message(peer_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_receive_message_timeout(self, webtorrent_protocol, mock_data_channel):
        """Test receiving message with timeout."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        peer_id = "test_peer_1"
        connection = WebRTCConnection(
            peer_id=peer_id,
            data_channel=mock_data_channel,
        )
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        # Create empty queue
        import asyncio as aio

        queue = aio.Queue()
        webtorrent_protocol._message_queue[peer_id] = queue

        result = await webtorrent_protocol.receive_message(peer_id)

        # Should timeout and return None
        assert result is None


class TestWebTorrentMessageFraming:
    """Tests for message framing and buffering."""

    @pytest.mark.asyncio
    async def test_process_received_data_complete_message(self, webtorrent_protocol):
        """Test processing complete message."""
        peer_id = "test_peer_1"
        message = b"\x00\x00\x00\x05\x02test"  # Length 5, type 2, payload "test"

        await webtorrent_protocol._process_received_data(peer_id, message)

        # Message should be queued
        assert peer_id in webtorrent_protocol._message_queue
        queued_message = await webtorrent_protocol._message_queue[peer_id].get()
        assert queued_message == message

    @pytest.mark.asyncio
    async def test_process_received_data_partial_message(self, webtorrent_protocol):
        """Test processing partial message (split across packets)."""
        peer_id = "test_peer_1"

        # First packet: just length prefix
        partial1 = b"\x00\x00\x00\x05"
        await webtorrent_protocol._process_received_data(peer_id, partial1)

        # Should be buffered, not queued
        assert peer_id in webtorrent_protocol._message_buffer
        assert webtorrent_protocol._message_queue[peer_id].empty()

        # Second packet: rest of message
        partial2 = b"\x02test"
        await webtorrent_protocol._process_received_data(peer_id, partial2)

        # Now should be queued
        queued_message = await webtorrent_protocol._message_queue[peer_id].get()
        assert queued_message == b"\x00\x00\x00\x05\x02test"

    @pytest.mark.asyncio
    async def test_process_received_data_multi_message(self, webtorrent_protocol):
        """Test processing multiple messages in single packet."""
        peer_id = "test_peer_1"

        # Two complete messages
        message1 = b"\x00\x00\x00\x05\x02test"
        message2 = b"\x00\x00\x00\x07\x03hello!"
        combined = message1 + message2

        await webtorrent_protocol._process_received_data(peer_id, combined)

        # Both should be queued
        queue = webtorrent_protocol._message_queue[peer_id]
        queued1 = await queue.get()
        queued2 = await queue.get()

        assert queued1 == message1
        assert queued2 == message2

    @pytest.mark.asyncio
    async def test_process_received_data_keep_alive(self, webtorrent_protocol):
        """Test processing keep-alive message (length 0)."""
        peer_id = "test_peer_1"
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        connection = WebRTCConnection(peer_id=peer_id)
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        keep_alive = b"\x00\x00\x00\x00"  # Keep-alive (length 0)

        await webtorrent_protocol._process_received_data(peer_id, keep_alive)

        # Keep-alive should update activity but not be queued
        assert webtorrent_protocol._message_queue[peer_id].empty()

    @pytest.mark.asyncio
    async def test_cleanup_peer_buffers(self, webtorrent_protocol):
        """Test cleaning up peer buffers."""
        peer_id = "test_peer_1"

        # Add buffer and queue
        webtorrent_protocol._message_buffer[peer_id] = b"test buffer"
        import asyncio as aio

        queue = aio.Queue()
        queue.put_nowait(b"test message")
        webtorrent_protocol._message_queue[peer_id] = queue

        webtorrent_protocol._cleanup_peer_buffers(peer_id)

        # Should be cleaned up
        assert peer_id not in webtorrent_protocol._message_buffer
        assert webtorrent_protocol._message_queue[peer_id].empty()


class TestWebTorrentDisconnect:
    """Tests for disconnect_peer method."""

    @pytest.mark.asyncio
    async def test_disconnect_peer_success(
        self, webtorrent_protocol, mock_data_channel
    ):
        """Test successful peer disconnection."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        peer_id = "test_peer_1"
        connection = WebRTCConnection(
            peer_id=peer_id,
            data_channel=mock_data_channel,
        )
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        await webtorrent_protocol.disconnect_peer(peer_id)

        assert peer_id not in webtorrent_protocol.webrtc_connections
        mock_data_channel.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_peer_nonexistent(self, webtorrent_protocol):
        """Test disconnecting non-existent peer."""
        peer_id = "nonexistent_peer"

        # Should not raise
        await webtorrent_protocol.disconnect_peer(peer_id)


class TestWebTorrentConnectionStats:
    """Tests for connection statistics."""

    def test_get_connection_stats(self, webtorrent_protocol, mock_data_channel):
        """Test getting connection statistics."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        peer_id = "test_peer_1"
        connection = WebRTCConnection(
            peer_id=peer_id,
            data_channel=mock_data_channel,
            bytes_sent=100,
            bytes_received=200,
        )
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        stats = webtorrent_protocol.get_connection_stats(peer_id)

        assert stats is not None
        assert stats["peer_id"] == peer_id
        assert stats["bytes_sent"] == 100
        assert stats["bytes_received"] == 200

    def test_get_connection_stats_nonexistent(self, webtorrent_protocol):
        """Test getting stats for non-existent peer."""
        peer_id = "nonexistent_peer"

        stats = webtorrent_protocol.get_connection_stats(peer_id)

        assert stats is None

    def test_get_all_connection_stats(self, webtorrent_protocol, mock_data_channel):
        """Test getting statistics for all connections."""
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        # Add multiple connections
        for i in range(3):
            peer_id = f"peer_{i}"
            connection = WebRTCConnection(
                peer_id=peer_id,
                data_channel=mock_data_channel,
                bytes_sent=i * 10,
                bytes_received=i * 20,
            )
            webtorrent_protocol.webrtc_connections[peer_id] = connection

        all_stats = webtorrent_protocol.get_all_connection_stats()

        assert len(all_stats) == 3
        for i in range(3):
            assert f"peer_{i}" in all_stats
            assert all_stats[f"peer_{i}"]["bytes_sent"] == i * 10

