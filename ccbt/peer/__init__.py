"""Peer connection and management.

This module handles peer connections, both synchronous and asynchronous.
"""

from __future__ import annotations

# Submodule aliases so patch("ccbt.peer.<submodule>...") resolves on all platforms.
from ccbt.peer import async_peer_connection as async_peer_connection
from ccbt.peer import peer as peer
from ccbt.peer import ssl_peer as ssl_peer
from ccbt.peer import utp_peer as utp_peer
from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager
from ccbt.peer.connection_pool import PeerConnectionPool
from ccbt.peer.peer import Handshake
from ccbt.peer.peer_connection import PeerConnection

# Alias for backward compatibility
ConnectionPool = PeerConnectionPool

__all__ = [
    "AsyncPeerConnectionManager",
    "Handshake",
    "PeerConnection",
    "PeerConnectionPool",
]
