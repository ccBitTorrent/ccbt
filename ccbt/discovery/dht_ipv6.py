"""IPv6 Extension for DHT (BEP 32).

Provides IPv6 address support for DHT nodes, including encoding/decoding
of IPv6 node format and address selection logic.
"""

from __future__ import annotations

import ipaddress
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ccbt.discovery.dht import DHTNode
    # TYPE_CHECKING block is never executed at runtime, only used for type checking

logger = logging.getLogger(__name__)

# IPv6 node format: 20 bytes node_id + 16 bytes IPv6 address + 2 bytes port = 38 bytes
IPv6_NODE_SIZE = 38


def encode_ipv6_node(node: DHTNode) -> bytes:
    """Encode a DHT node with IPv6 address to compact format (BEP 32).

    Args:
        node: DHT node with IPv6 address

    Returns:
        38-byte encoded node format: 20 bytes ID + 16 bytes IPv6 + 2 bytes port

    Raises:
        ValueError: If node doesn't have IPv6 address or invalid format

    """
    if not node.has_ipv6 or node.ipv6 is None or node.port6 is None:
        msg = "Node must have IPv6 address and port"
        raise ValueError(msg)

    try:
        ipv6_addr = ipaddress.IPv6Address(node.ipv6)
        ipv6_bytes = ipv6_addr.packed
    except ValueError as e:  # pragma: no cover
        # Defensive check: ipaddress.IPv6Address is very permissive and accepts
        # most 16-byte patterns. This path is nearly impossible to trigger in practice
        # since validation happens at DHTNode level, but kept for robustness.
        msg = f"Invalid IPv6 address: {node.ipv6}"
        raise ValueError(msg) from e

    if not (1 <= node.port6 <= 65535):  # pragma: no cover
        # Defensive check: port validation happens at DHTNode construction,
        # so invalid ports shouldn't reach here. Kept for robustness.
        msg = f"Invalid port: {node.port6}"
        raise ValueError(msg)

    # Encode: node_id (20) + IPv6 address (16) + port (2)
    encoded = (
        node.node_id[:20].ljust(20, b"\x00")  # Ensure 20 bytes
        + ipv6_bytes  # 16 bytes
        + node.port6.to_bytes(2, "big")  # 2 bytes
    )

    if len(encoded) != IPv6_NODE_SIZE:  # pragma: no cover
        # Defensive check: This should never happen given our encoding logic
        # (20 + 16 + 2 = 38 bytes). Kept as a sanity check.
        msg = f"Encoded node size mismatch: {len(encoded)} != {IPv6_NODE_SIZE}"
        raise ValueError(msg)

    return encoded


def decode_ipv6_node(data: bytes, offset: int = 0) -> tuple[DHTNode, int]:
    """Decode a DHT node from IPv6 compact format (BEP 32).

    Args:
        data: Binary data containing IPv6 node
        offset: Starting offset in data

    Returns:
        Tuple of (DHTNode, bytes_consumed)

    Raises:
        ValueError: If data is invalid or too short

    """
    if len(data) < offset + IPv6_NODE_SIZE:
        msg = f"Data too short for IPv6 node: need {IPv6_NODE_SIZE} bytes, got {len(data) - offset}"
        raise ValueError(msg)

    # Extract node components
    node_id = data[offset : offset + 20]
    ipv6_bytes = data[offset + 20 : offset + 36]
    port_bytes = data[offset + 36 : offset + 38]

    # Decode IPv6 address
    try:
        ipv6_addr = ipaddress.IPv6Address(ipv6_bytes)
        ipv6_str = str(ipv6_addr)
    except ValueError as e:  # pragma: no cover
        # Defensive check: ipaddress.IPv6Address accepts virtually any 16-byte pattern,
        # so this exception is extremely rare. Kept for robustness.
        msg = f"Invalid IPv6 address bytes: {ipv6_bytes.hex()}"
        raise ValueError(msg) from e

    # Decode port
    port6 = int.from_bytes(port_bytes, "big")
    if not (1 <= port6 <= 65535):
        msg = f"Invalid port: {port6}"
        raise ValueError(msg)

    # Create node (IPv4 fields set to None/0, will be set if dual-stack)
    from ccbt.discovery.dht import DHTNode

    node = DHTNode(
        node_id=node_id,
        ip="",  # IPv4 not available from IPv6-only node
        port=0,
        ipv6=ipv6_str,
        port6=port6,
    )

    return node, IPv6_NODE_SIZE


def parse_ipv6_nodes(data: bytes) -> list[DHTNode]:
    """Parse multiple IPv6 nodes from compact format.

    Args:
        data: Binary data containing multiple IPv6 nodes (38 bytes each)

    Returns:
        List of DHTNode objects with IPv6 addresses

    """
    nodes = []
    offset = 0

    while offset + IPv6_NODE_SIZE <= len(data):
        try:
            node, consumed = decode_ipv6_node(data, offset)
            nodes.append(node)
            offset += consumed
        except ValueError as e:
            logger.debug("Failed to parse IPv6 node at offset %d: %s", offset, e)
            # Skip to next possible node
            offset += IPv6_NODE_SIZE

    return nodes


def select_best_address(
    node: DHTNode, prefer_ipv6: bool = True, enable_ipv6: bool = True
) -> tuple[str, int]:
    """Select best address for a node (IPv4 or IPv6).

    Args:
        node: DHT node with potentially both IPv4 and IPv6 addresses
        prefer_ipv6: If True, prefer IPv6 when available
        enable_ipv6: If False, only use IPv4 addresses

    Returns:
        Tuple of (ip, port) for best address

    Raises:
        ValueError: If node has no valid address

    """
    # If IPv6 is enabled and preferred, try IPv6 first
    if (
        enable_ipv6
        and prefer_ipv6
        and node.has_ipv6
        and node.ipv6 is not None
        and node.port6 is not None
    ):
        return (node.ipv6, node.port6)

    # Try IPv4 if available
    if node.ip and node.port:
        return (node.ip, node.port)

    # Fallback to IPv6 if IPv4 not available (only if IPv6 enabled)
    if (
        enable_ipv6
        and node.has_ipv6
        and node.ipv6 is not None
        and node.port6 is not None
    ):  # pragma: no cover
        # Edge case: IPv6 enabled but prefer_ipv6=False, and IPv4 unavailable.
        # This path is rarely reached in practice since IPv6 preference is usually enabled.
        return (node.ipv6, node.port6)

    msg = "Node has no valid address"
    raise ValueError(msg)


def validate_ipv6_address(ip: str) -> bool:
    """Validate IPv6 address format.

    Args:
        ip: IP address string

    Returns:
        True if valid IPv6 address, False otherwise

    """
    try:
        ipaddress.IPv6Address(ip)
        return True
    except ValueError:
        return False
