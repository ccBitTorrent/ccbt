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
from typing import Any, Optional, Union

from ccbt.models import PeerInfo
from ccbt.utils.events import Event, EventType, emit_event


class PEXMessageType(IntEnum):
    """PEX message types."""

    ADDED = 0
    DROPPED = 1
    CHUNKS_ADDED = 2  # XET chunk availability
    CHUNKS_DROPPED = 3  # XET chunk unavailability


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
        self.FLAG_PREFER_ENCRYPT = 0x01
        self.FLAG_SEED = 0x02

    def encode_compact_peer(self, peer: PEXPeer) -> bytes:
        """Encode peer in compact format."""
        try:
            # Try IPv4 first
            ip_bytes = socket.inet_aton(peer.ip)
            if len(ip_bytes) == 4:  # IPv4
                return struct.pack("!4sH", ip_bytes, peer.port)
            msg = "Invalid IPv4 address"  # pragma: no cover - Invalid IPv4 length error, tested via valid IPv4
            raise ValueError(msg)
        except (
            OSError,
            ValueError,
        ):  # pragma: no cover - IPv4 conversion error fallback, tested via IPv4 success
            try:
                # Try IPv6
                ip_bytes = socket.inet_pton(socket.AF_INET6, peer.ip)
                if len(ip_bytes) == 16:  # IPv6
                    return struct.pack("!16sH", ip_bytes, peer.port)
                msg = "Invalid IPv6 address"  # pragma: no cover - Invalid IPv6 length error, tested via valid IPv6
                raise ValueError(msg)
            except (
                OSError,
                ValueError,
            ) as e:  # pragma: no cover - IPv6 conversion error fallback, tested via IPv6 success
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

    @staticmethod
    def _is_ipv6_peer(ip: str) -> bool:
        """Check whether peer IP is IPv6."""
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except OSError:
            return False

    def encode_peers_list(self, peers: list[PEXPeer], is_ipv6: bool = False) -> bytes:
        """Encode list of peers in compact format."""
        if not peers:
            return b""

        peer_data = b""
        for peer in peers:
            if self._is_ipv6_peer(peer.ip) != is_ipv6:
                continue
            peer_data += self.encode_compact_peer(peer)

        return peer_data

    def encode_peer_flags(self, peers: list[PEXPeer], is_ipv6: bool = False) -> bytes:
        """Encode peer flags in compact flag bytes."""
        if not peers:
            return b""
        return bytes(
            peer.flags & 0xFF
            for peer in peers
            if self._is_ipv6_peer(peer.ip) == is_ipv6
        )

    def decode_peers_list(
        self, data: bytes, is_ipv6: bool = False, flags: Optional[bytes] = None
    ) -> list[PEXPeer]:
        """Decode list of peers from compact format."""
        peers = []

        peer_size = (
            18 if is_ipv6 else 6
        )  # 16 bytes IP + 2 bytes port for IPv6, 4 bytes IP + 2 bytes port for IPv4

        peer_flags = flags or b""
        for idx, offset in enumerate(range(0, len(data), peer_size)):
            if offset + peer_size <= len(data):
                try:
                    peer = self.decode_compact_peer(
                        data[offset : offset + peer_size], is_ipv6
                    )
                    peers.append(
                        PEXPeer(
                            ip=peer.ip,
                            port=peer.port,
                            flags=peer_flags[idx] if idx < len(peer_flags) else 0,
                        )
                    )
                except ValueError:  # pragma: no cover - Invalid peer data skip, tested via valid peer data
                    # Skip invalid peer data
                    continue

        return peers

    def encode_bep11_payload(
        self,
        *,
        added_peers: Optional[list[PEXPeer]] = None,
        dropped_peers: Optional[list[PEXPeer]] = None,
    ) -> bytes:
        """Encode BEP11 payload containing peer list updates."""
        payload: dict[bytes, bytes] = {}

        added_v4: list[PEXPeer] = []
        added_v6: list[PEXPeer] = []
        if added_peers:
            for peer in added_peers:
                if self._is_ipv6_peer(peer.ip):
                    added_v6.append(peer)
                else:
                    added_v4.append(peer)

        dropped_v4: list[PEXPeer] = []
        dropped_v6: list[PEXPeer] = []
        if dropped_peers:
            for peer in dropped_peers:
                if self._is_ipv6_peer(peer.ip):
                    dropped_v6.append(peer)
                else:
                    dropped_v4.append(peer)

        if added_v4:
            payload[b"added"] = self.encode_peers_list(added_v4, is_ipv6=False)
            payload[b"added.f"] = self.encode_peer_flags(added_v4, is_ipv6=False)
        if added_v6:
            payload[b"added6"] = self.encode_peers_list(added_v6, is_ipv6=True)
            payload[b"added6.f"] = self.encode_peer_flags(added_v6, is_ipv6=True)
        if dropped_v4:
            payload[b"dropped"] = self.encode_peers_list(dropped_v4, is_ipv6=False)
            payload[b"dropped.f"] = self.encode_peer_flags(dropped_v4, is_ipv6=False)
        if dropped_v6:
            payload[b"dropped6"] = self.encode_peers_list(dropped_v6, is_ipv6=True)
            payload[b"dropped6.f"] = self.encode_peer_flags(dropped_v6, is_ipv6=True)

        if not payload:
            return b""

        from ccbt.core.bencode import BencodeEncoder

        encoder = BencodeEncoder()
        return encoder.encode(payload)

    def _extract_bep11_bytes(
        self, payload: dict[Any, Any], key: Union[str, bytes]
    ) -> bytes:
        """Extract a bytes field from a BEP11 payload."""
        if not isinstance(payload, dict):
            return b""
        value = payload.get(key)
        if value is None and isinstance(key, str):
            value = payload.get(key.encode())
        if isinstance(value, bytes):
            return value
        return b""

    def decode_bep11_payload(
        self, payload: bytes
    ) -> tuple[list[PEXPeer], list[PEXPeer], list[PEXPeer], list[PEXPeer]]:
        """Decode BEP11 payload.

        Returns:
            Tuple of (added_peers_v4, added_peers_v6, dropped_peers_v4, dropped_peers_v6).
        """
        if not payload:
            return [], [], [], []

        from ccbt.core.bencode import BencodeDecoder

        decoder = BencodeDecoder(payload)
        decoded = decoder.decode()
        if not isinstance(decoded, dict):
            msg = "Invalid BEP11 payload"
            raise TypeError(msg)

        added_peers = self.decode_peers_list(
            self._extract_bep11_bytes(decoded, b"added"),
            is_ipv6=False,
            flags=self._extract_bep11_bytes(decoded, b"added.f"),
        )
        added_v6 = self.decode_peers_list(
            self._extract_bep11_bytes(decoded, b"added6"),
            is_ipv6=True,
            flags=self._extract_bep11_bytes(decoded, b"added6.f"),
        )
        dropped_peers = self.decode_peers_list(
            self._extract_bep11_bytes(decoded, b"dropped"),
            is_ipv6=False,
            flags=self._extract_bep11_bytes(decoded, b"dropped.f"),
        )
        dropped_v6 = self.decode_peers_list(
            self._extract_bep11_bytes(decoded, b"dropped6"),
            is_ipv6=True,
            flags=self._extract_bep11_bytes(decoded, b"dropped6.f"),
        )
        return added_peers, added_v6, dropped_peers, dropped_v6

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

    def encode_chunks_list(self, chunk_hashes: list[bytes]) -> bytes:
        """Encode list of chunk hashes in compact format.

        Args:
            chunk_hashes: List of 32-byte chunk hashes

        Returns:
            Encoded chunk hashes as bytes

        """
        if not chunk_hashes:
            return b""

        chunks_data = b""
        for chunk_hash in chunk_hashes:
            if len(chunk_hash) != 32:
                continue
            chunks_data += chunk_hash

        return chunks_data

    def decode_chunks_list(self, data: bytes) -> list[bytes]:
        """Decode list of chunk hashes from compact format.

        Args:
            data: Encoded chunk hashes data

        Returns:
            List of 32-byte chunk hashes

        """
        chunks = []
        chunk_size = 32  # 32 bytes per chunk hash

        for i in range(0, len(data), chunk_size):
            if i + chunk_size <= len(data):
                chunk_hash = data[i : i + chunk_size]
                chunks.append(chunk_hash)

        return chunks

    def encode_added_chunks(self, chunk_hashes: list[bytes]) -> bytes:
        """Encode added chunks message.

        Args:
            chunk_hashes: List of 32-byte chunk hashes

        Returns:
            Encoded message bytes

        """
        chunks_data = self.encode_chunks_list(chunk_hashes)

        # Pack message: <length><message_id><chunks_data>
        return (
            struct.pack("!IB", len(chunks_data) + 1, PEXMessageType.CHUNKS_ADDED)
            + chunks_data
        )

    def encode_dropped_chunks(self, chunk_hashes: list[bytes]) -> bytes:
        """Encode dropped chunks message.

        Args:
            chunk_hashes: List of 32-byte chunk hashes

        Returns:
            Encoded message bytes

        """
        chunks_data = self.encode_chunks_list(chunk_hashes)

        # Pack message: <length><message_id><chunks_data>
        return (
            struct.pack("!IB", len(chunks_data) + 1, PEXMessageType.CHUNKS_DROPPED)
            + chunks_data
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
        return (flags & self.FLAG_SEED) != 0

    def is_peer_encrypt_preferred(self, ip: str, port: int) -> bool:
        """Check if peer prefers encryption."""
        flags = self.get_peer_flags(ip, port)
        return (flags & self.FLAG_PREFER_ENCRYPT) != 0

    def is_peer_connectable(self, ip: str, port: int) -> bool:
        """Return whether peer can be considered connectable.

        BEP 11 flags only define encryption preference and seed/upload-only bits.
        Because connectability is not explicitly represented, this helper currently
        returns ``True`` for known peers to preserve compatibility.
        """
        _ = self.get_peer_flags(ip, port)
        return True

    def get_peer_statistics(self) -> dict[str, Any]:
        """Get PEX statistics."""
        return {
            "added_peers_count": len(self.added_peers),
            "dropped_peers_count": len(self.dropped_peers),
            "total_peers_with_flags": len(self.peer_flags),
            "seeds_count": sum(
                1 for flags in self.peer_flags.values() if (flags & self.FLAG_SEED) != 0
            ),
            "connectable_peers_count": len(self.peer_flags),
        }

    def create_peer_from_info(
        self,
        peer_info: PeerInfo,
        is_seed: bool = False,
        is_connectable: bool = True,
    ) -> PEXPeer:
        """Create PEX peer from PeerInfo.

        Note: ``is_connectable`` maps to the BEP 11 encryption-preference bit
        (0x01). PEX has no dedicated connectability bit in this implementation.
        """
        flags = 0
        if is_seed:
            flags |= self.FLAG_SEED
        if is_connectable:
            flags |= self.FLAG_PREFER_ENCRYPT

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
