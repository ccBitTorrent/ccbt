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
import ipaddress
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner

cli_nat_commands = __import__("ccbt.cli.nat_commands", fromlist=["nat"])

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

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": cfg})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock(config=cfg))
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "NAT manager not initialized" in result.output
        assert "Auto-map ports" in result.output

    def test_nat_status_with_mappings(self, monkeypatch):
        """Test NAT status with active mappings (lines 44-85)."""
        runner = CliRunner()

        mock_mapping = SimpleNamespace(
            protocol="tcp",
            internal_port=6881,
            external_port=6881,
            protocol_source="natpmp",
            expires_at="2024-12-31 23:59:59",
        )

        mock_port_mapping_manager = MagicMock()
        mock_port_mapping_manager.get_all_mappings = AsyncMock(return_value=[mock_mapping])

        mock_nat_manager = MagicMock()
        mock_nat_manager.get_status = AsyncMock(
            return_value={
                "active_protocol": "natpmp",
                "external_ip": "203.0.113.1",
                "mappings": [
                    {
                        "protocol": "tcp",
                        "internal_port": 6881,
                        "external_port": 6881,
                        "source": "natpmp",
                        "expires_at": "2024-12-31 23:59:59",
                    }
                ],
            }
        )
        mock_nat_manager.port_mapping_manager = mock_port_mapping_manager

        mock_session = AsyncMock()
        mock_session.nat_manager = mock_nat_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "NAT Traversal Status" in result.output
        assert "natpmp" in result.output.lower() or "NAT-PMP" in result.output

    def test_nat_status_without_protocol(self, monkeypatch):
        """Test NAT status without active protocol (lines 50-55)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.get_status = AsyncMock(
            return_value={
                "active_protocol": None,
                "external_ip": None,
                "mappings": [],
            }
        )

        mock_session = AsyncMock()
        mock_session.nat_manager = mock_nat_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "not discovered" in result.output.lower() or "None" in result.output

    def test_nat_status_without_external_ip(self, monkeypatch):
        """Test NAT status without external IP (lines 58-61)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.get_status = AsyncMock(
            return_value={
                "active_protocol": "upnp",
                "external_ip": None,
                "mappings": [],
            }
        )

        mock_session = AsyncMock()
        mock_session.nat_manager = mock_nat_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "External IP" in result.output or "Not available" in result.output

    def test_nat_status_with_permanent_mapping(self, monkeypatch):
        """Test NAT status with permanent mapping (line 75)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.get_status = AsyncMock(
            return_value={
                "active_protocol": "natpmp",
                "external_ip": "203.0.113.1",
                "mappings": [
                    {
                        "protocol": "tcp",
                        "internal_port": 6881,
                        "external_port": 6881,
                        "source": "natpmp",
                        "expires_at": None,  # Permanent mapping
                    }
                ],
            }
        )

        mock_session = AsyncMock()
        mock_session.nat_manager = mock_nat_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "Permanent" in result.output or "No active port mappings" in result.output

    def test_nat_status_exception_handling(self, monkeypatch):
        """Test NAT status exception handling (lines 94-96)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.get_status = AsyncMock(side_effect=Exception("Test error"))

        mock_session = AsyncMock()
        mock_session.nat_manager = mock_nat_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["status"], obj=ctx.obj)
        assert result.exit_code != 0
        assert "Error" in result.output


class TestNATDiscover:
    """Tests for NAT discover command (lines 103-150)."""

    def test_nat_discover_success(self, monkeypatch):
        """Test NAT discover success (lines 128-138)."""
        runner = CliRunner()

        cfg = SimpleNamespace(
            nat=SimpleNamespace(
                enable_nat_pmp=True,
                enable_upnp=True,
            )
        )

        mock_nat_manager = MagicMock()
        mock_nat_manager.discover = AsyncMock(return_value=True)
        mock_nat_manager.active_protocol = "natpmp"
        mock_nat_manager.get_external_ip = AsyncMock(
            return_value=ipaddress.IPv4Address("203.0.113.1")
        )

        mock_session = AsyncMock()
        mock_session.nat_manager = None  # Will be created
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        # Mock NATManager creation - patch in ccbt.nat.manager module
        monkeypatch.setattr(
            "ccbt.nat.manager.NATManager", lambda config: mock_nat_manager
        )

        ctx = SimpleNamespace(obj={"config": cfg})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock(config=cfg))
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["discover"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "Discovery successful" in result.output or "✓" in result.output

    def test_nat_discover_failure(self, monkeypatch):
        """Test NAT discover failure (lines 139-141)."""
        runner = CliRunner()

        cfg = SimpleNamespace(
            nat=SimpleNamespace(
                enable_nat_pmp=True,
                enable_upnp=True,
            )
        )

        mock_nat_manager = MagicMock()
        mock_nat_manager.discover = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        # Mock NATManager creation - patch in ccbt.nat.manager module
        monkeypatch.setattr(
            "ccbt.nat.manager.NATManager", lambda config: mock_nat_manager
        )

        ctx = SimpleNamespace(obj={"config": cfg})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock(config=cfg))
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["discover"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "No NAT devices discovered" in result.output or "✗" in result.output

    def test_nat_discover_exception_handling(self, monkeypatch):
        """Test NAT discover exception handling (lines 148-150)."""
        runner = CliRunner()

        cfg = SimpleNamespace(
            nat=SimpleNamespace(
                enable_nat_pmp=True,
                enable_upnp=True,
            )
        )

        mock_nat_manager = MagicMock()
        mock_nat_manager.discover = AsyncMock(side_effect=Exception("Test error"))

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        # Mock NATManager creation - patch in ccbt.nat.manager module
        monkeypatch.setattr(
            "ccbt.nat.manager.NATManager", lambda config: mock_nat_manager
        )

        ctx = SimpleNamespace(obj={"config": cfg})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock(config=cfg))
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["discover"], obj=ctx.obj)
        assert result.exit_code != 0
        assert "Error" in result.output


class TestNATMap:
    """Tests for NAT map command (lines 167-216)."""

    def test_nat_map_success(self, monkeypatch):
        """Test NAT map success (lines 197-205)."""
        runner = CliRunner()

        mock_mapping = SimpleNamespace(
            internal_port=6881,
            external_port=6881,
            protocol="tcp",
            protocol_source="natpmp",
        )

        mock_nat_manager = MagicMock()
        mock_nat_manager.active_protocol = "natpmp"
        mock_nat_manager.discover = AsyncMock()
        mock_nat_manager.map_port = AsyncMock(return_value=mock_mapping)
        mock_nat_manager.start = AsyncMock()

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        # Mock NATManager creation - patch in ccbt.nat.manager module
        monkeypatch.setattr(
            "ccbt.nat.manager.NATManager", lambda config: mock_nat_manager
        )

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["map", "--port", "6881", "--protocol", "tcp"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Port mapping successful" in result.output or "✓" in result.output

    def test_nat_map_no_protocol(self, monkeypatch):
        """Test NAT map with no protocol available (lines 186-194)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.active_protocol = None
        mock_nat_manager.discover = AsyncMock(return_value=False)
        mock_nat_manager.start = AsyncMock()

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        # Mock NATManager creation - patch in ccbt.nat.manager module
        monkeypatch.setattr(
            "ccbt.nat.manager.NATManager", lambda config: mock_nat_manager
        )

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["map", "--port", "6881"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "No NAT protocol available" in result.output or "Cannot map port" in result.output

    def test_nat_map_failure(self, monkeypatch):
        """Test NAT map failure (lines 206-207)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.active_protocol = "upnp"
        mock_nat_manager.discover = AsyncMock()
        mock_nat_manager.map_port = AsyncMock(return_value=None)
        mock_nat_manager.start = AsyncMock()

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        # Mock NATManager creation - patch in ccbt.nat.manager module
        monkeypatch.setattr(
            "ccbt.nat.manager.NATManager", lambda config: mock_nat_manager
        )

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["map", "--port", "6881"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Port mapping failed" in result.output or "✗" in result.output

    def test_nat_map_exception_handling(self, monkeypatch):
        """Test NAT map exception handling (lines 214-216)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.active_protocol = "natpmp"
        mock_nat_manager.discover = AsyncMock()
        mock_nat_manager.map_port = AsyncMock(side_effect=Exception("Test error"))
        mock_nat_manager.start = AsyncMock()

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        # Mock NATManager creation - patch in ccbt.nat.manager module
        monkeypatch.setattr(
            "ccbt.nat.manager.NATManager", lambda config: mock_nat_manager
        )

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
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

        mock_nat_manager = MagicMock()
        mock_nat_manager.unmap_port = AsyncMock(return_value=True)

        mock_session = AsyncMock()
        mock_session.nat_manager = mock_nat_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["unmap", "--port", "6881", "--protocol", "tcp"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Port mapping removed" in result.output or "✓" in result.output

    def test_nat_unmap_without_manager(self, monkeypatch):
        """Test NAT unmap without manager (lines 240-242)."""
        runner = CliRunner()

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["unmap", "--port", "6881"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "NAT manager not initialized" in result.output

    def test_nat_unmap_failure(self, monkeypatch):
        """Test NAT unmap failure (lines 252-253)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.unmap_port = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.nat_manager = mock_nat_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(
            cli_nat_commands.nat, ["unmap", "--port", "6881"], obj=ctx.obj
        )
        assert result.exit_code == 0
        assert "Failed to remove port mapping" in result.output or "✗" in result.output

    def test_nat_unmap_exception_handling(self, monkeypatch):
        """Test NAT unmap exception handling (lines 260-262)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.unmap_port = AsyncMock(side_effect=Exception("Test error"))

        mock_session = AsyncMock()
        mock_session.nat_manager = mock_nat_manager
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
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

        mock_nat_manager = MagicMock()
        mock_nat_manager.active_protocol = "natpmp"
        mock_nat_manager.get_external_ip = AsyncMock(
            return_value=ipaddress.IPv4Address("203.0.113.1")
        )
        mock_nat_manager.start = AsyncMock()

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        # Mock NATManager creation - patch in ccbt.nat.manager module
        monkeypatch.setattr(
            "ccbt.nat.manager.NATManager", lambda config: mock_nat_manager
        )

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["external-ip"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "203.0.113.1" in result.output or "External IP" in result.output

    def test_nat_external_ip_not_available(self, monkeypatch):
        """Test NAT external-ip not available (lines 295-299)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.active_protocol = None
        mock_nat_manager.get_external_ip = AsyncMock(return_value=None)
        mock_nat_manager.start = AsyncMock()

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        # Mock NATManager creation - patch in ccbt.nat.manager module
        monkeypatch.setattr(
            "ccbt.nat.manager.NATManager", lambda config: mock_nat_manager
        )

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["external-ip"], obj=ctx.obj)
        assert result.exit_code == 0
        assert "External IP not available" in result.output or "not available" in result.output.lower()

    def test_nat_external_ip_exception_handling(self, monkeypatch):
        """Test NAT external-ip exception handling (lines 306-308)."""
        runner = CliRunner()

        mock_nat_manager = MagicMock()
        mock_nat_manager.get_external_ip = AsyncMock(side_effect=Exception("Test error"))
        mock_nat_manager.start = AsyncMock()

        mock_session = AsyncMock()
        mock_session.nat_manager = None
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()

        # Mock NATManager creation - patch in ccbt.nat.manager module
        monkeypatch.setattr(
            "ccbt.nat.manager.NATManager", lambda config: mock_nat_manager
        )

        ctx = SimpleNamespace(obj={"config": SimpleNamespace()})

        monkeypatch.setattr(
            cli_nat_commands, "ConfigManager", MagicMock(return_value=MagicMock())
        )
        monkeypatch.setattr(
            cli_nat_commands,
            "AsyncSessionManager",
            lambda *args, **kwargs: mock_session,
        )
        monkeypatch.setattr(cli_nat_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_nat_commands.nat, ["external-ip"], obj=ctx.obj)
        assert result.exit_code != 0
        assert "Error" in result.output

