"""Unit tests for CLI scrape commands (BEP 48).

Tests:
- scrape torrent command
- scrape list command
Target: 95%+ code coverage for ccbt/cli/scrape_commands.py.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from ccbt.cli.scrape_commands import scrape
from ccbt.models import ScrapeResult

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run a coroutine to completion without touching global loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_session_manager():
    """Create mock AsyncSessionManager."""
    session = MagicMock()
    session.start = AsyncMock()
    session.stop = AsyncMock()
    session.force_scrape = AsyncMock(return_value=True)
    session.get_scrape_result = AsyncMock(return_value=None)
    session.scrape_cache = {}
    session.scrape_cache_lock = MagicMock()
    session.scrape_cache_lock.__aenter__ = AsyncMock(return_value=None)
    session.scrape_cache_lock.__aexit__ = AsyncMock(return_value=None)
    return session


class TestScrapeTorrentCommand:
    """Test scrape torrent command."""

    @patch("ccbt.session.session.AsyncSessionManager")
    def test_scrape_torrent_invalid_hash_length(self, mock_session_class, runner):
        """Test scrape torrent with invalid hash length."""
        # Create minimal mock (won't be used since validation fails first)
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session_class.return_value = mock_session
        
        result = runner.invoke(scrape, ["torrent", "short"])

        assert result.exit_code != 0
        assert "40 hex characters" in result.output

    @patch("ccbt.session.session.AsyncSessionManager")
    def test_scrape_torrent_invalid_hash_format(self, mock_session_class, runner):
        """Test scrape torrent with invalid hash format."""
        # Create minimal mock (won't be used since validation fails first)
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.get_scrape_result = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session
        
        result = runner.invoke(scrape, ["torrent", "X" * 40])

        # Should exit with error (invalid hex or other validation error)
        assert result.exit_code != 0

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_torrent_success(self, mock_asyncio_run, mock_session_class, runner):
        """Test successful scrape torrent command."""
        info_hash_hex = "a" * 40

        # Create mock session manager
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.force_scrape = AsyncMock(return_value=True)
        # First call returns None (no cache), second call returns result (after scrape)
        mock_session.get_scrape_result = AsyncMock(
            side_effect=[
                None,  # First call: no cached result
                ScrapeResult(
                    info_hash=bytes.fromhex(info_hash_hex),
                    seeders=100,
                    leechers=50,
                    completed=1000,
                    last_scrape_time=1234567890.0,
                    scrape_count=1,
                ),
            ]
        )
        mock_session_class.return_value = mock_session

        result = runner.invoke(scrape, ["torrent", info_hash_hex])

        # Command should execute successfully
        assert result.exit_code == 0

        # Verify session methods were called
        mock_session.start.assert_called()
        mock_session.stop.assert_called()
        mock_session.force_scrape.assert_called()

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_torrent_failure(self, mock_asyncio_run, mock_session_class, runner):
        """Test scrape torrent command when scrape fails."""
        info_hash_hex = "a" * 40

        # Create mock session manager
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.force_scrape = AsyncMock(return_value=False)
        mock_session.get_scrape_result = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        result = runner.invoke(scrape, ["torrent", info_hash_hex])

        # Command should exit with error
        assert result.exit_code != 0
        assert "Scrape failed" in result.output

        mock_session.force_scrape.assert_called()

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_torrent_with_cached_result(self, mock_asyncio_run, mock_session_class, runner):
        """Test scrape torrent command with cached result."""
        info_hash_hex = "a" * 40

        # Create mock session manager
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.force_scrape = AsyncMock(return_value=True)
        mock_session.get_scrape_result = AsyncMock(
            return_value=ScrapeResult(
                info_hash=bytes.fromhex(info_hash_hex),
                seeders=75,
                leechers=30,
                completed=600,
                last_scrape_time=time.time() - 10.0,  # 10 seconds ago
                scrape_count=1,
            )
        )
        mock_session_class.return_value = mock_session

        # Invoke without --force flag
        result = runner.invoke(scrape, ["torrent", info_hash_hex])

        # Command should show cached result
        assert result.exit_code == 0
        assert "cached" in result.output.lower()
        assert "Cached Scrape Results" in result.output

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_torrent_with_force_flag(self, mock_asyncio_run, mock_session_class, runner):
        """Test scrape torrent command with --force flag."""
        info_hash_hex = "a" * 40

        # Create mock session manager
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.force_scrape = AsyncMock(return_value=True)
        mock_session.get_scrape_result = AsyncMock(
            return_value=ScrapeResult(
                info_hash=bytes.fromhex(info_hash_hex),
                seeders=100,
                leechers=50,
                completed=1000,
                last_scrape_time=1234567890.0,
                scrape_count=2,
            )
        )
        mock_session_class.return_value = mock_session

        result = runner.invoke(scrape, ["torrent", info_hash_hex, "--force"])

        # Should force scrape regardless of cache
        assert result.exit_code == 0
        mock_session.force_scrape.assert_called()
        assert "Scrape Results" in result.output

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_torrent_exception_handling(self, mock_asyncio_run, mock_session_class, runner):
        """Test scrape torrent command exception handling."""
        info_hash_hex = "a" * 40

        # Create mock session manager that raises exception
        mock_session = MagicMock()
        mock_session.start = AsyncMock(side_effect=Exception("Connection error"))
        mock_session.stop = AsyncMock()
        mock_session_class.return_value = mock_session

        result = runner.invoke(scrape, ["torrent", info_hash_hex])

        # Should handle exception gracefully
        assert result.exit_code != 0
        assert "Error:" in result.output
        # Stop may or may not be called depending on when exception occurs


class TestScrapeListCommand:
    """Test scrape list command."""

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_list_empty(self, mock_asyncio_run, mock_session_class, runner):
        """Test scrape list with empty cache."""
        # Create mock session manager
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.scrape_cache = {}
        mock_session.scrape_cache_lock = MagicMock()

        async def lock_enter(_self):
            return None

        async def lock_exit(_self, *_args):
            return None

        mock_session.scrape_cache_lock.__aenter__ = lock_enter
        mock_session.scrape_cache_lock.__aexit__ = lock_exit
        mock_session_class.return_value = mock_session

        result = runner.invoke(scrape, ["list"])

        # Should show no cached results message
        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert "no cached" in result.output.lower()

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_list_with_results(self, mock_asyncio_run, mock_session_class, runner):
        """Test scrape list with cached results."""
        info_hash1 = b"x" * 20
        info_hash2 = b"y" * 20

        # Create mock session manager with cached results
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        result1 = ScrapeResult(
            info_hash=info_hash1,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=time.time() - 60.0,
            scrape_count=1,
        )
        result2 = ScrapeResult(
            info_hash=info_hash2,
            seeders=75,
            leechers=30,
            completed=600,
            last_scrape_time=time.time() - 120.0,
            scrape_count=2,
        )

        mock_session.scrape_cache = {info_hash1: result1, info_hash2: result2}
        mock_session.scrape_cache_lock = MagicMock()

        async def lock_enter(_self):
            return None

        async def lock_exit(_self, *_args):
            return None

        mock_session.scrape_cache_lock.__aenter__ = lock_enter
        mock_session.scrape_cache_lock.__aexit__ = lock_exit
        mock_session_class.return_value = mock_session

        result = runner.invoke(scrape, ["list"])

        # Should show table with results
        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert "Cached Scrape Results" in result.output
        # The hash is displayed (may be truncated with ellipsis)
        assert info_hash1.hex()[:28] in result.output or "7878" in result.output

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_list_exception_handling(self, mock_asyncio_run, mock_session_class, runner):
        """Test scrape list command exception handling."""
        # Create mock session manager that raises exception
        mock_session = MagicMock()
        mock_session.start = AsyncMock(side_effect=Exception("Error"))
        mock_session.stop = AsyncMock()
        mock_session.scrape_cache = {}
        mock_session.scrape_cache_lock = MagicMock()
        mock_session_class.return_value = mock_session

        result = runner.invoke(scrape, ["list"])

        # Should handle exception gracefully
        assert result.exit_code != 0
        assert "Error:" in result.output
        # Stop may or may not be called depending on when exception occurs

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_torrent_exception_during_scrape(self, mock_asyncio_run, mock_session_class, runner):
        """Test scrape torrent when exception occurs during scrape."""
        info_hash_hex = "a" * 40

        # Create mock session manager that raises exception during force_scrape
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.force_scrape = AsyncMock(side_effect=Exception("Scrape exception"))
        mock_session.get_scrape_result = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        result = runner.invoke(scrape, ["torrent", info_hash_hex])

        # Should handle exception gracefully
        assert result.exit_code != 0
        assert "Error:" in result.output

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_torrent_success_no_cache_entry(self, mock_asyncio_run, mock_session_class, runner):
        """Test scrape torrent when scrape succeeds but no cache entry found (lines 98-101)."""
        info_hash_hex = "a" * 40

        # Create mock session manager
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.force_scrape = AsyncMock(return_value=True)
        # get_scrape_result returns None even after successful scrape (simulating no cache)
        mock_session.get_scrape_result = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session

        result = runner.invoke(scrape, ["torrent", info_hash_hex, "--force"])

        # Should show warning about no cache entry
        assert result.exit_code == 0
        assert "succeeded but no cache" in result.output.lower()

    @patch("ccbt.session.session.AsyncSessionManager")
    @patch("ccbt.cli.scrape_commands.asyncio.run", side_effect=_run_coro_locally)
    def test_scrape_list_exception_during_access(self, mock_asyncio_run, mock_session_class, runner):
        """Test scrape list when exception occurs accessing cache."""
        # Create mock session manager that raises exception during cache access
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.scrape_cache = {}
        mock_session.scrape_cache_lock = MagicMock()

        async def lock_enter():
            raise Exception("Lock error")

        async def lock_exit(*_args):
            return None

        mock_session.scrape_cache_lock.__aenter__ = lock_enter
        mock_session.scrape_cache_lock.__aexit__ = lock_exit
        mock_session_class.return_value = mock_session

        result = runner.invoke(scrape, ["list"])

        # Should handle exception gracefully
        assert result.exit_code != 0
        assert "Error:" in result.output
