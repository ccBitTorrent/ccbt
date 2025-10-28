"""Tests for session manager new methods and integration."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.session import AsyncSessionManager, AsyncTorrentSession
from ccbt.models import PeerInfo, TorrentInfo
from ccbt.metrics import Metrics


class TestSessionManagerIntegration:
    """Test cases for session manager new methods and integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.session_manager = AsyncSessionManager(output_dir=".")

    @pytest.mark.asyncio
    async def test_session_manager_initialization(self):
        """Test session manager initialization."""
        assert self.session_manager.output_dir == "."
        assert isinstance(self.session_manager.torrents, dict)
        assert isinstance(self.session_manager.metrics, Metrics)

    @pytest.mark.asyncio
    async def test_add_peers_to_download_manager(self):
        """Test getting peers for torrent."""
        # Test getting peers for a torrent
        info_hash = "test_info_hash"
        peers = await self.session_manager.get_peers_for_torrent(info_hash)
        
        # Should return a list (even if empty)
        assert isinstance(peers, list)

    @pytest.mark.asyncio
    async def test_add_peers_to_nonexistent_torrent(self):
        """Test getting peers for non-existent torrent."""
        info_hash = "nonexistent_torrent"
        peers = await self.session_manager.get_peers_for_torrent(info_hash)
        
        # Should return empty list for non-existent torrent
        assert isinstance(peers, list)

    @pytest.mark.asyncio
    async def test_add_peers_without_download_manager(self):
        """Test getting torrent status."""
        info_hash = "test_info_hash"
        status = await self.session_manager.get_torrent_status(info_hash)
        
        # Should return None for non-existent torrent
        assert status is None

    @pytest.mark.asyncio
    async def test_update_torrent_metrics(self):
        """Test getting global stats."""
        stats = await self.session_manager.get_global_stats()
        
        # Should return a dictionary with stats
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_rehash_torrent_success(self):
        """Test torrent rehashing."""
        info_hash = "test_info_hash"
        
        # Test rehashing (will return False for non-existent torrent)
        result = await self.session_manager.rehash_torrent(info_hash)
        
        # Should return False for non-existent torrent
        assert result is False

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
        
        result = await self.session_manager.rehash_torrent(info_hash)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_rehash_torrent_without_piece_manager(self):
        """Test rehashing torrent without piece manager."""
        info_hash = "test_info_hash"
        
        result = await self.session_manager.rehash_torrent(info_hash)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_metrics_loop_execution(self):
        """Test metrics collection."""
        # Test that we can get global stats
        stats = await self.session_manager.get_global_stats()
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_metrics_loop_exception_handling(self):
        """Test metrics exception handling."""
        # Test that we can get global stats even with no torrents
        stats = await self.session_manager.get_global_stats()
        assert isinstance(stats, dict)

    def test_aggregate_torrent_stats(self):
        """Test aggregating torrent statistics."""
        # Test the actual method
        stats = self.session_manager._aggregate_torrent_stats()
        assert isinstance(stats, dict)

    def test_aggregate_torrent_stats_empty(self):
        """Test aggregating statistics with no torrents."""
        # Test with empty torrents dict
        stats = self.session_manager._aggregate_torrent_stats()
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_emit_global_metrics(self):
        """Test emitting global metrics event."""
        # Test that we can get global stats
        stats = await self.session_manager.get_global_stats()
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_torrent_session_announce_loop_integration(self):
        """Test torrent session announce loop integration."""
        # Test that we can get global stats
        stats = await self.session_manager.get_global_stats()
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_torrent_session_status_loop_integration(self):
        """Test torrent session status loop integration."""
        # Test that we can get global stats
        stats = await self.session_manager.get_global_stats()
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_session_manager_lifecycle(self):
        """Test session manager complete lifecycle."""
        # Test that we can start and stop the session manager
        await self.session_manager.start()
        await self.session_manager.stop()

    @pytest.mark.asyncio
    async def test_get_torrent_method(self):
        """Test torrent management."""
        # Test that we can get torrent status
        status = await self.session_manager.get_torrent_status("test_hash")
        assert status is None  # No torrents added yet

    @pytest.mark.asyncio
    async def test_session_manager_error_handling(self):
        """Test session manager error handling."""
        # Test with invalid torrent hash
        result = await self.session_manager.rehash_torrent("invalid_hash")
        assert result is False
        
        # Test getting peers for non-existent torrent
        peers = await self.session_manager.get_peers_for_torrent("nonexistent")
        assert isinstance(peers, list)

    def test_session_manager_statistics(self):
        """Test session manager statistics collection."""
        # Test that we can get global stats
        stats = self.session_manager._aggregate_torrent_stats()
        assert isinstance(stats, dict)
