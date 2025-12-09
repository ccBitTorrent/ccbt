"""Tests for file selection in interactive download functions.

Covers:
- start_interactive_download with files_selection (lines 2395-2428)
- start_interactive_download with file_priorities (lines 2410-2428)
- start_basic_download with files_selection (lines 2482-2519)
- start_basic_download with file_priorities (lines 2501-2519)
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

cli_main = __import__("ccbt.cli.main", fromlist=["start_interactive_download", "start_basic_download"])

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run a coroutine to completion without touching global loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def mock_torrent_session():
    """Create a mock torrent session with file selection manager."""
    mock_manager = MagicMock()
    mock_manager.deselect_all = AsyncMock()
    mock_manager.select_files = AsyncMock()
    mock_manager.set_file_priority = AsyncMock()
    
    mock_session = SimpleNamespace(
        file_selection_manager=mock_manager,
    )
    return mock_session


@pytest.fixture
def mock_session_manager(mock_torrent_session):
    """Create a mock session manager."""
    info_hash_bytes = b"\x00" * 20
    info_hash_hex = info_hash_bytes.hex()
    
    session = AsyncMock()
    session.add_torrent = AsyncMock(return_value=info_hash_hex)
    session.torrents = {info_hash_bytes: mock_torrent_session}
    session.lock = AsyncMock()
    session.lock.__aenter__ = AsyncMock(return_value=None)
    session.lock.__aexit__ = AsyncMock(return_value=None)
    session.queue_manager = None
    
    return session


@pytest.fixture
def mock_console():
    """Create a mock console."""
    console = MagicMock()
    console.print = MagicMock()
    return console


class TestStartInteractiveDownloadFileSelection:
    """Tests for file selection in start_interactive_download (lines 2395-2428)."""

    @pytest.mark.asyncio
    async def test_files_selection_before_interactive(
        self, mock_session_manager, mock_torrent_session, mock_console
    ):
        """Test files_selection applied before interactive mode (lines 2406-2408)."""
        from ccbt.cli.interactive import InteractiveCLI
        
        torrent_data = {"name": "test", "info_hash": b"\x00" * 20}
        
        with patch("ccbt.cli.main.InteractiveCLI") as mock_interactive_cli:
            mock_interactive = MagicMock()
            mock_interactive.download_torrent = AsyncMock()
            mock_interactive.current_info_hash_hex = "0" * 40
            mock_interactive_cli.return_value = mock_interactive
            
            await cli_main.start_interactive_download(
                mock_session_manager,
                torrent_data,
                mock_console,
                resume=False,
                files_selection=(0, 1),
            )
            
            # Verify deselect_all and select_files were called
            mock_torrent_session.file_selection_manager.deselect_all.assert_called_once()
            mock_torrent_session.file_selection_manager.select_files.assert_called_once_with([0, 1])

    @pytest.mark.asyncio
    async def test_file_priorities_before_interactive(
        self, mock_session_manager, mock_torrent_session, mock_console
    ):
        """Test file_priorities applied before interactive mode (lines 2411-2428)."""
        from ccbt.cli.interactive import InteractiveCLI
        
        torrent_data = {"name": "test", "info_hash": b"\x00" * 20}
        
        with patch("ccbt.cli.main.InteractiveCLI") as mock_interactive_cli:
            mock_interactive = MagicMock()
            mock_interactive.download_torrent = AsyncMock()
            mock_interactive.current_info_hash_hex = "0" * 40
            mock_interactive_cli.return_value = mock_interactive
            
            await cli_main.start_interactive_download(
                mock_session_manager,
                torrent_data,
                mock_console,
                resume=False,
                file_priorities=("0=high", "1=normal"),
            )
            
            # Verify set_file_priority was called twice
            assert mock_torrent_session.file_selection_manager.set_file_priority.call_count == 2

    @pytest.mark.asyncio
    async def test_file_priorities_invalid_format(
        self, mock_session_manager, mock_torrent_session, mock_console
    ):
        """Test file_priorities with invalid format (lines 2420-2428)."""
        from ccbt.cli.interactive import InteractiveCLI
        
        torrent_data = {"name": "test", "info_hash": b"\x00" * 20}
        
        with patch("ccbt.cli.main.InteractiveCLI") as mock_interactive_cli:
            mock_interactive = MagicMock()
            mock_interactive.download_torrent = AsyncMock()
            mock_interactive.current_info_hash_hex = "0" * 40
            mock_interactive_cli.return_value = mock_interactive
            
            # Test with invalid format (no = separator)
            await cli_main.start_interactive_download(
                mock_session_manager,
                torrent_data,
                mock_console,
                resume=False,
                file_priorities=("invalid-format",),
            )
            
            # Should print warning about invalid priority spec
            assert mock_console.print.called

    @pytest.mark.asyncio
    async def test_file_priorities_invalid_priority_name(
        self, mock_session_manager, mock_torrent_session, mock_console
    ):
        """Test file_priorities with invalid priority name (KeyError) (lines 2425-2428)."""
        from ccbt.cli.interactive import InteractiveCLI
        
        torrent_data = {"name": "test", "info_hash": b"\x00" * 20}
        
        with patch("ccbt.cli.main.InteractiveCLI") as mock_interactive_cli:
            mock_interactive = MagicMock()
            mock_interactive.download_torrent = AsyncMock()
            mock_interactive.current_info_hash_hex = "0" * 40
            mock_interactive_cli.return_value = mock_interactive
            
            # Test with invalid priority name
            await cli_main.start_interactive_download(
                mock_session_manager,
                torrent_data,
                mock_console,
                resume=False,
                file_priorities=("0=invalid_priority",),
            )
            
            # Should print warning about invalid priority spec
            assert mock_console.print.called

    @pytest.mark.asyncio
    async def test_file_priorities_with_value_error(
        self, mock_session_manager, mock_torrent_session, mock_console
    ):
        """Test file_priorities with ValueError (invalid file index) (lines 2420-2428)."""
        from ccbt.cli.interactive import InteractiveCLI
        
        torrent_data = {"name": "test", "info_hash": b"\x00" * 20}
        
        with patch("ccbt.cli.main.InteractiveCLI") as mock_interactive_cli:
            mock_interactive = MagicMock()
            mock_interactive.download_torrent = AsyncMock()
            mock_interactive.current_info_hash_hex = "0" * 40
            mock_interactive_cli.return_value = mock_interactive
            
            # Test with invalid file index (non-numeric)
            await cli_main.start_interactive_download(
                mock_session_manager,
                torrent_data,
                mock_console,
                resume=False,
                file_priorities=("not-a-number=high",),
            )
            
            # Should print warning about invalid priority spec
            assert mock_console.print.called


class TestStartBasicDownloadFileSelection:
    """Tests for file selection in start_basic_download (lines 2482-2519)."""

    @pytest.mark.asyncio
    async def test_files_selection_in_basic_download(
        self, mock_session_manager, mock_torrent_session, mock_console
    ):
        """Test files_selection in basic download (lines 2493-2499)."""
        torrent_data = {"name": "test", "info_hash": b"\x00" * 20}
        
        # Mock the progress monitoring loop to exit immediately
        # Progress is imported from rich.progress in main.py
        with patch("rich.progress.Progress") as mock_progress_class:
            mock_progress_instance = MagicMock()
            mock_progress_instance.__enter__ = MagicMock(return_value=mock_progress_instance)
            mock_progress_instance.__exit__ = MagicMock(return_value=False)
            mock_progress_instance.add_task = MagicMock(return_value=MagicMock())
            mock_progress_class.return_value = mock_progress_instance
            
            # Make the while loop exit quickly by making get_torrent_status return None after first call
            call_count = 0
            async def mock_get_status(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count > 1:
                    return None  # Exit loop
                return {"status": "downloading", "progress": 0.5}
            
            mock_session_manager.get_torrent_status = AsyncMock(side_effect=mock_get_status)
            
            try:
                await cli_main.start_basic_download(
                    mock_session_manager,
                    torrent_data,
                    mock_console,
                    resume=False,
                    files_selection=(0, 1),
                )
            except (StopIteration, RuntimeError, asyncio.CancelledError):
                # Expected when loop exits
                pass
            
            # Verify deselect_all and select_files were called
            mock_torrent_session.file_selection_manager.deselect_all.assert_called_once()
            mock_torrent_session.file_selection_manager.select_files.assert_called_once_with([0, 1])
            # Verify success message was printed
            assert mock_console.print.called

    @pytest.mark.asyncio
    async def test_file_priorities_in_basic_download(
        self, mock_session_manager, mock_torrent_session, mock_console
    ):
        """Test file_priorities in basic download (lines 2502-2519)."""
        torrent_data = {"name": "test", "info_hash": b"\x00" * 20}
        
        # Mock the progress monitoring loop to exit immediately
        # Progress is imported from rich.progress in main.py
        with patch("rich.progress.Progress") as mock_progress_class:
            mock_progress_instance = MagicMock()
            mock_progress_instance.__enter__ = MagicMock(return_value=mock_progress_instance)
            mock_progress_instance.__exit__ = MagicMock(return_value=False)
            mock_progress_instance.add_task = MagicMock(return_value=MagicMock())
            mock_progress_class.return_value = mock_progress_instance
            
            # Make the while loop exit quickly
            call_count = 0
            async def mock_get_status(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count > 1:
                    return None
                return {"status": "downloading", "progress": 0.5}
            
            mock_session_manager.get_torrent_status = AsyncMock(side_effect=mock_get_status)
            
            try:
                await cli_main.start_basic_download(
                    mock_session_manager,
                    torrent_data,
                    mock_console,
                    resume=False,
                    file_priorities=("0=high", "1=normal"),
                )
            except (StopIteration, RuntimeError, asyncio.CancelledError):
                pass
            
            # Verify set_file_priority was called
            assert mock_torrent_session.file_selection_manager.set_file_priority.call_count >= 1

    @pytest.mark.asyncio
    async def test_file_priorities_invalid_in_basic_download(
        self, mock_session_manager, mock_torrent_session, mock_console
    ):
        """Test invalid file_priorities in basic download (lines 2516-2519)."""
        torrent_data = {"name": "test", "info_hash": b"\x00" * 20}
        
        # Mock the progress monitoring loop to exit immediately
        # Progress is imported from rich.progress in main.py
        with patch("rich.progress.Progress") as mock_progress_class:
            mock_progress_instance = MagicMock()
            mock_progress_instance.__enter__ = MagicMock(return_value=mock_progress_instance)
            mock_progress_instance.__exit__ = MagicMock(return_value=False)
            mock_progress_instance.add_task = MagicMock(return_value=MagicMock())
            mock_progress_class.return_value = mock_progress_instance
            
            # Make the while loop exit quickly
            call_count = 0
            async def mock_get_status(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count > 1:
                    return None
                return {"status": "downloading", "progress": 0.5}
            
            mock_session_manager.get_torrent_status = AsyncMock(side_effect=mock_get_status)
            
            try:
                await cli_main.start_basic_download(
                    mock_session_manager,
                    torrent_data,
                    mock_console,
                    resume=False,
                    file_priorities=("invalid-format",),
                )
            except (StopIteration, RuntimeError, asyncio.CancelledError):
                pass
            
            # Should print warning about invalid priority spec
            assert mock_console.print.called

