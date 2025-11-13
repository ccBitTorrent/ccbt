"""Unit tests for SSL peer connections.

Tests SSL/TLS wrapper for peer connections including connection establishment,
wrapping existing connections, and opportunistic encryption.
Target: 95%+ code coverage for ccbt/peer/ssl_peer.py.
"""

from __future__ import annotations

import asyncio
import ssl
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.peer, pytest.mark.security]

from ccbt.models import Config
from ccbt.peer.ssl_peer import SSLPeerConnection, SSLPeerStats


class TestSSLPeerStats:
    """Tests for SSLPeerStats dataclass."""

    def test_ssl_peer_stats_default(self):
        """Test SSLPeerStats with default values."""
        stats = SSLPeerStats()
        assert stats.connections_attempted == 0
        assert stats.connections_successful == 0
        assert stats.connections_failed == 0
        assert stats.handshake_errors == 0
        assert stats.certificate_errors == 0
        assert stats.bytes_encrypted == 0
        assert stats.fallback_to_plain == 0

    def test_ssl_peer_stats_custom(self):
        """Test SSLPeerStats with custom values."""
        stats = SSLPeerStats(
            connections_attempted=10,
            connections_successful=8,
            connections_failed=2,
            handshake_errors=1,
            certificate_errors=1,
            bytes_encrypted=1024,
            fallback_to_plain=2,
        )
        assert stats.connections_attempted == 10
        assert stats.connections_successful == 8
        assert stats.connections_failed == 2
        assert stats.handshake_errors == 1
        assert stats.certificate_errors == 1
        assert stats.bytes_encrypted == 1024
        assert stats.fallback_to_plain == 2


class TestSSLPeerConnectionInitialization:
    """Tests for SSLPeerConnection initialization."""

    def test_ssl_peer_connection_init(self):
        """Test SSLPeerConnection initialization."""
        connection = SSLPeerConnection()
        assert connection.config is not None
        assert connection.ssl_builder is not None
        assert connection.logger is not None
        assert isinstance(connection.stats, SSLPeerStats)


class TestSSLPeerConnectionConnect:
    """Tests for connect_with_ssl method."""

    @pytest.mark.asyncio
    async def test_connect_with_ssl_success(self):
        """Test successful SSL connection."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            # Mock SSL context and open_connection
            mock_context = MagicMock(spec=ssl.SSLContext)
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()

            with patch.object(
                connection.ssl_builder, "create_peer_context", return_value=mock_context
            ):
                with patch(
                    "asyncio.open_connection",
                    return_value=(mock_reader, mock_writer),
                ):
                    reader, writer = await connection.connect_with_ssl("127.0.0.1", 6881)

                assert reader == mock_reader
                assert writer == mock_writer
                assert connection.stats.connections_successful == 1
                assert connection.stats.connections_attempted == 1

    @pytest.mark.asyncio
    async def test_connect_with_ssl_ssl_disabled(self):
        """Test SSL connection when SSL is disabled."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": False,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            with pytest.raises(ValueError, match="SSL peer connections are disabled"):
                await connection.connect_with_ssl("127.0.0.1", 6881)

    @pytest.mark.asyncio
    async def test_connect_with_ssl_handshake_error(self):
        """Test SSL connection with handshake error."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_context = MagicMock(spec=ssl.SSLContext)

            with patch.object(
                connection.ssl_builder, "create_peer_context", return_value=mock_context
            ):
                with patch(
                    "asyncio.open_connection",
                    side_effect=ssl.SSLError("Handshake failed"),
                ), pytest.raises(ssl.SSLError):
                    await connection.connect_with_ssl("127.0.0.1", 6881)

                assert connection.stats.connections_failed == 1
                assert connection.stats.handshake_errors == 1

    @pytest.mark.asyncio
    async def test_connect_with_ssl_connection_error(self):
        """Test SSL connection with connection error."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_context = MagicMock(spec=ssl.SSLContext)

            with patch.object(
                connection.ssl_builder, "create_peer_context", return_value=mock_context
            ):
                with patch(
                    "asyncio.open_connection",
                    side_effect=OSError("Connection refused"),
                ), pytest.raises(OSError):
                    await connection.connect_with_ssl("127.0.0.1", 6881)

                assert connection.stats.connections_failed == 1

    @pytest.mark.asyncio
    async def test_connect_with_ssl_verify_hostname(self):
        """Test SSL connection with hostname verification."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_context = MagicMock(spec=ssl.SSLContext)
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()

            with patch.object(
                connection.ssl_builder, "create_peer_context", return_value=mock_context
            ):
                with patch(
                    "asyncio.open_connection",
                    return_value=(mock_reader, mock_writer),
                ) as mock_open:
                    await connection.connect_with_ssl("example.com", 6881, verify_hostname=True)

                # Verify that server_hostname was passed
                mock_open.assert_called_once()
                call_kwargs = mock_open.call_args[1]
                assert call_kwargs.get("server_hostname") == "example.com"


class TestSSLPeerConnectionWrap:
    """Tests for wrap_connection method."""

    @pytest.mark.asyncio
    async def test_wrap_connection_ssl_disabled(self):
        """Test wrapping connection when SSL is disabled."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": False,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_reader = AsyncMock()
            mock_writer = AsyncMock()

            reader, writer, ssl_enabled = await connection.wrap_connection(
                mock_reader, mock_writer, "127.0.0.1", 6881
            )

            assert reader == mock_reader
            assert writer == mock_writer
            assert ssl_enabled is False

    @pytest.mark.asyncio
    async def test_wrap_connection_success(self):
        """Test successful SSL wrapping."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.get_extra_info = Mock(return_value=MagicMock())  # Mock socket
            mock_ssl_reader = AsyncMock()
            mock_ssl_writer = AsyncMock()

            mock_context = MagicMock(spec=ssl.SSLContext)

            # Mock start_tls if available
            start_tls = getattr(asyncio, "start_tls", None)
            if start_tls:
                with patch.object(
                    connection.ssl_builder, "create_peer_context", return_value=mock_context
                ):
                    with patch(
                        "asyncio.start_tls",
                        return_value=(mock_ssl_reader, mock_ssl_writer),
                    ):
                        reader, writer, ssl_enabled = await connection.wrap_connection(
                            mock_reader, mock_writer, "127.0.0.1", 6881
                        )

                        assert reader == mock_ssl_reader
                        assert writer == mock_ssl_writer
                        assert ssl_enabled is True
                        assert connection.stats.connections_successful == 1

    @pytest.mark.asyncio
    async def test_wrap_connection_opportunistic_fallback(self):
        """Test opportunistic encryption with fallback."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.get_extra_info = Mock(return_value=MagicMock())  # Mock socket

            mock_context = MagicMock(spec=ssl.SSLContext)

            start_tls = getattr(asyncio, "start_tls", None)
            if start_tls:
                with patch.object(
                    connection.ssl_builder, "create_peer_context", return_value=mock_context
                ):
                    with patch(
                        "asyncio.start_tls",
                        side_effect=ssl.SSLError("Handshake failed"),
                    ):
                        reader, writer, ssl_enabled = await connection.wrap_connection(
                            mock_reader, mock_writer, "127.0.0.1", 6881, opportunistic=True
                        )

                        # Should fallback to plain connection
                        assert reader == mock_reader
                        assert writer == mock_writer
                        assert ssl_enabled is False
                        assert connection.stats.fallback_to_plain == 1
                        assert connection.stats.handshake_errors == 1

    @pytest.mark.asyncio
    async def test_wrap_connection_not_opportunistic_raises(self):
        """Test wrapping without opportunistic encryption raises error."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.get_extra_info = Mock(return_value=MagicMock())  # Mock socket

            mock_context = MagicMock(spec=ssl.SSLContext)

            start_tls = getattr(asyncio, "start_tls", None)
            if start_tls:
                with patch.object(
                    connection.ssl_builder, "create_peer_context", return_value=mock_context
                ):
                    with patch(
                        "asyncio.start_tls",
                        side_effect=ssl.SSLError("Handshake failed"),
                    ):
                        with pytest.raises(ssl.SSLError):
                            await connection.wrap_connection(
                                mock_reader,
                                mock_writer,
                                "127.0.0.1",
                                6881,
                                opportunistic=False,
                            )

                        assert connection.stats.connections_failed == 1

    @pytest.mark.asyncio
    async def test_wrap_connection_no_start_tls_fallback(self):
        """Test wrapping when start_tls is not available."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.get_extra_info = Mock(return_value=MagicMock())  # Mock socket

            mock_context = MagicMock(spec=ssl.SSLContext)

            with patch.object(
                connection.ssl_builder, "create_peer_context", return_value=mock_context
            ):
                # Mock getattr to return None for asyncio.start_tls
                original_getattr = getattr
                def mock_getattr(obj, attr, default=None):
                    if obj is asyncio and attr == "start_tls":
                        return None
                    return original_getattr(obj, attr, default)
                
                with patch("ccbt.peer.ssl_peer.getattr", side_effect=mock_getattr):
                    reader, writer, ssl_enabled = await connection.wrap_connection(
                        mock_reader, mock_writer, "127.0.0.1", 6881, opportunistic=True
                    )

                    # Should fallback to plain connection
                    assert reader == mock_reader
                    assert writer == mock_writer
                    assert ssl_enabled is False
                    assert connection.stats.fallback_to_plain == 1

    @pytest.mark.asyncio
    async def test_wrap_connection_no_start_tls_no_opportunistic_raises(self):
        """Test wrapping when start_tls is not available and opportunistic=False."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.get_extra_info = Mock(return_value=MagicMock())

            mock_context = MagicMock(spec=ssl.SSLContext)

            with patch.object(
                connection.ssl_builder, "create_peer_context", return_value=mock_context
            ):
                # Mock getattr to return None for asyncio.start_tls
                original_getattr = getattr
                def mock_getattr(obj, attr, default=None):
                    if obj is asyncio and attr == "start_tls":
                        return None
                    return original_getattr(obj, attr, default)
                
                with patch("ccbt.peer.ssl_peer.getattr", side_effect=mock_getattr):
                    with pytest.raises(RuntimeError, match="asyncio.start_tls not available"):
                        await connection.wrap_connection(
                            mock_reader, mock_writer, "127.0.0.1", 6881, opportunistic=False
                        )

    @pytest.mark.asyncio
    async def test_wrap_connection_general_exception_opportunistic(self):
        """Test wrapping with general exception and opportunistic fallback."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.get_extra_info = Mock(return_value=MagicMock())

            mock_context = MagicMock(spec=ssl.SSLContext)

            with patch.object(
                connection.ssl_builder, "create_peer_context", return_value=mock_context
            ), patch.object(asyncio, "start_tls", side_effect=ValueError("Unexpected error"), create=True):
                reader, writer, ssl_enabled = await connection.wrap_connection(
                    mock_reader, mock_writer, "127.0.0.1", 6881, opportunistic=True
                )

                assert reader == mock_reader
                assert writer == mock_writer
                assert ssl_enabled is False
                assert connection.stats.connections_failed == 1
                assert connection.stats.fallback_to_plain == 1

    @pytest.mark.asyncio
    async def test_wrap_connection_general_exception_not_opportunistic(self):
        """Test wrapping with general exception and not opportunistic raises."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.get_extra_info = Mock(return_value=MagicMock())

            mock_context = MagicMock(spec=ssl.SSLContext)

            with patch.object(
                connection.ssl_builder, "create_peer_context", return_value=mock_context
            ), patch.object(asyncio, "start_tls", side_effect=ValueError("Unexpected error"), create=True):
                with pytest.raises(ValueError, match="Unexpected error"):
                    await connection.wrap_connection(
                        mock_reader, mock_writer, "127.0.0.1", 6881, opportunistic=False
                    )

                assert connection.stats.connections_failed == 1

    @pytest.mark.asyncio
    async def test_negotiate_ssl_after_handshake(self):
        """Test SSL negotiation after BitTorrent handshake (not implemented)."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            # Create mock reader and writer
            mock_reader = AsyncMock(spec=asyncio.StreamReader)
            mock_writer = AsyncMock(spec=asyncio.StreamWriter)

            # Mock the method to return None since SSL extension is disabled by default
            with patch.object(connection.config.security, 'ssl', None):
                result = await connection.negotiate_ssl_after_handshake(
                    mock_reader, mock_writer, "peer_id_123", "127.0.0.1", 6881
                )
                assert result is None

    @pytest.mark.asyncio
    async def test_wrap_connection_socket_not_available(self):
        """Test wrapping when socket is not available."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            mock_reader = AsyncMock()
            mock_writer = MagicMock()
            # Make get_extra_info return None (no socket)
            mock_writer.get_extra_info = Mock(return_value=None)

            mock_context = MagicMock(spec=ssl.SSLContext)

            start_tls = getattr(asyncio, "start_tls", None)
            if start_tls:
                with patch.object(
                    connection.ssl_builder, "create_peer_context", return_value=mock_context
                ):
                    with pytest.raises(ValueError, match="Socket not available"):
                        await connection.wrap_connection(
                            mock_reader, mock_writer, "127.0.0.1", 6881
                        )


class TestSSLPeerConnectionNegotiation:
    """Tests for negotiate_ssl_after_handshake method."""

    @pytest.mark.asyncio
    async def test_negotiate_ssl_after_handshake_not_implemented(self):
        """Test SSL negotiation after handshake returns None when disabled."""
        with patch("ccbt.peer.ssl_peer.get_config") as mock_get_config:
            config = MagicMock()
            config.security.ssl.enable_ssl_peers = False
            mock_get_config.return_value = config
            
            connection = SSLPeerConnection()
            connection.config = config

            mock_reader = AsyncMock()
            mock_writer = AsyncMock()

            result = await connection.negotiate_ssl_after_handshake(
                mock_reader, mock_writer, "peer_id_123", "127.0.0.1", 6881
            )

            # Should return None when SSL is disabled
            assert result is None


class TestSSLPeerConnectionStats:
    """Tests for statistics methods."""

    def test_get_stats(self):
        """Test getting statistics."""
        connection = SSLPeerConnection()
        stats = connection.get_stats()

        assert isinstance(stats, SSLPeerStats)
        assert stats == connection.stats

    def test_reset_stats(self):
        """Test resetting statistics."""
        connection = SSLPeerConnection()

        # Set some stats
        connection.stats.connections_attempted = 10
        connection.stats.connections_successful = 5

        # Reset
        connection.reset_stats()

        # Verify reset
        assert connection.stats.connections_attempted == 0
        assert connection.stats.connections_successful == 0

