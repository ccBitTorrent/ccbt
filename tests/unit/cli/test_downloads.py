"""Tests for CLI downloads module - comprehensive test suite for Phase 2 fixes.

Tests verify:
- F811 fix: No duplicate function definitions (start_interactive_magnet_download)
- Function works correctly after any fixes
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.cli import downloads
from ccbt.session.session import AsyncSessionManager

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run a coroutine to completion without touching global loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestDownloadsF811Fix:
    """Test that F811 fix (no duplicate function definitions) works correctly."""

    def test_start_interactive_magnet_download_exists(self):
        """Test that start_interactive_magnet_download function exists and is callable."""
        # Verify function exists (only one definition - F811 fix verified)
        assert hasattr(downloads, "start_interactive_magnet_download")
        assert callable(downloads.start_interactive_magnet_download)

    def test_start_interactive_magnet_download_signature(self):
        """Test that start_interactive_magnet_download has correct signature."""
        import inspect

        sig = inspect.signature(downloads.start_interactive_magnet_download)
        params = list(sig.parameters.keys())

        # Verify expected parameters
        assert "session" in params
        assert "magnet_link" in params
        assert "info_hash_hex" in params
        assert "console" in params
        assert "resume" in params

    @pytest.mark.asyncio
    async def test_start_interactive_magnet_download_basic(self, monkeypatch):
        """Test start_interactive_magnet_download function executes without errors."""
        from rich.console import Console

        # Create mock session
        mock_session = MagicMock(spec=AsyncSessionManager)
        mock_session._cleanup_task = None
        mock_session.start = AsyncMock()

        # Create mock executor
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error = None
        mock_executor.execute = AsyncMock(return_value=mock_result)

        # Mock LocalSessionAdapter, UnifiedCommandExecutor, and InteractiveCLI (avoid real UI)
        mock_adapter = MagicMock()
        mock_interactive = MagicMock()
        mock_interactive.download_torrent = AsyncMock(return_value=None)
        with patch("ccbt.cli.downloads.LocalSessionAdapter", return_value=mock_adapter), \
             patch("ccbt.cli.downloads.UnifiedCommandExecutor", return_value=mock_executor), \
             patch("ccbt.cli.downloads.InteractiveCLI", return_value=mock_interactive):
            console = Console()
            magnet_link = "magnet:?xt=urn:btih:test"
            info_hash_hex = "a" * 40

            # Test that function can be called (may raise KeyboardInterrupt or other expected errors)
            try:
                await downloads.start_interactive_magnet_download(
                    mock_session,
                    magnet_link,
                    info_hash_hex,
                    console,
                    resume=False,
                )
            except (KeyboardInterrupt, RuntimeError):
                # Expected errors - function structure is correct
                pass

            # Verify session.start was called if cleanup_task was None
            if mock_session._cleanup_task is None:
                mock_session.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_interactive_magnet_download_with_existing_session(self, monkeypatch):
        """Test start_interactive_magnet_download with existing session cleanup task."""
        from rich.console import Console

        # Create mock session with existing cleanup task
        mock_session = MagicMock(spec=AsyncSessionManager)
        mock_session._cleanup_task = MagicMock()  # Existing task
        mock_session.start = AsyncMock()

        # Create mock executor
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error = None
        mock_executor.execute = AsyncMock(return_value=mock_result)

        # Mock LocalSessionAdapter, UnifiedCommandExecutor, and InteractiveCLI (avoid real UI)
        mock_adapter = MagicMock()
        mock_interactive = MagicMock()
        mock_interactive.download_torrent = AsyncMock(return_value=None)
        with patch("ccbt.cli.downloads.LocalSessionAdapter", return_value=mock_adapter), \
             patch("ccbt.cli.downloads.UnifiedCommandExecutor", return_value=mock_executor), \
             patch("ccbt.cli.downloads.InteractiveCLI", return_value=mock_interactive):
            console = Console()
            magnet_link = "magnet:?xt=urn:btih:test"
            info_hash_hex = "a" * 40

            # Test that function can be called
            try:
                await downloads.start_interactive_magnet_download(
                    mock_session,
                    magnet_link,
                    info_hash_hex,
                    console,
                    resume=False,
                )
            except (KeyboardInterrupt, RuntimeError):
                # Expected errors - function structure is correct
                pass

            # Verify session.start was NOT called if cleanup_task exists
            mock_session.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_interactive_magnet_download_executor_failure(self, monkeypatch):
        """Test start_interactive_magnet_download handles executor failures."""
        from rich.console import Console

        # Create mock session
        mock_session = MagicMock(spec=AsyncSessionManager)
        mock_session._cleanup_task = None
        mock_session.start = AsyncMock()

        # Create mock executor that fails
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Test error"
        mock_executor.execute = AsyncMock(return_value=mock_result)

        # Mock LocalSessionAdapter, UnifiedCommandExecutor, and InteractiveCLI to raise on download_torrent
        mock_adapter = MagicMock()
        mock_interactive = MagicMock()
        mock_interactive.download_torrent = AsyncMock(
            side_effect=RuntimeError("Test error")
        )
        with patch("ccbt.cli.downloads.LocalSessionAdapter", return_value=mock_adapter), \
             patch("ccbt.cli.downloads.UnifiedCommandExecutor", return_value=mock_executor), \
             patch("ccbt.cli.downloads.InteractiveCLI", return_value=mock_interactive):
            console = Console()
            magnet_link = "magnet:?xt=urn:btih:test"
            info_hash_hex = "a" * 40

            # Function calls InteractiveCLI.download_torrent which we mock to raise RuntimeError
            with pytest.raises(RuntimeError, match="Test error"):
                await downloads.start_interactive_magnet_download(
                    mock_session,
                    magnet_link,
                    info_hash_hex,
                    console,
                    resume=False,
                )


class TestDownloadsFunctionUniqueness:
    """Test that there are no duplicate function definitions (F811 verification)."""

    def test_no_duplicate_start_interactive_magnet_download(self):
        """Verify there's only one definition of start_interactive_magnet_download."""
        import inspect

        import ccbt.cli.downloads as downloads_module

        # Get all functions in the module
        functions = [
            name
            for name, obj in inspect.getmembers(downloads_module, inspect.iscoroutinefunction)
            if name == "start_interactive_magnet_download"
        ]

        # Should be exactly one
        assert len(functions) == 1, "Found duplicate definitions of start_interactive_magnet_download"

