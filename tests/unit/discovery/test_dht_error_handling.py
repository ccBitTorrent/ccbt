"""Tests for DHT error handling and edge cases.

Covers missing lines:
- get_peers ValueError handling (lines 541-548)
- get_peers IPv6 node parsing and merging (lines 596-607)
- announce_peer error handling (lines 708-715)
- _send_query timeout handling (lines 781-783)
- handle_response exception handling (lines 816-818)
- _refresh_loop exception handling (lines 825-828)
- put_data error handling (lines 988-1017)
- get_data error handling (lines 1053-1134)
- Various other edge cases
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.discovery.dht import AsyncDHTClient, DHTNode

pytestmark = [pytest.mark.unit]


class TestDHTGetPeersErrorHandling:
    """Tests for get_peers error handling (lines 541-548, 596-607, 617-624)."""

    @pytest.mark.asyncio
    async def test_get_peers_value_error_fallback(self):
        """Test get_peers ValueError handling with fallback (lines 541-548)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.routing_table = MagicMock()
        client.routing_table.get_closest_nodes = MagicMock(
            return_value=[
                DHTNode(
                    b"\x01" * 20,
                    "192.168.1.1",
                    6881,
                    ipv6="2001:db8::1",
                    port6=6881,
                )
            ]
        )
        client.routing_table.nodes = {}
        client.routing_table.add_node = MagicMock()
        client.routing_table.mark_node_good = MagicMock()
        client.routing_table.mark_node_bad = MagicMock()
        client.tokens = {}
        client.peer_callbacks = []

        # Mock select_best_address to raise ValueError
        with patch("ccbt.discovery.dht_ipv6.select_best_address") as mock_select:
            mock_select.side_effect = ValueError("Invalid address")
            
            # Mock _send_query to return valid response
            async def mock_send_query(addr, query, params):
                return {
                    b"y": b"r",
                    b"r": {b"id": b"\x02" * 20, b"values": []},
                }

            client._send_query = mock_send_query

            # Should handle ValueError and fallback to get_primary_address
            result = await client.get_peers(b"\x11" * 20)
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_peers_ipv6_node_parsing_error(self):
        """Test get_peers IPv6 node parsing error handling (lines 596-607)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.routing_table = MagicMock()
        client.routing_table.get_closest_nodes = MagicMock(
            return_value=[DHTNode(b"\x01" * 20, "192.168.1.1", 6881)]
        )
        client.routing_table.nodes = {}
        client.routing_table.add_node = MagicMock()
        client.routing_table.mark_node_good = MagicMock()
        client.routing_table.mark_node_bad = MagicMock()
        client.tokens = {}
        client.peer_callbacks = []

        # Mock parse_ipv6_nodes to raise exception
        with patch("ccbt.discovery.dht_ipv6.parse_ipv6_nodes") as mock_parse:
            mock_parse.side_effect = ValueError("Invalid IPv6 data")

            async def mock_send_query(addr, query, params):
                return {
                    b"y": b"r",
                    b"r": {
                        b"id": b"\x02" * 20,
                        b"nodes6": b"invalid_data",
                    },
                }

            client._send_query = mock_send_query

            # Should handle exception gracefully
            result = await client.get_peers(b"\x11" * 20)
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_peers_exception_handling(self):
        """Test get_peers general exception handling (lines 617-624)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.routing_table = MagicMock()
        client.routing_table.get_closest_nodes = MagicMock(
            return_value=[DHTNode(b"\x01" * 20, "192.168.1.1", 6881)]
        )
        client.routing_table.mark_node_bad = MagicMock()
        client.tokens = {}
        client.peer_callbacks = []

        # Mock _send_query to raise exception
        async def mock_send_query(addr, query, params):
            raise Exception("Network error")

        client._send_query = mock_send_query

        # Should handle exception and mark node as bad
        result = await client.get_peers(b"\x11" * 20)
        assert isinstance(result, list)
        client.routing_table.mark_node_bad.assert_called()


class TestDHTAnnouncePeerErrorHandling:
    """Tests for announce_peer error handling (lines 708-715)."""

    @pytest.mark.asyncio
    async def test_announce_peer_value_error_fallback(self):
        """Test announce_peer ValueError handling (lines 708-715)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.routing_table = MagicMock()
        client.routing_table.get_closest_nodes = MagicMock(
            return_value=[
                DHTNode(
                    b"\x01" * 20,
                    "192.168.1.1",
                    6881,
                    ipv6="2001:db8::1",
                    port6=6881,
                )
            ]
        )
        client.routing_table.mark_node_good = MagicMock()
        client.routing_table.mark_node_bad = MagicMock()
        
        # Create proper token mock
        from ccbt.discovery.dht import DHTToken
        import time
        token = DHTToken(b"token_data", b"\x11" * 20)
        client.tokens = {b"\x11" * 20: token}

        # Mock select_best_address to raise ValueError
        with patch("ccbt.discovery.dht_ipv6.select_best_address") as mock_select:
            mock_select.side_effect = ValueError("Invalid address")

            async def mock_send_query(addr, query, params):
                return {b"y": b"r", b"r": {b"id": b"\x02" * 20}}

            client._send_query = mock_send_query

            # Should handle ValueError and fallback
            result = await client.announce_peer(b"\x11" * 20, 6881)
            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_announce_peer_exception_handling(self):
        """Test announce_peer general exception handling (lines 734-738)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.routing_table = MagicMock()
        client.routing_table.get_closest_nodes = MagicMock(
            return_value=[DHTNode(b"\x01" * 20, "192.168.1.1", 6881)]
        )
        client.routing_table.mark_node_bad = MagicMock()
        
        # Create proper token mock
        from ccbt.discovery.dht import DHTToken
        token = DHTToken(b"token_data", b"\x11" * 20)
        client.tokens = {b"\x11" * 20: token}

        # Mock _send_query to raise exception
        async def mock_send_query(addr, query, params):
            raise Exception("Network error")

        client._send_query = mock_send_query

        # Should handle exception gracefully
        result = await client.announce_peer(b"\x11" * 20, 6881)
        assert isinstance(result, bool)


class TestDHTSendQueryTimeout:
    """Tests for _send_query timeout handling (lines 781-783)."""

    @pytest.mark.asyncio
    async def test_send_query_timeout(self):
        """Test _send_query timeout handling (lines 781-783)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.query_timeout = 0.1  # Short timeout
        client.transport = MagicMock()
        client.transport.is_closing.return_value = False
        client.pending_queries = {}

        # Mock _wait_for_response to timeout
        async def mock_wait_for_response(tid):
            await asyncio.sleep(0.2)  # Longer than timeout
            return {}

        client._wait_for_response = mock_wait_for_response

        # Should return None on timeout
        result = await client._send_query(("127.0.0.1", 6881), "ping", {})
        assert result is None


class TestDHTResponseHandling:
    """Tests for response handling error cases (lines 816-818)."""

    def test_handle_response_exception(self):
        """Test handle_response exception handling (lines 816-818)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.pending_queries = {}

        # Test with invalid bencode data
        invalid_data = b"invalid bencode data"

        # Should handle exception gracefully
        client.handle_response(invalid_data, ("127.0.0.1", 6881))
        # Should not crash


class TestDHTRefreshLoop:
    """Tests for _refresh_loop exception handling (lines 825-828)."""

    @pytest.mark.asyncio
    async def test_refresh_loop_exception_handling(self):
        """Test _refresh_loop exception handling (lines 825-828)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.routing_table = MagicMock()

        # Mock _refresh_routing_table to raise exception
        async def mock_refresh():
            raise Exception("Refresh error")

        client._refresh_routing_table = mock_refresh

        # Create refresh loop task
        task = asyncio.create_task(client._refresh_loop())

        # Wait a bit for it to run
        await asyncio.sleep(0.1)

        # Cancel task
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass


class TestDHTPutDataErrorHandling:
    """Tests for put_data error handling (lines 988-1017)."""

    @pytest.mark.asyncio
    async def test_put_data_value_error_fallback(self):
        """Test put_data ValueError handling (lines 988-1017)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.config = MagicMock()
        client.config.discovery = MagicMock()
        client.config.discovery.dht_enable_ipv6 = True
        client.config.discovery.dht_prefer_ipv6 = True
        client.config.discovery.dht_enable_multiaddress = False
        client.config.discovery.dht_max_addresses_per_node = 4

        client.routing_table = MagicMock()
        client.routing_table.get_closest_nodes = MagicMock(
            return_value=[
                DHTNode(
                    b"\x01" * 20,
                    "192.168.1.1",
                    6881,
                    ipv6="2001:db8::1",
                    port6=6881,
                )
            ]
        )
        client.routing_table.mark_node_good = MagicMock()
        client.routing_table.mark_node_bad = MagicMock()

        # Mock select_best_address to raise ValueError
        with patch("ccbt.discovery.dht_ipv6.select_best_address") as mock_select:
            mock_select.side_effect = ValueError("Invalid address")

            async def mock_send_query(addr, query, params):
                return {b"y": b"r", b"r": {b"id": b"\x02" * 20}}

            client._send_query = mock_send_query

            # Should handle ValueError and fallback
            result = await client.put_data(b"\x11" * 20, b"test_value")
            assert isinstance(result, int)

    @pytest.mark.asyncio
    async def test_put_data_exception_handling(self):
        """Test put_data general exception handling (lines 1008-1015)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.config = MagicMock()
        client.config.discovery = MagicMock()
        client.config.discovery.dht_enable_ipv6 = False
        client.config.discovery.dht_prefer_ipv6 = False
        client.config.discovery.dht_enable_multiaddress = False

        client.routing_table = MagicMock()
        client.routing_table.get_closest_nodes = MagicMock(
            return_value=[DHTNode(b"\x01" * 20, "192.168.1.1", 6881)]
        )
        client.routing_table.mark_node_bad = MagicMock()

        # Mock _send_query to raise exception
        async def mock_send_query(addr, query, params):
            raise Exception("Network error")

        client._send_query = mock_send_query

        # Should handle exception and mark node as bad
        result = await client.put_data(b"\x11" * 20, b"test_value")
        assert isinstance(result, int)
        client.routing_table.mark_node_bad.assert_called()


class TestDHTGetDataErrorHandling:
    """Tests for get_data error handling (lines 1053-1134)."""

    @pytest.mark.asyncio
    async def test_get_data_value_error_fallback(self):
        """Test get_data ValueError handling."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.config = MagicMock()
        client.config.discovery = MagicMock()
        client.config.discovery.dht_enable_ipv6 = True
        client.config.discovery.dht_prefer_ipv6 = True
        client.config.discovery.dht_enable_multiaddress = False

        client.routing_table = MagicMock()
        client.routing_table.get_closest_nodes = MagicMock(
            return_value=[
                DHTNode(
                    b"\x01" * 20,
                    "192.168.1.1",
                    6881,
                    ipv6="2001:db8::1",
                    port6=6881,
                )
            ]
        )
        client.routing_table.mark_node_good = MagicMock()
        client.routing_table.mark_node_bad = MagicMock()

        # Mock select_best_address to raise ValueError
        with patch("ccbt.discovery.dht_ipv6.select_best_address") as mock_select:
            mock_select.side_effect = ValueError("Invalid address")

            async def mock_send_query(addr, query, params):
                return {b"y": b"r", b"r": {b"id": b"\x02" * 20}}

            client._send_query = mock_send_query

            # Should handle ValueError and fallback
            result = await client.get_data(b"\x11" * 20)
            assert result is None or isinstance(result, bytes)


class TestDHTPeerCallbackErrorHandling:
    """Tests for peer callback error handling (lines 631-632)."""

    @pytest.mark.asyncio
    async def test_peer_callback_exception(self):
        """Test peer callback exception handling (lines 631-632)."""
        client = AsyncDHTClient(b"\x00" * 20)
        client.routing_table = MagicMock()
        client.routing_table.get_closest_nodes = MagicMock(return_value=[])
        client.tokens = {}
        
        # Add callback that raises exception
        def bad_callback(peers):
            raise Exception("Callback error")

        client.peer_callbacks = [bad_callback]

        # Should handle callback exception gracefully
        result = await client.get_peers(b"\x11" * 20)
        assert isinstance(result, list)

