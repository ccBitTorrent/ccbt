"""Peer connection and management.

This module handles peer connections, both synchronous and asynchronous.
"""

from __future__ import annotations

from ccbt.peer import async_peer_connection, connection_pool, peer, ssl_peer, utp_peer
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
    "async_peer_connection",
    "connection_pool",
    "peer",
    "ssl_peer",
    "utp_peer",
]
