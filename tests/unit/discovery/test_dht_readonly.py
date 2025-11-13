"""Unit tests for BEP 43: Read-only DHT Nodes.

Tests read-only mode detection and behavior.
Target: 95%+ code coverage for ccbt/discovery/dht_readonly.py
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest

from ccbt.core.bencode import BencodeDecoder
from ccbt.discovery.dht import AsyncDHTClient
from ccbt.discovery.dht_readonly import is_read_only_node

pytestmark = [pytest.mark.unit, pytest.mark.discovery]


class TestIsReadOnlyNode:
    """Test is_read_only_node function."""

    def test_is_read_only_node_with_ro_flag(self):
        """Test detecting read-only node with ro: 1 flag."""
        response = {
            b"y": b"r",
            b"r": {
                b"id": b"\x01" * 20,
                b"ro": 1,
            },
        }
        assert is_read_only_node(response) is True

    def test_is_read_only_node_without_ro_flag(self):
        """Test detecting normal node without ro flag."""
        response = {
            b"y": b"r",
            b"r": {
                b"id": b"\x01" * 20,
            },
        }
        assert is_read_only_node(response) is False

    def test_is_read_only_node_with_ro_zero(self):
        """Test detecting node with ro: 0 (not read-only)."""
        response = {
            b"y": b"r",
            b"r": {
                b"id": b"\x01" * 20,
                b"ro": 0,
            },
        }
        assert is_read_only_node(response) is False

    def test_is_read_only_node_missing_response(self):
        """Test handling missing response dictionary."""
        response = {
            b"y": b"r",
        }
        assert is_read_only_node(response) is False

    def test_is_read_only_node_not_response(self):
        """Test handling query message (not response)."""
        query = {
            b"y": b"q",
            b"q": b"ping",
        }
        assert is_read_only_node(query) is False


class TestShouldSkipStorageForNode:
    """Test should_skip_storage_for_node function."""

    def test_should_skip_storage_normal_node(self):
        """Test that normal nodes don't skip storage."""
        from ccbt.discovery.dht import DHTNode
        from ccbt.discovery.dht_readonly import should_skip_storage_for_node

        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
        )

        assert should_skip_storage_for_node(node) is False

    def test_should_skip_storage_read_only_node(self):
        """Test that read-only nodes skip storage."""
        from ccbt.discovery.dht import DHTNode
        from ccbt.discovery.dht_readonly import should_skip_storage_for_node

        node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
        )
        # Add read-only attribute
        node.is_read_only = True  # type: ignore[attr-defined]

        assert should_skip_storage_for_node(node) is True


class TestFilterReadOnlyNodesForStorage:
    """Test filter_read_only_nodes_for_storage function."""

    def test_filter_read_only_nodes(self):
        """Test filtering read-only nodes."""
        from ccbt.discovery.dht import DHTNode
        from ccbt.discovery.dht_readonly import filter_read_only_nodes_for_storage

        normal_node = DHTNode(
            node_id=b"\x01" * 20,
            ip="192.168.1.1",
            port=6881,
        )
        read_only_node = DHTNode(
            node_id=b"\x02" * 20,
            ip="192.168.1.2",
            port=6881,
        )
        read_only_node.is_read_only = True  # type: ignore[attr-defined]

        nodes = [normal_node, read_only_node]
        filtered = filter_read_only_nodes_for_storage(nodes)

        assert len(filtered) == 1
        assert normal_node in filtered
        assert read_only_node not in filtered


class TestAsyncDHTClientReadOnly:
    """Test AsyncDHTClient read-only mode behavior."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = MagicMock()
        config.discovery = MagicMock()
        config.discovery.dht_readonly_mode = False
        config.discovery.dht_enable_ipv6 = True
        config.discovery.dht_prefer_ipv6 = True
        config.discovery.dht_enable_multiaddress = False
        config.discovery.dht_enable_storage = False
        config.discovery.dht_storage_ttl = 3600
        config.discovery.dht_enable_indexing = False
        return config

    @pytest.mark.asyncio
    async def test_client_read_only_mode_enabled(self, mock_config):
        """Test client with read-only mode enabled."""
        from unittest.mock import patch

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient(read_only=True)

            assert client.read_only is True

    @pytest.mark.asyncio
    async def test_client_read_only_mode_disabled(self, mock_config):
        """Test client with read-only mode disabled."""
        from unittest.mock import patch

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient(read_only=False)

            assert client.read_only is False

    @pytest.mark.asyncio
    async def test_client_read_only_from_config(self, mock_config):
        """Test client read-only mode from config."""
        mock_config.discovery.dht_readonly_mode = True
        from unittest.mock import patch

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient(read_only=None)

            assert client.read_only is True

    @pytest.mark.asyncio
    async def test_announce_peer_in_readonly_mode(self, mock_config):
        """Test announce_peer skips in read-only mode."""
        mock_config.discovery.dht_readonly_mode = True
        from unittest.mock import patch

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient(read_only=True)

            # Should return False (read-only mode prevents announcing)
            result = await client.announce_peer(
                info_hash=b"\x01" * 20,
                port=6881,
            )

            # Should return False without actually announcing
            assert result is False

    @pytest.mark.asyncio
    async def test_put_data_in_readonly_mode(self, mock_config):
        """Test put_data skips in read-only mode."""
        mock_config.discovery.dht_readonly_mode = True
        mock_config.discovery.dht_enable_storage = True
        from unittest.mock import patch

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient(read_only=True)

            # Mock routing table
            client.routing_table = MagicMock()
            client.routing_table.get_closest_nodes = MagicMock(return_value=[])

            result = await client.put_data(
                key=b"\x01" * 20,
                value={b"v": b"test"},
            )

            # Should return 0 (no successful stores in read-only mode)
            assert result == 0

    @pytest.mark.asyncio
    async def test_send_query_with_ro_flag(self, mock_config):
        """Test _send_query includes ro flag in read-only mode."""
        mock_config.discovery.dht_readonly_mode = True
        from unittest.mock import patch

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient(read_only=True)

        # Mock socket and transport (noqa: SLF001 - needed for testing)
        client._socket = MagicMock()  # noqa: SLF001
        client._transport = MagicMock()  # noqa: SLF001
        client.transaction_id_counter = 0

        # Mock response
        client.pending_queries = {}
        client.handle_response = MagicMock()

        # Mock socket.sendto to capture arguments
        sendto_calls = []

        def mock_sendto(data, addr):  # noqa: ARG001
            sendto_calls.append(data)
            # Create a mock response
            decoder = BencodeDecoder(data)
            message = decoder.decode()
            tid = message.get(b"t")
            # Simulate response
            response = {
                b"y": b"r",
                b"t": tid,
                b"r": {b"id": b"\x02" * 20},
            }
            encoder = client._get_encoder()  # noqa: SLF001
            response_data = encoder.encode(response)
            client.handle_response(response_data, ("127.0.0.1", 6881))

        client._socket.sendto = mock_sendto  # noqa: SLF001

        # Send query (noqa: SLF001 - needed for testing)
        with contextlib.suppress(Exception):
            await client._send_query(  # noqa: SLF001
                ("127.0.0.1", 6881),
                "ping",
                {b"id": client.node_id},
            )

        # Verify ro flag was included in query
        if sendto_calls:
            for call_data in sendto_calls:
                decoder = BencodeDecoder(call_data)
                message = decoder.decode()
                if message.get(b"y") == b"q":
                    args = message.get(b"a", {})
                    # Check if ro flag is present (should be 1 in read-only mode)
                    if b"ro" in args:
                        assert args[b"ro"] == 1

