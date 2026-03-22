"""Experimental peer TLS extension (BEP 10 extension protocol framing).

This is **not** BEP 47 (BEP 47 defines padding files and extended file attributes).
The client uses the LTEP/BEP-10 extension namespace to negotiate opportunistic
TLS **after** the BitTorrent handshake. This provides transport confidentiality
only when both peers cooperate; it does **not** authenticate peers or replace
MSE/PE (BEP 3) traffic obfuscation.

Provides support for:
- TLS negotiation after BitTorrent handshake
- Extension-protocol-framed upgrade messages
- Opportunistic encryption (config-gated)
"""

from __future__ import annotations

import asyncio
import struct
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Optional

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
    request_id: Optional[int] = None
    completion_event: Optional[asyncio.Event] = None


class SSLExtension:
    """Experimental peer TLS extension (BEP 10), not BEP 47 file attributes."""

    def __init__(self):
        """Initialize SSL Extension."""
        self.negotiation_states: dict[str, SSLNegotiationState] = {}
        self.request_counter = 0
        self._request_policy: Callable[[str], bool] | bool = True

    def set_request_policy(self, policy: Callable[[str], bool] | bool | None) -> None:
        """Configure how inbound SSL requests should be handled."""
        self._request_policy = True if policy is None else policy

    def _is_request_allowed(self, peer_id: str) -> bool:
        policy = self._request_policy
        if isinstance(policy, bool):
            return policy
        try:
            return bool(policy(peer_id))
        except Exception:
            return False

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
        # Update negotiation state and make it observable for outbound waiters.
        state = SSLNegotiationState(
            peer_id=peer_id,
            state="requested",
            completion_event=asyncio.Event(),
            timestamp=time.time(),
            request_id=request_id,
        )
        self.negotiation_states[peer_id] = state

        accepted = self._is_request_allowed(peer_id)
        state.state = "accepted" if accepted else "rejected"
        state.completion_event.set()
        response = (
            self.encode_accept(request_id)
            if accepted
            else self.encode_reject(request_id)
        )

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
        state = self.negotiation_states.get(peer_id)
        if state is None:
            state = SSLNegotiationState(
                peer_id=peer_id,
                state="accepted" if accepted else "rejected",
                timestamp=time.time(),
                request_id=request_id,
                completion_event=asyncio.Event(),
            )
            self.negotiation_states[peer_id] = state

        if state.request_id == request_id:
            state.state = "accepted" if accepted else "rejected"
            state.completion_event = state.completion_event or asyncio.Event()
            state.completion_event.set()

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

    def get_negotiation_state(self, peer_id: str) -> Optional[SSLNegotiationState]:
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
