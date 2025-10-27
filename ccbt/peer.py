"""High-performance peer protocol implementation for BitTorrent client.

This module handles the peer-to-peer protocol including handshakes,
message encoding/decoding, and peer state management with optimizations
for memory efficiency, zero-copy operations, and object reuse.
"""

import logging
import socket
import struct
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .config import get_config
from .exceptions import HandshakeError, MessageError
from .models import MessageType
from .models import PeerInfo as PeerInfoModel

# MessageType is now imported from models.py


class PeerState:
    """Tracks the state of a peer connection."""

    def __init__(self) -> None:
        self.am_choking: bool = True      # We are choking the peer
        self.am_interested: bool = False  # We are interested in the peer
        self.peer_choking: bool = True    # Peer is choking us
        self.peer_interested: bool = False # Peer is interested in us
        self.bitfield: Optional[bytes] = None        # Peer's bitfield (which pieces they have)
        self.pieces_we_have: Set[int] = set() # Pieces we have downloaded

    def __str__(self) -> str:
        return (f"PeerState(choking={self.am_choking}, "
                f"interested={self.am_interested}, "
                f"peer_choking={self.peer_choking}, "
                f"peer_interested={self.peer_interested})")

# HandshakeError and MessageError are now imported from exceptions.py


# PeerInfo is now imported from models.py as PeerInfoModel
# Keep backward compatibility
PeerInfo = PeerInfoModel


class Handshake:
    """BitTorrent handshake message."""

    PROTOCOL_STRING: bytes = b"BitTorrent protocol"
    RESERVED_BYTES: bytes = b"\x00" * 8  # 8 reserved bytes, all zero

    def __init__(self, info_hash: bytes, peer_id: bytes) -> None:
        """Initialize handshake.

        Args:
            info_hash: 20-byte SHA-1 hash of info dictionary
            peer_id: 20-byte peer ID
        """
        if len(info_hash) != 20:
            raise HandshakeError(f"Info hash must be 20 bytes, got {len(info_hash)}")
        if len(peer_id) != 20:
            raise HandshakeError(f"Peer ID must be 20 bytes, got {len(peer_id)}")

        self.info_hash: bytes = info_hash
        self.peer_id: bytes = peer_id

    def encode(self) -> bytes:
        """Encode handshake to bytes.

        Format: <protocol len><protocol><reserved><info_hash><peer_id>
        Total: 1 + 19 + 8 + 20 + 20 = 68 bytes
        """
        protocol_len = len(self.PROTOCOL_STRING)
        return (struct.pack("B", protocol_len) +
                self.PROTOCOL_STRING +
                self.RESERVED_BYTES +
                self.info_hash +
                self.peer_id)

    @classmethod
    def decode(cls, data: bytes) -> "Handshake":
        """Decode handshake from bytes.

        Args:
            data: Raw handshake data (68 bytes)

        Returns:
            Handshake object

        Raises:
            HandshakeError: If data is invalid
        """
        if len(data) != 68:
            raise HandshakeError(f"Handshake must be 68 bytes, got {len(data)}")

        # Parse protocol length and string
        protocol_len = struct.unpack("B", data[0:1])[0]
        if protocol_len != 19:
            raise HandshakeError(f"Invalid protocol length: {protocol_len}")

        protocol_string = data[1:20]
        if protocol_string != cls.PROTOCOL_STRING:
            raise HandshakeError(f"Invalid protocol string: {protocol_string}")

        # Parse reserved bytes
        reserved = data[20:28]
        if reserved != cls.RESERVED_BYTES:
            # For now we require all reserved bytes to be zero
            # In the future we might support extensions
            pass

        # Parse info hash and peer ID
        info_hash = data[28:48]
        peer_id = data[48:68]

        return cls(info_hash, peer_id)

    @classmethod
    def from_parts(cls, protocol_len: int, protocol: bytes,
                   reserved: bytes, info_hash: bytes, peer_id: bytes) -> "Handshake":
        """Create handshake from individual components."""
        # Validate components
        if len(protocol) != protocol_len:
            raise HandshakeError(f"Protocol length mismatch: expected {protocol_len}, got {len(protocol)}")
        if len(reserved) != 8:
            raise HandshakeError(f"Reserved must be 8 bytes, got {len(reserved)}")

        return cls(info_hash, peer_id)


class PeerMessage:
    """Base class for peer messages."""

    def __init__(self, message_id: int):
        self.message_id = message_id

    def encode(self) -> bytes:
        """Encode message to bytes."""
        raise NotImplementedError

    @classmethod
    def decode(cls, data: bytes) -> "PeerMessage":
        """Decode message from bytes."""
        raise NotImplementedError


class KeepAliveMessage(PeerMessage):
    """Keep-alive message (length = 0)."""

    def __init__(self):
        super().__init__(-1)  # Keep-alive doesn't have a message ID

    def encode(self) -> bytes:
        """Encode keep-alive message."""
        return struct.pack("!I", 0)  # 4-byte length = 0

    @classmethod
    def decode(cls, data: bytes) -> "KeepAliveMessage":
        """Decode keep-alive message."""
        if len(data) != 4:
            raise MessageError(f"Keep-alive must be 4 bytes, got {len(data)}")
        length = struct.unpack("!I", data)[0]
        if length != 0:
            raise MessageError(f"Keep-alive length must be 0, got {length}")
        return cls()


class ChokeMessage(PeerMessage):
    """Choke message."""

    def __init__(self):
        super().__init__(MessageType.CHOKE)

    def encode(self) -> bytes:
        """Encode choke message."""
        return struct.pack("!I", 1) + struct.pack("B", self.message_id)

    @classmethod
    def decode(cls, data: bytes) -> "ChokeMessage":
        """Decode choke message."""
        if len(data) != 5:
            raise MessageError(f"Choke message must be 5 bytes, got {len(data)}")
        length, message_id = struct.unpack("!IB", data)
        if length != 1:
            raise MessageError(f"Choke message length must be 1, got {length}")
        if message_id != MessageType.CHOKE:
            raise MessageError(f"Expected choke message ID {MessageType.CHOKE}, got {message_id}")
        return cls()


class UnchokeMessage(PeerMessage):
    """Unchoke message."""

    def __init__(self):
        super().__init__(MessageType.UNCHOKE)

    def encode(self) -> bytes:
        """Encode unchoke message."""
        return struct.pack("!I", 1) + struct.pack("B", self.message_id)

    @classmethod
    def decode(cls, data: bytes) -> "UnchokeMessage":
        """Decode unchoke message."""
        if len(data) != 5:
            raise MessageError(f"Unchoke message must be 5 bytes, got {len(data)}")
        length, message_id = struct.unpack("!IB", data)
        if length != 1:
            raise MessageError(f"Unchoke message length must be 1, got {length}")
        if message_id != MessageType.UNCHOKE:
            raise MessageError(f"Expected unchoke message ID {MessageType.UNCHOKE}, got {message_id}")
        return cls()


class InterestedMessage(PeerMessage):
    """Interested message."""

    def __init__(self):
        super().__init__(MessageType.INTERESTED)

    def encode(self) -> bytes:
        """Encode interested message."""
        return struct.pack("!I", 1) + struct.pack("B", self.message_id)

    @classmethod
    def decode(cls, data: bytes) -> "InterestedMessage":
        """Decode interested message."""
        if len(data) != 5:
            raise MessageError(f"Interested message must be 5 bytes, got {len(data)}")
        length, message_id = struct.unpack("!IB", data)
        if length != 1:
            raise MessageError(f"Interested message length must be 1, got {length}")
        if message_id != MessageType.INTERESTED:
            raise MessageError(f"Expected interested message ID {MessageType.INTERESTED}, got {message_id}")
        return cls()


class NotInterestedMessage(PeerMessage):
    """Not interested message."""

    def __init__(self):
        super().__init__(MessageType.NOT_INTERESTED)

    def encode(self) -> bytes:
        """Encode not interested message."""
        return struct.pack("!I", 1) + struct.pack("B", self.message_id)

    @classmethod
    def decode(cls, data: bytes) -> "NotInterestedMessage":
        """Decode not interested message."""
        if len(data) != 5:
            raise MessageError(f"Not interested message must be 5 bytes, got {len(data)}")
        length, message_id = struct.unpack("!IB", data)
        if length != 1:
            raise MessageError(f"Not interested message length must be 1, got {length}")
        if message_id != MessageType.NOT_INTERESTED:
            raise MessageError(f"Expected not interested message ID {MessageType.NOT_INTERESTED}, got {message_id}")
        return cls()


class HaveMessage(PeerMessage):
    """Have message (announces that peer has a piece)."""

    def __init__(self, piece_index: int):
        """Initialize have message.

        Args:
            piece_index: Index of the piece the peer now has
        """
        super().__init__(MessageType.HAVE)
        self.piece_index = piece_index

    def encode(self) -> bytes:
        """Encode have message."""
        return (struct.pack("!I", 5) +  # length = 5 (1 byte ID + 4 bytes piece index)
                struct.pack("B", self.message_id) +
                struct.pack("!I", self.piece_index))

    @classmethod
    def decode(cls, data: bytes) -> "HaveMessage":
        """Decode have message."""
        if len(data) != 9:
            raise MessageError(f"Have message must be 9 bytes, got {len(data)}")
        length, message_id, piece_index = struct.unpack("!IBI", data)
        if length != 5:
            raise MessageError(f"Have message length must be 5, got {length}")
        if message_id != MessageType.HAVE:
            raise MessageError(f"Expected have message ID {MessageType.HAVE}, got {message_id}")
        return cls(piece_index)


class BitfieldMessage(PeerMessage):
    """Bitfield message (shows which pieces the peer has)."""

    def __init__(self, bitfield: bytes):
        """Initialize bitfield message.

        Args:
            bitfield: Bitfield bytes where each bit represents a piece
        """
        super().__init__(MessageType.BITFIELD)
        self.bitfield = bitfield

    def encode(self) -> bytes:
        """Encode bitfield message."""
        length = 1 + len(self.bitfield)  # 1 byte ID + bitfield
        return (struct.pack("!I", length) +
                struct.pack("B", self.message_id) +
                self.bitfield)

    @classmethod
    def decode(cls, data: bytes) -> "BitfieldMessage":
        """Decode bitfield message."""
        if len(data) < 5:
            raise MessageError(f"Bitfield message too short: {len(data)} bytes")

        length, message_id = struct.unpack("!IB", data[:5])
        if length < 1:
            raise MessageError(f"Bitfield message length too small: {length}")

        expected_length = 4 + length  # 4 bytes length + length field value
        if len(data) != expected_length:
            raise MessageError(f"Bitfield message length mismatch: expected {expected_length}, got {len(data)}")

        if message_id != MessageType.BITFIELD:
            raise MessageError(f"Expected bitfield message ID {MessageType.BITFIELD}, got {message_id}")

        bitfield = data[5:]
        return cls(bitfield)

    def has_piece(self, piece_index: int, num_pieces: int) -> bool:
        """Check if peer has a specific piece.

        Args:
            piece_index: Index of piece to check
            num_pieces: Total number of pieces

        Returns:
            True if peer has the piece
        """
        if piece_index < 0 or piece_index >= num_pieces:
            return False

        # Calculate byte and bit position
        byte_index = piece_index // 8
        bit_index = piece_index % 8

        if byte_index >= len(self.bitfield):
            return False

        # Check if bit is set (1 = has piece, 0 = doesn't have piece)
        return bool(self.bitfield[byte_index] & (1 << (7 - bit_index)))


class RequestMessage(PeerMessage):
    """Request message (request a block from a piece)."""

    def __init__(self, piece_index: int, begin: int, length: int):
        """Initialize request message.

        Args:
            piece_index: Index of the piece to request
            begin: Byte offset within the piece
            length: Number of bytes to request (up to 16KB typically)
        """
        super().__init__(MessageType.REQUEST)
        self.piece_index = piece_index
        self.begin = begin
        self.length = length

    def encode(self) -> bytes:
        """Encode request message."""
        return (struct.pack("!I", 13) +  # length = 13 (1 byte ID + 12 bytes payload)
                struct.pack("B", self.message_id) +
                struct.pack("!III", self.piece_index, self.begin, self.length))

    @classmethod
    def decode(cls, data: bytes) -> "RequestMessage":
        """Decode request message."""
        if len(data) != 17:
            raise MessageError(f"Request message must be 17 bytes, got {len(data)}")
        length, message_id, piece_index, begin, req_length = struct.unpack("!IBIII", data)
        if length != 13:
            raise MessageError(f"Request message length must be 13, got {length}")
        if message_id != MessageType.REQUEST:
            raise MessageError(f"Expected request message ID {MessageType.REQUEST}, got {message_id}")
        return cls(piece_index, begin, req_length)


class PieceMessage(PeerMessage):
    """Piece message (contains a block of piece data)."""

    def __init__(self, piece_index: int, begin: int, block: bytes):
        """Initialize piece message.

        Args:
            piece_index: Index of the piece
            begin: Byte offset within the piece
            block: The actual data block
        """
        super().__init__(MessageType.PIECE)
        self.piece_index = piece_index
        self.begin = begin
        self.block = block

    def encode(self) -> bytes:
        """Encode piece message."""
        length = 1 + 4 + 4 + len(self.block)  # ID + index + begin + block
        return (struct.pack("!I", length) +
                struct.pack("B", self.message_id) +
                struct.pack("!II", self.piece_index, self.begin) +
                self.block)

    @classmethod
    def decode(cls, data: bytes) -> "PieceMessage":
        """Decode piece message."""
        if len(data) < 13:
            raise MessageError(f"Piece message too short: {len(data)} bytes")

        length, message_id = struct.unpack("!IB", data[:5])
        if length < 9:
            raise MessageError(f"Piece message length too small: {length}")

        expected_length = 4 + length  # 4 bytes length + length field value
        if len(data) != expected_length:
            raise MessageError(f"Piece message length mismatch: expected {expected_length}, got {len(data)}")

        if message_id != MessageType.PIECE:
            raise MessageError(f"Expected piece message ID {MessageType.PIECE}, got {message_id}")

        piece_index, begin = struct.unpack("!II", data[5:13])
        block = data[13:]
        return cls(piece_index, begin, block)


class CancelMessage(PeerMessage):
    """Cancel message (cancel a previous request)."""

    def __init__(self, piece_index: int, begin: int, length: int):
        """Initialize cancel message.

        Args:
            piece_index: Index of the piece
            begin: Byte offset within the piece
            length: Number of bytes being cancelled
        """
        super().__init__(MessageType.CANCEL)
        self.piece_index = piece_index
        self.begin = begin
        self.length = length

    def encode(self) -> bytes:
        """Encode cancel message."""
        return (struct.pack("!I", 13) +  # length = 13 (1 byte ID + 12 bytes payload)
                struct.pack("B", self.message_id) +
                struct.pack("!III", self.piece_index, self.begin, self.length))

    @classmethod
    def decode(cls, data: bytes) -> "CancelMessage":
        """Decode cancel message."""
        if len(data) != 17:
            raise MessageError(f"Cancel message must be 17 bytes, got {len(data)}")
        length, message_id, piece_index, begin, req_length = struct.unpack("!IBIII", data)
        if length != 13:
            raise MessageError(f"Cancel message length must be 13, got {length}")
        if message_id != MessageType.CANCEL:
            raise MessageError(f"Expected cancel message ID {MessageType.CANCEL}, got {message_id}")
        return cls(piece_index, begin, req_length)


class OptimizedMessageDecoder:
    """High-performance message decoder with memoryview and object reuse."""

    def __init__(self, max_buffer_size: int = 1024 * 1024):  # 1MB buffer
        self.config = get_config()
        self.max_buffer_size = max_buffer_size

        # Simple buffer for partial messages
        self.buffer = bytearray()

        # Object pools for message reuse
        self.message_pools = {
            MessageType.CHOKE: deque(maxlen=100),
            MessageType.UNCHOKE: deque(maxlen=100),
            MessageType.INTERESTED: deque(maxlen=100),
            MessageType.NOT_INTERESTED: deque(maxlen=100),
            MessageType.HAVE: deque(maxlen=100),
            MessageType.REQUEST: deque(maxlen=100),
            MessageType.CANCEL: deque(maxlen=100),
        }

        # Pre-allocated struct unpackers for performance
        self._unpack_length = struct.Struct("!I").unpack
        self._unpack_message_id = struct.Struct("B").unpack
        self._unpack_have = struct.Struct("!IBI").unpack
        _unpack_request = struct.Struct("!IBIII").unpack

        self.logger = logging.getLogger(__name__)

    def add_data(self, data: Union[bytes, memoryview]) -> List[PeerMessage]:
        """Add data to the buffer and return any complete messages.
        
        Args:
            data: Raw bytes or memoryview from the peer connection
            
        Returns:
            List of decoded messages
        """
        # Convert to bytes for simpler handling
        if isinstance(data, memoryview):
            data_bytes = bytes(data)
        else:
            data_bytes = data

        # Add to buffer
        self.buffer.extend(data_bytes)

        messages = []

        # Process complete messages from buffer
        while len(self.buffer) >= 4:
            # Read message length
            length = struct.unpack("!I", self.buffer[0:4])[0]

            # Check if we have complete message
            if len(self.buffer) < 4 + length:
                break

            # Extract message data
            message_data = self.buffer[4:4+length]

            # Decode message
            if length == 0:
                # Keep-alive message
                messages.append(KeepAliveMessage())
            else:
                message_id = message_data[0]
                if length == 1:
                    # Simple 1-byte messages
                    messages.append(self._decode_simple_message(message_id))
                else:
                    # Complex messages with payload
                    messages.append(self._decode_complex_message(message_id, message_data))

            # Remove processed message from buffer
            del self.buffer[0:4+length]

        return messages

    def _decode_next_message(self) -> Optional[PeerMessage]:
        """Decode the next message from the buffer using memoryview."""
        if self.buffer_size < 4:
            return None  # Need at least 4 bytes for length

        # Read message length using memoryview
        length = self._unpack_length(self.buffer_view[0:4])[0]

        if length == 0:
            # Keep-alive message
            if self.buffer_size >= 4:
                self._consume_buffer(4)
                return KeepAliveMessage()
            return None

        # Need complete message
        if self.buffer_size < 4 + length:
            return None

        # Extract message data using memoryview (zero-copy)
        message_data = self.buffer_view[4:4 + length]
        self._consume_buffer(4 + length)

        # Decode based on message ID
        message_id = self._unpack_message_id(message_data[0:1])[0]

        if length == 1:
            # Simple 1-byte messages (CHOKE, UNCHOKE, INTERESTED, NOT_INTERESTED)
            return self._decode_simple_message(message_id)
        # Complex messages with payload (HAVE, BITFIELD, REQUEST, PIECE, CANCEL)
        return self._decode_complex_message(message_id, message_data)

    def _decode_simple_message(self, message_id: int) -> PeerMessage:
        """Decode simple 1-byte messages."""
        if message_id == MessageType.CHOKE:
            return self._get_pooled_message(MessageType.CHOKE)
        if message_id == MessageType.UNCHOKE:
            return self._get_pooled_message(MessageType.UNCHOKE)
        if message_id == MessageType.INTERESTED:
            return self._get_pooled_message(MessageType.INTERESTED)
        if message_id == MessageType.NOT_INTERESTED:
            return self._get_pooled_message(MessageType.NOT_INTERESTED)
        raise MessageError(f"Unknown simple message type: {message_id}")

    def _decode_complex_message(self, message_id: int, message_data: memoryview) -> PeerMessage:
        """Decode complex messages with payload."""
        if message_id == MessageType.HAVE:
            if len(message_data) != 5:
                raise MessageError(f"Have message must be 5 bytes, got {len(message_data)}")
            piece_index = struct.unpack("!I", message_data[1:5])[0]
            return self._get_pooled_have_message(piece_index)

        if message_id == MessageType.BITFIELD:
            if len(message_data) < 1:
                raise MessageError("Bitfield message too short")
            bitfield = bytes(message_data[1:])  # Convert to bytes for storage
            return BitfieldMessage(bitfield)

        if message_id == MessageType.REQUEST:
            if len(message_data) != 13:
                raise MessageError(f"Request message must be 13 bytes, got {len(message_data)}")
            piece_index, begin, length = struct.unpack("!III", message_data[1:13])
            return self._get_pooled_request_message(piece_index, begin, length)

        if message_id == MessageType.PIECE:
            if len(message_data) < 9:
                raise MessageError("Piece message too short")
            piece_index, begin = struct.unpack("!II", message_data[1:9])
            block_data = bytes(message_data[9:])  # Convert to bytes
            return PieceMessage(piece_index, begin, block_data)

        if message_id == MessageType.CANCEL:
            if len(message_data) != 13:
                raise MessageError(f"Cancel message must be 13 bytes, got {len(message_data)}")
            piece_index, begin, length = struct.unpack("!III", message_data[1:13])
            return self._get_pooled_cancel_message(piece_index, begin, length)

        raise MessageError(f"Unknown complex message type: {message_id}")

    def _get_pooled_message(self, message_type: MessageType) -> PeerMessage:
        """Get a message from the object pool or create new one."""
        pool = self.message_pools.get(message_type)
        if pool and pool:
            return pool.popleft()

        # Create new message
        if message_type == MessageType.CHOKE:
            return ChokeMessage()
        if message_type == MessageType.UNCHOKE:
            return UnchokeMessage()
        if message_type == MessageType.INTERESTED:
            return InterestedMessage()
        if message_type == MessageType.NOT_INTERESTED:
            return NotInterestedMessage()
        raise MessageError(f"Cannot pool message type: {message_type}")

    def _get_pooled_have_message(self, piece_index: int) -> HaveMessage:
        """Get a HaveMessage from pool or create new one."""
        pool = self.message_pools[MessageType.HAVE]
        if pool:
            msg = pool.popleft()
            msg.piece_index = piece_index
            return msg
        return HaveMessage(piece_index)

    def _get_pooled_request_message(self, piece_index: int, begin: int, length: int) -> RequestMessage:
        """Get a RequestMessage from pool or create new one."""
        pool = self.message_pools[MessageType.REQUEST]
        if pool:
            msg = pool.popleft()
            msg.piece_index = piece_index
            msg.begin = begin
            msg.length = length
            return msg
        return RequestMessage(piece_index, begin, length)

    def _get_pooled_cancel_message(self, piece_index: int, begin: int, length: int) -> CancelMessage:
        """Get a CancelMessage from pool or create new one."""
        pool = self.message_pools[MessageType.CANCEL]
        if pool:
            msg = pool.popleft()
            msg.piece_index = piece_index
            msg.begin = begin
            msg.length = length
            return msg
        return CancelMessage(piece_index, begin, length)

    def _consume_buffer(self, bytes_to_consume: int) -> None:
        """Consume bytes from the buffer by shifting remaining data."""
        if bytes_to_consume >= self.buffer_size:
            self._reset_buffer()
            return

        # Simple approach: create new buffer with remaining data
        remaining = self.buffer_size - bytes_to_consume
        remaining_data = bytes(self.buffer_view[bytes_to_consume:bytes_to_consume + remaining])

        # Clear buffer and add remaining data
        self.buffer_size = 0
        self.buffer_pos = 0
        self.buffer_view[0:remaining] = remaining_data
        self.buffer_size = remaining
        self.buffer_pos = remaining

    def _reset_buffer(self) -> None:
        """Reset the buffer to empty state."""
        self.buffer_pos = 0
        self.buffer_size = 0

    def return_message_to_pool(self, message: PeerMessage) -> None:
        """Return a message to the object pool for reuse."""
        if message.message_id in self.message_pools:
            pool = self.message_pools[message.message_id]
            if len(pool) < pool.maxlen:
                pool.append(message)

    def get_buffer_stats(self) -> Dict[str, Any]:
        """Get buffer statistics for monitoring."""
        return {
            "buffer_size": self.buffer_size,
            "buffer_capacity": self.max_buffer_size,
            "buffer_usage": self.buffer_size / self.max_buffer_size,
            "pool_sizes": {msg_type.name: len(pool) for msg_type, pool in self.message_pools.items()},
        }


class MessageDecoder(OptimizedMessageDecoder):
    """Backward compatibility wrapper for MessageDecoder."""

    def __init__(self):
        super().__init__()


def create_message(message_type: MessageType, **kwargs) -> PeerMessage:
    """Factory function to create messages.

    Args:
        message_type: Type of message to create
        **kwargs: Additional arguments for message initialization

    Returns:
        Appropriate message object
    """
    if message_type == MessageType.CHOKE:
        return ChokeMessage()
    if message_type == MessageType.UNCHOKE:
        return UnchokeMessage()
    if message_type == MessageType.INTERESTED:
        return InterestedMessage()
    if message_type == MessageType.NOT_INTERESTED:
        return NotInterestedMessage()
    if message_type == MessageType.HAVE:
        return HaveMessage(kwargs["piece_index"])
    if message_type == MessageType.BITFIELD:
        return BitfieldMessage(kwargs["bitfield"])
    if message_type == MessageType.REQUEST:
        return RequestMessage(kwargs["piece_index"], kwargs["begin"], kwargs["length"])
    if message_type == MessageType.PIECE:
        return PieceMessage(kwargs["piece_index"], kwargs["begin"], kwargs["block"])
    if message_type == MessageType.CANCEL:
        return CancelMessage(kwargs["piece_index"], kwargs["begin"], kwargs["length"])
    raise MessageError(f"Unknown message type: {message_type}")


class SocketOptimizer:
    """Socket optimization utilities for high-performance networking."""

    def __init__(self):
        self.config = get_config()
        self.logger = logging.getLogger(__name__)

    def optimize_socket(self, sock: socket.socket) -> None:
        """Apply socket optimizations for high-performance BitTorrent.
        
        Args:
            sock: Socket to optimize
        """
        try:
            # TCP_NODELAY - disable Nagle's algorithm for low latency
            if self.config.network.tcp_nodelay:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            # Socket buffer sizes
            rcvbuf = self.config.network.socket_rcvbuf
            sndbuf = self.config.network.socket_sndbuf

            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, sndbuf)

            # Enable address reuse for faster reconnection
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Set socket timeout for non-blocking operations
            sock.settimeout(self.config.network.connection_timeout)

            # Enable keep-alive for connection health monitoring
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            # Platform-specific optimizations
            self._apply_platform_optimizations(sock)

            self.logger.debug(f"Applied socket optimizations: rcvbuf={rcvbuf}, sndbuf={sndbuf}")

        except Exception as e:
            self.logger.warning(f"Failed to apply socket optimizations: {e}")

    def _apply_platform_optimizations(self, sock) -> None:
        """Apply platform-specific socket optimizations."""
        import platform

        system = platform.system()

        if system == "Linux":
            try:
                # TCP_CORK - batch small packets (Linux only)
                sock.setsockopt(socket.IPPROTO_TCP, 3, 1)  # TCP_CORK

                # TCP_QUICKACK - send ACKs immediately
                sock.setsockopt(socket.IPPROTO_TCP, 9, 1)  # TCP_QUICKACK

            except (OSError, AttributeError):
                pass  # Not supported on this system

        elif system == "Darwin":  # macOS
            try:
                # TCP_NOPUSH - batch small packets (macOS equivalent of TCP_CORK)
                sock.setsockopt(socket.IPPROTO_TCP, 4, 1)  # TCP_NOPUSH

            except (OSError, AttributeError):
                pass  # Not supported on this system

        elif system == "Windows":
            try:
                # Windows-specific optimizations
                import ctypes
                from ctypes import wintypes

                # Set TCP window scaling
                sock.setsockopt(socket.IPPROTO_TCP, 8, 1)  # TCP window scaling

            except (OSError, AttributeError, ImportError):
                pass  # Not supported on this system

    def get_optimal_buffer_sizes(self, connection_count: int) -> Tuple[int, int]:
        """Calculate optimal socket buffer sizes based on connection count.
        
        Args:
            connection_count: Number of active connections
            
        Returns:
            Tuple of (receive_buffer_size, send_buffer_size)
        """
        # Base buffer sizes
        base_rcvbuf = self.config.network.socket_rcvbuf
        base_sndbuf = self.config.network.socket_sndbuf

        # Scale with connection count (up to a maximum)
        max_connections = self.config.network.max_global_peers
        scale_factor = min(connection_count / max_connections, 1.0)

        # Calculate scaled buffer sizes
        rcvbuf = int(base_rcvbuf * (1.0 + scale_factor))
        sndbuf = int(base_sndbuf * (1.0 + scale_factor))

        # Cap at reasonable maximums
        max_buffer = 1024 * 1024  # 1MB
        rcvbuf = min(rcvbuf, max_buffer)
        sndbuf = min(sndbuf, max_buffer)

        return rcvbuf, sndbuf


class MessageBuffer:
    """High-performance message buffer with preallocation and batching."""

    def __init__(self, max_size: int = 64 * 1024):  # 64KB default
        self.max_size = max_size
        self.buffer = bytearray(max_size)
        self.buffer_view = memoryview(self.buffer)
        self.write_pos = 0
        self.pending_messages = deque(maxlen=1000)

        # Pre-allocated struct packers for performance
        self._pack_length = struct.Struct("!I").pack
        self._pack_message_id = struct.Struct("B").pack
        self._pack_have = struct.Struct("!IBI").pack
        self._pack_request = struct.Struct("!IBIII").pack

        self.logger = logging.getLogger(__name__)

    def add_message(self, message: PeerMessage) -> bool:
        """Add a message to the buffer.
        
        Args:
            message: Message to add
            
        Returns:
            True if message was added, False if buffer is full
        """
        try:
            # Encode message
            message_data = message.encode()

            # Check if we have space
            if self.write_pos + len(message_data) > self.max_size:
                return False

            # Add to buffer
            self.buffer_view[self.write_pos:self.write_pos + len(message_data)] = message_data
            self.write_pos += len(message_data)

            # Track pending message
            self.pending_messages.append((message, len(message_data)))

            return True

        except Exception as e:
            self.logger.error(f"Failed to add message to buffer: {e}")
            return False

    def get_buffered_data(self) -> memoryview:
        """Get all buffered data as memoryview."""
        return self.buffer_view[:self.write_pos]

    def clear(self) -> None:
        """Clear the buffer."""
        self.write_pos = 0
        self.pending_messages.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        return {
            "buffer_size": self.write_pos,
            "buffer_capacity": self.max_size,
            "buffer_usage": self.write_pos / self.max_size,
            "pending_messages": len(self.pending_messages),
        }


# Global socket optimizer instance
_socket_optimizer = SocketOptimizer()


def optimize_socket(sock: socket.socket) -> None:
    """Optimize a socket for high-performance BitTorrent."""
    _socket_optimizer.optimize_socket(sock)


def get_optimal_buffer_sizes(connection_count: int) -> Tuple[int, int]:
    """Get optimal socket buffer sizes for the given connection count."""
    return _socket_optimizer.get_optimal_buffer_sizes(connection_count)
