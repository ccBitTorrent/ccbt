"""PEX extension coverage boost tests."""

import pytest
import socket
import struct
from unittest.mock import AsyncMock, patch

from ccbt.extensions.pex import PEXPeer, PeerExchange, PEXMessageType
from ccbt.models import PeerInfo
from ccbt.utils.events import Event, EventType


pytestmark = [pytest.mark.unit, pytest.mark.extensions]


class TestPEXIPv6Support:
    """Test IPv6 encoding/decoding and edge cases."""

    def test_encode_compact_peer_ipv6_success(self):
        """Test IPv6 peer encoding."""
        pex = PeerExchange()
        peer = PEXPeer(ip="::1", port=6881)
        data = pex.encode_compact_peer(peer)
        assert len(data) == 18  # 16 bytes IP + 2 bytes port
        assert data[16:18] == struct.pack("!H", 6881)

    def test_encode_compact_peer_ipv6_failure_fallback(self):
        """Test IPv6 encoding failure falls back to error."""
        pex = PeerExchange()
        peer = PEXPeer(ip="invalid-ipv6", port=6881)
        with pytest.raises(ValueError, match="Invalid IP address"):
            pex.encode_compact_peer(peer)

    def test_decode_compact_peer_ipv6_success(self):
        """Test IPv6 peer decoding."""
        pex = PeerExchange()
        ipv6_bytes = socket.inet_pton(socket.AF_INET6, "::1")
        data = struct.pack("!16sH", ipv6_bytes, 6881)
        peer = pex.decode_compact_peer(data, is_ipv6=True)
        assert peer.ip == "::1"
        assert peer.port == 6881

    def test_decode_compact_peer_ipv6_short_data(self):
        """Test IPv6 decoding with insufficient data."""
        pex = PeerExchange()
        with pytest.raises(ValueError, match="Invalid IPv6 compact peer format"):
            pex.decode_compact_peer(b"short", is_ipv6=True)

    def test_encode_peers_list_ipv6(self):
        """Test encoding list of IPv6 peers."""
        pex = PeerExchange()
        peers = [
            PEXPeer(ip="::1", port=6881),
            PEXPeer(ip="2001:db8::1", port=6882),
        ]
        data = pex.encode_peers_list(peers, _is_ipv6=True)
        assert len(data) == 36  # 2 peers * 18 bytes each

    def test_decode_peers_list_ipv6_with_invalid_peer(self):
        """Test decoding IPv6 peers list with invalid peer data."""
        pex = PeerExchange()
        ipv6_bytes = socket.inet_pton(socket.AF_INET6, "::1")
        valid_peer = struct.pack("!16sH", ipv6_bytes, 6881)
        invalid_data = valid_peer + b"invalid"
        peers = pex.decode_peers_list(invalid_data, is_ipv6=True)
        assert len(peers) == 1  # Only valid peer should be decoded

    def test_decode_peers_list_ipv6_partial_peer(self):
        """Test decoding IPv6 peers list with partial peer at end."""
        pex = PeerExchange()
        ipv6_bytes = socket.inet_pton(socket.AF_INET6, "::1")
        valid_peer = struct.pack("!16sH", ipv6_bytes, 6881)
        partial_data = valid_peer + b"partial"
        peers = pex.decode_peers_list(partial_data, is_ipv6=True)
        assert len(peers) == 1  # Only complete peer should be decoded


class TestPEXMessageParsing:
    """Test PEX message parsing edge cases and error handling."""

    def test_decode_pex_message_short_data(self):
        """Test decoding PEX message with insufficient data."""
        pex = PeerExchange()
        with pytest.raises(ValueError, match="Invalid PEX message"):
            pex.decode_pex_message(b"sh")

    def test_decode_pex_message_incomplete_data(self):
        """Test decoding PEX message with incomplete peer data."""
        pex = PeerExchange()
        # Length says 10 bytes but only 5 provided
        data = struct.pack("!IB", 10, PEXMessageType.ADDED) + b"incomp"
        with pytest.raises(ValueError, match="Incomplete PEX message"):
            pex.decode_pex_message(data)

    def test_decode_pex_message_valid_with_peers(self):
        """Test decoding valid PEX message with peer data."""
        pex = PeerExchange()
        peer_data = struct.pack("!4sH", socket.inet_aton("127.0.0.1"), 6881)
        data = struct.pack("!IB", len(peer_data) + 1, PEXMessageType.ADDED) + peer_data
        message_id, peers = pex.decode_pex_message(data)
        assert message_id == PEXMessageType.ADDED
        assert len(peers) == 1
        assert peers[0].ip == "127.0.0.1"
        assert peers[0].port == 6881

    def test_encode_added_peers_ipv6(self):
        """Test encoding added peers message with IPv6."""
        pex = PeerExchange()
        peers = [PEXPeer(ip="::1", port=6881)]
        data = pex.encode_added_peers(peers, is_ipv6=True)
        message_id, decoded_peers = pex.decode_pex_message(data, is_ipv6=True)
        assert message_id == PEXMessageType.ADDED
        assert len(decoded_peers) == 1

    def test_encode_dropped_peers_ipv6(self):
        """Test encoding dropped peers message with IPv6."""
        pex = PeerExchange()
        peers = [PEXPeer(ip="::1", port=6881)]
        data = pex.encode_dropped_peers(peers, is_ipv6=True)
        message_id, decoded_peers = pex.decode_pex_message(data, is_ipv6=True)
        assert message_id == PEXMessageType.DROPPED
        assert len(decoded_peers) == 1


class TestPEXFlagOperations:
    """Test peer flag operations and filtering."""

    def test_peer_flags_set_and_get(self):
        """Test setting and getting peer flags."""
        pex = PeerExchange()
        pex.set_peer_flags("127.0.0.1", 6881, 0x03)  # Both seed and connectable
        flags = pex.get_peer_flags("127.0.0.1", 6881)
        assert flags == 0x03

    def test_peer_flags_default_zero(self):
        """Test getting flags for unknown peer returns 0."""
        pex = PeerExchange()
        flags = pex.get_peer_flags("127.0.0.1", 9999)
        assert flags == 0

    def test_is_peer_seed_true(self):
        """Test checking if peer is seed (flag bit 0 set)."""
        pex = PeerExchange()
        pex.set_peer_flags("127.0.0.1", 6881, 0x01)
        assert pex.is_peer_seed("127.0.0.1", 6881) is True

    def test_is_peer_seed_false(self):
        """Test checking if peer is not seed (flag bit 0 not set)."""
        pex = PeerExchange()
        pex.set_peer_flags("127.0.0.1", 6881, 0x02)  # Only connectable
        assert pex.is_peer_seed("127.0.0.1", 6881) is False

    def test_is_peer_connectable_true(self):
        """Test checking if peer is connectable (flag bit 1 set)."""
        pex = PeerExchange()
        pex.set_peer_flags("127.0.0.1", 6881, 0x02)
        assert pex.is_peer_connectable("127.0.0.1", 6881) is True

    def test_is_peer_connectable_false(self):
        """Test checking if peer is not connectable (flag bit 1 not set)."""
        pex = PeerExchange()
        pex.set_peer_flags("127.0.0.1", 6881, 0x01)  # Only seed
        assert pex.is_peer_connectable("127.0.0.1", 6881) is False

    def test_create_peer_from_info_with_flags(self):
        """Test creating PEX peer from PeerInfo with flags."""
        pex = PeerExchange()
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer = pex.create_peer_from_info(peer_info, is_seed=True, is_connectable=True)
        assert peer.flags == 0x03  # Both bits set

    def test_create_peer_from_info_seed_only(self):
        """Test creating PEX peer with only seed flag."""
        pex = PeerExchange()
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer = pex.create_peer_from_info(peer_info, is_seed=True, is_connectable=False)
        assert peer.flags == 0x01  # Only seed bit set

    def test_create_peer_from_info_connectable_only(self):
        """Test creating PEX peer with only connectable flag."""
        pex = PeerExchange()
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer = pex.create_peer_from_info(peer_info, is_seed=False, is_connectable=True)
        assert peer.flags == 0x02  # Only connectable bit set

    def test_create_peer_from_info_no_flags(self):
        """Test creating PEX peer with no flags."""
        pex = PeerExchange()
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        peer = pex.create_peer_from_info(peer_info, is_seed=False, is_connectable=False)
        assert peer.flags == 0x00  # No flags set


class TestPEXFilteringAndMerging:
    """Test peer filtering and merging operations."""

    def test_filter_peers_by_flags_require_seed(self):
        """Test filtering peers requiring seed flag."""
        pex = PeerExchange()
        peers = [
            PEXPeer(ip="127.0.0.1", port=6881, flags=0x01),  # Seed only
            PEXPeer(ip="127.0.0.2", port=6882, flags=0x02),  # Connectable only
            PEXPeer(ip="127.0.0.3", port=6883, flags=0x03),  # Both
        ]
        pex.set_peer_flags("127.0.0.1", 6881, 0x01)
        pex.set_peer_flags("127.0.0.2", 6882, 0x02)
        pex.set_peer_flags("127.0.0.3", 6883, 0x03)
        
        filtered = pex.filter_peers_by_flags(peers, require_seed=True)
        assert len(filtered) == 2  # Only seeds
        assert filtered[0].ip == "127.0.0.1"
        assert filtered[1].ip == "127.0.0.3"

    def test_filter_peers_by_flags_require_connectable(self):
        """Test filtering peers requiring connectable flag."""
        pex = PeerExchange()
        peers = [
            PEXPeer(ip="127.0.0.1", port=6881, flags=0x01),  # Seed only
            PEXPeer(ip="127.0.0.2", port=6882, flags=0x02),  # Connectable only
            PEXPeer(ip="127.0.0.3", port=6883, flags=0x03),  # Both
        ]
        pex.set_peer_flags("127.0.0.1", 6881, 0x01)
        pex.set_peer_flags("127.0.0.2", 6882, 0x02)
        pex.set_peer_flags("127.0.0.3", 6883, 0x03)
        
        filtered = pex.filter_peers_by_flags(peers, require_connectable=True)
        assert len(filtered) == 2  # Only connectable
        assert filtered[0].ip == "127.0.0.2"
        assert filtered[1].ip == "127.0.0.3"

    def test_filter_peers_by_flags_both_requirements(self):
        """Test filtering peers requiring both seed and connectable flags."""
        pex = PeerExchange()
        peers = [
            PEXPeer(ip="127.0.0.1", port=6881, flags=0x01),  # Seed only
            PEXPeer(ip="127.0.0.2", port=6882, flags=0x02),  # Connectable only
            PEXPeer(ip="127.0.0.3", port=6883, flags=0x03),  # Both
        ]
        pex.set_peer_flags("127.0.0.1", 6881, 0x01)
        pex.set_peer_flags("127.0.0.2", 6882, 0x02)
        pex.set_peer_flags("127.0.0.3", 6883, 0x03)
        
        filtered = pex.filter_peers_by_flags(peers, require_seed=True, require_connectable=True)
        assert len(filtered) == 1  # Only both
        assert filtered[0].ip == "127.0.0.3"

    def test_filter_peers_by_flags_no_requirements(self):
        """Test filtering peers with no requirements returns all."""
        pex = PeerExchange()
        peers = [
            PEXPeer(ip="127.0.0.1", port=6881, flags=0x01),
            PEXPeer(ip="127.0.0.2", port=6882, flags=0x02),
        ]
        filtered = pex.filter_peers_by_flags(peers)
        assert len(filtered) == 2

    def test_merge_peer_lists_no_duplicates(self):
        """Test merging peer lists with no duplicates."""
        pex = PeerExchange()
        peers1 = [PEXPeer(ip="127.0.0.1", port=6881)]
        peers2 = [PEXPeer(ip="127.0.0.2", port=6882)]
        merged = pex.merge_peer_lists(peers1, peers2)
        assert len(merged) == 2

    def test_merge_peer_lists_with_duplicates(self):
        """Test merging peer lists with duplicates."""
        pex = PeerExchange()
        peers1 = [PEXPeer(ip="127.0.0.1", port=6881)]
        peers2 = [PEXPeer(ip="127.0.0.1", port=6881)]  # Duplicate
        merged = pex.merge_peer_lists(peers1, peers2)
        assert len(merged) == 1  # Duplicate removed

    def test_merge_peer_lists_empty_lists(self):
        """Test merging empty peer lists."""
        pex = PeerExchange()
        merged = pex.merge_peer_lists([], [])
        assert len(merged) == 0

    def test_merge_peer_lists_one_empty(self):
        """Test merging one empty and one non-empty list."""
        pex = PeerExchange()
        peers1 = [PEXPeer(ip="127.0.0.1", port=6881)]
        merged = pex.merge_peer_lists(peers1, [])
        assert len(merged) == 1
        assert merged[0].ip == "127.0.0.1"


class TestPEXStatistics:
    """Test PEX statistics and edge cases."""

    def test_get_peer_statistics_empty(self):
        """Test getting statistics with no peers."""
        pex = PeerExchange()
        stats = pex.get_peer_statistics()
        assert stats["added_peers_count"] == 0
        assert stats["dropped_peers_count"] == 0
        assert stats["total_peers_with_flags"] == 0
        assert stats["seeds_count"] == 0
        assert stats["connectable_peers_count"] == 0

    def test_get_peer_statistics_with_peers(self):
        """Test getting statistics with various peer types."""
        pex = PeerExchange()
        # Add some peers
        pex.add_peer(PEXPeer(ip="127.0.0.1", port=6881))
        pex.add_peer(PEXPeer(ip="127.0.0.2", port=6882))
        pex.drop_peer(PEXPeer(ip="127.0.0.3", port=6883))
        
        # Set flags
        pex.set_peer_flags("127.0.0.1", 6881, 0x01)  # Seed only
        pex.set_peer_flags("127.0.0.2", 6882, 0x02)  # Connectable only
        pex.set_peer_flags("127.0.0.4", 6884, 0x03)  # Both
        
        stats = pex.get_peer_statistics()
        assert stats["added_peers_count"] == 2
        assert stats["dropped_peers_count"] == 1
        assert stats["total_peers_with_flags"] == 3
        assert stats["seeds_count"] == 2  # 127.0.0.1 and 127.0.0.4
        assert stats["connectable_peers_count"] == 2  # 127.0.0.2 and 127.0.0.4


class TestPEXEventHandling:
    """Test PEX event handling and edge cases."""

    @pytest.mark.asyncio
    async def test_handle_added_peers_emits_events(self):
        """Test handling added peers emits events."""
        pex = PeerExchange()
        peers = [PEXPeer(ip="127.0.0.1", port=6881, flags=0x01)]
        
        with patch("ccbt.extensions.pex.emit_event", new_callable=AsyncMock) as mock_emit:
            await pex.handle_added_peers("peer123", peers)
            
            # Check peer was added
            assert len(pex.get_added_peers()) == 1
            
            # Check event was emitted
            mock_emit.assert_called_once()
            call_args = mock_emit.call_args[0][0]
            assert call_args.event_type == EventType.PEER_DISCOVERED.value
            assert call_args.data["peer_id"] == "peer123"
            assert call_args.data["new_peer"]["ip"] == "127.0.0.1"
            assert call_args.data["source"] == "pex"

    @pytest.mark.asyncio
    async def test_handle_dropped_peers_emits_events(self):
        """Test handling dropped peers emits events."""
        pex = PeerExchange()
        peers = [PEXPeer(ip="127.0.0.1", port=6881, flags=0x01)]
        
        with patch("ccbt.extensions.pex.emit_event", new_callable=AsyncMock) as mock_emit:
            await pex.handle_dropped_peers("peer123", peers)
            
            # Check peer was dropped
            assert len(pex.get_dropped_peers()) == 1
            
            # Check event was emitted
            mock_emit.assert_called_once()
            call_args = mock_emit.call_args[0][0]
            assert call_args.event_type == EventType.PEER_DROPPED.value
            assert call_args.data["peer_id"] == "peer123"
            assert call_args.data["dropped_peer"]["ip"] == "127.0.0.1"
            assert call_args.data["source"] == "pex"

    def test_clear_peers_sets(self):
        """Test clearing added and dropped peer sets."""
        pex = PeerExchange()
        pex.add_peer(PEXPeer(ip="127.0.0.1", port=6881))
        pex.drop_peer(PEXPeer(ip="127.0.0.2", port=6882))
        
        assert len(pex.get_added_peers()) == 1
        assert len(pex.get_dropped_peers()) == 1
        
        pex.clear_added_peers()
        pex.clear_dropped_peers()
        
        assert len(pex.get_added_peers()) == 0
        assert len(pex.get_dropped_peers()) == 0


class TestPEXEdgeCases:
    """Test PEX edge cases and error conditions."""

    def test_encode_peers_list_empty(self):
        """Test encoding empty peers list."""
        pex = PeerExchange()
        data = pex.encode_peers_list([])
        assert data == b""

    def test_decode_peers_list_empty(self):
        """Test decoding empty peers data."""
        pex = PeerExchange()
        peers = pex.decode_peers_list(b"")
        assert len(peers) == 0

    def test_peer_info_conversion(self):
        """Test PEXPeer to/from PeerInfo conversion."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        pex_peer = PEXPeer.from_peer_info(peer_info, flags=0x03)
        assert pex_peer.ip == "127.0.0.1"
        assert pex_peer.port == 6881
        assert pex_peer.flags == 0x03
        
        converted_back = pex_peer.to_peer_info()
        assert converted_back.ip == "127.0.0.1"
        assert converted_back.port == 6881

    def test_peer_info_conversion_default_flags(self):
        """Test PEXPeer from PeerInfo with default flags."""
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)
        pex_peer = PEXPeer.from_peer_info(peer_info)
        assert pex_peer.flags == 0
