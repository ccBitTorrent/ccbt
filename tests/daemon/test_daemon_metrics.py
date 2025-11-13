"""Integration tests for metrics initialization in daemon.

from __future__ import annotations

Tests that metrics collection is properly initialized and shut down in daemon.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.daemon.main import DaemonMain
from ccbt.monitoring import get_metrics_collector, reset_metrics_collector


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file with metrics enabled."""
    config_file = tmp_path / "config.toml"
    config_content = """
[observability]
enable_metrics = true
metrics_interval = 5.0
"""
    config_file.write_text(config_content, encoding="utf-8")
    return str(config_file)


@pytest.fixture
def temp_daemon_dir(tmp_path):
    """Create a temporary daemon directory."""
    daemon_dir = tmp_path / "daemon"
    daemon_dir.mkdir()
    return daemon_dir


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics collector before and after each test."""
    reset_metrics_collector()
    yield
    reset_metrics_collector()


@pytest.mark.asyncio
async def test_daemon_initializes_metrics(temp_config_file, temp_daemon_dir):
    """Test that daemon initializes metrics collection on startup."""
    # Mock config to have metrics enabled
    with patch("ccbt.daemon.main.init_config") as mock_init_config:
        from ccbt.config.config import ConfigManager

        # Create a mock config with metrics enabled
        mock_config_manager = MagicMock()
        mock_config = MagicMock()
        mock_observability = MagicMock()
        mock_observability.enable_metrics = True
        mock_observability.metrics_interval = 5.0
        mock_config.observability = mock_observability
        mock_config.daemon = None
        mock_config_manager.config = mock_config
        mock_init_config.return_value = mock_config_manager

        # Create daemon
        daemon = DaemonMain(config_file=temp_config_file, foreground=True)

        # Mock session manager to avoid actual initialization
        mock_session = AsyncMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.get_global_stats = AsyncMock(return_value={})

        # Mock state manager
        with patch("ccbt.daemon.main.StateManager") as mock_state_manager:
            mock_state = MagicMock()
            mock_state.load_state = AsyncMock(return_value=None)
            mock_state_manager.return_value = mock_state

            # Mock IPC server
            with patch("ccbt.daemon.main.IPCServer") as mock_ipc_server:
                mock_ipc = AsyncMock()
                mock_ipc.host = "127.0.0.1"
                mock_ipc.port = 8080
                mock_ipc.start = AsyncMock()
                mock_ipc.stop = AsyncMock()
                mock_ipc_server.return_value = mock_ipc

                # Mock daemon manager
                with patch("ccbt.daemon.main.DaemonManager") as mock_daemon_manager:
                    mock_daemon_mgr = MagicMock()
                    mock_daemon_mgr.setup_signal_handlers = MagicMock()
                    mock_daemon_mgr.write_pid = MagicMock()
                    mock_daemon_mgr.remove_pid = MagicMock()
                    mock_daemon_manager.return_value = mock_daemon_mgr

                    # Mock AsyncSessionManager
                    with patch("ccbt.daemon.main.AsyncSessionManager", return_value=mock_session):
                        # Mock init_metrics to return a metrics collector
                        mock_metrics_collector = MagicMock()
                        mock_metrics_collector.running = True
                        mock_metrics_collector.set_session = MagicMock()

                        with patch("ccbt.daemon.main.init_metrics", return_value=mock_metrics_collector):
                            # Start daemon
                            await daemon.start()

                            # Verify metrics were initialized
                            assert mock_metrics_collector.set_session.called
                            assert mock_metrics_collector.set_session.call_args[0][0] == mock_session

                            # Cleanup
                            await daemon.stop()


@pytest.mark.asyncio
async def test_daemon_shuts_down_metrics(temp_config_file, temp_daemon_dir):
    """Test that daemon shuts down metrics collection on stop."""
    # Mock config
    with patch("ccbt.daemon.main.init_config") as mock_init_config:
        from ccbt.config.config import ConfigManager

        mock_config_manager = MagicMock()
        mock_config = MagicMock()
        mock_observability = MagicMock()
        mock_observability.enable_metrics = True
        mock_observability.metrics_interval = 5.0
        mock_config.observability = mock_observability
        mock_config.daemon = None
        mock_config_manager.config = mock_config
        mock_init_config.return_value = mock_config_manager

        # Create daemon
        daemon = DaemonMain(config_file=temp_config_file, foreground=True)

        # Mock session manager
        mock_session = AsyncMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.get_global_stats = AsyncMock(return_value={})

        # Mock state manager
        with patch("ccbt.daemon.main.StateManager") as mock_state_manager:
            mock_state = MagicMock()
            mock_state.load_state = AsyncMock(return_value=None)
            mock_state.save_state = AsyncMock()
            mock_state_manager.return_value = mock_state

            # Mock IPC server
            with patch("ccbt.daemon.main.IPCServer") as mock_ipc_server:
                mock_ipc = AsyncMock()
                mock_ipc.host = "127.0.0.1"
                mock_ipc.port = 8080
                mock_ipc.start = AsyncMock()
                mock_ipc.stop = AsyncMock()
                mock_ipc_server.return_value = mock_ipc

                # Mock daemon manager
                with patch("ccbt.daemon.main.DaemonManager") as mock_daemon_manager:
                    mock_daemon_mgr = MagicMock()
                    mock_daemon_mgr.setup_signal_handlers = MagicMock()
                    mock_daemon_mgr.write_pid = MagicMock()
                    mock_daemon_mgr.remove_pid = MagicMock()
                    mock_daemon_manager.return_value = mock_daemon_mgr

                    # Mock AsyncSessionManager
                    with patch("ccbt.daemon.main.AsyncSessionManager", return_value=mock_session):
                        # Mock init_metrics
                        mock_metrics_collector = MagicMock()
                        mock_metrics_collector.running = True
                        mock_metrics_collector.set_session = MagicMock()

                        with patch("ccbt.daemon.main.init_metrics", return_value=mock_metrics_collector):
                            # Mock shutdown_metrics
                            mock_shutdown = AsyncMock()
                            with patch("ccbt.daemon.main.shutdown_metrics", mock_shutdown):
                                # Start and stop daemon
                                await daemon.start()
                                await daemon.stop()

                                # Verify shutdown_metrics was called
                                assert mock_shutdown.called


@pytest.mark.asyncio
async def test_daemon_handles_metrics_init_failure(temp_config_file, temp_daemon_dir):
    """Test that daemon continues if metrics initialization fails."""
    # Mock config
    with patch("ccbt.daemon.main.init_config") as mock_init_config:
        mock_config_manager = MagicMock()
        mock_config = MagicMock()
        mock_observability = MagicMock()
        mock_observability.enable_metrics = True
        mock_observability.metrics_interval = 5.0
        mock_config.observability = mock_observability
        mock_config.daemon = None
        mock_config_manager.config = mock_config
        mock_init_config.return_value = mock_config_manager

        # Create daemon
        daemon = DaemonMain(config_file=temp_config_file, foreground=True)

        # Mock session manager
        mock_session = AsyncMock()
        mock_session.start = AsyncMock()
        mock_session.stop = AsyncMock()
        mock_session.get_global_stats = AsyncMock(return_value={})

        # Mock state manager
        with patch("ccbt.daemon.main.StateManager") as mock_state_manager:
            mock_state = MagicMock()
            mock_state.load_state = AsyncMock(return_value=None)
            mock_state_manager.return_value = mock_state

            # Mock IPC server
            with patch("ccbt.daemon.main.IPCServer") as mock_ipc_server:
                mock_ipc = AsyncMock()
                mock_ipc.host = "127.0.0.1"
                mock_ipc.port = 8080
                mock_ipc.start = AsyncMock()
                mock_ipc.stop = AsyncMock()
                mock_ipc_server.return_value = mock_ipc

                # Mock daemon manager
                with patch("ccbt.daemon.main.DaemonManager") as mock_daemon_manager:
                    mock_daemon_mgr = MagicMock()
                    mock_daemon_mgr.setup_signal_handlers = MagicMock()
                    mock_daemon_mgr.write_pid = MagicMock()
                    mock_daemon_mgr.remove_pid = MagicMock()
                    mock_daemon_manager.return_value = mock_daemon_mgr

                    # Mock AsyncSessionManager
                    with patch("ccbt.daemon.main.AsyncSessionManager", return_value=mock_session):
                        # Mock init_metrics to raise exception
                        with patch("ccbt.daemon.main.init_metrics", side_effect=Exception("Metrics init failed")):
                            # Start should not raise (metrics init failure is logged but doesn't stop daemon)
                            await daemon.start()

                            # Daemon should still be running
                            assert daemon.session_manager is not None

                            # Cleanup
                            await daemon.stop()

