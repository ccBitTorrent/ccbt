"""Tests for CLI advanced commands (performance, security, recover, test)."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

pytestmark = [pytest.mark.unit, pytest.mark.cli]

from ccbt.cli.advanced_commands import performance, recover, security, test


class TestPerformanceCommand:
    """Test performance CLI command."""

    @patch("ccbt.cli.advanced_commands.get_config")
    def test_performance_analyze(self, mock_get_config):
        """Test performance --analyze."""
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.write_buffer_kib = 64
        config.disk.write_batch_kib = 32
        config.disk.use_mmap = True
        config.disk.direct_io = False
        config.disk.enable_io_uring = False
        mock_get_config.return_value = config
        
        runner = CliRunner()
        result = runner.invoke(performance, ["--analyze"])
        
        assert result.exit_code == 0
        assert "System & Config Analysis" in result.output
        assert "Python" in result.output
        assert "Platform" in result.output

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.get_config")
    def test_performance_benchmark(self, mock_get_config, mock_asyncio_run):
        """Test performance --benchmark."""
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.disk_queue_size = 100
        config.disk.mmap_cache_mb = 64
        mock_get_config.return_value = config
        
        mock_asyncio_run.return_value = {"write_mbps": 100.0, "read_mbps": 80.0}
        
        runner = CliRunner()
        result = runner.invoke(performance, ["--benchmark"])
        
        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()

    def test_performance_optimize(self):
        """Test performance --optimize."""
        runner = CliRunner()
        result = runner.invoke(performance, ["--optimize"])
        
        assert result.exit_code == 0
        assert "Suggested optimizations" in result.output
        assert "Increase --write-buffer-kib" in result.output

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.get_config")
    def test_performance_profile(self, mock_get_config, mock_asyncio_run):
        """Test performance --profile."""
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.disk_queue_size = 100
        config.disk.mmap_cache_mb = 64
        mock_get_config.return_value = config
        
        mock_asyncio_run.return_value = {"write_mbps": 100.0, "read_mbps": 80.0}
        
        runner = CliRunner()
        result = runner.invoke(performance, ["--profile"])
        
        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.get_config")
    def test_performance_all_flags(self, mock_get_config, mock_asyncio_run):
        """Test performance with all flags."""
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.disk_queue_size = 100
        config.disk.mmap_cache_mb = 64
        mock_get_config.return_value = config
        
        mock_asyncio_run.return_value = {"write_mbps": 100.0, "read_mbps": 80.0}
        
        runner = CliRunner()
        result = runner.invoke(performance, ["--analyze", "--optimize", "--benchmark", "--profile"])
        
        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()

    def test_performance_no_flags(self):
        """Test performance with no flags."""
        runner = CliRunner()
        result = runner.invoke(performance, [])
        
        assert result.exit_code == 0
        assert "No performance action specified" in result.output


class TestSecurityCommand:
    """Test security CLI command."""

    @patch("ccbt.cli.advanced_commands.get_config")
    def test_security_scan(self, mock_get_config):
        """Test security --scan."""
        config = MagicMock()
        config.security.validate_peers = False
        config.network.max_connections_per_peer = 8
        config.security.rate_limit_enabled = False
        config.network.global_down_kib = 0
        config.network.global_up_kib = 0
        mock_get_config.return_value = config
        
        runner = CliRunner()
        result = runner.invoke(security, ["--scan"])
        
        assert result.exit_code == 0
        assert "Performing basic configuration scan" in result.output
        assert "Found 3 potential issues" in result.output

    def test_security_validate(self):
        """Test security --validate."""
        runner = CliRunner()
        result = runner.invoke(security, ["--validate"])
        
        assert result.exit_code == 0
        assert "Peer validation hooks are enabled" in result.output

    def test_security_encrypt(self):
        """Test security --encrypt."""
        runner = CliRunner()
        result = runner.invoke(security, ["--encrypt"])
        
        assert result.exit_code == 0
        assert "Toggle encryption via" in result.output

    def test_security_rate_limit(self):
        """Test security --rate-limit."""
        runner = CliRunner()
        result = runner.invoke(security, ["--rate-limit"])
        
        assert result.exit_code == 0
        assert "Set --download-limit" in result.output

    def test_security_all_flags(self):
        """Test security with all flags."""
        runner = CliRunner()
        result = runner.invoke(security, ["--scan", "--validate", "--encrypt", "--rate-limit"])
        
        assert result.exit_code == 0
        assert "Performing basic configuration scan" in result.output
        assert "Peer validation hooks are enabled" in result.output
        assert "Toggle encryption via" in result.output
        assert "Set --download-limit" in result.output

    def test_security_no_flags(self):
        """Test security with no flags."""
        runner = CliRunner()
        result = runner.invoke(security, [])
        
        assert result.exit_code == 0
        assert "No security action specified" in result.output


class TestRecoverCommand:
    """Test recover CLI command."""

    @patch("ccbt.cli.advanced_commands.CheckpointManager")
    def test_recover_repair(self, mock_checkpoint_manager):
        """Test recover --repair."""
        mock_cm = MagicMock()
        mock_checkpoint_manager.return_value = mock_cm
        
        runner = CliRunner()
        result = runner.invoke(recover, ["1234567890123456789012345678901234567890", "--repair"])
        
        assert result.exit_code == 0
        assert "Automatic repair not implemented" in result.output

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.CheckpointManager")
    def test_recover_verify(self, mock_checkpoint_manager, mock_asyncio_run):
        """Test recover --verify."""
        mock_cm = MagicMock()
        mock_checkpoint_manager.return_value = mock_cm
        mock_asyncio_run.return_value = True
        
        runner = CliRunner()
        result = runner.invoke(recover, ["1234567890123456789012345678901234567890", "--verify"])
        
        assert result.exit_code == 0
        assert "Checkpoint valid" in result.output
        mock_asyncio_run.assert_called_once()

    @patch("ccbt.cli.advanced_commands.CheckpointManager")
    def test_recover_rehash(self, mock_checkpoint_manager):
        """Test recover --rehash."""
        mock_cm = MagicMock()
        mock_checkpoint_manager.return_value = mock_cm
        
        runner = CliRunner()
        result = runner.invoke(recover, ["1234567890123456789012345678901234567890", "--rehash"])
        
        assert result.exit_code == 0
        assert "Full rehash not implemented" in result.output

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.CheckpointManager")
    def test_recover_all_flags(self, mock_checkpoint_manager, mock_asyncio_run):
        """Test recover with all flags."""
        mock_cm = MagicMock()
        mock_checkpoint_manager.return_value = mock_cm
        mock_asyncio_run.return_value = True
        
        runner = CliRunner()
        result = runner.invoke(recover, ["1234567890123456789012345678901234567890", "--repair", "--verify", "--rehash"])
        
        assert result.exit_code == 0
        assert "Checkpoint valid" in result.output
        assert "Automatic repair not implemented" in result.output
        assert "Full rehash not implemented" in result.output
        mock_asyncio_run.assert_called_once()

    @patch("ccbt.cli.advanced_commands.CheckpointManager")
    def test_recover_no_flags(self, mock_checkpoint_manager):
        """Test recover with no flags."""
        mock_cm = MagicMock()
        mock_checkpoint_manager.return_value = mock_cm
        
        runner = CliRunner()
        result = runner.invoke(recover, ["1234567890123456789012345678901234567890"])
        
        assert result.exit_code == 0
        assert "No recover action specified" in result.output

    def test_recover_invalid_hash(self):
        """Test recover with invalid info hash."""
        runner = CliRunner()
        result = runner.invoke(recover, ["invalid_hash"])
        
        assert result.exit_code == 0
        assert "Invalid info hash format" in result.output


class TestTestCommand:
    """Test test CLI command."""

    @patch("ccbt.cli.advanced_commands.subprocess.run")
    def test_test_unit(self, mock_subprocess_run):
        """Test test --unit."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        runner = CliRunner()
        result = runner.invoke(test, ["--unit"])
        
        assert result.exit_code == 0
        mock_subprocess_run.assert_called_once()

    @patch("ccbt.cli.advanced_commands.subprocess.run")
    def test_test_integration(self, mock_subprocess_run):
        """Test test --integration."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        runner = CliRunner()
        result = runner.invoke(test, ["--integration"])
        
        assert result.exit_code == 0
        mock_subprocess_run.assert_called_once()

    @patch("ccbt.cli.advanced_commands.subprocess.run")
    def test_test_performance(self, mock_subprocess_run):
        """Test test --performance."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        runner = CliRunner()
        result = runner.invoke(test, ["--performance"])
        
        assert result.exit_code == 0
        mock_subprocess_run.assert_called_once()

    @patch("ccbt.cli.advanced_commands.subprocess.run")
    def test_test_security(self, mock_subprocess_run):
        """Test test --security."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        runner = CliRunner()
        result = runner.invoke(test, ["--security"])
        
        assert result.exit_code == 0
        mock_subprocess_run.assert_called_once()

    @patch("ccbt.cli.advanced_commands.subprocess.run")
    def test_test_all_flags(self, mock_subprocess_run):
        """Test test with all flags."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        runner = CliRunner()
        result = runner.invoke(test, ["--unit", "--integration", "--performance", "--security"])
        
        assert result.exit_code == 0
        # Should call subprocess once for all test types
        assert mock_subprocess_run.call_count == 1

    @patch("ccbt.cli.advanced_commands.subprocess.run")
    def test_test_no_flags(self, mock_subprocess_run):
        """Test test with no flags."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        runner = CliRunner()
        result = runner.invoke(test, [])
        
        assert result.exit_code == 0
        mock_subprocess_run.assert_called_once()


class TestAdvancedCommandsIntegration:
    """Integration tests for advanced commands."""

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.get_config")
    def test_performance_benchmark_integration(self, mock_get_config, mock_asyncio_run):
        """Test performance benchmark with actual config."""
        config = MagicMock()
        config.disk.disk_workers = 8
        config.disk.disk_queue_size = 200
        config.disk.mmap_cache_mb = 128
        mock_get_config.return_value = config
        
        mock_asyncio_run.return_value = {"write_mbps": 150.0, "read_mbps": 120.0}
        
        runner = CliRunner()
        result = runner.invoke(performance, ["--benchmark"])
        
        assert result.exit_code == 0
        mock_get_config.assert_called_once()

    @patch("ccbt.cli.advanced_commands.get_config")
    def test_security_scan_integration(self, mock_get_config):
        """Test security scan with realistic output."""
        config = MagicMock()
        config.security.validate_peers = True
        config.network.max_connections_per_peer = 2
        config.security.rate_limit_enabled = True
        config.network.global_down_kib = 1000
        config.network.global_up_kib = 500
        mock_get_config.return_value = config
        
        runner = CliRunner()
        result = runner.invoke(security, ["--scan"])
        
        assert result.exit_code == 0
        assert "Performing basic configuration scan" in result.output

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.CheckpointManager")
    def test_recover_checkpoint_integration(self, mock_checkpoint_manager, mock_asyncio_run):
        """Test recover checkpoint with realistic output."""
        mock_cm = MagicMock()
        mock_checkpoint_manager.return_value = mock_cm
        mock_asyncio_run.return_value = True
        
        runner = CliRunner()
        result = runner.invoke(recover, ["1234567890123456789012345678901234567890", "--verify"])
        
        assert result.exit_code == 0
        assert "Checkpoint valid" in result.output
        mock_asyncio_run.assert_called_once()

    @patch("ccbt.cli.advanced_commands.subprocess.run")
    def test_test_unit_integration(self, mock_subprocess_run):
        """Test unit tests with realistic output."""
        # Mock a realistic test result
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        runner = CliRunner()
        result = runner.invoke(test, ["--unit"])
        
        assert result.exit_code == 0
        mock_subprocess_run.assert_called_once()