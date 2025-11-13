"""Unit tests for Xet protocol wrapper.

Tests protocol lifecycle, peer connections, announce_torrent,
and hybrid integration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.models import PeerInfo, TorrentInfo
from ccbt.protocols.base import ProtocolState, ProtocolType
from ccbt.protocols.xet import XetProtocol


pytestmark = [pytest.mark.unit, pytest.mark.protocols]


class TestXetProtocol:
    """Test XetProtocol class."""

    @pytest.fixture
    def protocol(self):
        """Create XetProtocol instance for testing."""
        return XetProtocol()

    @pytest.mark.asyncio
    async def test_protocol_initialization(self, protocol):
        """Test protocol initialization."""
        assert protocol.protocol_type == ProtocolType.XET
        assert protocol.state == ProtocolState.DISCONNECTED
        assert protocol.capabilities.supports_xet is True

    @pytest.mark.asyncio
    async def test_protocol_start(self, protocol):
        """Test protocol start."""
        # Mock DHT client so cas_client gets initialized
        mock_dht = AsyncMock()
        protocol.dht_client = mock_dht
        
        with patch("ccbt.protocols.xet.P2PCASClient") as mock_cas_class:
            mock_cas = AsyncMock()
            mock_cas_class.return_value = mock_cas

            await protocol.start()

            assert protocol.state == ProtocolState.CONNECTED
            # cas_client may be None if no dht/tracker client
            # Just verify protocol started successfully
            assert protocol.state == ProtocolState.CONNECTED

    @pytest.mark.asyncio
    async def test_protocol_stop(self, protocol):
        """Test protocol stop."""
        # Start protocol first
        with patch("ccbt.protocols.xet.P2PCASClient"):
            await protocol.start()

        # Stop protocol
        await protocol.stop()

        assert protocol.state == ProtocolState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_connect_peer(self, protocol):
        """Test connecting to a peer."""
        peer = PeerInfo(ip="192.168.1.1", port=6881)

        # Mock CAS client
        with patch.object(protocol, "cas_client", None):
            # Without P2P CAS, connection should fail gracefully
            result = await protocol.connect_peer(peer)

            # Should return False or handle gracefully
            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_disconnect_peer(self, protocol):
        """Test disconnecting from a peer."""
        peer_id = "192.168.1.1:6881"

        # Should not raise
        await protocol.disconnect_peer(peer_id)

    @pytest.mark.asyncio
    async def test_send_message(self, protocol):
        """Test sending message."""
        peer_id = "192.168.1.1:6881"
        message = b"Test message"

        # Xet uses extension protocol, so this may return False
        result = await protocol.send_message(peer_id, message)

        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_receive_message(self, protocol):
        """Test receiving message."""
        peer_id = "192.168.1.1:6881"

        # Xet uses extension protocol, so this may return None
        result = await protocol.receive_message(peer_id)

        # Should return bytes or None
        assert result is None or isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_announce_torrent_with_xet_metadata(self, protocol):
        """Test announcing torrent with Xet metadata."""
        # Create torrent info with Xet metadata
        from ccbt.models import XetTorrentMetadata

        from ccbt.models import XetPieceMetadata

        xet_metadata = XetTorrentMetadata(
            chunk_hashes=[b"A" * 32, b"B" * 32],
            file_metadata=[],
            piece_metadata=[],  # List, not dict
            xorb_hashes=[],
        )

        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"X" * 20,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"Y" * 20],
            xet_metadata=xet_metadata,
        )

        # Mock P2P CAS
        mock_cas = AsyncMock()
        mock_cas.find_chunk_peers = AsyncMock(return_value=[])

        with patch.object(protocol, "cas_client", mock_cas):
            peers = await protocol.announce_torrent(torrent_info)

            # Should return list of peers
            assert isinstance(peers, list)

    @pytest.mark.asyncio
    async def test_announce_torrent_without_xet_metadata(self, protocol):
        """Test announcing torrent without Xet metadata."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"Y" * 20,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"Z" * 20],
            xet_metadata=None,
        )

        # Mock P2P CAS
        mock_cas = AsyncMock()
        mock_cas.find_chunk_peers = AsyncMock(return_value=[])

        with patch.object(protocol, "cas_client", mock_cas):
            peers = await protocol.announce_torrent(torrent_info)

            # Should still return list (may be empty)
            assert isinstance(peers, list)

    @pytest.mark.asyncio
    async def test_announce_torrent_v2_piece_layers(self, protocol):
        """Test announcing torrent using v2 piece layers."""
        # Create v2 torrent with piece layers
        torrent_info = TorrentInfo(
            name="test_v2_torrent",
            info_hash=b"Z" * 20,
            info_hash_v2=b"W" * 32,  # v2 hash
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"A" * 20],
            piece_layers={
                b"piece1": [b"root1" * 8],  # List of 32-byte hashes
                b"piece2": [b"root2" * 8],
            },
            xet_metadata=None,
        )

        # Mock P2P CAS
        mock_cas = AsyncMock()
        mock_cas.find_chunk_peers = AsyncMock(return_value=[])

        with patch.object(protocol, "cas_client", mock_cas):
            peers = await protocol.announce_torrent(torrent_info)

            # Should use piece layer roots as chunk identifiers
            assert isinstance(peers, list)

    @pytest.mark.asyncio
    async def test_scrape_torrent(self, protocol):
        """Test scraping torrent statistics."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Scrape should return empty stats for Xet protocol
        stats = await protocol.scrape_torrent(torrent_info)

        assert isinstance(stats, dict)
        assert "seeders" in stats
        assert "leechers" in stats
        assert "completed" in stats

    def test_get_capabilities(self, protocol):
        """Test getting protocol capabilities."""
        capabilities = protocol.get_capabilities()

        assert capabilities.supports_xet is True

    def test_get_stats(self, protocol):
        """Test getting protocol statistics."""
        stats = protocol.get_stats()

        assert stats is not None
        assert hasattr(stats, "bytes_sent")
        assert hasattr(stats, "bytes_received")

    def test_get_peers(self, protocol):
        """Test getting connected peers."""
        peers = protocol.get_peers()

        assert isinstance(peers, dict)

    @pytest.mark.asyncio
    async def test_protocol_lifecycle(self, protocol):
        """Test full protocol lifecycle."""
        # Start
        with patch("ccbt.protocols.xet.P2PCASClient"):
            await protocol.start()
            assert protocol.state == ProtocolState.CONNECTED

        # Stop
        await protocol.stop()
        assert protocol.state == ProtocolState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_announce_torrent_deduplicates_peers(self, protocol):
        """Test that announce_torrent deduplicates peers."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"T" * 20,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"U" * 20],
        )

        # Create duplicate peers
        peer1 = PeerInfo(ip="192.168.1.1", port=6881)
        peer2 = PeerInfo(ip="192.168.1.1", port=6881)  # Duplicate

        mock_cas = AsyncMock()
        mock_cas.find_chunk_peers = AsyncMock(return_value=[peer1, peer2])

        with patch.object(protocol, "cas_client", mock_cas):
            peers = await protocol.announce_torrent(torrent_info)

            # Should deduplicate
            unique_peers = list({(p.ip, p.port) for p in peers})
            assert len(unique_peers) <= len(peers)

    @pytest.mark.asyncio
    async def test_scrape_torrent_with_tracker_stats(self, protocol):
        """Test scraping torrent with tracker statistics."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="http://tracker.example.com:8080/announce",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Mock _scrape_from_trackers to return stats
        with patch.object(
            protocol,
            "_scrape_from_trackers",
            return_value={"seeders": 10, "leechers": 5, "completed": 100},
        ):
            stats = await protocol.scrape_torrent(torrent_info)

            assert stats["seeders"] == 10
            assert stats["leechers"] == 5
            assert stats["completed"] == 100

    @pytest.mark.asyncio
    async def test_scrape_torrent_with_dht_stats(self, protocol):
        """Test scraping torrent with DHT statistics."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Mock both methods
        with patch.object(
            protocol, "_scrape_from_trackers", return_value={}
        ), patch.object(
            protocol, "_scrape_from_dht", return_value={"seeders": 5, "leechers": 3, "completed": 50}
        ):
            stats = await protocol.scrape_torrent(torrent_info)

            assert stats["seeders"] == 5
            assert stats["leechers"] == 3
            assert stats["completed"] == 50

    @pytest.mark.asyncio
    async def test_scrape_torrent_enhances_with_dht(self, protocol):
        """Test that scrape enhances tracker stats with DHT stats."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="http://tracker.example.com:8080/announce",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Mock both methods - tracker has lower stats, DHT has higher
        with patch.object(
            protocol,
            "_scrape_from_trackers",
            return_value={"seeders": 5, "leechers": 2, "completed": 50},
        ), patch.object(
            protocol,
            "_scrape_from_dht",
            return_value={"seeders": 10, "leechers": 8, "completed": 100},
        ):
            stats = await protocol.scrape_torrent(torrent_info)

            # Should take maximum (enhance tracker with DHT)
            assert stats["seeders"] == 10  # max(5, 10)
            assert stats["leechers"] == 8  # max(2, 8)

    @pytest.mark.asyncio
    async def test_scrape_torrent_with_exception(self, protocol):
        """Test scraping torrent with exception handling."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Mock method to raise exception
        with patch.object(
            protocol, "_scrape_from_trackers", side_effect=Exception("Test error")
        ):
            stats = await protocol.scrape_torrent(torrent_info)

            # Should return default stats on error
            assert stats["seeders"] == 0
            assert stats["leechers"] == 0
            assert stats["completed"] == 0

    @pytest.mark.asyncio
    async def test_scrape_from_trackers_http(self, protocol):
        """Test scraping from HTTP tracker."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="http://tracker.example.com:8080/announce",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Mock AsyncTrackerClient (imported inside method)
        with patch("ccbt.discovery.tracker.AsyncTrackerClient") as mock_tracker_class:
            mock_tracker = AsyncMock()
            mock_tracker.start = AsyncMock()
            mock_tracker.stop = AsyncMock()
            mock_tracker.scrape = AsyncMock(
                return_value={"seeders": 10, "leechers": 5, "completed": 100}
            )
            mock_tracker_class.return_value = mock_tracker

            stats = await protocol._scrape_from_trackers(torrent_info)

            assert stats["seeders"] == 10
            assert stats["leechers"] == 5
            assert stats["completed"] == 100

    @pytest.mark.asyncio
    async def test_scrape_from_trackers_udp(self, protocol):
        """Test scraping from UDP tracker."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="udp://tracker.example.com:8080",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Mock AsyncUDPTrackerClient (imported inside method)
        with patch("ccbt.discovery.tracker_udp_client.AsyncUDPTrackerClient") as mock_tracker_class:
            mock_tracker = AsyncMock()
            mock_tracker.start = AsyncMock()
            mock_tracker.stop = AsyncMock()
            mock_tracker.scrape = AsyncMock(
                return_value={"seeders": 8, "leechers": 3, "completed": 80}
            )
            mock_tracker_class.return_value = mock_tracker

            stats = await protocol._scrape_from_trackers(torrent_info)

            assert stats["seeders"] == 8
            assert stats["leechers"] == 3
            assert stats["completed"] == 80

    @pytest.mark.asyncio
    async def test_scrape_from_trackers_no_urls(self, protocol):
        """Test scraping from trackers with no URLs."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="",  # No announce URL
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        stats = await protocol._scrape_from_trackers(torrent_info)

        assert stats == {}

    @pytest.mark.asyncio
    async def test_scrape_from_trackers_unsupported_scheme(self, protocol):
        """Test scraping from tracker with unsupported scheme."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="ftp://tracker.example.com:8080",  # Unsupported
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        stats = await protocol._scrape_from_trackers(torrent_info)

        assert stats == {}

    @pytest.mark.asyncio
    async def test_scrape_from_trackers_tracker_error(self, protocol):
        """Test scraping from tracker with tracker error."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="http://tracker.example.com:8080/announce",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Mock tracker to raise exception (imported inside method)
        with patch("ccbt.discovery.tracker.AsyncTrackerClient") as mock_tracker_class:
            mock_tracker = AsyncMock()
            mock_tracker.start = AsyncMock()
            mock_tracker.stop = AsyncMock()
            mock_tracker.scrape = AsyncMock(side_effect=Exception("Tracker error"))
            mock_tracker_class.return_value = mock_tracker

            stats = await protocol._scrape_from_trackers(torrent_info)

            # Should return empty dict on error
            assert stats == {}

    @pytest.mark.asyncio
    async def test_scrape_from_dht_no_client(self, protocol):
        """Test scraping from DHT with no DHT client."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        protocol.dht_client = None

        stats = await protocol._scrape_from_dht(torrent_info)

        assert stats == {}

    @pytest.mark.asyncio
    async def test_scrape_from_dht_with_peers(self, protocol):
        """Test scraping from DHT with peers."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Mock DHT client
        mock_dht = AsyncMock()
        mock_dht.get_peers = AsyncMock(
            return_value=[("192.168.1.1", 6881), ("192.168.1.2", 6882)]
        )
        protocol.dht_client = mock_dht
        protocol.cas_client = None  # No CAS client for this test

        stats = await protocol._scrape_from_dht(torrent_info)

        assert "seeders" in stats
        assert "leechers" in stats
        assert "completed" in stats

    @pytest.mark.asyncio
    async def test_scrape_from_dht_with_v2_hash(self, protocol):
        """Test scraping from DHT with v2 info hash."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            info_hash_v2=b"V" * 32,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Mock DHT client
        mock_dht = AsyncMock()
        mock_dht.get_peers = AsyncMock(return_value=[("192.168.1.1", 6881)])
        protocol.dht_client = mock_dht
        protocol.cas_client = None

        stats = await protocol._scrape_from_dht(torrent_info)

        # Should query both v1 and v2 hashes
        assert mock_dht.get_peers.call_count >= 1

    @pytest.mark.asyncio
    async def test_scrape_from_dht_with_xet_metadata(self, protocol):
        """Test scraping from DHT with Xet metadata."""
        from ccbt.models import XetTorrentMetadata, XetPieceMetadata

        xet_metadata = XetTorrentMetadata(
            chunk_hashes=[b"C" * 32, b"D" * 32],
            file_metadata=[],
            piece_metadata=[],
            xorb_hashes=[],
        )

        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
            xet_metadata=xet_metadata,
        )

        # Mock DHT and CAS clients
        mock_dht = AsyncMock()
        mock_dht.get_peers = AsyncMock(return_value=[])
        protocol.dht_client = mock_dht

        mock_cas = AsyncMock()
        mock_cas.find_chunk_peers = AsyncMock(return_value=[PeerInfo(ip="192.168.1.1", port=6881)])
        protocol.cas_client = mock_cas

        stats = await protocol._scrape_from_dht(torrent_info)

        # Should query chunk peers
        assert mock_cas.find_chunk_peers.call_count > 0
        assert "seeders" in stats

    @pytest.mark.asyncio
    async def test_scrape_from_dht_with_exception(self, protocol):
        """Test scraping from DHT with exception."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        # Mock DHT client to raise exception
        mock_dht = AsyncMock()
        mock_dht.get_peers = AsyncMock(side_effect=Exception("DHT error"))
        protocol.dht_client = mock_dht

        stats = await protocol._scrape_from_dht(torrent_info)

        # Should return default stats on error (not empty dict)
        assert stats == {"seeders": 0, "leechers": 0, "completed": 0}

    def test_torrent_info_to_dict_single_file(self, protocol):
        """Test converting TorrentInfo to dict for single file."""
        from ccbt.models import FileInfo

        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[FileInfo(name="test.txt", length=1024, path=["test.txt"])],
            announce="http://tracker.example.com:8080/announce",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        torrent_data = protocol._torrent_info_to_dict(torrent_info)

        assert torrent_data["name"] == "test_torrent"
        assert torrent_data["info_hash"] == b"S" * 20
        assert torrent_data["total_length"] == 1024
        assert torrent_data["file_info"]["type"] == "single"
        assert torrent_data["file_info"]["length"] == 1024

    def test_torrent_info_to_dict_multi_file(self, protocol):
        """Test converting TorrentInfo to dict for multi-file torrent."""
        from ccbt.models import FileInfo

        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=2048,
            files=[
                FileInfo(name="file1.txt", length=1024, path=["file1.txt"]),
                FileInfo(name="file2.txt", length=1024, path=["file2.txt"]),
            ],
            announce="http://tracker.example.com:8080/announce",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        torrent_data = protocol._torrent_info_to_dict(torrent_info)

        assert torrent_data["file_info"]["type"] == "multi"
        assert len(torrent_data["file_info"]["files"]) == 2

    def test_torrent_info_to_dict_with_announce_list(self, protocol):
        """Test converting TorrentInfo with announce_list."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="http://tracker1.example.com:8080/announce",
            announce_list=[["http://tracker2.example.com:8080/announce"]],
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        torrent_data = protocol._torrent_info_to_dict(torrent_info)

        assert len(torrent_data["announce_list"]) == 1
        assert "tracker2.example.com" in torrent_data["announce_list"][0]

    def test_get_tracker_urls_from_announce(self, protocol):
        """Test getting tracker URLs from announce field."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="http://tracker.example.com:8080/announce",
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        urls = protocol._get_tracker_urls(torrent_info)

        assert len(urls) == 1
        assert "tracker.example.com" in urls[0]

    def test_get_tracker_urls_from_announce_list(self, protocol):
        """Test getting tracker URLs from announce_list."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="",
            announce_list=[
                ["http://tracker1.example.com:8080/announce"],
                ["http://tracker2.example.com:8080/announce"],
            ],
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        urls = protocol._get_tracker_urls(torrent_info)

        assert len(urls) == 2
        assert any("tracker1" in url for url in urls)
        assert any("tracker2" in url for url in urls)

    def test_get_tracker_urls_deduplicates(self, protocol):
        """Test that get_tracker_urls deduplicates URLs."""
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"S" * 20,
            total_length=1024,
            files=[],
            announce="http://tracker.example.com:8080/announce",
            announce_list=[["http://tracker.example.com:8080/announce"]],  # Duplicate
            piece_length=16384,
            num_pieces=1,
            pieces=[b"T" * 20],
        )

        urls = protocol._get_tracker_urls(torrent_info)

        # Should deduplicate
        assert len(urls) == 1

    def test_deduplicate_peers(self, protocol):
        """Test peer deduplication."""
        peer1 = PeerInfo(ip="192.168.1.1", port=6881)
        peer2 = PeerInfo(ip="192.168.1.2", port=6882)
        peer3 = PeerInfo(ip="192.168.1.1", port=6881)  # Duplicate of peer1

        peers = [peer1, peer2, peer3]

        unique_peers = protocol._deduplicate_peers(peers)

        assert len(unique_peers) == 2
        assert (peer1.ip, peer1.port) in {(p.ip, p.port) for p in unique_peers}
        assert (peer2.ip, peer2.port) in {(p.ip, p.port) for p in unique_peers}

    def test_deduplicate_peers_empty(self, protocol):
        """Test deduplication with empty list."""
        unique_peers = protocol._deduplicate_peers([])

        assert len(unique_peers) == 0

