"""Comprehensive tests for CLI queue commands covering missing edge cases.

Covers missing lines:
- Queue list: Empty queue, error handling (lines 43-80)
- Queue add: Queue manager not initialized, error handling (lines 104-127)
- Queue remove: Torrent not found, queue manager not initialized (lines 145-163)
- Queue priority: Torrent not found, queue manager not initialized (lines 185-207)
- Queue reorder: Failed move, queue manager not initialized (lines 226-246)
- Queue pause/resume: Torrent not found, queue manager not initialized (lines 264-318)
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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


class TestQueueListEdgeCases:
    """Tests for queue list edge cases."""

    def test_queue_list_empty_queue(self, monkeypatch):
        """Test queue list with empty queue (lines 43-72)."""
        runner = CliRunner()

        mock_queue_status = {
            "entries": [],
            "statistics": {
                "total_torrents": 0,
                "active_downloading": 0,
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
        assert "Statistics" in result.output or "Total:" in result.output

    def test_queue_list_exception_handling(self, monkeypatch):
        """Test queue list exception handling (lines 78-80)."""
        runner = CliRunner()

        mock_queue_manager = MagicMock()
        mock_queue_manager.get_queue_status = AsyncMock(side_effect=Exception("Test error"))

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
        assert result.exit_code != 0
        assert "Error" in result.output


class TestQueueAddEdgeCases:
    """Tests for queue add edge cases."""

    def test_queue_add_without_queue_manager(self, monkeypatch):
        """Test queue add without queue manager (lines 104-106)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

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

        result = runner.invoke(
            cli_queue_commands.queue,
            ["add", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Queue manager not initialized" in result.output

    def test_queue_add_with_entry_object(self, monkeypatch):
        """Test queue add with proper entry object (lines 111-119)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        # Create a mock entry object with queue_position attribute
        mock_entry = SimpleNamespace(queue_position=2)

        mock_queue_manager = MagicMock()
        mock_queue_manager.add_torrent = AsyncMock(return_value=mock_entry)

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
            ["add", info_hash, "--priority", "normal"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "position 2" in result.output or "Added" in result.output

    def test_queue_add_exception_handling(self, monkeypatch):
        """Test queue add exception handling (lines 125-127)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.add_torrent = AsyncMock(side_effect=Exception("Test error"))

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
            ["add", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code != 0
        assert "Error" in result.output


class TestQueueRemoveEdgeCases:
    """Tests for queue remove edge cases."""

    def test_queue_remove_without_queue_manager(self, monkeypatch):
        """Test queue remove without queue manager (lines 145-147)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

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

        result = runner.invoke(
            cli_queue_commands.queue,
            ["remove", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Queue manager not initialized" in result.output

    def test_queue_remove_torrent_not_found(self, monkeypatch):
        """Test queue remove with torrent not found (lines 150-155)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.remove_torrent = AsyncMock(return_value=False)

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
        assert "Torrent not found in queue" in result.output

    def test_queue_remove_exception_handling(self, monkeypatch):
        """Test queue remove exception handling (lines 161-163)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.remove_torrent = AsyncMock(side_effect=Exception("Test error"))

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
        assert result.exit_code != 0
        assert "Error" in result.output


class TestQueuePriorityEdgeCases:
    """Tests for queue priority edge cases."""

    def test_queue_priority_without_queue_manager(self, monkeypatch):
        """Test queue priority without queue manager (lines 185-187)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

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

        result = runner.invoke(
            cli_queue_commands.queue,
            ["priority", info_hash, "high"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Queue manager not initialized" in result.output

    def test_queue_priority_torrent_not_found(self, monkeypatch):
        """Test queue priority with torrent not found (lines 192-199)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.set_priority = AsyncMock(return_value=False)

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
            ["priority", info_hash, "high"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Torrent not found in queue" in result.output

    def test_queue_priority_exception_handling(self, monkeypatch):
        """Test queue priority exception handling (lines 205-207)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.set_priority = AsyncMock(side_effect=Exception("Test error"))

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
            ["priority", info_hash, "high"],
            obj=ctx.obj,
        )
        assert result.exit_code != 0
        assert "Error" in result.output


class TestQueueReorderEdgeCases:
    """Tests for queue reorder edge cases."""

    def test_queue_reorder_without_queue_manager(self, monkeypatch):
        """Test queue reorder without queue manager (lines 226-228)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

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

        result = runner.invoke(
            cli_queue_commands.queue,
            ["reorder", info_hash, "1"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Queue manager not initialized" in result.output

    def test_queue_reorder_failed(self, monkeypatch):
        """Test queue reorder with failed move (lines 231-238)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.reorder_torrent = AsyncMock(return_value=False)

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
            ["reorder", info_hash, "1"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Failed to move torrent" in result.output

    def test_queue_reorder_exception_handling(self, monkeypatch):
        """Test queue reorder exception handling (lines 244-246)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.reorder_torrent = AsyncMock(side_effect=Exception("Test error"))

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
            ["reorder", info_hash, "1"],
            obj=ctx.obj,
        )
        assert result.exit_code != 0
        assert "Error" in result.output


class TestQueuePauseResumeEdgeCases:
    """Tests for queue pause/resume edge cases."""

    def test_queue_pause_without_queue_manager(self, monkeypatch):
        """Test queue pause without queue manager (lines 264-266)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

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

        result = runner.invoke(
            cli_queue_commands.queue,
            ["pause", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Queue manager not initialized" in result.output

    def test_queue_pause_torrent_not_found(self, monkeypatch):
        """Test queue pause with torrent not found (lines 269-274)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.pause_torrent = AsyncMock(return_value=False)

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
        assert "Torrent not found" in result.output

    def test_queue_pause_exception_handling(self, monkeypatch):
        """Test queue pause exception handling (lines 280-282)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.pause_torrent = AsyncMock(side_effect=Exception("Test error"))

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
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_queue_resume_without_queue_manager(self, monkeypatch):
        """Test queue resume without queue manager (lines 300-302)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

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

        result = runner.invoke(
            cli_queue_commands.queue,
            ["resume", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Queue manager not initialized" in result.output

    def test_queue_resume_torrent_not_found(self, monkeypatch):
        """Test queue resume with torrent not found (lines 305-310)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.resume_torrent = AsyncMock(return_value=False)

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
        assert "Torrent not found" in result.output

    def test_queue_resume_exception_handling(self, monkeypatch):
        """Test queue resume exception handling (lines 316-318)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_queue_manager = MagicMock()
        mock_queue_manager.resume_torrent = AsyncMock(side_effect=Exception("Test error"))

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
        assert result.exit_code != 0
        assert "Error" in result.output

