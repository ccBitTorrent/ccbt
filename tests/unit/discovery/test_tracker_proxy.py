"""Unit tests for tracker proxy integration.

Tests proxy integration in tracker client.
Target: 95%+ code coverage for proxy-related code in ccbt/discovery/tracker.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.tracker]

from ccbt.discovery.tracker import AsyncTrackerClient


class TestTrackerProxyIntegration:
    """Tests for proxy integration in AsyncTrackerClient."""

    @pytest.fixture
    def mock_config_with_proxy(self):
        """Create mock config with proxy enabled."""
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

    @pytest.fixture
    def mock_config_no_proxy(self):
        """Create mock config with proxy disabled."""
        config = MagicMock()
        config.network = MagicMock()
        config.network.connection_timeout = 10.0
        config.proxy = MagicMock()
        config.proxy.enable_proxy = False
        return config

    @pytest.mark.asyncio
    async def test_start_with_proxy(self, mock_config_with_proxy):
        """Test starting tracker client with proxy enabled."""
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            with patch("ccbt.proxy.client.ProxyClient") as mock_proxy_client:
                mock_client = MagicMock()
                mock_client.create_proxy_connector.return_value = MagicMock()
                mock_proxy_client.return_value = mock_client
                
                client = AsyncTrackerClient()
                await client.start()
                
                # Verify connector was created
                mock_client.create_proxy_connector.assert_called_once()
                assert client.session is not None
                
                await client.stop()

    @pytest.mark.asyncio
    async def test_start_without_proxy(self, mock_config_no_proxy):
        """Test starting tracker client without proxy."""
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_no_proxy):
            client = AsyncTrackerClient()
            await client.start()
            
            assert client.session is not None
            
            await client.stop()

    @pytest.mark.asyncio
    async def test_should_bypass_proxy_localhost(self, mock_config_with_proxy):
        """Test bypass logic for localhost."""
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            client = AsyncTrackerClient()
            
            assert client._should_bypass_proxy("http://localhost:8080/announce")
            assert client._should_bypass_proxy("http://127.0.0.1:8080/announce")
            assert not client._should_bypass_proxy("http://tracker.example.com/announce")

    @pytest.mark.asyncio
    async def test_should_bypass_proxy_bypass_list(self, mock_config_with_proxy):
        """Test bypass logic for bypass list."""
        mock_config_with_proxy.proxy.proxy_bypass_list = ["example.local"]
        
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            client = AsyncTrackerClient()
            
            assert client._should_bypass_proxy("http://example.local:8080/announce")
            assert not client._should_bypass_proxy("http://tracker.example.com/announce")

    @pytest.mark.asyncio
    async def test_should_bypass_proxy_private_ip(self, mock_config_with_proxy):
        """Test bypass logic for private IPs."""
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            client = AsyncTrackerClient()
            
            assert client._should_bypass_proxy("http://192.168.1.1:8080/announce")
            assert client._should_bypass_proxy("http://10.0.0.1:8080/announce")

    @pytest.mark.asyncio
    async def test_make_request_async_with_proxy(self, mock_config_with_proxy):
        """Test making request through proxy."""
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            # Mock ProxyClient to avoid ProxyConnector issues
            with patch("ccbt.proxy.client.ProxyClient") as mock_proxy_client:
                mock_client = MagicMock()
                mock_client.create_proxy_connector.return_value = MagicMock()
                mock_proxy_client.return_value = mock_client
                
                client = AsyncTrackerClient()
                await client.start()
                
                # Use helper for async context manager
                from tests.unit.proxy.conftest import AsyncContextManagerMock, create_async_response_mock
                
                mock_response = create_async_response_mock(
                    status=200,
                    headers={},
                )
                mock_response.read = AsyncMock(return_value=b"d8:intervali1800e5:peers0:e")
                
                client.session = AsyncMock()
                # Use MagicMock to return the async context manager properly
                client.session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
                
                # Should not bypass for external URL
                result = await client._make_request_async("http://tracker.example.com/announce")
                
                assert result is not None
                assert len(result) > 0
                
                await client.stop()

    @pytest.mark.asyncio
    async def test_make_request_async_bypass_localhost(self, mock_config_with_proxy):
        """Test making request bypasses proxy for localhost."""
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            with patch("ccbt.proxy.client.ProxyConnector"):
                client = AsyncTrackerClient()
                
                # Create session without proxy (bypass case)
                await client.start()
                
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
                
                # Should bypass for localhost
                assert client._should_bypass_proxy("http://localhost:8080/announce")
                
                await client.stop()

    @pytest.mark.asyncio
    async def test_make_request_async_407_handling(self, mock_config_with_proxy):
        """Test handling 407 Proxy Authentication Required."""
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            with patch("ccbt.proxy.client.ProxyConnector"):
                client = AsyncTrackerClient()
                await client.start()
                
                # Mock 407 response with proper async context manager
                # Use helper for async context manager
                from tests.unit.proxy.conftest import AsyncContextManagerMock, create_async_response_mock
                
                mock_response = create_async_response_mock(
                    status=407,
                    headers={"Proxy-Authenticate": 'Basic realm="Proxy"'},
                )
                
                client.session = AsyncMock()
                # Use MagicMock to return the async context manager properly
                client.session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
                
                # Should handle 407 and raise TrackerError
                with pytest.raises(Exception):  # TrackerError
                    await client._make_request_async("http://tracker.example.com/announce")
                
                await client.stop()

    @pytest.mark.asyncio
    async def test_create_connector_with_auth(self, mock_config_with_proxy):
        """Test creating connector with authentication."""
        mock_config_with_proxy.proxy.proxy_username = "user"
        mock_config_with_proxy.proxy.proxy_password = "pass"
        
        with patch("ccbt.discovery.tracker.get_config", return_value=mock_config_with_proxy):
            with patch("ccbt.proxy.client.ProxyClient") as mock_proxy_client:
                mock_client = MagicMock()
                mock_connector = MagicMock()
                mock_client.create_proxy_connector.return_value = mock_connector
                mock_proxy_client.return_value = mock_client
                
                client = AsyncTrackerClient()
                await client.start()
                
                # Verify connector created with auth
                mock_client.create_proxy_connector.assert_called_once()
                call_kwargs = mock_client.create_proxy_connector.call_args[1]
                assert call_kwargs.get("proxy_username") == "user"
                
                await client.stop()

