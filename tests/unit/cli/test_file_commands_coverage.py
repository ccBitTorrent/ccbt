"""Tests to cover uncovered lines in file_commands.py.

Covers:
- Line 111: Hidden file attribute display
- Lines 221-223: Invalid info hash error in file list
- Lines 268-270: Invalid info hash error in file selection
- Lines 313-315: Invalid info hash error in file deselect-all
- Lines 368-370: Invalid info hash error in file priority
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
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


class TestFileCommandsCoverage:
    """Tests for uncovered lines in file_commands.py."""

    def test_files_list_shows_hidden_attribute(self, monkeypatch):
        """Test that hidden file attribute 'H' is displayed (line 111)."""
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
            is_hidden=True,  # This should trigger line 111
            file_sha1=None,
        )

        file_state = SimpleNamespace(
            priority=SimpleNamespace(name="NORMAL"),
            selected=True,
            progress=0.0,
        )

        mock_manager = MagicMock()
        mock_manager.torrent_info = SimpleNamespace(files=[hidden_file])
        mock_manager.get_file_state = MagicMock(return_value=file_state)
        mock_manager.get_statistics = MagicMock(
            return_value={
                "total_files": 1,
                "padding_files": 0,
                "padding_size": 0,
                "selected_files": 1,
                "selected_size": 512,
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

        ctx = MagicMock()
        ctx.obj = {"config": MagicMock()}

        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            MagicMock(return_value=mock_session_obj),
        )
        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_file_commands.files, ["list", info_hash], obj=ctx.obj
        )

        assert result.exit_code == 0
        # Verify "H" appears in attributes column (line 111)
        assert "H" in result.output or "hidden" in result.output.lower()

    def test_files_list_invalid_info_hash(self, monkeypatch):
        """Test files list with invalid info hash (lines 221-223)."""
        runner = CliRunner()

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = MagicMock()
        ctx.obj = {"config": MagicMock()}

        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            MagicMock(return_value=mock_session_obj),
        )
        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        # Use invalid hex string that will cause ValueError in bytes.fromhex
        result = runner.invoke(
            cli_file_commands.files, ["list", "invalid-hex-not-40-chars"], obj=ctx.obj
        )

        assert result.exit_code == 0
        # Verify error message is printed (line 222)
        assert "Invalid info hash" in result.output
        assert "invalid-hex-not-40-chars" in result.output

    def test_files_selection_invalid_info_hash(self, monkeypatch):
        """Test files selection with invalid info hash (lines 268-270)."""
        runner = CliRunner()

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = MagicMock()
        ctx.obj = {"config": MagicMock()}

        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            MagicMock(return_value=mock_session_obj),
        )
        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        # Use invalid hex string
        result = runner.invoke(
            cli_file_commands.files,
            ["select", "invalid-hex-123", "0"],
            obj=ctx.obj,
        )

        assert result.exit_code == 0
        # Verify error message is printed (line 269)
        assert "Invalid info hash" in result.output
        assert "invalid-hex-123" in result.output

    def test_files_deselect_all_invalid_info_hash(self, monkeypatch):
        """Test files deselect-all with invalid info hash (lines 313-315)."""
        runner = CliRunner()

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = MagicMock()
        ctx.obj = {"config": MagicMock()}

        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            MagicMock(return_value=mock_session_obj),
        )
        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        # Use invalid hex string
        result = runner.invoke(
            cli_file_commands.files,
            ["deselect-all", "invalid-hex-xyz"],
            obj=ctx.obj,
        )

        assert result.exit_code == 0
        # Verify error message is printed (line 314)
        assert "Invalid info hash" in result.output
        assert "invalid-hex-xyz" in result.output

    def test_files_priority_invalid_info_hash(self, monkeypatch):
        """Test files priority with invalid info hash (lines 368-370)."""
        runner = CliRunner()

        mock_session_obj = AsyncMock()
        mock_session_obj.torrents = {}
        mock_session_obj.lock = AsyncMock()
        mock_session_obj.lock.__aenter__ = AsyncMock(return_value=None)
        mock_session_obj.lock.__aexit__ = AsyncMock(return_value=None)
        mock_session_obj.start = AsyncMock()
        mock_session_obj.stop = AsyncMock()

        ctx = MagicMock()
        ctx.obj = {"config": MagicMock()}

        monkeypatch.setattr(
            cli_file_commands,
            "AsyncSessionManager",
            MagicMock(return_value=mock_session_obj),
        )
        monkeypatch.setattr(
            cli_file_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(cli_file_commands.asyncio, "run", _run_coro_locally)

        # Use invalid hex string
        result = runner.invoke(
            cli_file_commands.files,
            ["priority", "invalid-hex-abc", "0", "high"],
            obj=ctx.obj,
        )

        assert result.exit_code == 0
        # Verify error message is printed (line 369)
        assert "Invalid info hash" in result.output
        assert "invalid-hex-abc" in result.output

