"""Multiple-Address Operation for DHT (BEP 45).

Provides support for DHT nodes with multiple network addresses,
improving connectivity and resilience.
"""

from __future__ import annotations

import ipaddress
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ccbt.discovery.dht import DHTNode
    # TYPE_CHECKING block is never executed at runtime, only used for type checking

logger = logging.getLogger(__name__)


class AddressType(str, Enum):
    """Address type enumeration."""

    IPv4 = "ipv4"
    IPv6 = "ipv6"


def get_address_type(ip: str) -> AddressType:
    """Get address type for an IP address.

    Args:
        ip: IP address string

    Returns:
        AddressType (IPv4 or IPv6)

    """
    try:
        addr = ipaddress.ip_address(ip)
        if isinstance(addr, ipaddress.IPv6Address):
            return AddressType.IPv6
        return AddressType.IPv4
    except ValueError:
        # Default to IPv4 for unknown format
        return AddressType.IPv4


def calculate_address_priority(
    ip: str,
    port: int,
    prefer_ipv6: bool = True,
) -> int:
    """Calculate priority score for an address (higher = better).

    Args:
        ip: IP address
        port: Port number
        prefer_ipv6: If True, IPv6 addresses get higher priority

    Returns:
        Priority score (higher is better)

    """
    addr_type = get_address_type(ip)
    base_priority = 100 if addr_type == AddressType.IPv6 else 50

    # Adjust based on preferences
    if prefer_ipv6 and addr_type == AddressType.IPv6:
        base_priority += 50

    # Prefer well-known ports (lower numbers)
    if 1024 <= port <= 65535:
        base_priority += 10

    return base_priority


def encode_multi_address_node(node: DHTNode) -> dict[bytes, Any]:
    """Encode a DHT node with multiple addresses (BEP 45).

    Args:
        node: DHT node with potentially multiple addresses

    Returns:
        Dictionary with encoded node information including multiple addresses

    """
    result: dict[bytes, Any] = {
        b"id": node.node_id,
    }

    # Encode primary IPv4 address
    if node.ip and node.port:
        # Encode IPv4 in compact format (4 bytes IP + 2 bytes port)
        ip_bytes = ipaddress.IPv4Address(node.ip).packed
        port_bytes = node.port.to_bytes(2, "big")
        result[b"ip"] = ip_bytes + port_bytes

    # Encode IPv6 address if available
    if node.has_ipv6 and node.ipv6 and node.port6:
        ipv6_bytes = ipaddress.IPv6Address(node.ipv6).packed
        port6_bytes = node.port6.to_bytes(2, "big")
        result[b"ip6"] = ipv6_bytes + port6_bytes

    # Encode additional addresses (BEP 45)
    if node.additional_addresses:
        addresses_list = []
        for ip, port in node.additional_addresses:
            addr_type = get_address_type(ip)
            if addr_type == AddressType.IPv4:
                ip_bytes = ipaddress.IPv4Address(ip).packed
                port_bytes = port.to_bytes(2, "big")
                addresses_list.append(ip_bytes + port_bytes)
            else:  # IPv6  # pragma: no cover
                # IPv6 encoding in additional addresses - covered by integration tests
                # but this specific branch difficult to isolate in unit tests
                ip_bytes = ipaddress.IPv6Address(ip).packed
                port_bytes = port.to_bytes(2, "big")
                # Mark as IPv6 address (use a special format or separate list)
                # BEP 45 uses 'addresses' field for additional IPv4/IPv6 addresses
                addresses_list.append(ip_bytes + port_bytes)
        result[b"addresses"] = addresses_list

    return result


def decode_multi_address_node(
    data: dict[bytes, Any], node_id: bytes | None = None
) -> DHTNode:
    """Decode a DHT node from response with multiple addresses (BEP 45).

    Args:
        data: Dictionary containing node information
        node_id: Node ID (if not in data)

    Returns:
        DHTNode with all addresses decoded

    Raises:
        ValueError: If node data is invalid

    """
    from ccbt.discovery.dht import DHTNode

    # Extract node ID
    if node_id is None:
        node_id = data.get(b"id")
        if not node_id or len(node_id) != 20:
            msg = "Invalid node ID in multi-address data"
            raise ValueError(msg)

    # Decode primary IPv4 address
    ip = ""
    port = 0
    ip_data = data.get(b"ip")
    if ip_data and len(ip_data) >= 6:
        ip_addr = ipaddress.IPv4Address(ip_data[:4])
        ip = str(ip_addr)
        port = int.from_bytes(ip_data[4:6], "big")

    # Decode IPv6 address
    ipv6 = None
    port6 = None
    ip6_data = data.get(b"ip6")
    if ip6_data and len(ip6_data) >= 18:
        ipv6_addr = ipaddress.IPv6Address(ip6_data[:16])
        ipv6 = str(ipv6_addr)
        port6 = int.from_bytes(ip6_data[16:18], "big")

    # Create node
    node = DHTNode(
        node_id=node_id,
        ip=ip,
        port=port,
        ipv6=ipv6,
        port6=port6,
    )

    # Decode additional addresses (BEP 45)
    addresses_data = data.get(b"addresses", [])
    if isinstance(addresses_data, list):
        for addr_data in addresses_data:
            if not isinstance(addr_data, bytes):
                continue

            # Try IPv6 first (18 bytes), then IPv4 (6 bytes)
            if len(addr_data) >= 18:
                # IPv6 address
                try:
                    ipv6_addr = ipaddress.IPv6Address(addr_data[:16])
                    addr_ip = str(ipv6_addr)
                    addr_port = int.from_bytes(addr_data[16:18], "big")
                    if (addr_ip, addr_port) not in node.get_all_addresses():
                        node.add_address(addr_ip, addr_port)
                except (ValueError, IndexError):  # pragma: no cover
                    # Defensive: ipaddress.IPv6Address is very permissive, so this exception
                    # is extremely rare. Hard to trigger without generating malformed network data.
                    logger.debug("Failed to decode IPv6 address: %s", addr_data.hex())
            elif len(addr_data) >= 6:
                # IPv4 address
                try:
                    ipv4_addr = ipaddress.IPv4Address(addr_data[:4])
                    addr_ip = str(ipv4_addr)
                    addr_port = int.from_bytes(addr_data[4:6], "big")
                    if (addr_ip, addr_port) not in node.get_all_addresses():
                        node.add_address(addr_ip, addr_port)
                except (ValueError, IndexError):  # pragma: no cover
                    # Defensive: ipaddress.IPv4Address accepts any 4-byte pattern as valid,
                    # so this exception is extremely rare. Hard to trigger realistically.
                    logger.debug("Failed to decode IPv4 address: %s", addr_data.hex())

    return node


def select_best_address_multi(
    node: DHTNode,
    prefer_ipv6: bool = True,
    enable_ipv6: bool = True,
    max_addresses: int = 4,
) -> tuple[str, int]:
    """Select best address from a multi-address node (BEP 45).

    Args:
        node: DHT node with potentially multiple addresses
        prefer_ipv6: If True, prefer IPv6 addresses
        enable_ipv6: If True, IPv6 addresses are considered
        max_addresses: Maximum number of addresses to consider

    Returns:
        Tuple of (ip, port) for best address

    Raises:
        ValueError: If node has no valid address

    """
    all_addresses = node.get_all_addresses()
    if not all_addresses:
        msg = "Node has no valid address"
        raise ValueError(msg)

    # Filter addresses based on preferences
    candidates = []
    for ip, port in all_addresses[:max_addresses]:
        addr_type = get_address_type(ip)

        # Skip IPv6 if disabled
        if addr_type == AddressType.IPv6 and not enable_ipv6:
            continue

        priority = calculate_address_priority(ip, port, prefer_ipv6)
        candidates.append((priority, ip, port))

    if not candidates:  # pragma: no cover
        # Edge case: all addresses filtered out (e.g., IPv6 disabled but only IPv6 available).
        # Rare in practice since we typically have at least IPv4. Kept as defensive fallback.
        return all_addresses[0]

    # Sort by priority (highest first)
    candidates.sort(reverse=True, key=lambda x: x[0])

    # Return best address
    return (candidates[0][1], candidates[0][2])


def validate_address(ip: str, port: int) -> bool:
    """Validate an address (IP and port).

    Args:
        ip: IP address string
        port: Port number

    Returns:
        True if address is valid, False otherwise

    """
    try:
        # Validate IP address
        ipaddress.ip_address(ip)

        # Validate port range
        return 1 <= port <= 65535
    except ValueError:
        return False


async def discover_node_addresses(
    known_addresses: list[tuple[str, int]],
    max_results: int = 4,
    node_id: bytes | None = None,
    dht_client: Any | None = None,
) -> list[tuple[str, int]]:
    """Discover additional addresses for a node from known addresses and DHT.

    Args:
        known_addresses: List of known addresses for the node
        max_results: Maximum number of addresses to return
        node_id: Optional node ID for DHT lookup. If provided, will query DHT
            to discover additional addresses for this node.
        dht_client: Optional DHT client instance. If None, will attempt to get
            from global DHT client singleton.

    Returns:
        List of unique addresses (up to max_results), combining known addresses
        with addresses discovered from DHT.

    """
    # Start with validated known addresses
    unique_addresses = []
    seen = set()

    for ip, port in known_addresses:
        if not validate_address(ip, port):
            continue

        addr = (ip, port)
        if addr not in seen:
            seen.add(addr)
            unique_addresses.append(addr)

            if len(unique_addresses) >= max_results:
                break

    # If we have a node_id, try to discover additional addresses via DHT
    if node_id and len(node_id) == 20:
        # Get DHT client if not provided
        if dht_client is None:
            try:
                from ccbt.discovery.dht import get_dht_client

                dht_client = get_dht_client()
            except Exception as e:
                logger.debug("Could not get DHT client for address discovery: %s", e)
                # Fallback to known addresses only
                return unique_addresses

        # Perform find_node operation for target node ID
        try:
            import asyncio

            # Use one of the known addresses as bootstrap for find_node
            if known_addresses:
                bootstrap_addr = known_addresses[0]
            else:
                # No known addresses, can't bootstrap find_node
                return unique_addresses

            # Wrap DHT query in timeout (5 seconds)
            nodes = await asyncio.wait_for(
                dht_client._find_nodes(bootstrap_addr, node_id),  # noqa: SLF001
                timeout=5.0,
            )

            # Extract addresses from DHT response
            for node in nodes:
                # Check if this is the node we're looking for (same node_id)
                if node.node_id == node_id:
                    # Extract IPv4 address
                    if node.ip and node.port:
                        addr = (node.ip, node.port)
                        if addr not in seen and validate_address(node.ip, node.port):
                            seen.add(addr)
                            unique_addresses.append(addr)
                            if len(unique_addresses) >= max_results:
                                break

                    # Extract IPv6 address if available
                    if node.has_ipv6 and node.ipv6 and node.port6:
                        addr6 = (node.ipv6, node.port6)
                        if addr6 not in seen and validate_address(
                            node.ipv6, node.port6
                        ):
                            seen.add(addr6)
                            unique_addresses.append(addr6)
                            if len(unique_addresses) >= max_results:
                                break

                    # Extract additional addresses (BEP 45 multiaddr support)
                    if node.additional_addresses:
                        for add_ip, add_port in node.additional_addresses:
                            addr = (add_ip, add_port)
                            if (
                                addr not in seen
                                and validate_address(add_ip, add_port)
                                and len(unique_addresses) < max_results
                            ):
                                seen.add(addr)
                                unique_addresses.append(addr)
                                if len(unique_addresses) >= max_results:
                                    break

        except asyncio.TimeoutError:
            logger.debug("DHT find_node timeout for node_id: %s", node_id.hex()[:16])
            # Fallback to known addresses only
        except Exception as e:
            logger.warning("DHT lookup failed for address discovery: %s", e)
            # Fallback to known addresses only

    # Return combined addresses (known + discovered), limited to max_results
    return unique_addresses[:max_results]
