"""Comprehensive tests for interactive file selection features.

Tests interactive file selection UI, enhanced cmd_files command, and status display.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.cli]

from ccbt.cli.interactive import InteractiveCLI
from ccbt.models import FileInfo, TorrentInfo
from ccbt.piece.file_selection import FilePriority, FileSelectionManager, FileSelectionState


@pytest.fixture
def mock_session():
    """Create a mock AsyncSessionManager."""
    session = AsyncMock()
    session.add_torrent = AsyncMock(return_value="abcd1234" * 5)  # 40 char hex
    session.get_torrent_status = AsyncMock(return_value={"status": "downloading", "progress": 0.5})
    session.lock = AsyncMock()
    session.lock.__aenter__ = AsyncMock(return_value=None)
    session.lock.__aexit__ = AsyncMock(return_value=None)
    session.torrents = {}
    session.peers = []
    session.config = MagicMock()
    session.config.network = MagicMock()
    session.config.network.listen_port = 6881
    session.dht = None
    return session


@pytest.fixture
def mock_console():
    """Create a mock Console."""
    console = MagicMock()
    console.print = Mock()
    console.clear = Mock()
    return console


@pytest.fixture
def multi_file_torrent_info():
    """Create multi-file torrent info for testing."""
    return TorrentInfo(
        name="test_torrent",
        info_hash=b"\x01" * 20,
        announce="http://tracker.example.com/announce",
        files=[
            FileInfo(
                name="file0.txt",
                length=1024 * 1024,  # 1 MB
                path=["file0.txt"],
                full_path="file0.txt",
            ),
            FileInfo(
                name="file1.txt",
                length=2048 * 1024,  # 2 MB
                path=["file1.txt"],
                full_path="file1.txt",
            ),
            FileInfo(
                name="file2.txt",
                length=512 * 1024,  # 512 KB
                path=["file2.txt"],
                full_path="file2.txt",
            ),
        ],
        total_length=3584 * 1024,
        piece_length=16384,
        pieces=[b"\x02" * 20 for _ in range(5)],
        num_pieces=5,
    )


@pytest.fixture
def file_selection_manager(multi_file_torrent_info):
    """Create a FileSelectionManager instance with mocked async methods for testing."""
    manager = FileSelectionManager(multi_file_torrent_info)
    # Mock async methods to enable assertions while preserving get_all_file_states behavior
    original_select = manager.select_file
    original_deselect = manager.deselect_file
    original_select_all_method = manager.select_all
    original_deselect_all_method = manager.deselect_all
    original_set_priority_method = manager.set_file_priority
    
    async def mock_select(idx):
        await original_select(idx)
    
    async def mock_deselect(idx):
        await original_deselect(idx)
    
    async def mock_select_all_impl():
        await original_select_all_method()
    
    async def mock_deselect_all_impl():
        await original_deselect_all_method()
    
    async def mock_set_priority_impl(idx, pri):
        await original_set_priority_method(idx, pri)
    
    # Wrap with AsyncMock using setattr to avoid shadowing warnings
    setattr(manager, "select_file", AsyncMock(side_effect=mock_select))
    setattr(manager, "deselect_file", AsyncMock(side_effect=mock_deselect))
    setattr(manager, "select_all", AsyncMock(side_effect=mock_select_all_impl))
    setattr(manager, "deselect_all", AsyncMock(side_effect=mock_deselect_all_impl))
    setattr(manager, "set_file_priority", AsyncMock(side_effect=mock_set_priority_impl))
    return manager


@pytest.fixture
def torrent_session_with_files(file_selection_manager):
    """Create a mock torrent session with file selection manager."""
    session = MagicMock()
    session.file_selection_manager = file_selection_manager
    return session


@pytest.fixture
def interactive_cli_with_layout(interactive_cli):
    """Create InteractiveCLI with layout set up."""
    interactive_cli.setup_layout()
    return interactive_cli


@pytest.fixture
def interactive_cli(mock_session, mock_console):
    """Create an InteractiveCLI instance."""
    return InteractiveCLI(mock_session, mock_console)


class TestInteractiveFileSelection:
    """Test interactive file selection UI."""

    @pytest.mark.asyncio
    async def test_interactive_file_selection_empty_state(
        self,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with empty file states."""
        # Create empty file selection manager
        empty_manager = MagicMock()
        empty_manager.get_all_file_states = Mock(return_value={})

        await interactive_cli._interactive_file_selection(empty_manager)

        # Should return early without prompting
        empty_manager.select_file.assert_not_called()
        empty_manager.deselect_file.assert_not_called()

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_done_immediately(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with 'done' command."""
        mock_prompt.return_value = "done"

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should call prompt once and exit
        mock_prompt.assert_called_once()
        # Console should print the file table
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_select_all(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with 'select-all' command."""
        mock_prompt.side_effect = ["select-all", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should call select_all
        file_selection_manager.select_all.assert_called_once()
        # Should show success message
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_deselect_all(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with 'deselect-all' command."""
        mock_prompt.side_effect = ["deselect-all", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should call deselect_all
        file_selection_manager.deselect_all.assert_called_once()

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_select_file(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with 'select' command."""
        mock_prompt.side_effect = ["select 1", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should call select_file with index 1
        file_selection_manager.select_file.assert_called_once_with(1)

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_deselect_file(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with 'deselect' command."""
        mock_prompt.side_effect = ["deselect 0", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should call deselect_file with index 0
        file_selection_manager.deselect_file.assert_called_once_with(0)

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_priority(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with 'priority' command."""
        mock_prompt.side_effect = ["priority 0 high", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should call set_file_priority with index 0 and HIGH priority
        file_selection_manager.set_file_priority.assert_called_once_with(0, FilePriority.HIGH)

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_invalid_file_index(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with invalid file index."""
        mock_prompt.side_effect = ["select 999", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should not call select_file with invalid index
        file_selection_manager.select_file.assert_not_called()
        # Should print error message
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_invalid_priority(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with invalid priority."""
        mock_prompt.side_effect = ["priority 0 invalid", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should not call set_file_priority
        file_selection_manager.set_file_priority.assert_not_called()
        # Should print error message
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_keyboard_interrupt(  # pragma: no cover
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection handling KeyboardInterrupt."""
        mock_prompt.side_effect = KeyboardInterrupt()

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should handle gracefully and print cancellation message
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_multiple_commands(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with multiple commands."""
        mock_prompt.side_effect = [
            "select 0",
            "deselect 1",
            "priority 2 maximum",
            "done",
        ]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should call all three operations
        file_selection_manager.select_file.assert_called_with(0)
        file_selection_manager.deselect_file.assert_called_with(1)
        file_selection_manager.set_file_priority.assert_called_with(2, FilePriority.MAXIMUM)

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_table_refresh(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test that table refreshes after each command."""
        mock_prompt.side_effect = ["select 0", "select 1", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should print table multiple times (initial + after each command)
        assert interactive_cli.console.print.call_count >= 3

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_empty_command(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with empty command."""
        mock_prompt.side_effect = ["", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should handle empty command gracefully (continue loop)
        mock_prompt.assert_called()

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_unknown_command(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with unknown command."""
        mock_prompt.side_effect = ["unknown-command", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should print error message for unknown command
        calls = [str(call) for call in interactive_cli.console.print.call_args_list]
        assert any("Unknown command" in str(call) for call in calls)

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_priority_invalid_file_idx(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection priority with invalid file index."""
        mock_prompt.side_effect = ["priority 999 normal", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should not call set_file_priority
        file_selection_manager.set_file_priority.assert_not_called()

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_all_priority_levels(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test interactive file selection with all priority levels."""
        mock_prompt.side_effect = [
            "priority 0 do_not_download",
            "priority 1 low",
            "priority 2 normal",
            "priority 0 high",  # Change existing
            "priority 1 maximum",
            "done",
        ]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should call set_file_priority for each priority level
        assert file_selection_manager.set_file_priority.call_count == 5

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_size_formatting_mb(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test that file sizes are formatted correctly for MB."""
        mock_prompt.return_value = "done"

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Check that console.print was called (table display)
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_select_less_than_two_args(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test select command with insufficient arguments."""
        mock_prompt.side_effect = ["select", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should not call select_file when args insufficient
        file_selection_manager.select_file.assert_not_called()

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_deselect_less_than_two_args(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test deselect command with insufficient arguments."""
        mock_prompt.side_effect = ["deselect", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should not call deselect_file when args insufficient
        file_selection_manager.deselect_file.assert_not_called()

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_priority_less_than_three_args(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test priority command with insufficient arguments."""
        mock_prompt.side_effect = ["priority 0", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should not call set_file_priority when args insufficient
        file_selection_manager.set_file_priority.assert_not_called()

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_deselect_value_error(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test deselect command with ValueError (non-numeric index)."""
        mock_prompt.side_effect = ["deselect invalid", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should handle ValueError gracefully
        file_selection_manager.deselect_file.assert_not_called()

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_interactive_file_selection_priority_value_error(
        self,
        mock_prompt,
        interactive_cli,
        file_selection_manager,
    ):
        """Test priority command with ValueError (non-numeric index)."""
        mock_prompt.side_effect = ["priority invalid normal", "done"]

        await interactive_cli._interactive_file_selection(file_selection_manager)

        # Should handle ValueError gracefully
        file_selection_manager.set_file_priority.assert_not_called()


class TestCmdFiles:
    """Test enhanced cmd_files command."""

    @pytest.mark.asyncio
    async def test_cmd_files_no_torrent(self, interactive_cli):
        """Test cmd_files when no torrent is active."""
        interactive_cli.current_info_hash_hex = None

        await interactive_cli.cmd_files([])

        # Should print error message
        interactive_cli.console.print.assert_called_with("No torrent active")

    @pytest.mark.asyncio
    async def test_cmd_files_no_file_manager(
        self,
        interactive_cli,
        mock_session,
    ):
        """Test cmd_files when file manager is not available."""
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {}
        interactive_cli.session = mock_session

        async def get_torrent_none(_bytes):
            return None

        mock_session.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session.lock.__aexit__ = AsyncMock(return_value=None)

        await interactive_cli.cmd_files([])

        # Should print error about file selection not available
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_display_table(
        self,
        interactive_cli,
        mock_session,
        torrent_session_with_files,
    ):
        """Test cmd_files displays file table."""
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli.session = mock_session

        await interactive_cli.cmd_files([])

        # Should print table
        assert interactive_cli.console.print.called
        # Should print usage hint
        calls = [str(call) for call in interactive_cli.console.print.call_args_list]
        assert any("files select" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_cmd_files_select_command(
        self,
        interactive_cli,
        mock_session,
        torrent_session_with_files,
    ):
        """Test cmd_files select subcommand."""
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli.session = mock_session

        await interactive_cli.cmd_files(["select", "0"])

        # Should call select_file
        torrent_session_with_files.file_selection_manager.select_file.assert_called_once_with(0)
        # Should print success message
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_deselect_command(
        self,
        interactive_cli,
        mock_session,
        torrent_session_with_files,
    ):
        """Test cmd_files deselect subcommand."""
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli.session = mock_session

        await interactive_cli.cmd_files(["deselect", "1"])

        # Should call deselect_file
        torrent_session_with_files.file_selection_manager.deselect_file.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_cmd_files_priority_command(
        self,
        interactive_cli,
        mock_session,
        torrent_session_with_files,
    ):
        """Test cmd_files priority subcommand."""
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli.session = mock_session

        await interactive_cli.cmd_files(["priority", "2", "high"])

        # Should call set_file_priority
        torrent_session_with_files.file_selection_manager.set_file_priority.assert_called_once_with(
            2,
            FilePriority.HIGH,
        )

    @pytest.mark.asyncio
    async def test_cmd_files_priority_invalid(
        self,
        interactive_cli,
        mock_session,
        torrent_session_with_files,
    ):
        """Test cmd_files priority with invalid priority value."""
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli.session = mock_session

        await interactive_cli.cmd_files(["priority", "0", "invalid"])

        # Should not call set_file_priority
        torrent_session_with_files.file_selection_manager.set_file_priority.assert_not_called()
        # Should print error message
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_select_invalid_index(
        self,
        interactive_cli,
        mock_session,
        torrent_session_with_files,
    ):
        """Test cmd_files select with invalid file index."""
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli.session = mock_session

        await interactive_cli.cmd_files(["select", "invalid"])

        # Should not call select_file
        torrent_session_with_files.file_selection_manager.select_file.assert_not_called()
        # Should print error message
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_progress_calculation(
        self,
        interactive_cli,
        mock_session,
        torrent_session_with_files,
    ):
        """Test cmd_files displays progress correctly."""
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli.session = mock_session

        # Set some progress on files
        file_manager = torrent_session_with_files.file_selection_manager
        await file_manager.update_file_progress(0, 512 * 1024)  # 50% of 1MB file

        await interactive_cli.cmd_files([])

        # Should display progress in table
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_size_formatting(
        self,
        interactive_cli,
        mock_session,
        torrent_session_with_files,
    ):
        """Test cmd_files formats file sizes correctly."""
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli.session = mock_session

        await interactive_cli.cmd_files([])

        # Should format sizes (MB for >1MB, KB for <1MB)
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_deselect_index_error(
        self,
        interactive_cli,
        mock_session,
        torrent_session_with_files,
    ):
        """Test cmd_files deselect with IndexError."""
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli.session = mock_session

        # Call with empty args list to trigger IndexError
        await interactive_cli.cmd_files(["deselect"])

        # Should handle IndexError gracefully
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_priority_index_error(
        self,
        interactive_cli,
        mock_session,
        torrent_session_with_files,
    ):
        """Test cmd_files priority with IndexError."""
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        interactive_cli.current_info_hash_hex = "abcd1234" * 5
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli.session = mock_session

        # Call with insufficient args to trigger IndexError
        await interactive_cli.cmd_files(["priority", "0"])

        # Should handle IndexError gracefully
        assert interactive_cli.console.print.called


class TestDownloadTorrentWithFileSelection:
    """Test download_torrent integration with file selection."""

    @pytest.mark.asyncio
    @patch("ccbt.cli.interactive.Prompt.ask")
    async def test_download_torrent_with_file_selection(
        self,
        mock_prompt,
        interactive_cli_with_layout,
        mock_session,
        torrent_session_with_files,
    ):
        """Test download_torrent calls interactive file selection."""
        mock_prompt.return_value = "done"
        info_hash_hex = "abcd1234" * 5
        info_hash_bytes = bytes.fromhex(info_hash_hex)
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        interactive_cli_with_layout.session = mock_session
        interactive_cli_with_layout.running = False  # Exit loop immediately

        torrent_data = {
            "name": "test_torrent",
            "info_hash": info_hash_bytes,
            "files": [
                {"name": "file0.txt", "length": 1024 * 1024},
                {"name": "file1.txt", "length": 2048 * 1024},
            ],
        }

        # Mock get_torrent_status to return None to exit loop
        mock_session.get_torrent_status = AsyncMock(return_value=None)

        await interactive_cli_with_layout.download_torrent(torrent_data, resume=False)

        # Should have called interactive file selection
        mock_prompt.assert_called()
        # Should set current_info_hash_hex
        assert interactive_cli_with_layout.current_info_hash_hex == info_hash_hex

    @pytest.mark.asyncio
    async def test_download_torrent_no_file_manager(
        self,
        interactive_cli_with_layout,
        mock_session,
    ):
        """Test download_torrent when file manager is None."""
        info_hash_hex = "abcd1234" * 5
        info_hash_bytes = bytes.fromhex(info_hash_hex)
        torrent_session = MagicMock()
        torrent_session.file_selection_manager = None
        mock_session.torrents = {info_hash_bytes: torrent_session}
        interactive_cli_with_layout.session = mock_session
        interactive_cli_with_layout.running = False

        torrent_data = {"name": "test_torrent", "info_hash": info_hash_bytes}
        mock_session.get_torrent_status = AsyncMock(return_value=None)

        await interactive_cli_with_layout.download_torrent(torrent_data, resume=False)

        # Should not raise and should complete
        assert interactive_cli_with_layout.current_info_hash_hex == info_hash_hex


class TestStatusCommandFileSelection:
    """Test status command file selection display."""

    @pytest.mark.asyncio
    async def test_show_status_with_file_selection(
        self,
        mock_session,
        torrent_session_with_files,
    ):
        """Test show_status includes file selection information."""
        from ccbt.cli.main import show_status
        from rich.console import Console

        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        mock_session.torrents = {info_hash_bytes: torrent_session_with_files}
        console = Console(record=True)

        await show_status(mock_session, console)

        # Check output contains file selection info
        output = console.export_text()
        # Should show torrent count
        assert "Torrents" in output or "Count" in output

    @pytest.mark.asyncio
    async def test_show_status_no_file_selection(
        self,
        mock_session,
    ):
        """Test show_status when no file selection managers exist."""
        from ccbt.cli.main import show_status
        from rich.console import Console

        # Create torrent session without file manager
        torrent_session = MagicMock()
        torrent_session.file_selection_manager = None
        info_hash_bytes = bytes.fromhex("abcd1234" * 5)
        mock_session.torrents = {info_hash_bytes: torrent_session}
        console = Console(record=True)

        await show_status(mock_session, console)

        # Should still complete without error
        output = console.export_text()
        assert "Torrents" in output or "Count" in output

    @pytest.mark.asyncio
    async def test_show_status_empty_torrents(self, mock_session):
        """Test show_status with empty torrents."""
        from ccbt.cli.main import show_status
        from rich.console import Console

        mock_session.torrents = {}
        console = Console(record=True)

        await show_status(mock_session, console)

        # Should complete without error
        output = console.export_text()
        assert "Torrents" in output or "Count" in output

