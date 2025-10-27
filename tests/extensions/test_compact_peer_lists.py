"""
Tests for Compact Peer Lists (BEP 23).
"""

import socket

import pytest

from ccbt.extensions.compact import CompactPeer, CompactPeerLists
from ccbt.models import PeerInfo


class TestCompactPeerLists:
    """Tests for Compact Peer Lists."""

    @pytest.fixture
    def sample_peers(self):
        """Create sample peers for testing."""
        return [
            CompactPeer(ip="192.168.1.1", port=6881, is_ipv6=False),
            CompactPeer(ip="192.168.1.2", port=6882, is_ipv6=False),
            CompactPeer(ip="10.0.0.1", port=6883, is_ipv6=False),
        ]

    @pytest.fixture
    def sample_ipv6_peers(self):
        """Create sample IPv6 peers for testing."""
        return [
            CompactPeer(ip="2001:db8::1", port=6881, is_ipv6=True),
            CompactPeer(ip="2001:db8::2", port=6882, is_ipv6=True),
        ]

    def test_compact_peer_creation(self):
        """Test CompactPeer creation."""
        peer = CompactPeer(ip="192.168.1.1", port=6881, is_ipv6=False)

        assert peer.ip == "192.168.1.1"
        assert peer.port == 6881
        assert not peer.is_ipv6

    def test_compact_peer_to_peer_info(self):
        """Test CompactPeer to PeerInfo conversion."""
        peer = CompactPeer(ip="192.168.1.1", port=6881, is_ipv6=False)
        peer_info = peer.to_peer_info()

        assert isinstance(peer_info, PeerInfo)
        assert peer_info.ip == "192.168.1.1"
        assert peer_info.port == 6881

    def test_compact_peer_from_peer_info(self):
        """Test CompactPeer from PeerInfo creation."""
        peer_info = PeerInfo(ip="192.168.1.1", port=6881)
        peer = CompactPeer.from_peer_info(peer_info)

        assert peer.ip == "192.168.1.1"
        assert peer.port == 6881
        assert not peer.is_ipv6  # Should detect IPv4

    def test_encode_peer_ipv4(self, sample_peers):
        """Test encoding IPv4 peer."""
        peer = sample_peers[0]
        data = CompactPeerLists.encode_peer(peer)

        assert isinstance(data, bytes)
        assert len(data) == 6  # 4 bytes IP + 2 bytes port

        # Decode and verify
        ip_bytes, port = struct.unpack("!4sH", data)
        decoded_ip = socket.inet_ntop(socket.AF_INET, ip_bytes)
        assert decoded_ip == peer.ip
        assert port == peer.port

    def test_decode_peer_ipv4(self):
        """Test decoding IPv4 peer."""
        ip = "192.168.1.1"
        port = 6881

        # Encode manually
        ip_bytes = socket.inet_aton(ip)
        data = struct.pack("!4sH", ip_bytes, port)

        # Decode
        peer = CompactPeerLists.decode_peer(data, is_ipv6=False)
        assert peer.ip == ip
        assert peer.port == port
        assert not peer.is_ipv6

    def test_encode_peer_ipv6(self, sample_ipv6_peers):
        """Test encoding IPv6 peer."""
        peer = sample_ipv6_peers[0]
        data = CompactPeerLists.encode_peer(peer)

        assert isinstance(data, bytes)
        assert len(data) == 18  # 16 bytes IP + 2 bytes port

        # Decode and verify
        ip_bytes, port = struct.unpack("!16sH", data)
        decoded_ip = socket.inet_ntop(socket.AF_INET6, ip_bytes)
        assert decoded_ip == peer.ip
        assert port == peer.port

    def test_decode_peer_ipv6(self):
        """Test decoding IPv6 peer."""
        ip = "2001:db8::1"
        port = 6881

        # Encode manually
        ip_bytes = socket.inet_pton(socket.AF_INET6, ip)
        data = struct.pack("!16sH", ip_bytes, port)

        # Decode
        peer = CompactPeerLists.decode_peer(data, is_ipv6=True)
        assert peer.ip == ip
        assert peer.port == port
        assert peer.is_ipv6

    def test_encode_peers_list_ipv4(self, sample_peers):
        """Test encoding list of IPv4 peers."""
        data = CompactPeerLists.encode_peers_list(sample_peers)

        assert isinstance(data, bytes)
        assert len(data) == len(sample_peers) * 6  # 6 bytes per peer

    def test_decode_peers_list_ipv4(self, sample_peers):
        """Test decoding list of IPv4 peers."""
        # Encode
        data = CompactPeerLists.encode_peers_list(sample_peers)

        # Decode
        decoded_peers = CompactPeerLists.decode_peers_list(data, is_ipv6=False)

        assert len(decoded_peers) == len(sample_peers)
        for i, peer in enumerate(decoded_peers):
            assert peer.ip == sample_peers[i].ip
            assert peer.port == sample_peers[i].port
            assert peer.is_ipv6 == sample_peers[i].is_ipv6

    def test_encode_peers_list_ipv6(self, sample_ipv6_peers):
        """Test encoding list of IPv6 peers."""
        data = CompactPeerLists.encode_peers_list(sample_ipv6_peers)

        assert isinstance(data, bytes)
        assert len(data) == len(sample_ipv6_peers) * 18  # 18 bytes per peer

    def test_decode_peers_list_ipv6(self, sample_ipv6_peers):
        """Test decoding list of IPv6 peers."""
        # Encode
        data = CompactPeerLists.encode_peers_list(sample_ipv6_peers)

        # Decode
        decoded_peers = CompactPeerLists.decode_peers_list(data, is_ipv6=True)

        assert len(decoded_peers) == len(sample_ipv6_peers)
        for i, peer in enumerate(decoded_peers):
            assert peer.ip == sample_ipv6_peers[i].ip
            assert peer.port == sample_ipv6_peers[i].port
            assert peer.is_ipv6 == sample_ipv6_peers[i].is_ipv6

    def test_encode_peers_dict(self, sample_peers, sample_ipv6_peers):
        """Test encoding peers as dictionary."""
        all_peers = sample_peers + sample_ipv6_peers
        result = CompactPeerLists.encode_peers_dict(all_peers)

        assert isinstance(result, dict)
        assert "peers" in result
        assert "peers6" in result

        # Check IPv4 peers
        assert len(result["peers"]) == len(sample_peers) * 6

        # Check IPv6 peers
        assert len(result["peers6"]) == len(sample_ipv6_peers) * 18

    def test_decode_peers_dict(self, sample_peers, sample_ipv6_peers):
        """Test decoding peers from dictionary."""
        all_peers = sample_peers + sample_ipv6_peers
        encoded_dict = CompactPeerLists.encode_peers_dict(all_peers)

        # Decode
        decoded_peers = CompactPeerLists.decode_peers_dict(encoded_dict)

        assert len(decoded_peers) == len(all_peers)
        # Note: Order might be different due to separate encoding

    def test_convert_peer_info_to_compact(self):
        """Test converting PeerInfo to CompactPeer."""
        peer_info = PeerInfo(ip="192.168.1.1", port=6881)
        compact_peer = CompactPeerLists.convert_peer_info_to_compact(peer_info)

        assert compact_peer.ip == peer_info.ip
        assert compact_peer.port == peer_info.port
        assert not compact_peer.is_ipv6  # Should detect IPv4

    def test_convert_compact_to_peer_info(self):
        """Test converting CompactPeer to PeerInfo."""
        compact_peer = CompactPeer(ip="192.168.1.1", port=6881, is_ipv6=False)
        peer_info = CompactPeerLists.convert_compact_to_peer_info(compact_peer)

        assert isinstance(peer_info, PeerInfo)
        assert peer_info.ip == compact_peer.ip
        assert peer_info.port == compact_peer.port

    def test_convert_peer_info_list_to_compact(self):
        """Test converting list of PeerInfo to list of CompactPeer."""
        peer_infos = [
            PeerInfo(ip="192.168.1.1", port=6881),
            PeerInfo(ip="192.168.1.2", port=6882),
        ]

        compact_peers = CompactPeerLists.convert_peer_info_list_to_compact(peer_infos)

        assert len(compact_peers) == len(peer_infos)
        for i, compact_peer in enumerate(compact_peers):
            assert compact_peer.ip == peer_infos[i].ip
            assert compact_peer.port == peer_infos[i].port

    def test_convert_compact_list_to_peer_info(self, sample_peers):
        """Test converting list of CompactPeer to list of PeerInfo."""
        peer_infos = CompactPeerLists.convert_compact_list_to_peer_info(sample_peers)

        assert len(peer_infos) == len(sample_peers)
        for i, peer_info in enumerate(peer_infos):
            assert isinstance(peer_info, PeerInfo)
            assert peer_info.ip == sample_peers[i].ip
            assert peer_info.port == sample_peers[i].port

    def test_get_peer_size(self):
        """Test getting peer size."""
        assert CompactPeerLists.get_peer_size(is_ipv6=False) == 6
        assert CompactPeerLists.get_peer_size(is_ipv6=True) == 18

    def test_estimate_peers_list_size(self, sample_peers, sample_ipv6_peers):
        """Test estimating peers list size."""
        # IPv4 peers
        size = CompactPeerLists.estimate_peers_list_size(sample_peers)
        assert size == len(sample_peers) * 6

        # IPv6 peers
        size = CompactPeerLists.estimate_peers_list_size(sample_ipv6_peers)
        assert size == len(sample_ipv6_peers) * 18

    def test_split_peers_by_ip_version(self, sample_peers, sample_ipv6_peers):
        """Test splitting peers by IP version."""
        all_peers = sample_peers + sample_ipv6_peers
        ipv4_peers, ipv6_peers = CompactPeerLists.split_peers_by_ip_version(all_peers)

        assert len(ipv4_peers) == len(sample_peers)
        assert len(ipv6_peers) == len(sample_ipv6_peers)

        for peer in ipv4_peers:
            assert not peer.is_ipv6
        for peer in ipv6_peers:
            assert peer.is_ipv6

    def test_merge_peers_lists(self, sample_peers):
        """Test merging peer lists."""
        peers1 = sample_peers[:2]
        peers2 = sample_peers[1:]  # Overlap with peers1

        merged = CompactPeerLists.merge_peers_lists(peers1, peers2)

        # Should have unique peers
        assert len(merged) == len(sample_peers)

        # Check uniqueness
        peer_keys = set((peer.ip, peer.port, peer.is_ipv6) for peer in merged)
        assert len(peer_keys) == len(merged)

    def test_filter_peers_by_ip_version(self, sample_peers, sample_ipv6_peers):
        """Test filtering peers by IP version."""
        all_peers = sample_peers + sample_ipv6_peers

        # Filter IPv4 only
        ipv4_peers = CompactPeerLists.filter_peers_by_ip_version(all_peers, ipv6_only=False)
        assert len(ipv4_peers) == len(sample_peers)
        for peer in ipv4_peers:
            assert not peer.is_ipv6

        # Filter IPv6 only
        ipv6_peers = CompactPeerLists.filter_peers_by_ip_version(all_peers, ipv6_only=True)
        assert len(ipv6_peers) == len(sample_ipv6_peers)
        for peer in ipv6_peers:
            assert peer.is_ipv6

    def test_validate_peer_data(self):
        """Test validating peer data."""
        # Valid IPv4 data
        valid_ipv4_data = b"\x00" * 6  # 6 bytes
        assert CompactPeerLists.validate_peer_data(valid_ipv4_data, is_ipv6=False)

        # Invalid IPv4 data
        invalid_ipv4_data = b"\x00" * 5  # 5 bytes (too short)
        assert not CompactPeerLists.validate_peer_data(invalid_ipv4_data, is_ipv6=False)

        # Valid IPv6 data
        valid_ipv6_data = b"\x00" * 18  # 18 bytes
        assert CompactPeerLists.validate_peer_data(valid_ipv6_data, is_ipv6=True)

        # Invalid IPv6 data
        invalid_ipv6_data = b"\x00" * 17  # 17 bytes (too short)
        assert not CompactPeerLists.validate_peer_data(invalid_ipv6_data, is_ipv6=True)

    def test_get_peer_count(self):
        """Test getting peer count."""
        # IPv4 peers
        ipv4_data = b"\x00" * 12  # 2 peers * 6 bytes each
        assert CompactPeerLists.get_peer_count(ipv4_data, is_ipv6=False) == 2

        # IPv6 peers
        ipv6_data = b"\x00" * 36  # 2 peers * 18 bytes each
        assert CompactPeerLists.get_peer_count(ipv6_data, is_ipv6=True) == 2

    def test_roundtrip_encoding(self, sample_peers):
        """Test roundtrip encoding/decoding."""
        # Encode
        encoded = CompactPeerLists.encode_peers_list(sample_peers)

        # Decode
        decoded = CompactPeerLists.decode_peers_list(encoded, is_ipv6=False)

        assert len(decoded) == len(sample_peers)
        for i, peer in enumerate(decoded):
            assert peer.ip == sample_peers[i].ip
            assert peer.port == sample_peers[i].port
            assert peer.is_ipv6 == sample_peers[i].is_ipv6

    def test_invalid_ip_address(self):
        """Test handling invalid IP addresses."""
        # Invalid IPv4
        with pytest.raises(ValueError):
            CompactPeerLists.encode_peer(CompactPeer(ip="invalid", port=6881, is_ipv6=False))

        # Invalid IPv6
        with pytest.raises(ValueError):
            CompactPeerLists.encode_peer(CompactPeer(ip="invalid", port=6881, is_ipv6=True))

    def test_empty_peers_list(self):
        """Test handling empty peers list."""
        empty_peers = []
        data = CompactPeerLists.encode_peers_list(empty_peers)
        assert data == b""

        decoded = CompactPeerLists.decode_peers_list(data, is_ipv6=False)
        assert decoded == []


# Import struct for testing
import struct
