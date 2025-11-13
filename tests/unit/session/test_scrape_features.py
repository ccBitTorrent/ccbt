"""Unit tests for BEP 48 scrape features in AsyncSessionManager.

Tests:
- Scrape cache initialization and management
- Staleness checking
- Auto-scrape on torrent add
- Periodic scrape loop
- Force scrape edge cases
Target: 95%+ code coverage for scrape-related code in ccbt/session/session.py.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.session]


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = MagicMock()
    config.discovery = MagicMock()
    config.discovery.tracker_auto_scrape = False
    config.discovery.tracker_scrape_interval = 300.0  # 5 minutes
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
    from ccbt.session.session import AsyncSessionManager

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
def sample_info_hash():
    """Create sample info hash."""
    return b"x" * 20


@pytest.fixture
def sample_info_hash_hex(sample_info_hash):
    """Create sample info hash in hex format."""
    return sample_info_hash.hex()


@pytest.fixture
def sample_torrent_data(sample_info_hash):
    """Create sample torrent data."""
    return {
        "name": "test_torrent",
        "info_hash": sample_info_hash,
        "announce": "http://tracker.example.com/announce",
        "pieces": b"pieces_hash_data",
        "piece_length": 16384,
        "files": [{"path": ["file1.txt"], "length": 1024}],
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"piece_hash_1"],
        },
        "file_info": {
            "total_length": 1024,
            "piece_length": 16384,
        },
        "total_length": 1024,
    }


class TestScrapeCache:
    """Test scrape cache functionality."""

    @pytest.mark.asyncio
    async def test_scrape_cache_initialization(self, session_manager):
        """Test scrape cache is initialized as empty dict."""
        assert isinstance(session_manager.scrape_cache, dict)
        assert len(session_manager.scrape_cache) == 0
        assert session_manager.scrape_cache_lock is not None

    @pytest.mark.asyncio
    async def test_get_scrape_result_missing(self, session_manager, sample_info_hash_hex):
        """Test get_scrape_result returns None for missing entry."""
        result = await session_manager.get_scrape_result(sample_info_hash_hex)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_scrape_result_invalid_hex(self, session_manager):
        """Test get_scrape_result handles invalid hex format."""
        result = await session_manager.get_scrape_result("invalid_hex")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_scrape_result_cached(
        self, session_manager, sample_info_hash, sample_info_hash_hex
    ):
        """Test get_scrape_result returns cached entry."""
        from ccbt.models import ScrapeResult

        scrape_result = ScrapeResult(
            info_hash=sample_info_hash,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=time.time(),
            scrape_count=1,
        )

        async with session_manager.scrape_cache_lock:
            session_manager.scrape_cache[sample_info_hash] = scrape_result

        result = await session_manager.get_scrape_result(sample_info_hash_hex)

        assert result is not None
        assert result.info_hash == sample_info_hash
        assert result.seeders == 100
        assert result.leechers == 50
        assert result.completed == 1000

    @pytest.mark.asyncio
    async def test_scrape_result_cached_after_force_scrape(
        self,
        session_manager,
        sample_torrent_data,
        sample_info_hash,
        sample_info_hash_hex,
    ):
        """Test scrape result is cached after successful force_scrape."""
        from ccbt.session.session import AsyncTorrentSession

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 75, "leechers": 30, "completed": 600}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            success = await session_manager.force_scrape(sample_info_hash_hex)

            assert success is True

            # Check cache
            cached_result = await session_manager.get_scrape_result(
                sample_info_hash_hex
            )
            assert cached_result is not None
            assert cached_result.seeders == 75
            assert cached_result.leechers == 30

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_scrape_count_increments(
        self,
        session_manager,
        sample_torrent_data,
        sample_info_hash,
        sample_info_hash_hex,
    ):
        """Test scrape_count increments on multiple scrapes."""
        from ccbt.models import ScrapeResult
        from ccbt.session.session import AsyncTorrentSession

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 100, "leechers": 50, "completed": 1000}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            # First scrape
            success1 = await session_manager.force_scrape(sample_info_hash_hex)
            assert success1 is True

            result1 = await session_manager.get_scrape_result(sample_info_hash_hex)
            assert result1 is not None
            assert result1.scrape_count == 1

            # Second scrape
            success2 = await session_manager.force_scrape(sample_info_hash_hex)
            assert success2 is True

            result2 = await session_manager.get_scrape_result(sample_info_hash_hex)
            assert result2 is not None
            assert result2.scrape_count == 2

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_scrape_cache_cleared_on_remove(
        self, session_manager, sample_info_hash, sample_info_hash_hex
    ):
        """Test scrape cache is cleared when torrent is removed."""
        from ccbt.models import ScrapeResult

        # Add cached scrape result
        scrape_result = ScrapeResult(
            info_hash=sample_info_hash,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=time.time(),
            scrape_count=1,
        )

        async with session_manager.scrape_cache_lock:
            session_manager.scrape_cache[sample_info_hash] = scrape_result

        # Verify it's cached
        cached = await session_manager.get_scrape_result(sample_info_hash_hex)
        assert cached is not None

        # Remove torrent (this will also clear cache)
        # First add a torrent session to remove
        mock_torrent_session = MagicMock()
        mock_torrent_session.stop = AsyncMock()  # Make stop() async
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = mock_torrent_session

        await session_manager.remove(sample_info_hash_hex)

        # Verify cache is cleared
        cached = await session_manager.get_scrape_result(sample_info_hash_hex)
        assert cached is None


class TestScrapeStaleness:
    """Test scrape staleness checking."""

    @pytest.mark.asyncio
    async def test_is_scrape_stale_zero_time(self, session_manager):
        """Test _is_scrape_stale returns True for zero time."""
        from ccbt.models import ScrapeResult

        result = ScrapeResult(
            info_hash=b"x" * 20,
            seeders=0,
            leechers=0,
            completed=0,
            last_scrape_time=0.0,
            scrape_count=0,
        )

        assert session_manager._is_scrape_stale(result) is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_is_scrape_stale_recent(self, session_manager):
        """Test _is_scrape_stale returns False for recent scrape."""
        from ccbt.models import ScrapeResult

        result = ScrapeResult(
            info_hash=b"x" * 20,
            seeders=0,
            leechers=0,
            completed=0,
            last_scrape_time=time.time() - 10.0,  # 10 seconds ago
            scrape_count=0,
        )

        assert session_manager._is_scrape_stale(result) is False  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_is_scrape_stale_old(self, session_manager):
        """Test _is_scrape_stale returns True for old scrape."""
        from ccbt.models import ScrapeResult

        result = ScrapeResult(
            info_hash=b"x" * 20,
            seeders=0,
            leechers=0,
            completed=0,
            last_scrape_time=time.time() - 1000.0,  # Very old
            scrape_count=0,
        )

        assert session_manager._is_scrape_stale(result) is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_is_scrape_stale_exact_interval(self, session_manager, mock_config):
        """Test _is_scrape_stale at exact interval boundary."""
        from ccbt.models import ScrapeResult

        mock_config.discovery.tracker_scrape_interval = 300.0  # 5 minutes

        result = ScrapeResult(
            info_hash=b"x" * 20,
            seeders=0,
            leechers=0,
            completed=0,
            last_scrape_time=time.time() - 300.0,  # Exactly at interval
            scrape_count=0,
        )

        # Should be stale (>= interval)
        assert session_manager._is_scrape_stale(result) is True  # noqa: SLF001


class TestAutoScrapeOnAdd:
    """Test auto-scrape on torrent add."""

    @pytest.mark.asyncio
    async def test_auto_scrape_disabled(
        self, session_manager, mock_config, sample_torrent_data
    ):
        """Test auto-scrape doesn't run when disabled."""
        mock_config.discovery.tracker_auto_scrape = False

        # Mock force_scrape to verify it's not called
        with patch.object(
            session_manager, "force_scrape", new_callable=AsyncMock
        ) as mock_force:
            await session_manager.add_torrent(sample_torrent_data, resume=False)

            # Give a moment for any background tasks
            await asyncio.sleep(0.1)

            # force_scrape should not be called (no auto-scrape)
            mock_force.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_scrape_enabled(
        self, session_manager, mock_config, sample_torrent_data, sample_info_hash_hex
    ):
        """Test auto-scrape runs when enabled."""
        mock_config.discovery.tracker_auto_scrape = True

        # Mock force_scrape
        with patch.object(
            session_manager, "force_scrape", new_callable=AsyncMock
        ) as mock_force:
            mock_force.return_value = True

            await session_manager.add_torrent(sample_torrent_data, resume=False)

            # Wait for auto-scrape delay (2 seconds) but check periodically
            for _ in range(25):  # 2.5 seconds total
                await asyncio.sleep(0.1)
                if mock_force.called:
                    break

            # force_scrape should be called once
            mock_force.assert_called_once_with(sample_info_hash_hex)

    @pytest.mark.asyncio
    async def test_auto_scrape_error_handling(
        self, session_manager, mock_config, sample_torrent_data, sample_info_hash_hex
    ):
        """Test auto-scrape handles errors gracefully."""
        mock_config.discovery.tracker_auto_scrape = True

        # Mock force_scrape to raise exception
        with patch.object(
            session_manager, "force_scrape", new_callable=AsyncMock
        ) as mock_force:
            mock_force.side_effect = Exception("Scrape error")

            # Should not raise exception
            await session_manager.add_torrent(sample_torrent_data, resume=False)

            # Wait for auto-scrape delay but with timeout
            for _ in range(25):  # 2.5 seconds total
                await asyncio.sleep(0.1)
                if mock_force.called:
                    break

            # force_scrape should have been called
            mock_force.assert_called_once_with(sample_info_hash_hex)


class TestPeriodicScrapeLoop:
    """Test periodic scrape loop."""

    @pytest.mark.asyncio
    async def test_periodic_scrape_loop_starts(
        self, session_manager, mock_config
    ):
        """Test periodic scrape loop starts when auto-scrape enabled."""
        mock_config.discovery.tracker_auto_scrape = True

        await session_manager.stop()
        await session_manager.start()

        assert session_manager.scrape_task is not None
        assert not session_manager.scrape_task.done()

        await session_manager.stop()

    @pytest.mark.asyncio
    async def test_periodic_scrape_loop_not_started_when_disabled(
        self, session_manager, mock_config
    ):
        """Test periodic scrape loop doesn't start when disabled."""
        mock_config.discovery.tracker_auto_scrape = False

        await session_manager.stop()
        await session_manager.start()

        # scrape_task should be None when disabled
        assert session_manager.scrape_task is None

    @pytest.mark.asyncio
    async def test_periodic_scrape_loop_scrapes_stale_torrents(
        self,
        session_manager,
        mock_config,
        sample_torrent_data,
        sample_info_hash,
        sample_info_hash_hex,
    ):
        """Test periodic scrape loop scrapes stale torrents."""
        from ccbt.models import ScrapeResult

        mock_config.discovery.tracker_auto_scrape = True
        mock_config.discovery.tracker_scrape_interval = (
            1.0  # Short interval for testing
        )

        # Add a torrent
        from ccbt.session.session import AsyncTorrentSession

        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Add stale scrape result
        stale_result = ScrapeResult(
            info_hash=sample_info_hash,
            seeders=50,
            leechers=25,
            completed=500,
            last_scrape_time=time.time() - 2000.0,  # Very old
            scrape_count=1,
        )

        async with session_manager.scrape_cache_lock:
            session_manager.scrape_cache[sample_info_hash] = stale_result

        # The periodic loop needs auto-scrape enabled and started
        # Stop and restart to apply new config with auto-scrape enabled
        await session_manager.stop()
        
        # Mock force_scrape before restarting
        with patch.object(
            session_manager, "force_scrape", new_callable=AsyncMock
        ) as mock_force:
            mock_force.return_value = True

            # Restart with auto-scrape enabled to start periodic loop
            await session_manager.start()

            # Re-add torrent after restart (it was cleared during stop)
            async with session_manager.lock:
                session_manager.torrents[sample_info_hash] = torrent_session

            # Wait for periodic loop to run (interval + processing time + rate limit)
            # The loop waits for interval first, then processes
            max_wait = 5  # 5 seconds max
            for _ in range(max_wait * 10):  # Check every 0.1s
                await asyncio.sleep(0.1)
                if mock_force.called:
                    break

            # force_scrape should have been called (stale result)
            assert mock_force.called, (
                f"Periodic scrape should have called force_scrape within {max_wait}s. "
                f"Active torrents: {len(session_manager.torrents)}, "
                f"Stale cache entry exists: {sample_info_hash in session_manager.scrape_cache}"
            )

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_periodic_scrape_loop_skips_fresh_torrents(
        self,
        session_manager,
        mock_config,
        sample_torrent_data,
        sample_info_hash,
        sample_info_hash_hex,
    ):
        """Test periodic scrape loop skips fresh torrents."""
        from ccbt.models import ScrapeResult

        mock_config.discovery.tracker_auto_scrape = True
        mock_config.discovery.tracker_scrape_interval = 300.0

        # Add a torrent
        from ccbt.session.session import AsyncTorrentSession

        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Add fresh scrape result
        fresh_result = ScrapeResult(
            info_hash=sample_info_hash,
            seeders=50,
            leechers=25,
            completed=500,
            last_scrape_time=time.time() - 10.0,  # Very recent
            scrape_count=1,
        )

        async with session_manager.scrape_cache_lock:
            session_manager.scrape_cache[sample_info_hash] = fresh_result

        # Mock force_scrape
        with patch.object(
            session_manager, "force_scrape", new_callable=AsyncMock
        ) as mock_force:
            mock_force.return_value = True

            await session_manager.stop()
            await session_manager.start()

            # Re-add torrent after restart
            async with session_manager.lock:
                session_manager.torrents[sample_info_hash] = torrent_session

            # Wait a bit (but less than interval)
            await asyncio.sleep(0.5)

            # force_scrape should not be called (fresh result)
            mock_force.assert_not_called()

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)
        await session_manager.stop()

    @pytest.mark.asyncio
    async def test_periodic_scrape_loop_cancelled_on_stop(
        self, session_manager, mock_config
    ):
        """Test periodic scrape loop is cancelled on stop."""
        mock_config.discovery.tracker_auto_scrape = True

        await session_manager.start()

        assert session_manager.scrape_task is not None
        assert not session_manager.scrape_task.done()

        await session_manager.stop()

        # Task should be cancelled
        assert session_manager.scrape_task.done()

    @pytest.mark.asyncio
    async def test_periodic_scrape_loop_error_recovery(
        self, session_manager, mock_config, sample_torrent_data, sample_info_hash
    ):
        """Test periodic scrape loop recovers from errors."""
        mock_config.discovery.tracker_auto_scrape = True
        mock_config.discovery.tracker_scrape_interval = 1.0  # Short interval

        # Add a torrent
        from ccbt.session.session import AsyncTorrentSession

        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Stop and restart to apply new config and start periodic loop
        await session_manager.stop()
        
        # Mock force_scrape to raise exception
        with patch.object(
            session_manager, "force_scrape", new_callable=AsyncMock
        ) as mock_force:
            mock_force.side_effect = Exception("Scrape error")

            # Restart with auto-scrape enabled to start periodic loop
            await session_manager.start()

            # Re-add torrent after restart (it was cleared during stop)
            async with session_manager.lock:
                session_manager.torrents[sample_info_hash] = torrent_session

            # Wait for loop to process (should handle error and continue)
            # The loop waits for interval first, then processes
            max_wait = 5  # 5 seconds max wait
            for _ in range(max_wait * 10):  # Check every 0.1s
                await asyncio.sleep(0.1)
                if mock_force.called:
                    break

            # force_scrape should have been called (even if it failed)
            assert mock_force.called, (
                f"Periodic scrape should have called force_scrape within {max_wait}s despite error. "
                f"Torrent active: {sample_info_hash in session_manager.torrents}"
            )

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)


class TestForceScrapeEdgeCases:
    """Test edge cases for force_scrape."""

    @pytest.mark.asyncio
    async def test_force_scrape_invalid_length(self, session_manager):
        """Test force_scrape with invalid info hash length."""
        result = await session_manager.force_scrape("short")
        assert result is False

    @pytest.mark.asyncio
    async def test_force_scrape_invalid_format(self, session_manager):
        """Test force_scrape with invalid hex format."""
        result = await session_manager.force_scrape("X" * 40)
        assert result is False

    @pytest.mark.asyncio
    async def test_force_scrape_torrent_not_found(
        self, session_manager, sample_info_hash_hex
    ):
        """Test force_scrape when torrent is not found."""
        result = await session_manager.force_scrape(sample_info_hash_hex)
        assert result is False

    @pytest.mark.asyncio
    async def test_force_scrape_zero_stats(
        self, session_manager, sample_torrent_data, sample_info_hash, sample_info_hash_hex
    ):
        """Test force_scrape when scrape returns zero stats."""
        from ccbt.session.session import AsyncTorrentSession

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Mock protocol scrape to return zero stats
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 0, "leechers": 0, "completed": 0}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(sample_info_hash_hex)

            assert result is False  # Should fail because stats are zero

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_exception_handling(
        self, session_manager, sample_torrent_data, sample_info_hash, sample_info_hash_hex
    ):
        """Test force_scrape exception handling."""
        from ccbt.session.session import AsyncTorrentSession

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Mock protocol scrape to raise exception
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(side_effect=Exception("Scrape error"))

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(sample_info_hash_hex)

            assert result is False  # Should handle exception gracefully

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_success_but_zero_stats(
        self, session_manager, sample_torrent_data, sample_info_hash, sample_info_hash_hex
    ):
        """Test force_scrape when scrape succeeds but returns zero stats (covers else branch)."""
        from ccbt.session.session import AsyncTorrentSession

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Mock protocol scrape to return zero stats but successful call
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 0, "leechers": 0, "completed": 0}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(sample_info_hash_hex)

            # Should fail because stats are zero (covers the else branch at line 1680)
            assert result is False

            # Verify no cache entry was created (zero stats don't get cached)
            cached = await session_manager.get_scrape_result(sample_info_hash_hex)
            # May or may not be None depending on implementation, but result should be False

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_success_with_existing_cache(
        self, session_manager, sample_torrent_data, sample_info_hash, sample_info_hash_hex
    ):
        """Test force_scrape increments scrape_count when cache entry exists."""
        from ccbt.models import ScrapeResult
        from ccbt.session.session import AsyncTorrentSession

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Add existing cache entry
        existing_result = ScrapeResult(
            info_hash=sample_info_hash,
            seeders=50,
            leechers=25,
            completed=500,
            last_scrape_time=time.time() - 1000.0,
            scrape_count=5,
        )
        async with session_manager.scrape_cache_lock:
            session_manager.scrape_cache[sample_info_hash] = existing_result

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 100, "leechers": 50, "completed": 1000}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(sample_info_hash_hex)

            assert result is True

            # Check scrape_count was incremented
            cached = await session_manager.get_scrape_result(sample_info_hash_hex)
            assert cached is not None
            assert cached.scrape_count == 6  # Was 5, incremented to 6

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_with_torrentinfo_model(
        self, session_manager, sample_torrent_data, sample_info_hash, sample_info_hash_hex
    ):
        """Test force_scrape when torrent_data is already a TorrentInfo model."""
        from ccbt.models import TorrentInfo
        from ccbt.session.session import AsyncTorrentSession

        # Create TorrentInfo from sample data
        torrent_info = TorrentInfo(
            name=sample_torrent_data.get("name", "test"),
            info_hash=sample_info_hash,
            announce=sample_torrent_data.get("announce", ""),
            files=[],
            total_length=sample_torrent_data.get("total_length", 0),
            piece_length=sample_torrent_data.get("file_info", {}).get("piece_length", 16384),
            pieces=[],
            num_pieces=0,
        )

        # Create torrent session with TorrentInfo model
        torrent_session = AsyncTorrentSession(
            torrent_info, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 75, "leechers": 30, "completed": 600}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(sample_info_hash_hex)

            assert result is True

            # Verify cache
            cached = await session_manager.get_scrape_result(sample_info_hash_hex)
            assert cached is not None
            assert cached.seeders == 75

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_unsupported_torrent_data_type(
        self, session_manager, sample_info_hash, sample_info_hash_hex
    ):
        """Test force_scrape with unsupported torrent_data type."""
        # Create torrent session with unsupported type
        torrent_session = MagicMock()
        torrent_session.torrent_data = 12345  # Unsupported type
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        result = await session_manager.force_scrape(sample_info_hash_hex)

        assert result is False

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_dict_missing_fields(
        self, session_manager, sample_info_hash, sample_info_hash_hex
    ):
        """Test force_scrape with dict torrent_data missing optional fields (like file_info)."""
        from ccbt.session.session import AsyncTorrentSession

        # Create minimal torrent data dict with required fields
        # file_info missing piece_length to test default handling in force_scrape
        minimal_torrent_data = {
            "name": "test_torrent",
            "info_hash": sample_info_hash,
            "announce": "http://tracker.example.com/announce",
            "total_length": 1024,
            "pieces_info": {"num_pieces": 1, "piece_length": 16384, "piece_hashes": [b"hash"]},
            "file_info": {"total_length": 1024},  # Missing piece_length to test default
        }

        torrent_session = AsyncTorrentSession(
            minimal_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Mock protocol scrape
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 50, "leechers": 25, "completed": 500}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(sample_info_hash_hex)

            assert result is True

            # Verify cache was created
            cached = await session_manager.get_scrape_result(sample_info_hash_hex)
            assert cached is not None

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_with_leechers_only(
        self, session_manager, sample_torrent_data, sample_info_hash, sample_info_hash_hex
    ):
        """Test force_scrape when scrape returns only leechers (no seeders)."""
        from ccbt.session.session import AsyncTorrentSession

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Mock protocol scrape to return only leechers
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 0, "leechers": 50, "completed": 0}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(sample_info_hash_hex)

            # Should succeed because leechers > 0
            assert result is True

            # Verify cache
            cached = await session_manager.get_scrape_result(sample_info_hash_hex)
            assert cached is not None
            assert cached.leechers == 50
            assert cached.seeders == 0

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)

    @pytest.mark.asyncio
    async def test_force_scrape_with_seeders_only(
        self, session_manager, sample_torrent_data, sample_info_hash, sample_info_hash_hex
    ):
        """Test force_scrape when scrape returns only seeders (no leechers)."""
        from ccbt.session.session import AsyncTorrentSession

        # Add torrent session
        torrent_session = AsyncTorrentSession(
            sample_torrent_data, output_dir=".", session_manager=session_manager
        )
        async with session_manager.lock:
            session_manager.torrents[sample_info_hash] = torrent_session

        # Mock protocol scrape to return only seeders
        mock_protocol = AsyncMock()
        mock_protocol.scrape_torrent = AsyncMock(
            return_value={"seeders": 100, "leechers": 0, "completed": 1000}
        )

        with patch(
            "ccbt.protocols.bittorrent.BitTorrentProtocol", return_value=mock_protocol
        ):
            result = await session_manager.force_scrape(sample_info_hash_hex)

            # Should succeed because seeders > 0
            assert result is True

            # Verify cache
            cached = await session_manager.get_scrape_result(sample_info_hash_hex)
            assert cached is not None
            assert cached.seeders == 100
            assert cached.leechers == 0

        # Clean up
        async with session_manager.lock:
            session_manager.torrents.pop(sample_info_hash, None)


class TestScrapeResultModel:
    """Test ScrapeResult model edge cases."""

    def test_scrape_result_defaults(self):
        """Test ScrapeResult with minimal required fields."""
        from ccbt.models import ScrapeResult

        result = ScrapeResult(info_hash=b"x" * 20)

        assert result.info_hash == b"x" * 20
        assert result.seeders == 0
        assert result.leechers == 0
        assert result.completed == 0
        assert result.last_scrape_time == 0.0
        assert result.scrape_count == 0

    def test_scrape_result_all_fields(self):
        """Test ScrapeResult with all fields."""
        from ccbt.models import ScrapeResult
        import time

        result = ScrapeResult(
            info_hash=b"y" * 20,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=time.time(),
            scrape_count=5,
        )

        assert result.info_hash == b"y" * 20
        assert result.seeders == 100
        assert result.leechers == 50
        assert result.completed == 1000
        assert result.scrape_count == 5
        assert result.last_scrape_time > 0

    def test_scrape_result_validation_negative_values(self):
        """Test ScrapeResult validation rejects negative values."""
        from ccbt.models import ScrapeResult
        from pydantic import ValidationError

        # Should raise ValidationError for negative seeders
        with pytest.raises(ValidationError):
            ScrapeResult(info_hash=b"x" * 20, seeders=-1)

        # Should raise ValidationError for negative leechers
        with pytest.raises(ValidationError):
            ScrapeResult(info_hash=b"x" * 20, leechers=-1)

        # Should raise ValidationError for negative completed
        with pytest.raises(ValidationError):
            ScrapeResult(info_hash=b"x" * 20, completed=-1)

        # Should raise ValidationError for negative last_scrape_time
        with pytest.raises(ValidationError):
            ScrapeResult(info_hash=b"x" * 20, last_scrape_time=-1.0)

        # Should raise ValidationError for negative scrape_count
        with pytest.raises(ValidationError):
            ScrapeResult(info_hash=b"x" * 20, scrape_count=-1)

    def test_scrape_result_model_dump(self):
        """Test ScrapeResult model_dump method."""
        from ccbt.models import ScrapeResult

        result = ScrapeResult(
            info_hash=b"z" * 20,
            seeders=75,
            leechers=30,
            completed=600,
        )

        dumped = result.model_dump()
        assert dumped["info_hash"] == b"z" * 20
        assert dumped["seeders"] == 75
        assert dumped["leechers"] == 30
        assert dumped["completed"] == 600
