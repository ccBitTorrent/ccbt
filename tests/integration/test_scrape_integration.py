"""Integration tests for BEP 48 scrape features.

Tests end-to-end workflows:
- Cache persistence across operations
- Auto-scrape on torrent add
- Periodic scraping
Target: 95%+ code coverage for scrape integration features.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from ccbt.models import ScrapeResult
from ccbt.session.session import AsyncSessionManager, AsyncTorrentSession
from tests.conftest import create_test_torrent_dict

pytestmark = [pytest.mark.integration, pytest.mark.session]


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = MagicMock()
    config.discovery = MagicMock()
    config.discovery.tracker_auto_scrape = False
    config.discovery.tracker_scrape_interval = 300.0
    config.discovery.enable_dht = False  # Disable DHT to avoid network operations
    config.nat = MagicMock()
    config.nat.auto_map_ports = False  # Disable NAT to avoid network operations
    config.security = MagicMock()
    config.security.ip_filter = MagicMock()
    config.security.ip_filter.filter_update_interval = 3600.0  # Long interval to avoid updates
    config.queue = MagicMock()
    config.queue.auto_manage_queue = False
    config.disk = MagicMock()
    config.disk.checkpoint_interval = 30.0  # Real numeric value
    config.disk.resume_save_interval = 30.0  # Real numeric value
    config.disk.fast_resume_enabled = False  # Use checkpoint_interval instead
    config.disk.checkpoint_batch_interval = 0  # Real numeric value
    config.disk.checkpoint_batch_pieces = 0  # Real numeric value
    from ccbt.models import CheckpointFormat
    config.disk.checkpoint_format = CheckpointFormat.BINARY  # Real enum value
    config.disk.checkpoint_enabled = True
    return config


@pytest_asyncio.fixture
async def session_manager(mock_config):
    """Create AsyncSessionManager instance for testing."""
    with patch("ccbt.session.session.get_config") as mock_get_config:
        mock_get_config.return_value = mock_config

        session = AsyncSessionManager(".")
        await session.start()
        try:
            yield session
        finally:
            # Ensure all background tasks are stopped
            await session.stop()
            # Give a moment for cleanup
            await asyncio.sleep(0.1)


@pytest.fixture
def sample_torrent_data():
    """Create sample torrent data."""
    return create_test_torrent_dict(
        name="test_torrent",
        info_hash=b"x" * 20,
        announce="http://tracker.example.com/announce",
        file_length=1024,
        piece_length=16384,
        num_pieces=1,
    )


class TestScrapeCacheIntegration:
    """Test scrape cache integration."""

    @pytest.mark.asyncio
    async def test_cache_persists_across_scrapes(
        self, session_manager, sample_torrent_data
    ):
        """Test scrape cache persists across multiple scrapes."""
        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[info_hash] = torrent_session

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 100, "leechers": 50, "completed": 1000}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            # First scrape
            success1 = await session_manager.force_scrape(info_hash_hex)
            assert success1 is True

            result1 = await session_manager.get_scrape_result(info_hash_hex)
            assert result1 is not None
            assert result1.scrape_count == 1

            # Second scrape
            mock_protocol.scrape_torrent.return_value = {
                "seeders": 120,
                "leechers": 60,
                "completed": 1100,
            }

            success2 = await session_manager.force_scrape(info_hash_hex)
            assert success2 is True

            result2 = await session_manager.get_scrape_result(info_hash_hex)
            assert result2 is not None
            assert result2.scrape_count == 2
            assert result2.seeders == 120  # Updated value

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)

    @pytest.mark.asyncio
    async def test_cache_cleared_on_torrent_remove(
        self, session_manager, sample_torrent_data
    ):
        """Test scrape cache is cleared when torrent is removed."""
        from ccbt.session.session import AsyncTorrentSession

        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[info_hash] = torrent_session

        # Mock protocol scrape to populate cache
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 100, "leechers": 50, "completed": 1000}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            await session_manager.force_scrape(info_hash_hex)

            # Verify cache entry exists
            cached = await session_manager.get_scrape_result(info_hash_hex)
            assert cached is not None

            # Remove torrent
            await session_manager.remove(info_hash_hex)

            # Verify cache entry is cleared
            cached = await session_manager.get_scrape_result(info_hash_hex)
            assert cached is None

    @pytest.mark.asyncio
    async def test_cache_thread_safety(self, session_manager, sample_torrent_data):
        """Test scrape cache thread safety with concurrent access."""
        from ccbt.session.session import AsyncTorrentSession

        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[info_hash] = torrent_session

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 100, "leechers": 50, "completed": 1000}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            # Concurrent cache reads
            async def read_cache():
                return await session_manager.get_scrape_result(info_hash_hex)

            # Perform scrape
            await session_manager.force_scrape(info_hash_hex)

            # Concurrent reads
            results = await asyncio.gather(*[read_cache() for _ in range(10)])

            # All should return the same result
            assert all(r is not None for r in results)
            assert all(r.seeders == 100 for r in results)

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(info_hash, None)


class TestAutoScrapeIntegration:
    """Test auto-scrape integration."""

    @pytest.mark.asyncio
    async def test_auto_scrape_on_add_integration(
        self, session_manager, mock_config, sample_torrent_data
    ):
        """Test auto-scrape triggers when adding torrent."""
        mock_config.discovery.tracker_auto_scrape = True

        info_hash_hex = (b"x" * 20).hex()

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 100, "leechers": 50, "completed": 1000}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            # Add torrent (should trigger auto-scrape)
            await session_manager.add_torrent(sample_torrent_data, resume=False)

            # Wait for auto-scrape delay (2 seconds)
            await asyncio.sleep(2.5)

            # Verify scrape result is cached
            result = await session_manager.get_scrape_result(info_hash_hex)
            assert result is not None
            assert result.seeders == 100
            assert result.leechers == 50
            assert result.completed == 1000

            # Clean up
            await session_manager.remove(info_hash_hex)


class TestPeriodicScrapeIntegration:
    """Test periodic scrape integration."""

    @pytest.mark.asyncio
    async def test_periodic_scrape_runs_on_interval(
        self, session_manager, mock_config, sample_torrent_data
    ):
        """Test periodic scrape runs at configured interval."""
        mock_config.discovery.tracker_auto_scrape = True
        mock_config.discovery.tracker_scrape_interval = 1.0  # 1 second for testing

        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Add torrent
        from ccbt.session.session import AsyncTorrentSession

        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[info_hash] = torrent_session

        # Track scrape calls
        scrape_call_count = 0

        async def mock_scrape(_info_hash_hex_param):
            nonlocal scrape_call_count
            scrape_call_count += 1

            # Mock protocol scrape
            mock_protocol = AsyncMock()
            mock_protocol.scrape_torrent = AsyncMock(
                return_value={
                    "seeders": 100 + scrape_call_count,
                    "leechers": 50,
                    "completed": 1000,
                }
            )

            # Update cache manually (simulating what force_scrape does)
            # Note: This test simulates what force_scrape does but doesn't call the real protocol
            stats = {
                "seeders": 100 + scrape_call_count,
                "leechers": 50,
                "completed": 1000,
            }

            scrape_result = ScrapeResult(
                info_hash=info_hash,
                seeders=stats.get("seeders", 0),
                leechers=stats.get("leechers", 0),
                completed=stats.get("completed", 0),
                last_scrape_time=time.time(),
                scrape_count=scrape_call_count,
            )

            async with session_manager.scrape_cache_lock:
                session_manager.scrape_cache[info_hash] = scrape_result

            return True

        # Replace force_scrape with our tracking version
        original_force_scrape = session_manager.force_scrape
        session_manager.force_scrape = mock_scrape

        try:
            # Restart session to start periodic loop with new config
            await session_manager.stop()
            await session_manager.start()

            # Re-add torrent after restart (it was cleared during stop)
            await session_manager.add_torrent(sample_torrent_data, resume=False)

            # Wait for periodic loop to run at least once
            # The loop waits for interval first (1.0s), then processes
            max_wait = 5  # 5 seconds max
            for _ in range(max_wait * 10):  # Check every 0.1s
                await asyncio.sleep(0.1)
                if scrape_call_count > 0:
                    break

            # Should have been scraped at least once by periodic loop
            assert scrape_call_count > 0, (
                f"Periodic scrape should have called force_scrape within {max_wait}s. "
                f"Active torrents: {len(session_manager.torrents)}"
            )

            # Verify cache was updated
            result = await session_manager.get_scrape_result(info_hash_hex)
            assert result is not None

        finally:
            # Restore original method
            session_manager.force_scrape = original_force_scrape

            # Clean up
            async with session_manager.lock:
                session_manager.torrents.pop(info_hash, None)
            await session_manager.stop()

    @pytest.mark.asyncio
    async def test_periodic_scrape_respects_staleness(
        self, session_manager, mock_config, sample_torrent_data
    ):
        """Test periodic scrape respects staleness checks."""
        mock_config.discovery.tracker_auto_scrape = True
        mock_config.discovery.tracker_scrape_interval = 300.0  # 5 minutes

        info_hash = b"x" * 20

        # Add torrent
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[info_hash] = torrent_session

        # Add fresh scrape result (not stale)
        fresh_result = ScrapeResult(
            info_hash=info_hash,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=time.time() - 60.0,  # 1 minute ago (fresh)
            scrape_count=1,
        )

        async with session_manager.scrape_cache_lock:
            session_manager.scrape_cache[info_hash] = fresh_result

        # Track scrape calls
        scrape_call_count = 0

        original_force_scrape = session_manager.force_scrape

        async def mock_scrape(_info_hash_hex_param):
            nonlocal scrape_call_count
            scrape_call_count += 1
            return True

        session_manager.force_scrape = mock_scrape

        try:
            # Restart session to start periodic loop
            await session_manager.stop()
            await session_manager.start()

            # Wait a bit (but less than interval)
            await asyncio.sleep(0.5)

            # Should not scrape (fresh result)
            assert scrape_call_count == 0

        finally:
            session_manager.force_scrape = original_force_scrape

            # Clean up
            async with session_manager.lock:
                session_manager.torrents.pop(info_hash, None)
            await session_manager.stop()

    @pytest.mark.asyncio
    async def test_periodic_scrape_cancelled_on_stop(
        self, session_manager, mock_config
    ):
        """Test periodic scrape is cancelled when session stops."""
        mock_config.discovery.tracker_auto_scrape = True

        await session_manager.start()

        assert session_manager.scrape_task is not None
        assert not session_manager.scrape_task.done()

        # Stop session
        await session_manager.stop()

        # Task should be cancelled
        assert session_manager.scrape_task.done()


class TestEndToEndScrapeWorkflow:
    """Test complete end-to-end scrape workflows."""

    @pytest.mark.asyncio
    async def test_complete_scrape_workflow(
        self, session_manager, mock_config, sample_torrent_data
    ):
        """Test complete workflow: add torrent -> auto-scrape -> periodic scrape -> remove."""  # noqa: E501
        mock_config.discovery.tracker_auto_scrape = True
        mock_config.discovery.tracker_scrape_interval = 3600.0  # 1 hour (long enough)

        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 100, "leechers": 50, "completed": 1000}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            # Step 1: Add torrent (should trigger auto-scrape)
            await session_manager.add_torrent(sample_torrent_data, resume=False)

            # Wait for auto-scrape
            await asyncio.sleep(2.5)

            # Step 2: Verify cache entry exists
            result1 = await session_manager.get_scrape_result(info_hash_hex)
            assert result1 is not None
            assert result1.seeders == 100

            # Step 3: Manually force scrape (should update cache)
            mock_protocol.scrape_torrent.return_value = {
                "seeders": 120,
                "leechers": 60,
                "completed": 1100,
            }

            await session_manager.force_scrape(info_hash_hex)

            result2 = await session_manager.get_scrape_result(info_hash_hex)
            assert result2 is not None
            assert result2.seeders == 120
            assert result2.scrape_count == 2  # Incremented

            # Step 4: Remove torrent (should clear cache)
            await session_manager.remove(info_hash_hex)

            result3 = await session_manager.get_scrape_result(info_hash_hex)
            assert result3 is None
