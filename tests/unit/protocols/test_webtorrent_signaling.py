"""Unit tests for WebTorrent signaling (offer/answer/ICE candidate handling).

Tests WebSocket signaling message handling including offer/answer exchange,
ICE candidate processing, and error cases.

Target: 95%+ code coverage.
"""

from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# Try to import aiortc, skip tests if not available
try:
    from aiortc import (
        RTCPeerConnection,
        RTCSessionDescription,
        RTCIceCandidate,
    )

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
def mock_websocket():
    """Create a mock WebSocket response."""
    mock_ws = MagicMock()
    mock_ws.closed = False
    mock_ws.send_json = AsyncMock()
    return mock_ws


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
    mock_pc.addIceCandidate = AsyncMock()
    mock_pc.close = AsyncMock()
    return mock_pc


@pytest.fixture
def mock_data_channel():
    """Create a mock RTCDataChannel."""
    mock_channel = MagicMock()
    mock_channel.readyState = "open"
    mock_channel.close = MagicMock()
    return mock_channel


class TestWebTorrentSignalingOffer:
    """Tests for offer handling."""

    @pytest.mark.asyncio
    async def test_handle_offer_success(
        self, webtorrent_protocol, mock_websocket, mock_rtc_peer_connection, mock_data_channel
    ):
        """Test successful offer handling."""
        peer_id = "test_peer_1"
        offer_sdp = {
            "type": "offer",
            "sdp": "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
        }
        data = {
            "type": "offer",
            "sdp": offer_sdp,
            "peer_id": peer_id,
        }

        # Mock WebRTC manager
        with patch(
            "ccbt.protocols.webtorrent.webrtc_manager.WebRTCConnectionManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.create_peer_connection = AsyncMock(return_value=mock_rtc_peer_connection)
            mock_manager.create_data_channel = MagicMock(return_value=mock_data_channel)
            webtorrent_protocol.webrtc_manager = mock_manager

            # Mock createAnswer
            mock_answer = MagicMock()
            mock_answer.type = "answer"
            mock_answer.sdp = "v=0\r\no=- 987654321 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"
            mock_rtc_peer_connection.createAnswer = AsyncMock(return_value=mock_answer)

            await webtorrent_protocol._handle_offer(mock_websocket, data)

            # Verify connection was created
            mock_manager.create_peer_connection.assert_called_once()
            mock_rtc_peer_connection.setRemoteDescription.assert_called_once()
            mock_manager.create_data_channel.assert_called_once()

            # Verify answer was sent
            mock_websocket.send_json.assert_called_once()
            call_args = mock_websocket.send_json.call_args[0][0]
            assert call_args["type"] == "answer"
            assert "sdp" in call_args
            assert call_args["peer_id"] == peer_id

    @pytest.mark.asyncio
    async def test_handle_offer_missing_sdp(self, webtorrent_protocol, mock_websocket):
        """Test offer handling with missing SDP."""
        data = {"type": "offer", "peer_id": "test_peer_1"}

        await webtorrent_protocol._handle_offer(mock_websocket, data)

        # Should send error response
        mock_websocket.send_json.assert_called_once()
        assert mock_websocket.send_json.call_args[0][0]["type"] == "error"

    @pytest.mark.asyncio
    async def test_handle_offer_missing_peer_id(self, webtorrent_protocol, mock_websocket):
        """Test offer handling with missing peer_id."""
        data = {
            "type": "offer",
            "sdp": {"type": "offer", "sdp": "test"},
        }

        await webtorrent_protocol._handle_offer(mock_websocket, data)

        # Should send error response
        mock_websocket.send_json.assert_called_once()
        assert mock_websocket.send_json.call_args[0][0]["type"] == "error"

    @pytest.mark.asyncio
    async def test_handle_offer_timeout(
        self, webtorrent_protocol, mock_websocket, mock_rtc_peer_connection
    ):
        """Test offer handling with timeout."""
        peer_id = "test_peer_1"
        data = {
            "type": "offer",
            "sdp": {"type": "offer", "sdp": "test"},
            "peer_id": peer_id,
        }

        with patch(
            "ccbt.protocols.webtorrent.WebRTCConnectionManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            # Make create_peer_connection hang (simulate timeout)
            async def slow_create(*args, **kwargs):
                await asyncio.sleep(35.0)  # Longer than timeout
                return mock_rtc_peer_connection

            mock_manager.create_peer_connection = slow_create
            webtorrent_protocol.webrtc_manager = mock_manager

            await webtorrent_protocol._handle_offer(mock_websocket, data)

            # Should send timeout error
            mock_websocket.send_json.assert_called()
            error_call = None
            for call in mock_websocket.send_json.call_args_list:
                if call[0][0].get("type") == "error":
                    error_call = call
                    break
            assert error_call is not None

    @pytest.mark.asyncio
    async def test_handle_offer_webrtc_not_available(self, webtorrent_protocol, mock_websocket):
        """Test offer handling when WebRTC is not available."""
        data = {
            "type": "offer",
            "sdp": {"type": "offer", "sdp": "test"},
            "peer_id": "test_peer_1",
        }

        # Mock ImportError
        with patch(
            "ccbt.protocols.webtorrent.WebRTCConnectionManager",
            side_effect=ImportError("aiortc not available"),
        ):
            await webtorrent_protocol._handle_offer(mock_websocket, data)

            # Should send error response
            mock_websocket.send_json.assert_called_once()
            assert mock_websocket.send_json.call_args[0][0]["type"] == "error"


class TestWebTorrentSignalingAnswer:
    """Tests for answer handling."""

    @pytest.mark.asyncio
    async def test_handle_answer_success(
        self, webtorrent_protocol, mock_websocket, mock_rtc_peer_connection
    ):
        """Test successful answer handling."""
        peer_id = "test_peer_1"
        answer_sdp = {
            "type": "answer",
            "sdp": "v=0\r\no=- 987654321 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
        }
        data = {
            "type": "answer",
            "sdp": answer_sdp,
            "peer_id": peer_id,
        }

        # Create connection
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        connection = WebRTCConnection(peer_id=peer_id)
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        # Mock WebRTC manager
        webtorrent_protocol.webrtc_manager = MagicMock()
        webtorrent_protocol.webrtc_manager.connections = {peer_id: mock_rtc_peer_connection}

        await webtorrent_protocol._handle_answer(mock_websocket, data)

        # Verify answer was processed
        mock_rtc_peer_connection.setRemoteDescription.assert_called_once()
        assert connection.connection_state == "connected"

    @pytest.mark.asyncio
    async def test_handle_answer_unknown_peer(self, webtorrent_protocol, mock_websocket):
        """Test answer handling for unknown peer."""
        data = {
            "type": "answer",
            "sdp": {"type": "answer", "sdp": "test"},
            "peer_id": "unknown_peer",
        }

        # Should not raise, just log warning
        await webtorrent_protocol._handle_answer(mock_websocket, data)

    @pytest.mark.asyncio
    async def test_handle_answer_invalid_format(self, webtorrent_protocol, mock_websocket):
        """Test answer handling with invalid format."""
        peer_id = "test_peer_1"
        from ccbt.protocols.webtorrent import WebRTCConnection

        webtorrent_protocol.webrtc_connections[peer_id] = WebRTCConnection(peer_id=peer_id)

        data = {
            "type": "answer",
            "sdp": None,  # Invalid
            "peer_id": peer_id,
        }

        # Should not raise, just log warning
        await webtorrent_protocol._handle_answer(mock_websocket, data)

    @pytest.mark.asyncio
    async def test_handle_answer_wrong_type(self, webtorrent_protocol, mock_websocket):
        """Test answer handling with wrong SDP type."""
        peer_id = "test_peer_1"
        from ccbt.protocols.webtorrent import WebRTCConnection

        webtorrent_protocol.webrtc_connections[peer_id] = WebRTCConnection(peer_id=peer_id)

        data = {
            "type": "answer",
            "sdp": {"type": "offer", "sdp": "test"},  # Wrong type (should be answer)
            "peer_id": peer_id,
        }

        # Should not raise, just log warning
        await webtorrent_protocol._handle_answer(mock_websocket, data)


class TestWebTorrentSignalingICECandidate:
    """Tests for ICE candidate handling."""

    @pytest.mark.asyncio
    async def test_handle_ice_candidate_success(
        self, webtorrent_protocol, mock_websocket, mock_rtc_peer_connection
    ):
        """Test successful ICE candidate handling."""
        peer_id = "test_peer_1"
        candidate_dict = {
            "component": 1,
            "foundation": "test",
            "ip": "192.168.1.1",
            "port": 12345,
            "priority": 100,
            "protocol": "udp",
            "type": "host",
            "sdpMid": "0",
            "sdpMLineIndex": 0,
        }
        data = {
            "type": "ice-candidate",
            "candidate": candidate_dict,
            "peer_id": peer_id,
        }

        # Create connection
        import ccbt.protocols.webtorrent as webtorrent_module

        WebRTCConnection = webtorrent_module.WebRTCConnection  # type: ignore[attr-defined]

        connection = WebRTCConnection(peer_id=peer_id)
        webtorrent_protocol.webrtc_connections[peer_id] = connection

        # Mock WebRTC manager
        webtorrent_protocol.webrtc_manager = MagicMock()
        webtorrent_protocol.webrtc_manager.connections = {peer_id: mock_rtc_peer_connection}

        await webtorrent_protocol._handle_ice_candidate(mock_websocket, data)

        # Verify candidate was added
        mock_rtc_peer_connection.addIceCandidate.assert_called_once()
        candidate_arg = mock_rtc_peer_connection.addIceCandidate.call_args[0][0]
        assert candidate_arg.component == 1
        assert candidate_arg.ip == "192.168.1.1"
        assert candidate_arg.port == 12345

    @pytest.mark.asyncio
    async def test_handle_ice_candidate_unknown_peer(self, webtorrent_protocol, mock_websocket):
        """Test ICE candidate handling for unknown peer."""
        data = {
            "type": "ice-candidate",
            "candidate": {"ip": "192.168.1.1", "port": 12345},
            "peer_id": "unknown_peer",
        }

        # Should not raise, just log debug
        await webtorrent_protocol._handle_ice_candidate(mock_websocket, data)

    @pytest.mark.asyncio
    async def test_handle_ice_candidate_no_manager(self, webtorrent_protocol, mock_websocket):
        """Test ICE candidate handling when manager is not initialized."""
        peer_id = "test_peer_1"
        from ccbt.protocols.webtorrent import WebRTCConnection

        webtorrent_protocol.webrtc_connections[peer_id] = WebRTCConnection(peer_id=peer_id)
        webtorrent_protocol.webrtc_manager = None

        data = {
            "type": "ice-candidate",
            "candidate": {"ip": "192.168.1.1", "port": 12345},
            "peer_id": peer_id,
        }

        # Should not raise, just log error
        await webtorrent_protocol._handle_ice_candidate(mock_websocket, data)


class TestWebTorrentSignalingWebSocket:
    """Tests for WebSocket handler."""

    @pytest.mark.asyncio
    async def test_websocket_handler_tracks_peer_id(self, webtorrent_protocol):
        """Test that WebSocket handler tracks connections by peer_id."""
        from aiohttp import web

        mock_request = MagicMock()
        mock_ws = MagicMock()
        mock_ws.closed = False
        mock_ws.send_json = AsyncMock()

        # Mock WebSocketResponse - use actual aiohttp.web module
        with patch("aiohttp.web.WebSocketResponse") as mock_ws_class:
            mock_ws_class.return_value = mock_ws
            mock_ws.prepare = AsyncMock()

            # Mock message
            mock_msg = MagicMock()
            mock_msg.type = web.WSMsgType.TEXT  # type: ignore[attr-defined]
            mock_msg.data = json.dumps({"type": "offer", "peer_id": "test_peer", "sdp": {"type": "offer", "sdp": "test"}})

            async def mock_msg_iter():
                yield mock_msg
                mock_msg.type = web.WSMsgType.CLOSE  # type: ignore[attr-defined]
                yield mock_msg

            mock_ws.__aiter__ = mock_msg_iter

            # Mock _handle_signaling_message to avoid actual processing
            webtorrent_protocol._handle_signaling_message = AsyncMock()

            handler = webtorrent_protocol._websocket_handler(mock_request)
            await handler

            # Verify peer tracking
            assert "test_peer" in webtorrent_protocol.websocket_connections_by_peer

    @pytest.mark.asyncio
    async def test_websocket_handler_cleanup_on_disconnect(self, webtorrent_protocol):
        """Test WebSocket handler cleans up on disconnect."""
        from aiohttp import web

        mock_request = MagicMock()
        mock_ws = MagicMock()
        mock_ws.closed = False
        peer_id = "test_peer"
        webtorrent_protocol.websocket_connections_by_peer[peer_id] = mock_ws

        with patch("ccbt.protocols.webtorrent.web.WebSocketResponse") as mock_ws_class:
            mock_ws_class.return_value = mock_ws
            mock_ws.prepare = AsyncMock()

            # Mock close message
            mock_msg = MagicMock()
            mock_msg.type = web.WSMsgType.CLOSE

            async def mock_msg_iter():
                yield mock_msg

            mock_ws.__aiter__ = mock_msg_iter

            handler = webtorrent_protocol._websocket_handler(mock_request)
            await handler

            # Verify cleanup
            assert peer_id not in webtorrent_protocol.websocket_connections_by_peer

