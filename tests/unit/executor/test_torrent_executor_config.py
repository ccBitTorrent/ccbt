"""Unit tests for TorrentExecutor config commands.

Tests the new torrent configuration commands:
- torrent.set_option
- torrent.get_option
- torrent.get_config
- torrent.reset_options
- torrent.save_checkpoint
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.executor.base import CommandResult
from ccbt.executor.torrent_executor import TorrentExecutor

pytestmark = [pytest.mark.unit, pytest.mark.executor]


class TestTorrentExecutorConfigCommands:
    """Test TorrentExecutor config commands."""

    @pytest.fixture
    def mock_adapter(self):
        """Create mock session adapter."""
        adapter = AsyncMock()
        return adapter

    @pytest.fixture
    def executor(self, mock_adapter):
        """Create TorrentExecutor with mocked adapter."""
        # Add session_manager to mock_adapter to simulate LocalSessionAdapter
        mock_session_manager = MagicMock()
        # Add torrents dict with a dummy torrent for testing (using "a" * 40 as hex)
        mock_session_manager.torrents = {bytes.fromhex("a" * 40): MagicMock()}
        mock_session_manager.lock = AsyncMock()
        mock_session_manager.lock.__aenter__.return_value = None
        mock_session_manager.lock.__aexit__.return_value = None
        mock_adapter.session_manager = mock_session_manager
        return TorrentExecutor(mock_adapter)

    @pytest.mark.asyncio
    async def test_set_torrent_option_success(self, executor, mock_adapter):
        """Test successful option setting."""
        info_hash = "a" * 40
        key = "piece_selection"
        value = "sequential"

        mock_adapter.set_torrent_option = AsyncMock(return_value=True)

        result = await executor.execute(
            "torrent.set_option",
            info_hash=info_hash,
            key=key,
            value=value,
        )

        assert result.success is True
        assert result.data["set"] is True
        assert result.data["key"] == key
        assert result.data["value"] == value
        mock_adapter.set_torrent_option.assert_called_once_with(
            info_hash, key, value
        )

    @pytest.mark.asyncio
    async def test_set_torrent_option_failure(self, executor, mock_adapter):
        """Test option setting failure."""
        info_hash = "a" * 40
        key = "piece_selection"
        value = "sequential"

        mock_adapter.set_torrent_option = AsyncMock(return_value=False)

        result = await executor.execute(
            "torrent.set_option",
            info_hash=info_hash,
            key=key,
            value=value,
        )

        assert result.success is False
        assert result.data["set"] is False

    @pytest.mark.asyncio
    async def test_set_torrent_option_error(self, executor, mock_adapter):
        """Test option setting with exception."""
        info_hash = "a" * 40
        key = "piece_selection"
        value = "sequential"

        mock_adapter.set_torrent_option = AsyncMock(
            side_effect=Exception("Torrent not found")
        )

        result = await executor.execute(
            "torrent.set_option",
            info_hash=info_hash,
            key=key,
            value=value,
        )

        assert result.success is False
        assert "Torrent not found" in result.error

    @pytest.mark.asyncio
    async def test_get_torrent_option_success(self, executor, mock_adapter):
        """Test successful option retrieval."""
        info_hash = "a" * 40
        key = "piece_selection"
        expected_value = "sequential"

        mock_adapter.get_torrent_option = AsyncMock(return_value=expected_value)

        result = await executor.execute(
            "torrent.get_option",
            info_hash=info_hash,
            key=key,
        )

        assert result.success is True
        assert result.data["key"] == key
        assert result.data["value"] == expected_value
        mock_adapter.get_torrent_option.assert_called_once_with(info_hash, key)

    @pytest.mark.asyncio
    async def test_get_torrent_option_not_set(self, executor, mock_adapter):
        """Test getting option that is not set."""
        info_hash = "a" * 40
        key = "piece_selection"

        mock_adapter.get_torrent_option = AsyncMock(return_value=None)

        result = await executor.execute(
            "torrent.get_option",
            info_hash=info_hash,
            key=key,
        )

        assert result.success is True
        assert result.data["key"] == key
        assert result.data["value"] is None

    @pytest.mark.asyncio
    async def test_get_torrent_option_error(self, executor, mock_adapter):
        """Test getting option with exception."""
        info_hash = "a" * 40
        key = "piece_selection"

        mock_adapter.get_torrent_option = AsyncMock(
            side_effect=Exception("Torrent not found")
        )

        result = await executor.execute(
            "torrent.get_option",
            info_hash=info_hash,
            key=key,
        )

        assert result.success is False
        assert "Torrent not found" in result.error

    @pytest.mark.asyncio
    async def test_get_torrent_config_success(self, executor, mock_adapter):
        """Test successful config retrieval."""
        info_hash = "a" * 40
        expected_config = {
            "options": {
                "piece_selection": "sequential",
                "streaming_mode": True,
            },
            "rate_limits": {
                "down_kib": 100,
                "up_kib": 50,
            },
        }

        mock_adapter.get_torrent_config = AsyncMock(return_value=expected_config)

        result = await executor.execute(
            "torrent.get_config",
            info_hash=info_hash,
        )

        assert result.success is True
        assert result.data == expected_config
        mock_adapter.get_torrent_config.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_get_torrent_config_empty(self, executor, mock_adapter):
        """Test getting config for torrent with no options."""
        info_hash = "a" * 40
        expected_config = {"options": {}, "rate_limits": {}}

        mock_adapter.get_torrent_config = AsyncMock(return_value=expected_config)

        result = await executor.execute(
            "torrent.get_config",
            info_hash=info_hash,
        )

        assert result.success is True
        assert result.data == expected_config

    @pytest.mark.asyncio
    async def test_get_torrent_config_error(self, executor, mock_adapter):
        """Test getting config with exception."""
        info_hash = "a" * 40

        mock_adapter.get_torrent_config = AsyncMock(
            side_effect=Exception("Torrent not found")
        )

        result = await executor.execute(
            "torrent.get_config",
            info_hash=info_hash,
        )

        assert result.success is False
        assert "Torrent not found" in result.error

    @pytest.mark.asyncio
    async def test_reset_torrent_options_all_success(self, executor, mock_adapter):
        """Test successful reset of all options."""
        info_hash = "a" * 40

        mock_adapter.reset_torrent_options = AsyncMock(return_value=True)

        result = await executor.execute(
            "torrent.reset_options",
            info_hash=info_hash,
            key=None,
        )

        assert result.success is True
        assert result.data["reset"] is True
        assert result.data["key"] is None
        mock_adapter.reset_torrent_options.assert_called_once_with(
            info_hash, key=None
        )

    @pytest.mark.asyncio
    async def test_reset_torrent_options_single_key_success(
        self, executor, mock_adapter
    ):
        """Test successful reset of single option."""
        info_hash = "a" * 40
        key = "piece_selection"

        mock_adapter.reset_torrent_options = AsyncMock(return_value=True)

        result = await executor.execute(
            "torrent.reset_options",
            info_hash=info_hash,
            key=key,
        )

        assert result.success is True
        assert result.data["reset"] is True
        assert result.data["key"] == key
        mock_adapter.reset_torrent_options.assert_called_once_with(
            info_hash, key=key
        )

    @pytest.mark.asyncio
    async def test_reset_torrent_options_failure(self, executor, mock_adapter):
        """Test reset options failure."""
        info_hash = "a" * 40

        mock_adapter.reset_torrent_options = AsyncMock(return_value=False)

        result = await executor.execute(
            "torrent.reset_options",
            info_hash=info_hash,
            key=None,
        )

        assert result.success is False
        assert result.data["reset"] is False

    @pytest.mark.asyncio
    async def test_reset_torrent_options_error(self, executor, mock_adapter):
        """Test reset options with exception."""
        info_hash = "a" * 40

        mock_adapter.reset_torrent_options = AsyncMock(
            side_effect=Exception("Torrent not found")
        )

        result = await executor.execute(
            "torrent.reset_options",
            info_hash=info_hash,
            key=None,
        )

        assert result.success is False
        assert "Torrent not found" in result.error

    @pytest.mark.asyncio
    async def test_save_torrent_checkpoint_success(self, executor, mock_adapter):
        """Test successful checkpoint save."""
        info_hash = "a" * 40

        mock_adapter.save_torrent_checkpoint = AsyncMock(return_value=True)

        result = await executor.execute(
            "torrent.save_checkpoint",
            info_hash=info_hash,
        )

        assert result.success is True
        assert result.data["saved"] is True
        mock_adapter.save_torrent_checkpoint.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_save_torrent_checkpoint_failure(self, executor, mock_adapter):
        """Test checkpoint save failure."""
        info_hash = "a" * 40

        mock_adapter.save_torrent_checkpoint = AsyncMock(return_value=False)

        result = await executor.execute(
            "torrent.save_checkpoint",
            info_hash=info_hash,
        )

        assert result.success is False
        assert result.data["saved"] is False

    @pytest.mark.asyncio
    async def test_save_torrent_checkpoint_error(self, executor, mock_adapter):
        """Test checkpoint save with exception."""
        info_hash = "a" * 40

        mock_adapter.save_torrent_checkpoint = AsyncMock(
            side_effect=Exception("Torrent not found")
        )

        result = await executor.execute(
            "torrent.save_checkpoint",
            info_hash=info_hash,
        )

        assert result.success is False
        assert "Torrent not found" in result.error

    @pytest.mark.asyncio
    async def test_unknown_command(self, executor):
        """Test unknown command returns error."""
        result = await executor.execute("torrent.unknown_command")

        assert result.success is False
        assert "Unknown torrent command" in result.error

