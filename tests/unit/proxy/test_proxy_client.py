"""Unit tests for proxy client.

Tests proxy client functionality including CONNECT, pooling, errors, and statistics.
Target: 95%+ code coverage for ccbt/proxy/client.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.network]

from ccbt.proxy.client import ProxyClient, ProxyStats
from ccbt.proxy.exceptions import (
    ProxyAuthError,
    ProxyConnectionError,
    ProxyError,
    ProxyTimeoutError,
)
from ccbt.proxy.client import ProxyStats

# Check for aiohttp ProxyConnector availability
try:
    from aiohttp import ProxyConnector

    HAS_PROXY_CONNECTOR = ProxyConnector is not None
except (ImportError, AttributeError):
    HAS_PROXY_CONNECTOR = False

# Check for aiohttp-socks
try:
    from aiohttp_socks import ProxyConnector as SocksProxyConnector  # type: ignore[import-untyped]

    HAS_SOCKS = True
except ImportError:
    HAS_SOCKS = False
    SocksProxyConnector = None  # type: ignore[assignment, misc]


class TestProxyStats:
    """Tests for ProxyStats dataclass."""

    def test_proxy_stats_default(self):
        """Test ProxyStats with default values."""
        stats = ProxyStats()
        assert stats.connections_total == 0
        assert stats.connections_successful == 0
        assert stats.connections_failed == 0
        assert stats.auth_failures == 0
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0
        assert stats.timeouts == 0

    def test_proxy_stats_custom(self):
        """Test ProxyStats with custom values."""
        stats = ProxyStats(
            connections_total=10,
            connections_successful=8,
            connections_failed=2,
            auth_failures=1,
            bytes_sent=1024,
            bytes_received=2048,
            timeouts=1,
        )
        assert stats.connections_total == 10
        assert stats.connections_successful == 8
        assert stats.connections_failed == 2
        assert stats.auth_failures == 1
        assert stats.bytes_sent == 1024
        assert stats.bytes_received == 2048
        assert stats.timeouts == 1


class TestProxyClientInitialization:
    """Tests for ProxyClient initialization."""

    def test_proxy_client_init_default(self):
        """Test ProxyClient initialization with defaults."""
        client = ProxyClient()
        assert client.default_timeout == 30.0
        assert client.max_retries == 3
        assert client._pools == {}
        assert isinstance(client.stats, ProxyStats)

    def test_proxy_client_init_custom(self):
        """Test ProxyClient initialization with custom values."""
        client = ProxyClient(default_timeout=60.0, max_retries=5)
        assert client.default_timeout == 60.0
        assert client.max_retries == 5


class TestBuildProxyUrl:
    """Tests for _build_proxy_url method."""

    def test_build_proxy_url_no_auth(self):
        """Test building proxy URL without authentication."""
        client = ProxyClient()
        url = client._build_proxy_url("proxy.example.com", 8080)
        assert url == "http://proxy.example.com:8080"

    def test_build_proxy_url_with_auth(self):
        """Test building proxy URL with authentication."""
        client = ProxyClient()
        url = client._build_proxy_url(
            "proxy.example.com", 8080, "user", "pass"
        )
        assert url == "http://user:pass@proxy.example.com:8080"

    def test_build_proxy_url_special_chars(self):
        """Test building proxy URL with special characters in credentials."""
        client = ProxyClient()
        url = client._build_proxy_url(
            "proxy.example.com", 8080, "user@domain", "p@ss:w0rd"
        )
        assert "user@domain" in url
        assert "p@ss:w0rd" in url


class TestCreateProxyConnector:
    """Tests for create_proxy_connector method."""

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_http_no_auth(self):
        """Test creating HTTP proxy connector without auth."""
        client = ProxyClient()
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=8080,
            proxy_type="http",
        )
        assert connector is not None

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_http_with_auth(self):
        """Test creating HTTP proxy connector with auth."""
        client = ProxyClient()
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=8080,
            proxy_type="http",
            proxy_username="user",
            proxy_password="pass",
        )
        assert connector is not None

    @pytest.mark.skipif(not HAS_SOCKS, reason="aiohttp-socks not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_socks4(self):
        """Test creating SOCKS4 proxy connector."""
        client = ProxyClient()
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=1080,
            proxy_type="socks4",
        )
        assert connector is not None

    @pytest.mark.skipif(not HAS_SOCKS, reason="aiohttp-socks not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_socks5(self):
        """Test creating SOCKS5 proxy connector."""
        client = ProxyClient()
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=1080,
            proxy_type="socks5",
            proxy_username="user",
            proxy_password="pass",
        )
        assert connector is not None

    @pytest.mark.asyncio
    async def test_create_proxy_connector_socks_without_library(self):
        """Test creating SOCKS connector without aiohttp-socks."""
        client = ProxyClient()
        with patch("ccbt.proxy.client.SOCKS_AVAILABLE", False):
            with pytest.raises(ProxyError) as exc_info:
                client.create_proxy_connector(
                    proxy_host="proxy.example.com",
                    proxy_port=1080,
                    proxy_type="socks5",
                )
            assert "aiohttp-socks" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_proxy_connector_invalid_type(self):
        """Test creating connector with invalid proxy type."""
        client = ProxyClient()
        with pytest.raises(ProxyError):
            client.create_proxy_connector(
                proxy_host="proxy.example.com",
                proxy_port=8080,
                proxy_type="invalid",
            )

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_default(self):
        """Test creating connector with default type."""
        client = ProxyClient()
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=8080,
            proxy_type="http",
        )
        assert connector is not None


class TestProxySessionManagement:
    """Tests for proxy session creation and pooling."""

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_create_proxy_session(self):
        """Test creating a proxy session."""
        client = ProxyClient()
        session = client.create_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
        )
        assert session is not None
        await session.close()

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_get_proxy_session_pooling(self):
        """Test proxy session pooling."""
        client = ProxyClient()
        
        session1 = await client.get_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
        )
        
        session2 = await client.get_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
        )
        
        # Should return same session (pooled)
        assert session1 is session2
        
        await client.cleanup()

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_get_proxy_session_different_proxies(self):
        """Test that different proxies get different sessions."""
        client = ProxyClient()
        
        session1 = await client.get_proxy_session(
            proxy_host="proxy1.example.com",
            proxy_port=8080,
        )
        
        session2 = await client.get_proxy_session(
            proxy_host="proxy2.example.com",
            proxy_port=8080,
        )
        
        # Should be different sessions
        assert session1 is not session2
        
        await client.cleanup()

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test cleaning up proxy connection pools."""
        client = ProxyClient()
        
        # Create some sessions
        await client.get_proxy_session("proxy1.example.com", 8080)
        await client.get_proxy_session("proxy2.example.com", 8080)
        
        assert len(client._pools) == 2
        
        # Cleanup
        await client.cleanup()
        
        assert len(client._pools) == 0


class TestConnectViaChain:
    """Tests for connect_via_chain method."""

    @pytest.mark.asyncio
    async def test_connect_via_chain_empty(self):
        """Test connecting with empty chain."""
        client = ProxyClient()
        with pytest.raises(ProxyError, match="cannot be empty"):
            await client.connect_via_chain(
                target_host="target.example.com",
                target_port=80,
                proxy_chain=[],
            )

    @pytest.mark.asyncio
    async def test_connect_via_chain_circular(self):
        """Test connecting with circular proxy chain."""
        client = ProxyClient()
        chain = [
            {"host": "proxy1.example.com", "port": 8080, "type": "http"},
            {"host": "proxy1.example.com", "port": 8080, "type": "http"},
        ]
        with pytest.raises(ProxyError, match="Circular reference"):
            await client.connect_via_chain(
                target_host="target.example.com",
                target_port=80,
                proxy_chain=chain,
            )

    @pytest.mark.asyncio
    async def test_connect_via_chain_non_http(self):
        """Test connecting with non-HTTP proxy in chain."""
        client = ProxyClient()
        chain = [
            {"host": "proxy.example.com", "port": 1080, "type": "socks5"},
        ]
        with pytest.raises(ProxyError, match="only supports HTTP"):
            await client.connect_via_chain(
                target_host="target.example.com",
                target_port=80,
                proxy_chain=chain,
            )

    @pytest.mark.asyncio
    async def test_connect_via_chain_single_proxy(self):
        """Test connecting through single proxy."""
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
                    timeout=5.0,
                )
                
                assert reader is not None
                assert writer is not None


class TestConnectToProxy:
    """Tests for _connect_to_proxy method."""

    @pytest.mark.asyncio
    async def test_connect_to_proxy_success(self):
        """Test successful proxy connection."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        
        with patch(
            "asyncio.open_connection", return_value=(mock_reader, mock_writer)
        ):
            reader, writer = await client._connect_to_proxy(
                proxy_host="proxy.example.com",
                proxy_port=8080,
                _username=None,
                _password=None,
                timeout=5.0,
            )
            
            assert reader is mock_reader
            assert writer is mock_writer

    @pytest.mark.asyncio
    async def test_connect_to_proxy_timeout(self):
        """Test proxy connection timeout."""
        client = ProxyClient()
        
        with patch(
            "asyncio.open_connection",
            side_effect=asyncio.TimeoutError(),
        ):
            with pytest.raises(ProxyTimeoutError):
                await client._connect_to_proxy(
                    proxy_host="proxy.example.com",
                    proxy_port=8080,
                    _username=None,
                    _password=None,
                    timeout=1.0,
                )
            
            assert client.stats.timeouts > 0

    @pytest.mark.asyncio
    async def test_connect_to_proxy_connection_error(self):
        """Test proxy connection error."""
        client = ProxyClient()
        
        with patch(
            "asyncio.open_connection",
            side_effect=ConnectionError("Connection refused"),
        ):
            with pytest.raises(ProxyConnectionError):
                await client._connect_to_proxy(
                    proxy_host="proxy.example.com",
                    proxy_port=8080,
                    _username=None,
                    _password=None,
                    timeout=5.0,
                )
            
            assert client.stats.connections_failed > 0


class TestSendConnectRequest:
    """Tests for _send_connect_request method."""

    @pytest.mark.asyncio
    async def test_send_connect_request_no_auth(self):
        """Test sending CONNECT request without authentication."""
        client = ProxyClient()
        
        mock_writer = AsyncMock()
        mock_writer.drain = AsyncMock()
        
        await client._send_connect_request(
            writer=mock_writer,
            target_host="target.example.com",
            target_port=80,
            username=None,
            password=None,
        )
        
        mock_writer.write.assert_called_once()
        mock_writer.drain.assert_called_once()
        
        # Verify request format
        call_args = mock_writer.write.call_args[0][0]
        request = call_args.decode("utf-8")
        assert request.startswith("CONNECT target.example.com:80 HTTP/1.1")
        assert "Host: target.example.com:80" in request
        assert "Proxy-Authorization" not in request

    @pytest.mark.asyncio
    async def test_send_connect_request_with_auth(self):
        """Test sending CONNECT request with authentication."""
        client = ProxyClient()
        
        mock_writer = AsyncMock()
        mock_writer.drain = AsyncMock()
        
        await client._send_connect_request(
            writer=mock_writer,
            target_host="target.example.com",
            target_port=80,
            username="user",
            password="pass",
        )
        
        mock_writer.write.assert_called_once()
        mock_writer.drain.assert_called_once()
        
        # Verify request format
        call_args = mock_writer.write.call_args[0][0]
        request = call_args.decode("utf-8")
        assert "Proxy-Authorization: Basic" in request


class TestReadConnectResponse:
    """Tests for _read_connect_response method."""

    @pytest.mark.asyncio
    async def test_read_connect_response_success(self):
        """Test reading successful CONNECT response."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(
            side_effect=[
                b"HTTP/1.1 200 Connection established\r\n",
                b"Content-Length: 0\r\n",
                b"\r\n",
            ]
        )
        
        result = await client._read_connect_response(mock_reader)
        assert result is not None

    @pytest.mark.asyncio
    async def test_read_connect_response_auth_required(self):
        """Test reading 407 Proxy Authentication Required response."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(
            side_effect=[
                b"HTTP/1.1 407 Proxy Authentication Required\r\n",
                b"Proxy-Authenticate: Basic realm=\"Proxy\"\r\n",
                b"\r\n",
            ]
        )
        
        result = await client._read_connect_response(mock_reader)
        assert result is None
        assert client.stats.auth_failures > 0

    @pytest.mark.asyncio
    async def test_read_connect_response_forbidden(self):
        """Test reading 403 Forbidden response."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(
            side_effect=[
                b"HTTP/1.1 403 Forbidden\r\n",
                b"\r\n",
            ]
        )
        
        result = await client._read_connect_response(mock_reader)
        assert result is None
        assert client.stats.connections_failed > 0

    @pytest.mark.asyncio
    async def test_read_connect_response_empty(self):
        """Test reading empty response."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(return_value=b"")
        
        result = await client._read_connect_response(mock_reader)
        assert result is None

    @pytest.mark.asyncio
    async def test_read_connect_response_invalid_format(self):
        """Test reading invalid response format."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(return_value=b"Invalid\r\n")
        
        result = await client._read_connect_response(mock_reader)
        assert result is None

    @pytest.mark.asyncio
    async def test_read_connect_response_exception(self):
        """Test exception handling in _read_connect_response."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=Exception("Read error"))
        
        result = await client._read_connect_response(mock_reader)
        assert result is None
        assert client.stats.connections_failed > 0


class TestTestConnection:
    """Tests for test_connection method."""

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        """Test successful connection test."""
        from tests.unit.proxy.conftest import AsyncContextManagerMock, create_async_response_mock
        
        client = ProxyClient()
        
        # Create properly configured async response mock
        mock_response = create_async_response_mock(status=200)
        
        # Create async session mock with proper context manager
        # The key is that session.get() must return an object that works with async with
        mock_session = AsyncMock()
        # Return the async context manager directly (not wrapped)
        mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
        
        # Mock get_proxy_session to return the session (async function)
        async def get_session(*args, **kwargs):
            return mock_session
        
        with patch.object(client, "get_proxy_session", side_effect=get_session):
            result = await client.test_connection(
                proxy_host="proxy.example.com",
                proxy_port=8080,
            )
            
            assert result is True
            assert client.stats.connections_successful > 0

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        """Test failed connection test."""
        client = ProxyClient()
        
        # Mock response with proper async context manager
        mock_response = AsyncMock()
        mock_response.status = 500
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
            
            assert result is False
            assert client.stats.connections_failed > 0

    @pytest.mark.asyncio
    async def test_test_connection_timeout(self):
        """Test connection test timeout."""
        client = ProxyClient()
        
        with patch.object(
            client, "get_proxy_session", side_effect=asyncio.TimeoutError()
        ):
            result = await client.test_connection(
                proxy_host="proxy.example.com",
                proxy_port=8080,
            )
            
            assert result is False
            assert client.stats.timeouts > 0

    @pytest.mark.asyncio
    async def test_test_connection_auth_error(self):
        """Test connection test with auth error."""
        client = ProxyClient()
        
        with patch.object(
            client, "get_proxy_session", side_effect=ProxyAuthError("Auth failed")
        ):
            result = await client.test_connection(
                proxy_host="proxy.example.com",
                proxy_port=8080,
            )
            
            assert result is False
            assert client.stats.auth_failures > 0


class TestGetStats:
    """Tests for get_stats method."""

    def test_get_stats(self):
        """Test getting proxy statistics."""
        client = ProxyClient()
        client.stats.connections_total = 10
        client.stats.connections_successful = 8
        
        stats = client.get_stats()
        assert stats.connections_total == 10
        assert stats.connections_successful == 8


class TestProxyClientEdgeCases:
    """Tests for proxy client edge cases and error paths."""

    @pytest.mark.asyncio
    async def test_cleanup_with_exception(self):
        """Test cleanup handles exceptions gracefully."""
        client = ProxyClient()
        
        # Create a mock session that raises on close
        mock_session = AsyncMock()
        mock_session.close = AsyncMock(side_effect=Exception("Close error"))
        
        client._pools["test:8080"] = mock_session
        
        # Should handle exception and continue
        await client.cleanup()
        
        # Pool should be removed even if close failed
        assert "test:8080" not in client._pools

    @pytest.mark.asyncio
    async def test_cleanup_empty_pools(self):
        """Test cleanup with no pools."""
        client = ProxyClient()
        await client.cleanup()
        assert len(client._pools) == 0

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_get_proxy_session_concurrent(self):
        """Test concurrent access to get_proxy_session."""
        client = ProxyClient()
        
        async def get_session():
            return await client.get_proxy_session("proxy.example.com", 8080)
        
        # Get multiple sessions concurrently
        sessions = await asyncio.gather(*[get_session() for _ in range(5)])
        
        # All should be the same (pooled)
        assert all(s is sessions[0] for s in sessions)

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_create_proxy_session_with_headers(self):
        """Test creating proxy session with custom headers."""
        client = ProxyClient()
        session = client.create_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
            headers={"Custom-Header": "value"},
        )
        assert session is not None
        # Headers are set in session creation
        await session.close()

    @pytest.mark.asyncio
    async def test_build_proxy_url_with_special_chars_in_password(self):
        """Test building proxy URL with special characters in password."""
        client = ProxyClient()
        url = client._build_proxy_url(
            proxy_host="proxy.example.com",
            proxy_port=8080,
            proxy_username="user",
            proxy_password="p@ss:w0rd#test",
        )
        # URL should contain encoded credentials
        assert "p@ss:w0rd#test" in url or "%40" in url  # @ encoded

    @pytest.mark.asyncio
    async def test_connect_via_chain_single_proxy_with_auth(self):
        """Test connecting through single proxy with authentication."""
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
                            "username": "user",
                            "password": "pass",
                        }
                    ],
                    timeout=5.0,
                )
                
                assert reader is not None
                assert writer is not None
                
                # Verify CONNECT was called with auth
                assert mock_writer.write.called

    @pytest.mark.asyncio
    async def test_connect_via_chain_connection_lost(self):
        """Test handling connection loss in chain."""
        client = ProxyClient()
        
        with patch.object(
            client, "_connect_to_proxy", return_value=(None, None)
        ):
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
    async def test_read_connect_response_500_error(self):
        """Test reading 500 Internal Server Error response."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(
            side_effect=[
                b"HTTP/1.1 500 Internal Server Error\r\n",
                b"\r\n",
            ]
        )
        
        result = await client._read_connect_response(mock_reader)
        assert result is None
        assert client.stats.connections_failed > 0

    @pytest.mark.asyncio
    async def test_send_connect_request_exception(self):
        """Test exception handling in _send_connect_request."""
        client = ProxyClient()
        
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock(side_effect=Exception("Write error"))
        mock_writer.drain = AsyncMock()
        
        with pytest.raises(Exception):
            await client._send_connect_request(
                writer=mock_writer,
                target_host="target.example.com",
                target_port=80,
                username=None,
                password=None,
            )

