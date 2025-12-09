"""Unit tests for SSL capability in tracker peer parsing.

Tests that tracker peer parsing includes ssl_capable field.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.discovery, pytest.mark.security]

from ccbt.discovery.tracker import AsyncTrackerClient
from ccbt.models import PeerInfo


class TestTrackerSSLPeerParsing:
    """Tests for SSL capability in tracker peer parsing."""

    def test_parse_compact_peers_includes_ssl_capable(self):
        """Test that _parse_compact_peers includes ssl_capable field."""
        client = AsyncTrackerClient()
        
        # Compact peer format: 6 bytes per peer (4 bytes IP + 2 bytes port)
        # Peer: 192.168.1.1:6881
        peer_bytes = bytes([192, 168, 1, 1, 0x1A, 0xE1])  # 6881 = 0x1AE1
        
        peers = client._parse_compact_peers(peer_bytes)
        
        assert len(peers) == 1
        assert peers[0]["ip"] == "192.168.1.1"
        assert peers[0]["port"] == 6881
        assert peers[0]["ssl_capable"] is None  # Unknown until extension handshake
        assert peers[0]["peer_source"] == "tracker"

    def test_parse_compact_peers_multiple_includes_ssl_capable(self):
        """Test that _parse_compact_peers includes ssl_capable for multiple peers."""
        client = AsyncTrackerClient()
        
        # Two peers: 192.168.1.1:6881 and 192.168.1.2:6882
        peer_bytes = (
            bytes([192, 168, 1, 1, 0x1A, 0xE1])  # 192.168.1.1:6881
            + bytes([192, 168, 1, 2, 0x1A, 0xE2])  # 192.168.1.2:6882
        )
        
        peers = client._parse_compact_peers(peer_bytes)
        
        assert len(peers) == 2
        for peer in peers:
            assert "ssl_capable" in peer
            assert peer["ssl_capable"] is None
            assert peer["peer_source"] == "tracker"

    def test_parse_response_async_peer_info_ssl_capable(self):
        """Test that _parse_response_async creates PeerInfo with ssl_capable."""
        client = AsyncTrackerClient()
        
        # Mock bencoded response with compact peers
        from ccbt.core.bencode import BencodeEncoder
        
        encoder = BencodeEncoder()
        response_data = encoder.encode(
            {
                b"interval": 1800,
                b"peers": bytes([192, 168, 1, 1, 0x1A, 0xE1]),  # One peer
            }
        )
        
        response = client._parse_response_async(response_data)
        
        assert len(response.peers) == 1
        peer_info = response.peers[0]
        assert isinstance(peer_info, PeerInfo)
        assert peer_info.ssl_capable is None  # Unknown until extension handshake
        assert peer_info.ssl_enabled is False

