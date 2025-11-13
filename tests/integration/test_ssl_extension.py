"""Integration tests for SSL/TLS Extension Protocol (BEP 47).

Tests end-to-end SSL extension negotiation flow including:
- Extension handshake with SSL support
- SSL extension message exchange
- SSL connection wrapping
- Fallback to plain connection
"""

from __future__ import annotations

import asyncio
import json
import struct
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.security, pytest.mark.extensions]

from ccbt.extensions.manager import ExtensionManager, get_extension_manager
from ccbt.extensions.protocol import ExtensionMessageType
from ccbt.extensions.ssl import SSLMessageType, SSLNegotiationState
from ccbt.models import Config
from ccbt.peer.ssl_peer import SSLPeerConnection


class TestSSLExtensionIntegration:
    """Integration tests for SSL extension protocol."""

    @pytest.mark.asyncio
    async def test_extension_handshake_with_ssl(self):
        """Test extension handshake includes SSL extension."""
        manager = ExtensionManager()
        protocol_ext = manager.get_extension("protocol")

        # Encode handshake
        handshake_data = protocol_ext.encode_handshake()

        # Decode to verify SSL extension is included
        # Format: <length><message_id><json_data>
        length = struct.unpack("!I", handshake_data[:4])[0]
        message_id = handshake_data[4]
        json_data = handshake_data[5:].decode("utf-8")
        extensions = json.loads(json_data)

        assert message_id == ExtensionMessageType.EXTENDED
        assert "ssl" in extensions
        assert extensions["ssl"]["version"] == "1.0"

    @pytest.mark.asyncio
    async def test_ssl_extension_message_flow(self):
        """Test complete SSL extension message flow."""
        manager = ExtensionManager()
        # Start extensions to activate SSL extension
        await manager.start()

        protocol_ext = manager.get_extension("protocol")
        ssl_ext = manager.get_extension("ssl")

        peer_id = "integration_test_peer"

        # Simulate peer extension handshake
        peer_handshake = {"ssl": {"supports_ssl": True, "version": "1.0"}}
        manager.set_peer_extensions(peer_id, peer_handshake)

        # Verify peer supports SSL extension
        assert manager.peer_supports_extension(peer_id, "ssl")

        # Encode SSL request
        request_data = ssl_ext.encode_request()
        request_id = ssl_ext.decode_request(request_data)

        # Get SSL extension message ID
        ssl_ext_info = protocol_ext.get_extension_info("ssl")
        assert ssl_ext_info is not None

        # Encode as extension message
        extension_message = protocol_ext.encode_extension_message(
            ssl_ext_info.message_id, request_data
        )

        # Verify message format
        # Extension message format: <length><extension_message_id><payload>
        assert len(extension_message) >= 5
        length, ext_msg_id = struct.unpack("!IB", extension_message[:5])
        assert ext_msg_id == ssl_ext_info.message_id

        # Handle request (simulate peer receiving)
        response = await manager.handle_ssl_message(peer_id, ssl_ext_info.message_id, request_data)

        # Verify response
        assert response is not None
        response_msg_type, response_request_id = struct.unpack("!BI", response)
        assert response_msg_type == SSLMessageType.ACCEPT
        assert response_request_id == request_id

        # Verify negotiation state
        negotiation_state = ssl_ext.get_negotiation_state(peer_id)
        assert negotiation_state is not None
        assert negotiation_state.state == "accepted"

    @pytest.mark.asyncio
    async def test_ssl_negotiation_with_mock_connection(self):
        """Test SSL negotiation with mock peer connection."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                    "ssl_extension_enabled": True,
                    "ssl_extension_timeout": 2.0,
                    "ssl_extension_opportunistic": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            # Setup mock extension manager
            manager = ExtensionManager()
            protocol_ext = manager.get_extension("protocol")
            ssl_ext = manager.get_extension("ssl")

            peer_id = "mock_peer_123"
            manager.set_peer_extensions(peer_id, {"ssl": {"supports_ssl": True}})

            # Mock writer
            mock_writer = AsyncMock()

            # Mock SSL extension state to be accepted immediately
            negotiation_state = SSLNegotiationState(
                peer_id=peer_id, state="accepted", timestamp=time.time(), request_id=1
            )
            ssl_ext.negotiation_states[peer_id] = negotiation_state

            with patch("ccbt.peer.ssl_peer.get_extension_manager", return_value=manager):
                with patch.object(
                    connection, "_send_ssl_extension_message", return_value=None
                ) as mock_send:
                    with patch.object(
                        connection, "_wrap_connection_with_ssl", new_callable=AsyncMock
                    ) as mock_wrap:
                        mock_ssl_reader = AsyncMock()
                        mock_ssl_writer = AsyncMock()
                        mock_wrap.return_value = (mock_ssl_reader, mock_ssl_writer, True)

                        mock_reader = AsyncMock()

                        result = await connection.negotiate_ssl_after_handshake(
                            mock_reader, mock_writer, peer_id, "127.0.0.1", 6881
                        )

                        # Should return SSL reader/writer
                        assert result is not None
                        assert result[0] == mock_ssl_reader
                        assert result[1] == mock_ssl_writer
                        mock_send.assert_called_once()
                        mock_wrap.assert_called_once()

    @pytest.mark.asyncio
    async def test_ssl_negotiation_fallback_on_timeout(self):
        """Test SSL negotiation falls back to plain connection on timeout."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                    "ssl_extension_enabled": True,
                    "ssl_extension_timeout": 0.1,  # Very short timeout
                    "ssl_extension_opportunistic": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            manager = ExtensionManager()
            ssl_ext = manager.get_extension("ssl")

            peer_id = "timeout_peer"
            manager.set_peer_extensions(peer_id, {"ssl": {"supports_ssl": True}})

            # Create state that stays in "requested" (never gets response)
            negotiation_state = SSLNegotiationState(
                peer_id=peer_id, state="requested", timestamp=time.time(), request_id=1
            )
            ssl_ext.negotiation_states[peer_id] = negotiation_state

            with patch("ccbt.peer.ssl_peer.get_extension_manager", return_value=manager):
                with patch.object(
                    connection, "_send_ssl_extension_message", return_value=None
                ):
                    mock_reader = AsyncMock()
                    mock_writer = AsyncMock()

                    result = await connection.negotiate_ssl_after_handshake(
                        mock_reader, mock_writer, peer_id, "127.0.0.1", 6881
                    )

                    # Should return None (fallback to plain) due to timeout
                    assert result is None

    @pytest.mark.asyncio
    async def test_ssl_negotiation_fallback_on_rejection(self):
        """Test SSL negotiation falls back to plain connection on rejection."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                    "ssl_extension_enabled": True,
                    "ssl_extension_timeout": 2.0,
                    "ssl_extension_opportunistic": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.peer.ssl_peer.get_config", return_value=config):
            connection = SSLPeerConnection()
            connection.config = config

            manager = ExtensionManager()
            ssl_ext = manager.get_extension("ssl")

            peer_id = "reject_peer"
            manager.set_peer_extensions(peer_id, {"ssl": {"supports_ssl": True}})

            # Create rejected state
            negotiation_state = SSLNegotiationState(
                peer_id=peer_id, state="rejected", timestamp=time.time(), request_id=1
            )
            ssl_ext.negotiation_states[peer_id] = negotiation_state

            with patch("ccbt.peer.ssl_peer.get_extension_manager", return_value=manager):
                with patch.object(
                    connection, "_send_ssl_extension_message", return_value=None
                ):
                    mock_reader = AsyncMock()
                    mock_writer = AsyncMock()

                    result = await connection.negotiate_ssl_after_handshake(
                        mock_reader, mock_writer, peer_id, "127.0.0.1", 6881
                    )

                    # Should return None (fallback to plain) due to rejection
                    assert result is None

    @pytest.mark.asyncio
    async def test_ssl_extension_handshake_decoding(self):
        """Test SSL extension handshake decoding."""
        manager = ExtensionManager()
        ssl_ext = manager.get_extension("ssl")

        # Test with valid SSL handshake
        handshake_data = {"ssl": {"supports_ssl": True, "version": "1.0"}}
        result = ssl_ext.decode_handshake(handshake_data)
        assert result is True

        # Test with invalid handshake
        handshake_data_no_ssl = {"other_ext": {"version": "1.0"}}
        result = ssl_ext.decode_handshake(handshake_data_no_ssl)
        assert result is False

    @pytest.mark.asyncio
    async def test_ssl_extension_state_management(self):
        """Test SSL extension state management across multiple requests."""
        manager = ExtensionManager()
        ssl_ext = manager.get_extension("ssl")

        peer_id = "state_test_peer"

        # First request
        request_id_1 = 100
        await ssl_ext.handle_request(peer_id, request_id_1)

        state_1 = ssl_ext.get_negotiation_state(peer_id)
        assert state_1 is not None
        assert state_1.request_id == request_id_1
        assert state_1.state == "accepted"

        # Clear and test second request
        ssl_ext.clear_negotiation_state(peer_id)
        assert ssl_ext.get_negotiation_state(peer_id) is None

        request_id_2 = 200
        await ssl_ext.handle_request(peer_id, request_id_2)

        state_2 = ssl_ext.get_negotiation_state(peer_id)
        assert state_2 is not None
        assert state_2.request_id == request_id_2

    @pytest.mark.asyncio
    async def test_ssl_extension_capabilities(self):
        """Test SSL extension capabilities reporting."""
        manager = ExtensionManager()
        ssl_ext = manager.get_extension("ssl")

        # Initial capabilities
        caps = ssl_ext.get_capabilities()
        assert caps["supports_ssl"] is True
        assert caps["version"] == "1.0"
        assert caps["active_negotiations"] == 0

        # Add some negotiation states
        peer_id = "cap_test_peer"
        ssl_ext.negotiation_states[peer_id] = SSLNegotiationState(
            peer_id=peer_id, state="requested", timestamp=time.time(), request_id=1
        )

        caps = ssl_ext.get_capabilities()
        assert caps["active_negotiations"] == 1

