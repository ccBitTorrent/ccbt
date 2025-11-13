"""Test executor and IPC client alignment.

Verifies that executor, adapter, and IPC client work together correctly
with consistent parameter passing, error handling, and response types.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.daemon.ipc_client import IPCClient
from ccbt.daemon.ipc_protocol import TorrentAddRequest
from ccbt.executor.executor import UnifiedCommandExecutor
from ccbt.executor.session_adapter import DaemonSessionAdapter, LocalSessionAdapter
from ccbt.session.session import AsyncSessionManager


class TestResumeParameterFlow:
    """Test resume parameter flows through executor → adapter → IPC chain."""

    @pytest.mark.asyncio
    async def test_resume_parameter_through_daemon_adapter(self):
        """Test resume parameter passes through DaemonSessionAdapter to IPC client."""
        # Create mock IPC client
        mock_ipc_client = AsyncMock(spec=IPCClient)
        mock_ipc_client.add_torrent = AsyncMock(return_value="test_info_hash_hex")
        
        # Create adapter with mock IPC client
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        # Call add_torrent with resume=True
        result = await adapter.add_torrent(
            "test.torrent",
            output_dir="/test/output",
            resume=True,
        )
        
        # Verify IPC client was called with resume parameter
        mock_ipc_client.add_torrent.assert_called_once_with(
            "test.torrent",
            output_dir="/test/output",
            resume=True,
        )
        assert result == "test_info_hash_hex"

    @pytest.mark.asyncio
    async def test_resume_parameter_through_executor(self):
        """Test resume parameter flows through executor → adapter → IPC."""
        # Create mock IPC client
        mock_ipc_client = AsyncMock(spec=IPCClient)
        mock_ipc_client.add_torrent = AsyncMock(return_value="test_info_hash_hex")
        
        # Create adapter and executor
        adapter = DaemonSessionAdapter(mock_ipc_client)
        executor = UnifiedCommandExecutor(adapter)
        
        # Execute command with resume=True
        result = await executor.execute(
            "torrent.add",
            path_or_magnet="test.torrent",
            output_dir="/test/output",
            resume=True,
        )
        
        # Verify IPC client was called with resume parameter
        mock_ipc_client.add_torrent.assert_called_once_with(
            "test.torrent",
            output_dir="/test/output",
            resume=True,
        )
        assert result.success is True
        assert result.data["info_hash"] == "test_info_hash_hex"

    def test_torrent_add_request_includes_resume(self):
        """Test that TorrentAddRequest model includes resume field."""
        from ccbt.daemon.ipc_protocol import TorrentAddRequest
        
        # Create request with resume=True
        request = TorrentAddRequest(
            path_or_magnet="test.torrent",
            output_dir="/test/output",
            resume=True,
        )
        
        # Verify resume is included
        assert request.resume is True
        assert "resume" in request.model_dump()
        
        # Test default value
        request_default = TorrentAddRequest(path_or_magnet="test.torrent")
        assert request_default.resume is False


class TestGetScrapeResultFlow:
    """Test get_scrape_result flows through executor → adapter → IPC chain."""

    @pytest.mark.asyncio
    async def test_get_scrape_result_through_daemon_adapter(self):
        """Test get_scrape_result passes through DaemonSessionAdapter to IPC client."""
        from ccbt.daemon.ipc_protocol import ScrapeResult
        
        # Create mock scrape result
        mock_scrape_result = ScrapeResult(
            info_hash="test_info_hash",
            seeders=10,
            leechers=5,
            completed=100,
            last_scrape_time=1234567890.0,
            scrape_count=1,
        )
        
        # Create mock IPC client
        mock_ipc_client = AsyncMock(spec=IPCClient)
        mock_ipc_client.get_scrape_result = AsyncMock(return_value=mock_scrape_result)
        
        # Create adapter with mock IPC client
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        # Call get_scrape_result
        result = await adapter.get_scrape_result("test_info_hash")
        
        # Verify IPC client was called
        mock_ipc_client.get_scrape_result.assert_called_once_with("test_info_hash")
        assert result == mock_scrape_result
        assert result.seeders == 10

    @pytest.mark.asyncio
    async def test_get_scrape_result_not_found(self):
        """Test get_scrape_result returns None when not found."""
        # Create mock IPC client that returns None
        mock_ipc_client = AsyncMock(spec=IPCClient)
        mock_ipc_client.get_scrape_result = AsyncMock(return_value=None)
        
        # Create adapter with mock IPC client
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        # Call get_scrape_result
        result = await adapter.get_scrape_result("test_info_hash")
        
        # Verify result is None
        assert result is None
        mock_ipc_client.get_scrape_result.assert_called_once_with("test_info_hash")

    @pytest.mark.asyncio
    async def test_get_scrape_result_through_executor(self):
        """Test get_scrape_result flows through executor → adapter → IPC."""
        from ccbt.daemon.ipc_protocol import ScrapeResult
        
        # Create mock scrape result
        mock_scrape_result = ScrapeResult(
            info_hash="test_info_hash",
            seeders=10,
            leechers=5,
            completed=100,
            last_scrape_time=1234567890.0,
            scrape_count=1,
        )
        
        # Create mock IPC client
        mock_ipc_client = AsyncMock(spec=IPCClient)
        mock_ipc_client.get_scrape_result = AsyncMock(return_value=mock_scrape_result)
        
        # Create adapter and executor
        adapter = DaemonSessionAdapter(mock_ipc_client)
        executor = UnifiedCommandExecutor(adapter)
        
        # Execute command
        result = await executor.execute("scrape.get_result", info_hash="test_info_hash")
        
        # Verify IPC client was called
        mock_ipc_client.get_scrape_result.assert_called_once_with("test_info_hash")
        assert result.success is True
        assert result.data["result"] == mock_scrape_result


class TestInterfaceExecutorRouting:
    """Test interface executor routes commands through executor pattern."""

    @pytest.mark.asyncio
    async def test_interface_executor_uses_executor_for_pause(self):
        """Test interface executor routes pause command through executor."""
        from ccbt.interface.commands.executor import CommandExecutor
        from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
        
        # Create mock session (DaemonInterfaceAdapter)
        mock_session = MagicMock(spec=DaemonInterfaceAdapter)
        mock_session._client = AsyncMock(spec=IPCClient)
        
        # Create executor instance
        interface_executor = CommandExecutor(mock_session)
        
        # Mock the executor's execute method
        with patch.object(interface_executor._executor, 'execute') as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                data={"paused": True},
            )
            
            # Execute pause command
            success, message, result = await interface_executor.execute_command(
                "pause",
                [],
                current_info_hash="test_info_hash",
            )
            
            # Verify executor.execute was called with correct command
            mock_execute.assert_called_once_with(
                "torrent.pause",
                info_hash="test_info_hash",
            )
            assert success is True

    @pytest.mark.asyncio
    async def test_interface_executor_uses_executor_for_resume(self):
        """Test interface executor routes resume command through executor."""
        from ccbt.interface.commands.executor import CommandExecutor
        from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
        
        # Create mock session
        mock_session = MagicMock(spec=DaemonInterfaceAdapter)
        mock_session._client = AsyncMock(spec=IPCClient)
        
        # Create executor instance
        interface_executor = CommandExecutor(mock_session)
        
        # Mock the executor's execute method
        with patch.object(interface_executor._executor, 'execute') as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                data={"resumed": True},
            )
            
            # Execute resume command
            success, message, result = await interface_executor.execute_command(
                "resume",
                [],
                current_info_hash="test_info_hash",
            )
            
            # Verify executor.execute was called
            mock_execute.assert_called_once_with(
                "torrent.resume",
                info_hash="test_info_hash",
            )
            assert success is True

    @pytest.mark.asyncio
    async def test_interface_executor_uses_executor_for_remove(self):
        """Test interface executor routes remove command through executor."""
        from ccbt.interface.commands.executor import CommandExecutor
        from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
        
        # Create mock session
        mock_session = MagicMock(spec=DaemonInterfaceAdapter)
        mock_session._client = AsyncMock(spec=IPCClient)
        
        # Create executor instance
        interface_executor = CommandExecutor(mock_session)
        
        # Mock the executor's execute method
        with patch.object(interface_executor._executor, 'execute') as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                data={"removed": True},
            )
            
            # Execute remove command
            success, message, result = await interface_executor.execute_command(
                "remove",
                [],
                current_info_hash="test_info_hash",
            )
            
            # Verify executor.execute was called
            mock_execute.assert_called_once_with(
                "torrent.remove",
                info_hash="test_info_hash",
            )
            assert success is True


class TestErrorHandlingConsistency:
    """Test error handling is consistent across adapter methods."""

    @pytest.mark.asyncio
    async def test_set_rate_limits_raises_on_connection_error(self):
        """Test set_rate_limits raises RuntimeError on connection failure."""
        import aiohttp
        
        # Create mock IPC client that raises connection error
        mock_ipc_client = AsyncMock(spec=IPCClient)
        mock_ipc_client.set_rate_limits = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                "Connection refused",
                OSError("Connection refused"),
            )
        )
        
        # Create adapter
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        # Call set_rate_limits - should raise RuntimeError
        with pytest.raises(RuntimeError, match="Cannot connect to daemon"):
            await adapter.set_rate_limits("test_info_hash", 100, 50)

    @pytest.mark.asyncio
    async def test_force_announce_raises_on_connection_error(self):
        """Test force_announce raises RuntimeError on connection failure."""
        import aiohttp
        
        # Create mock IPC client that raises connection error
        mock_ipc_client = AsyncMock(spec=IPCClient)
        mock_ipc_client.force_announce = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                "Connection refused",
                OSError("Connection refused"),
            )
        )
        
        # Create adapter
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        # Call force_announce - should raise RuntimeError
        with pytest.raises(RuntimeError, match="Cannot connect to daemon"):
            await adapter.force_announce("test_info_hash")

    @pytest.mark.asyncio
    async def test_get_global_stats_raises_on_connection_error(self):
        """Test get_global_stats raises RuntimeError on connection failure."""
        import aiohttp
        
        # Create mock IPC client that raises connection error
        mock_ipc_client = AsyncMock(spec=IPCClient)
        mock_ipc_client.get_global_stats = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                "Connection refused",
                OSError("Connection refused"),
            )
        )
        
        # Create adapter
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        # Call get_global_stats - should raise RuntimeError
        with pytest.raises(RuntimeError, match="Cannot connect to daemon"):
            await adapter.get_global_stats()

    @pytest.mark.asyncio
    async def test_set_rate_limits_returns_false_on_404(self):
        """Test set_rate_limits returns False on 404 (torrent not found)."""
        import aiohttp
        
        # Create mock IPC client that returns 404
        mock_ipc_client = AsyncMock(spec=IPCClient)
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.message = "Not Found"
        mock_ipc_client.set_rate_limits = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=404,
                message="Not Found",
            )
        )
        
        # Create adapter
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        # Call set_rate_limits - should return False (not raise)
        result = await adapter.set_rate_limits("test_info_hash", 100, 50)
        assert result is False


class TestResponseConversion:
    """Test response conversion helpers work correctly."""

    def test_convert_peer_list_response(self):
        """Test _convert_peer_list_response helper method."""
        from ccbt.daemon.ipc_protocol import PeerInfo, PeerListResponse
        
        # Create mock peer list response
        peer_list_response = PeerListResponse(
            info_hash="test_info_hash",
            peers=[
                PeerInfo(
                    ip="192.168.1.1",
                    port=6881,
                    download_rate=1000.0,
                    upload_rate=500.0,
                    choked=False,
                    client="TestClient",
                ),
            ],
            count=1,
        )
        
        # Create adapter (we just need the method)
        mock_ipc_client = AsyncMock(spec=IPCClient)
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        # Convert response
        peers = adapter._convert_peer_list_response(peer_list_response)
        
        # Verify conversion
        assert len(peers) == 1
        assert peers[0]["ip"] == "192.168.1.1"
        assert peers[0]["port"] == 6881
        assert peers[0]["download_rate"] == 1000.0
        assert peers[0]["upload_rate"] == 500.0
        assert peers[0]["choked"] is False
        assert peers[0]["client"] == "TestClient"

    def test_convert_global_stats_response(self):
        """Test _convert_global_stats_response helper method."""
        from ccbt.daemon.ipc_protocol import GlobalStatsResponse
        
        # Create mock global stats response
        stats_response = GlobalStatsResponse(
            num_torrents=5,
            num_active=3,
            num_paused=2,
            total_download_rate=1000.0,
            total_upload_rate=500.0,
            total_downloaded=1000000,
            total_uploaded=500000,
            stats={"additional": "data"},
        )
        
        # Create adapter
        mock_ipc_client = AsyncMock(spec=IPCClient)
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        # Convert response
        stats = adapter._convert_global_stats_response(stats_response)
        
        # Verify conversion
        assert stats["num_torrents"] == 5
        assert stats["num_active"] == 3
        assert stats["num_paused"] == 2
        assert stats["download_rate"] == 1000.0
        assert stats["upload_rate"] == 500.0
        assert stats["total_downloaded"] == 1000000
        assert stats["total_uploaded"] == 500000
        assert stats["additional"] == "data"

