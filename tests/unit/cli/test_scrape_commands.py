"""Unit tests for CLI scrape commands (BEP 48).

Tests:
- scrape torrent command
- scrape list command
Target: 95%+ code coverage for ccbt/cli/scrape_commands.py.
"""

from __future__ import annotations

import asyncio
import importlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from ccbt.cli.scrape_commands import scrape

pytestmark = [pytest.mark.unit, pytest.mark.cli]

cli_main = importlib.import_module("ccbt.cli.main")


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


@pytest.fixture(scope="function")
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

    def test_scrape_torrent_success(self, runner, monkeypatch):
        """Test successful scrape torrent command."""
        from ccbt.daemon.ipc_protocol import ScrapeResult as IPCScrapeResult

        info_hash_hex = "a" * 40

        # Mock ScrapeResult response
        mock_scrape_result = IPCScrapeResult(
            info_hash=info_hash_hex,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=1234567890.0,
            scrape_count=1,
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"result": mock_scrape_result}
        ))
        mock_executor.adapter = MagicMock()
        mock_ipc_client = MagicMock()
        mock_ipc_client.close = AsyncMock()
        mock_executor.adapter.ipc_client = mock_ipc_client

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr("ccbt.cli.scrape_commands.asyncio.run", _run_coro_locally)

        result = runner.invoke(scrape, ["torrent", info_hash_hex])

        # Command should execute successfully
        assert result.exit_code == 0
        assert "Scrape Results" in result.output
        assert "100" in result.output  # seeders
        assert "50" in result.output  # leechers

    def test_scrape_torrent_failure(self, runner, monkeypatch):
        """Test scrape torrent command when scrape fails."""
        info_hash_hex = "a" * 40

        # Mock executor with failure
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=False,
            error="Scrape failed"
        ))
        mock_executor.adapter = MagicMock()
        mock_ipc_client = MagicMock()
        mock_ipc_client.close = AsyncMock()
        mock_executor.adapter.ipc_client = mock_ipc_client

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr("ccbt.cli.scrape_commands.asyncio.run", _run_coro_locally)

        result = runner.invoke(scrape, ["torrent", info_hash_hex])

        # Command should exit with error
        assert result.exit_code != 0
        assert "Scrape failed" in result.output or "Failed" in result.output

    def test_scrape_torrent_with_cached_result(self, runner, monkeypatch):
        """Test scrape torrent command with cached result."""
        from ccbt.daemon.ipc_protocol import ScrapeResult as IPCScrapeResult

        info_hash_hex = "a" * 40

        # Mock ScrapeResult response (cached result)
        mock_scrape_result = IPCScrapeResult(
            info_hash=info_hash_hex,
            seeders=75,
            leechers=30,
            completed=600,
            last_scrape_time=time.time() - 10.0,  # 10 seconds ago
            scrape_count=1,
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"result": mock_scrape_result}
        ))
        mock_executor.adapter = MagicMock()
        mock_ipc_client = MagicMock()
        mock_ipc_client.close = AsyncMock()
        mock_executor.adapter.ipc_client = mock_ipc_client

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr("ccbt.cli.scrape_commands.asyncio.run", _run_coro_locally)

        # Invoke without --force flag
        result = runner.invoke(scrape, ["torrent", info_hash_hex])

        # Command should show result
        assert result.exit_code == 0
        assert "Scrape Results" in result.output

    def test_scrape_torrent_with_force_flag(self, runner, monkeypatch):
        """Test scrape torrent command with --force flag."""
        from ccbt.daemon.ipc_protocol import ScrapeResult as IPCScrapeResult

        info_hash_hex = "a" * 40

        # Mock ScrapeResult response
        mock_scrape_result = IPCScrapeResult(
            info_hash=info_hash_hex,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=1234567890.0,
            scrape_count=2,
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"result": mock_scrape_result}
        ))
        mock_executor.adapter = MagicMock()
        mock_ipc_client = MagicMock()
        mock_ipc_client.close = AsyncMock()
        mock_executor.adapter.ipc_client = mock_ipc_client

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr("ccbt.cli.scrape_commands.asyncio.run", _run_coro_locally)

        result = runner.invoke(scrape, ["torrent", info_hash_hex, "--force"])

        # Should force scrape regardless of cache
        assert result.exit_code == 0
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

    def test_scrape_list_empty(self, runner, monkeypatch):
        """Test scrape list with empty cache."""
        from ccbt.daemon.ipc_protocol import ScrapeListResponse

        # Mock empty ScrapeListResponse
        mock_list_response = ScrapeListResponse(results=[])

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"results": mock_list_response}
        ))
        mock_executor.adapter = MagicMock()
        mock_ipc_client = MagicMock()
        mock_ipc_client.close = AsyncMock()
        mock_executor.adapter.ipc_client = mock_ipc_client

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr("ccbt.cli.scrape_commands.asyncio.run", _run_coro_locally)

        result = runner.invoke(scrape, ["list"])

        # Should show no cached results message
        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert "no cached" in result.output.lower() or "No" in result.output

    def test_scrape_list_with_results(self, runner, monkeypatch):
        """Test scrape list with cached results."""
        from ccbt.daemon.ipc_protocol import ScrapeListResponse
        from ccbt.daemon.ipc_protocol import ScrapeResult as IPCScrapeResult

        info_hash1_hex = "x" * 40
        info_hash2_hex = "y" * 40

        # Create mock scrape results
        result1 = IPCScrapeResult(
            info_hash=info_hash1_hex,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=time.time() - 60.0,
            scrape_count=1,
        )
        result2 = IPCScrapeResult(
            info_hash=info_hash2_hex,
            seeders=75,
            leechers=30,
            completed=600,
            last_scrape_time=time.time() - 120.0,
            scrape_count=2,
        )

        # Mock ScrapeListResponse
        mock_list_response = ScrapeListResponse(results=[result1, result2])

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"results": mock_list_response}
        ))
        mock_executor.adapter = MagicMock()
        mock_ipc_client = MagicMock()
        mock_ipc_client.close = AsyncMock()
        mock_executor.adapter.ipc_client = mock_ipc_client

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr("ccbt.cli.scrape_commands.asyncio.run", _run_coro_locally)

        result = runner.invoke(scrape, ["list"])

        # Should show table with results
        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert "Scrape Results" in result.output or "Cached" in result.output
        # The hash is displayed (may be truncated with ellipsis)
        assert info_hash1_hex[:16] in result.output or "x" in result.output

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

    def test_scrape_torrent_success_no_cache_entry(self, runner, monkeypatch):
        """Test scrape torrent when scrape succeeds but no cache entry found (lines 98-101)."""
        from ccbt.daemon.ipc_protocol import ScrapeResult as IPCScrapeResult

        info_hash_hex = "a" * 40

        # Mock ScrapeResult response (scrape succeeds)
        mock_scrape_result = IPCScrapeResult(
            info_hash=info_hash_hex,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=1234567890.0,
            scrape_count=1,
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"result": mock_scrape_result}
        ))
        mock_executor.adapter = MagicMock()
        mock_ipc_client = MagicMock()
        mock_ipc_client.close = AsyncMock()
        mock_executor.adapter.ipc_client = mock_ipc_client

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr("ccbt.cli.scrape_commands.asyncio.run", _run_coro_locally)

        result = runner.invoke(scrape, ["torrent", info_hash_hex, "--force"])

        # Should succeed and show results
        assert result.exit_code == 0
        assert "Scrape Results" in result.output

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
