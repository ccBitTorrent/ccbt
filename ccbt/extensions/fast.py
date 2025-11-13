"""Fast Extension (BEP 6) implementation.

Provides support for:
- Suggest piece
- Have All
- Have None
- Reject Request
- Allow Fast
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from enum import IntEnum

from ccbt.utils.events import Event, EventType, emit_event


class FastMessageType(IntEnum):
    """Fast Extension message types."""

    SUGGEST = 0x0D
    HAVE_ALL = 0x0E
    HAVE_NONE = 0x0F
    REJECT = 0x10
    ALLOW_FAST = 0x11


@dataclass
class FastCapabilities:
    """Fast Extension capabilities."""

    suggest: bool = False
    have_all: bool = False
    have_none: bool = False
    reject: bool = False
    allow_fast: bool = False


class FastExtension:
    """Fast Extension implementation (BEP 6)."""

    def __init__(self):
        """Initialize Fast Extension."""
        self.capabilities = FastCapabilities()
        self.suggested_pieces: set[int] = set()
        self.allowed_fast: set[int] = set()
        self.rejected_requests: set[tuple[int, int, int]] = (
            set()
        )  # (index, begin, length)

    def supports_fast_extension(self, peer_capabilities: bytes) -> bool:
        """Check if peer supports Fast Extension."""
        # Fast Extension is indicated by bit 2 in the extension bits
        return len(peer_capabilities) >= 8 and (peer_capabilities[7] & 0x04) != 0

    def encode_handshake(self) -> bytes:
        """Encode Fast Extension handshake."""
        # Set Fast Extension bit (bit 2)
        extension_bits = 0x04
        return struct.pack("!Q", extension_bits)

    def decode_handshake(self, data: bytes) -> FastCapabilities:
        """Decode Fast Extension handshake."""
        if (
            len(data) < 8
        ):  # Tested in test_fast_coverage.py::TestFastExtensionCoverage::test_decode_handshake_short_data
            return FastCapabilities()

        extension_bits = struct.unpack("!Q", data[:8])[0]

        return FastCapabilities(
            suggest=(extension_bits & 0x01) != 0,
            have_all=(extension_bits & 0x02) != 0,
            have_none=(extension_bits & 0x04) != 0,
            reject=(extension_bits & 0x08) != 0,
            allow_fast=(extension_bits & 0x10) != 0,
        )

    def encode_suggest(self, piece_index: int) -> bytes:
        """Encode Suggest message."""
        return struct.pack("!BI", FastMessageType.SUGGEST, piece_index)

    def decode_suggest(self, data: bytes) -> int:
        """Decode Suggest message."""
        if len(data) < 5:
            msg = "Invalid Suggest message"
            raise ValueError(msg)

        message_type, piece_index = struct.unpack("!BI", data[:5])
        if (
            message_type != FastMessageType.SUGGEST
        ):  # Tested in test_fast_coverage.py::TestFastExtensionCoverage::test_decode_suggest_invalid_message_type
            msg = "Invalid message type for Suggest"
            raise ValueError(msg)

        return piece_index

    def encode_have_all(self) -> bytes:
        """Encode Have All message."""
        return struct.pack("!B", FastMessageType.HAVE_ALL)

    def decode_have_all(self, data: bytes) -> bool:
        """Decode Have All message."""
        if (
            len(data) < 1
        ):  # Tested in test_fast_coverage.py::TestFastExtensionCoverage::test_decode_have_all_short_data
            return False

        return data[0] == FastMessageType.HAVE_ALL

    def encode_have_none(self) -> bytes:
        """Encode Have None message."""
        return struct.pack("!B", FastMessageType.HAVE_NONE)

    def decode_have_none(self, data: bytes) -> bool:
        """Decode Have None message."""
        if (
            len(data) < 1
        ):  # Tested in test_fast_coverage.py::TestFastExtensionCoverage::test_decode_have_none_short_data
            return False

        return data[0] == FastMessageType.HAVE_NONE

    def encode_reject(self, index: int, begin: int, length: int) -> bytes:
        """Encode Reject message."""
        return struct.pack("!BIII", FastMessageType.REJECT, index, begin, length)

    def decode_reject(self, data: bytes) -> tuple[int, int, int]:
        """Decode Reject message."""
        if len(data) < 13:
            msg = "Invalid Reject message"
            raise ValueError(msg)

        message_type, index, begin, length = struct.unpack("!BIII", data[:13])
        if (
            message_type != FastMessageType.REJECT
        ):  # Tested in test_fast_coverage.py::TestFastExtensionCoverage::test_decode_reject_invalid_message_type
            msg = "Invalid message type for Reject"
            raise ValueError(msg)

        return index, begin, length

    def encode_allow_fast(self, piece_index: int) -> bytes:
        """Encode Allow Fast message."""
        return struct.pack("!BI", FastMessageType.ALLOW_FAST, piece_index)

    def decode_allow_fast(self, data: bytes) -> int:
        """Decode Allow Fast message."""
        if (
            len(data) < 5
        ):  # Tested in test_fast_coverage.py::TestFastExtensionCoverage::test_decode_allow_fast_short_data
            msg = "Invalid Allow Fast message"
            raise ValueError(msg)

        message_type, piece_index = struct.unpack("!BI", data[:5])
        if (
            message_type != FastMessageType.ALLOW_FAST
        ):  # Tested in test_fast_coverage.py::TestFastExtensionCoverage::test_decode_allow_fast_invalid_message_type
            msg = "Invalid message type for Allow Fast"
            raise ValueError(msg)

        return piece_index

    async def handle_suggest(self, peer_id: str, piece_index: int) -> None:
        """Handle Suggest message from peer."""
        self.suggested_pieces.add(piece_index)

        # Emit event for piece suggestion
        await emit_event(
            Event(
                event_type=EventType.PIECE_SUGGESTED.value,
                data={
                    "peer_id": peer_id,
                    "piece_index": piece_index,
                    "timestamp": time.time(),
                },
            ),
        )

    async def handle_have_all(self, peer_id: str) -> None:
        """Handle Have All message from peer."""
        # Emit event for have all
        await emit_event(
            Event(
                event_type=EventType.PEER_HAVE_ALL.value,
                data={
                    "peer_id": peer_id,
                    "timestamp": time.time(),
                },
            ),
        )

    async def handle_have_none(self, peer_id: str) -> None:
        """Handle Have None message from peer."""
        # Emit event for have none
        await emit_event(
            Event(
                event_type=EventType.PEER_HAVE_NONE.value,
                data={
                    "peer_id": peer_id,
                    "timestamp": time.time(),
                },
            ),
        )

    async def handle_reject(
        self,
        peer_id: str,
        index: int,
        begin: int,
        length: int,
    ) -> None:
        """Handle Reject message from peer."""
        self.rejected_requests.add((index, begin, length))

        # Emit event for request rejection
        await emit_event(
            Event(
                event_type=EventType.REQUEST_REJECTED.value,
                data={
                    "peer_id": peer_id,
                    "index": index,
                    "begin": begin,
                    "length": length,
                    "timestamp": time.time(),
                },
            ),
        )

    async def handle_allow_fast(self, peer_id: str, piece_index: int) -> None:
        """Handle Allow Fast message from peer."""
        self.allowed_fast.add(piece_index)

        # Emit event for allow fast
        await emit_event(
            Event(
                event_type=EventType.PIECE_ALLOWED_FAST.value,
                data={
                    "peer_id": peer_id,
                    "piece_index": piece_index,
                    "timestamp": time.time(),
                },
            ),
        )

    def get_suggested_pieces(self) -> set[int]:
        """Get set of suggested pieces."""
        return self.suggested_pieces.copy()

    def get_allowed_fast_pieces(self) -> set[int]:
        """Get set of allowed fast pieces."""
        return self.allowed_fast.copy()

    def get_rejected_requests(self) -> set[tuple[int, int, int]]:
        """Get set of rejected requests."""
        return self.rejected_requests.copy()

    def clear_suggestions(self) -> None:
        """Clear all suggestions."""
        self.suggested_pieces.clear()

    def clear_allowed_fast(self) -> None:
        """Clear all allowed fast pieces."""
        self.allowed_fast.clear()

    def clear_rejected_requests(self) -> None:
        """Clear all rejected requests."""
        self.rejected_requests.clear()

    def is_piece_allowed_fast(self, piece_index: int) -> bool:
        """Check if piece is allowed for fast download."""
        return piece_index in self.allowed_fast

    def is_request_rejected(self, index: int, begin: int, length: int) -> bool:
        """Check if request was rejected."""
        return (index, begin, length) in self.rejected_requests

    def get_capabilities(self) -> FastCapabilities:
        """Get current capabilities."""
        return self.capabilities

    def set_capabilities(self, capabilities: FastCapabilities) -> None:
        """Set capabilities."""
        self.capabilities = capabilities
