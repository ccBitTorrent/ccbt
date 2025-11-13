"""Async peer connection management for BitTorrent client.

This module handles establishing TCP connections to peers, exchanging handshakes,
managing bitfields, and coordinating peer communication using asyncio.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    import asyncio

    from ccbt.security.encrypted_stream import (
        EncryptedStreamReader,
        EncryptedStreamWriter,
    )

from ccbt.peer.peer import (
    MessageDecoder,
    PeerInfo,
    PeerState,
)


class ConnectionState(Enum):
    """States of a peer connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    HANDSHAKE_SENT = "handshake_sent"
    HANDSHAKE_RECEIVED = "handshake_received"
    CONNECTED = "connected"
    BITFIELD_SENT = "bitfield_sent"
    BITFIELD_RECEIVED = "bitfield_received"
    ACTIVE = "active"
    CHOKED = "choked"
    ERROR = "error"


class PeerConnectionError(Exception):
    """Exception raised when peer connection fails."""


@dataclass
class PeerConnection:
    """Represents an async connection to a single peer."""

    peer_info: PeerInfo
    torrent_data: dict[str, Any]
    reader: asyncio.StreamReader | EncryptedStreamReader | None = None
    writer: asyncio.StreamWriter | EncryptedStreamWriter | None = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    peer_state: PeerState = field(default_factory=PeerState)
    message_decoder: MessageDecoder = field(default_factory=MessageDecoder)
    last_activity: float = field(default_factory=time.time)
    connection_task: asyncio.Task | None = None
    error_message: str | None = None

    # Encryption support
    is_encrypted: bool = False
    encryption_cipher: Any = None  # CipherSuite instance from MSE handshake

    def __str__(
        self,
    ):  # pragma: no cover - String representation for debugging, tested implicitly via logging/errors
        """Return string representation of peer connection."""
        return f"PeerConnection({self.peer_info}, state={self.state.value})"

    def is_connected(self) -> bool:
        """Check if connection is established."""
        return self.state in [
            ConnectionState.CONNECTED,
            ConnectionState.BITFIELD_SENT,
            ConnectionState.BITFIELD_RECEIVED,
            ConnectionState.ACTIVE,
            ConnectionState.CHOKED,
        ]

    def is_active(self) -> bool:
        """Check if connection is fully active (handshake and bitfield exchanged)."""
        return self.state in [ConnectionState.ACTIVE, ConnectionState.CHOKED]

    def has_timed_out(self, timeout: float = 30.0) -> bool:
        """Check if connection has timed out due to inactivity."""
        return time.time() - self.last_activity > timeout
