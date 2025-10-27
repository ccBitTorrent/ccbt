"""Compact Peer Lists implementation (BEP 23).

Provides support for:
- Compact peer format
- IPv6 compact format
- Optimized peer list parsing
"""

import socket
import struct
from dataclasses import dataclass
from typing import List, Tuple

from ..models import PeerInfo


@dataclass
class CompactPeer:
    """Compact peer representation."""
    ip: str
    port: int
    is_ipv6: bool = False

    def to_peer_info(self) -> PeerInfo:
        """Convert to PeerInfo."""
        return PeerInfo(ip=self.ip, port=self.port)

    @classmethod
    def from_peer_info(cls, peer_info: PeerInfo) -> "CompactPeer":
        """Create from PeerInfo."""
        is_ipv6 = ":" in peer_info.ip  # Simple IPv6 detection
        return cls(ip=peer_info.ip, port=peer_info.port, is_ipv6=is_ipv6)


class CompactPeerLists:
    """Compact Peer Lists implementation (BEP 23)."""

    @staticmethod
    def encode_peer(peer: CompactPeer) -> bytes:
        """Encode single peer in compact format."""
        try:
            if peer.is_ipv6:
                # IPv6 format: 16 bytes IP + 2 bytes port
                ip_bytes = socket.inet_pton(socket.AF_INET6, peer.ip)
                return struct.pack("!16sH", ip_bytes, peer.port)
            # IPv4 format: 4 bytes IP + 2 bytes port
            ip_bytes = socket.inet_aton(peer.ip)
            return struct.pack("!4sH", ip_bytes, peer.port)
        except (OSError, ValueError):
            raise ValueError(f"Invalid IP address: {peer.ip}")

    @staticmethod
    def decode_peer(data: bytes, is_ipv6: bool = False) -> CompactPeer:
        """Decode single peer from compact format."""
        if is_ipv6:
            if len(data) < 18:  # 16 bytes IP + 2 bytes port
                raise ValueError("Invalid IPv6 compact peer format")

            ip_bytes, port = struct.unpack("!16sH", data[:18])
            ip = socket.inet_ntop(socket.AF_INET6, ip_bytes)
            return CompactPeer(ip=ip, port=port, is_ipv6=True)
        if len(data) < 6:  # 4 bytes IP + 2 bytes port
            raise ValueError("Invalid IPv4 compact peer format")

        ip_bytes, port = struct.unpack("!4sH", data[:6])
        ip = socket.inet_ntop(socket.AF_INET, ip_bytes)
        return CompactPeer(ip=ip, port=port, is_ipv6=False)

    @staticmethod
    def encode_peers_list(peers: List[CompactPeer]) -> bytes:
        """Encode list of peers in compact format."""
        if not peers:
            return b""

        # Check if all peers are IPv6
        is_ipv6 = all(peer.is_ipv6 for peer in peers)

        peer_data = b""
        for peer in peers:
            peer_data += CompactPeerLists.encode_peer(peer)

        return peer_data

    @staticmethod
    def decode_peers_list(data: bytes, is_ipv6: bool = False) -> List[CompactPeer]:
        """Decode list of peers from compact format."""
        peers = []

        if is_ipv6:
            peer_size = 18  # 16 bytes IP + 2 bytes port
        else:
            peer_size = 6   # 4 bytes IP + 2 bytes port

        for i in range(0, len(data), peer_size):
            if i + peer_size <= len(data):
                try:
                    peer = CompactPeerLists.decode_peer(data[i:i + peer_size], is_ipv6)
                    peers.append(peer)
                except ValueError:
                    # Skip invalid peer data
                    continue

        return peers

    @staticmethod
    def encode_peers_dict(peers: List[CompactPeer]) -> dict:
        """Encode peers as dictionary with compact format."""
        if not peers:
            return {"peers": b"", "peers6": b""}

        # Separate IPv4 and IPv6 peers
        ipv4_peers = [peer for peer in peers if not peer.is_ipv6]
        ipv6_peers = [peer for peer in peers if peer.is_ipv6]

        result = {}

        if ipv4_peers:
            result["peers"] = CompactPeerLists.encode_peers_list(ipv4_peers)

        if ipv6_peers:
            result["peers6"] = CompactPeerLists.encode_peers_list(ipv6_peers)

        return result

    @staticmethod
    def decode_peers_dict(data: dict) -> List[CompactPeer]:
        """Decode peers from dictionary with compact format."""
        peers = []

        # Decode IPv4 peers
        if "peers" in data and isinstance(data["peers"], bytes):
            ipv4_peers = CompactPeerLists.decode_peers_list(data["peers"], is_ipv6=False)
            peers.extend(ipv4_peers)

        # Decode IPv6 peers
        if "peers6" in data and isinstance(data["peers6"], bytes):
            ipv6_peers = CompactPeerLists.decode_peers_list(data["peers6"], is_ipv6=True)
            peers.extend(ipv6_peers)

        return peers

    @staticmethod
    def convert_peer_info_to_compact(peer_info: PeerInfo) -> CompactPeer:
        """Convert PeerInfo to CompactPeer."""
        is_ipv6 = ":" in peer_info.ip  # Simple IPv6 detection
        return CompactPeer(ip=peer_info.ip, port=peer_info.port, is_ipv6=is_ipv6)

    @staticmethod
    def convert_compact_to_peer_info(peer: CompactPeer) -> PeerInfo:
        """Convert CompactPeer to PeerInfo."""
        return peer.to_peer_info()

    @staticmethod
    def convert_peer_info_list_to_compact(peer_infos: List[PeerInfo]) -> List[CompactPeer]:
        """Convert list of PeerInfo to list of CompactPeer."""
        return [CompactPeerLists.convert_peer_info_to_compact(peer_info) for peer_info in peer_infos]

    @staticmethod
    def convert_compact_list_to_peer_info(peers: List[CompactPeer]) -> List[PeerInfo]:
        """Convert list of CompactPeer to list of PeerInfo."""
        return [peer.to_peer_info() for peer in peers]

    @staticmethod
    def get_peer_size(is_ipv6: bool = False) -> int:
        """Get size of single peer in compact format."""
        return 18 if is_ipv6 else 6

    @staticmethod
    def estimate_peers_list_size(peers: List[CompactPeer]) -> int:
        """Estimate size of peers list in compact format."""
        if not peers:
            return 0

        # Check if all peers are IPv6
        is_ipv6 = all(peer.is_ipv6 for peer in peers)
        peer_size = CompactPeerLists.get_peer_size(is_ipv6)

        return len(peers) * peer_size

    @staticmethod
    def split_peers_by_ip_version(peers: List[CompactPeer]) -> Tuple[List[CompactPeer], List[CompactPeer]]:
        """Split peers by IP version."""
        ipv4_peers = [peer for peer in peers if not peer.is_ipv6]
        ipv6_peers = [peer for peer in peers if peer.is_ipv6]

        return ipv4_peers, ipv6_peers

    @staticmethod
    def merge_peers_lists(peers1: List[CompactPeer], peers2: List[CompactPeer]) -> List[CompactPeer]:
        """Merge two peer lists, removing duplicates."""
        peer_set = set()
        merged_peers = []

        for peer in peers1 + peers2:
            peer_key = (peer.ip, peer.port, peer.is_ipv6)
            if peer_key not in peer_set:
                peer_set.add(peer_key)
                merged_peers.append(peer)

        return merged_peers

    @staticmethod
    def filter_peers_by_ip_version(peers: List[CompactPeer], ipv6_only: bool = False) -> List[CompactPeer]:
        """Filter peers by IP version."""
        if ipv6_only:
            return [peer for peer in peers if peer.is_ipv6]
        return [peer for peer in peers if not peer.is_ipv6]

    @staticmethod
    def validate_peer_data(data: bytes, is_ipv6: bool = False) -> bool:
        """Validate peer data format."""
        if is_ipv6:
            return len(data) >= 18 and len(data) % 18 == 0
        return len(data) >= 6 and len(data) % 6 == 0

    @staticmethod
    def get_peer_count(data: bytes, is_ipv6: bool = False) -> int:
        """Get number of peers in compact data."""
        if not CompactPeerLists.validate_peer_data(data, is_ipv6):
            return 0

        peer_size = CompactPeerLists.get_peer_size(is_ipv6)
        return len(data) // peer_size
