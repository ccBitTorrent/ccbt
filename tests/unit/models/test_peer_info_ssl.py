"""Unit tests for PeerInfo SSL capability tracking.

Tests SSL capability fields in PeerInfo model and SSL capability propagation.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.models, pytest.mark.security]

from ccbt.models import PeerInfo


class TestPeerInfoSSL:
    """Tests for PeerInfo SSL capability fields."""

    def test_peer_info_ssl_fields_default(self):
        """Test PeerInfo SSL fields have correct defaults."""
        peer = PeerInfo(ip="192.168.1.1", port=6881)
        assert peer.ssl_capable is None
        assert peer.ssl_enabled is False

    def test_peer_info_ssl_capable_none(self):
        """Test PeerInfo with ssl_capable=None (unknown)."""
        peer = PeerInfo(ip="192.168.1.1", port=6881, ssl_capable=None)
        assert peer.ssl_capable is None
        assert peer.ssl_enabled is False

    def test_peer_info_ssl_capable_true(self):
        """Test PeerInfo with ssl_capable=True."""
        peer = PeerInfo(ip="192.168.1.1", port=6881, ssl_capable=True)
        assert peer.ssl_capable is True
        assert peer.ssl_enabled is False  # Not yet enabled

    def test_peer_info_ssl_capable_false(self):
        """Test PeerInfo with ssl_capable=False."""
        peer = PeerInfo(ip="192.168.1.1", port=6881, ssl_capable=False)
        assert peer.ssl_capable is False
        assert peer.ssl_enabled is False

    def test_peer_info_ssl_enabled(self):
        """Test PeerInfo with ssl_enabled=True."""
        peer = PeerInfo(
            ip="192.168.1.1", port=6881, ssl_capable=True, ssl_enabled=True
        )
        assert peer.ssl_capable is True
        assert peer.ssl_enabled is True

    def test_peer_info_ssl_hash_unchanged(self):
        """Test that SSL fields don't affect hash (based on IP:port only)."""
        peer1 = PeerInfo(ip="192.168.1.1", port=6881, ssl_capable=None)
        peer2 = PeerInfo(ip="192.168.1.1", port=6881, ssl_capable=True)
        peer3 = PeerInfo(
            ip="192.168.1.1", port=6881, ssl_capable=True, ssl_enabled=True
        )
        assert hash(peer1) == hash(peer2)
        assert hash(peer2) == hash(peer3)

    def test_peer_info_ssl_equality_unchanged(self):
        """Test that SSL fields don't affect equality (based on IP:port only)."""
        peer1 = PeerInfo(ip="192.168.1.1", port=6881, ssl_capable=None)
        peer2 = PeerInfo(ip="192.168.1.1", port=6881, ssl_capable=True)
        peer3 = PeerInfo(
            ip="192.168.1.1", port=6881, ssl_capable=True, ssl_enabled=True
        )
        assert peer1 == peer2
        assert peer2 == peer3


