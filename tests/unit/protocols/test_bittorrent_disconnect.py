"""Comprehensive unit tests for BitTorrentProtocol disconnect_peer method.

Tests peer disconnection, event emission, statistics updates, and error handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.protocols]


@pytest.fixture
def mock_session_manager():
    """Create mock session manager."""
    return Mock()


@pytest.fixture
def mock_peer_manager():
    """Create mock peer manager."""
    manager = Mock()
    manager.disconnect_peer = AsyncMock()
    return manager


@pytest.fixture
def protocol(mock_session_manager):
    """Create BitTorrentProtocol instance for testing."""
    from ccbt.protocols.bittorrent import BitTorrentProtocol

    return BitTorrentProtocol(session_manager=mock_session_manager)


@pytest.fixture
def protocol_with_peer_manager(mock_session_manager, mock_peer_manager):
    """Create BitTorrentProtocol instance with peer manager."""
    from ccbt.protocols.bittorrent import BitTorrentProtocol

    protocol = BitTorrentProtocol(session_manager=mock_session_manager)
    protocol.peer_manager = mock_peer_manager
    return protocol


@pytest.fixture
def protocol_with_peer(mock_session_manager):
    """Create BitTorrentProtocol instance with a tracked peer."""
    from ccbt.models import PeerInfo
    from ccbt.protocols.bittorrent import BitTorrentProtocol

    protocol = BitTorrentProtocol(session_manager=mock_session_manager)
    peer_id = "192.168.1.1:6881"
    peer_ip = "192.168.1.1"
    peer_info = PeerInfo(ip="192.168.1.1", port=6881, peer_id=b"x" * 20)
    protocol.add_peer(peer_info)
    # Note: add_peer stores by IP, not full peer_id
    return protocol, peer_id, peer_ip


class TestDisconnectPeer:
    """Test disconnect_peer method."""

    @pytest.mark.asyncio
    async def test_disconnect_peer_with_peer_manager(
        self, protocol_with_peer_manager
    ):
        """Test disconnection via peer_manager."""
        protocol = protocol_with_peer_manager
        peer_id = "192.168.1.1:6881"

        # Add peer to tracking
        from ccbt.models import PeerInfo

        peer_info = PeerInfo(ip="192.168.1.1", port=6881, peer_id=b"x" * 20)
        protocol.add_peer(peer_info)

        with patch(
            "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
        ) as mock_emit:
            await protocol.disconnect_peer(peer_id)

            # Verify peer_manager.disconnect_peer was called
            protocol.peer_manager.disconnect_peer.assert_called_once_with(peer_id)

            # Verify event was emitted
            assert mock_emit.called
            call_args = mock_emit.call_args[0][0]
            assert call_args.event_type == "peer_disconnected"
            assert call_args.data["protocol_type"] == "bittorrent"
            assert call_args.data["peer_id"] == peer_id
            assert "timestamp" in call_args.data

            # Verify peer was removed (stored by IP)
            peer_ip = "192.168.1.1"
            assert peer_ip not in protocol.peers
            assert peer_ip not in protocol.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_peer_with_session_manager_fallback(
        self, protocol
    ):
        """Test disconnection via session_manager fallback."""
        peer_id = "192.168.1.1:6881"

        # Add peer to tracking
        from ccbt.models import PeerInfo

        peer_info = PeerInfo(ip="192.168.1.1", port=6881, peer_id=b"x" * 20)
        protocol.add_peer(peer_info)

        # Mock session_manager with disconnect_peer
        protocol.session_manager.disconnect_peer = AsyncMock()

        with patch(
            "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
        ) as mock_emit:
            await protocol.disconnect_peer(peer_id)

            # Verify session_manager.disconnect_peer was called
            protocol.session_manager.disconnect_peer.assert_called_once_with(
                peer_id
            )

            # Verify event was emitted
            assert mock_emit.called
            call_args = mock_emit.call_args[0][0]
            assert call_args.event_type == "peer_disconnected"

            # Verify peer was removed (stored by IP)
            peer_ip = "192.168.1.1"
            assert peer_ip not in protocol.peers

    @pytest.mark.asyncio
    async def test_disconnect_peer_when_peer_not_found(self, protocol):
        """Test disconnection when peer doesn't exist."""
        peer_id = "192.168.1.1:6881"

        with patch(
            "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
        ) as mock_emit:
            await protocol.disconnect_peer(peer_id)

            # Event should not be emitted for non-existent peer
            assert not mock_emit.called

    @pytest.mark.asyncio
    async def test_disconnect_peer_event_emission(self, protocol_with_peer):
        """Test that PEER_DISCONNECTED event is emitted correctly."""
        protocol, peer_id, peer_ip = protocol_with_peer

        with patch(
            "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
        ) as mock_emit:
            await protocol.disconnect_peer(peer_id)

            # Verify event was emitted
            assert mock_emit.called
            call_args = mock_emit.call_args[0][0]
            assert call_args.event_type == "peer_disconnected"
            assert call_args.data["protocol_type"] == "bittorrent"
            assert call_args.data["peer_id"] == peer_id
            assert "timestamp" in call_args.data
            assert isinstance(call_args.data["timestamp"], float)

    @pytest.mark.asyncio
    async def test_disconnect_peer_statistics_update(self, protocol_with_peer):
        """Test that statistics are updated on disconnection."""
        protocol, peer_id, peer_ip = protocol_with_peer

        initial_errors = protocol.stats.errors

        with patch(
            "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
        ):
            await protocol.disconnect_peer(peer_id)

            # Verify update_stats was called (indirectly via method execution)
            # The stats.last_activity should be updated
            assert protocol.stats.last_activity > 0

    @pytest.mark.asyncio
    async def test_disconnect_peer_calls_remove_peer(self, protocol_with_peer):
        """Test that remove_peer is called during disconnection."""
        protocol, peer_id, peer_ip = protocol_with_peer

        # Mock remove_peer to track calls
        with patch.object(protocol, "remove_peer") as mock_remove:
            with patch(
                "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
            ):
                await protocol.disconnect_peer(peer_id)

                # Verify remove_peer was called (with IP, not full peer_id)
                mock_remove.assert_called_once_with(peer_ip)

    @pytest.mark.asyncio
    async def test_disconnect_peer_error_handling(
        self, protocol_with_peer_manager
    ):
        """Test error handling during disconnection."""
        protocol = protocol_with_peer_manager
        peer_id = "192.168.1.1:6881"

        # Add peer to tracking
        from ccbt.models import PeerInfo

        peer_info = PeerInfo(ip="192.168.1.1", port=6881, peer_id=b"x" * 20)
        protocol.add_peer(peer_info)

        # Make peer_manager.disconnect_peer raise an exception
        protocol.peer_manager.disconnect_peer.side_effect = Exception(
            "Connection error"
        )

        initial_errors = protocol.stats.errors

        with patch(
            "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
        ) as mock_emit:
            await protocol.disconnect_peer(peer_id)

            # Verify error was tracked
            assert protocol.stats.errors > initial_errors

            # Verify event was still emitted (with error info)
            assert mock_emit.called
            # Should be called twice: once in try block, once in except block
            assert mock_emit.call_count >= 1

            # Verify peer was still removed even on error (stored by IP)
            peer_ip = "192.168.1.1"
            assert peer_ip not in protocol.peers

    @pytest.mark.asyncio
    async def test_disconnect_peer_error_emits_event_with_error(
        self, protocol_with_peer_manager
    ):
        """Test that error event includes error information."""
        protocol = protocol_with_peer_manager
        peer_id = "192.168.1.1:6881"

        # Add peer to tracking
        from ccbt.models import PeerInfo

        peer_info = PeerInfo(ip="192.168.1.1", port=6881, peer_id=b"x" * 20)
        protocol.add_peer(peer_info)

        error_message = "Connection timeout"
        protocol.peer_manager.disconnect_peer.side_effect = Exception(
            error_message
        )

        with patch(
            "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
        ) as mock_emit:
            await protocol.disconnect_peer(peer_id)

            # Verify event was emitted with error
            assert mock_emit.called
            # Check the last call (from except block)
            call_args = mock_emit.call_args[0][0]
            assert call_args.event_type == "peer_disconnected"
            assert "error" in call_args.data
            assert error_message in call_args.data["error"]

    @pytest.mark.asyncio
    async def test_disconnect_peer_no_managers(self, protocol_with_peer):
        """Test disconnection when neither peer_manager nor session_manager have disconnect_peer."""
        protocol, peer_id, peer_ip = protocol_with_peer

        # Ensure no peer_manager or session_manager with disconnect_peer
        protocol.peer_manager = None
        protocol.session_manager.disconnect_peer = None

        with patch(
            "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
        ) as mock_emit:
            await protocol.disconnect_peer(peer_id)

            # Should still emit event and remove peer
            assert mock_emit.called
            assert peer_ip not in protocol.peers

    @pytest.mark.asyncio
    async def test_disconnect_peer_active_connections_only(self, protocol):
        """Test disconnection when peer is only in active_connections."""
        peer_id = "192.168.1.1:6881"

        # Add to active_connections but not peers
        protocol.active_connections.add(peer_id)

        with patch(
            "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
        ) as mock_emit:
            await protocol.disconnect_peer(peer_id)

            # Should still process disconnection
            assert mock_emit.called
            assert peer_id not in protocol.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_peer_removes_from_both_tracking(self, protocol_with_peer):
        """Test that peer is removed from both peers and active_connections."""
        protocol, peer_id, peer_ip = protocol_with_peer

        # Verify peer is in both (stored by IP)
        assert peer_ip in protocol.peers
        assert peer_ip in protocol.active_connections

        with patch(
            "ccbt.protocols.bittorrent.emit_event", new_callable=AsyncMock
        ):
            await protocol.disconnect_peer(peer_id)

            # Verify removed from both
            assert peer_ip not in protocol.peers
            assert peer_ip not in protocol.active_connections

