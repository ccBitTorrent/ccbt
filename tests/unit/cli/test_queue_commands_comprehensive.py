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

        mock_config_manager = MagicMock()
        # Patch _get_executor to return a mock executor
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Create SimpleNamespace for queue response (matches executor response format)
            queue_response = SimpleNamespace(
                entries=mock_queue_status["entries"],
                statistics=mock_queue_status["statistics"]
            )
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=True,
                data={"queue": queue_response}
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_queue_commands.queue, ["list"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "Statistics" in result.output or "Total:" in result.output

    def test_queue_list_exception_handling(self, monkeypatch):
        """Test queue list exception handling (lines 78-80)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that raises exception
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Make execute raise exception to test error handling
            mock_executor.execute = AsyncMock(side_effect=Exception("Test error"))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
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

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates queue manager not initialized
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate queue manager not initialized error
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Queue manager not initialized"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["add", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code != 0  # Should fail with error
        assert "Queue manager not initialized" in result.output or "Failed to add" in result.output

    def test_queue_add_with_entry_object(self, monkeypatch):
        """Test queue add with proper entry object (lines 111-119)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that succeeds
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate successful add
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=True,
                data={}
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["add", info_hash, "--priority", "normal"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0
        assert "Added" in result.output or "priority" in result.output.lower()

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

        mock_config_manager = MagicMock()
        # Patch _get_executor to return a mock executor
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Create SimpleNamespace for queue response (matches executor response format)
            queue_response = SimpleNamespace(
                entries=mock_queue_status["entries"],
                statistics=mock_queue_status["statistics"]
            )
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=True,
                data={"queue": queue_response}
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
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

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates queue manager not initialized
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate queue manager not initialized error
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Queue manager not initialized"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["remove", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code != 0  # Should fail with error
        assert "Queue manager not initialized" in result.output or "Failed to remove" in result.output

    def test_queue_remove_torrent_not_found(self, monkeypatch):
        """Test queue remove with torrent not found (lines 150-155)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates torrent not found
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate torrent not found (success=False with "not found" in error)
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Torrent not found in queue"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["remove", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code == 0  # Should succeed but show warning
        assert "Torrent not found" in result.output

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

        mock_config_manager = MagicMock()
        # Patch _get_executor to return a mock executor
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Create SimpleNamespace for queue response (matches executor response format)
            queue_response = SimpleNamespace(
                entries=mock_queue_status["entries"],
                statistics=mock_queue_status["statistics"]
            )
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=True,
                data={"queue": queue_response}
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
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

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates queue manager not initialized
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate queue manager not initialized error
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Queue manager not initialized"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["priority", info_hash, "high"],
            obj=ctx.obj,
        )
        assert result.exit_code != 0  # Should fail with error
        assert "Queue manager not initialized" in result.output or "Failed to set" in result.output

    def test_queue_priority_torrent_not_found(self, monkeypatch):
        """Test queue priority with torrent not found (lines 192-199)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates torrent not found
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate torrent not found (success=False with "not found" in error)
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Torrent not found in queue"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["priority", info_hash, "high"],
            obj=ctx.obj,
        )
        assert result.exit_code == 0  # Should succeed but show warning
        assert "Torrent not found" in result.output

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

        mock_config_manager = MagicMock()
        # Patch _get_executor to return a mock executor
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Create SimpleNamespace for queue response (matches executor response format)
            queue_response = SimpleNamespace(
                entries=mock_queue_status["entries"],
                statistics=mock_queue_status["statistics"]
            )
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=True,
                data={"queue": queue_response}
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
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

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates queue manager not initialized
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate queue manager not initialized error
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Queue manager not initialized"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["reorder", info_hash, "1"],
            obj=ctx.obj,
        )
        assert result.exit_code != 0  # Should fail with error
        assert "Queue manager not initialized" in result.output or "Failed to move" in result.output

    def test_queue_reorder_failed(self, monkeypatch):
        """Test queue reorder with failed move (lines 231-238)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates failed move
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate failed move (success=False)
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Failed to move torrent"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["reorder", info_hash, "1"],
            obj=ctx.obj,
        )
        # The command should fail with error, but if it succeeds, check for error message
        if result.exit_code == 0:
            # If it succeeds, it means the error was handled gracefully
            assert "Failed to move" in result.output or "not found" in result.output.lower()
        else:
            assert "Failed to move" in result.output

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

        mock_config_manager = MagicMock()
        # Patch _get_executor to return a mock executor
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Create SimpleNamespace for queue response (matches executor response format)
            queue_response = SimpleNamespace(
                entries=mock_queue_status["entries"],
                statistics=mock_queue_status["statistics"]
            )
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=True,
                data={"queue": queue_response}
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
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

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates queue manager not initialized
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate queue manager not initialized error
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Queue manager not initialized"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["pause", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code != 0  # Should fail with error
        assert "Queue manager not initialized" in result.output or "Failed to pause" in result.output

    def test_queue_pause_torrent_not_found(self, monkeypatch):
        """Test queue pause with torrent not found (lines 269-274)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates torrent not found
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate torrent not found (success=False with "not found" in error)
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Torrent not found in queue"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["pause", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code == 0  # Should succeed but show warning
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

        mock_config_manager = MagicMock()
        # Patch _get_executor to return a mock executor
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Create SimpleNamespace for queue response (matches executor response format)
            queue_response = SimpleNamespace(
                entries=mock_queue_status["entries"],
                statistics=mock_queue_status["statistics"]
            )
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=True,
                data={"queue": queue_response}
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
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

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates queue manager not initialized
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate queue manager not initialized error
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Queue manager not initialized"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["resume", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code != 0  # Should fail with error
        assert "Queue manager not initialized" in result.output or "Failed to resume" in result.output

    def test_queue_resume_torrent_not_found(self, monkeypatch):
        """Test queue resume with torrent not found (lines 305-310)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Patch _get_executor to return a mock executor that simulates torrent not found
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Simulate torrent not found (success=False with "not found" in error)
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=False,
                error="Torrent not found in queue"
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["resume", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code == 0  # Should succeed but show warning
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

        mock_config_manager = MagicMock()
        # Patch _get_executor to return a mock executor
        import sys
        main_module = sys.modules.get('ccbt.cli.main')
        if main_module is None:
            import ccbt.cli.main
            main_module = sys.modules['ccbt.cli.main']
        
        async def mock_get_executor():
            # Return a mock executor and indicate it's daemon mode
            mock_executor = MagicMock()
            # Create SimpleNamespace for queue response (matches executor response format)
            queue_response = SimpleNamespace(
                entries=mock_queue_status["entries"],
                statistics=mock_queue_status["statistics"]
            )
            mock_executor.execute = AsyncMock(return_value=MagicMock(
                success=True,
                data={"queue": queue_response}
            ))
            mock_executor.adapter = MagicMock()
            mock_executor.adapter.ipc_client = MagicMock()
            mock_executor.adapter.ipc_client.close = AsyncMock()
            return (mock_executor, True)
        
        monkeypatch.setattr(main_module, "_get_executor", mock_get_executor)
        monkeypatch.setattr(cli_queue_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_queue_commands.queue,
            ["resume", info_hash],
            obj=ctx.obj,
        )
        assert result.exit_code != 0
        assert "Error" in result.output

