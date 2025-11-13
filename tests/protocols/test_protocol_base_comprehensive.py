"""Comprehensive tests for protocol base classes to achieve 95%+ coverage.

Covers all missing lines in ccbt/protocols/base.py:
- Protocol state transitions with error handling
- Protocol manager lifecycle operations
- Protocol registration/discovery with error paths
- Connection lifecycle methods
- Message handling and peer connection management
- Error handling paths and circuit breaker logic
- Advanced protocol features (circuit breaker states)
- Event handlers
- Background tasks and concurrent operations
- Integration paths and health checks
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

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
from ccbt.utils.events import Event, EventType


class _TestProtocolImpl(Protocol):
    """Concrete implementation of Protocol for testing."""

    def __init__(self, protocol_type: ProtocolType, fail_start: bool = False, fail_stop: bool = False):
        super().__init__(protocol_type)
        self.fail_start = fail_start
        self.fail_stop = fail_stop

    async def start(self) -> None:
        """Start the protocol."""
        if self.fail_start:
            raise RuntimeError("Start failed")
        self.state = ProtocolState.CONNECTED

    async def stop(self) -> None:
        """Stop the protocol."""
        if self.fail_stop:
            raise RuntimeError("Stop failed")
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

    async def receive_message(self, peer_id: str) -> bytes | None:
        """Receive message from peer."""
        if peer_id in self.active_connections:
            self.stats.messages_received += 1
            return b"test_message"
        return None

    async def announce_torrent(self, torrent_info: TorrentInfo) -> list[PeerInfo]:
        """Announce torrent and get peers."""
        self.stats.announces += 1
        return [PeerInfo(ip="127.0.0.1", port=6881)]

    async def scrape_torrent(self, torrent_info: TorrentInfo) -> dict[str, int]:
        """Scrape torrent statistics."""
        return {"seeders": 10, "leechers": 5, "completed": 100}


pytestmark = [pytest.mark.unit, pytest.mark.protocols]


class TestProtocolStateTransitions:
    """Test protocol state transitions with error handling."""

    @pytest.mark.asyncio
    async def test_set_state_with_runtime_error(self):
        """Test _set_state when no event loop is running (line 232-234)."""
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        
        # Mock emit_event to raise RuntimeError
        with patch('ccbt.protocols.base.emit_event', side_effect=RuntimeError("No event loop")):
            # This should not raise, just skip event emission
            protocol.set_state(ProtocolState.CONNECTED)
            assert protocol.state == ProtocolState.CONNECTED

    def test_is_healthy_sync(self):
        """Test synchronous health check (line 242)."""
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        
        # Disconnected - not healthy
        assert not protocol.is_healthy()
        
        # Connected - healthy
        protocol.set_state(ProtocolState.CONNECTED)
        assert protocol.is_healthy()
        
        # Active - healthy
        protocol.set_state(ProtocolState.ACTIVE)
        assert protocol.is_healthy()

    @pytest.mark.asyncio
    async def test_async_context_manager_entry(self):
        """Test async context manager entry (line 246)."""
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        
        async with protocol:
            assert protocol.state == ProtocolState.CONNECTED

    @pytest.mark.asyncio
    async def test_async_context_manager_exit(self):
        """Test async context manager exit (line 251)."""
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        
        async with protocol:
            pass
        
        assert protocol.state == ProtocolState.DISCONNECTED


class TestProtocolManagerLifecycle:
    """Test protocol manager lifecycle operations."""

    @pytest.mark.asyncio
    async def test_start_protocol_success(self):
        """Test successful protocol start (lines 357-390)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        manager.register_protocol(protocol)

        with patch('ccbt.protocols.base.emit_event', new_callable=AsyncMock) as mock_emit:
            result = await manager.start_protocol(ProtocolType.BITTORRENT)
            
            assert result is True
            assert ProtocolType.BITTORRENT in manager.active_protocols
            assert protocol.state == ProtocolState.CONNECTED
            mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_protocol_not_found(self):
        """Test starting non-existent protocol (line 358)."""
        manager = ProtocolManager()
        
        result = await manager.start_protocol(ProtocolType.BITTORRENT)
        assert result is False

    @pytest.mark.asyncio
    async def test_start_protocol_with_exception(self):
        """Test protocol start with exception (lines 375-388)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT, fail_start=True)
        manager.register_protocol(protocol)

        with patch('ccbt.protocols.base.emit_event', new_callable=AsyncMock) as mock_emit:
            result = await manager.start_protocol(ProtocolType.BITTORRENT)
            
            assert result is False
            assert ProtocolType.BITTORRENT not in manager.active_protocols
            # Should emit protocol error event
            assert mock_emit.called

    @pytest.mark.asyncio
    async def test_stop_protocol_success(self):
        """Test successful protocol stop (lines 392-414)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        with patch('ccbt.protocols.base.emit_event', new_callable=AsyncMock) as mock_emit:
            result = await manager.stop_protocol(ProtocolType.BITTORRENT)
            
            assert result is True
            assert ProtocolType.BITTORRENT not in manager.active_protocols
            assert protocol.state == ProtocolState.DISCONNECTED
            mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_protocol_not_found(self):
        """Test stopping non-existent protocol (line 395)."""
        manager = ProtocolManager()
        
        result = await manager.stop_protocol(ProtocolType.BITTORRENT)
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_protocol_with_exception(self):
        """Test protocol stop with exception (lines 415-428)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT, fail_stop=True)
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        with patch('ccbt.protocols.base.emit_event', new_callable=AsyncMock) as mock_emit:
            result = await manager.stop_protocol(ProtocolType.BITTORRENT)
            
            assert result is False
            # Should emit protocol error event
            assert mock_emit.called

    @pytest.mark.asyncio
    async def test_start_all_protocols(self):
        """Test starting all protocols (lines 432-439)."""
        manager = ProtocolManager()
        protocol1 = _TestProtocolImpl(ProtocolType.BITTORRENT)
        protocol2 = _TestProtocolImpl(ProtocolType.WEBTORRENT)
        manager.register_protocol(protocol1)
        manager.register_protocol(protocol2)

        with patch('ccbt.protocols.base.emit_event', new_callable=AsyncMock):
            results = await manager.start_all_protocols()
            
            assert len(results) == 2
            assert results[ProtocolType.BITTORRENT] is True
            assert results[ProtocolType.WEBTORRENT] is True

    @pytest.mark.asyncio
    async def test_stop_all_protocols(self):
        """Test stopping all protocols (lines 441-448)."""
        manager = ProtocolManager()
        protocol1 = _TestProtocolImpl(ProtocolType.BITTORRENT)
        protocol2 = _TestProtocolImpl(ProtocolType.WEBTORRENT)
        manager.register_protocol(protocol1)
        manager.register_protocol(protocol2)
        manager.active_protocols.add(ProtocolType.BITTORRENT)
        manager.active_protocols.add(ProtocolType.WEBTORRENT)

        with patch('ccbt.protocols.base.emit_event', new_callable=AsyncMock):
            results = await manager.stop_all_protocols()
            
            assert len(results) == 2
            assert results[ProtocolType.BITTORRENT] is True
            assert results[ProtocolType.WEBTORRENT] is True
            assert len(manager.active_protocols) == 0


class TestProtocolConnectionManagement:
    """Test connection lifecycle and peer connection management."""

    @pytest.mark.asyncio
    async def test_connect_peers_concurrently_success(self):
        """Test concurrent peer connections (lines 471-495)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        peers = [
            PeerInfo(ip="192.168.1.1", port=6881),
            PeerInfo(ip="192.168.1.2", port=6882),
        ]

        results = await manager.connect_peers_batch(
            peers, preferred_protocol=ProtocolType.BITTORRENT
        )

        assert ProtocolType.BITTORRENT in results
        assert len(results[ProtocolType.BITTORRENT]) == 2

    @pytest.mark.asyncio
    async def test_connect_peers_concurrently_with_exception(self):
        """Test concurrent connections with protocol exception (lines 490-493)."""
        manager = ProtocolManager()
        
        # Mock protocol to raise exception
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        async def failing_connect(*args, **kwargs):
            raise Exception("Connection failed")
        protocol.connect_peer = failing_connect
        
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        peers = [PeerInfo(ip="192.168.1.1", port=6881)]

        results = await manager.connect_peers_batch(
            peers, preferred_protocol=ProtocolType.BITTORRENT
        )

        assert ProtocolType.BITTORRENT in results
        assert len(results[ProtocolType.BITTORRENT]) == 0

    @pytest.mark.asyncio
    async def test_connect_peers_for_protocol_unavailable(self):
        """Test connecting peers when protocol unavailable (line 502)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        manager.register_protocol(protocol)
        # Don't add to active_protocols, but make it unavailable via circuit breaker
        manager.circuit_breaker_state[ProtocolType.BITTORRENT] = {
            "state": "open",
            "failure_count": 10,
            "last_failure": time.time() - 1,  # Very recent failure
        }

        peers = [PeerInfo(ip="192.168.1.1", port=6881)]

        result = await manager._connect_peers_for_protocol(
            ProtocolType.BITTORRENT, peers
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_connect_peers_for_protocol_with_exceptions(self):
        """Test connecting peers with exceptions in results (lines 511-518)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        
        # Make connect_peer return exceptions for some peers
        async def mixed_connect(peer_info):
            if peer_info.port == 6881:
                return True
            raise Exception("Connection failed")
        
        protocol.connect_peer = mixed_connect
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        peers = [
            PeerInfo(ip="192.168.1.1", port=6881),
            PeerInfo(ip="192.168.1.2", port=6882),
        ]

        result = await manager._connect_peers_for_protocol(
            ProtocolType.BITTORRENT, peers
        )

        assert len(result) == 1

    def test_group_peers_by_protocol(self):
        """Test grouping peers by protocol (lines 520-536)."""
        manager = ProtocolManager()
        protocol1 = _TestProtocolImpl(ProtocolType.BITTORRENT)
        protocol2 = _TestProtocolImpl(ProtocolType.WEBTORRENT)
        manager.register_protocol(protocol1)
        manager.register_protocol(protocol2)
        manager.active_protocols.add(ProtocolType.BITTORRENT)
        manager.active_protocols.add(ProtocolType.WEBTORRENT)

        peers = [
            PeerInfo(ip="192.168.1.1", port=6881),
            PeerInfo(ip="192.168.1.2", port=6882),
        ]

        groups = manager._group_peers_by_protocol(
            peers, preferred_protocol=ProtocolType.BITTORRENT
        )

        assert len(groups) > 0
        assert ProtocolType.BITTORRENT in groups or ProtocolType.WEBTORRENT in groups

    def test_select_best_protocol_for_peer_preferred(self):
        """Test selecting preferred protocol (lines 538-561)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        peer = PeerInfo(ip="192.168.1.1", port=6881)

        best = manager._select_best_protocol_for_peer(
            peer, preferred_protocol=ProtocolType.BITTORRENT
        )

        assert best == ProtocolType.BITTORRENT

    def test_select_best_protocol_for_peer_no_preferred(self):
        """Test selecting protocol without preference (lines 548-561)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        peer = PeerInfo(ip="192.168.1.1", port=6881)

        best = manager._select_best_protocol_for_peer(peer, preferred_protocol=None)

        assert best is not None
        assert best in manager.active_protocols

    def test_select_best_protocol_for_peer_no_available(self):
        """Test selecting protocol when none available (line 554)."""
        manager = ProtocolManager()

        peer = PeerInfo(ip="192.168.1.1", port=6881)

        best = manager._select_best_protocol_for_peer(peer, preferred_protocol=None)

        assert best is None


class TestCircuitBreakerLogic:
    """Test circuit breaker logic and protocol availability."""

    def test_is_protocol_available_not_in_state(self):
        """Test protocol availability when not in circuit breaker state (line 565)."""
        manager = ProtocolManager()

        assert manager._is_protocol_available(ProtocolType.BITTORRENT) is True

    def test_is_protocol_available_closed(self):
        """Test protocol availability with closed circuit (line 570)."""
        manager = ProtocolManager()
        manager.circuit_breaker_state[ProtocolType.BITTORRENT] = {
            "state": "closed",
            "failure_count": 0,
            "last_failure": 0.0,
        }

        assert manager._is_protocol_available(ProtocolType.BITTORRENT) is True

    def test_is_protocol_available_open_recovery(self):
        """Test protocol availability with open circuit after recovery timeout (lines 572-577)."""
        manager = ProtocolManager()
        manager.recovery_timeout = 0.1
        manager.circuit_breaker_state[ProtocolType.BITTORRENT] = {
            "state": "open",
            "failure_count": 10,
            "last_failure": time.time() - 0.2,  # Past recovery timeout
        }

        assert manager._is_protocol_available(ProtocolType.BITTORRENT) is True
        # Should transition to half-open
        assert manager.circuit_breaker_state[ProtocolType.BITTORRENT]["state"] == "half-open"

    def test_is_protocol_available_open_not_recovered(self):
        """Test protocol availability with open circuit before recovery (line 578)."""
        manager = ProtocolManager()
        manager.recovery_timeout = 10.0
        manager.circuit_breaker_state[ProtocolType.BITTORRENT] = {
            "state": "open",
            "failure_count": 10,
            "last_failure": time.time(),  # Recent failure
        }

        assert manager._is_protocol_available(ProtocolType.BITTORRENT) is False

    def test_is_protocol_available_half_open(self):
        """Test protocol availability with half-open circuit (line 579)."""
        manager = ProtocolManager()
        manager.circuit_breaker_state[ProtocolType.BITTORRENT] = {
            "state": "half-open",
            "failure_count": 5,
            "last_failure": 0.0,
        }

        assert manager._is_protocol_available(ProtocolType.BITTORRENT) is True

    def test_record_protocol_success(self):
        """Test recording protocol success (lines 584-599)."""
        manager = ProtocolManager()

        manager._record_protocol_success(ProtocolType.BITTORRENT)

        state = manager.circuit_breaker_state[ProtocolType.BITTORRENT]
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        assert ProtocolType.BITTORRENT in manager.protocol_performance

    def test_record_protocol_success_updates_performance(self):
        """Test that success updates performance score (lines 597-599)."""
        manager = ProtocolManager()
        manager.protocol_performance[ProtocolType.BITTORRENT] = 1.0

        manager._record_protocol_success(ProtocolType.BITTORRENT)

        assert manager.protocol_performance[ProtocolType.BITTORRENT] == 1.1

    def test_record_protocol_failure(self):
        """Test recording protocol failure (lines 601-620)."""
        manager = ProtocolManager()

        manager._record_protocol_failure(ProtocolType.BITTORRENT)

        state = manager.circuit_breaker_state[ProtocolType.BITTORRENT]
        assert state["failure_count"] == 1
        assert state["last_failure"] > 0
        assert ProtocolType.BITTORRENT in manager.protocol_performance

    def test_record_protocol_failure_updates_performance(self):
        """Test that failure updates performance score (lines 614-616)."""
        manager = ProtocolManager()
        manager.protocol_performance[ProtocolType.BITTORRENT] = 1.0

        manager._record_protocol_failure(ProtocolType.BITTORRENT)

        assert manager.protocol_performance[ProtocolType.BITTORRENT] == 0.9

    def test_record_protocol_failure_opens_circuit(self):
        """Test that repeated failures open circuit breaker (lines 618-620)."""
        manager = ProtocolManager()
        manager.failure_threshold = 5

        # Record enough failures to open circuit
        for _ in range(5):
            manager._record_protocol_failure(ProtocolType.BITTORRENT)

        state = manager.circuit_breaker_state[ProtocolType.BITTORRENT]
        assert state["state"] == "open"


class TestConcurrentOperations:
    """Test concurrent operations and background tasks."""

    @pytest.mark.asyncio
    async def test_announce_torrents_concurrently(self):
        """Test concurrent torrent announcements (lines 633-673)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        torrents = [
            TorrentInfo(
                name="test1",
                info_hash=b"\x01" * 20,
                announce="http://tracker.example.com/announce",
                files=[],
                total_length=1024,
                piece_length=16384,
                pieces=[b"\x00" * 20],
                num_pieces=1,
            ),
            TorrentInfo(
                name="test2",
                info_hash=b"\x02" * 20,
                announce="http://tracker.example.com/announce",
                files=[],
                total_length=2048,
                piece_length=16384,
                pieces=[b"\x00" * 20],
                num_pieces=1,
            ),
        ]

        results = await manager.announce_torrent_batch(
            torrents
        )

        assert ProtocolType.BITTORRENT in results
        assert "test1" in results[ProtocolType.BITTORRENT]
        assert "test2" in results[ProtocolType.BITTORRENT]

    @pytest.mark.asyncio
    async def test_announce_torrents_concurrently_with_exceptions(self):
        """Test concurrent announcements with exceptions (lines 649-671)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        
        # Make announce_torrent raise exception
        async def failing_announce(*args, **kwargs):
            raise Exception("Announce failed")
        protocol.announce_torrent = failing_announce
        
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        torrents = [
            TorrentInfo(
                name="test1",
                info_hash=b"\x01" * 20,
                announce="http://tracker.example.com/announce",
                files=[],
                total_length=1024,
                piece_length=16384,
                pieces=[b"\x00" * 20],
                num_pieces=1,
            ),
        ]

        results = await manager.announce_torrent_batch(
            torrents
        )

        assert ProtocolType.BITTORRENT in results
        assert len(results[ProtocolType.BITTORRENT]["test1"]) == 0

    def test_get_circuit_breaker_status(self):
        """Test getting circuit breaker status (lines 675-687)."""
        manager = ProtocolManager()
        manager.circuit_breaker_state[ProtocolType.BITTORRENT] = {
            "state": "closed",
            "failure_count": 2,
            "last_failure": 100.0,
        }
        manager.protocol_performance[ProtocolType.BITTORRENT] = 1.5

        status = manager.get_circuit_breaker_status()

        assert ProtocolType.BITTORRENT.value in status
        assert status[ProtocolType.BITTORRENT.value]["state"] == "closed"
        assert status[ProtocolType.BITTORRENT.value]["failure_count"] == 2
        assert status[ProtocolType.BITTORRENT.value]["performance_score"] == 1.5


class TestIntegrationPaths:
    """Test integration paths and health checks."""

    @pytest.mark.asyncio
    async def test_announce_torrent_all_success(self):
        """Test announcing torrent on all protocols (lines 700-712)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        torrent = TorrentInfo(
            name="test",
            info_hash=b"\x01" * 20,
            announce="http://tracker.example.com/announce",
            files=[],
            total_length=1024,
            piece_length=16384,
            pieces=[b"\x00" * 20],
            num_pieces=1,
        )

        results = await manager.announce_torrent_all(torrent)

        assert ProtocolType.BITTORRENT in results
        assert len(results[ProtocolType.BITTORRENT]) > 0

    @pytest.mark.asyncio
    async def test_announce_torrent_all_with_exception(self):
        """Test announcing torrent with exception (lines 713-725)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        
        # Make announce_torrent raise exception
        async def failing_announce(*args, **kwargs):
            raise Exception("Announce failed")
        protocol.announce_torrent = failing_announce
        
        manager.register_protocol(protocol)
        manager.active_protocols.add(ProtocolType.BITTORRENT)

        torrent = TorrentInfo(
            name="test",
            info_hash=b"\x01" * 20,
            announce="http://tracker.example.com/announce",
            files=[],
            total_length=1024,
            piece_length=16384,
            pieces=[b"\x00" * 20],
            num_pieces=1,
        )

        with patch('ccbt.protocols.base.emit_event', new_callable=AsyncMock) as mock_emit:
            results = await manager.announce_torrent_all(torrent)

            assert ProtocolType.BITTORRENT in results
            assert len(results[ProtocolType.BITTORRENT]) == 0
            mock_emit.assert_called()

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """Test health check on all protocols (lines 729-738)."""
        manager = ProtocolManager()
        protocol1 = _TestProtocolImpl(ProtocolType.BITTORRENT)
        protocol2 = _TestProtocolImpl(ProtocolType.WEBTORRENT)
        manager.register_protocol(protocol1)
        manager.register_protocol(protocol2)
        protocol1.set_state(ProtocolState.CONNECTED)
        protocol2.set_state(ProtocolState.DISCONNECTED)

        results = await manager.health_check_all()

        assert ProtocolType.BITTORRENT in results
        assert ProtocolType.WEBTORRENT in results
        assert results[ProtocolType.BITTORRENT] is True
        assert results[ProtocolType.WEBTORRENT] is False

    @pytest.mark.asyncio
    async def test_health_check_all_with_exception(self):
        """Test health check with exception (lines 736-737)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        
        # Make health_check raise exception
        async def failing_health_check():
            raise Exception("Health check failed")
        protocol.health_check = failing_health_check
        
        manager.register_protocol(protocol)

        results = await manager.health_check_all()

        assert ProtocolType.BITTORRENT in results
        assert results[ProtocolType.BITTORRENT] is False

    def test_health_check_all_sync(self):
        """Test synchronous health check on all protocols (lines 741-750)."""
        manager = ProtocolManager()
        protocol1 = _TestProtocolImpl(ProtocolType.BITTORRENT)
        protocol2 = _TestProtocolImpl(ProtocolType.WEBTORRENT)
        manager.register_protocol(protocol1)
        manager.register_protocol(protocol2)
        protocol1.set_state(ProtocolState.CONNECTED)
        protocol2.set_state(ProtocolState.DISCONNECTED)

        results = manager.health_check_all_sync()

        assert ProtocolType.BITTORRENT in results
        assert ProtocolType.WEBTORRENT in results
        assert results[ProtocolType.BITTORRENT] is True
        assert results[ProtocolType.WEBTORRENT] is False

    def test_health_check_all_sync_with_exception(self):
        """Test synchronous health check with exception (lines 748-749)."""
        manager = ProtocolManager()
        protocol = _TestProtocolImpl(ProtocolType.BITTORRENT)
        
        # Make is_healthy raise exception
        def failing_health_check():
            raise Exception("Health check failed")
        protocol.is_healthy = failing_health_check
        
        manager.register_protocol(protocol)

        results = manager.health_check_all_sync()

        assert ProtocolType.BITTORRENT in results
        assert results[ProtocolType.BITTORRENT] is False

    def test_get_protocol_manager(self):
        """Test getting global protocol manager (lines 758-763)."""
        from ccbt.protocols.base import get_protocol_manager

        manager1 = get_protocol_manager()
        manager2 = get_protocol_manager()

        assert manager1 is manager2
        assert isinstance(manager1, ProtocolManager)

