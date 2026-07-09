"""Unit tests for ScrapeManager."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.session.scrape import ScrapeManager


class TestScrapeManager:
    """Test ScrapeManager functionality."""

    @pytest.fixture
    def mock_manager(self):
        """Create a mock session manager."""
        manager = Mock()
        manager.lock = asyncio.Lock()
        manager.torrents = {}
        manager.scrape_cache = {}
        manager.scrape_cache_lock = asyncio.Lock()
        manager.logger = Mock()
        manager.config = Mock()
        manager._manager_shutting_down = False
        manager.config.discovery = Mock()
        manager.config.discovery.tracker_scrape_interval = 300.0
        return manager

    @pytest.fixture
    def scrape_manager(self, mock_manager):
        """Create ScrapeManager instance."""
        return ScrapeManager(mock_manager)

    @pytest.mark.asyncio
    async def test_force_scrape_invalid_info_hash(self, scrape_manager):
        """Test force_scrape with invalid info_hash."""
        result = await scrape_manager.force_scrape("invalid")
        assert result is False

        result = await scrape_manager.force_scrape("a" * 39)  # Too short
        assert result is False

    @pytest.mark.asyncio
    async def test_force_scrape_torrent_not_found(self, scrape_manager, mock_manager):
        """Test force_scrape when torrent is not found."""
        info_hash_hex = "a" * 40
        mock_manager.torrents = {}

        result = await scrape_manager.force_scrape(info_hash_hex)
        assert result is False

    @pytest.mark.asyncio
    async def test_force_scrape_success(self, scrape_manager, mock_manager):
        """Test successful force_scrape."""
        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Create mock session
        session = Mock()
        session.torrent_data = {
            "info_hash": info_hash,
            "name": "test",
            "announce": "http://tracker.example.com/announce",
        }

        mock_manager.torrents = {info_hash: session}

        # Mock BitTorrentProtocol
        with patch("ccbt.protocols.bittorrent.BitTorrentProtocol") as mock_protocol_class:
            mock_protocol = Mock()
            mock_protocol.scrape_torrent = AsyncMock(
                return_value={"seeders": 10, "leechers": 5, "completed": 100}
            )
            mock_protocol_class.return_value = mock_protocol

            result = await scrape_manager.force_scrape(info_hash_hex)

            assert result is True
            assert info_hash in mock_manager.scrape_cache

    @pytest.mark.asyncio
    async def test_force_scrape_zero_stats(self, scrape_manager, mock_manager):
        """Test force_scrape with zero stats."""
        info_hash = b"y" * 20
        info_hash_hex = info_hash.hex()

        session = Mock()
        session.torrent_data = {
            "info_hash": info_hash,
            "name": "test",
            "announce": "http://tracker.example.com/announce",
        }

        mock_manager.torrents = {info_hash: session}

        with patch("ccbt.protocols.bittorrent.BitTorrentProtocol") as mock_protocol_class:
            mock_protocol = Mock()
            mock_protocol.scrape_torrent = AsyncMock(
                return_value={"seeders": 0, "leechers": 0, "completed": 0}
            )
            mock_protocol_class.return_value = mock_protocol

            result = await scrape_manager.force_scrape(info_hash_hex)

            assert result is False

    @pytest.mark.asyncio
    async def test_get_cached_result(self, scrape_manager, mock_manager):
        """Test getting cached scrape result."""
        from ccbt.models import ScrapeResult

        info_hash = b"z" * 20
        info_hash_hex = info_hash.hex()

        scrape_result = ScrapeResult(
            info_hash=info_hash,
            seeders=10,
            leechers=5,
            completed=100,
            last_scrape_time=1000.0,
            scrape_count=1,
        )

        mock_manager.scrape_cache[info_hash] = scrape_result

        result = await scrape_manager.get_cached_result(info_hash_hex)
        assert result == scrape_result

    @pytest.mark.asyncio
    async def test_get_cached_result_not_found(self, scrape_manager, mock_manager):
        """Test getting cached result when not found."""
        info_hash_hex = "a" * 40
        result = await scrape_manager.get_cached_result(info_hash_hex)
        assert result is None

    def test_is_stale(self, scrape_manager, mock_manager):
        """Test is_stale method."""
        import time

        from ccbt.models import ScrapeResult

        info_hash = b"stale" * 5

        # Fresh result
        fresh_result = ScrapeResult(
            info_hash=info_hash,
            seeders=10,
            leechers=5,
            completed=100,
            last_scrape_time=time.time(),
            scrape_count=1,
        )
        assert scrape_manager.is_stale(fresh_result) is False

        # Stale result
        stale_result = ScrapeResult(
            info_hash=info_hash,
            seeders=10,
            leechers=5,
            completed=100,
            last_scrape_time=time.time() - 400.0,  # Older than interval
            scrape_count=1,
        )
        assert scrape_manager.is_stale(stale_result) is True

        # Result with zero timestamp
        zero_result = ScrapeResult(
            info_hash=info_hash,
            seeders=10,
            leechers=5,
            completed=100,
            last_scrape_time=0.0,
            scrape_count=1,
        )
        assert scrape_manager.is_stale(zero_result) is True

