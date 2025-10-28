"""Simple functionality tests for the high-performance BitTorrent client.

These tests verify basic functionality without complex async operations.
"""

import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSimpleFunctionality:
    """Test basic functionality of the BitTorrent client."""

    def test_config_loading(self):
        """Test that configuration can be loaded."""
        from ccbt.config import get_config

        config = get_config()
        assert config is not None
        assert hasattr(config, "network")
        assert hasattr(config, "disk")

    def test_config_values(self):
        """Test that configuration has expected values."""
        from ccbt.config import get_config

        config = get_config()

        # Test some basic config values
        assert config.network.max_global_peers == 200
        assert config.disk.write_batch_kib == 64
        assert config.strategy.piece_selection.value == "rarest_first"

    def test_peer_info_creation(self):
        """Test PeerInfo creation."""
        from ccbt.peer import PeerInfo

        peer = PeerInfo(ip="127.0.0.1", port=6881)
        assert peer.ip == "127.0.0.1"
        assert peer.port == 6881

    def test_message_types(self):
        """Test message type constants."""
        from ccbt.peer import MessageType

        assert MessageType.CHOKE == 0
        assert MessageType.UNCHOKE == 1
        assert MessageType.INTERESTED == 2
        assert MessageType.NOT_INTERESTED == 3
        assert MessageType.HAVE == 4
        assert MessageType.BITFIELD == 5
        assert MessageType.REQUEST == 6
        assert MessageType.PIECE == 7
        assert MessageType.CANCEL == 8

    def test_piece_state_enum(self):
        """Test PieceState enum."""
        from ccbt.async_piece_manager import PieceState

        assert PieceState.MISSING.value == "missing"
        assert PieceState.DOWNLOADING.value == "downloading"
        assert PieceState.COMPLETE.value == "complete"
        assert PieceState.VERIFIED.value == "verified"

    def test_torrent_parser_basic(self):
        """Test basic torrent parsing functionality."""
        from ccbt.torrent import TorrentParser

        # Create a minimal test torrent data

        parser = TorrentParser()
        # This would normally parse a file, but we'll just test the class exists
        assert parser is not None

    def test_bencode_encoding(self):
        """Test bencode encoding."""
        from ccbt.bencode import BencodeEncoder

        encoder = BencodeEncoder()

        # Test encoding a simple string
        result = encoder.encode("hello")
        assert result == b"5:hello"

        # Test encoding a number
        result = encoder.encode(42)
        assert result == b"i42e"

        # Test encoding a list
        result = encoder.encode([1, 2, 3])
        assert result == b"li1ei2ei3ee"

    def test_bencode_decoding(self):
        """Test bencode decoding."""
        from ccbt.bencode import BencodeDecoder

        decoder = BencodeDecoder(b"5:hello")
        result = decoder.decode()
        assert result == b"hello"

        decoder = BencodeDecoder(b"i42e")
        result = decoder.decode()
        assert result == 42

        decoder = BencodeDecoder(b"li1ei2ei3ee")
        result = decoder.decode()
        assert result == [1, 2, 3]

    def test_magnet_parsing(self):
        """Test magnet link parsing."""
        from ccbt.magnet import parse_magnet

        # Test with a simple magnet link
        magnet_uri = (
            "magnet:?xt=urn:btih:1234567890123456789012345678901234567890&dn=test"
        )
        magnet_info = parse_magnet(magnet_uri)

        assert (
            magnet_info.info_hash
            == b"\x12\x34\x56\x78\x90\x12\x34\x56\x78\x90\x12\x34\x56\x78\x90\x12\x34\x56\x78\x90"
        )
        assert magnet_info.display_name == "test"

    def test_metrics_collector_creation(self):
        """Test metrics collector creation."""
        from ccbt.metrics import MetricsCollector

        collector = MetricsCollector()
        assert collector is not None
        assert hasattr(collector, "global_download_rate")
        assert hasattr(collector, "global_upload_rate")

    def test_metrics_summary(self):
        """Test metrics summary generation."""
        from ccbt.metrics import MetricsCollector

        collector = MetricsCollector()
        summary = collector.get_metrics_summary()

        assert "global" in summary
        assert "system" in summary
        assert "torrents" in summary
        assert "peers" in summary

    def test_pex_manager_creation(self):
        """Test PEX manager creation."""
        from ccbt.pex import AsyncPexManager

        manager = AsyncPexManager()
        assert manager is not None
        assert hasattr(manager, "known_peers")
        assert hasattr(manager, "sessions")

    def test_dht_client_creation(self):
        """Test DHT client creation."""
        from ccbt.dht import AsyncDHTClient

        client = AsyncDHTClient()
        assert client is not None
        assert hasattr(client, "routing_table")

    def test_tracker_response_creation(self):
        """Test tracker response creation."""
        from ccbt.tracker import TrackerResponse

        response = TrackerResponse(
            interval=1800,
            peers=[{"ip": "127.0.0.1", "port": 6881}],
        )

        assert response.interval == 1800
        assert len(response.peers) == 1
        assert response.peers[0]["ip"] == "127.0.0.1"
        assert response.peers[0]["port"] == 6881

    def test_socket_optimizer_creation(self):
        """Test socket optimizer creation."""
        from ccbt.peer import SocketOptimizer

        optimizer = SocketOptimizer()
        assert optimizer is not None
        assert hasattr(optimizer, "config")
        assert hasattr(optimizer, "logger")

    def test_file_segment_creation(self):
        """Test file segment creation."""
        from ccbt.file_assembler import FileSegment

        segment = FileSegment(
            file_path="test.txt",
            piece_index=0,
            piece_offset=0,
            start_offset=0,
            end_offset=1024,
        )

        assert segment.file_path == "test.txt"
        assert segment.piece_index == 0
        assert segment.piece_offset == 0
        assert segment.start_offset == 0
        assert segment.end_offset == 1024

    def test_write_request_creation(self):
        """Test write request creation."""
        from pathlib import Path

        from ccbt.disk_io import WriteRequest

        request = WriteRequest(
            file_path=Path("test.txt"),
            offset=0,
            data=b"test data",
            future=asyncio.Future(),
        )

        assert request.file_path == Path("test.txt")
        assert request.offset == 0
        assert request.data == b"test data"
        assert request.future is not None

    def test_pex_peer_creation(self):
        """Test PEX peer creation."""
        from ccbt.pex import PexPeer

        peer = PexPeer(ip="127.0.0.1", port=6881)
        assert peer.ip == "127.0.0.1"
        assert peer.port == 6881
        assert peer.source == "pex"
        assert peer.reliability_score == 1.0

    def test_peer_metrics_creation(self):
        """Test peer metrics creation."""
        from ccbt.metrics import PeerMetrics

        metrics = PeerMetrics(peer_key="test_peer")
        assert metrics.peer_key == "test_peer"
        assert metrics.bytes_downloaded == 0
        assert metrics.bytes_uploaded == 0
        assert metrics.download_rate == 0.0
        assert metrics.upload_rate == 0.0

    def test_torrent_metrics_creation(self):
        """Test torrent metrics creation."""
        from ccbt.metrics import TorrentMetrics

        metrics = TorrentMetrics(torrent_id="test_torrent")
        assert metrics.torrent_id == "test_torrent"
        assert metrics.bytes_downloaded == 0
        assert metrics.bytes_uploaded == 0
        assert metrics.pieces_completed == 0
        assert metrics.pieces_total == 0
        assert metrics.progress == 0.0

    def test_all_classes_instantiable(self):
        """Test that all main classes can be instantiated."""
        # Test that we can create instances of main classes
        from pathlib import Path

        from ccbt.config import Config
        from ccbt.dht import AsyncDHTClient
        from ccbt.disk_io import WriteRequest
        from ccbt.file_assembler import FileSegment
        from ccbt.metrics import MetricsCollector, PeerMetrics, TorrentMetrics
        from ccbt.peer import PeerInfo, SocketOptimizer
        from ccbt.pex import AsyncPexManager, PexPeer
        from ccbt.tracker import TrackerResponse

        # Create instances
        config = Config()
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        socket_opt = SocketOptimizer()
        metrics = MetricsCollector()
        peer_metrics = PeerMetrics("test")
        torrent_metrics = TorrentMetrics("test")
        pex_manager = AsyncPexManager()
        pex_peer = PexPeer("127.0.0.1", 6881)
        dht_client = AsyncDHTClient()
        tracker_response = TrackerResponse(1800, [])
        file_segment = FileSegment("test.txt", 0, 0, 0, 1024)
        write_request = WriteRequest(Path("test.txt"), 0, b"data", asyncio.Future())

        # Verify they were created
        assert config is not None
        assert peer_info is not None
        assert socket_opt is not None
        assert metrics is not None
        assert peer_metrics is not None
        assert torrent_metrics is not None
        assert pex_manager is not None
        assert pex_peer is not None
        assert dht_client is not None
        assert tracker_response is not None
        assert file_segment is not None
        assert write_request is not None
