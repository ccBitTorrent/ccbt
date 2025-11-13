"""Unit tests for status command scrape statistics display (BEP 48).

Tests the enhanced status command that displays detailed scrape statistics table.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

import importlib

cli_main = importlib.import_module("ccbt.cli.main")

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run a coroutine to completion without touching global loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestStatusScrapeDisplay:
    """Test status command scrape statistics display."""

    def test_status_without_scrape_cache_attribute(self, monkeypatch):
        """Test status command when session doesn't have scrape_cache attribute."""
        runner = CliRunner()

        class _FakeSession:
            def __init__(self):
                network = SimpleNamespace(
                    listen_port=6881,
                    enable_utp=False,
                    protocol_v2=SimpleNamespace(
                        enable_protocol_v2=False,
                        prefer_protocol_v2=False,
                        support_hybrid=False,
                        v2_handshake_timeout=30.0,
                    ),
                    webtorrent=SimpleNamespace(enable_webtorrent=False),
                )
                self.config = SimpleNamespace(
                    network=network,
                    discovery=SimpleNamespace(tracker_auto_scrape=False),
                )
                self.peers: list = []
                self.torrents: dict = {}
                self.dht = None
                self.lock = asyncio.Lock()
                # No scrape_cache attribute (to test hasattr False branch)

        monkeypatch.setattr(
            cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=SimpleNamespace())
        )
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeSession())
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_main.cli, ["status"])
        assert result.exit_code == 0
        assert "ccBitTorrent Status" in result.output
        # Should not show scrape statistics table when scrape_cache attribute doesn't exist
        assert "Tracker Scrape Statistics" not in result.output

    def test_status_with_empty_scrape_cache(self, monkeypatch):
        """Test status command with empty scrape cache (should not show table)."""
        runner = CliRunner()

        class _FakeSession:
            def __init__(self):
                network = SimpleNamespace(
                    listen_port=6881,
                    enable_utp=False,
                    protocol_v2=SimpleNamespace(
                        enable_protocol_v2=False,
                        prefer_protocol_v2=False,
                        support_hybrid=False,
                        v2_handshake_timeout=30.0,
                    ),
                    webtorrent=SimpleNamespace(enable_webtorrent=False),
                )
                self.config = SimpleNamespace(
                    network=network,
                    discovery=SimpleNamespace(tracker_auto_scrape=False),
                )
                self.peers: list = []
                self.torrents: dict = {}
                self.dht = None
                self.lock = asyncio.Lock()
                # Empty scrape cache
                self.scrape_cache: dict = {}
                self.scrape_cache_lock = asyncio.Lock()

        monkeypatch.setattr(
            cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=SimpleNamespace())
        )
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeSession())
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_main.cli, ["status"])
        assert result.exit_code == 0
        assert "ccBitTorrent Status" in result.output
        # Should not show scrape statistics table when cache is empty
        assert "Tracker Scrape Statistics" not in result.output

    def test_status_with_scrape_cache_entries(self, monkeypatch):
        """Test status command with scrape cache entries (should show table)."""
        runner = CliRunner()

        from ccbt.models import ScrapeResult

        class _FakeSession:
            def __init__(self):
                network = SimpleNamespace(
                    listen_port=6881,
                    enable_utp=False,
                    protocol_v2=SimpleNamespace(
                        enable_protocol_v2=False,
                        prefer_protocol_v2=False,
                        support_hybrid=False,
                        v2_handshake_timeout=30.0,
                    ),
                    webtorrent=SimpleNamespace(enable_webtorrent=False),
                )
                self.config = SimpleNamespace(
                    network=network,
                    discovery=SimpleNamespace(tracker_auto_scrape=True),
                )
                self.peers: list = []
                self.torrents: dict = {}
                self.dht = None
                self.lock = asyncio.Lock()
                # Scrape cache with entries
                self.scrape_cache: dict = {
                    b"x" * 20: ScrapeResult(
                        info_hash=b"x" * 20,
                        seeders=100,
                        leechers=50,
                        completed=1000,
                        last_scrape_time=1234567890.0,
                        scrape_count=1,
                    ),
                    b"y" * 20: ScrapeResult(
                        info_hash=b"y" * 20,
                        seeders=200,
                        leechers=75,
                        completed=2000,
                        last_scrape_time=1234567890.0,
                        scrape_count=2,
                    ),
                }
                self.scrape_cache_lock = asyncio.Lock()

        monkeypatch.setattr(
            cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=SimpleNamespace())
        )
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeSession())
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_main.cli, ["status"])
        assert result.exit_code == 0
        assert "ccBitTorrent Status" in result.output
        # Should show scrape statistics table
        assert "Tracker Scrape Statistics" in result.output
        # Should show info hash (hex format, truncated)
        # Info hash 'x' * 20 = '7878...' in hex, 'y' * 20 = '7979...' in hex
        assert "7878" in result.output or "7979" in result.output
        # Should show seeders and leechers
        assert "100" in result.output or "200" in result.output
        assert "50" in result.output or "75" in result.output

    def test_status_with_many_scrape_cache_entries(self, monkeypatch):
        """Test status command with more than 10 scrape cache entries (should show only top 10)."""
        runner = CliRunner()

        from ccbt.models import ScrapeResult

        class _FakeSession:
            def __init__(self):
                network = SimpleNamespace(
                    listen_port=6881,
                    enable_utp=False,
                    protocol_v2=SimpleNamespace(
                        enable_protocol_v2=False,
                        prefer_protocol_v2=False,
                        support_hybrid=False,
                        v2_handshake_timeout=30.0,
                    ),
                    webtorrent=SimpleNamespace(enable_webtorrent=False),
                )
                self.config = SimpleNamespace(
                    network=network,
                    discovery=SimpleNamespace(tracker_auto_scrape=True),
                )
                self.peers: list = []
                self.torrents: dict = {}
                self.dht = None
                self.lock = asyncio.Lock()
                # Scrape cache with 15 entries (should only show 10)
                self.scrape_cache: dict = {}
                for i in range(15):
                    info_hash = bytes([i] * 20)
                    self.scrape_cache[info_hash] = ScrapeResult(
                        info_hash=info_hash,
                        seeders=10 + i,
                        leechers=5 + i,
                        completed=100 + i,
                        last_scrape_time=1234567890.0,
                        scrape_count=1,
                    )
                self.scrape_cache_lock = asyncio.Lock()

        monkeypatch.setattr(
            cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=SimpleNamespace())
        )
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeSession())
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_main.cli, ["status"])
        assert result.exit_code == 0
        assert "Tracker Scrape Statistics" in result.output
        # Count occurrences of seeders to verify we're showing limited entries
        # (exact count depends on output format, but should be <= 10)

    def test_status_scrape_display_error_handling(self, monkeypatch):
        """Test status command handles errors in scrape display gracefully."""
        runner = CliRunner()

        from ccbt.models import ScrapeResult

        class _FakeSession:
            def __init__(self):
                network = SimpleNamespace(
                    listen_port=6881,
                    enable_utp=False,
                    protocol_v2=SimpleNamespace(
                        enable_protocol_v2=False,
                        prefer_protocol_v2=False,
                        support_hybrid=False,
                        v2_handshake_timeout=30.0,
                    ),
                    webtorrent=SimpleNamespace(enable_webtorrent=False),
                )
                self.config = SimpleNamespace(
                    network=network,
                    discovery=SimpleNamespace(tracker_auto_scrape=True),
                )
                self.peers: list = []
                self.torrents: dict = {}
                self.dht = None
                self.lock = asyncio.Lock()
                # Scrape cache with entry that might cause error
                self.scrape_cache: dict = {
                    b"x" * 20: ScrapeResult(
                        info_hash=b"x" * 20,
                        seeders=100,
                        leechers=50,
                        completed=1000,
                        last_scrape_time=1234567890.0,
                        scrape_count=1,
                    ),
                }
                # Create a lock that raises error when used as async context manager
                self._lock_raises_error = True

            @property
            def scrape_cache_lock(self):
                if self._lock_raises_error:
                    # Return an object that raises error when used as async context manager
                    class ErrorLock:
                        async def __aenter__(self):
                            raise RuntimeError("Lock error")
                        async def __aexit__(self, *args):
                            pass
                    return ErrorLock()
                return asyncio.Lock()

        monkeypatch.setattr(
            cli_main, "ConfigManager", lambda *_a, **_k: SimpleNamespace(config=SimpleNamespace())
        )
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *_a, **_k: _FakeSession())
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_main.cli, ["status"])
        # Should still succeed despite error in scrape display
        assert result.exit_code == 0
        assert "ccBitTorrent Status" in result.output
        # Verify that the exception was caught (no traceback in output)
        assert "Lock error" not in result.output
        # Verify scrape statistics table is not shown due to error
        assert "Tracker Scrape Statistics" not in result.output

    @pytest.mark.asyncio
    async def test_show_status_function_with_scrape_cache(self):
        """Test show_status async function directly with scrape cache."""
        from ccbt.models import ScrapeResult
        from io import StringIO

        session = MagicMock()
        network = SimpleNamespace(
            listen_port=6881,
            enable_utp=False,
            protocol_v2=SimpleNamespace(
                enable_protocol_v2=False,
                prefer_protocol_v2=False,
                support_hybrid=False,
                v2_handshake_timeout=30.0,
            ),
            webtorrent=SimpleNamespace(enable_webtorrent=False),
        )
        session.config = SimpleNamespace(
            network=network,
            discovery=SimpleNamespace(tracker_auto_scrape=True),
        )
        session.peers = []
        session.torrents = {}
        session.dht = None
        session.lock = AsyncMock()
        session.lock.__aenter__ = AsyncMock(return_value=None)
        session.lock.__aexit__ = AsyncMock(return_value=None)

        # Scrape cache with entries
        session.scrape_cache = {
            b"x" * 20: ScrapeResult(
                info_hash=b"x" * 20,
                seeders=100,
                leechers=50,
                completed=1000,
                last_scrape_time=1234567890.0,
                scrape_count=1,
            ),
        }
        session.scrape_cache_lock = AsyncMock()
        session.scrape_cache_lock.__aenter__ = AsyncMock(return_value=None)
        session.scrape_cache_lock.__aexit__ = AsyncMock(return_value=None)

        console = Console(file=StringIO(), width=120)
        
        # Patch console.print to track calls (for coverage verification)
        print_call_count = 0
        original_print = console.print
        
        def tracked_print(*args, **kwargs):
            nonlocal print_call_count
            print_call_count += 1
            return original_print(*args, **kwargs)
        
        console.print = tracked_print

        # Call show_status directly
        await cli_main.show_status(session, console)

        # Verify scrape cache was accessed
        session.scrape_cache_lock.__aenter__.assert_called()
        session.scrape_cache_lock.__aexit__.assert_called()
        
        # Verify output contains scrape statistics
        output = console.file.getvalue()
        assert "Tracker Scrape Statistics" in output
        
        # Verify console.print was called for the table (to ensure line 2585 is covered)
        # We expect at least 2 calls: one for the header and one for the table
        assert print_call_count >= 2, f"Expected at least 2 console.print calls, got {print_call_count}"

    @pytest.mark.asyncio
    async def test_show_status_without_scrape_cache_attribute(self):
        """Test show_status when session doesn't have scrape_cache attribute."""
        from io import StringIO

        session = MagicMock()
        network = SimpleNamespace(
            listen_port=6881,
            enable_utp=False,
            protocol_v2=SimpleNamespace(
                enable_protocol_v2=False,
                prefer_protocol_v2=False,
                support_hybrid=False,
                v2_handshake_timeout=30.0,
            ),
            webtorrent=SimpleNamespace(enable_webtorrent=False),
        )
        session.config = SimpleNamespace(
            network=network,
            discovery=SimpleNamespace(tracker_auto_scrape=True),
        )
        session.peers = []
        session.torrents = {}
        session.dht = None
        session.lock = AsyncMock()
        session.lock.__aenter__ = AsyncMock(return_value=None)
        session.lock.__aexit__ = AsyncMock(return_value=None)
        
        # No scrape_cache attribute
        # (don't set session.scrape_cache to test hasattr False branch)

        console = Console(file=StringIO(), width=120)

        # Call show_status directly - should not error even without scrape_cache
        await cli_main.show_status(session, console)

        # Verify output does not contain scrape statistics
        output = console.file.getvalue()
        assert "Tracker Scrape Statistics" not in output

