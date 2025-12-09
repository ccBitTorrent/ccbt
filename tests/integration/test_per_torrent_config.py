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
    torrent_config_get,
    torrent_config_list,
    torrent_config_reset,
    torrent_config_set,
)


@pytest.fixture
def mock_daemon_running():
    """Mock daemon manager that reports daemon as running."""
    with patch("ccbt.cli.torrent_config_commands.DaemonManager") as mock_dm:
        instance = MagicMock()
        instance.is_running.return_value = True
        mock_dm.return_value = instance
        yield instance


@pytest.fixture
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


@pytest.fixture
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
        ctx = MagicMock()
        ctx.obj = {}

        # Mock successful execution
        result = MagicMock()
        result.success = True
        result.data = {"status": "ok"}
        mock_ipc_client.execute = AsyncMock(return_value=result)

        await torrent_config_set(ctx, info_hash, key, value, save_checkpoint=False)

        # Verify IPC call was made
        mock_ipc_client.execute.assert_called_once()
        call_args = mock_ipc_client.execute.call_args
        assert call_args[0][0] == "torrent.set_config"
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
        ctx = MagicMock()
        ctx.obj = {}

        result = MagicMock()
        result.success = True
        result.data = {"status": "ok"}
        mock_ipc_client.execute = AsyncMock(return_value=result)

        await torrent_config_set(ctx, info_hash, key, value, save_checkpoint=True)

        # Verify both set_config and save_checkpoint were called
        assert mock_ipc_client.execute.call_count >= 2
        calls = [call[0][0] for call in mock_ipc_client.execute.call_args_list]
        assert "torrent.set_config" in calls
        assert "torrent.save_checkpoint" in calls


@pytest.mark.asyncio
async def test_torrent_config_get_with_daemon(mock_daemon_running, mock_ipc_client):
    """Test getting per-torrent config via daemon IPC."""
    info_hash = "a" * 40
    key = "piece_selection"

    with patch("ccbt.cli.torrent_config_commands.IPCClient", return_value=mock_ipc_client):
        ctx = MagicMock()
        ctx.obj = {}

        result = MagicMock()
        result.success = True
        result.data = {"value": "sequential"}
        mock_ipc_client.execute = AsyncMock(return_value=result)

        await torrent_config_get(ctx, info_hash, key)

        # Verify IPC call was made
        mock_ipc_client.execute.assert_called_once()
        call_args = mock_ipc_client.execute.call_args
        assert call_args[0][0] == "torrent.get_config"
        assert call_args[1]["info_hash"] == info_hash
        assert call_args[1]["key"] == key


@pytest.mark.asyncio
async def test_torrent_config_list_with_daemon(mock_daemon_running, mock_ipc_client):
    """Test listing per-torrent config via daemon IPC."""
    info_hash = "a" * 40

    with patch("ccbt.cli.torrent_config_commands.IPCClient", return_value=mock_ipc_client):
        ctx = MagicMock()
        ctx.obj = {}

        result = MagicMock()
        result.success = True
        result.data = {
            "options": {
                "piece_selection": "sequential",
                "streaming_mode": True,
            },
            "rate_limits": {
                "down_kib": 100,
                "up_kib": 50,
            },
        }
        mock_ipc_client.execute = AsyncMock(return_value=result)

        await torrent_config_list(ctx, info_hash)

        # Verify IPC call was made
        mock_ipc_client.execute.assert_called_once()
        call_args = mock_ipc_client.execute.call_args
        assert call_args[0][0] == "torrent.get_config"
        assert call_args[1]["info_hash"] == info_hash


@pytest.mark.asyncio
async def test_torrent_config_reset_all(mock_daemon_running, mock_ipc_client):
    """Test resetting all per-torrent config via daemon IPC."""
    info_hash = "a" * 40

    with patch("ccbt.cli.torrent_config_commands.IPCClient", return_value=mock_ipc_client):
        ctx = MagicMock()
        ctx.obj = {}

        result = MagicMock()
        result.success = True
        result.data = {"status": "ok"}
        mock_ipc_client.execute = AsyncMock(return_value=result)

        await torrent_config_reset(ctx, info_hash, key=None)

        # Verify IPC call was made
        mock_ipc_client.execute.assert_called_once()
        call_args = mock_ipc_client.execute.call_args
        assert call_args[0][0] == "torrent.reset_config"
        assert call_args[1]["info_hash"] == info_hash
        assert call_args[1].get("key") is None


@pytest.mark.asyncio
async def test_torrent_config_reset_key(mock_daemon_running, mock_ipc_client):
    """Test resetting specific per-torrent config key via daemon IPC."""
    info_hash = "a" * 40
    key = "piece_selection"

    with patch("ccbt.cli.torrent_config_commands.IPCClient", return_value=mock_ipc_client):
        ctx = MagicMock()
        ctx.obj = {}

        result = MagicMock()
        result.success = True
        result.data = {"status": "ok"}
        mock_ipc_client.execute = AsyncMock(return_value=result)

        await torrent_config_reset(ctx, info_hash, key=key)

        # Verify IPC call was made
        mock_ipc_client.execute.assert_called_once()
        call_args = mock_ipc_client.execute.call_args
        assert call_args[0][0] == "torrent.reset_config"
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
    mock_session_manager.torrents[info_hash_bytes] = fake_session

    with patch(
        "ccbt.cli.torrent_config_commands.get_session_manager",
        return_value=mock_session_manager,
    ):
        ctx = MagicMock()
        ctx.obj = {}

        await torrent_config_set(ctx, info_hash, key, value, save_checkpoint=False)

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
        "ccbt.cli.torrent_config_commands.get_session_manager",
        return_value=mock_session_manager,
    ):
        ctx = MagicMock()
        ctx.obj = {}

        await torrent_config_get(ctx, info_hash, key)

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
        "ccbt.cli.torrent_config_commands.get_session_manager",
        return_value=mock_session_manager,
    ):
        ctx = MagicMock()
        ctx.obj = {}

        await torrent_config_list(ctx, info_hash)

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
    mock_session_manager.torrents[info_hash_bytes] = fake_session

    with patch(
        "ccbt.cli.torrent_config_commands.get_session_manager",
        return_value=mock_session_manager,
    ):
        ctx = MagicMock()
        ctx.obj = {}

        await torrent_config_reset(ctx, info_hash, key=key)

        # Verify option was removed
        assert key not in fake_session.options
        assert "streaming_mode" in fake_session.options  # Other options remain





















































