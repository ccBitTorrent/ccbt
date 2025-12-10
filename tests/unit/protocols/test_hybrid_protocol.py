"""Tests for hybrid protocol implementation.
"""

import pytest

from ccbt.models import PeerInfo, TorrentInfo
from ccbt.protocols.base import ProtocolState, ProtocolStats, ProtocolType
from ccbt.protocols.hybrid import HybridProtocol, HybridStrategy

# Check if WebTorrent is available - use same check as hybrid.py
try:
    from ccbt.protocols import WebTorrentProtocol  # noqa: F401

    HAS_WEBTORRENT = WebTorrentProtocol is not None
except (ImportError, AttributeError):
    HAS_WEBTORRENT = False


class TestHybridProtocol:
    """Tests for HybridProtocol class."""

    @pytest.fixture
    def sample_peer_info(self):
        """Create sample peer info."""
        return PeerInfo(ip="192.168.1.1", port=6881, peer_id=b"test_peer_id")

    @pytest.fixture
    def sample_torrent_info(self):
        """Create sample torrent info."""
        return TorrentInfo(
            name="test_torrent",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com/announce",
            files=[],
            total_length=1024,
            piece_length=16384,
            pieces=[b"\x00" * 20],
            num_pieces=1,
        )

    def test_hybrid_protocol_creation(self):
        """Test hybrid protocol creation."""
        # Use strategy based on WebTorrent availability
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        assert protocol.protocol_type == ProtocolType.HYBRID
        assert protocol.state == ProtocolState.DISCONNECTED
        assert isinstance(protocol.strategy, HybridStrategy)
        # Count may be 2 or 3 depending on WebTorrent availability
        expected_count = 3 if HAS_WEBTORRENT else 2
        assert len(protocol.sub_protocols) == expected_count

    def test_hybrid_protocol_with_strategy(self):
        """Test hybrid protocol with custom strategy."""
        # Use strategy without WebTorrent to avoid import errors
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=False,
            use_ipfs=True,
            bittorrent_weight=0.7,
            webtorrent_weight=0.0,
            ipfs_weight=0.3,
        )

        protocol = HybridProtocol(strategy)

        assert protocol.strategy == strategy
        assert protocol.strategy.use_bittorrent
        assert not protocol.strategy.use_webtorrent
        assert protocol.strategy.use_ipfs
        assert protocol.strategy.bittorrent_weight == 0.7
        assert protocol.strategy.webtorrent_weight == 0.0
        assert protocol.strategy.ipfs_weight == 0.3

    @pytest.mark.skipif(
        not HAS_WEBTORRENT, reason="WebTorrent protocol not available"
    )
    def test_initialize_sub_protocols(self):
        """Test sub-protocol initialization."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=True,
            use_ipfs=False,
        )

        protocol = HybridProtocol(strategy)

        # Should have BitTorrent and WebTorrent protocols
        assert ProtocolType.BITTORRENT in protocol.sub_protocols
        assert ProtocolType.WEBTORRENT in protocol.sub_protocols
        assert ProtocolType.IPFS not in protocol.sub_protocols

        # Check protocol weights (using default values from HybridStrategy)
        assert protocol.protocol_weights[ProtocolType.BITTORRENT] == 0.5
        assert protocol.protocol_weights[ProtocolType.WEBTORRENT] == 0.25
        assert ProtocolType.IPFS not in protocol.protocol_weights

    @pytest.mark.skipif(
        not HAS_WEBTORRENT, reason="WebTorrent protocol not available"
    )
    def test_protocol_weights(self):
        """Test protocol weights."""
        strategy = HybridStrategy(
            bittorrent_weight=0.8,
            webtorrent_weight=0.2,
            ipfs_weight=0.0,
        )

        protocol = HybridProtocol(strategy)

        assert protocol.protocol_weights[ProtocolType.BITTORRENT] == 0.8
        assert protocol.protocol_weights[ProtocolType.WEBTORRENT] == 0.2
        assert protocol.protocol_weights[ProtocolType.IPFS] == 0.0

    def test_protocol_performance(self):
        """Test protocol performance tracking."""
        # Use strategy without WebTorrent if not available
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        # Initial performance scores
        for protocol_type in protocol.sub_protocols:
            assert protocol.protocol_performance[protocol_type] == 1.0

        # Update performance
        protocol._update_protocol_performance(ProtocolType.BITTORRENT, True)
        assert protocol.protocol_performance[ProtocolType.BITTORRENT] > 1.0

        protocol._update_protocol_performance(ProtocolType.BITTORRENT, False)
        assert protocol.protocol_performance[ProtocolType.BITTORRENT] < 1.0

    def test_select_best_protocol(self, sample_peer_info):
        """Test best protocol selection."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        # Should return a protocol if available
        best_protocol = protocol._select_best_protocol(sample_peer_info)
        assert best_protocol is not None
        assert best_protocol.protocol_type in protocol.sub_protocols

    def test_find_protocol_for_peer(self, sample_peer_info):
        """Test finding protocol for peer."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        # No peers connected yet
        found_protocol = protocol._find_protocol_for_peer(sample_peer_info.ip)
        assert found_protocol is None

    def test_deduplicate_peers(self):
        """Test peer deduplication."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        # Create duplicate peers
        peer1 = PeerInfo(ip="192.168.1.1", port=6881)
        peer2 = PeerInfo(ip="192.168.1.1", port=6881)  # Duplicate
        peer3 = PeerInfo(ip="192.168.1.2", port=6882)

        peers = [peer1, peer2, peer3]
        unique_peers = protocol._deduplicate_peers(peers)

        assert len(unique_peers) == 2
        assert unique_peers[0] == peer1
        assert unique_peers[1] == peer3

    def test_get_sub_protocols(self):
        """Test getting sub-protocols."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        sub_protocols = protocol.get_sub_protocols()
        assert isinstance(sub_protocols, dict)
        assert len(sub_protocols) > 0

        for protocol_type, sub_protocol in sub_protocols.items():
            assert isinstance(protocol_type, ProtocolType)
            assert hasattr(sub_protocol, "protocol_type")

    def test_get_protocol_weights(self):
        """Test getting protocol weights."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        weights = protocol.get_protocol_weights()
        assert isinstance(weights, dict)

        for protocol_type, weight in weights.items():
            assert isinstance(protocol_type, ProtocolType)
            assert isinstance(weight, float)
            assert 0.0 <= weight <= 1.0

    def test_get_protocol_performance(self):
        """Test getting protocol performance."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        performance = protocol.get_protocol_performance()
        assert isinstance(performance, dict)

        for protocol_type, score in performance.items():
            assert isinstance(protocol_type, ProtocolType)
            assert isinstance(score, float)
            assert score > 0.0

    @pytest.mark.skipif(
        not HAS_WEBTORRENT, reason="WebTorrent protocol not available"
    )
    def test_update_strategy(self):
        """Test updating strategy."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        # New strategy
        new_strategy = HybridStrategy(
            use_bittorrent=False,
            use_webtorrent=True,
            use_ipfs=True,
            bittorrent_weight=0.0,
            webtorrent_weight=0.5,
            ipfs_weight=0.5,
        )

        protocol.update_strategy(new_strategy)

        assert protocol.strategy == new_strategy
        assert not protocol.strategy.use_bittorrent
        assert protocol.strategy.use_webtorrent
        assert protocol.strategy.use_ipfs

    def test_get_hybrid_stats(self):
        """Test getting hybrid statistics."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        stats = protocol.get_hybrid_stats()
        assert isinstance(stats, dict)

        # Check required fields
        assert "protocol_type" in stats
        assert "state" in stats
        assert "strategy" in stats
        assert "protocol_weights" in stats
        assert "protocol_performance" in stats
        assert "sub_protocols" in stats
        assert "total_peers" in stats
        assert "active_connections" in stats

        assert stats["protocol_type"] == "hybrid"
        assert stats["total_peers"] == 0
        assert stats["active_connections"] == 0

    def test_capabilities(self):
        """Test hybrid protocol capabilities."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        caps = protocol.get_capabilities()
        assert caps.supports_encryption
        assert caps.supports_metadata
        assert caps.supports_pex
        assert caps.supports_dht
        # Hybrid protocol claims to support WebRTC regardless of availability
        # (capabilities are set at initialization, not dynamically)
        assert caps.supports_webrtc is True
        assert caps.supports_ipfs
        assert caps.max_connections > 0
        assert caps.supports_ipv6

    @pytest.mark.asyncio
    async def test_state_management(self):
        """Test state management."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        # Initial state
        assert protocol.get_state() == ProtocolState.DISCONNECTED

        # Change state
        protocol.set_state(ProtocolState.CONNECTED)
        assert protocol.get_state() == ProtocolState.CONNECTED

        # Change to active
        protocol.set_state(ProtocolState.ACTIVE)
        assert protocol.get_state() == ProtocolState.ACTIVE

    @pytest.mark.asyncio
    async def test_peer_management(self, sample_peer_info):
        """Test peer management."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        # Add peer
        protocol.add_peer(sample_peer_info)

        assert len(protocol.peers) == 1
        assert sample_peer_info.ip in protocol.peers
        assert sample_peer_info.ip in protocol.active_connections

        # Get peer
        peer = protocol.get_peer(sample_peer_info.ip)
        assert peer == sample_peer_info

        # Check if connected
        assert protocol.is_connected(sample_peer_info.ip)

        # Remove peer
        protocol.remove_peer(sample_peer_info.ip)

        assert len(protocol.peers) == 0
        assert sample_peer_info.ip not in protocol.active_connections
        assert not protocol.is_connected(sample_peer_info.ip)

    def test_stats_management(self):
        """Test statistics management."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        stats = protocol.get_stats()
        assert isinstance(stats, ProtocolStats)
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0

        # Update stats
        protocol.update_stats(
            bytes_sent=100,
            bytes_received=200,
            messages_sent=5,
            messages_received=3,
        )

        updated_stats = protocol.get_stats()
        assert updated_stats.bytes_sent == 100
        assert updated_stats.bytes_received == 200
        assert updated_stats.messages_sent == 5
        assert updated_stats.messages_received == 3

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        strategy = HybridStrategy(
            use_bittorrent=True,
            use_webtorrent=HAS_WEBTORRENT,
            use_ipfs=True,
        )
        protocol = HybridProtocol(strategy)

        # Disconnected state
        assert not await protocol.health_check()

        # Connected state
        protocol.set_state(ProtocolState.CONNECTED)
        assert await protocol.health_check()

        # Active state
        protocol.set_state(ProtocolState.ACTIVE)
        assert await protocol.health_check()

        # Error state
        protocol.set_state(ProtocolState.ERROR)
        assert not await protocol.health_check()
