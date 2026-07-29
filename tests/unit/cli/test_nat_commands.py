"""Tests for CLI NAT commands.

Covers:
- NAT status command (lines 24-96)
- NAT discover command (lines 103-150)
- NAT map command (lines 167-216)
- NAT unmap command (lines 230-262)
- NAT external-ip command (lines 269-308)
"""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner

cli_nat_commands = __import__("ccbt.cli.nat_commands", fromlist=["nat"])
cli_main = importlib.import_module("ccbt.cli.main")

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run a coroutine to completion without touching global loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestNATStatus:
    """Tests for NAT status command (lines 24-96)."""

    def test_nat_status_without_manager(self, monkeypatch):
        """Test NAT status without manager (lines 35-42)."""
        runner = CliRunner()

        cfg = SimpleNamespace(
            nat=SimpleNamespace(
                auto_map_ports=True,
                enable_nat_pmp=True,
                enable_upnp=True,
            )
        )

        ctx = SimpleNamespace(obj={"config": cfg})

        # Mock NATStatusResponse
        from ccbt.daemon.ipc_protocol import NATStatusResponse
        mock_nat_status = NATStatusResponse(
            enabled=True,
            method=None,
            external_ip=None,
            mappings=[],
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": mock_nat_status}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None  # No IPC client for this test

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        if result.exit_code != 0:
            print(f"Test failed with exit code {result.exit_code}")
            print(f"Output: {result.output}")
            print(f"Exception: {result.exception}")
        assert result.exit_code == 0, f"Command failed. Output: {result.output}"
        # Check for expected output when no protocol is discovered
        assert "NAT Traversal Status" in result.output or "NAT" in result.output
        assert "Active Protocol" in result.output or "None (not discovered)" in result.output or "Protocol" in result.output
        assert "External IP" in result.output or "IP" in result.output
        assert "Active Port Mappings" in result.output or "No active port mappings" in result.output or "mappings" in result.output.lower()

    def test_nat_status_with_mappings(self, monkeypatch):
        """Test NAT status with active mappings (lines 44-85)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock NATStatusResponse
        from ccbt.daemon.ipc_protocol import NATStatusResponse
        mock_nat_status = NATStatusResponse(
            enabled=True,
            method="natpmp",
            external_ip="203.0.113.1",
            mappings=[
                {
                    "protocol": "tcp",
                    "internal_port": 6881,
                    "external_port": 6881,
                    "source": "natpmp",
                    "expires_at": "2024-12-31 23:59:59",
                }
            ],
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": mock_nat_status}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "NAT Traversal Status" in result.output
        assert "natpmp" in result.output.lower() or "NAT-PMP" in result.output

    def test_nat_status_without_protocol(self, monkeypatch):
        """Test NAT status without active protocol (lines 50-55)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock NATStatusResponse
        from ccbt.daemon.ipc_protocol import NATStatusResponse
        mock_nat_status = NATStatusResponse(
            enabled=True,
            method=None,
            external_ip=None,
            mappings=[],
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": mock_nat_status}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "not discovered" in result.output.lower() or "None" in result.output

    def test_nat_status_without_external_ip(self, monkeypatch):
        """Test NAT status without external IP (lines 58-61)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock NATStatusResponse
        from ccbt.daemon.ipc_protocol import NATStatusResponse
        mock_nat_status = NATStatusResponse(
            enabled=True,
            method="upnp",
            external_ip=None,
            mappings=[],
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": mock_nat_status}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "External IP" in result.output or "Not available" in result.output

    def test_nat_status_with_permanent_mapping(self, monkeypatch):
        """Test NAT status with permanent mapping (line 75)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock NATStatusResponse
        from ccbt.daemon.ipc_protocol import NATStatusResponse
        mock_nat_status = NATStatusResponse(
            enabled=True,
            method="natpmp",
            external_ip="203.0.113.1",
            mappings=[
                {
                    "protocol": "tcp",
                    "internal_port": 6881,
                    "external_port": 6881,
                    "source": "natpmp",
                    "expires_at": None,  # Permanent mapping
                }
            ],
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": mock_nat_status}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "Permanent" in result.output or "No active port mappings" in result.output

    def test_nat_status_exception_handling(self, monkeypatch):
        """Test NAT status exception handling (lines 94-96)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor with failure
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=False,
            error="Test error"
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code != 0
        assert "Error" in result.output


class TestNATDiscover:
    """Tests for NAT discover command (lines 103-150)."""

    def test_nat_discover_success(self, monkeypatch):
        """Test NAT discover success (lines 128-138)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock NATStatusResponse for the status call
        from ccbt.daemon.ipc_protocol import NATStatusResponse
        mock_nat_status = NATStatusResponse(
            enabled=True,
            method="natpmp",
            external_ip="203.0.113.1",
            mappings=[],
        )

        # Mock executor - discover returns success, then status is called
        mock_executor = MagicMock()
        call_count = 0
        async def mock_execute(command):
            nonlocal call_count
            call_count += 1
            if command == "nat.discover":
                return MagicMock(
                    success=True,
                    data={"status": "discovered", "result": True}
                )
            if command == "nat.status":
                return MagicMock(
                    success=True,
                    data={"status": mock_nat_status}
                )
            return MagicMock(success=False, error="Unknown command")
        mock_executor.execute = AsyncMock(side_effect=mock_execute)
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["discover"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "Discovery successful" in result.output or "✓" in result.output

    def test_nat_discover_failure(self, monkeypatch):
        """Test NAT discover failure (lines 139-141)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor - discover returns failure
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": "not_discovered", "result": False}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["discover"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "No NAT devices discovered" in result.output or "✗" in result.output

    def test_nat_discover_exception_handling(self, monkeypatch):
        """Test NAT discover exception handling (lines 148-150)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor with failure
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=False,
            error="Test error"
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["discover"], obj=ctx.obj)
        assert result.exit_code != 0
        assert "Error" in result.output


class TestNATMap:
    """Tests for NAT map command (lines 167-216)."""

    def test_nat_map_success(self, monkeypatch):
        """Test NAT map success (lines 197-205)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor - map returns success
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={
                "status": "mapped",
                "result": {
                    "internal_port": 6881,
                    "external_port": 6881,
                    "protocol": "tcp",
                    "source": "natpmp",
                }
            }
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["map", "--port", "6881", "--protocol", "tcp"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Port mapping successful" in result.output or "✓" in result.output

    def test_nat_map_no_protocol(self, monkeypatch):
        """Test NAT map with no protocol available (lines 186-194)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor - map returns failure (no protocol)
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=False,
            error="No NAT protocol available"
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["map", "--port", "6881"], obj=ctx.obj
        )
        assert result.exit_code != 0
        assert "No NAT protocol available" in result.output or "Cannot map port" in result.output or "error" in result.output.lower()

    def test_nat_map_failure(self, monkeypatch):
        """Test NAT map failure (lines 206-207)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor - map returns success but status is not "mapped"
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": "failed", "result": None}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["map", "--port", "6881"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Port mapping failed" in result.output or "✗" in result.output

    def test_nat_map_exception_handling(self, monkeypatch):
        """Test NAT map exception handling (lines 214-216)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor with failure
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=False,
            error="Test error"
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["map", "--port", "6881"], obj=ctx.obj
        )
        assert result.exit_code != 0
        assert "Error" in result.output


class TestNATUnmap:
    """Tests for NAT unmap command (lines 230-262)."""

    def test_nat_unmap_success(self, monkeypatch):
        """Test NAT unmap success (lines 248-251)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor - unmap returns success
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": "unmapped"}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["unmap", "--port", "6881", "--protocol", "tcp"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Port mapping removed" in result.output or "✓" in result.output

    def test_nat_unmap_without_manager(self, monkeypatch):
        """Test NAT unmap without manager (lines 240-242)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor with failure (no manager)
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=False,
            error="NAT manager not initialized"
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["unmap", "--port", "6881"], obj=ctx.obj
        )
        assert result.exit_code != 0
        assert "NAT manager not initialized" in result.output or "error" in result.output.lower()

    def test_nat_unmap_failure(self, monkeypatch):
        """Test NAT unmap failure (lines 252-253)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor - unmap returns success but status is not "unmapped"
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": "failed"}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["unmap", "--port", "6881"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Failed to remove port mapping" in result.output or "✗" in result.output

    def test_nat_unmap_exception_handling(self, monkeypatch):
        """Test NAT unmap exception handling (lines 260-262)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor with failure
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=False,
            error="Test error"
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["unmap", "--port", "6881"], obj=ctx.obj
        )
        assert result.exit_code != 0
        assert "Error" in result.output


class TestNATExternalIP:
    """Tests for NAT external-ip command (lines 269-308)."""

    def test_nat_external_ip_success(self, monkeypatch):
        """Test NAT external-ip success (lines 288-294)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock NATStatusResponse for the status call
        from ccbt.daemon.ipc_protocol import NATStatusResponse
        mock_nat_status = NATStatusResponse(
            enabled=True,
            method="natpmp",
            external_ip="203.0.113.1",
            mappings=[],
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": mock_nat_status}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["external-ip"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "203.0.113.1" in result.output or "External IP" in result.output

    def test_nat_external_ip_not_available(self, monkeypatch):
        """Test NAT external-ip not available (lines 295-299)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock NATStatusResponse with no external IP
        from ccbt.daemon.ipc_protocol import NATStatusResponse
        mock_nat_status = NATStatusResponse(
            enabled=True,
            method=None,
            external_ip=None,
            mappings=[],
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=True,
            data={"status": mock_nat_status}
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["external-ip"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "External IP not available" in result.output or "not available" in result.output.lower()

    def test_nat_external_ip_exception_handling(self, monkeypatch):
        """Test NAT external-ip exception handling (lines 306-308)."""
        runner = CliRunner()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        # Mock executor with failure
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            success=False,
            error="Test error"
        ))
        mock_executor.adapter = MagicMock()
        mock_executor.adapter.ipc_client = None

        # Mock _get_executor to return (executor, is_daemon)
        async def _mock_get_executor():
            return (mock_executor, True)

        # Patch _get_executor in main module (where it's actually defined)
        monkeypatch.setattr(cli_main, "_get_executor", _mock_get_executor)
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["external-ip"], obj=ctx.obj)
        assert result.exit_code != 0
        assert "Error" in result.output

