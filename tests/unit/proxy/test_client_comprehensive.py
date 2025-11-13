"""Comprehensive tests for client.py to reach 95%+ coverage.

Targets all missing coverage paths.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.network]

from ccbt.proxy.client import ProxyClient
from ccbt.proxy.exceptions import ProxyConnectionError, ProxyError

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


class TestProxyClientSOCKSComprehensive:
    """Tests for SOCKS connector creation to cover lines 142-150."""

    @pytest.mark.skipif(not HAS_SOCKS, reason="aiohttp-socks not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_socks4_comprehensive(self):
        """Test creating SOCKS4 connector (coverage lines 142-150)."""
        client = ProxyClient()
        
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=1080,
            proxy_type="socks4",
            proxy_username="user",
            proxy_password="pass",
        )
        assert connector is not None
        # Cleanup
        await connector.close()

    @pytest.mark.skipif(not HAS_SOCKS, reason="aiohttp-socks not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_socks5_comprehensive(self):
        """Test creating SOCKS5 connector (coverage lines 142-150)."""
        client = ProxyClient()
        
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=1080,
            proxy_type="socks5",
            proxy_username="user",
            proxy_password="pass",
        )
        assert connector is not None
        # Cleanup
        await connector.close()

    @pytest.mark.skipif(not HAS_SOCKS, reason="aiohttp-socks not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_socks4_with_timeout(self):
        """Test creating SOCKS4 connector with timeout (coverage lines 142-150)."""
        from aiohttp import ClientTimeout
        
        client = ProxyClient()
        
        timeout = ClientTimeout(total=30.0)
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=1080,
            proxy_type="socks4",
            timeout=timeout,
        )
        assert connector is not None
        # Cleanup
        await connector.close()

    @pytest.mark.skipif(not HAS_SOCKS, reason="aiohttp-socks not available")
    @pytest.mark.asyncio
    async def test_create_proxy_connector_socks5_with_timeout(self):
        """Test creating SOCKS5 connector with timeout (coverage lines 142-150)."""
        from aiohttp import ClientTimeout
        
        client = ProxyClient()
        
        timeout = ClientTimeout(total=30.0)
        connector = client.create_proxy_connector(
            proxy_host="proxy.example.com",
            proxy_port=1080,
            proxy_type="socks5",
            timeout=timeout,
        )
        assert connector is not None
        # Cleanup
        await connector.close()


class TestProxyClientSessionCreation:
    """Tests for create_proxy_session to cover lines 200-213."""

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_create_proxy_session_with_timeout(self):
        """Test create_proxy_session with timeout parameter (coverage lines 200-213)."""
        from aiohttp import ClientTimeout
        
        client = ProxyClient()
        
        timeout = ClientTimeout(total=30.0)
        session = client.create_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
            timeout=timeout,
        )
        assert session is not None
        await session.close()

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_create_proxy_session_with_headers(self):
        """Test create_proxy_session with custom headers (coverage lines 200-213)."""
        client = ProxyClient()
        
        headers = {"Custom-Header": "value", "Another-Header": "another-value"}
        session = client.create_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
            headers=headers,
        )
        assert session is not None
        await session.close()

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_create_proxy_session_with_auth(self):
        """Test create_proxy_session with authentication (coverage lines 200-213)."""
        client = ProxyClient()
        
        session = client.create_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
            proxy_username="user",
            proxy_password="pass",
        )
        assert session is not None
        await session.close()


class TestProxyClientSessionPooling:
    """Tests for get_proxy_session pooling to cover lines 238-251."""

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_get_proxy_session_creates_new_pool(self):
        """Test get_proxy_session creates new pool entry (coverage lines 238-251)."""
        client = ProxyClient()
        
        session = await client.get_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
        )
        
        assert session is not None
        assert "proxy.example.com:8080" in client._pools
        assert client._pools["proxy.example.com:8080"] is session
        
        await client.cleanup()

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_get_proxy_session_reuses_existing_pool(self):
        """Test get_proxy_session reuses existing pool (coverage lines 238-251)."""
        client = ProxyClient()
        
        session1 = await client.get_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
        )
        
        session2 = await client.get_proxy_session(
            proxy_host="proxy.example.com",
            proxy_port=8080,
        )
        
        # Should be the same session
        assert session1 is session2
        assert len(client._pools) == 1
        
        await client.cleanup()

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_get_proxy_session_different_proxies_different_pools(self):
        """Test different proxies create different pools (coverage lines 238-251)."""
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
        assert len(client._pools) == 2
        
        await client.cleanup()


class TestProxyClientCleanupErrorHandling:
    """Tests for cleanup error handling to cover line 314."""

    @pytest.mark.skipif(not HAS_PROXY_CONNECTOR, reason="ProxyConnector not available")
    @pytest.mark.asyncio
    async def test_cleanup_logs_warning_on_close_error(self):
        """Test cleanup logs warning when session close fails (coverage line 314)."""
        client = ProxyClient()
        
        # Create a mock session that raises on close
        mock_session = AsyncMock()
        mock_session.close = AsyncMock(side_effect=Exception("Close error"))
        
        client._pools["test:8080"] = mock_session
        
        with patch("ccbt.proxy.client.logger") as mock_logger:
            await client.cleanup()
            # Should log warning
            mock_logger.warning.assert_called()
            assert "test:8080" in str(mock_logger.warning.call_args[0])
            # Pool should be removed despite error
            assert "test:8080" not in client._pools


class TestProxyClientConnectViaChainSubsequentProxies:
    """Tests for connect_via_chain subsequent proxy handling (lines 409-421)."""

    @pytest.mark.asyncio
    async def test_connect_via_chain_subsequent_proxy_response_none(self):
        """Test connect_via_chain when subsequent proxy response is None (coverage lines 409-421)."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        
        # Mock for chain of 2 proxies
        call_count = [0]
        async def mock_read_response(reader):
            call_count[0] += 1
            if call_count[0] == 1:
                # First proxy connection succeeds
                return mock_reader
            elif call_count[0] == 2:
                # Second proxy (subsequent) response fails
                return None
            else:
                return mock_reader
        
        with patch.object(
            client, "_connect_to_proxy", return_value=(mock_reader, mock_writer)
        ):
            with patch.object(
                client, "_send_connect_request", return_value=None
            ):
                with patch.object(
                    client, "_read_connect_response", side_effect=mock_read_response
                ):
                    with pytest.raises(ProxyConnectionError) as exc_info:
                        await client.connect_via_chain(
                            target_host="target.example.com",
                            target_port=80,
                            proxy_chain=[
                                {"host": "proxy1.example.com", "port": 8080, "type": "http"},
                                {"host": "proxy2.example.com", "port": 8080, "type": "http"},
                            ],
                        )
                    # Error could be from line 417 (subsequent proxy) or 433 (final target)
                    assert "tunnel" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_connect_via_chain_subsequent_proxy_connection_lost(self):
        """Test connect_via_chain when subsequent proxy connection is lost (coverage lines 403-406)."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        
        # First proxy succeeds, but reader/writer become None for second
        with patch.object(
            client, "_connect_to_proxy", return_value=(None, None)
        ):
            with pytest.raises(ProxyConnectionError) as exc_info:
                await client.connect_via_chain(
                    target_host="target.example.com",
                    target_port=80,
                    proxy_chain=[
                        {"host": "proxy1.example.com", "port": 8080, "type": "http"},
                        {"host": "proxy2.example.com", "port": 8080, "type": "http"},
                    ],
                )
            assert "connection lost" in str(exc_info.value).lower()


class TestProxyClientReadConnectResponseComprehensive:
    """Tests for _read_connect_response to cover line 542."""

    @pytest.mark.asyncio
    async def test_read_connect_response_empty_header_immediately(self):
        """Test _read_connect_response when header line is empty immediately (coverage line 542)."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        # Return empty line immediately (before any status line)
        mock_reader.readline = AsyncMock(return_value=b"")
        
        result = await client._read_connect_response(mock_reader)
        assert result is None

    @pytest.mark.asyncio
    async def test_read_connect_response_exception_during_read(self):
        """Test _read_connect_response when exception occurs during read."""
        client = ProxyClient()
        
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(side_effect=Exception("Read error"))
        
        # Should catch exception and return None
        result = await client._read_connect_response(mock_reader)
        assert result is None

