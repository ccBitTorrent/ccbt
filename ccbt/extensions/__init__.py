"""BitTorrent protocol extensions.

Implements various BitTorrent protocol extensions including:
- Fast Extension (BEP 6)
- Extension Protocol (BEP 10)
- Peer Exchange (BEP 11)
- DHT (BEP 5)
- WebSeed (BEP 19)
- Compact Peer Lists (BEP 23)
"""

from .dht import DHTExtension
from .fast import FastExtension
from .pex import PeerExchange
from .protocol import ExtensionProtocol
from .webseed import WebSeedExtension

__all__ = [
    "DHTExtension",
    "ExtensionProtocol",
    "FastExtension",
    "PeerExchange",
    "WebSeedExtension",
]
