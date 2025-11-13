"""Read-only DHT Nodes support (BEP 43).

Provides utilities for detecting and handling read-only DHT nodes,
which can query the DHT but cannot store data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ccbt.discovery.dht import DHTNode
    # TYPE_CHECKING block is never executed at runtime, only used for type checking

logger = logging.getLogger(__name__)


def is_read_only_node(response: dict[bytes, Any]) -> bool:
    """Check if a DHT response indicates a read-only node (BEP 43).

    Args:
        response: DHT response message dictionary

    Returns:
        True if node is read-only (has ro: 1 in response)

    """
    if response.get(b"y") != b"r":
        return False

    r = response.get(b"r", {})
    # Check for ro: 1 in response arguments (BEP 43)
    ro_flag = r.get(b"ro")
    return ro_flag == 1


def should_skip_storage_for_node(node: DHTNode) -> bool:
    """Check if storage operations should be skipped for a node.

    Args:
        node: DHT node to check

    Returns:
        True if node is read-only and storage should be skipped

    """
    # Check if node has read-only flag set (requires DHTNode extension)
    # For now, nodes don't track read-only status, so return False
    # This function exists for future extension when we track node read-only status
    return hasattr(node, "is_read_only") and getattr(node, "is_read_only", False)


def filter_read_only_nodes_for_storage(
    nodes: list[DHTNode],
) -> list[DHTNode]:
    """Filter out read-only nodes from a list for storage operations.

    Args:
        nodes: List of DHT nodes

    Returns:
        Filtered list excluding read-only nodes

    """
    # For now, return all nodes since we don't track read-only status per node
    # This function exists for future extension
    return [node for node in nodes if not should_skip_storage_for_node(node)]
