"""SSL/TLS Extension Protocol (BEP 47) implementation.

Provides support for:
- SSL/TLS negotiation after BitTorrent handshake
- Extension protocol-based SSL upgrade
- Opportunistic encryption
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ccbt.utils.events import Event, EventType, emit_event


class SSLMessageType(IntEnum):
    """SSL Extension message types."""

    REQUEST = 0x01  # Request SSL upgrade
    RESPONSE = 0x02  # Response to SSL request
    ACCEPT = 0x03  # Accept SSL upgrade
    REJECT = 0x04  # Reject SSL upgrade


@dataclass
class SSLNegotiationState:
    """SSL negotiation state for a peer."""

    peer_id: str
    state: str  # "idle", "requested", "accepted", "rejected"
    timestamp: float
    request_id: int | None = None


class SSLExtension:
    """SSL/TLS Extension implementation (BEP 47)."""

    def __init__(self):
        """Initialize SSL Extension."""
        self.negotiation_states: dict[str, SSLNegotiationState] = {}
        self.request_counter = 0

    def encode_handshake(self) -> dict[str, Any]:
        """Encode SSL extension handshake data.

        Returns:
            Dictionary containing SSL extension capabilities

        """
        return {
            "ssl": {
                "version": "1.0",
                "supports_ssl": True,
            }
        }

    def decode_handshake(self, data: dict[str, Any]) -> bool:
        """Decode SSL extension handshake data.

        Args:
            data: Extension handshake data dictionary

        Returns:
            True if peer supports SSL extension

        """
        ssl_data = data.get("ssl", {})
        if isinstance(ssl_data, dict):
            return ssl_data.get("supports_ssl", False)
        return False

    def encode_request(self) -> bytes:
        """Encode SSL upgrade request message.

        Returns:
            Encoded request message

        """
        self.request_counter += 1
        request_id = self.request_counter
        # Pack: <message_type><request_id>
        return struct.pack("!BI", SSLMessageType.REQUEST, request_id)

    def decode_request(self, data: bytes) -> int:
        """Decode SSL upgrade request message.

        Args:
            data: Encoded request message

        Returns:
            Request ID

        Raises:
            ValueError: If message is invalid

        """
        if len(data) < 5:
            msg = "Invalid SSL request message"
            raise ValueError(msg)

        message_type, request_id = struct.unpack("!BI", data[:5])
        if message_type != SSLMessageType.REQUEST:
            msg = "Invalid message type for SSL request"
            raise ValueError(msg)

        return request_id

    def encode_accept(self, request_id: int) -> bytes:
        """Encode SSL upgrade accept message.

        Args:
            request_id: Request ID to accept

        Returns:
            Encoded accept message

        """
        # Pack: <message_type><request_id>
        return struct.pack("!BI", SSLMessageType.ACCEPT, request_id)

    def decode_accept(self, data: bytes) -> int:
        """Decode SSL upgrade accept message.

        Args:
            data: Encoded accept message

        Returns:
            Request ID

        Raises:
            ValueError: If message is invalid

        """
        if len(data) < 5:
            msg = "Invalid SSL accept message"
            raise ValueError(msg)

        message_type, request_id = struct.unpack("!BI", data[:5])
        if message_type != SSLMessageType.ACCEPT:
            msg = "Invalid message type for SSL accept"
            raise ValueError(msg)

        return request_id

    def encode_reject(self, request_id: int) -> bytes:
        """Encode SSL upgrade reject message.

        Args:
            request_id: Request ID to reject

        Returns:
            Encoded reject message

        """
        # Pack: <message_type><request_id>
        return struct.pack("!BI", SSLMessageType.REJECT, request_id)

    def decode_reject(self, data: bytes) -> int:
        """Decode SSL upgrade reject message.

        Args:
            data: Encoded reject message

        Returns:
            Request ID

        Raises:
            ValueError: If message is invalid

        """
        if len(data) < 5:
            msg = "Invalid SSL reject message"
            raise ValueError(msg)

        message_type, request_id = struct.unpack("!BI", data[:5])
        if message_type != SSLMessageType.REJECT:
            msg = "Invalid message type for SSL reject"
            raise ValueError(msg)

        return request_id

    def encode_response(self, request_id: int, accepted: bool) -> bytes:
        """Encode SSL upgrade response message.

        Args:
            request_id: Request ID to respond to
            accepted: Whether SSL upgrade is accepted

        Returns:
            Encoded response message

        """
        message_type = SSLMessageType.ACCEPT if accepted else SSLMessageType.REJECT
        # Pack: <message_type><request_id>
        return struct.pack("!BI", message_type, request_id)

    def decode_response(self, data: bytes) -> tuple[int, bool]:
        """Decode SSL upgrade response message.

        Args:
            data: Encoded response message

        Returns:
            Tuple of (request_id, accepted)

        Raises:
            ValueError: If message is invalid

        """
        if len(data) < 5:
            msg = "Invalid SSL response message"
            raise ValueError(msg)

        message_type, request_id = struct.unpack("!BI", data[:5])
        if message_type not in (SSLMessageType.ACCEPT, SSLMessageType.REJECT):
            msg = "Invalid message type for SSL response"
            raise ValueError(msg)

        accepted = message_type == SSLMessageType.ACCEPT
        return request_id, accepted

    async def handle_request(self, peer_id: str, request_id: int) -> bytes:
        """Handle SSL upgrade request from peer.

        Args:
            peer_id: Peer identifier
            request_id: Request ID

        Returns:
            Response message (accept or reject)

        """
        # Update negotiation state
        self.negotiation_states[peer_id] = SSLNegotiationState(
            peer_id=peer_id,
            state="requested",
            timestamp=time.time(),
            request_id=request_id,
        )

        # For now, always accept (can be configured later)
        # TODO: Add configuration option to accept/reject based on settings
        accepted = True

        if accepted:
            self.negotiation_states[peer_id].state = "accepted"
            response = self.encode_accept(request_id)
        else:  # pragma: no cover - Unreachable: accepted is hardcoded to True (TODO: make configurable)
            self.negotiation_states[peer_id].state = "rejected"
            response = self.encode_reject(request_id)

        # Emit event
        await emit_event(
            Event(
                event_type=EventType.SSL_NEGOTIATION.value,
                data={
                    "peer_id": peer_id,
                    "request_id": request_id,
                    "accepted": accepted,
                    "timestamp": time.time(),
                },
            ),
        )

        return response

    async def handle_response(
        self, peer_id: str, request_id: int, accepted: bool
    ) -> None:
        """Handle SSL upgrade response from peer.

        Args:
            peer_id: Peer identifier
            request_id: Request ID
            accepted: Whether SSL upgrade was accepted

        """
        if peer_id in self.negotiation_states:
            state = self.negotiation_states[peer_id]
            if state.request_id == request_id:
                state.state = "accepted" if accepted else "rejected"

        # Emit event
        await emit_event(
            Event(
                event_type=EventType.SSL_NEGOTIATION.value,
                data={
                    "peer_id": peer_id,
                    "request_id": request_id,
                    "accepted": accepted,
                    "timestamp": time.time(),
                },
            ),
        )

    def get_negotiation_state(self, peer_id: str) -> SSLNegotiationState | None:
        """Get SSL negotiation state for peer.

        Args:
            peer_id: Peer identifier

        Returns:
            Negotiation state or None

        """
        return self.negotiation_states.get(peer_id)

    def clear_negotiation_state(self, peer_id: str) -> None:
        """Clear SSL negotiation state for peer.

        Args:
            peer_id: Peer identifier

        """
        if peer_id in self.negotiation_states:
            del self.negotiation_states[peer_id]

    def get_capabilities(self) -> dict[str, Any]:
        """Get SSL extension capabilities.

        Returns:
            Capabilities dictionary

        """
        return {
            "supports_ssl": True,
            "version": "1.0",
            "active_negotiations": len(
                [
                    s
                    for s in self.negotiation_states.values()
                    if s.state in ("requested", "accepted")
                ]
            ),
        }
