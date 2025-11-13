"""Additional tests for proxy client to improve coverage.

Targets missing coverage paths in ccbt/proxy/client.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.network]

from ccbt.proxy.client import ProxyClient
from ccbt.proxy.exceptions import ProxyError

# Check for aiohttp ProxyConnector availability
try:
    from aiohttp import ProxyConnector

    HAS_PROXY_CONNECTOR = ProxyConnector is not None
except (ImportError, AttributeError):
    HAS_PROXY_CONNECTOR = False

# Check for aiohttp-socks
try:
    from aiohttp_socks import ProxyConnector as SocksProxyConnector  # type: ignore[import-untyped]
    from aiohttp_socks import ProxyType

    HAS_SOCKS = True
except ImportError:
    HAS_SOCKS = False
    SocksProxyConnector = None  # type: ignore[assignment, misc]
    ProxyType = None  # type: ignore[assignment, misc]


class TestProxyClientSOCKS:
    """Tests for SOCKS proxy connector creation."""

    @pytest.mark.skipif(not HAS_SOCKS, reason="aiohttp-socks not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_socks4_coverage(self):
        """Test creating SOCKS4 connector (coverage for lines 142-145)."""
        client = ProxyClient()
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=1080,
            proxy_type="socks4",
        )
        assert connector is not None
        await connector.close()

    @pytest.mark.skipif(not HAS_SOCKS, reason="aiohttp-socks not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_socks5_coverage(self):
        """Test creating SOCKS5 connector (coverage for lines 145-150)."""
        client = ProxyClient()
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=1080,
            proxy_type="socks5",
            proxy_username="user",
            proxy_password="pass",
        )
        assert connector is not None
        await connector.close()


class TestProxyClientSOCKSWithoutLibrary:
    """Tests for SOCKS when library not available."""

    def test_socks4_without_library_error_path(self):
        """Test SOCKS4 raises error when library unavailable (line 30-31 coverage)."""
        client = ProxyClient()
        with patch("ccbt.proxy.client.SOCKS_AVAILABLE", False):
            with pytest.raises(ProxyError) as exc_info:
                client.create_proxy_connector(
                    proxy_host="proxy.example.com",
                    proxy_port=1080,
                    proxy_type="socks4",
                )
            assert "aiohttp-socks" in str(exc_info.value)

    def test_socks5_without_library_error_path(self):
        """Test SOCKS5 raises error when library unavailable."""
        client = ProxyClient()
        with patch("ccbt.proxy.client.SOCKS_AVAILABLE", False):
            with pytest.raises(ProxyError) as exc_info:
                client.create_proxy_connector(
                    proxy_host="proxy.example.com",
                    proxy_port=1080,
                    proxy_type="socks5",
                )
            assert "aiohttp-socks" in str(exc_info.value)


class TestProxyClientHTTPWithoutConnector:
    """Tests for HTTP proxy when ProxyConnector unavailable."""

    def test_create_proxy_connector_http_no_connector(self):
        """Test HTTP proxy raises error when ProxyConnector unavailable."""
        client = ProxyClient()
        with patch("ccbt.proxy.client.ProxyConnector", None):
            with pytest.raises(ProxyError) as exc_info:
                client.create_proxy_connector(
                    proxy_host="proxy.example.com",
                    proxy_port=8080,
                    proxy_type="http",
                )
            assert "ProxyConnector" in str(exc_info.value)


class TestProxyClientSessionEdgeCases:
    """Tests for session management edge cases."""

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    def test_create_proxy_session_no_timeout(self):
        """Test create_proxy_session without timeout (coverage for lines 209-213)."""
        client = ProxyClient()
        session = client.create_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
        )
        assert session is not None
        # Close to avoid resource warnings
        asyncio.run(session.close())


class TestProxyClientTestConnectionCoverage:
    """Tests for test_connection method coverage."""

    @pytest.mark.asyncio
    async def test_test_connection_non_200_status(self):
        """Test test_connection with non-200 status (coverage for lines 284-287)."""
        client = ProxyClient()
        
        # Mock response with 404 status
        mock_response = AsyncMock()
        mock_response.status = 404
        
        class AsyncContextManager:
            async def __aenter__(self):
                return mock_response
            async def __aexit__(self, *args):
                return None
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=AsyncContextManager())
        
        with patch.object(client, "get_proxy_session", return_value=mock_session):
            result = await client.test_connection(
                proxy_host="proxy.example.com",
                proxy_port=8080,
            )
            
            assert result is False
            assert client.stats.connections_failed > 0

    @pytest.mark.asyncio
    async def test_test_connection_generic_exception(self):
        """Test test_connection with generic exception (coverage for lines 297-300)."""
        client = ProxyClient()
        
        with patch.object(
            client, "get_proxy_session", side_effect=Exception("Generic error")
        ):
            result = await client.test_connection(
                proxy_host="proxy.example.com",
                proxy_port=8080,
            )
            
            assert result is False
            assert client.stats.connections_failed > 0


class TestProxyClientCleanupCoverage:
    """Tests for cleanup method coverage."""

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_cleanup_exception_logging(self):
        """Test cleanup logs exceptions (coverage for line 308-314)."""
        client = ProxyClient()
        
        # Create a session that raises on close
        mock_session = AsyncMock()
        mock_session.close = AsyncMock(side_effect=Exception("Close error"))
        
        client._pools["test:8080"] = mock_session
        
        with patch("ccbt.proxy.client.logger") as mock_logger:
            await client.cleanup()
            # Should log warning
            mock_logger.warning.assert_called()
            # Pool should be removed
            assert "test:8080" not in client._pools


class TestProxyClientConnectViaChainCoverage:
    """Tests for connect_via_chain edge cases."""

    @pytest.mark.asyncio
    async def test_connect_via_chain_connection_lost_during_chain(self):
        """Test connect_via_chain when connection lost during chain."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=Exception("Connection lost"))
        
        with patch.object(
            client, "_connect_to_proxy", return_value=(mock_reader, mock_writer)
        ):
            with pytest.raises(Exception):  # Should raise ProxyConnectionError or similar
                await client.connect_via_chain(
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

    @pytest.mark.asyncio
    async def test_connect_via_chain_read_response_error(self):
        """Test connect_via_chain when reading response returns None."""
        from ccbt.proxy.exceptions import ProxyConnectionError
        
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        
        # Mock _read_connect_response to return None (simulating failure)
        with patch.object(
            client, "_connect_to_proxy", return_value=(mock_reader, mock_writer)
        ):
            with patch.object(
                client, "_read_connect_response", return_value=None
            ):
                # Should handle None response and raise ProxyConnectionError
                with pytest.raises(ProxyConnectionError):
                    await client.connect_via_chain(
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

    @pytest.mark.asyncio
    async def test_connect_via_chain_send_request_error(self):
        """Test connect_via_chain when sending CONNECT request fails."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock(side_effect=Exception("Write error"))
        mock_writer.drain = AsyncMock()
        
        with patch.object(
            client, "_connect_to_proxy", return_value=(mock_reader, mock_writer)
        ):
            with pytest.raises(Exception):
                await client.connect_via_chain(
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

