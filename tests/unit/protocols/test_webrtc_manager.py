"""Unit tests for WebRTC connection manager.

Tests WebRTCConnectionManager functionality including connection creation,
lifecycle management, data channel operations, and statistics tracking.

Target: 95%+ code coverage.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# Try to import aiortc, skip tests if not available
try:
    from aiortc import (
        RTCPeerConnection,
        RTCConfiguration,
        RTCIceServer,
        RTCDataChannel,
        RTCIceCandidate,
    )

    HAS_AIORTC = True
except ImportError:
    HAS_AIORTC = False
    RTCPeerConnection = None  # type: ignore[assignment, misc]
    RTCConfiguration = None  # type: ignore[assignment, misc]
    RTCIceServer = None  # type: ignore[assignment, misc]
    RTCDataChannel = None  # type: ignore[assignment, misc]
    RTCIceCandidate = None  # type: ignore[assignment, misc]

pytestmark = pytest.mark.skipif(
    not HAS_AIORTC,
    reason="aiortc not installed, run: uv sync --extra webrtc",
)


@pytest.fixture
def mock_rtc_peer_connection():
    """Create a mock RTCPeerConnection."""
    mock_pc = MagicMock(spec=RTCPeerConnection)
    mock_pc.connectionState = "new"
    mock_pc.iceConnectionState = "new"
    mock_pc.setRemoteDescription = AsyncMock()
    mock_pc.setLocalDescription = AsyncMock()
    mock_pc.createAnswer = AsyncMock()
    mock_pc.createOffer = AsyncMock()
    mock_pc.addIceCandidate = AsyncMock()
    mock_pc.close = AsyncMock()
    mock_pc.createDataChannel = MagicMock()
    return mock_pc


@pytest.fixture
def mock_data_channel():
    """Create a mock RTCDataChannel."""
    mock_channel = MagicMock(spec=RTCDataChannel)
    mock_channel.readyState = "open"
    mock_channel.close = MagicMock()
    return mock_channel


@pytest.fixture
def webrtc_manager():
    """Create a WebRTCConnectionManager instance."""
    from ccbt.protocols.webtorrent.webrtc_manager import (  # type: ignore[import-untyped]
        WebRTCConnectionManager,
    )

    return WebRTCConnectionManager(
        stun_servers=["stun:stun.l.google.com:19302"],
        turn_servers=[],
        max_connections=10,
    )


class TestWebRTCConnectionManagerInit:
    """Tests for WebRTCConnectionManager initialization."""

    def test_init_defaults(self):
        """Test initialization with default parameters."""
        from ccbt.protocols.webtorrent.webrtc_manager import (  # type: ignore[import-untyped]
            WebRTCConnectionManager,
        )

        manager = WebRTCConnectionManager()
        assert len(manager.connections) == 0
        assert len(manager.data_channels) == 0
        assert manager.total_connections == 0
        assert manager.active_connections == 0
        assert manager.failed_connections == 0
        assert len(manager.stun_servers) > 0
        assert manager.max_connections == 100

    def test_init_custom_config(self):
        """Test initialization with custom configuration."""
        from ccbt.protocols.webtorrent.webrtc_manager import WebRTCConnectionManager

        stun_servers = ["stun:stun1.example.com:19302", "stun:stun2.example.com:19302"]
        turn_servers = ["turn:turn.example.com:3478"]
        manager = WebRTCConnectionManager(
            stun_servers=stun_servers,
            turn_servers=turn_servers,
            max_connections=50,
        )
        assert manager.stun_servers == stun_servers
        assert manager.turn_servers == turn_servers
        assert manager.max_connections == 50
        assert len(manager.ice_servers) == 3  # 2 STUN + 1 TURN

    def test_init_without_aiortc(self):
        """Test that initialization fails without aiortc."""
        from ccbt.protocols.webtorrent import webrtc_manager

        # Temporarily replace RTCPeerConnection with None
        original_rtc = webrtc_manager.RTCPeerConnection
        webrtc_manager.RTCPeerConnection = None  # type: ignore[assignment]

        try:
            from ccbt.protocols.webtorrent.webrtc_manager import WebRTCConnectionManager

            with pytest.raises(ImportError, match="aiortc is not installed"):
                WebRTCConnectionManager()
        finally:
            # Restore
            webrtc_manager.RTCPeerConnection = original_rtc

    def test_build_ice_servers(self, webrtc_manager):
        """Test ICE server configuration building."""
        ice_servers = webrtc_manager._build_ice_servers()
        assert len(ice_servers) > 0
        assert all(isinstance(server, RTCIceServer) for server in ice_servers)


class TestWebRTCConnectionManagerConnectionCreation:
    """Tests for peer connection creation."""

    @pytest.mark.asyncio
    async def test_create_peer_connection_success(
        self, webrtc_manager, mock_rtc_peer_connection
    ):
        """Test successful peer connection creation."""
        peer_id = "test_peer_1"

        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        with patch.object(webrtc_manager_module, "RTCPeerConnection") as mock_pc_class:
            mock_pc_class.return_value = mock_rtc_peer_connection

            pc = await webrtc_manager.create_peer_connection(peer_id)

            assert pc is not None
            assert peer_id in webrtc_manager.connections
            assert webrtc_manager.connections[peer_id] == mock_rtc_peer_connection
            assert peer_id in webrtc_manager.connection_stats
            assert webrtc_manager.total_connections == 1
            assert webrtc_manager.active_connections == 1

            # Verify event handlers were set
            assert mock_rtc_peer_connection.on.call_count >= 3  # connectionstatechange, iceconnectionstatechange, icecandidate

    @pytest.mark.asyncio
    async def test_create_peer_connection_max_exceeded(self, webrtc_manager):
        """Test that maximum connections limit is enforced."""
        peer_id = "test_peer_1"

        # Fill up to max connections
        webrtc_manager.max_connections = 2
        with patch("ccbt.protocols.webtorrent.webrtc_manager.RTCPeerConnection"):
            await webrtc_manager.create_peer_connection("peer_1")
            await webrtc_manager.create_peer_connection("peer_2")

            # Should raise ValueError when trying to exceed max
            with pytest.raises(ValueError, match="Maximum connections"):
                await webrtc_manager.create_peer_connection(peer_id)

    @pytest.mark.asyncio
    async def test_create_peer_connection_duplicate(self, webrtc_manager, mock_rtc_peer_connection):
        """Test creating connection for existing peer returns existing connection."""
        peer_id = "test_peer_1"

        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        with patch.object(webrtc_manager_module, "RTCPeerConnection") as mock_pc_class:
            mock_pc_class.return_value = mock_rtc_peer_connection

            pc1 = await webrtc_manager.create_peer_connection(peer_id)
            pc2 = await webrtc_manager.create_peer_connection(peer_id)

            assert pc1 is pc2
            assert mock_pc_class.call_count == 1  # Should only create once

    @pytest.mark.asyncio
    async def test_create_peer_connection_with_ice_callback(
        self, webrtc_manager, mock_rtc_peer_connection
    ):
        """Test creating connection with ICE candidate callback."""
        peer_id = "test_peer_1"
        callback_called = []

        async def ice_callback(peer_id: str, candidate: dict | None):
            callback_called.append((peer_id, candidate))

        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        with patch.object(webrtc_manager_module, "RTCPeerConnection") as mock_pc_class:
            mock_pc_class.return_value = mock_rtc_peer_connection

            # Capture the on("icecandidate") handler
            ice_handler = None

            def capture_ice_handler(event_name):
                if event_name == "icecandidate":
                    def wrapper(handler):
                        nonlocal ice_handler
                        ice_handler = handler
                        return handler
                    return wrapper
                return lambda handler: handler

            mock_rtc_peer_connection.on.side_effect = capture_ice_handler

            await webrtc_manager.create_peer_connection(peer_id, ice_candidate_callback=ice_callback)

            # Simulate ICE candidate event
            if ice_handler:
                mock_candidate = MagicMock()
                mock_candidate.component = 1
                mock_candidate.foundation = "test"
                mock_candidate.ip = "192.168.1.1"
                mock_candidate.port = 12345
                mock_candidate.priority = 100
                mock_candidate.protocol = "udp"
                mock_candidate.type = "host"
                mock_candidate.sdpMid = None
                mock_candidate.sdpMLineIndex = None

                await ice_handler(mock_candidate)

                # Callback should have been called
                assert len(callback_called) == 1
                assert callback_called[0][0] == peer_id


class TestWebRTCConnectionManagerLifecycle:
    """Tests for connection lifecycle management."""

    @pytest.mark.asyncio
    async def test_handle_connection_state_change(self, webrtc_manager, mock_rtc_peer_connection):
        """Test connection state change handling."""
        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.connection_stats[peer_id] = {"connection_state": "new"}

        mock_rtc_peer_connection.connectionState = "connected"

        await webrtc_manager._handle_connection_state_change(peer_id, mock_rtc_peer_connection)

        assert webrtc_manager.connection_stats[peer_id]["connection_state"] == "connected"

    @pytest.mark.asyncio
    async def test_handle_connection_state_failed(self, webrtc_manager, mock_rtc_peer_connection):
        """Test handling of failed connection state."""
        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.connection_stats[peer_id] = {"connection_state": "new"}
        webrtc_manager.active_connections = 1
        initial_failed = webrtc_manager.failed_connections

        mock_rtc_peer_connection.connectionState = "failed"

        await webrtc_manager._handle_connection_state_change(peer_id, mock_rtc_peer_connection)

        assert webrtc_manager.failed_connections == initial_failed + 1
        assert webrtc_manager.active_connections == 0

    @pytest.mark.asyncio
    async def test_handle_ice_connection_state_change(
        self, webrtc_manager, mock_rtc_peer_connection
    ):
        """Test ICE connection state change handling."""
        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.connection_stats[peer_id] = {"ice_connection_state": "new"}

        mock_rtc_peer_connection.iceConnectionState = "checking"

        await webrtc_manager._handle_ice_connection_state_change(peer_id, mock_rtc_peer_connection)

        assert webrtc_manager.connection_stats[peer_id]["ice_connection_state"] == "checking"

    @pytest.mark.asyncio
    async def test_close_peer_connection(self, webrtc_manager, mock_rtc_peer_connection, mock_data_channel):
        """Test closing a peer connection."""
        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.data_channels[peer_id] = mock_data_channel
        webrtc_manager.connection_stats[peer_id] = {"created_at": 0}
        webrtc_manager.active_connections = 1

        await webrtc_manager.close_peer_connection(peer_id)

        assert peer_id not in webrtc_manager.connections
        assert peer_id not in webrtc_manager.data_channels
        assert peer_id not in webrtc_manager.connection_stats
        assert webrtc_manager.active_connections == 0
        mock_data_channel.close.assert_called_once()
        mock_rtc_peer_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_nonexistent_peer_connection(self, webrtc_manager):
        """Test closing a non-existent peer connection."""
        peer_id = "nonexistent_peer"

        # Should not raise, just log warning
        await webrtc_manager.close_peer_connection(peer_id)

    @pytest.mark.asyncio
    async def test_close_peer_connection_with_error(
        self, webrtc_manager, mock_rtc_peer_connection, mock_data_channel
    ):
        """Test closing connection when close raises an error."""
        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.data_channels[peer_id] = mock_data_channel
        webrtc_manager.connection_stats[peer_id] = {"created_at": 0}

        mock_rtc_peer_connection.close.side_effect = Exception("Close error")

        # Should handle error gracefully
        await webrtc_manager.close_peer_connection(peer_id)


class TestWebRTCConnectionManagerDataChannels:
    """Tests for data channel management."""

    @pytest.mark.asyncio
    async def test_create_data_channel(self, webrtc_manager, mock_rtc_peer_connection, mock_data_channel):
        """Test creating a data channel."""
        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        mock_rtc_peer_connection.createDataChannel.return_value = mock_data_channel

        channel = webrtc_manager.create_data_channel(
            peer_id, mock_rtc_peer_connection, channel_name="webtorrent", ordered=True
        )

        assert channel == mock_data_channel
        assert peer_id in webrtc_manager.data_channels
        assert webrtc_manager.data_channels[peer_id] == mock_data_channel
        mock_rtc_peer_connection.createDataChannel.assert_called_once_with("webtorrent", ordered=True)

        # Verify event handlers were set
        assert mock_data_channel.on.call_count >= 3  # open, close, message

    @pytest.mark.asyncio
    async def test_create_data_channel_missing_connection(self, webrtc_manager, mock_rtc_peer_connection):
        """Test creating data channel for non-existent connection."""
        peer_id = "nonexistent_peer"

        with pytest.raises(ValueError, match="Connection for peer"):
            webrtc_manager.create_data_channel(peer_id, mock_rtc_peer_connection)

    def test_handle_data_channel_open(self, webrtc_manager, mock_data_channel):
        """Test data channel open event handling."""
        peer_id = "test_peer_1"
        webrtc_manager.data_channels[peer_id] = mock_data_channel

        webrtc_manager._handle_data_channel_open(peer_id, mock_data_channel)

        # Should not raise, just log
        assert peer_id in webrtc_manager.data_channels

    def test_handle_data_channel_close(self, webrtc_manager, mock_data_channel):
        """Test data channel close event handling."""
        peer_id = "test_peer_1"
        webrtc_manager.data_channels[peer_id] = mock_data_channel

        webrtc_manager._handle_data_channel_close(peer_id, mock_data_channel)

        assert peer_id not in webrtc_manager.data_channels

    def test_handle_data_channel_message(self, webrtc_manager, mock_data_channel):
        """Test data channel message event handling."""
        peer_id = "test_peer_1"
        webrtc_manager.connection_stats[peer_id] = {"bytes_received": 0}
        webrtc_manager.total_bytes_received = 0

        message = b"test message"
        webrtc_manager._handle_data_channel_message(peer_id, mock_data_channel, message)

        assert webrtc_manager.connection_stats[peer_id]["bytes_received"] == len(message)
        assert webrtc_manager.total_bytes_received == len(message)

    def test_format_ice_candidate_for_websocket(self, webrtc_manager):
        """Test formatting ICE candidate for WebSocket transmission."""
        mock_candidate = MagicMock()
        mock_candidate.component = 1
        mock_candidate.foundation = "test_foundation"
        mock_candidate.ip = "192.168.1.1"
        mock_candidate.port = 12345
        mock_candidate.priority = 100
        mock_candidate.protocol = "udp"
        mock_candidate.type = "host"
        mock_candidate.sdpMid = "0"
        mock_candidate.sdpMLineIndex = 0

        candidate_dict = webrtc_manager._format_ice_candidate_for_websocket(mock_candidate)

        assert candidate_dict["component"] == 1
        assert candidate_dict["foundation"] == "test_foundation"
        assert candidate_dict["ip"] == "192.168.1.1"
        assert candidate_dict["port"] == 12345
        assert candidate_dict["priority"] == 100
        assert candidate_dict["protocol"] == "udp"
        assert candidate_dict["type"] == "host"
        assert candidate_dict["sdpMid"] == "0"
        assert candidate_dict["sdpMLineIndex"] == 0


class TestWebRTCConnectionManagerStatistics:
    """Tests for statistics and monitoring."""

    def test_get_connection_stats(self, webrtc_manager, mock_rtc_peer_connection):
        """Test getting connection statistics for a peer."""
        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.connection_stats[peer_id] = {
            "created_at": 1000.0,
            "connection_state": "connected",
            "ice_connection_state": "connected",
            "bytes_sent": 100,
            "bytes_received": 200,
        }
        mock_rtc_peer_connection.connectionState = "connected"
        mock_rtc_peer_connection.iceConnectionState = "connected"

        stats = webrtc_manager.get_connection_stats(peer_id)

        assert stats is not None
        assert stats["peer_id"] == peer_id
        assert stats["connection_state"] == "connected"
        assert stats["ice_connection_state"] == "connected"
        assert stats["bytes_sent"] == 100
        assert stats["bytes_received"] == 200

    def test_get_connection_stats_nonexistent(self, webrtc_manager):
        """Test getting stats for non-existent peer."""
        peer_id = "nonexistent_peer"

        stats = webrtc_manager.get_connection_stats(peer_id)

        assert stats is None

    def test_get_all_connections(self, webrtc_manager, mock_rtc_peer_connection):
        """Test getting statistics for all connections."""
        # Add multiple connections
        for i in range(3):
            peer_id = f"peer_{i}"
            webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
            webrtc_manager.connection_stats[peer_id] = {
                "created_at": 1000.0 + i,
                "connection_state": "connected",
                "ice_connection_state": "connected",
            }

        all_stats = webrtc_manager.get_all_connections()

        assert len(all_stats) == 3
        for i in range(3):
            assert f"peer_{i}" in all_stats

    @pytest.mark.asyncio
    async def test_cleanup_stale_connections(self, webrtc_manager, mock_rtc_peer_connection):
        """Test cleaning up stale connections."""
        import time

        # Create connections with different ages
        current_time = time.time()

        # Stale connection (older than timeout)
        stale_peer = "stale_peer"
        webrtc_manager.connections[stale_peer] = mock_rtc_peer_connection
        webrtc_manager.connection_stats[stale_peer] = {
            "created_at": current_time - 400.0,  # 400 seconds ago
        }

        # Fresh connection
        fresh_peer = "fresh_peer"
        fresh_mock_pc = MagicMock()
        webrtc_manager.connections[fresh_peer] = fresh_mock_pc
        webrtc_manager.connection_stats[fresh_peer] = {
            "created_at": current_time - 100.0,  # 100 seconds ago
        }

        webrtc_manager.active_connections = 2

        # Cleanup with 300 second timeout
        cleaned = await webrtc_manager.cleanup_stale_connections(timeout=300.0)

        assert cleaned == 1
        assert stale_peer not in webrtc_manager.connections
        assert fresh_peer in webrtc_manager.connections
        mock_rtc_peer_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_stale_connections_no_stale(self, webrtc_manager, mock_rtc_peer_connection):
        """Test cleanup when no stale connections exist."""
        import time

        current_time = time.time()

        peer_id = "fresh_peer"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.connection_stats[peer_id] = {
            "created_at": current_time - 100.0,  # 100 seconds ago
        }

        # Cleanup with 300 second timeout
        cleaned = await webrtc_manager.cleanup_stale_connections(timeout=300.0)

        assert cleaned == 0
        assert peer_id in webrtc_manager.connections

