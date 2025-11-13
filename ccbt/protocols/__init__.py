"""Modern protocol support for ccBitTorrent.

Provides support for:
- WebTorrent (WebRTC-based)
- IPFS integration
- Protocol abstraction layer
- Multi-protocol support
"""

from __future__ import annotations

from ccbt.protocols.base import Protocol, ProtocolManager, ProtocolType
from ccbt.protocols.bittorrent import BitTorrentProtocol

try:
    from ccbt.protocols.ipfs import IPFSProtocol as _IPFSProtocol

    IPFSProtocol: type[Protocol] | None = _IPFSProtocol  # type: ignore[assignment]
except ImportError:
    IPFSProtocol = None  # type: ignore[assignment]  # IPFS support optional

# Import WebTorrentProtocol conditionally (may require aiortc)
try:
    # Import from the module file directly (not from package __init__)
    import ccbt.protocols.webtorrent as webtorrent_module

    WebTorrentProtocol = webtorrent_module.WebTorrentProtocol  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    WebTorrentProtocol = None  # type: ignore[assignment, misc]

__all__ = [
    "BitTorrentProtocol",
    "IPFSProtocol",
    "Protocol",
    "ProtocolManager",
    "ProtocolType",
    "WebTorrentProtocol",
]
