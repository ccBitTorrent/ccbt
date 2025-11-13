"""Comprehensive tests for CLI Proxy commands - missing coverage.

Covers:
- proxy_set: No config file path (line 101)
- proxy_set: Exception handling (lines 116-118)
- proxy_test: Success with stats (lines 154-163)
- proxy_test: ProxyError handling (lines 166-167)
- proxy_status: Statistics display (lines 214-229)
- proxy_disable: No config file (line 252)
- proxy_disable: Exception handling (lines 258-260)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner

cli_proxy_commands = __import__("ccbt.cli.proxy_commands", fromlist=["proxy"])

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run a coroutine to completion without touching global loop."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestProxySetEdgeCases:
    """Tests for proxy_set command edge cases."""

    def test_proxy_set_without_config_file(self, monkeypatch, tmp_path):
        """Test proxy_set without config file (line 101)."""
        runner = CliRunner()

        mock_proxy_config = SimpleNamespace(
            enable_proxy=False,
            proxy_host=None,
            proxy_port=None,
            proxy_type="http",
            proxy_username=None,
            proxy_password=None,
            proxy_for_trackers=True,
            proxy_for_peers=False,
            proxy_for_webseeds=True,
            proxy_bypass_list=[],
        )

        mock_config = SimpleNamespace(proxy=mock_proxy_config)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = None  # No config file

        monkeypatch.setattr(
            cli_proxy_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(
            cli_proxy_commands.proxy,
            ["set", "--host", "proxy.example.com", "--port", "8080"],
        )
        assert result.exit_code == 0
        assert "configuration not persisted" in result.output
        assert mock_proxy_config.enable_proxy is True

    def test_proxy_set_exception_handling(self, monkeypatch):
        """Test proxy_set exception handling (lines 116-118)."""
        runner = CliRunner()

        def _raise_error():
            raise Exception("Test error")

        monkeypatch.setattr(cli_proxy_commands, "ConfigManager", _raise_error)

        result = runner.invoke(
            cli_proxy_commands.proxy,
            ["set", "--host", "proxy.example.com", "--port", "8080"],
        )
        assert result.exit_code != 0
        assert "Failed to set proxy configuration" in result.output


class TestProxyTestComprehensive:
    """Tests for proxy_test command comprehensive coverage."""

    def test_proxy_test_success_with_stats(self, monkeypatch):
        """Test proxy_test success with statistics (lines 154-163)."""
        runner = CliRunner()

        mock_proxy_config = SimpleNamespace(
            enable_proxy=True,
            proxy_host="proxy.example.com",
            proxy_port=8080,
            proxy_type="http",
            proxy_username=None,
            proxy_password=None,
        )

        mock_config = SimpleNamespace(proxy=mock_proxy_config)

        mock_proxy_client = MagicMock()
        mock_proxy_client.test_connection = AsyncMock(return_value=True)
        mock_proxy_client.get_stats = MagicMock(
            return_value=SimpleNamespace(
                connections_total=10,
                connections_successful=8,
                connections_failed=2,
                auth_failures=1,
            )
        )

        monkeypatch.setattr(cli_proxy_commands, "get_config", lambda: mock_config)
        monkeypatch.setattr(
            cli_proxy_commands, "ProxyClient", lambda: mock_proxy_client
        )
        monkeypatch.setattr(cli_proxy_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_proxy_commands.proxy, ["test"])
        assert result.exit_code == 0
        assert "Proxy connection test successful" in result.output
        assert "Total connections" in result.output
        assert "Successful" in result.output
        assert "Failed" in result.output
        assert "Auth failures" in result.output

    def test_proxy_test_proxy_error(self, monkeypatch):
        """Test proxy_test with ProxyError (lines 165-167)."""
        runner = CliRunner()

        from ccbt.proxy.exceptions import ProxyError

        mock_proxy_config = SimpleNamespace(
            enable_proxy=True,
            proxy_host="proxy.example.com",
            proxy_port=8080,
            proxy_type="http",
            proxy_username=None,
            proxy_password=None,
        )

        mock_config = SimpleNamespace(proxy=mock_proxy_config)

        mock_proxy_client = MagicMock()
        mock_proxy_client.test_connection = AsyncMock(
            side_effect=ProxyError("Connection failed")
        )

        monkeypatch.setattr(cli_proxy_commands, "get_config", lambda: mock_config)
        monkeypatch.setattr(
            cli_proxy_commands, "ProxyClient", lambda: mock_proxy_client
        )
        monkeypatch.setattr(cli_proxy_commands.asyncio, "run", _run_coro_locally)

        result = runner.invoke(cli_proxy_commands.proxy, ["test"])
        assert result.exit_code != 0
        assert "Proxy error" in result.output


class TestProxyStatusComprehensive:
    """Tests for proxy_status command comprehensive coverage."""

    def test_proxy_status_with_statistics(self, monkeypatch):
        """Test proxy_status with statistics display (lines 214-229)."""
        runner = CliRunner()

        mock_proxy_config = SimpleNamespace(
            enable_proxy=True,
            proxy_type="http",
            proxy_host="proxy.example.com",
            proxy_port=8080,
            proxy_username="user",
            proxy_password="pass",
            proxy_for_trackers=True,
            proxy_for_peers=False,
            proxy_for_webseeds=True,
            proxy_bypass_list=["localhost"],
        )

        mock_config = SimpleNamespace(proxy=mock_proxy_config)

        mock_proxy_client = MagicMock()
        mock_proxy_client.get_stats = MagicMock(
            return_value=SimpleNamespace(
                connections_total=100,
                connections_successful=95,
                connections_failed=5,
                auth_failures=2,
                timeouts=3,
                bytes_sent=1000000,
                bytes_received=5000000,
            )
        )

        monkeypatch.setattr(cli_proxy_commands, "get_config", lambda: mock_config)
        monkeypatch.setattr(
            cli_proxy_commands, "ProxyClient", lambda: mock_proxy_client
        )

        result = runner.invoke(cli_proxy_commands.proxy, ["status"])
        assert result.exit_code == 0
        assert "Proxy Statistics" in result.output
        assert "Total Connections" in result.output
        assert "Successful" in result.output
        assert "Failed" in result.output
        assert "Auth Failures" in result.output
        assert "Timeouts" in result.output
        assert "Bytes Sent" in result.output
        assert "Bytes Received" in result.output


class TestProxyDisableComprehensive:
    """Tests for proxy_disable command comprehensive coverage."""

    def test_proxy_disable_without_config_file(self, monkeypatch):
        """Test proxy_disable without config file (line 252)."""
        runner = CliRunner()

        mock_proxy_config = SimpleNamespace(enable_proxy=True)

        mock_config = SimpleNamespace(proxy=mock_proxy_config)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = None  # No config file

        monkeypatch.setattr(
            cli_proxy_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(cli_proxy_commands.proxy, ["disable"])
        assert result.exit_code == 0
        assert "configuration not persisted" in result.output
        assert mock_proxy_config.enable_proxy is False

    def test_proxy_disable_exception_handling(self, monkeypatch):
        """Test proxy_disable exception handling (lines 258-260)."""
        runner = CliRunner()

        def _raise_error():
            raise Exception("Test error")

        monkeypatch.setattr(cli_proxy_commands, "ConfigManager", _raise_error)

        result = runner.invoke(cli_proxy_commands.proxy, ["disable"])
        assert result.exit_code != 0
        assert "Failed to disable proxy" in result.output

