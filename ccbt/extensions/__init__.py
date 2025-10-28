"""BitTorrent protocol extensions.

from __future__ import annotations

Implements various BitTorrent protocol extensions including:
- Fast Extension (BEP 6)
- Extension Protocol (BEP 10)
- Peer Exchange (BEP 11)
- DHT (BEP 5)
- WebSeed (BEP 19)
- Compact Peer Lists (BEP 23)
"""

from ccbt.extensions.dht import DHTExtension
from ccbt.extensions.fast import FastExtension
from ccbt.extensions.pex import PeerExchange
from ccbt.extensions.protocol import ExtensionProtocol
from ccbt.extensions.webseed import WebSeedExtension

__all__ = [
    "DHTExtension",
    "ExtensionProtocol",
    "FastExtension",
    "PeerExchange",
    "WebSeedExtension",
]
