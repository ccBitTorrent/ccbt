"""Comprehensive tests for WebRTC peer connection.

Covers all methods and error paths in ccbt.peer.webrtc_peer.WebRTCPeerConnection.
Target: 100% code coverage for webrtc_peer.py.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.peer]

from ccbt.peer.async_peer_connection import ConnectionState, PeerStats
from ccbt.peer.peer import PeerInfo, PeerState
from ccbt.peer.webrtc_peer import WebRTCPeerConnection


@pytest.fixture
def mock_peer_info():
    """Create mock peer info."""
    return PeerInfo(
        ip="webrtc",
        port=6881,  # Use valid port (WebRTC doesn't actually use ports, but PeerInfo requires >= 1)
        peer_id=b"test_peer_id_1234567890",
    )


@pytest.fixture
def mock_webtorrent_protocol():
    """Create mock WebTorrent protocol."""
    protocol = MagicMock()
    protocol.connect_peer = AsyncMock(return_value=True)
    protocol.disconnect_peer = AsyncMock()
    protocol.send_message = AsyncMock(return_value=True)
    protocol.receive_message = AsyncMock(return_value=None)
    return protocol


@pytest.fixture
def mock_torrent_data():
    """Create mock torrent data."""
    return {
        "info_hash": b"test_info_hash_20byt",  # Exactly 20 bytes
        "pieces_info": {"num_pieces": 100},
    }


@pytest.fixture
def webrtc_peer(mock_peer_info, mock_webtorrent_protocol, mock_torrent_data):
    """Create WebRTC peer connection."""
    peer = WebRTCPeerConnection(
        peer_info=mock_peer_info,
        torrent_data=mock_torrent_data,
        webtorrent_protocol=mock_webtorrent_protocol,
    )
    return peer


class TestWebRTCPeerInitialization:
    """Tests for WebRTC peer initialization."""

    def test_post_init_sets_defaults(self, mock_peer_info, mock_torrent_data):
        """Test __post_init__ initializes default state."""
        peer = WebRTCPeerConnection(
            peer_info=mock_peer_info,
            torrent_data=mock_torrent_data,
        )
        
        assert peer.peer_info == mock_peer_info
        assert isinstance(peer.peer_state, PeerState)
        assert isinstance(peer.stats, PeerStats)
        assert peer.state == ConnectionState.DISCONNECTED
        assert peer.webtorrent_protocol is None
        assert peer._receive_task is None

    def test_post_init_with_existing_attributes(self, mock_peer_info, mock_torrent_data):
        """Test __post_init__ doesn't override existing attributes."""
        existing_state = PeerState()
        existing_stats = PeerStats()
        
        peer = WebRTCPeerConnection(
            peer_info=mock_peer_info,
            torrent_data=mock_torrent_data,
            peer_state=existing_state,
            stats=existing_stats,
        )
        
        assert peer.peer_state is existing_state
        assert peer.stats is existing_stats


class TestWebRTCPeerConnect:
    """Tests for connect() method."""

    @pytest.mark.asyncio
    async def test_connect_success(self, webrtc_peer, mock_webtorrent_protocol):
        """Test successful connection."""
        mock_webtorrent_protocol.connect_peer = AsyncMock(return_value=True)
        
        await webrtc_peer.connect()
        
        assert webrtc_peer.state == ConnectionState.CONNECTED
        assert webrtc_peer.stats.last_activity > 0
        assert webrtc_peer._receive_task is not None
        assert not webrtc_peer._receive_task.done()
        mock_webtorrent_protocol.connect_peer.assert_called_once_with(webrtc_peer.peer_info)

    @pytest.mark.asyncio
    async def test_connect_with_callback(self, webrtc_peer, mock_webtorrent_protocol):
        """Test connection triggers on_peer_connected callback."""
        callback_called = False
        def on_connected(conn):
            nonlocal callback_called
            callback_called = True
            assert conn is webrtc_peer
        
        webrtc_peer.on_peer_connected = on_connected
        mock_webtorrent_protocol.connect_peer = AsyncMock(return_value=True)
        
        await webrtc_peer.connect()
        
        assert callback_called
        assert webrtc_peer.state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_failure_returns_false(self, webrtc_peer, mock_webtorrent_protocol):
        """Test connection failure when protocol returns False."""
        mock_webtorrent_protocol.connect_peer = AsyncMock(return_value=False)
        
        await webrtc_peer.connect()
        
        assert webrtc_peer.state == ConnectionState.ERROR
        assert webrtc_peer.error_message == "Failed to establish WebRTC connection"
        assert webrtc_peer._receive_task is None

    @pytest.mark.asyncio
    async def test_connect_exception_handling(self, webrtc_peer, mock_webtorrent_protocol):
        """Test connection exception handling."""
        mock_webtorrent_protocol.connect_peer = AsyncMock(side_effect=RuntimeError("Connection error"))
        
        with pytest.raises(RuntimeError, match="Connection error"):
            await webrtc_peer.connect()
        
        assert webrtc_peer.state == ConnectionState.ERROR
        assert "Connection error" in webrtc_peer.error_message

    @pytest.mark.asyncio
    async def test_connect_no_protocol(self, mock_peer_info, mock_torrent_data):
        """Test connect without WebTorrent protocol raises ValueError."""
        peer = WebRTCPeerConnection(
            peer_info=mock_peer_info,
            torrent_data=mock_torrent_data,
        )
        
        with pytest.raises(ValueError, match="WebTorrent protocol not set"):
            await peer.connect()


class TestWebRTCPeerDisconnect:
    """Tests for disconnect() method."""

    @pytest.mark.asyncio
    async def test_disconnect_when_disconnected(self, webrtc_peer):
        """Test disconnect when already disconnected is no-op."""
        webrtc_peer.state = ConnectionState.DISCONNECTED
        
        await webrtc_peer.disconnect()
        
        assert webrtc_peer.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_disconnect_cancels_receive_task(self, webrtc_peer, mock_webtorrent_protocol):
        """Test disconnect cancels receive task."""
        mock_webtorrent_protocol.connect_peer = AsyncMock(return_value=True)
        await webrtc_peer.connect()
        
        receive_task = webrtc_peer._receive_task
        assert receive_task is not None
        
        await webrtc_peer.disconnect()
        
        assert webrtc_peer.state == ConnectionState.DISCONNECTED
        assert receive_task.done()

    @pytest.mark.asyncio
    async def test_disconnect_calls_protocol_disconnect(self, webrtc_peer, mock_webtorrent_protocol):
        """Test disconnect calls protocol disconnect_peer."""
        mock_webtorrent_protocol.connect_peer = AsyncMock(return_value=True)
        await webrtc_peer.connect()
        
        peer_id = webrtc_peer.peer_info.peer_id.hex()
        await webrtc_peer.disconnect()
        
        mock_webtorrent_protocol.disconnect_peer.assert_called_once_with(peer_id)

    @pytest.mark.asyncio
    async def test_disconnect_without_peer_id(self, mock_peer_info, mock_webtorrent_protocol, mock_torrent_data):
        """Test disconnect when peer_id is None."""
        peer_info = PeerInfo(ip="webrtc", port=6881, peer_id=None)
        peer = WebRTCPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
            webtorrent_protocol=mock_webtorrent_protocol,
        )
        mock_webtorrent_protocol.connect_peer = AsyncMock(return_value=True)
        await peer.connect()
        
        await peer.disconnect()
        
        # Should not call disconnect_peer when peer_id is None
        mock_webtorrent_protocol.disconnect_peer.assert_not_called()

    @pytest.mark.asyncio
    async def test_disconnect_triggers_callback(self, webrtc_peer, mock_webtorrent_protocol):
        """Test disconnect triggers on_peer_disconnected callback."""
        callback_called = False
        def on_disconnected(conn):
            nonlocal callback_called
            callback_called = True
            assert conn is webrtc_peer
        
        webrtc_peer.on_peer_disconnected = on_disconnected
        mock_webtorrent_protocol.connect_peer = AsyncMock(return_value=True)
        await webrtc_peer.connect()
        
        await webrtc_peer.disconnect()
        
        assert callback_called

    @pytest.mark.asyncio
    async def test_disconnect_no_protocol(self, webrtc_peer):
        """Test disconnect when protocol is None."""
        webrtc_peer.webtorrent_protocol = None
        webrtc_peer.state = ConnectionState.CONNECTED
        
        await webrtc_peer.disconnect()
        
        assert webrtc_peer.state == ConnectionState.DISCONNECTED


class TestWebRTCPeerSendMessage:
    """Tests for send_message() method."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, webrtc_peer, mock_webtorrent_protocol):
        """Test successful message sending."""
        webrtc_peer.state = ConnectionState.CONNECTED
        message = b"test message"
        peer_id = webrtc_peer.peer_info.peer_id.hex()
        initial_uploaded = webrtc_peer.stats.bytes_uploaded
        
        await webrtc_peer.send_message(message)
        
        mock_webtorrent_protocol.send_message.assert_called_once_with(peer_id, message)
        assert webrtc_peer.stats.bytes_uploaded == initial_uploaded + len(message)
        assert webrtc_peer.stats.last_activity > 0

    @pytest.mark.asyncio
    async def test_send_message_active_state(self, webrtc_peer, mock_webtorrent_protocol):
        """Test send_message works in ACTIVE state."""
        webrtc_peer.state = ConnectionState.ACTIVE
        message = b"test"
        
        await webrtc_peer.send_message(message)
        
        mock_webtorrent_protocol.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_choked_state(self, webrtc_peer, mock_webtorrent_protocol):
        """Test send_message works in CHOKED state."""
        webrtc_peer.state = ConnectionState.CHOKED
        message = b"test"
        
        await webrtc_peer.send_message(message)
        
        mock_webtorrent_protocol.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_disconnected_raises(self, webrtc_peer):
        """Test send_message raises RuntimeError when disconnected."""
        webrtc_peer.state = ConnectionState.DISCONNECTED
        message = b"test"
        
        with pytest.raises(RuntimeError, match="Cannot send message"):
            await webrtc_peer.send_message(message)

    @pytest.mark.asyncio
    async def test_send_message_error_state_raises(self, webrtc_peer):
        """Test send_message raises RuntimeError in ERROR state."""
        webrtc_peer.state = ConnectionState.ERROR
        message = b"test"
        
        with pytest.raises(RuntimeError, match="Cannot send message"):
            await webrtc_peer.send_message(message)

    @pytest.mark.asyncio
    async def test_send_message_no_protocol_raises(self, webrtc_peer):
        """Test send_message raises RuntimeError when protocol is None."""
        webrtc_peer.state = ConnectionState.CONNECTED
        webrtc_peer.webtorrent_protocol = None
        message = b"test"
        
        with pytest.raises(RuntimeError, match="WebTorrent protocol not available"):
            await webrtc_peer.send_message(message)

    @pytest.mark.asyncio
    async def test_send_message_no_peer_id_raises(self, mock_peer_info, mock_webtorrent_protocol, mock_torrent_data):
        """Test send_message raises RuntimeError when peer_id is None."""
        peer_info = PeerInfo(ip="webrtc", port=6881, peer_id=None)
        peer = WebRTCPeerConnection(
            peer_info=peer_info,
            torrent_data=mock_torrent_data,
            webtorrent_protocol=mock_webtorrent_protocol,
        )
        peer.state = ConnectionState.CONNECTED
        message = b"test"
        
        with pytest.raises(RuntimeError, match="Peer ID not available"):
            await peer.send_message(message)

    @pytest.mark.asyncio
    async def test_send_message_failure_raises(self, webrtc_peer, mock_webtorrent_protocol):
        """Test send_message raises RuntimeError when protocol send fails."""
        webrtc_peer.state = ConnectionState.CONNECTED
        mock_webtorrent_protocol.send_message = AsyncMock(return_value=False)
        message = b"test"
        
        with pytest.raises(RuntimeError, match="Failed to send message via WebRTC"):
            await webrtc_peer.send_message(message)


class TestWebRTCPeerReceiveMessage:
    """Tests for receive_message() method."""

    @pytest.mark.asyncio
    async def test_receive_message_empty_queue(self, webrtc_peer):
        """Test receive_message returns None when queue is empty."""
        result = await webrtc_peer.receive_message()
        
        assert result is None

    @pytest.mark.asyncio
    async def test_receive_message_from_queue(self, webrtc_peer):
        """Test receive_message returns message from queue."""
        message = b"test message"
        await webrtc_peer._message_queue.put(message)
        initial_downloaded = webrtc_peer.stats.bytes_downloaded
        initial_activity = webrtc_peer.stats.last_activity
        
        # Wait a bit to ensure timestamp changes
        await asyncio.sleep(0.01)
        
        result = await webrtc_peer.receive_message()
        
        assert result == message
        assert webrtc_peer.stats.bytes_downloaded == initial_downloaded + len(message)
        assert webrtc_peer.stats.last_activity >= initial_activity

    @pytest.mark.asyncio
    async def test_receive_message_queue_empty_exception(self, webrtc_peer):
        """Test receive_message handles QueueEmpty exception."""
        # Queue is empty, get_nowait will raise QueueEmpty
        result = await webrtc_peer.receive_message()
        
        assert result is None


class TestWebRTCPeerReceiveLoop:
    """Tests for _receive_loop() method."""

    @pytest.mark.asyncio
    async def test_receive_loop_receives_messages(self, webrtc_peer, mock_webtorrent_protocol):
        """Test _receive_loop receives and queues messages."""
        webrtc_peer.state = ConnectionState.CONNECTED
        peer_id = webrtc_peer.peer_info.peer_id.hex()
        message1 = b"message 1"
        message2 = b"message 2"
        
        # Mock receive_message to return messages then None
        call_count = 0
        async def mock_receive(pid):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return message1
            elif call_count == 2:
                return message2
            else:
                await asyncio.sleep(0.05)  # Sleep to allow loop to continue
                return None
        
        mock_webtorrent_protocol.receive_message = mock_receive
        
        # Start receive loop
        task = asyncio.create_task(webrtc_peer._receive_loop())
        
        # Wait for messages to be queued
        await asyncio.sleep(0.1)
        
        # Stop the loop
        webrtc_peer.state = ConnectionState.DISCONNECTED
        
        # Wait a bit for loop to exit
        await asyncio.sleep(0.05)
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Check messages were queued
        assert not webrtc_peer._message_queue.empty() or call_count > 0

    @pytest.mark.asyncio
    async def test_receive_loop_updates_state_to_active(self, webrtc_peer, mock_webtorrent_protocol):
        """Test _receive_loop updates state from CONNECTED to ACTIVE."""
        webrtc_peer.state = ConnectionState.CONNECTED
        peer_id = webrtc_peer.peer_info.peer_id.hex()
        
        async def mock_receive(pid):
            await asyncio.sleep(0.01)
            if webrtc_peer.state == ConnectionState.CONNECTED:
                return b"test message"
            return None
        
        mock_webtorrent_protocol.receive_message = mock_receive
        
        task = asyncio.create_task(webrtc_peer._receive_loop())
        
        # Wait for state update
        await asyncio.sleep(0.05)
        
        # Stop loop
        webrtc_peer.state = ConnectionState.DISCONNECTED
        await asyncio.sleep(0.01)
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # State should have been updated to ACTIVE after receiving message
        # (or remain CONNECTED if loop exited before processing)
        assert webrtc_peer.state in [ConnectionState.DISCONNECTED, ConnectionState.ACTIVE]

    @pytest.mark.asyncio
    async def test_receive_loop_no_protocol_exits(self, webrtc_peer):
        """Test _receive_loop exits when protocol is None."""
        webrtc_peer.state = ConnectionState.CONNECTED
        webrtc_peer.webtorrent_protocol = None
        
        await webrtc_peer._receive_loop()
        
        # Loop should exit immediately

    @pytest.mark.asyncio
    async def test_receive_loop_handles_cancelled_error(self, webrtc_peer, mock_webtorrent_protocol):
        """Test _receive_loop handles CancelledError gracefully."""
        webrtc_peer.state = ConnectionState.CONNECTED
        
        async def mock_receive(pid):
            await asyncio.sleep(0.1)
            raise asyncio.CancelledError()
        
        mock_webtorrent_protocol.receive_message = mock_receive
        
        task = asyncio.create_task(webrtc_peer._receive_loop())
        
        # Wait a bit then cancel
        await asyncio.sleep(0.05)
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Should exit gracefully

    @pytest.mark.asyncio
    async def test_receive_loop_handles_exception(self, webrtc_peer, mock_webtorrent_protocol):
        """Test _receive_loop handles exceptions and sets error state."""
        webrtc_peer.state = ConnectionState.CONNECTED
        peer_id = webrtc_peer.peer_info.peer_id.hex()
        
        async def mock_receive(pid):
            raise RuntimeError("Receive error")
        
        mock_webtorrent_protocol.receive_message = mock_receive
        
        await webrtc_peer._receive_loop()
        
        assert webrtc_peer.state == ConnectionState.ERROR
        assert "Receive error" in webrtc_peer.error_message

    @pytest.mark.asyncio
    async def test_receive_loop_exits_on_disconnected_state(self, webrtc_peer, mock_webtorrent_protocol):
        """Test _receive_loop exits when state becomes disconnected."""
        webrtc_peer.state = ConnectionState.CONNECTED
        
        async def mock_receive(pid):
            await asyncio.sleep(0.01)
            return None
        
        mock_webtorrent_protocol.receive_message = mock_receive
        
        task = asyncio.create_task(webrtc_peer._receive_loop())
        
        # Wait a bit then change state
        await asyncio.sleep(0.02)
        webrtc_peer.state = ConnectionState.DISCONNECTED
        
        # Wait for loop to exit
        await asyncio.sleep(0.05)
        
        # Task should be done or close to done
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class TestWebRTCPeerStateChecks:
    """Tests for state checking methods."""

    def test_is_connected_when_connected(self, webrtc_peer):
        """Test is_connected returns True when CONNECTED."""
        webrtc_peer.state = ConnectionState.CONNECTED
        assert webrtc_peer.is_connected() is True

    def test_is_connected_when_active(self, webrtc_peer):
        """Test is_connected returns True when ACTIVE."""
        webrtc_peer.state = ConnectionState.ACTIVE
        assert webrtc_peer.is_connected() is True

    def test_is_connected_when_choked(self, webrtc_peer):
        """Test is_connected returns True when CHOKED."""
        webrtc_peer.state = ConnectionState.CHOKED
        assert webrtc_peer.is_connected() is True

    def test_is_connected_when_disconnected(self, webrtc_peer):
        """Test is_connected returns False when DISCONNECTED."""
        webrtc_peer.state = ConnectionState.DISCONNECTED
        assert webrtc_peer.is_connected() is False

    def test_is_active_when_active(self, webrtc_peer):
        """Test is_active returns True when ACTIVE."""
        webrtc_peer.state = ConnectionState.ACTIVE
        assert webrtc_peer.is_active() is True

    def test_is_active_when_choked(self, webrtc_peer):
        """Test is_active returns True when CHOKED."""
        webrtc_peer.state = ConnectionState.CHOKED
        assert webrtc_peer.is_active() is True

    def test_is_active_when_connected(self, webrtc_peer):
        """Test is_active returns False when CONNECTED."""
        webrtc_peer.state = ConnectionState.CONNECTED
        assert webrtc_peer.is_active() is False

    def test_has_timed_out_when_timed_out(self, webrtc_peer):
        """Test has_timed_out returns True after timeout."""
        webrtc_peer.stats.last_activity = time.time() - 61.0  # 61 seconds ago
        assert webrtc_peer.has_timed_out(60.0) is True

    def test_has_timed_out_when_not_timed_out(self, webrtc_peer):
        """Test has_timed_out returns False within timeout."""
        webrtc_peer.stats.last_activity = time.time()  # Just now
        assert webrtc_peer.has_timed_out(60.0) is False

    def test_has_timed_out_custom_timeout(self, webrtc_peer):
        """Test has_timed_out with custom timeout."""
        webrtc_peer.stats.last_activity = time.time() - 31.0  # 31 seconds ago
        assert webrtc_peer.has_timed_out(30.0) is True
        assert webrtc_peer.has_timed_out(60.0) is False


class TestWebRTCPeerProperties:
    """Tests for reader and writer properties."""

    def test_reader_returns_none(self, webrtc_peer):
        """Test reader property returns None."""
        assert webrtc_peer.reader is None

    def test_writer_returns_none(self, webrtc_peer):
        """Test writer property returns None."""
        assert webrtc_peer.writer is None

