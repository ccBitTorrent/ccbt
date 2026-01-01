"""Integration tests for per-torrent configuration CLI commands.

Tests the CLI commands for managing per-torrent configuration options
and rate limits, including persistence via checkpoints.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.cli.torrent_config_commands import (
    _get_torrent_option,
    _list_torrent_options,
    _reset_torrent_options,
    _set_torrent_option,
)


@pytest.fixture(scope="function")
def mock_daemon_running():
    """Mock daemon manager that reports daemon as running."""
    with patch("ccbt.cli.torrent_config_commands.DaemonManager") as mock_dm:
        instance = MagicMock()
        instance.is_running.return_value = True
        mock_dm.return_value = instance
        yield instance


@pytest.fixture(scope="function")
def mock_daemon_not_running():
    """Mock daemon manager that reports daemon as not running."""
    with patch("ccbt.cli.torrent_config_commands.DaemonManager") as mock_dm:
        instance = MagicMock()
        instance.is_running.return_value = False
        mock_dm.return_value = instance
        yield instance


@pytest.fixture
def mock_ipc_client():
    """Mock IPC client for daemon communication."""
    client = AsyncMock()
    result = MagicMock()
    result.success = True
    result.data = {}
    client.execute = AsyncMock(return_value=result)
    return client


@pytest.fixture(scope="function")
def mock_session_manager():
    """Mock session manager for direct mode."""
    manager = AsyncMock()
    manager.torrents = {}
    manager._per_torrent_limits = {}
    return manager


@pytest.mark.asyncio
async def test_torrent_config_set_with_daemon(mock_daemon_running, mock_ipc_client):
    """Test setting per-torrent config via daemon IPC."""
    info_hash = "a" * 40
    key = "piece_selection"
    value = "sequential"

    with patch("ccbt.cli.torrent_config_commands.IPCClient", return_value=mock_ipc_client):
        from ccbt.executor.base import CommandResult
        from ccbt.daemon.ipc_protocol import TorrentStatusResponse
        
        # Mock executor manager and executor
        mock_executor = AsyncMock()
        # Mock adapter.get_torrent_status (used to check if torrent exists)
        mock_adapter = AsyncMock()
        mock_status = TorrentStatusResponse(
            info_hash=info_hash,
            name="test",
            status="active",
            progress=0.0,
            download_rate=0.0,
            upload_rate=0.0,
            num_peers=0,
            num_seeds=0,
            total_size=0,
            downloaded=0,
            uploaded=0,
            is_private=False,
        )
        mock_adapter.get_torrent_status = AsyncMock(return_value=mock_status)
        mock_executor.adapter = mock_adapter
        
        # Mock set_option
        set_option_result = CommandResult(success=True, data={"set": True, "key": key, "value": value})
        mock_executor.execute = AsyncMock(return_value=set_option_result)
        
        # Mock ExecutorManager.get_instance and get_executor
        # ExecutorManager is imported inside the function, so patch it there
        with patch("ccbt.executor.manager.ExecutorManager.get_instance") as mock_get_instance:
            mock_manager = MagicMock()
            mock_manager.get_executor = MagicMock(return_value=mock_executor)
            mock_get_instance.return_value = mock_manager
            
            await _set_torrent_option(info_hash, key, value, save_checkpoint=False)

            # Verify adapter.get_torrent_status was called
            mock_adapter.get_torrent_status.assert_called_once_with(info_hash)
            # Verify executor.execute was called for set_option
            mock_executor.execute.assert_called_once()
            call_args = mock_executor.execute.call_args
            assert call_args[0][0] == "torrent.set_option"
            assert call_args[1]["info_hash"] == info_hash
            assert call_args[1]["key"] == key
            assert call_args[1]["value"] == value


@pytest.mark.asyncio
async def test_torrent_config_set_with_checkpoint(mock_daemon_running, mock_ipc_client):
    """Test setting per-torrent config with checkpoint save."""
    info_hash = "a" * 40
    key = "streaming_mode"
    value = "true"

    with patch("ccbt.cli.torrent_config_commands.IPCClient", return_value=mock_ipc_client):
        from ccbt.executor.base import CommandResult
        from ccbt.daemon.ipc_protocol import TorrentStatusResponse
        
        # Mock executor manager and executor
        mock_executor = AsyncMock()
        # Mock adapter.get_torrent_status (used to check if torrent exists)
        mock_adapter = AsyncMock()
        mock_status = TorrentStatusResponse(
            info_hash=info_hash,
            name="test",
            status="active",
            progress=0.0,
            download_rate=0.0,
            upload_rate=0.0,
            num_peers=0,
            num_seeds=0,
            total_size=0,
            downloaded=0,
            uploaded=0,
            is_private=False,
        )
        mock_adapter.get_torrent_status = AsyncMock(return_value=mock_status)
        mock_executor.adapter = mock_adapter
        
        # Mock set_option and save_checkpoint
        set_option_result = CommandResult(success=True, data={"set": True, "key": key, "value": value})
        save_checkpoint_result = CommandResult(success=True, data={"saved": True})
        mock_executor.execute = AsyncMock(side_effect=[set_option_result, save_checkpoint_result])
        
        # Mock ExecutorManager.get_instance and get_executor
        # ExecutorManager is imported inside the function, so patch it there
        with patch("ccbt.executor.manager.ExecutorManager.get_instance") as mock_get_instance:
            mock_manager = MagicMock()
            mock_manager.get_executor = MagicMock(return_value=mock_executor)
            mock_get_instance.return_value = mock_manager
            
            await _set_torrent_option(info_hash, key, value, save_checkpoint=True)

            # Verify adapter.get_torrent_status was called
            mock_adapter.get_torrent_status.assert_called_once_with(info_hash)
            # Verify all executor.execute calls were made
            calls = [call[0][0] for call in mock_executor.execute.call_args_list]
            assert "torrent.set_option" in calls
            assert "torrent.save_checkpoint" in calls


@pytest.mark.asyncio
async def test_torrent_config_get_with_daemon(mock_daemon_running, mock_ipc_client):
    """Test getting per-torrent config via daemon IPC."""
    info_hash = "a" * 40
    key = "piece_selection"

    with patch("ccbt.cli.torrent_config_commands.IPCClient", return_value=mock_ipc_client):
        from ccbt.executor.base import CommandResult
        
        # Mock executor manager and executor
        mock_executor = AsyncMock()
        result = CommandResult(success=True, data={"key": key, "value": "sequential"})
        mock_executor.execute = AsyncMock(return_value=result)
        
        # Mock ExecutorManager.get_instance and get_executor
        # ExecutorManager is imported inside the function, so patch it there
        with patch("ccbt.executor.manager.ExecutorManager.get_instance") as mock_get_instance:
            mock_manager = MagicMock()
            mock_manager.get_executor = MagicMock(return_value=mock_executor)
            mock_get_instance.return_value = mock_manager

            await _get_torrent_option(info_hash, key)

            # Verify executor.execute was called
            mock_executor.execute.assert_called_once()
            call_args = mock_executor.execute.call_args
            assert call_args[0][0] == "torrent.get_option"
            assert call_args[1]["info_hash"] == info_hash
            assert call_args[1]["key"] == key


@pytest.mark.asyncio
async def test_torrent_config_list_with_daemon(mock_daemon_running, mock_ipc_client):
    """Test listing per-torrent config via daemon IPC."""
    info_hash = "a" * 40

    with patch("ccbt.cli.torrent_config_commands.IPCClient", return_value=mock_ipc_client):
        from ccbt.executor.base import CommandResult
        
        # Mock executor manager and executor
        mock_executor = AsyncMock()
        result = CommandResult(
            success=True,
            data={
                "options": {
                    "piece_selection": "sequential",
                    "streaming_mode": True,
                },
                "rate_limits": {
                    "down_kib": 100,
                    "up_kib": 50,
                },
            },
        )
        mock_executor.execute = AsyncMock(return_value=result)
        
        # Mock ExecutorManager.get_instance and get_executor
        # ExecutorManager is imported inside the function, so patch it there
        with patch("ccbt.executor.manager.ExecutorManager.get_instance") as mock_get_instance:
            mock_manager = MagicMock()
            mock_manager.get_executor = MagicMock(return_value=mock_executor)
            mock_get_instance.return_value = mock_manager

            await _list_torrent_options(info_hash)

            # Verify executor.execute was called
            mock_executor.execute.assert_called_once()
            call_args = mock_executor.execute.call_args
            assert call_args[0][0] == "torrent.get_config"
            assert call_args[1]["info_hash"] == info_hash


@pytest.mark.asyncio
async def test_torrent_config_reset_all(mock_daemon_running, mock_ipc_client):
    """Test resetting all per-torrent config via daemon IPC."""
    info_hash = "a" * 40

    with patch("ccbt.cli.torrent_config_commands.IPCClient", return_value=mock_ipc_client):
        from ccbt.executor.base import CommandResult
        
        # Mock executor manager and executor
        mock_executor = AsyncMock()
        result = CommandResult(success=True, data={"reset": True, "key": None})
        mock_executor.execute = AsyncMock(return_value=result)
        
        # Mock ExecutorManager.get_instance and get_executor
        # ExecutorManager is imported inside the function, so patch it there
        with patch("ccbt.executor.manager.ExecutorManager.get_instance") as mock_get_instance:
            mock_manager = MagicMock()
            mock_manager.get_executor = MagicMock(return_value=mock_executor)
            mock_get_instance.return_value = mock_manager

            await _reset_torrent_options(info_hash, key=None, save_checkpoint=False)

            # Verify executor.execute was called
            mock_executor.execute.assert_called_once()
            call_args = mock_executor.execute.call_args
            assert call_args[0][0] == "torrent.reset_options"
            assert call_args[1]["info_hash"] == info_hash
            assert call_args[1].get("key") is None


@pytest.mark.asyncio
async def test_torrent_config_reset_key(mock_daemon_running, mock_ipc_client):
    """Test resetting specific per-torrent config key via daemon IPC."""
    info_hash = "a" * 40
    key = "piece_selection"

    with patch("ccbt.cli.torrent_config_commands.IPCClient", return_value=mock_ipc_client):
        from ccbt.executor.base import CommandResult
        
        # Mock executor manager and executor
        mock_executor = AsyncMock()
        result = CommandResult(success=True, data={"reset": True, "key": key})
        mock_executor.execute = AsyncMock(return_value=result)
        
        # Mock ExecutorManager.get_instance and get_executor
        # ExecutorManager is imported inside the function, so patch it there
        with patch("ccbt.executor.manager.ExecutorManager.get_instance") as mock_get_instance:
            mock_manager = MagicMock()
            mock_manager.get_executor = MagicMock(return_value=mock_executor)
            mock_get_instance.return_value = mock_manager

            await _reset_torrent_options(info_hash, key=key, save_checkpoint=False)

            # Verify executor.execute was called
            mock_executor.execute.assert_called_once()
            call_args = mock_executor.execute.call_args
            assert call_args[0][0] == "torrent.reset_options"
            assert call_args[1]["info_hash"] == info_hash
            assert call_args[1]["key"] == key


@pytest.mark.asyncio
async def test_torrent_config_set_direct_mode(mock_daemon_not_running, mock_session_manager):
    """Test setting per-torrent config in direct mode (no daemon)."""
    info_hash = "a" * 40
    key = "piece_selection"
    value = "sequential"

    # Create a fake torrent session
    from types import SimpleNamespace

    info_hash_bytes = bytes.fromhex(info_hash)
    fake_session = MagicMock()
    fake_session.options = {}
    fake_session.info = SimpleNamespace(info_hash=info_hash_bytes, name="test")
    fake_session._apply_per_torrent_options = MagicMock()
    mock_session_manager.torrents[info_hash_bytes] = fake_session

    with patch(
        "ccbt.cli.torrent_config_commands._get_torrent_session",
        return_value=fake_session,
    ), patch(
        "ccbt.cli.torrent_config_commands.AsyncSessionManager",
        return_value=mock_session_manager,
    ):
        await _set_torrent_option(info_hash, key, value, save_checkpoint=False)

        # Verify option was set
        assert fake_session.options[key] == value


@pytest.mark.asyncio
async def test_torrent_config_get_direct_mode(mock_daemon_not_running, mock_session_manager):
    """Test getting per-torrent config in direct mode (no daemon)."""
    info_hash = "a" * 40
    key = "piece_selection"

    # Create a fake torrent session with existing option
    from types import SimpleNamespace

    info_hash_bytes = bytes.fromhex(info_hash)
    fake_session = MagicMock()
    fake_session.options = {key: "sequential"}
    fake_session.info = SimpleNamespace(info_hash=info_hash_bytes, name="test")
    mock_session_manager.torrents[info_hash_bytes] = fake_session

    with patch(
        "ccbt.cli.torrent_config_commands._get_torrent_session",
        return_value=fake_session,
    ), patch(
        "ccbt.cli.torrent_config_commands.AsyncSessionManager",
        return_value=mock_session_manager,
    ):
        await _get_torrent_option(info_hash, key)

        # Test passes if no exception is raised
        assert True


@pytest.mark.asyncio
async def test_torrent_config_list_direct_mode(mock_daemon_not_running, mock_session_manager):
    """Test listing per-torrent config in direct mode (no daemon)."""
    info_hash = "a" * 40

    # Create a fake torrent session with options and rate limits
    from types import SimpleNamespace

    info_hash_bytes = bytes.fromhex(info_hash)
    fake_session = MagicMock()
    fake_session.options = {
        "piece_selection": "sequential",
        "streaming_mode": True,
    }
    fake_session.info = SimpleNamespace(info_hash=info_hash_bytes, name="test")
    mock_session_manager.torrents[info_hash_bytes] = fake_session
    mock_session_manager._per_torrent_limits[info_hash_bytes] = {
        "down_kib": 100,
        "up_kib": 50,
    }

    with patch(
        "ccbt.cli.torrent_config_commands._get_torrent_session",
        return_value=fake_session,
    ), patch(
        "ccbt.cli.torrent_config_commands.AsyncSessionManager",
        return_value=mock_session_manager,
    ):
        await _list_torrent_options(info_hash)

        # Test passes if no exception is raised
        assert True


@pytest.mark.asyncio
async def test_torrent_config_reset_direct_mode(mock_daemon_not_running, mock_session_manager):
    """Test resetting per-torrent config in direct mode (no daemon)."""
    info_hash = "a" * 40
    key = "piece_selection"

    # Create a fake torrent session with existing option
    from types import SimpleNamespace

    info_hash_bytes = bytes.fromhex(info_hash)
    fake_session = MagicMock()
    fake_session.options = {key: "sequential", "streaming_mode": True}
    fake_session.info = SimpleNamespace(info_hash=info_hash_bytes, name="test")
    fake_session._apply_per_torrent_options = MagicMock()
    mock_session_manager.torrents[info_hash_bytes] = fake_session

    with patch(
        "ccbt.cli.torrent_config_commands._get_torrent_session",
        return_value=fake_session,
    ), patch(
        "ccbt.cli.torrent_config_commands.AsyncSessionManager",
        return_value=mock_session_manager,
    ):
        await _reset_torrent_options(info_hash, key=key, save_checkpoint=False)

        # Verify option was removed
        assert key not in fake_session.options
        assert "streaming_mode" in fake_session.options  # Other options remain





















































