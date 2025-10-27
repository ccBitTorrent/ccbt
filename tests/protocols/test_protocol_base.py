"""
Tests for protocol base classes.
"""

from typing import Dict, List, Optional

import pytest

from ccbt.models import PeerInfo, TorrentInfo
from ccbt.protocols.base import (
    Protocol,
    ProtocolCapabilities,
    ProtocolManager,
    ProtocolState,
    ProtocolStats,
    ProtocolType,
)


class TestProtocol(Protocol):
    """Concrete implementation of Protocol for testing."""

    def __init__(self, protocol_type: ProtocolType):
        super().__init__(protocol_type)

    async def start(self) -> None:
        """Start the protocol."""
        self.state = ProtocolState.CONNECTED

    async def stop(self) -> None:
        """Stop the protocol."""
        self.state = ProtocolState.DISCONNECTED

    async def connect_peer(self, peer_info: PeerInfo) -> bool:
        """Connect to a peer."""
        peer_key = f"{peer_info.ip}:{peer_info.port}"
        if peer_key not in self.active_connections:
            self.active_connections.add(peer_key)
            self.peers[peer_key] = peer_info
            return True
        return False

    async def disconnect_peer(self, peer_id: str) -> None:
        """Disconnect from a peer."""
        self.active_connections.discard(peer_id)
        self.peers.pop(peer_id, None)

    async def send_message(self, peer_id: str, message: bytes) -> bool:
        """Send message to peer."""
        if peer_id in self.active_connections:
            self.stats.messages_sent += 1
            return True
        return False

    async def receive_message(self, peer_id: str) -> Optional[bytes]:
        """Receive message from peer."""
        if peer_id in self.active_connections:
            self.stats.messages_received += 1
            return b"test_message"
        return None

    async def announce_torrent(self, torrent_info: TorrentInfo) -> List[PeerInfo]:
        """Announce torrent and get peers."""
        self.stats.announces += 1
        return [PeerInfo(ip="127.0.0.1", port=6881)]

    async def scrape_torrent(self, torrent_info: TorrentInfo) -> Dict[str, int]:
        """Scrape torrent statistics."""
        return {"seeders": 10, "leechers": 5, "completed": 100}

    def health_check(self) -> bool:
        """Check protocol health."""
        return self.state in [ProtocolState.CONNECTED, ProtocolState.ACTIVE]


class TestProtocolBase:
    """Tests for base Protocol class."""

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

    def test_protocol_creation(self):
        """Test protocol creation."""
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        assert protocol.protocol_type == ProtocolType.BITTORRENT
        assert protocol.state == ProtocolState.DISCONNECTED
        assert isinstance(protocol.capabilities, ProtocolCapabilities)
        assert isinstance(protocol.stats, ProtocolStats)
        assert len(protocol.peers) == 0
        assert len(protocol.active_connections) == 0

    def test_capabilities_management(self):
        """Test capabilities management."""
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        caps = protocol.get_capabilities()
        assert isinstance(caps, ProtocolCapabilities)

        # Set new capabilities
        new_caps = ProtocolCapabilities(
            supports_encryption=True,
            supports_metadata=True,
            max_connections=100,
        )
        protocol.capabilities = new_caps

        updated_caps = protocol.get_capabilities()
        assert updated_caps.supports_encryption
        assert updated_caps.supports_metadata
        assert updated_caps.max_connections == 100

    def test_stats_management(self):
        """Test statistics management."""
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        stats = protocol.get_stats()
        assert isinstance(stats, ProtocolStats)
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0

        # Update stats
        protocol.update_stats(bytes_sent=100, bytes_received=200, messages_sent=5, messages_received=3)

        updated_stats = protocol.get_stats()
        assert updated_stats.bytes_sent == 100
        assert updated_stats.bytes_received == 200
        assert updated_stats.messages_sent == 5
        assert updated_stats.messages_received == 3

    def test_peer_management(self, sample_peer_info):
        """Test peer management."""
        protocol = TestProtocol(ProtocolType.BITTORRENT)

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

    def test_state_management(self):
        """Test state management."""
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        # Initial state
        assert protocol.get_state() == ProtocolState.DISCONNECTED

        # Change state
        protocol.set_state(ProtocolState.CONNECTED)
        assert protocol.get_state() == ProtocolState.CONNECTED

        # Change to active
        protocol.set_state(ProtocolState.ACTIVE)
        assert protocol.get_state() == ProtocolState.ACTIVE

    def test_health_check(self):
        """Test health check."""
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        # Disconnected state
        assert not protocol.health_check()

        # Connected state
        protocol.set_state(ProtocolState.CONNECTED)
        assert protocol.health_check()

        # Active state
        protocol.set_state(ProtocolState.ACTIVE)
        assert protocol.health_check()

        # Error state
        protocol.set_state(ProtocolState.ERROR)
        assert not protocol.health_check()

    def test_protocol_info(self):
        """Test protocol information."""
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        info = protocol.get_protocol_info()
        assert isinstance(info, dict)
        assert "protocol_type" in info
        assert "state" in info
        assert "capabilities" in info
        assert "stats" in info
        assert "peers_count" in info
        assert "active_connections" in info

        assert info["protocol_type"] == ProtocolType.BITTORRENT.value
        assert info["state"] == ProtocolState.DISCONNECTED.value
        assert info["peers_count"] == 0
        assert info["active_connections"] == 0


class TestProtocolManager:
    """Tests for ProtocolManager class."""

    def test_protocol_manager_creation(self):
        """Test protocol manager creation."""
        manager = ProtocolManager()

        assert len(manager.protocols) == 0
        assert len(manager.active_protocols) == 0
        assert len(manager.protocol_stats) == 0

    def test_register_protocol(self):
        """Test protocol registration."""
        manager = ProtocolManager()
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        manager.register_protocol(protocol)

        assert len(manager.protocols) == 1
        assert ProtocolType.BITTORRENT in manager.protocols
        assert manager.protocols[ProtocolType.BITTORRENT] == protocol

    def test_unregister_protocol(self):
        """Test protocol unregistration."""
        manager = ProtocolManager()
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        manager.register_protocol(protocol)
        assert len(manager.protocols) == 1

        manager.unregister_protocol(ProtocolType.BITTORRENT)
        assert len(manager.protocols) == 0

    def test_get_protocol(self):
        """Test getting protocol."""
        manager = ProtocolManager()
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        manager.register_protocol(protocol)

        retrieved_protocol = manager.get_protocol(ProtocolType.BITTORRENT)
        assert retrieved_protocol == protocol

        # Test non-existent protocol
        non_existent = manager.get_protocol(ProtocolType.WEBTORRENT)
        assert non_existent is None

    def test_list_protocols(self):
        """Test listing protocols."""
        manager = ProtocolManager()

        # Empty list
        assert len(manager.list_protocols()) == 0

        # Add protocols
        protocol1 = TestProtocol(ProtocolType.BITTORRENT)
        protocol2 = TestProtocol(ProtocolType.WEBTORRENT)

        manager.register_protocol(protocol1)
        manager.register_protocol(protocol2)

        protocols = manager.list_protocols()
        assert len(protocols) == 2
        assert ProtocolType.BITTORRENT in protocols
        assert ProtocolType.WEBTORRENT in protocols

    def test_list_active_protocols(self):
        """Test listing active protocols."""
        manager = ProtocolManager()

        # Empty list
        assert len(manager.list_active_protocols()) == 0

        # Add protocols
        protocol1 = TestProtocol(ProtocolType.BITTORRENT)
        protocol2 = TestProtocol(ProtocolType.WEBTORRENT)

        manager.register_protocol(protocol1)
        manager.register_protocol(protocol2)

        # No active protocols yet
        assert len(manager.list_active_protocols()) == 0

    def test_get_protocol_statistics(self):
        """Test getting protocol statistics."""
        manager = ProtocolManager()
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        manager.register_protocol(protocol)

        stats = manager.get_protocol_statistics()
        assert isinstance(stats, dict)
        assert ProtocolType.BITTORRENT.value in stats

        protocol_stats = stats[ProtocolType.BITTORRENT.value]
        assert "protocol_type" in protocol_stats
        assert "state" in protocol_stats
        assert "capabilities" in protocol_stats
        assert "stats" in protocol_stats

    def test_get_combined_peers(self):
        """Test getting combined peers."""
        manager = ProtocolManager()
        protocol1 = TestProtocol(ProtocolType.BITTORRENT)
        protocol2 = TestProtocol(ProtocolType.WEBTORRENT)

        manager.register_protocol(protocol1)
        manager.register_protocol(protocol2)

        # Add peers to protocols
        peer1 = PeerInfo(ip="192.168.1.1", port=6881)
        peer2 = PeerInfo(ip="192.168.1.2", port=6882)

        protocol1.add_peer(peer1)
        protocol2.add_peer(peer2)

        # No active protocols yet
        combined_peers = manager.get_combined_peers()
        assert len(combined_peers) == 0

        # Activate protocols
        manager.active_protocols.add(ProtocolType.BITTORRENT)
        manager.active_protocols.add(ProtocolType.WEBTORRENT)

        combined_peers = manager.get_combined_peers()
        assert len(combined_peers) == 2
        assert "192.168.1.1" in combined_peers
        assert "192.168.1.2" in combined_peers

    def test_health_check_all(self):
        """Test health check for all protocols."""
        manager = ProtocolManager()
        protocol = TestProtocol(ProtocolType.BITTORRENT)

        manager.register_protocol(protocol)

        # Disconnected state
        health_results = manager.health_check_all_sync()
        assert ProtocolType.BITTORRENT in health_results
        assert not health_results[ProtocolType.BITTORRENT]

        # Connected state
        protocol.set_state(ProtocolState.CONNECTED)
        health_results = manager.health_check_all_sync()
        assert health_results[ProtocolType.BITTORRENT]
