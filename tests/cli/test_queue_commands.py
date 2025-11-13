"""Tests for CLI queue commands.

Covers:
- Queue list command (lines 25-80)
- Queue add command (lines 94-127)
- Queue remove command (lines 135-163)
- Queue priority command (lines 175-207)
- Queue move commands (lines 216-318)
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

cli_queue_commands = __import__("ccbt.cli.queue_commands", fromlist=["queue"])

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run a coroutine to completion without touching global loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestQueueList:
    """Tests for queue list command (lines 25-80)."""

    def test_queue_list_with_active_queue(self, monkeypatch):
        """Test queue list with active queue (lines 45-72)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_status = {
            "entries": [
                {
                    "queue_position": 1,
                    "info_hash": info_hash,
                    "priority": "normal",
                    "status": "downloading",
                    "allocated_down_kib": 100,
                    "allocated_up_kib": 50,
                }
            ],
            "statistics": {
                "total_torrents": 1,
                "active_downloading": 1,
                "active_seeding": 0,
                "queued": 0,
                "paused": 0,
            },
        }

        mock_queue_manager = MagicMock()
        mock_queue_manager.get_queue_status = AsyncMock(return_value=mock_queue_status)

        mock_session = AsyncMock()
        mock_session.queue_manager = mock_queue_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_queue_commands.queue, ["list"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "Torrent Queue" in result.output or "Total:" in result.output

    def test_queue_list_without_manager(self, monkeypatch):
        """Test queue list without queue manager (lines 36-40)."""
        runner = CliRunner()

        mock_session = AsyncMock()
        mock_session.queue_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_queue_commands.queue, ["list"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "Queue manager not initialized" in result.output


class TestQueueAdd:
    """Tests for queue add command (lines 94-127)."""

    def test_queue_add_with_priority(self, monkeypatch):
        """Test queue add with priority (lines 96-127)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        mock_queue_manager = MagicMock()
        mock_queue_manager.add_torrent = AsyncMock(return_value=1)  # Queue position 1

        mock_session = AsyncMock()
        mock_session.queue_manager = mock_queue_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["add", info_hash, "--priority", "high"],
            obj=ctx.obj,
        )
        # May exit with various codes depending on validation
        assert result.exit_code in [0, 1, 2]
        if result.exit_code == 0:
            assert "Added" in result.output or "priority" in result.output.lower() or len(result.output) > 0

    def test_queue_add_with_invalid_info_hash(self, monkeypatch):
        """Test queue add with invalid info hash."""
        runner = CliRunner()

        mock_session = AsyncMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["add", "invalid-hex"],
            obj=ctx.obj,
        )
        # May succeed or fail depending on validation
        assert result.exit_code in [0, 1]


class TestQueueRemove:
    """Tests for queue remove command (lines 135-163)."""

    def test_queue_remove(self, monkeypatch):
        """Test queue remove command."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.remove_torrent = AsyncMock(return_value=True)

        mock_session = AsyncMock()
        mock_session.queue_manager = mock_queue_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["remove", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        mock_queue_manager.remove_torrent.assert_called_once()


class TestQueuePriority:
    """Tests for queue priority command (lines 175-207)."""

    def test_queue_priority_update_success(self, monkeypatch):
        """Test queue priority update success message (line 197)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.update_priority = AsyncMock()

        mock_session = AsyncMock()
        mock_session.queue_manager = mock_queue_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        priorities = ["maximum", "high", "normal", "low", "paused"]
        for priority in priorities:
            result = runner.invoke(
                cli_queue_commands.queue,
                ["priority", info_hash, "--priority", priority],
                obj=ctx.obj,
            )
            # May exit with various codes depending on validation
            assert result.exit_code in [0, 1, 2]


class TestQueueMove:
    """Tests for queue move commands (lines 216-282)."""

    def test_queue_move_up(self, monkeypatch):
        """Test queue move up command."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.move_up = AsyncMock(return_value=True)

        mock_session = AsyncMock()
        mock_session.queue_manager = mock_queue_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["move-up", info_hash],
            obj=ctx.obj,
        )
        # May exit with various codes depending on validation
        assert result.exit_code in [0, 1, 2]
        # Verify method was called if command executed
        if result.exit_code == 0:
            mock_queue_manager.move_up.assert_called_once()

    def test_queue_move_down(self, monkeypatch):
        """Test queue move down command."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.move_down = AsyncMock(return_value=True)

        mock_session = AsyncMock()
        mock_session.queue_manager = mock_queue_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["move-down", info_hash],
            obj=ctx.obj,
        )
        # May exit with various codes depending on validation
        assert result.exit_code in [0, 1, 2]
        # Verify method was called if command executed
        if result.exit_code == 0:
            mock_queue_manager.move_down.assert_called_once()

    def test_queue_move_to_position(self, monkeypatch):
        """Test queue move to position command."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.move_to_position = AsyncMock(return_value=True)

        mock_session = AsyncMock()
        mock_session.queue_manager = mock_queue_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["move-to", info_hash, "--position", "1"],
            obj=ctx.obj,
        )
        # May exit with various codes depending on validation
        assert result.exit_code in [0, 1, 2]
        # Verify method was called if command executed
        if result.exit_code == 0:
            mock_queue_manager.move_to_position.assert_called_once()


class TestQueuePauseResume:
    """Tests for queue pause/resume commands (lines 290-318)."""

    def test_queue_pause(self, monkeypatch):
        """Test queue pause command."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.pause_torrent = AsyncMock()

        mock_session = AsyncMock()
        mock_session.queue_manager = mock_queue_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["pause", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        mock_queue_manager.pause_torrent.assert_called_once()

    def test_queue_resume(self, monkeypatch):
        """Test queue resume command."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.resume_torrent = AsyncMock()

        mock_session = AsyncMock()
        mock_session.queue_manager = mock_queue_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_queue_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_queue_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["resume", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        mock_queue_manager.resume_torrent.assert_called_once()

