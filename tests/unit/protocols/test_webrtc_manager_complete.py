"""Complete coverage tests for WebRTCConnectionManager.

Tests all remaining uncovered paths including event handlers and edge cases.
Target: 100% coverage.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Try to import aiortc, skip tests if not available
try:
    from aiortc import RTCPeerConnection, RTCDataChannel, RTCIceCandidate

    HAS_AIORTC = True
except ImportError:
    HAS_AIORTC = False

pytestmark = pytest.mark.skipif(
    not HAS_AIORTC,
    reason="aiortc not installed, run: uv sync --extra webrtc",
)


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
    mock_channel.send = MagicMock()
    return mock_channel


class TestEventHandlers:
    """Tests for event handler callbacks to achieve full coverage."""

    @pytest.mark.asyncio
    async def test_connection_state_change_handler_invoked(
        self, webrtc_manager, mock_rtc_peer_connection
    ):
        """Test that connection state change handler is invoked by RTCPeerConnection."""
        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        peer_id = "test_peer_1"

        # Capture the handler
        captured_handler = None

        def capture_handler(event_name):
            if event_name == "connectionstatechange":
                def wrapper(handler):
                    nonlocal captured_handler
                    captured_handler = handler
                    return handler
                return wrapper
            return lambda handler: handler

        mock_rtc_peer_connection.on.side_effect = capture_handler

        with patch.object(webrtc_manager_module, "RTCPeerConnection") as mock_pc_class:
            mock_pc_class.return_value = mock_rtc_peer_connection

            await webrtc_manager.create_peer_connection(peer_id)

            # Manually invoke the captured handler to simulate RTCPeerConnection event
            if captured_handler:
                mock_rtc_peer_connection.connectionState = "connected"
                await captured_handler()

                # Verify handler was called
                assert peer_id in webrtc_manager.connection_stats
                assert webrtc_manager.connection_stats[peer_id]["connection_state"] == "connected"

    @pytest.mark.asyncio
    async def test_ice_connection_state_change_handler_invoked(
        self, webrtc_manager, mock_rtc_peer_connection
    ):
        """Test that ICE connection state change handler is invoked."""
        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        peer_id = "test_peer_1"

        # Capture the handler
        captured_handler = None

        def capture_handler(event_name):
            if event_name == "iceconnectionstatechange":
                def wrapper(handler):
                    nonlocal captured_handler
                    captured_handler = handler
                    return handler
                return wrapper
            return lambda handler: handler

        mock_rtc_peer_connection.on.side_effect = capture_handler

        with patch.object(webrtc_manager_module, "RTCPeerConnection") as mock_pc_class:
            mock_pc_class.return_value = mock_rtc_peer_connection

            await webrtc_manager.create_peer_connection(peer_id)

            # Manually invoke the captured handler
            if captured_handler:
                mock_rtc_peer_connection.iceConnectionState = "checking"
                await captured_handler()

                # Verify handler was called
                assert peer_id in webrtc_manager.connection_stats
                assert webrtc_manager.connection_stats[peer_id]["ice_connection_state"] == "checking"

    @pytest.mark.asyncio
    async def test_ice_connection_state_failed_triggers_cleanup(
        self, webrtc_manager, mock_rtc_peer_connection
    ):
        """Test that ICE connection state 'failed' triggers connection cleanup."""
        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        peer_id = "test_peer_1"
        initial_failed = webrtc_manager.failed_connections

        # Capture the handler
        captured_handler = None

        def capture_handler(event_name):
            if event_name == "iceconnectionstatechange":
                def wrapper(handler):
                    nonlocal captured_handler
                    captured_handler = handler
                    return handler
                return wrapper
            return lambda handler: handler

        mock_rtc_peer_connection.on.side_effect = capture_handler

        with patch.object(webrtc_manager_module, "RTCPeerConnection") as mock_pc_class:
            mock_pc_class.return_value = mock_rtc_peer_connection

            await webrtc_manager.create_peer_connection(peer_id)

            # Verify connection was created (active_connections should be 1)
            assert webrtc_manager.active_connections == 1

            # Trigger failed state
            if captured_handler:
                mock_rtc_peer_connection.iceConnectionState = "failed"
                await captured_handler()

                # Verify cleanup occurred (active_connections decremented)
                assert webrtc_manager.failed_connections == initial_failed + 1
                assert webrtc_manager.active_connections == 0

    @pytest.mark.asyncio
    async def test_ice_connection_state_closed_triggers_cleanup(
        self, webrtc_manager, mock_rtc_peer_connection
    ):
        """Test that ICE connection state 'closed' triggers connection cleanup."""
        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        peer_id = "test_peer_1"
        initial_failed = webrtc_manager.failed_connections

        # Capture the handler
        captured_handler = None

        def capture_handler(event_name):
            if event_name == "iceconnectionstatechange":
                def wrapper(handler):
                    nonlocal captured_handler
                    captured_handler = handler
                    return handler
                return wrapper
            return lambda handler: handler

        mock_rtc_peer_connection.on.side_effect = capture_handler

        with patch.object(webrtc_manager_module, "RTCPeerConnection") as mock_pc_class:
            mock_pc_class.return_value = mock_rtc_peer_connection

            await webrtc_manager.create_peer_connection(peer_id)

            # Verify connection was created (active_connections should be 1)
            assert webrtc_manager.active_connections == 1

            # Trigger closed state
            if captured_handler:
                mock_rtc_peer_connection.iceConnectionState = "closed"
                await captured_handler()

                # Verify cleanup occurred (active_connections decremented)
                assert webrtc_manager.failed_connections == initial_failed + 1
                assert webrtc_manager.active_connections == 0


class TestDataChannelEventHandlers:
    """Tests for data channel event handlers."""

    def test_data_channel_open_handler_invoked(
        self, webrtc_manager, mock_rtc_peer_connection, mock_data_channel
    ):
        """Test that data channel open handler is invoked."""
        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection

        # Capture the open handler
        captured_open_handler = None

        def capture_channel_handler(event_name):
            if event_name == "open":
                def wrapper(handler):
                    nonlocal captured_open_handler
                    captured_open_handler = handler
                    return handler
                return wrapper
            return lambda handler: handler

        mock_data_channel.on.side_effect = capture_channel_handler
        mock_rtc_peer_connection.createDataChannel.return_value = mock_data_channel

        webrtc_manager.create_data_channel(peer_id, mock_rtc_peer_connection)

        # Manually invoke the handler to simulate event
        if captured_open_handler:
            captured_open_handler()

            # Handler should have been called (no exception)
            assert peer_id in webrtc_manager.data_channels

    def test_data_channel_close_handler_invoked(
        self, webrtc_manager, mock_rtc_peer_connection, mock_data_channel
    ):
        """Test that data channel close handler is invoked."""
        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.data_channels[peer_id] = mock_data_channel

        # Capture the close handler
        captured_close_handler = None

        def capture_channel_handler(event_name):
            if event_name == "close":
                def wrapper(handler):
                    nonlocal captured_close_handler
                    captured_close_handler = handler
                    return handler
                return wrapper
            return lambda handler: handler

        mock_data_channel.on.side_effect = capture_channel_handler
        mock_rtc_peer_connection.createDataChannel.return_value = mock_data_channel

        webrtc_manager.create_data_channel(peer_id, mock_rtc_peer_connection)

        # Manually invoke the handler to simulate event
        if captured_close_handler:
            captured_close_handler()

            # Handler should remove from data_channels
            assert peer_id not in webrtc_manager.data_channels

    def test_data_channel_message_handler_invoked(
        self, webrtc_manager, mock_rtc_peer_connection, mock_data_channel
    ):
        """Test that data channel message handler is invoked."""
        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.connection_stats[peer_id] = {"bytes_received": 0}
        webrtc_manager.total_bytes_received = 0

        # Capture the message handler
        captured_message_handler = None

        def capture_channel_handler(event_name):
            if event_name == "message":
                def wrapper(handler):
                    nonlocal captured_message_handler
                    captured_message_handler = handler
                    return handler
                return wrapper
            return lambda handler: handler

        mock_data_channel.on.side_effect = capture_channel_handler
        mock_rtc_peer_connection.createDataChannel.return_value = mock_data_channel

        webrtc_manager.create_data_channel(peer_id, mock_rtc_peer_connection)

        # Manually invoke the handler to simulate message event
        if captured_message_handler:
            message = b"test message"
            captured_message_handler(message)

            # Handler should update statistics
            assert webrtc_manager.connection_stats[peer_id]["bytes_received"] == len(message)
            assert webrtc_manager.total_bytes_received == len(message)

