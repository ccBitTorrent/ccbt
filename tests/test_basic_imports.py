"""Basic import tests to verify the high-performance BitTorrent client modules can be imported.

These tests ensure all the async components are properly structured and can be imported
without syntax errors.
"""

import os
import sys

import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBasicImports:
    """Test basic imports of all modules."""

    def test_config_import(self):
        """Test config module import."""
        from ccbt.config import get_config

        config = get_config()
        assert config is not None

    def test_disk_io_import(self):
        """Test disk I/O module import."""
        from ccbt.disk_io import (
            DiskIOManager,
            preallocate_file,
            read_block_async,
            write_block_async,
        )

        assert DiskIOManager is not None
        assert preallocate_file is not None
        assert write_block_async is not None
        assert read_block_async is not None

    def test_async_peer_connection_import(self):
        """Test async peer connection module import."""
        from ccbt.async_peer_connection import AsyncPeerConnectionManager

        assert AsyncPeerConnectionManager is not None

    def test_async_piece_manager_import(self):
        """Test async piece manager module import."""
        from ccbt.async_piece_manager import AsyncPieceManager, PieceState

        assert AsyncPieceManager is not None
        assert PieceState is not None

    def test_async_metadata_exchange_import(self):
        """Test async metadata exchange module import."""
        from ccbt.async_metadata_exchange import fetch_metadata_from_peers_async

        assert fetch_metadata_from_peers_async is not None

    def test_tracker_udp_client_import(self):
        """Test UDP tracker client module import."""
        from ccbt.tracker_udp_client import AsyncUDPTrackerClient

        assert AsyncUDPTrackerClient is not None

    def test_dht_import(self):
        """Test DHT module import."""
        from ccbt.dht import AsyncDHTClient

        assert AsyncDHTClient is not None

    def test_pex_import(self):
        """Test PEX module import."""
        from ccbt.pex import AsyncPexManager

        assert AsyncPexManager is not None

    def test_metrics_import(self):
        """Test metrics module import."""
        from ccbt.metrics import MetricsCollector

        assert MetricsCollector is not None

    def test_peer_import(self):
        """Test peer module import."""
        from ccbt.peer import MessageType, PeerInfo, SocketOptimizer

        assert PeerInfo is not None
        assert MessageType is not None
        assert SocketOptimizer is not None

    def test_file_assembler_import(self):
        """Test file assembler module import."""
        from ccbt.file_assembler import AsyncDownloadManager, AsyncFileAssembler

        assert AsyncFileAssembler is not None
        assert AsyncDownloadManager is not None

    def test_tracker_import(self):
        """Test tracker module import."""
        from ccbt.tracker import AsyncTrackerClient, TrackerResponse

        assert AsyncTrackerClient is not None
        assert TrackerResponse is not None

    def test_session_import(self):
        """Test session module import."""
        from ccbt.session import AsyncSessionManager, AsyncTorrentSession

        assert AsyncSessionManager is not None
        assert AsyncTorrentSession is not None

    def test_magnet_import(self):
        """Test magnet module import."""
        from ccbt.magnet import build_minimal_torrent_data, parse_magnet

        assert parse_magnet is not None
        assert build_minimal_torrent_data is not None

    def test_torrent_import(self):
        """Test torrent module import."""
        from ccbt.torrent import TorrentParser

        assert TorrentParser is not None

    def test_bencode_import(self):
        """Test bencode module import."""
        from ccbt.bencode import BencodeDecoder, BencodeEncoder

        assert BencodeDecoder is not None
        assert BencodeEncoder is not None

    def test_all_modules_importable(self):
        """Test that all modules can be imported without errors."""
        # This test verifies that the entire codebase can be imported
        # without syntax errors or missing dependencies
        try:
            import ccbt
            import ccbt.async_metadata_exchange
            import ccbt.async_peer_connection
            import ccbt.async_piece_manager
            import ccbt.bencode
            import ccbt.config
            import ccbt.dht
            import ccbt.disk_io
            import ccbt.file_assembler
            import ccbt.magnet
            import ccbt.metrics
            import ccbt.peer
            import ccbt.pex
            import ccbt.session
            import ccbt.torrent
            import ccbt.tracker
            import ccbt.tracker_udp_client

            # Verify tracker_udp_client is importable
            assert ccbt.tracker_udp_client is not None
        except ImportError as e:
            pytest.fail(f"Failed to import module: {e}")
        except SyntaxError as e:
            pytest.fail(f"Syntax error in module: {e}")
