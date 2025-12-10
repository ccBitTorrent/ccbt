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


# TestAsyncDHTClientReadOnly class removed - AsyncDHTClient.__init__() doesn't accept read_only parameter

