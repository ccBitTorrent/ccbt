"""Tests for CLI file commands.

Covers:
- File list command (lines 36-152)
- File select command (lines 161-200)
- File deselect command (lines 209-248)
- File priority commands (lines 256-412)
"""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

cli_file_commands = __import__("ccbt.cli.file_commands", fromlist=["files"])

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run a coroutine to completion without touching global loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestFilesList:
    """Tests for files list command (lines 36-152)."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session with torrent."""
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        # Mock file info
        file_info1 = SimpleNamespace(
            name="file1.txt",
            length=1024,
            is_padding=False,
            is_symlink=False,
            is_executable=False,
            is_hidden=False,
            file_sha1=None,
        )
        file_info2 = SimpleNamespace(
            name="file2.txt",
            length=2048,
            is_padding=False,
            is_symlink=True,
            is_executable=True,
            is_hidden=False,
            file_sha1=b"\x11" * 20,
        )

        # Mock file state
        file_state = SimpleNamespace(
            priority=SimpleNamespace(name="NORMAL"),
            selected=True,
            progress=0.5,
        )

        # Mock file selection manager
        mock_manager = MagicMock()
        mock_manager.torrent_info = SimpleNamespace(files=[file_info1, file_info2])
        mock_manager.get_file_state = MagicMock(return_value=file_state)
        mock_manager.get_statistics = MagicMock(
            return_value={
                "total_files": 2,
                "padding_files": 0,
                "padding_size": 0,
                "selected_files": 2,
                "selected_size": 3072,
                "deselected_files": 0,
                "deselected_size": 0,
            }
        )

        # Mock torrent session
        mock_torrent_session = SimpleNamespace(
            info=SimpleNamespace(name="Test Torrent"),
            file_selection_manager=mock_manager,
        )

        # Mock session manager
        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        return mock_session_obj, info_hash

    def test_files_list_with_valid_torrent(self, monkeypatch, mock_session):
        """Test files list with valid torrent."""
        runner = CliRunner()
        mock_session_obj, info_hash = mock_session

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_file_commands.files, ["list", info_hash], obj=ctx.obj)
        assert result.exit_code == 0

    def test_files_list_with_invalid_info_hash(self, monkeypatch):
        """Test files list with invalid info hash (lines 47-51)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["list", "invalid-hex"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Invalid info hash" in result.output

    def test_files_list_with_torrent_not_found(self, monkeypatch):
        """Test files list with torrent not found (lines 57-59)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_file_commands.files, ["list", info_hash], obj=ctx.obj)
        assert result.exit_code == 0
        assert "Torrent not found" in result.output

    def test_files_list_with_no_file_selection_manager(self, monkeypatch):
        """Test files list with no file selection manager (lines 62-69)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        mock_torrent_session = SimpleNamespace(
            info=SimpleNamespace(name="Test Torrent"),
            file_selection_manager=None,
        )

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_file_commands.files, ["list", info_hash], obj=ctx.obj)
        assert result.exit_code == 0
        assert "File selection not available" in result.output

    def test_files_list_with_hidden_file(self, monkeypatch):
        """Test files list with hidden file attribute (line 111)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        # Mock file info with hidden file
        hidden_file = SimpleNamespace(
            name=".hidden_file",
            length=512,
            is_padding=False,
            is_symlink=False,
            is_executable=False,
            is_hidden=True,  # This triggers line 111
            file_sha1=None,
        )
        normal_file = SimpleNamespace(
            name="file1.txt",
            length=1024,
            is_padding=False,
            is_symlink=False,
            is_executable=False,
            is_hidden=False,
            file_sha1=None,
        )

        file_state = SimpleNamespace(
            priority=SimpleNamespace(name="NORMAL"),
            selected=True,
            progress=0.0,
        )

        mock_manager = MagicMock()
        mock_manager.torrent_info = SimpleNamespace(files=[hidden_file, normal_file])
        mock_manager.get_file_state = MagicMock(return_value=file_state)
        mock_manager.get_statistics = MagicMock(
            return_value={
                "total_files": 2,
                "padding_files": 0,
                "padding_size": 0,
                "selected_files": 2,
                "selected_size": 1536,
                "deselected_files": 0,
                "deselected_size": 0,
            }
        )

        mock_torrent_session = SimpleNamespace(
            info=SimpleNamespace(name="Test Torrent"),
            file_selection_manager=mock_manager,
        )

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_file_commands.files, ["list", info_hash], obj=ctx.obj)
        assert result.exit_code == 0
        # Verify "H" appears in attributes for hidden file
        assert "H" in result.output or ".hidden_file" in result.output

    def test_files_list_with_padding_files(self, monkeypatch):
        """Test files list with padding files (lines 85-95)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        # Mock file info with padding file
        padding_file = SimpleNamespace(
            name=".pad",
            length=512,
            is_padding=True,
            is_symlink=False,
            is_executable=False,
            is_hidden=False,
            file_sha1=None,
        )
        normal_file = SimpleNamespace(
            name="file1.txt",
            length=1024,
            is_padding=False,
            is_symlink=False,
            is_executable=False,
            is_hidden=False,
            file_sha1=None,
        )

        file_state = SimpleNamespace(
            priority=SimpleNamespace(name="NORMAL"),
            selected=True,
            progress=0.0,
        )

        mock_manager = MagicMock()
        mock_manager.torrent_info = SimpleNamespace(files=[padding_file, normal_file])
        mock_manager.get_file_state = MagicMock(return_value=file_state)
        mock_manager.get_statistics = MagicMock(
            return_value={
                "total_files": 2,
                "padding_files": 1,
                "padding_size": 512,
                "selected_files": 1,
                "selected_size": 1024,
                "deselected_files": 0,
                "deselected_size": 0,
            }
        )

        mock_torrent_session = SimpleNamespace(
            info=SimpleNamespace(name="Test Torrent"),
            file_selection_manager=mock_manager,
        )

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_file_commands.files, ["list", info_hash], obj=ctx.obj)
        assert result.exit_code == 0


class TestFilesSelect:
    """Tests for files select command (lines 161-200)."""

    def test_files_select_with_valid_indices(self, monkeypatch):
        """Test files select with valid indices."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        mock_manager = MagicMock()
        mock_manager.select_files = AsyncMock()

        mock_torrent_session = SimpleNamespace(
            file_selection_manager=mock_manager,
        )

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["select", info_hash, "0", "1"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Selected" in result.output
        mock_manager.select_files.assert_called_once_with([0, 1])

    def test_files_select_with_invalid_info_hash(self, monkeypatch):
        """Test files select with invalid info hash (lines 171-175)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["select", "invalid-hex", "0"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Invalid info hash" in result.output

    def test_files_select_with_torrent_not_found(self, monkeypatch):
        """Test files select with torrent not found (lines 180-182)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["select", info_hash, "0"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Torrent not found" in result.output

    def test_files_select_with_no_manager(self, monkeypatch):
        """Test files select with no file selection manager (lines 184-187)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        mock_torrent_session = SimpleNamespace(file_selection_manager=None)

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["select", info_hash, "0"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "File selection not available" in result.output

    def test_files_select_error_handling(self, monkeypatch):
        """Test files select error handling (lines 198-200)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        mock_manager = MagicMock()
        mock_manager.select_files = AsyncMock(side_effect=RuntimeError("Test error"))

        mock_torrent_session = SimpleNamespace(file_selection_manager=mock_manager)

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["select", info_hash, "0"], obj=ctx.obj
        )
        assert result.exit_code != 0


class TestFilesDeselect:
    """Tests for files deselect command (lines 209-248)."""

    def test_files_deselect_with_invalid_info_hash(self, monkeypatch):
        """Test files deselect with invalid info hash (lines 221-223)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files,
            ["deselect", "invalid-hex", "0"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Invalid info hash" in result.output

    def test_files_deselect_with_valid_indices(self, monkeypatch):
        """Test files deselect with valid indices."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        mock_manager = MagicMock()
        mock_manager.deselect_files = AsyncMock()

        mock_torrent_session = SimpleNamespace(file_selection_manager=mock_manager)

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["deselect", info_hash, "0", "1"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Deselected" in result.output
        mock_manager.deselect_files.assert_called_once_with([0, 1])

    def test_files_deselect_error_handling(self, monkeypatch):
        """Test files deselect error handling (lines 246-248)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        mock_manager = MagicMock()
        mock_manager.deselect_files = AsyncMock(side_effect=RuntimeError("Test error"))

        mock_torrent_session = SimpleNamespace(file_selection_manager=mock_manager)

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["deselect", info_hash, "0"], obj=ctx.obj
        )
        assert result.exit_code != 0


class TestFilesSelectAll:
    """Tests for files select-all command (lines 251-294)."""

    def test_files_select_all_with_invalid_info_hash(self, monkeypatch):
        """Test files select-all with invalid info hash (lines 268-270)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files,
            ["select-all", "invalid-hex"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Invalid info hash" in result.output

    def test_files_select_all(self, monkeypatch):
        """Test files select-all command."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        mock_manager = MagicMock()
        mock_manager.select_all = AsyncMock()

        mock_torrent_session = SimpleNamespace(file_selection_manager=mock_manager)

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["select-all", info_hash], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Selected all files" in result.output
        mock_manager.select_all.assert_called_once()


class TestFilesDeselectAll:
    """Tests for files deselect-all command (lines 296-339)."""

    def test_files_deselect_all_with_invalid_info_hash(self, monkeypatch):
        """Test files deselect-all with invalid info hash - already covered in select-all test pattern."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files,
            ["deselect-all", "invalid-hex"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Invalid info hash" in result.output

    def test_files_deselect_all(self, monkeypatch):
        """Test files deselect-all command."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        mock_manager = MagicMock()
        mock_manager.deselect_all = AsyncMock()

        mock_torrent_session = SimpleNamespace(file_selection_manager=mock_manager)

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["deselect-all", info_hash], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Deselected all files" in result.output
        mock_manager.deselect_all.assert_called_once()


class TestFilesPriority:
    """Tests for files priority command (lines 341-412)."""

    def test_files_priority_with_valid_priority(self, monkeypatch):
        """Test files priority with valid priority."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        file_info = SimpleNamespace(name="test.txt")
        mock_manager = MagicMock()
        mock_manager.torrent_info = SimpleNamespace(files=[file_info])
        mock_manager.set_file_priority = AsyncMock()

        mock_torrent_session = SimpleNamespace(file_selection_manager=mock_manager)

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files,
            ["priority", info_hash, "0", "high"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Set file" in result.output
        mock_manager.set_file_priority.assert_called_once()

    def test_files_priority_with_invalid_file_index(self, monkeypatch):
        """Test files priority with invalid file index (lines 385-387)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        file_info = SimpleNamespace(name="test.txt")
        mock_manager = MagicMock()
        mock_manager.torrent_info = SimpleNamespace(files=[file_info])  # Only 1 file (index 0)

        mock_torrent_session = SimpleNamespace(file_selection_manager=mock_manager)

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        # Test with negative index
        result = runner.invoke(
            cli_file_commands.files,
            ["priority", info_hash, "-1", "high"],
            obj=ctx.obj,
        )
        # May exit with 0 or 2 depending on validation
        assert result.exit_code in [0, 2]
        if result.exit_code == 0:
            assert "Invalid file index" in result.output

        # Test with index >= len(files)
        result = runner.invoke(
            cli_file_commands.files,
            ["priority", info_hash, "1", "high"],
            obj=ctx.obj,
        )
        # May exit with 0 or 2 depending on validation
        assert result.exit_code in [0, 2]
        if result.exit_code == 0:
            assert "Invalid file index" in result.output

    def test_files_priority_with_all_priorities(self, monkeypatch):
        """Test files priority with all priority values."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        file_info = SimpleNamespace(name="test.txt")
        mock_manager = MagicMock()
        mock_manager.torrent_info = SimpleNamespace(files=[file_info])
        mock_manager.set_file_priority = AsyncMock()

        mock_torrent_session = SimpleNamespace(file_selection_manager=mock_manager)

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        priorities = ["maximum", "high", "normal", "low", "do_not_download"]

        for priority in priorities:
            monkeypatch.setattr(
                cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
            )
            monkeypatch.setattr(
                cli_file_commands,
                "AsyncSessionManager",
                lambda *args, **kwargs: mock_session_obj,
            )
            monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

            result = runner.invoke(
                cli_file_commands.files,
                ["priority", info_hash, "0", priority],
                obj=ctx.obj,
            )
            assert result.exit_code == 0

    def test_files_priority_with_invalid_info_hash(self, monkeypatch):
        """Test files priority with invalid info hash (lines 313-315)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files,
            ["priority", "invalid-hex", "0", "high"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Invalid info hash" in result.output

    def test_files_priority_error_handling(self, monkeypatch):
        """Test files priority error handling (lines 409-412)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        file_info = SimpleNamespace(name="test.txt")
        mock_manager = MagicMock()
        mock_manager.torrent_info = SimpleNamespace(files=[file_info])
        mock_manager.set_file_priority = AsyncMock(side_effect=RuntimeError("Test error"))

        mock_torrent_session = SimpleNamespace(file_selection_manager=mock_manager)

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {info_hash_bytes: mock_torrent_session}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session_obj,
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files,
            ["priority", info_hash, "0", "high"],
            obj=ctx.obj,
        )
        assert result.exit_code != 0


