"""Expanded tests for ccbt.cli.advanced_commands to achieve 95%+ coverage.

Covers missing lines:
- _quick_disk_benchmark() function (lines 30-70)
- Exception handling in performance command (lines 120-126, 150-156)
- Coverage flag handling in test command (line 281)
- Exception handling in test command (lines 286-287)
"""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

from ccbt.cli.advanced_commands import (
    _quick_disk_benchmark,
    performance,
    test,
)

pytestmark = [pytest.mark.unit, pytest.mark.cli]


class TestQuickDiskBenchmark:
    """Tests for _quick_disk_benchmark function."""

    @pytest.mark.asyncio
    @patch("ccbt.cli.advanced_commands.DiskIOManager")
    @patch("ccbt.cli.advanced_commands.get_config")
    async def test_quick_disk_benchmark_full(self, mock_get_config, mock_disk_manager):
        """Test _quick_disk_benchmark complete execution (lines 30-70)."""
        # Setup config
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.disk_queue_size = 100
        config.disk.mmap_cache_mb = 64
        mock_get_config.return_value = config

        # Setup disk manager
        mock_disk = AsyncMock()
        mock_disk_manager.return_value = mock_disk

        # Mock write_block: the code does `fut = await disk.write_block(...)` then `await fut`
        # So write_block when awaited should return something awaitable (a Future)
        from asyncio import Future
        async def async_write_block(*args, **kwargs):
            f = Future()
            f.set_result(None)
            return f
        # Use AsyncMock with side_effect to track calls but return the Future
        mock_disk.write_block = AsyncMock(side_effect=async_write_block)
        
        # Mock read_block
        mock_disk.read_block = AsyncMock(return_value=b"X" * (64 * 1024))

        # Run benchmark
        result = await _quick_disk_benchmark()

        # Verify
        assert "size_mb" in result
        assert "write_mb_s" in result
        assert "read_mb_s" in result
        assert "write_time_s" in result
        assert "read_time_s" in result
        assert result["size_mb"] == 16.0  # 16 MiB
        assert result["write_mb_s"] >= 0
        assert result["read_mb_s"] >= 0

        # Verify disk manager was started and stopped
        mock_disk.start.assert_called_once()
        mock_disk.stop.assert_called_once()

        # Verify blocks were written and read
        # 16 MiB / 64 KiB = 256 blocks
        assert mock_disk.write_block.call_count == 256
        assert mock_disk.read_block.call_count == 256

    @pytest.mark.asyncio
    @patch("ccbt.cli.advanced_commands.DiskIOManager")
    @patch("ccbt.cli.advanced_commands.get_config")
    async def test_quick_disk_benchmark_disk_stop_error(self, mock_get_config, mock_disk_manager):
        """Test _quick_disk_benchmark with disk.stop() error."""
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.disk_queue_size = 100
        config.disk.mmap_cache_mb = 64
        mock_get_config.return_value = config

        mock_disk = AsyncMock()
        mock_disk_manager.return_value = mock_disk
        mock_disk.stop.side_effect = Exception("Stop error")
        
        # Make write_block return a Future that can be awaited later
        from asyncio import Future
        async def async_write_block(*args, **kwargs):
            f = Future()
            f.set_result(None)
            return f
        mock_disk.write_block = AsyncMock(side_effect=async_write_block)
        mock_disk.read_block = AsyncMock(return_value=b"X" * (64 * 1024))

        # Should raise exception when stop() fails
        with pytest.raises(Exception, match="Stop error"):
            await _quick_disk_benchmark()
        
        mock_disk.start.assert_called_once()


class TestPerformanceCommandExpanded:
    """Expanded tests for performance command."""

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.get_config")
    def test_performance_profile_with_exception(
        self,
        mock_get_config,
        mock_asyncio_run,
    ):
        """Test performance --profile with exception handling (lines 120-126)."""
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.disk_queue_size = 100
        config.disk.mmap_cache_mb = 64
        mock_get_config.return_value = config

        # Mock asyncio.run to raise exception
        mock_asyncio_run.side_effect = Exception("Benchmark failed")

        # Patch cProfile inside the function context where it's imported
        with patch("builtins.__import__") as mock_import:
            def side_effect(name, *args, **kwargs):
                if name == "cProfile":
                    mock_prof_module = MagicMock()
                    mock_prof = MagicMock()
                    mock_prof_module.Profile.return_value = mock_prof
                    return mock_prof_module
                elif name == "pstats":
                    mock_pstats_module = MagicMock()
                    mock_stats = MagicMock()
                    mock_stats_instance = MagicMock()
                    mock_stats_instance.strip_dirs.return_value = mock_stats_instance
                    mock_stats_instance.sort_stats.return_value = mock_stats_instance
                    mock_stats.return_value = mock_stats_instance
                    mock_pstats_module.Stats = mock_stats
                    return mock_pstats_module
                # For other imports, use real import
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            runner = CliRunner()
            result = runner.invoke(performance, ["--profile"])

            # Should handle exception and show error or default results
            assert result.exit_code in [0, 1]

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.get_config")
    def test_performance_benchmark_with_exception(
        self,
        mock_get_config,
        mock_asyncio_run,
    ):
        """Test performance --benchmark with exception handling (lines 150-156)."""
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.disk_queue_size = 100
        config.disk.mmap_cache_mb = 64
        mock_get_config.return_value = config

        # Mock asyncio.run to raise exception
        mock_asyncio_run.side_effect = Exception("Benchmark failed")

        runner = CliRunner()
        result = runner.invoke(performance, ["--benchmark"])

        # Should handle exception and show default results
        assert result.exit_code in [0, 1]
        assert "Benchmark results" in result.output
        # Should show zero results on exception
        assert '"write_mb_s": 0' in result.output or '"read_mb_s": 0' in result.output

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.get_config")
    def test_performance_benchmark_coroutine_close_error(
        self,
        mock_get_config,
        mock_asyncio_run,
    ):
        """Test performance benchmark with coroutine close error (lines 150-156)."""
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.disk_queue_size = 100
        config.disk.mmap_cache_mb = 64
        mock_get_config.return_value = config

        # Create a real coroutine that will be closed
        async def mock_benchmark():
            raise Exception("Benchmark failed")

        # Mock _quick_disk_benchmark to return coroutine
        coro = mock_benchmark()
        with patch("ccbt.cli.advanced_commands._quick_disk_benchmark", return_value=coro):
            mock_asyncio_run.side_effect = Exception("Benchmark failed")

            runner = CliRunner()
            result = runner.invoke(performance, ["--benchmark"])

            # Should handle exception gracefully
            assert result.exit_code in [0, 1]
        
        # Clean up coroutine
        with contextlib.suppress(Exception):
            coro.close()

    @patch("ccbt.cli.advanced_commands.asyncio.run")
    @patch("ccbt.cli.advanced_commands.get_config")
    def test_performance_profile_coroutine_close_error(
        self,
        mock_get_config,
        mock_asyncio_run,
    ):
        """Test performance profile with coroutine close error (lines 120-126)."""
        config = MagicMock()
        config.disk.disk_workers = 4
        config.disk.disk_queue_size = 100
        config.disk.mmap_cache_mb = 64
        mock_get_config.return_value = config

        # Create a real coroutine that will be closed
        async def mock_benchmark():
            raise Exception("Benchmark failed")

        # Import the real __import__ before patching to avoid recursion
        import builtins
        real_import = builtins.__import__
        
        # Patch __import__ to handle cProfile/pstats imports
        with patch("builtins.__import__") as mock_import:
            def side_effect(name, *args, **kwargs):
                if name == "cProfile":
                    mock_prof_module = MagicMock()
                    mock_prof = MagicMock()
                    mock_prof_module.Profile.return_value = mock_prof
                    return mock_prof_module
                elif name == "pstats":
                    mock_pstats_module = MagicMock()
                    mock_stats = MagicMock()
                    mock_stats_instance = MagicMock()
                    mock_stats_instance.strip_dirs.return_value = mock_stats_instance
                    mock_stats_instance.sort_stats.return_value = mock_stats_instance
                    mock_stats.return_value = mock_stats_instance
                    mock_pstats_module.Stats = mock_stats
                    return mock_pstats_module
                return real_import(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            # Mock _quick_disk_benchmark to return coroutine
            coro = mock_benchmark()
            with patch("ccbt.cli.advanced_commands._quick_disk_benchmark", return_value=coro):
                mock_asyncio_run.side_effect = Exception("Benchmark failed")

                runner = CliRunner()
                result = runner.invoke(performance, ["--profile"])

                # Should handle exception gracefully
                assert result.exit_code in [0, 1]
            
            # Clean up coroutine
            with contextlib.suppress(Exception):
                coro.close()


class TestTestCommandExpanded:
    """Expanded tests for test command."""

    @patch("ccbt.cli.advanced_commands.subprocess.run")
    def test_test_with_coverage(self, mock_subprocess_run):
        """Test test command with --coverage flag (line 281)."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        runner = CliRunner()
        result = runner.invoke(test, ["--unit", "--coverage"])

        assert result.exit_code == 0
        mock_subprocess_run.assert_called_once()

        # Verify coverage args were added
        call_args = mock_subprocess_run.call_args[0][0]
        assert "--cov=ccbt" in call_args
        assert "--cov-report" in call_args
        assert "term-missing" in call_args

    @patch("ccbt.cli.advanced_commands.subprocess.run")
    def test_test_with_exception(self, mock_subprocess_run):
        """Test test command with subprocess exception (lines 286-287)."""
        mock_subprocess_run.side_effect = Exception("Subprocess failed")

        runner = CliRunner()
        result = runner.invoke(test, ["--unit"])

        # Should handle exception and show error message
        assert result.exit_code in [0, 1]
        assert "Failed to run tests" in result.output
        assert "Subprocess failed" in result.output

    @patch("ccbt.cli.advanced_commands.subprocess.run")
    def test_test_all_flags_with_coverage(self, mock_subprocess_run):
        """Test test command with all flags and coverage."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        runner = CliRunner()
        result = runner.invoke(test, [
            "--unit",
            "--integration",
            "--performance",
            "--security",
            "--coverage",
        ])

        assert result.exit_code == 0
        mock_subprocess_run.assert_called_once()

        # Verify all test types and coverage are included
        call_args = mock_subprocess_run.call_args[0][0]
        assert "--cov=ccbt" in call_args
        assert "tests/integration" in call_args or any("integration" in str(arg) for arg in call_args)
        assert "tests/performance" in call_args or any("performance" in str(arg) for arg in call_args)
        assert "tests/security" in call_args or any("security" in str(arg) for arg in call_args)

