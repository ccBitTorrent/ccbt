"""Modern protocol support for ccBitTorrent.

from __future__ import annotations

Provides support for:
- WebTorrent (WebRTC-based)
- IPFS integration
- Protocol abstraction layer
- Multi-protocol support
"""

from ccbt.protocols.base import Protocol, ProtocolManager, ProtocolType
from ccbt.protocols.bittorrent import BitTorrentProtocol
from ccbt.protocols.ipfs import IPFSProtocol
from ccbt.protocols.webtorrent import WebTorrentProtocol

__all__ = [
    "BitTorrentProtocol",
    "IPFSProtocol",
    "Protocol",
    "ProtocolManager",
    "ProtocolType",
    "WebTorrentProtocol",
]
