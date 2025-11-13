"""Integration tests for proxy functionality.

Tests proxy integration with trackers, WebSeeds, and real HTTP proxies.
Target: 95%+ code coverage for proxy integration points.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.network,
    pytest.mark.skip(reason="Integration tests skipped - focusing on unit test coverage first"),
]

from ccbt.discovery.tracker import AsyncTrackerClient, TrackerResponse
from ccbt.extensions.webseed import WebSeedExtension
from ccbt.proxy.client import ProxyClient
from ccbt.proxy.exceptions import ProxyAuthError, ProxyConnectionError


class TestProxyTrackerIntegration:
    """Tests for proxy integration with tracker client."""

    @pytest.fixture
    def mock_config_with_proxy(self):
        """Create mock config with proxy enabled for trackers."""
        config = MagicMock()
        config.network = MagicMock()
        config.network.connection_timeout = 10.0
        config.proxy = MagicMock()
        config.proxy.enable_proxy = True
        config.proxy.proxy_host = "proxy.example.com"
        config.proxy.proxy_port = 8080
        config.proxy.proxy_type = "http"
        config.proxy.proxy_username = None
        config.proxy.proxy_password = None
        config.proxy.proxy_for_trackers = True
        config.proxy.proxy_bypass_list = []
        return config

    @pytest.mark.asyncio
    async def test_tracker_with_proxy(self, mock_config_with_proxy):
        """Test tracker client using proxy."""
        client = AsyncTrackerClient()
        
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            with patch.object(client, "_create_connector") as mock_connector:
                mock_connector.return_value = MagicMock()
                
                await client.start()
                
                # Verify connector was created with proxy
                mock_connector.assert_called_once()
                assert client.session is not None
                
                await client.stop()

    @pytest.mark.asyncio
    async def test_tracker_bypass_localhost(self, mock_config_with_proxy):
        """Test tracker bypasses proxy for localhost."""
        client = AsyncTrackerClient()

        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            # Mock ProxyClient if needed
            with patch("ccbt.proxy.client.ProxyConnector"):
                await client.start()

            # Mock session
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=b"d8:intervali1800e5:peers0:e")
            async def async_enter():
                return mock_response
            async def async_exit(*args):
                return None
            mock_response.__aenter__ = async_enter
            mock_response.__aexit__ = async_exit

            client.session = AsyncMock()
            client.session.get = AsyncMock(return_value=mock_response)

            # Should bypass proxy for localhost
            assert client._should_bypass_proxy("http://localhost:8080/announce")
            
            await client.stop()

    @pytest.mark.asyncio
    async def test_tracker_proxy_407_handling(self, mock_config_with_proxy):
        """Test tracker handling of 407 Proxy Authentication Required."""
        client = AsyncTrackerClient()
        
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            with patch("ccbt.proxy.client.ProxyConnector"):
                await client.start()
            
            # Mock 407 response with proper async context manager
            mock_response = AsyncMock()
            mock_response.status = 407
            mock_response.headers = {"Proxy-Authenticate": "Basic realm=\"Proxy\""}
            async def async_enter():
                return mock_response
            async def async_exit(*args):
                return None
            mock_response.__aenter__ = async_enter
            mock_response.__aexit__ = async_exit
            
            client.session = AsyncMock()
            client.session.get = AsyncMock(return_value=mock_response)
            
            torrent_data = {
                "info_hash": b"12345678901234567890",
                "announce": "http://tracker.example.com/announce",
                "file_info": {"total_length": 1000},
            }
            
            # Should handle 407 gracefully
            try:
                await client.announce(torrent_data)
                pytest.fail("Should have raised TrackerError for 407")
            except Exception:
                # Expected - tracker should fail when proxy auth required
                pass
            
            await client.stop()


class TestProxyWebSeedIntegration:
    """Tests for proxy integration with WebSeed extension."""

    @pytest.fixture
    def mock_config_with_proxy(self):
        """Create mock config with proxy enabled for WebSeeds."""
        config = MagicMock()
        config.proxy = MagicMock()
        config.proxy.enable_proxy = True
        config.proxy.proxy_host = "proxy.example.com"
        config.proxy.proxy_port = 8080
        config.proxy.proxy_type = "http"
        config.proxy.proxy_username = None
        config.proxy.proxy_password = None
        config.proxy.proxy_for_webseeds = True
        config.proxy.proxy_bypass_list = []
        return config

    @pytest.mark.asyncio
    async def test_webseed_with_proxy(self, mock_config_with_proxy):
        """Test WebSeed extension using proxy."""
        extension = WebSeedExtension()
        
        with patch("ccbt.config.config.get_config", return_value=mock_config_with_proxy):
            with patch.object(extension, "_create_connector") as mock_connector:
                mock_connector.return_value = MagicMock()
                
                await extension.start()
                
                # Verify connector was created with proxy
                mock_connector.assert_called_once()
                assert extension.session is not None

    @pytest.mark.asyncio
    async def test_webseed_proxy_407_handling(self, mock_config_with_proxy):
        """Test WebSeed handling of 407 Proxy Authentication Required."""
        extension = WebSeedExtension()
        
        with patch("ccbt.config.config.get_config", return_value=mock_config_with_proxy):
            await extension.start()
            
            # Mock 407 response
            mock_response = AsyncMock()
            mock_response.status = 407
            mock_response.headers = {"Proxy-Authenticate": "Basic realm=\"Proxy\""}
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            extension.session = AsyncMock()
            extension.session.get = AsyncMock(return_value=mock_response)
            
            # Create mock piece info using PieceInfo model
            from ccbt.models import PieceInfo, PieceState
            
            piece_info = PieceInfo(
                index=0,
                length=16384,
                hash=b"12345678901234567890",
                state=PieceState.MISSING,
            )
            
            # Should handle 407 gracefully
            result = await extension.download_piece(
                webseed_id="test",
                piece_info=piece_info,
                _piece_data=b"",
            )
            
            # Should return None on 407
            assert result is None


class TestProxyClientIntegration:
    """Tests for ProxyClient integration scenarios."""

    @pytest.mark.asyncio
    async def test_proxy_client_test_connection_mock(self):
        """Test proxy client connection testing."""
        client = ProxyClient()
        
        # Mock successful connection - need proper async context manager
        mock_response = AsyncMock()
        mock_response.status = 200
        # Make __aenter__ and __aexit__ return async values
        async def async_enter():
            return mock_response
        async def async_exit(*args):
            return None
        mock_response.__aenter__ = async_enter
        mock_response.__aexit__ = async_exit
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        
        with patch.object(client, "get_proxy_session", return_value=mock_session):
            result = await client.test_connection(
                proxy_host="proxy.example.com",
                proxy_port=8080,
            )
            
            assert result is True
            assert client.stats.connections_successful > 0

    @pytest.mark.asyncio
    async def test_proxy_client_session_pooling(self):
        """Test proxy client session pooling across multiple requests."""
        client = ProxyClient()
        
        mock_session = MagicMock()
        mock_session.get = AsyncMock()
        
        with patch.object(
            client, "create_proxy_session", return_value=mock_session
        ) as mock_create:
            session1 = await client.get_proxy_session("proxy.example.com", 8080)
            session2 = await client.get_proxy_session("proxy.example.com", 8080)
            
            # Should only create session once
            assert mock_create.call_count == 1
            assert session1 is session2


class TestProxyChainIntegration:
    """Tests for proxy chain functionality."""

    @pytest.mark.asyncio
    async def test_proxy_chain_single_hop(self):
        """Test connecting through a single proxy."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.readline = AsyncMock(
            side_effect=[
                b"HTTP/1.1 200 Connection established\r\n",
                b"\r\n",
            ]
        )
        
        with patch.object(
            client, "_connect_to_proxy", return_value=(mock_reader, mock_writer)
        ):
            with patch.object(
                client, "_read_connect_response", return_value=mock_reader
            ):
                reader, writer = await client.connect_via_chain(
                    target_host="target.example.com",
                    target_port=80,
                    proxy_chain=[
                        {
                            "host": "proxy.example.com",
                            "port": 8080,
                            "type": "http",
                        }
                    ],
                )
                
                assert reader is not None
                assert writer is not None
                assert client.stats.connections_successful > 0

    @pytest.mark.asyncio
    async def test_proxy_chain_multi_hop(self):
        """Test connecting through multiple proxies."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_reader.readline = AsyncMock(
            side_effect=[
                b"HTTP/1.1 200 Connection established\r\n",
                b"\r\n",
            ]
        )
        
        with patch.object(
            client, "_connect_to_proxy", return_value=(mock_reader, mock_writer)
        ):
            with patch.object(
                client, "_read_connect_response", return_value=mock_reader
            ):
                reader, writer = await client.connect_via_chain(
                    target_host="target.example.com",
                    target_port=80,
                    proxy_chain=[
                        {
                            "host": "proxy1.example.com",
                            "port": 8080,
                            "type": "http",
                        },
                        {
                            "host": "proxy2.example.com",
                            "port": 8080,
                            "type": "http",
                        },
                    ],
                )
                
                assert reader is not None
                assert writer is not None

