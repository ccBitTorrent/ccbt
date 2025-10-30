"""Peer Exchange (PEX) extension implementation.

Provides support for:
- Peer discovery through PEX
- Compact peer format
- IPv6 support
"""

from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ccbt.models import PeerInfo
from ccbt.utils.events import Event, EventType, emit_event


class PEXMessageType(IntEnum):
    """PEX message types."""

    ADDED = 0
    DROPPED = 1


@dataclass(frozen=True)
class PEXPeer:
    """PEX peer information."""

    ip: str
    port: int
    flags: int = 0  # Bit flags for peer properties

    def to_peer_info(self) -> PeerInfo:
        """Convert to PeerInfo."""
        return PeerInfo(ip=self.ip, port=self.port)

    @classmethod
    def from_peer_info(cls, peer_info: PeerInfo, flags: int = 0) -> PEXPeer:
        """Create from PeerInfo."""
        return cls(ip=peer_info.ip, port=peer_info.port, flags=flags)


class PeerExchange:
    """Peer Exchange (PEX) implementation."""

    def __init__(self):
        """Initialize PEX message data."""
        self.added_peers: set[PEXPeer] = set()
        self.dropped_peers: set[PEXPeer] = set()
        self.peer_flags: dict[tuple[str, int], int] = {}  # (ip, port) -> flags

    def encode_compact_peer(self, peer: PEXPeer) -> bytes:
        """Encode peer in compact format."""
        try:
            # Try IPv4 first
            ip_bytes = socket.inet_aton(peer.ip)
            if len(ip_bytes) == 4:  # IPv4
                return struct.pack("!4sH", ip_bytes, peer.port)
            msg = "Invalid IPv4 address"
            raise ValueError(msg)
        except (OSError, ValueError):
            try:
                # Try IPv6
                ip_bytes = socket.inet_pton(socket.AF_INET6, peer.ip)
                if len(ip_bytes) == 16:  # IPv6
                    return struct.pack("!16sH", ip_bytes, peer.port)
                msg = "Invalid IPv6 address"
                raise ValueError(msg)
            except (OSError, ValueError) as e:
                msg = f"Invalid IP address: {peer.ip}"
                raise ValueError(msg) from e

    def decode_compact_peer(self, data: bytes, is_ipv6: bool = False) -> PEXPeer:
        """Decode peer from compact format."""
        if is_ipv6:
            if len(data) < 18:  # 16 bytes IP + 2 bytes port
                msg = "Invalid IPv6 compact peer format"
                raise ValueError(msg)

            ip_bytes, port = struct.unpack("!16sH", data[:18])
            ip = socket.inet_ntop(socket.AF_INET6, ip_bytes)
        else:
            if len(data) < 6:  # 4 bytes IP + 2 bytes port
                msg = "Invalid IPv4 compact peer format"
                raise ValueError(msg)

            ip_bytes, port = struct.unpack("!4sH", data[:6])
            ip = socket.inet_ntop(socket.AF_INET, ip_bytes)

        return PEXPeer(ip=ip, port=port)

    def encode_peers_list(self, peers: list[PEXPeer], _is_ipv6: bool = False) -> bytes:
        """Encode list of peers in compact format."""
        if not peers:
            return b""

        peer_data = b""
        for peer in peers:
            peer_data += self.encode_compact_peer(peer)

        return peer_data

    def decode_peers_list(self, data: bytes, is_ipv6: bool = False) -> list[PEXPeer]:
        """Decode list of peers from compact format."""
        peers = []

        peer_size = (
            18 if is_ipv6 else 6
        )  # 16 bytes IP + 2 bytes port for IPv6, 4 bytes IP + 2 bytes port for IPv4

        for i in range(0, len(data), peer_size):
            if i + peer_size <= len(data):
                try:
                    peer = self.decode_compact_peer(data[i : i + peer_size], is_ipv6)
                    peers.append(peer)
                except ValueError:
                    # Skip invalid peer data
                    continue

        return peers

    def encode_added_peers(self, peers: list[PEXPeer], is_ipv6: bool = False) -> bytes:
        """Encode added peers message."""
        peers_data = self.encode_peers_list(peers, is_ipv6)

        # Pack message: <length><message_id><peers_data>
        return (
            struct.pack("!IB", len(peers_data) + 1, PEXMessageType.ADDED) + peers_data
        )

    def encode_dropped_peers(
        self,
        peers: list[PEXPeer],
        is_ipv6: bool = False,
    ) -> bytes:
        """Encode dropped peers message."""
        peers_data = self.encode_peers_list(peers, is_ipv6)

        # Pack message: <length><message_id><peers_data>
        return (
            struct.pack("!IB", len(peers_data) + 1, PEXMessageType.DROPPED) + peers_data
        )

    def decode_pex_message(
        self,
        data: bytes,
        is_ipv6: bool = False,
    ) -> tuple[int, list[PEXPeer]]:
        """Decode PEX message."""
        if len(data) < 5:
            msg = "Invalid PEX message"
            raise ValueError(msg)

        length, message_id = struct.unpack("!IB", data[:5])

        if len(data) < 5 + length - 1:
            msg = "Incomplete PEX message"
            raise ValueError(msg)

        peers_data = data[5 : 5 + length - 1]
        peers = self.decode_peers_list(peers_data, is_ipv6)

        return message_id, peers

    async def handle_added_peers(self, peer_id: str, peers: list[PEXPeer]) -> None:
        """Handle added peers from PEX."""
        for pex_peer in peers:
            self.added_peers.add(pex_peer)

            # Emit event for new peer discovered
            await emit_event(
                Event(
                    event_type=EventType.PEER_DISCOVERED.value,
                    data={
                        "peer_id": peer_id,
                        "new_peer": {
                            "ip": pex_peer.ip,
                            "port": pex_peer.port,
                            "flags": pex_peer.flags,
                        },
                        "source": "pex",
                        "timestamp": time.time(),
                    },
                ),
            )

    async def handle_dropped_peers(self, peer_id: str, peers: list[PEXPeer]) -> None:
        """Handle dropped peers from PEX."""
        for pex_peer in peers:
            self.dropped_peers.add(pex_peer)

            # Emit event for peer dropped
            await emit_event(
                Event(
                    event_type=EventType.PEER_DROPPED.value,
                    data={
                        "peer_id": peer_id,
                        "dropped_peer": {
                            "ip": pex_peer.ip,
                            "port": pex_peer.port,
                            "flags": pex_peer.flags,
                        },
                        "source": "pex",
                        "timestamp": time.time(),
                    },
                ),
            )

    def add_peer(self, peer: PEXPeer) -> None:
        """Add peer to added peers set."""
        self.added_peers.add(peer)

    def drop_peer(self, peer: PEXPeer) -> None:
        """Add peer to dropped peers set."""
        self.dropped_peers.add(peer)

    def get_added_peers(self) -> set[PEXPeer]:
        """Get set of added peers."""
        return self.added_peers.copy()

    def get_dropped_peers(self) -> set[PEXPeer]:
        """Get set of dropped peers."""
        return self.dropped_peers.copy()

    def clear_added_peers(self) -> None:
        """Clear added peers set."""
        self.added_peers.clear()

    def clear_dropped_peers(self) -> None:
        """Clear dropped peers set."""
        self.dropped_peers.clear()

    def get_peer_flags(self, ip: str, port: int) -> int:
        """Get peer flags."""
        return self.peer_flags.get((ip, port), 0)

    def set_peer_flags(self, ip: str, port: int, flags: int) -> None:
        """Set peer flags."""
        self.peer_flags[(ip, port)] = flags

    def is_peer_seed(self, ip: str, port: int) -> bool:
        """Check if peer is a seed."""
        flags = self.get_peer_flags(ip, port)
        return (flags & 0x01) != 0  # Bit 0 indicates seed

    def is_peer_connectable(self, ip: str, port: int) -> bool:
        """Check if peer is connectable."""
        flags = self.get_peer_flags(ip, port)
        return (flags & 0x02) != 0  # Bit 1 indicates connectable

    def get_peer_statistics(self) -> dict[str, Any]:
        """Get PEX statistics."""
        return {
            "added_peers_count": len(self.added_peers),
            "dropped_peers_count": len(self.dropped_peers),
            "total_peers_with_flags": len(self.peer_flags),
            "seeds_count": sum(
                1 for flags in self.peer_flags.values() if (flags & 0x01) != 0
            ),
            "connectable_peers_count": sum(
                1 for flags in self.peer_flags.values() if (flags & 0x02) != 0
            ),
        }

    def create_peer_from_info(
        self,
        peer_info: PeerInfo,
        is_seed: bool = False,
        is_connectable: bool = True,
    ) -> PEXPeer:
        """Create PEX peer from PeerInfo."""
        flags = 0
        if is_seed:
            flags |= 0x01
        if is_connectable:
            flags |= 0x02

        return PEXPeer(ip=peer_info.ip, port=peer_info.port, flags=flags)

    def filter_peers_by_flags(
        self,
        peers: list[PEXPeer],
        require_seed: bool = False,
        require_connectable: bool = False,
    ) -> list[PEXPeer]:
        """Filter peers by flags."""
        filtered_peers = []

        for peer in peers:
            if require_seed and not self.is_peer_seed(peer.ip, peer.port):
                continue
            if require_connectable and not self.is_peer_connectable(peer.ip, peer.port):
                continue

            filtered_peers.append(peer)

        return filtered_peers

    def merge_peer_lists(
        self,
        peers1: list[PEXPeer],
        peers2: list[PEXPeer],
    ) -> list[PEXPeer]:
        """Merge two peer lists, removing duplicates."""
        peer_set = set()
        merged_peers = []

        for peer in peers1 + peers2:
            peer_key = (peer.ip, peer.port)
            if peer_key not in peer_set:
                peer_set.add(peer_key)
                merged_peers.append(peer)

        return merged_peers
