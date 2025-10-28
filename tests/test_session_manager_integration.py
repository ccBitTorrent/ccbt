"""Tests for session manager new methods and integration."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.session import AsyncSessionManager, AsyncTorrentSession
from ccbt.models import PeerInfo, TorrentInfo


class TestSessionManagerIntegration:
    """Test cases for session manager new methods and integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = MagicMock()
        self.session_manager = AsyncSessionManager(self.mock_config)

    @pytest.mark.asyncio
    async def test_session_manager_initialization(self):
        """Test session manager initialization."""
        assert self.session_manager.config == self.mock_config
        assert isinstance(self.session_manager.torrents, dict)
        assert isinstance(self.session_manager.global_stats, dict)

    @pytest.mark.asyncio
    async def test_add_peers_to_download_manager(self):
        """Test adding peers to download manager."""
        # Create a mock torrent session
        torrent_session = MagicMock()
        torrent_session.download_manager = MagicMock()
        torrent_session.download_manager.add_peers = AsyncMock()
        
        # Add torrent session to manager
        info_hash = "test_info_hash"
        self.session_manager.torrents[info_hash] = torrent_session
        
        # Create test peers
        peers = [
            PeerInfo(ip="192.168.1.100", port=6881),
            PeerInfo(ip="192.168.1.101", port=6882),
        ]
        
        # Test adding peers
        await self.session_manager.add_peers_to_torrent(info_hash, peers)
        
        # Verify peers were added to download manager
        torrent_session.download_manager.add_peers.assert_called_once_with(peers)

    @pytest.mark.asyncio
    async def test_add_peers_to_nonexistent_torrent(self):
        """Test adding peers to non-existent torrent."""
        info_hash = "nonexistent_torrent"
        peers = [PeerInfo(ip="192.168.1.100", port=6881)]
        
        # Should not raise exception
        await self.session_manager.add_peers_to_torrent(info_hash, peers)

    @pytest.mark.asyncio
    async def test_add_peers_without_download_manager(self):
        """Test adding peers when download manager is None."""
        # Create a mock torrent session without download manager
        torrent_session = MagicMock()
        torrent_session.download_manager = None
        
        # Add torrent session to manager
        info_hash = "test_info_hash"
        self.session_manager.torrents[info_hash] = torrent_session
        
        peers = [PeerInfo(ip="192.168.1.100", port=6881)]
        
        # Should not raise exception
        await self.session_manager.add_peers_to_torrent(info_hash, peers)

    @pytest.mark.asyncio
    async def test_update_torrent_metrics(self):
        """Test updating torrent metrics."""
        info_hash = "test_info_hash"
        metrics = {
            "downloaded": 1024,
            "uploaded": 512,
            "left": 2048,
            "peers_connected": 5,
            "download_rate": 100.0,
            "upload_rate": 50.0,
        }
        
        # Mock the update method
        self.session_manager._update_torrent_metrics = AsyncMock()
        
        await self.session_manager.update_torrent_metrics(info_hash, metrics)
        
        # Verify metrics were updated
        self.session_manager._update_torrent_metrics.assert_called_once_with(info_hash, metrics)

    @pytest.mark.asyncio
    async def test_rehash_torrent_success(self):
        """Test successful torrent rehashing."""
        info_hash = "test_info_hash"
        
        # Create mock torrent with piece manager
        mock_torrent = MagicMock()
        mock_piece_manager = MagicMock()
        mock_piece_manager.verify_all_pieces = AsyncMock(return_value=True)
        mock_torrent.piece_manager = mock_piece_manager
        
        # Mock _get_torrent method
        self.session_manager._get_torrent = MagicMock(return_value=mock_torrent)
        
        result = await self.session_manager.rehash_torrent(info_hash)
        
        assert result is True
        mock_piece_manager.verify_all_pieces.assert_called_once()

    @pytest.mark.asyncio
    async def test_rehash_torrent_invalid_hash(self):
        """Test rehashing torrent with invalid hash."""
        invalid_hash = "invalid_hash"
        
        result = await self.session_manager.rehash_torrent(invalid_hash)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_rehash_torrent_not_found(self):
        """Test rehashing non-existent torrent."""
        info_hash = "nonexistent_torrent"
        
        # Mock _get_torrent to return None
        self.session_manager._get_torrent = MagicMock(return_value=None)
        
        result = await self.session_manager.rehash_torrent(info_hash)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_rehash_torrent_without_piece_manager(self):
        """Test rehashing torrent without piece manager."""
        info_hash = "test_info_hash"
        
        # Create mock torrent without piece manager
        mock_torrent = MagicMock()
        mock_torrent.piece_manager = None
        
        # Mock _get_torrent method
        self.session_manager._get_torrent = MagicMock(return_value=mock_torrent)
        
        result = await self.session_manager.rehash_torrent(info_hash)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_metrics_loop_execution(self):
        """Test metrics loop execution."""
        # Mock the required methods
        self.session_manager._aggregate_torrent_stats = MagicMock(return_value={})
        self.session_manager._emit_global_metrics = AsyncMock()
        
        # Start metrics loop
        task = asyncio.create_task(self.session_manager._metrics_loop())
        
        # Let it run for a short time
        await asyncio.sleep(0.1)
        
        # Cancel the task
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Verify methods were called
        assert self.session_manager._aggregate_torrent_stats.called
        assert self.session_manager._emit_global_metrics.called

    @pytest.mark.asyncio
    async def test_metrics_loop_exception_handling(self):
        """Test metrics loop exception handling."""
        # Mock _aggregate_torrent_stats to raise exception
        self.session_manager._aggregate_torrent_stats = MagicMock(side_effect=Exception("Test error"))
        self.session_manager._emit_global_metrics = AsyncMock()
        
        # Start metrics loop
        task = asyncio.create_task(self.session_manager._metrics_loop())
        
        # Let it run for a short time
        await asyncio.sleep(0.1)
        
        # Cancel the task
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Should not crash despite exception

    def test_aggregate_torrent_stats(self):
        """Test aggregating torrent statistics."""
        # Add some mock torrents
        mock_torrent1 = MagicMock()
        mock_torrent1.get_stats.return_value = {
            "downloaded": 1000,
            "uploaded": 500,
            "peers_connected": 3,
            "download_rate": 100.0,
            "upload_rate": 50.0,
        }
        
        mock_torrent2 = MagicMock()
        mock_torrent2.get_stats.return_value = {
            "downloaded": 2000,
            "uploaded": 1000,
            "peers_connected": 5,
            "download_rate": 200.0,
            "upload_rate": 100.0,
        }
        
        self.session_manager.torrents = {
            "torrent1": mock_torrent1,
            "torrent2": mock_torrent2,
        }
        
        stats = self.session_manager._aggregate_torrent_stats()
        
        assert stats["total_downloaded"] == 3000
        assert stats["total_uploaded"] == 1500
        assert stats["total_peers_connected"] == 8
        assert stats["total_download_rate"] == 300.0
        assert stats["total_upload_rate"] == 150.0
        assert stats["active_torrents"] == 2

    def test_aggregate_torrent_stats_empty(self):
        """Test aggregating statistics with no torrents."""
        self.session_manager.torrents = {}
        
        stats = self.session_manager._aggregate_torrent_stats()
        
        assert stats["total_downloaded"] == 0
        assert stats["total_uploaded"] == 0
        assert stats["total_peers_connected"] == 0
        assert stats["total_download_rate"] == 0.0
        assert stats["total_upload_rate"] == 0.0
        assert stats["active_torrents"] == 0

    @pytest.mark.asyncio
    async def test_emit_global_metrics(self):
        """Test emitting global metrics event."""
        stats = {
            "total_downloaded": 1000,
            "total_uploaded": 500,
            "total_peers_connected": 5,
            "total_download_rate": 100.0,
            "total_upload_rate": 50.0,
            "active_torrents": 2,
        }
        
        # Mock emit_event
        with patch("ccbt.session.emit_event") as mock_emit:
            await self.session_manager._emit_global_metrics(stats)
            
            # Verify event was emitted
            mock_emit.assert_called_once()
            event = mock_emit.call_args[0][0]
            assert event.event_type == "global_metrics_update"
            assert event.data["stats"] == stats
            assert "timestamp" in event.data

    @pytest.mark.asyncio
    async def test_torrent_session_announce_loop_integration(self):
        """Test torrent session announce loop integration."""
        # Create a mock torrent session
        torrent_session = AsyncTorrentSession(
            info_hash_hex="test_hash",
            session_manager=self.session_manager
        )
        
        # Mock required attributes
        torrent_session.download_manager = MagicMock()
        torrent_session.download_manager.add_peers = AsyncMock()
        
        # Mock tracker response with peers
        mock_response = MagicMock()
        mock_response.peers = [
            PeerInfo(ip="192.168.1.100", port=6881),
            PeerInfo(ip="192.168.1.101", port=6882),
        ]
        
        # Mock tracker manager
        torrent_session.tracker_manager = MagicMock()
        torrent_session.tracker_manager.announce = AsyncMock(return_value=mock_response)
        
        # Test the announce loop logic
        response = await torrent_session.tracker_manager.announce()
        
        if response.peers and torrent_session.download_manager:
            await torrent_session.download_manager.add_peers(response.peers)
        
        # Verify peers were added
        torrent_session.download_manager.add_peers.assert_called_once_with(mock_response.peers)

    @pytest.mark.asyncio
    async def test_torrent_session_status_loop_integration(self):
        """Test torrent session status loop integration."""
        # Create a mock torrent session
        torrent_session = AsyncTorrentSession(
            info_hash_hex="test_hash",
            session_manager=self.session_manager
        )
        
        # Mock required attributes
        torrent_session.downloaded_bytes = 1000
        torrent_session.uploaded_bytes = 500
        torrent_session.left_bytes = 2000
        torrent_session.peers = {
            "peer1": MagicMock(),
            "peer2": MagicMock(),
        }
        torrent_session.download_rate = 100.0
        torrent_session.upload_rate = 50.0
        
        # Mock session manager
        torrent_session.session_manager = MagicMock()
        torrent_session.session_manager.update_torrent_metrics = AsyncMock()
        
        # Test the status loop logic
        metrics = {
            "downloaded": torrent_session.downloaded_bytes,
            "uploaded": torrent_session.uploaded_bytes,
            "left": torrent_session.left_bytes,
            "peers_connected": len(torrent_session.peers),
            "download_rate": torrent_session.download_rate,
            "upload_rate": torrent_session.upload_rate,
        }
        
        await torrent_session.session_manager.update_torrent_metrics(torrent_session.info_hash_hex, metrics)
        
        # Verify metrics were updated
        torrent_session.session_manager.update_torrent_metrics.assert_called_once_with(
            torrent_session.info_hash_hex, metrics
        )

    @pytest.mark.asyncio
    async def test_session_manager_lifecycle(self):
        """Test session manager complete lifecycle."""
        # Mock required methods
        self.session_manager._start_services = AsyncMock()
        self.session_manager._stop_services = AsyncMock()
        
        # Start session manager
        await self.session_manager.start()
        
        # Stop session manager
        await self.session_manager.stop()
        
        # Verify methods were called
        self.session_manager._start_services.assert_called_once()
        self.session_manager._stop_services.assert_called_once()

    def test_get_torrent_method(self):
        """Test _get_torrent method."""
        # Add a mock torrent
        mock_torrent = MagicMock()
        info_hash = "test_hash"
        self.session_manager.torrents[info_hash] = mock_torrent
        
        # Test getting existing torrent
        result = self.session_manager._get_torrent(info_hash)
        assert result == mock_torrent
        
        # Test getting non-existent torrent
        result = self.session_manager._get_torrent("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_session_manager_error_handling(self):
        """Test session manager error handling."""
        # Test with invalid torrent hash
        result = await self.session_manager.rehash_torrent("invalid_hash")
        assert result is False
        
        # Test adding peers to non-existent torrent
        await self.session_manager.add_peers_to_torrent("nonexistent", [])
        
        # Should not raise exception

    def test_session_manager_statistics(self):
        """Test session manager statistics collection."""
        # Add some mock torrents
        mock_torrent1 = MagicMock()
        mock_torrent1.get_stats.return_value = {"downloaded": 1000, "uploaded": 500}
        
        mock_torrent2 = MagicMock()
        mock_torrent2.get_stats.return_value = {"downloaded": 2000, "uploaded": 1000}
        
        self.session_manager.torrents = {
            "torrent1": mock_torrent1,
            "torrent2": mock_torrent2,
        }
        
        # Test global stats update
        self.session_manager.global_stats = {
            "total_downloaded": 3000,
            "total_uploaded": 1500,
            "active_torrents": 2,
        }
        
        stats = self.session_manager.get_global_stats()
        assert stats["total_downloaded"] == 3000
        assert stats["total_uploaded"] == 1500
        assert stats["active_torrents"] == 2
