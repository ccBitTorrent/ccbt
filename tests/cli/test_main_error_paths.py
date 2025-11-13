"""Tests for CLI main error paths and config flags.

Covers error handling and configuration flag paths in ccbt/cli/main.py.
Target: Cover missing lines 88, 132, 188, 200, 202-203, 224, 394, 461-462, 472, 641, 718, 808, 842-852, 945, 1008, 1068-1071, 1079, 1112-1115, 1121, 1155-1158, 1169
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _make_mock_config():
    """Create a mock config object."""
    cfg = MagicMock()
    cfg.network = MagicMock()
    cfg.network.enable_ipv6 = False  # Start False, test enable
    cfg.discovery = MagicMock()
    cfg.discovery.enable_http_trackers = False  # Start False, test enable
    cfg.disk = MagicMock()
    cfg.disk.use_mmap = True  # Start True, test disable
    cfg.disk.sparse_files = True  # Start True, test disable
    cfg.disk.enable_io_uring = False
    return cfg


class TestConfigFlags:
    """Test configuration flag setting in override functions."""

    def test_enable_ipv6_flag(self):
        """Test enable_ipv6 flag setting (line 88)."""
        from ccbt.cli.main import _apply_network_overrides

        cfg = _make_mock_config()
        options = {"enable_ipv6": True}

        _apply_network_overrides(cfg, options)

        assert cfg.network.enable_ipv6 is True

    def test_enable_http_trackers_flag(self):
        """Test enable_http_trackers flag setting (line 132)."""
        from ccbt.cli.main import _apply_discovery_overrides

        cfg = _make_mock_config()
        options = {"enable_http_trackers": True}

        _apply_discovery_overrides(cfg, options)

        assert cfg.discovery.enable_http_trackers is True

    def test_no_mmap_flag(self):
        """Test no_mmap flag setting (line 188)."""
        from ccbt.cli.main import _apply_disk_overrides

        cfg = _make_mock_config()
        options = {"no_mmap": True}

        _apply_disk_overrides(cfg, options)

        assert cfg.disk.use_mmap is False

    def test_no_sparse_files_flag(self):
        """Test no_sparse_files flag setting (line 200)."""
        from ccbt.cli.main import _apply_disk_overrides

        cfg = _make_mock_config()
        options = {"no_sparse_files": True}

        _apply_disk_overrides(cfg, options)

        assert cfg.disk.sparse_files is False

    def test_enable_io_uring_with_exception(self):
        """Test enable_io_uring flag with exception handling (lines 202-203)."""
        from ccbt.cli.main import _apply_disk_overrides

        cfg = _make_mock_config()
        
        # Make setting enable_io_uring raise an AttributeError (platform-specific)
        def set_io_uring(value):
            raise AttributeError("enable_io_uring not available on this platform")
        
        type(cfg.disk).enable_io_uring = property(
            lambda self: False,
            set_io_uring
        )
        
        options = {"enable_io_uring": True}

        # Exception should be caught and logged
        _apply_disk_overrides(cfg, options)
        
        # Should not raise - exception is caught


class TestObservabilityOverrides:
    """Test observability override functions."""

    def test_disable_metrics_flag(self):
        """Test disable_metrics flag setting (line 224)."""
        from ccbt.cli.main import _apply_observability_overrides

        cfg = _make_mock_config()
        cfg.observability = MagicMock()
        cfg.observability.enable_metrics = True  # Start with True
        options = {"disable_metrics": True}

        _apply_observability_overrides(cfg, options)

        assert cfg.observability.enable_metrics is False


class TestErrorPaths:
    """Test error handling paths."""

    @patch("ccbt.cli.main.ConfigManager")
    def test_checkpoint_export_invalid_info_hash(self, mock_config_manager):
        """Test checkpoint export with invalid info_hash format (lines 1112-1115)."""
        from click.testing import CliRunner
        from ccbt.cli.main import cli

        # Setup mock config manager
        mock_cfg = MagicMock()
        mock_cfg.config.disk = MagicMock()
        mock_config_manager.return_value = mock_cfg

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["checkpoints", "export", "invalid_hex_string", "--format", "json", "--output", "/tmp/output"],
            catch_exceptions=False,
        )

        # Should catch ValueError for invalid hex format
        assert "Invalid info hash format" in result.output

    @patch("ccbt.cli.main.ConfigManager")
    def test_checkpoint_backup_invalid_info_hash(self, mock_config_manager):
        """Test checkpoint backup with invalid info_hash format (lines 1155-1158)."""
        from click.testing import CliRunner
        from ccbt.cli.main import cli

        # Setup mock config manager
        mock_cfg = MagicMock()
        mock_cfg.config.disk = MagicMock()
        mock_config_manager.return_value = mock_cfg

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["checkpoints", "backup", "invalid_hex_string", "--destination", "/tmp/backup"],
            catch_exceptions=False,
        )

        # Should catch ValueError for invalid hex format
        assert "Invalid info hash format" in result.output

    @patch("ccbt.cli.main.ConfigManager")
    def test_checkpoint_verify_invalid_info_hash(self, mock_config_manager):
        """Test checkpoint verify with invalid info_hash format (lines 1068-1071)."""
        from click.testing import CliRunner
        from ccbt.cli.main import cli

        # Setup mock config manager
        mock_cfg = MagicMock()
        mock_cfg.config.disk = MagicMock()
        mock_config_manager.return_value = mock_cfg

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["checkpoints", "verify", "invalid_hex_string"],
            catch_exceptions=False,
        )

        # Should catch ValueError for invalid hex format
        assert "Invalid info hash format" in result.output

    @patch("ccbt.cli.main.ConfigManager")
    def test_config_command_exception(self, mock_config_manager):
        """Test config command exception handling (lines 842-852)."""
        from click.testing import CliRunner
        from ccbt.cli.main import cli

        # Make ConfigManager raise an exception
        mock_config_manager.side_effect = Exception("Config error")

        runner = CliRunner()
        result = runner.invoke(cli, ["config"], catch_exceptions=False)

        # Exception should be caught and displayed
        assert "Error" in result.output or result.exit_code != 0

