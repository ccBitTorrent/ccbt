"""Unit tests for tracker SSL/TLS functionality.

Tests HTTPS tracker connections, SSL context creation, and error handling.
Target: 95%+ code coverage for SSL-related code in ccbt/discovery/tracker.py.
"""

from __future__ import annotations

import ssl
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]

from ccbt.discovery.tracker import AsyncTrackerClient, TrackerError
from ccbt.models import Config


class TestTrackerSSLContextCreation:
    """Tests for SSL context creation in tracker client."""

    @pytest.mark.asyncio
    async def test_create_connector_with_ssl_enabled(self):
        """Test connector creation with SSL enabled for trackers."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                    "ssl_verify_certificates": True,
                }
            }
        }
        config = Config(**config_data)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            with patch("ccbt.security.ssl_context.SSLContextBuilder") as mock_builder_class:
                mock_builder = MagicMock()
                mock_context = MagicMock(spec=ssl.SSLContext)
                mock_builder.create_tracker_context.return_value = mock_context
                mock_builder_class.return_value = mock_builder

                connector = client._create_connector(timeout)

                assert isinstance(connector, aiohttp.TCPConnector)
                # Verify SSL context builder was called
                mock_builder.create_tracker_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_connector_with_ssl_disabled(self):
        """Test connector creation with SSL disabled."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": False,
                }
            }
        }
        config = Config(**config_data)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            connector = client._create_connector(timeout)

            assert isinstance(connector, aiohttp.TCPConnector)

    @pytest.mark.asyncio
    async def test_create_connector_ssl_context_error(self):
        """Test connector creation when SSL context creation fails."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                }
            }
        }
        config = Config(**config_data)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            with patch("ccbt.security.ssl_context.SSLContextBuilder") as mock_builder_class:
                mock_builder = MagicMock()
                mock_builder.create_tracker_context.side_effect = ValueError("Invalid cert path")
                mock_builder_class.return_value = mock_builder

                # Should not raise, but fallback to default
                connector = client._create_connector(timeout)

                assert isinstance(connector, aiohttp.TCPConnector)

    @pytest.mark.asyncio
    async def test_create_connector_with_proxy_and_ssl(self):
        """Test connector creation with both proxy and SSL enabled."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                }
            },
            "proxy": {
                "enable_proxy": True,
                "proxy_for_trackers": True,
                "proxy_host": "proxy.example.com",
                "proxy_port": 8080,
                "proxy_type": "http",
            },
        }
        config = Config(**config_data)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            with patch("ccbt.proxy.client.ProxyClient") as mock_proxy_client_class:
                mock_proxy_client = MagicMock()
                mock_proxy_connector = MagicMock(spec=aiohttp.BaseConnector)
                mock_proxy_client.create_proxy_connector.return_value = mock_proxy_connector
                mock_proxy_client_class.return_value = mock_proxy_client

                connector = client._create_connector(timeout)

                # Should use proxy connector
                assert connector == mock_proxy_connector
                mock_proxy_client.create_proxy_connector.assert_called_once()


class TestTrackerHTTPSDetection:
    """Tests for HTTPS URL detection and SSL handling."""

    @pytest.mark.asyncio
    async def test_make_request_https_with_ssl_enabled(self):
        """Test HTTPS request when SSL is enabled."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=b"response data")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_session.get = Mock(return_value=mock_response)  # Use Mock, not AsyncMock
            client.session = mock_session

            url = "https://tracker.example.com/announce"
            response_data = await client._make_request_async(url)

            assert response_data == b"response data"
            mock_session.get.assert_called_once_with(url)

    @pytest.mark.asyncio
    async def test_make_request_https_with_ssl_disabled(self):
        """Test HTTPS request when SSL is disabled (should warn)."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": False,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=b"response data")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_session.get = Mock(return_value=mock_response)
            client.session = mock_session

            url = "https://tracker.example.com/announce"
            with patch.object(client.logger, "warning") as mock_warning:
                response_data = await client._make_request_async(url)

                assert response_data == b"response data"
                # Should log warning about HTTPS without SSL
                mock_warning.assert_called()
                assert "HTTPS tracker detected but SSL not enabled" in str(mock_warning.call_args)

    @pytest.mark.asyncio
    async def test_make_request_http_url(self):
        """Test HTTP request (non-HTTPS)."""
        config_data = {"security": {"ssl": {"enable_ssl_trackers": True}}}
        config = Config(**config_data)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=b"response data")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_session.get = Mock(return_value=mock_response)
            client.session = mock_session

            url = "http://tracker.example.com/announce"
            response_data = await client._make_request_async(url)

            assert response_data == b"response data"

    @pytest.mark.asyncio
    async def test_make_request_ssl_error(self):
        """Test handling of SSL errors during HTTPS request."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            # Create proper ClientSSLError - it's a subclass of ClientConnectorError
            ssl_error = aiohttp.ClientSSLError(
                connection_key=MagicMock(),
                os_error=OSError("SSL handshake failed")
            )
            mock_session = AsyncMock()
            mock_session.get = Mock(side_effect=ssl_error)  # Use Mock, not AsyncMock for side_effect
            client.session = mock_session

            url = "https://tracker.example.com/announce"

            with patch.object(client.logger, "error") as mock_error:
                with pytest.raises(TrackerError, match="SSL handshake failed"):
                    await client._make_request_async(url)

                mock_error.assert_called_once()
                assert "SSL error connecting to tracker" in str(mock_error.call_args)

    @pytest.mark.asyncio
    async def test_make_request_https_with_debug_logging(self):
        """Test HTTPS request with debug logging enabled."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=b"response data")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_session.get = Mock(return_value=mock_response)
            client.session = mock_session

            url = "https://tracker.example.com/announce"

            with patch.object(client.logger, "debug") as mock_debug:
                await client._make_request_async(url)

                # Should log debug message about HTTPS connection
                mock_debug.assert_called()
                assert "Connecting to HTTPS tracker" in str(mock_debug.call_args)


class TestTrackerSSLIntegration:
    """Tests for SSL integration with tracker announce operations."""

    @pytest.mark.asyncio
    async def test_announce_to_https_tracker(self):
        """Test announcing to HTTPS tracker."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            # Mock session and response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.reason = "OK"
            mock_response.read = AsyncMock(return_value=b"d8:intervali3600e5:peers6:\x01\x02\x03\x04\x05\x06e")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_session.get = Mock(return_value=mock_response)

            # Mock connector creation
            with patch.object(client, "_create_connector") as mock_create_connector:
                mock_connector = MagicMock()
                mock_create_connector.return_value = mock_connector

                await client.start()
                client.session = mock_session

                torrent_data = {
                    "announce": "https://tracker.example.com/announce",
                    "info_hash": b"test_info_hash_20_bytes!",
                    "file_info": {"total_length": 1024},
                }

                # Mock URL building and parsing
                with patch.object(client, "_build_tracker_url") as mock_build_url:
                    mock_build_url.return_value = "https://tracker.example.com/announce?info_hash=..."
                    with patch.object(client, "_parse_response_async") as mock_parse:
                        mock_parse.return_value = {
                            "interval": 3600,
                            "peers": b"\x01\x02\x03\x04\x05\x06",
                        }
                        with patch.object(client, "_update_tracker_session"):
                            response = await client.announce(
                                torrent_data,
                                port=6881,
                            )

                            assert response is not None
                            mock_session.get.assert_called()

    @pytest.mark.asyncio
    async def test_announce_ssl_error_handling(self):
        """Test error handling when SSL fails during announce."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            # Mock session to raise SSL error
            ssl_error = aiohttp.ClientSSLError(
                connection_key=MagicMock(),
                os_error=OSError("Certificate verification failed")
            )
            # Create a mock that raises the error when used as async context manager
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(side_effect=ssl_error)
            mock_context.__aexit__ = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_session.get = Mock(return_value=mock_context)
            client.session = mock_session

            torrent_data = {
                "announce": "https://tracker.example.com/announce",
                "info_hash": b"test_info_hash_20_bytes!",
                "file_info": {"total_length": 1024},
            }

            with patch.object(client, "_build_tracker_url") as mock_build_url:
                mock_build_url.return_value = "https://tracker.example.com/announce?info_hash=..."
                with patch.object(client, "_handle_tracker_failure"):
                    with pytest.raises(TrackerError, match="SSL handshake failed"):
                        await client.announce(torrent_data, port=6881)


class TestTrackerSSLConfiguration:
    """Tests for SSL configuration handling in tracker client."""

    @pytest.mark.asyncio
    async def test_ssl_config_none(self):
        """Test behavior when SSL config is None."""
        # Create a config with proper security structure
        config_data = {"security": {"ssl": {"enable_ssl_trackers": False}}}
        config = Config(**config_data)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config
            # Manually set security to None to test that path
            client.config.security = None

            # Should not raise, SSL context creation should be skipped
            connector = client._create_connector(timeout)

            assert isinstance(connector, aiohttp.TCPConnector)

    @pytest.mark.asyncio
    async def test_ssl_config_missing(self):
        """Test behavior when security.ssl config is missing."""
        # Create a config with proper security structure
        config_data = {"security": {"ssl": {"enable_ssl_trackers": False}}}
        config = Config(**config_data)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config
            # Manually set ssl to None to test that path
            client.config.security.ssl = None

            # Should not raise, SSL context creation should be skipped
            connector = client._create_connector(timeout)

            assert isinstance(connector, aiohttp.TCPConnector)

    @pytest.mark.asyncio
    async def test_ssl_context_builder_import_error(self):
        """Test handling when SSLContextBuilder cannot be imported."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                }
            }
        }
        config = Config(**config_data)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        with patch("ccbt.discovery.tracker.get_config", return_value=config):
            client = AsyncTrackerClient()
            client.config = config

            with patch("ccbt.security.ssl_context.SSLContextBuilder", side_effect=ImportError("Module not found")):
                # Should fallback to default connector
                connector = client._create_connector(timeout)

                assert isinstance(connector, aiohttp.TCPConnector)
