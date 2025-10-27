"""Modern protocol support for ccBitTorrent.

Provides support for:
- WebTorrent (WebRTC-based)
- IPFS integration
- Protocol abstraction layer
- Multi-protocol support
"""

from .base import Protocol, ProtocolManager, ProtocolType
from .bittorrent import BitTorrentProtocol
from .ipfs import IPFSProtocol
from .webtorrent import WebTorrentProtocol

__all__ = [
    "BitTorrentProtocol",
    "IPFSProtocol",
    "Protocol",
    "ProtocolManager",
    "ProtocolType",
    "WebTorrentProtocol",
]
