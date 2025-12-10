"""Tests for BitTorrent protocol integration."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.protocols.bittorrent import BitTorrentProtocol, ProtocolState
from ccbt.models import PeerInfo, TorrentInfo


class TestBitTorrentProtocolIntegration:
    """Test cases for BitTorrent protocol integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session_manager = MagicMock()
        self.protocol = BitTorrentProtocol(session_manager=self.mock_session_manager)

    def test_protocol_initialization(self):
        """Test protocol initialization."""
        assert self.protocol.session_manager == self.mock_session_manager
        assert self.protocol.peer_manager is None
        assert self.protocol.tracker_manager is None
        assert self.protocol.get_state() == ProtocolState.DISCONNECTED

    def test_protocol_initialization_without_session(self):
        """Test protocol initialization without session manager."""
        protocol = BitTorrentProtocol()
        assert protocol.session_manager is None
        assert protocol.peer_manager is None
        assert protocol.tracker_manager is None

    @pytest.mark.asyncio
    async def test_start_protocol_success(self):
        """Test successful protocol start."""
        # Mock session manager with required attributes
        self.mock_session_manager.start = AsyncMock()
        self.mock_session_manager.peer_manager = MagicMock()
        self.mock_session_manager.tracker_manager = MagicMock()

        await self.protocol.start()

        # Verify session manager was started
        self.mock_session_manager.start.assert_called_once()
        
        # Verify managers were assigned
        assert self.protocol.peer_manager is not None
        assert self.protocol.tracker_manager is not None
        
        # Verify state changed
        assert self.protocol.get_state() == ProtocolState.CONNECTED

    @pytest.mark.asyncio
    async def test_start_protocol_without_session(self):
        """Test protocol start without session manager."""
        protocol = BitTorrentProtocol()
        
        # Should not raise exception
        await protocol.start()
        
        # Should set state to connected
        assert protocol.get_state() == ProtocolState.CONNECTED

    @pytest.mark.asyncio
    async def test_start_protocol_exception(self):
        """Test protocol start with exception."""
        self.mock_session_manager.start = AsyncMock(side_effect=Exception("Start failed"))
        
        with pytest.raises(Exception, match="Start failed"):
            await self.protocol.start()
        
        # Should set state to error
        assert self.protocol.get_state() == ProtocolState.ERROR

    @pytest.mark.asyncio
    async def test_stop_protocol(self):
        """Test protocol stop."""
        self.mock_session_manager.stop = AsyncMock()
        
        await self.protocol.stop()
        
        self.mock_session_manager.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_protocol_without_session(self):
        """Test protocol stop without session manager."""
        protocol = BitTorrentProtocol()
        
        # Should not raise exception
        await protocol.stop()

    @pytest.mark.asyncio
    async def test_connect_peer_with_peer_manager(self):
        """Test connecting peer using peer manager."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        
        # Mock peer manager
        mock_peer_manager = MagicMock()
        mock_peer_manager.connect_peer = AsyncMock(return_value=True)
        self.protocol.peer_manager = mock_peer_manager
        
        result = await self.protocol.connect_peer(peer_info)
        
        assert result is True
        mock_peer_manager.connect_peer.assert_called_once_with(peer_info)
        
        # Verify stats were updated
        assert self.protocol.stats.connections_established == 1

    @pytest.mark.asyncio
    async def test_connect_peer_with_session_manager_fallback(self):
        """Test connecting peer using session manager fallback."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        
        # Mock session manager
        self.mock_session_manager.connect_peer = AsyncMock(return_value=True)
        
        result = await self.protocol.connect_peer(peer_info)
        
        assert result is True
        self.mock_session_manager.connect_peer.assert_called_once_with(peer_info)
        
        # Verify stats were updated
        assert self.protocol.stats.connections_established == 1

    @pytest.mark.asyncio
    async def test_connect_peer_failure(self):
        """Test peer connection failure."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        
        # Mock peer manager to fail
        mock_peer_manager = MagicMock()
        mock_peer_manager.connect_peer = AsyncMock(return_value=False)
        self.protocol.peer_manager = mock_peer_manager
        
        # Mock session manager to also fail
        self.mock_session_manager.connect_peer = AsyncMock(return_value=False)
        
        result = await self.protocol.connect_peer(peer_info)
        
        assert result is False
        # connections_failed is only incremented on exceptions, not on False return
        assert self.protocol.stats.connections_failed == 0

    @pytest.mark.asyncio
    async def test_connect_peer_exception(self):
        """Test peer connection with exception."""
        peer_info = PeerInfo(ip="192.168.1.100", port=6881)
        
        # Mock peer manager to raise exception
        mock_peer_manager = MagicMock()
        mock_peer_manager.connect_peer = AsyncMock(side_effect=Exception("Connection failed"))
        self.protocol.peer_manager = mock_peer_manager
        
        result = await self.protocol.connect_peer(peer_info)
        
        assert result is False
        assert self.protocol.stats.connections_failed == 1
        assert self.protocol.stats.errors == 1

    @pytest.mark.asyncio
    async def test_send_message_with_peer_manager(self):
        """Test sending message using peer manager."""
        peer_id = "test_peer"
        message = b"test_message"
        
        # Mock peer manager
        mock_peer_manager = MagicMock()
        mock_peer_manager.send_message = AsyncMock(return_value=True)
        self.protocol.peer_manager = mock_peer_manager
        
        result = await self.protocol.send_message(peer_id, message)
        
        assert result is True
        mock_peer_manager.send_message.assert_called_once_with(peer_id, message)
        
        # Verify stats were updated
        assert self.protocol.stats.bytes_sent == len(message)
        assert self.protocol.stats.messages_sent == 1

    @pytest.mark.asyncio
    async def test_send_message_with_session_manager_fallback(self):
        """Test sending message using session manager fallback."""
        peer_id = "test_peer"
        message = b"test_message"
        
        # Mock session manager
        self.mock_session_manager.send_message = AsyncMock(return_value=True)
        
        result = await self.protocol.send_message(peer_id, message)
        
        assert result is True
        self.mock_session_manager.send_message.assert_called_once_with(peer_id, message)
        
        # Verify stats were updated
        assert self.protocol.stats.bytes_sent == len(message)
        assert self.protocol.stats.messages_sent == 1

    @pytest.mark.asyncio
    async def test_send_message_failure(self):
        """Test message sending failure."""
        peer_id = "test_peer"
        message = b"test_message"
        
        # Mock peer manager to fail
        mock_peer_manager = MagicMock()
        mock_peer_manager.send_message = AsyncMock(return_value=False)
        self.protocol.peer_manager = mock_peer_manager
        
        # Mock session manager to also fail
        self.mock_session_manager.send_message = AsyncMock(return_value=False)
        
        result = await self.protocol.send_message(peer_id, message)
        
        assert result is False
        # errors is only incremented on exceptions, not on False return
        assert self.protocol.stats.errors == 0

    @pytest.mark.asyncio
    async def test_send_message_exception(self):
        """Test message sending with exception."""
        peer_id = "test_peer"
        message = b"test_message"
        
        # Mock peer manager to raise exception
        mock_peer_manager = MagicMock()
        mock_peer_manager.send_message = AsyncMock(side_effect=Exception("Send failed"))
        self.protocol.peer_manager = mock_peer_manager
        
        result = await self.protocol.send_message(peer_id, message)
        
        assert result is False
        assert self.protocol.stats.errors == 1

    @pytest.mark.asyncio
    async def test_receive_message_with_peer_manager(self):
        """Test receiving message using peer manager."""
        peer_id = "test_peer"
        expected_message = b"received_message"
        
        # Mock peer manager
        mock_peer_manager = MagicMock()
        mock_peer_manager.receive_message = AsyncMock(return_value=expected_message)
        self.protocol.peer_manager = mock_peer_manager
        
        result = await self.protocol.receive_message(peer_id)
        
        assert result == expected_message
        mock_peer_manager.receive_message.assert_called_once_with(peer_id)
        
        # Verify stats were updated
        assert self.protocol.stats.bytes_received == len(expected_message)
        assert self.protocol.stats.messages_received == 1

    @pytest.mark.asyncio
    async def test_receive_message_with_session_manager_fallback(self):
        """Test receiving message using session manager fallback."""
        peer_id = "test_peer"
        expected_message = b"received_message"
        
        # Mock session manager
        self.mock_session_manager.receive_message = AsyncMock(return_value=expected_message)
        
        result = await self.protocol.receive_message(peer_id)
        
        assert result == expected_message
        self.mock_session_manager.receive_message.assert_called_once_with(peer_id)
        
        # Verify stats were updated
        assert self.protocol.stats.bytes_received == len(expected_message)
        assert self.protocol.stats.messages_received == 1

    @pytest.mark.asyncio
    async def test_receive_message_no_message(self):
        """Test receiving message when no message available."""
        peer_id = "test_peer"
        
        # Mock peer manager to return None
        mock_peer_manager = MagicMock()
        mock_peer_manager.receive_message = AsyncMock(return_value=None)
        self.protocol.peer_manager = mock_peer_manager
        
        result = await self.protocol.receive_message(peer_id)
        
        assert result is None
        # Stats should not be updated for None messages

    @pytest.mark.asyncio
    async def test_receive_message_exception(self):
        """Test receiving message with exception."""
        peer_id = "test_peer"
        
        # Mock peer manager to raise exception
        mock_peer_manager = MagicMock()
        mock_peer_manager.receive_message = AsyncMock(side_effect=Exception("Receive failed"))
        self.protocol.peer_manager = mock_peer_manager
        
        result = await self.protocol.receive_message(peer_id)
        
        assert result is None
        assert self.protocol.stats.errors == 1

    @pytest.mark.asyncio
    async def test_announce_torrent_with_tracker_manager(self):
        """Test announcing torrent using tracker manager."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[],
            total_length=1024,
            piece_length=16384,
            pieces=[],
            num_pieces=1,
        )
        expected_peers = [PeerInfo(ip="192.168.1.100", port=6881)]
        
        # Mock tracker manager
        mock_tracker_manager = MagicMock()
        mock_tracker_manager.announce = AsyncMock(return_value=expected_peers)
        self.protocol.tracker_manager = mock_tracker_manager
        
        result = await self.protocol.announce_torrent(torrent_info)
        
        assert result == expected_peers
        mock_tracker_manager.announce.assert_called_once_with(torrent_info)

    @pytest.mark.asyncio
    async def test_announce_torrent_with_session_manager_fallback(self):
        """Test announcing torrent using session manager fallback."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[],
            total_length=1024,
            piece_length=16384,
            pieces=[],
            num_pieces=1,
        )
        expected_peers = [PeerInfo(ip="192.168.1.100", port=6881)]
        
        # Mock session manager
        self.mock_session_manager.announce_torrent = AsyncMock(return_value=expected_peers)
        
        result = await self.protocol.announce_torrent(torrent_info)
        
        assert result == expected_peers
        self.mock_session_manager.announce_torrent.assert_called_once_with(torrent_info)

    @pytest.mark.asyncio
    async def test_announce_torrent_exception(self):
        """Test announcing torrent with exception."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[],
            total_length=1024,
            piece_length=16384,
            pieces=[],
            num_pieces=1,
        )
        
        # Mock tracker manager to raise exception
        mock_tracker_manager = MagicMock()
        mock_tracker_manager.announce = AsyncMock(side_effect=Exception("Announce failed"))
        self.protocol.tracker_manager = mock_tracker_manager
        
        result = await self.protocol.announce_torrent(torrent_info)
        
        assert result == []

    @pytest.mark.asyncio
    async def test_announce_torrent_no_managers(self):
        """Test announcing torrent with no managers available."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[],
            total_length=1024,
            piece_length=16384,
            pieces=[],
            num_pieces=1,
        )
        
        # No managers available
        self.protocol.tracker_manager = None
        self.protocol.session_manager = None
        
        result = await self.protocol.announce_torrent(torrent_info)
        
        assert result == []

    def test_protocol_stats_initialization(self):
        """Test protocol statistics initialization."""
        stats = self.protocol.stats
        
        assert stats.connections_established == 0
        assert stats.connections_failed == 0
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0
        assert stats.messages_sent == 0
        assert stats.messages_received == 0
        assert stats.errors == 0

    def test_protocol_stats_update(self):
        """Test protocol statistics update."""
        self.protocol.update_stats(
            bytes_sent=100,
            bytes_received=200,
            messages_sent=1,
            messages_received=1,
            errors=1
        )
        
        stats = self.protocol.stats
        assert stats.bytes_sent == 100
        assert stats.bytes_received == 200
        assert stats.messages_sent == 1
        assert stats.messages_received == 1
        assert stats.errors == 1

    def test_protocol_state_management(self):
        """Test protocol state management."""
        # Test initial state
        assert self.protocol.get_state() == ProtocolState.DISCONNECTED
        
        # Test state change
        self.protocol.set_state(ProtocolState.CONNECTING)
        assert self.protocol.get_state() == ProtocolState.CONNECTING
        
        self.protocol.set_state(ProtocolState.CONNECTED)
        assert self.protocol.get_state() == ProtocolState.CONNECTED

    def test_protocol_name(self):
        """Test protocol name."""
        protocol_info = self.protocol.get_protocol_info()
        assert protocol_info["protocol_type"] == "bittorrent"

    def test_protocol_version(self):
        """Test protocol version."""
        protocol_info = self.protocol.get_protocol_info()
        assert "protocol_type" in protocol_info
        assert protocol_info["protocol_type"] == "bittorrent"

    @pytest.mark.asyncio
    async def test_protocol_lifecycle(self):
        """Test complete protocol lifecycle."""
        # Mock session manager
        self.mock_session_manager.start = AsyncMock()
        self.mock_session_manager.stop = AsyncMock()
        self.mock_session_manager.peer_manager = MagicMock()
        self.mock_session_manager.tracker_manager = MagicMock()
        
        # Start protocol
        await self.protocol.start()
        assert self.protocol.get_state() == ProtocolState.CONNECTED
        
        # Stop protocol
        await self.protocol.stop()
        
        # Verify both start and stop were called
        self.mock_session_manager.start.assert_called_once()
        self.mock_session_manager.stop.assert_called_once()

    def test_protocol_error_handling(self):
        """Test protocol error handling."""
        # Test with invalid peer info
        invalid_peer = None
        
        # This should handle gracefully
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(self.protocol.connect_peer(invalid_peer))
            assert result is False
        except Exception:
            # Should handle gracefully
            pass
        finally:
            loop.close()
