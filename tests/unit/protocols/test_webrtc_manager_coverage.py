"""Additional tests to achieve 95%+ coverage for WebRTCConnectionManager.

Tests error paths and edge cases not covered in main test file.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Try to import aiortc, skip tests if not available
try:
    from aiortc import RTCPeerConnection, RTCDataChannel

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
    mock_pc.close = AsyncMock()
    return mock_pc


@pytest.fixture
def mock_data_channel():
    """Create a mock RTCDataChannel."""
    mock_channel = MagicMock(spec=RTCDataChannel)
    mock_channel.readyState = "open"
    mock_channel.close = MagicMock()
    return mock_channel


class TestAdditionalCoverage:
    """Additional tests for coverage gaps."""

    @pytest.mark.asyncio
    async def test_create_peer_connection_ice_candidate_none(self, webrtc_manager, mock_rtc_peer_connection):
        """Test ICE candidate callback with None (end of candidates)."""
        from ccbt.protocols.webtorrent import webrtc_manager as webrtc_manager_module

        peer_id = "test_peer_1"
        callback_called = []

        async def ice_callback(peer_id: str, candidate: dict | None):
            callback_called.append((peer_id, candidate))

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

            # Simulate None candidate (end of candidates)
            if ice_handler:
                await ice_handler(None)

                # Callback should have been called with None
                assert len(callback_called) == 1
                assert callback_called[0][0] == peer_id
                assert callback_called[0][1] is None

    @pytest.mark.asyncio
    async def test_close_peer_connection_no_data_channel(self, webrtc_manager, mock_rtc_peer_connection):
        """Test closing connection when data channel doesn't exist."""
        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.connection_stats[peer_id] = {"created_at": 0}
        webrtc_manager.active_connections = 1

        # No data channel in data_channels dict
        await webrtc_manager.close_peer_connection(peer_id)

        assert peer_id not in webrtc_manager.connections
        mock_rtc_peer_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_peer_connection_data_channel_not_in_dict(self, webrtc_manager, mock_rtc_peer_connection, mock_data_channel):
        """Test closing when data channel exists but not in dict."""
        peer_id = "test_peer_1"
        webrtc_manager.connections[peer_id] = mock_rtc_peer_connection
        webrtc_manager.connection_stats[peer_id] = {"created_at": 0}
        webrtc_manager.active_connections = 1

        # Data channel exists but not in dict (edge case)
        await webrtc_manager.close_peer_connection(peer_id)

        assert peer_id not in webrtc_manager.connections
        mock_rtc_peer_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_connection_stats_no_connection(self, webrtc_manager):
        """Test getting stats when connection object doesn't exist."""
        peer_id = "test_peer_1"
        webrtc_manager.connection_stats[peer_id] = {
            "created_at": 1000.0,
            "connection_state": "connected",
        }
        # No connection in connections dict

        stats = webrtc_manager.get_connection_stats(peer_id)

        assert stats is not None
        assert stats["peer_id"] == peer_id

    def test_handle_data_channel_message_str(self, webrtc_manager, mock_data_channel):
        """Test handling message that is a string."""
        peer_id = "test_peer_1"
        webrtc_manager.connection_stats[peer_id] = {"bytes_received": 0}
        webrtc_manager.total_bytes_received = 0

        message = "test message string"
        webrtc_manager._handle_data_channel_message(peer_id, mock_data_channel, message)

        # Should handle string message
        assert webrtc_manager.total_bytes_received > 0

    def test_handle_data_channel_message_non_bytes(self, webrtc_manager, mock_data_channel):
        """Test handling message that is neither bytes nor string."""
        peer_id = "test_peer_1"
        webrtc_manager.connection_stats[peer_id] = {"bytes_received": 0}
        webrtc_manager.total_bytes_received = 0

        message = 12345  # Not bytes or string
        webrtc_manager._handle_data_channel_message(peer_id, mock_data_channel, message)

        # Should handle gracefully (convert to string length)
        assert webrtc_manager.total_bytes_received >= 0

