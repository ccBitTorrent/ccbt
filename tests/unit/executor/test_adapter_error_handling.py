"""Unit tests for adapter error handling and response conversions."""

from __future__ import annotations

import aiohttp
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.daemon.ipc_protocol import GlobalStatsResponse, PeerInfo, PeerListResponse
from ccbt.executor.session_adapter import DaemonSessionAdapter


class TestDaemonSessionAdapterErrorHandling:
    """Test error handling in DaemonSessionAdapter methods."""

    @pytest.mark.asyncio
    async def test_set_rate_limits_connection_error(self):
        """Test set_rate_limits raises RuntimeError on connection failure."""
        mock_ipc_client = AsyncMock()
        mock_ipc_client.set_rate_limits = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                "Connection refused",
                OSError("Connection refused"),
            )
        )
        
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        with pytest.raises(RuntimeError, match="Cannot connect to daemon"):
            await adapter.set_rate_limits("test_hash", 100, 50)

    @pytest.mark.asyncio
    async def test_set_rate_limits_404_returns_false(self):
        """Test set_rate_limits returns False on 404."""
        mock_ipc_client = AsyncMock()
        mock_ipc_client.set_rate_limits = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=404,
                message="Not Found",
            )
        )
        
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        result = await adapter.set_rate_limits("test_hash", 100, 50)
        assert result is False

    @pytest.mark.asyncio
    async def test_set_rate_limits_other_http_error_raises(self):
        """Test set_rate_limits raises on non-404 HTTP errors."""
        mock_ipc_client = AsyncMock()
        mock_ipc_client.set_rate_limits = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=500,
                message="Internal Server Error",
            )
        )
        
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        with pytest.raises(RuntimeError, match="Daemon error"):
            await adapter.set_rate_limits("test_hash", 100, 50)

    @pytest.mark.asyncio
    async def test_force_announce_connection_error(self):
        """Test force_announce raises RuntimeError on connection failure."""
        mock_ipc_client = AsyncMock()
        mock_ipc_client.force_announce = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                "Connection refused",
                OSError("Connection refused"),
            )
        )
        
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        with pytest.raises(RuntimeError, match="Cannot connect to daemon"):
            await adapter.force_announce("test_hash")

    @pytest.mark.asyncio
    async def test_get_global_stats_connection_error(self):
        """Test get_global_stats raises RuntimeError on connection failure."""
        mock_ipc_client = AsyncMock()
        mock_ipc_client.get_global_stats = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                "Connection refused",
                OSError("Connection refused"),
            )
        )
        
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        with pytest.raises(RuntimeError, match="Cannot connect to daemon"):
            await adapter.get_global_stats()

    @pytest.mark.asyncio
    async def test_get_scrape_result_connection_error(self):
        """Test get_scrape_result raises RuntimeError on connection failure."""
        mock_ipc_client = AsyncMock()
        mock_ipc_client.get_scrape_result = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                "Connection refused",
                OSError("Connection refused"),
            )
        )
        
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        with pytest.raises(RuntimeError, match="Cannot connect to daemon"):
            await adapter.get_scrape_result("test_hash")

    @pytest.mark.asyncio
    async def test_get_scrape_result_404_returns_none(self):
        """Test get_scrape_result returns None on 404."""
        mock_ipc_client = AsyncMock()
        mock_ipc_client.get_scrape_result = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=404,
                message="Not Found",
            )
        )
        
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        result = await adapter.get_scrape_result("test_hash")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_peers_for_torrent_connection_error(self):
        """Test get_peers_for_torrent raises RuntimeError on connection failure."""
        mock_ipc_client = AsyncMock()
        mock_ipc_client.get_peers_for_torrent = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                "Connection refused",
                OSError("Connection refused"),
            )
        )
        
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        with pytest.raises(RuntimeError, match="Cannot connect to daemon"):
            await adapter.get_peers_for_torrent("test_hash")

    @pytest.mark.asyncio
    async def test_get_peers_for_torrent_404_returns_empty_list(self):
        """Test get_peers_for_torrent returns empty list on 404."""
        mock_ipc_client = AsyncMock()
        mock_ipc_client.get_peers_for_torrent = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=404,
                message="Not Found",
            )
        )
        
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        result = await adapter.get_peers_for_torrent("test_hash")
        assert result == []


class TestResponseConversionHelpers:
    """Test response conversion helper methods."""

    def test_convert_peer_list_response(self):
        """Test _convert_peer_list_response converts PeerListResponse correctly."""
        peer_list_response = PeerListResponse(
            info_hash="test_hash",
            peers=[
                PeerInfo(
                    ip="192.168.1.1",
                    port=6881,
                    download_rate=1000.0,
                    upload_rate=500.0,
                    choked=False,
                    client="TestClient",
                ),
                PeerInfo(
                    ip="192.168.1.2",
                    port=6882,
                    download_rate=2000.0,
                    upload_rate=1000.0,
                    choked=True,
                    client=None,
                ),
            ],
            count=2,
        )
        
        mock_ipc_client = AsyncMock()
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        peers = adapter._convert_peer_list_response(peer_list_response)
        
        assert len(peers) == 2
        assert peers[0]["ip"] == "192.168.1.1"
        assert peers[0]["port"] == 6881
        assert peers[0]["download_rate"] == 1000.0
        assert peers[0]["upload_rate"] == 500.0
        assert peers[0]["choked"] is False
        assert peers[0]["client"] == "TestClient"
        
        assert peers[1]["ip"] == "192.168.1.2"
        assert peers[1]["port"] == 6882
        assert peers[1]["download_rate"] == 2000.0
        assert peers[1]["upload_rate"] == 1000.0
        assert peers[1]["choked"] is True
        assert peers[1]["client"] is None

    def test_convert_global_stats_response(self):
        """Test _convert_global_stats_response converts GlobalStatsResponse correctly."""
        stats_response = GlobalStatsResponse(
            num_torrents=10,
            num_active=7,
            num_paused=3,
            total_download_rate=5000.0,
            total_upload_rate=2500.0,
            total_downloaded=5000000,
            total_uploaded=2500000,
            stats={
                "additional_field": "value",
                "another_field": 123,
            },
        )
        
        mock_ipc_client = AsyncMock()
        adapter = DaemonSessionAdapter(mock_ipc_client)
        
        stats = adapter._convert_global_stats_response(stats_response)
        
        assert stats["num_torrents"] == 10
        assert stats["num_active"] == 7
        assert stats["num_paused"] == 3
        assert stats["download_rate"] == 5000.0
        assert stats["upload_rate"] == 2500.0
        assert stats["total_downloaded"] == 5000000
        assert stats["total_uploaded"] == 2500000
        assert stats["additional_field"] == "value"
        assert stats["another_field"] == 123

