"""Unit tests for SessionAdapter config methods.

Tests the new config methods in:
- LocalSessionAdapter
- DaemonSessionAdapter
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from ccbt.executor.session_adapter import DaemonSessionAdapter, LocalSessionAdapter
from ccbt.session.session import AsyncSessionManager, AsyncTorrentSession

pytestmark = [pytest.mark.unit, pytest.mark.executor]


class TestLocalSessionAdapterConfig:
    """Test LocalSessionAdapter config methods."""

    @pytest.fixture
    def tmp_dir(self, tmp_path: Path) -> Path:
        """Create temporary directory."""
        return tmp_path / "downloads"

    @pytest.fixture
    async def session_manager(self, tmp_dir: Path) -> AsyncSessionManager:
        """Create session manager with disabled network services."""
        manager = AsyncSessionManager(output_dir=str(tmp_dir))
        manager.config.network.enable_tcp = False
        manager.config.network.enable_utp = False
        manager.config.discovery.enable_dht = False
        manager.config.nat.auto_map_ports = False
        manager.config.network.listen_port = 0

        # Mock heavy initialization
        manager._make_nat_manager = lambda: None  # type: ignore[method-assign]
        manager._make_tcp_server = lambda: None  # type: ignore[method-assign]

        await manager.start()
        try:
            yield manager
        finally:
            await manager.stop()

    @pytest.fixture
    def adapter(self, session_manager):
        """Create LocalSessionAdapter."""
        return LocalSessionAdapter(session_manager)

    @pytest.fixture
    async def torrent_session(self, session_manager, tmp_dir: Path):
        """Create a test torrent session."""
        torrent_data = {
            "name": "test_torrent",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }

        session = AsyncTorrentSession(torrent_data, str(tmp_dir), session_manager)
        info_hash_bytes = b"x" * 20
        async with session_manager.lock:
            session_manager.torrents[info_hash_bytes] = session
        return session, (b"x" * 20).hex()

    @pytest.mark.asyncio
    async def test_set_torrent_option_success(
        self, adapter, torrent_session, session_manager
    ):
        """Test setting option successfully."""
        session, info_hash_hex = torrent_session
        key = "piece_selection"
        value = "sequential"

        result = await adapter.set_torrent_option(info_hash_hex, key, value)

        assert result is True
        assert session.options[key] == value

    @pytest.mark.asyncio
    async def test_set_torrent_option_torrent_not_found(self, adapter):
        """Test setting option for non-existent torrent."""
        info_hash_hex = "a" * 40
        key = "piece_selection"
        value = "sequential"

        result = await adapter.set_torrent_option(info_hash_hex, key, value)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_torrent_option_success(
        self, adapter, torrent_session, session_manager
    ):
        """Test getting option successfully."""
        session, info_hash_hex = torrent_session
        key = "piece_selection"
        value = "sequential"
        session.options[key] = value

        result = await adapter.get_torrent_option(info_hash_hex, key)

        assert result == value

    @pytest.mark.asyncio
    async def test_get_torrent_option_not_set(
        self, adapter, torrent_session, session_manager
    ):
        """Test getting option that is not set."""
        _, info_hash_hex = torrent_session
        key = "piece_selection"

        result = await adapter.get_torrent_option(info_hash_hex, key)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_torrent_option_torrent_not_found(self, adapter):
        """Test getting option for non-existent torrent."""
        info_hash_hex = "a" * 40
        key = "piece_selection"

        result = await adapter.get_torrent_option(info_hash_hex, key)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_torrent_config_success(
        self, adapter, torrent_session, session_manager
    ):
        """Test getting full config successfully."""
        session, info_hash_hex = torrent_session
        session.options["piece_selection"] = "sequential"
        session.options["streaming_mode"] = True

        info_hash_bytes = bytes.fromhex(info_hash_hex)
        session_manager._per_torrent_limits[info_hash_bytes] = {
            "down_kib": 100,
            "up_kib": 50,
        }

        result = await adapter.get_torrent_config(info_hash_hex)

        assert "options" in result
        assert "rate_limits" in result
        assert result["options"]["piece_selection"] == "sequential"
        assert result["options"]["streaming_mode"] is True
        assert result["rate_limits"]["down_kib"] == 100
        assert result["rate_limits"]["up_kib"] == 50

    @pytest.mark.asyncio
    async def test_get_torrent_config_empty(self, adapter, torrent_session):
        """Test getting config for torrent with no options."""
        _, info_hash_hex = torrent_session

        result = await adapter.get_torrent_config(info_hash_hex)

        assert result == {"options": {}, "rate_limits": {}}

    @pytest.mark.asyncio
    async def test_get_torrent_config_torrent_not_found(self, adapter):
        """Test getting config for non-existent torrent."""
        info_hash_hex = "a" * 40

        result = await adapter.get_torrent_config(info_hash_hex)

        assert result == {"options": {}, "rate_limits": {}}

    @pytest.mark.asyncio
    async def test_reset_torrent_options_all_success(
        self, adapter, torrent_session, session_manager
    ):
        """Test resetting all options successfully."""
        session, info_hash_hex = torrent_session
        session.options["piece_selection"] = "sequential"
        session.options["streaming_mode"] = True

        result = await adapter.reset_torrent_options(info_hash_hex, key=None)

        assert result is True
        assert len(session.options) == 0

    @pytest.mark.asyncio
    async def test_reset_torrent_options_single_key_success(
        self, adapter, torrent_session, session_manager
    ):
        """Test resetting single option successfully."""
        session, info_hash_hex = torrent_session
        session.options["piece_selection"] = "sequential"
        session.options["streaming_mode"] = True

        result = await adapter.reset_torrent_options(
            info_hash_hex, key="piece_selection"
        )

        assert result is True
        assert "piece_selection" not in session.options
        assert "streaming_mode" in session.options

    @pytest.mark.asyncio
    async def test_reset_torrent_options_torrent_not_found(self, adapter):
        """Test resetting options for non-existent torrent."""
        info_hash_hex = "a" * 40

        result = await adapter.reset_torrent_options(info_hash_hex, key=None)

        assert result is False

    @pytest.mark.asyncio
    async def test_save_torrent_checkpoint_success(
        self, adapter, torrent_session, session_manager
    ):
        """Test saving checkpoint successfully."""
        session, info_hash_hex = torrent_session
        # Mock checkpoint controller
        session.checkpoint_controller = AsyncMock()
        session.checkpoint_controller.save_checkpoint_state = AsyncMock()

        result = await adapter.save_torrent_checkpoint(info_hash_hex)

        assert result is True
        session.checkpoint_controller.save_checkpoint_state.assert_called_once_with(
            session
        )

    @pytest.mark.asyncio
    async def test_save_torrent_checkpoint_no_controller(
        self, adapter, torrent_session, session_manager
    ):
        """Test saving checkpoint when controller not available."""
        session, info_hash_hex = torrent_session
        # Remove checkpoint controller
        if hasattr(session, "checkpoint_controller"):
            delattr(session, "checkpoint_controller")

        result = await adapter.save_torrent_checkpoint(info_hash_hex)

        assert result is False

    @pytest.mark.asyncio
    async def test_save_torrent_checkpoint_torrent_not_found(self, adapter):
        """Test saving checkpoint for non-existent torrent."""
        info_hash_hex = "a" * 40

        result = await adapter.save_torrent_checkpoint(info_hash_hex)

        assert result is False


class TestDaemonSessionAdapterConfig:
    """Test DaemonSessionAdapter config methods."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_set_torrent_option_delegates(self, adapter, mock_ipc_client):
        """Test set_torrent_option delegates to IPC client."""
        info_hash = "a" * 40
        key = "piece_selection"
        value = "sequential"

        mock_ipc_client.set_torrent_option = AsyncMock(return_value=True)

        result = await adapter.set_torrent_option(info_hash, key, value)

        assert result is True
        mock_ipc_client.set_torrent_option.assert_called_once_with(
            info_hash, key, value
        )

    @pytest.mark.asyncio
    async def test_get_torrent_option_delegates(self, adapter, mock_ipc_client):
        """Test get_torrent_option delegates to IPC client."""
        info_hash = "a" * 40
        key = "piece_selection"
        expected_value = "sequential"

        mock_ipc_client.get_torrent_option = AsyncMock(return_value=expected_value)

        result = await adapter.get_torrent_option(info_hash, key)

        assert result == expected_value
        mock_ipc_client.get_torrent_option.assert_called_once_with(info_hash, key)

    @pytest.mark.asyncio
    async def test_get_torrent_config_delegates(self, adapter, mock_ipc_client):
        """Test get_torrent_config delegates to IPC client."""
        info_hash = "a" * 40
        expected_config = {
            "options": {"piece_selection": "sequential"},
            "rate_limits": {"down_kib": 100, "up_kib": 50},
        }

        mock_ipc_client.get_torrent_config = AsyncMock(return_value=expected_config)

        result = await adapter.get_torrent_config(info_hash)

        assert result == expected_config
        mock_ipc_client.get_torrent_config.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_reset_torrent_options_delegates(self, adapter, mock_ipc_client):
        """Test reset_torrent_options delegates to IPC client."""
        info_hash = "a" * 40
        key = "piece_selection"

        mock_ipc_client.reset_torrent_options = AsyncMock(return_value=True)

        result = await adapter.reset_torrent_options(info_hash, key=key)

        assert result is True
        mock_ipc_client.reset_torrent_options.assert_called_once_with(
            info_hash, key=key
        )

    @pytest.mark.asyncio
    async def test_save_torrent_checkpoint_delegates(self, adapter, mock_ipc_client):
        """Test save_torrent_checkpoint delegates to IPC client."""
        info_hash = "a" * 40

        mock_ipc_client.save_torrent_checkpoint = AsyncMock(return_value=True)

        result = await adapter.save_torrent_checkpoint(info_hash)

        assert result is True
        mock_ipc_client.save_torrent_checkpoint.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_remove_torrent_delegates(self, adapter, mock_ipc_client):
        """Test remove_torrent delegates to IPC client."""
        info_hash = "a" * 40

        mock_ipc_client.remove_torrent = AsyncMock(return_value=True)

        result = await adapter.remove_torrent(info_hash)

        assert result is True
        mock_ipc_client.remove_torrent.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_remove_torrent_returns_false_when_not_found(self, adapter, mock_ipc_client):
        """Test remove_torrent returns False when torrent not found."""
        info_hash = "a" * 40

        mock_ipc_client.remove_torrent = AsyncMock(return_value=False)

        result = await adapter.remove_torrent(info_hash)

        assert result is False
        mock_ipc_client.remove_torrent.assert_called_once_with(info_hash)





