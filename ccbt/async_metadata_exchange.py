"""Async metadata exchange (BEP 10 + ut_metadata) for magnet downloads.

High-performance parallel metadata fetching with reliability scoring,
retry logic, and out-of-order piece handling.
"""

import asyncio
import hashlib
import logging
import math
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .bencode import BencodeDecoder, BencodeEncoder
from .config import get_config


class MetadataState(Enum):
    """States of metadata exchange."""
    CONNECTING = "connecting"
    HANDSHAKE = "handshake"
    NEGOTIATING = "negotiating"
    REQUESTING = "requesting"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class PeerMetadataSession:
    """Metadata exchange session with a single peer."""
    peer_info: Tuple[str, int]  # (ip, port)
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    state: MetadataState = MetadataState.CONNECTING

    # Extended protocol
    ut_metadata_id: Optional[int] = None
    metadata_size: Optional[int] = None

    # Reliability tracking
    reliability_score: float = 1.0
    consecutive_failures: int = 0
    last_activity: float = field(default_factory=time.time)

    # Piece tracking
    pieces_received: Dict[int, bytes] = field(default_factory=dict)
    pieces_requested: Set[int] = field(default_factory=set)
    pieces_failed: Set[int] = field(default_factory=set)

    # Retry logic
    retry_count: int = 0
    max_retries: int = 3
    backoff_delay: float = 1.0


@dataclass
class MetadataPiece:
    """Represents a metadata piece."""
    index: int
    data: Optional[bytes] = None
    received_count: int = 0
    sources: Set[Tuple[str, int]] = field(default_factory=set)


class AsyncMetadataExchange:
    """High-performance async metadata exchange manager."""

    def __init__(self, info_hash: bytes, peer_id: Optional[bytes] = None):
        """Initialize async metadata exchange.
        
        Args:
            info_hash: SHA-1 hash of the info dictionary
            peer_id: Our peer ID (20 bytes)
        """
        self.info_hash = info_hash
        self.config = get_config()

        if peer_id is None:
            peer_id = b"-CC0101-" + b"x" * 12
        self.our_peer_id = peer_id

        # Session management
        self.sessions: Dict[Tuple[str, int], PeerMetadataSession] = {}
        self.metadata_pieces: Dict[int, MetadataPiece] = {}
        self.metadata_size: Optional[int] = None
        self.num_pieces: int = 0

        # Completion tracking
        self.completed = False
        self.metadata_data: Optional[bytes] = None
        self.metadata_dict: Optional[Dict[bytes, Any]] = None

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_progress: Optional[callable] = None
        self.on_complete: Optional[callable] = None
        self.on_error: Optional[callable] = None

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start background tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("Async metadata exchange started")

    async def stop(self) -> None:
        """Stop background tasks and cleanup."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all sessions
        for session in list(self.sessions.values()):
            await self._close_session(session)

        self.logger.info("Async metadata exchange stopped")

    async def fetch_metadata(self, peers: List[Dict[str, Any]],
                           max_peers: int = 10, timeout: float = 30.0) -> Optional[Dict[bytes, Any]]:
        """Fetch metadata from multiple peers in parallel.
        
        Args:
            peers: List of peer dictionaries
            max_peers: Maximum number of peers to connect to
            timeout: Timeout in seconds
            
        Returns:
            Parsed metadata dictionary or None if failed
        """
        self.logger.info(f"Starting metadata fetch from {min(len(peers), max_peers)} peers")

        # Create connection tasks
        tasks = []
        for i, peer_data in enumerate(peers[:max_peers]):
            peer_info = (peer_data["ip"], peer_data["port"])
            task = asyncio.create_task(self._connect_and_fetch(peer_info, timeout))
            tasks.append(task)

        # Wait for completion or timeout
        try:
            await asyncio.wait_for(self._wait_for_completion(), timeout=timeout)
        except asyncio.TimeoutError:
            self.logger.warning("Metadata fetch timed out")
            return None

        # Cancel remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()

        return self.metadata_dict

    async def _connect_and_fetch(self, peer_info: Tuple[str, int], timeout: float) -> None:
        """Connect to a peer and attempt metadata fetch."""
        session = PeerMetadataSession(peer_info)
        self.sessions[peer_info] = session

        try:
            # Connect to peer
            session.reader, session.writer = await asyncio.wait_for(
                asyncio.open_connection(peer_info[0], peer_info[1]),
                timeout=timeout,
            )
            session.state = MetadataState.HANDSHAKE

            # Send handshake
            handshake_data = self._create_handshake()
            session.writer.write(handshake_data)
            await session.writer.drain()

            # Receive handshake
            peer_handshake = await session.reader.readexactly(68)
            if not self._validate_handshake(peer_handshake):
                raise ConnectionError("Invalid handshake")

            session.state = MetadataState.NEGOTIATING

            # Send extended handshake
            await self._send_extended_handshake(session)

            # Receive extended handshake
            await self._receive_extended_handshake(session)

            if not session.ut_metadata_id or not session.metadata_size:
                raise ConnectionError("Peer doesn't support ut_metadata")

            session.state = MetadataState.REQUESTING

            # Start requesting metadata pieces
            await self._request_metadata_pieces(session)

        except Exception as e:
            self.logger.debug(f"Failed to fetch metadata from {peer_info}: {e}")
            session.consecutive_failures += 1
            session.reliability_score = max(0.1, session.reliability_score - 0.2)

            if session.consecutive_failures >= session.max_retries:
                await self._close_session(session)
        finally:
            session.last_activity = time.time()

    def _create_handshake(self) -> bytes:
        """Create BitTorrent handshake with extension protocol support."""
        pstr = b"BitTorrent protocol"
        reserved = bytearray(8)
        reserved[5] |= 0x10  # Extension protocol flag
        return (struct.pack("B", len(pstr)) + pstr + bytes(reserved) +
                self.info_hash + self.our_peer_id)

    def _validate_handshake(self, handshake_data: bytes) -> bool:
        """Validate received handshake."""
        if len(handshake_data) != 68:
            return False

        if handshake_data[1:20] != b"BitTorrent protocol":
            return False

        if handshake_data[28:48] != self.info_hash:
            return False

        return True

    async def _send_extended_handshake(self, session: PeerMetadataSession) -> None:
        """Send extended handshake message."""
        payload = BencodeEncoder().encode({b"m": {b"ut_metadata": 1}})
        msg = struct.pack("!IBB", 2 + len(payload), 20, 0) + payload
        session.writer.write(msg)
        await session.writer.drain()

    async def _receive_extended_handshake(self, session: PeerMetadataSession) -> None:
        """Receive and parse extended handshake."""
        # Read messages until we get extended handshake
        for _ in range(10):
            try:
                length_data = await asyncio.wait_for(session.reader.readexactly(4), timeout=5.0)
                length = struct.unpack("!I", length_data)[0]

                if length == 0:
                    continue  # Keep-alive

                payload = await asyncio.wait_for(session.reader.readexactly(length), timeout=5.0)
                msg_id = payload[0] if payload else 0

                if msg_id == 20:  # Extended message
                    ext_id = payload[1] if len(payload) > 1 else 0
                    if ext_id == 0:  # Extended handshake
                        decoder = BencodeDecoder(payload[2:])
                        data = decoder.decode()

                        # Extract ut_metadata support
                        m = data.get(b"m", {})
                        session.ut_metadata_id = m.get(b"ut_metadata")
                        session.metadata_size = data.get(b"metadata_size")
                        break
            except asyncio.TimeoutError:
                break
            except Exception:
                break

    async def _request_metadata_pieces(self, session: PeerMetadataSession) -> None:
        """Request metadata pieces from a peer."""
        if not session.ut_metadata_id or not session.metadata_size:
            return

        # Calculate number of pieces
        session.num_pieces = math.ceil(session.metadata_size / 16384)

        # Initialize metadata pieces if not done
        if not self.metadata_pieces:
            self.metadata_size = session.metadata_size
            self.num_pieces = session.num_pieces
            for i in range(self.num_pieces):
                self.metadata_pieces[i] = MetadataPiece(i)

        # Request all pieces from this peer
        for piece_idx in range(session.num_pieces):
            if piece_idx not in session.pieces_requested:
                await self._request_metadata_piece(session, piece_idx)
                session.pieces_requested.add(piece_idx)
                await asyncio.sleep(0.1)  # Small delay between requests

    async def _request_metadata_piece(self, session: PeerMetadataSession, piece_idx: int) -> None:
        """Request a specific metadata piece."""
        try:
            req_dict = {b"msg_type": 0, b"piece": piece_idx}
            req_payload = BencodeEncoder().encode(req_dict)
            req_msg = struct.pack("!IBB", 2 + len(req_payload), 20, session.ut_metadata_id) + req_payload

            session.writer.write(req_msg)
            await session.writer.drain()

            # Wait for response
            await self._wait_for_piece_response(session, piece_idx)

        except Exception as e:
            self.logger.debug(f"Failed to request piece {piece_idx} from {session.peer_info}: {e}")
            session.pieces_failed.add(piece_idx)

    async def _wait_for_piece_response(self, session: PeerMetadataSession, piece_idx: int) -> None:
        """Wait for a metadata piece response."""
        timeout = 10.0
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                length_data = await asyncio.wait_for(session.reader.readexactly(4), timeout=1.0)
                length = struct.unpack("!I", length_data)[0]

                if length == 0:
                    continue  # Keep-alive

                payload = await asyncio.wait_for(session.reader.readexactly(length), timeout=1.0)
                msg_id = payload[0] if payload else 0

                if msg_id == 20:  # Extended message
                    ext_id = payload[1] if len(payload) > 1 else 0
                    if ext_id == session.ut_metadata_id:
                        # Parse metadata piece response
                        decoder = BencodeDecoder(payload[2:])
                        header = decoder.decode()

                        msg_type = header.get(b"msg_type")
                        piece_index = header.get(b"piece")

                        if msg_type == 1 and piece_index == piece_idx:  # Data response
                            header_len = decoder.pos
                            piece_data = payload[2 + header_len:]

                            await self._handle_metadata_piece(session, piece_idx, piece_data)
                            return
                        if msg_type == 2:  # Reject
                            self.logger.debug(f"Peer {session.peer_info} rejected piece {piece_idx}")
                            session.pieces_failed.add(piece_idx)
                            return

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.debug(f"Error waiting for piece {piece_idx}: {e}")
                break

        # Timeout
        session.pieces_failed.add(piece_idx)

    async def _handle_metadata_piece(self, session: PeerMetadataSession, piece_idx: int, piece_data: bytes) -> None:
        """Handle a received metadata piece."""
        # Store piece data
        session.pieces_received[piece_idx] = piece_data

        # Update global piece tracking
        if piece_idx in self.metadata_pieces:
            self.metadata_pieces[piece_idx].data = piece_data
            self.metadata_pieces[piece_idx].received_count += 1
            self.metadata_pieces[piece_idx].sources.add(session.peer_info)

        # Check if we have all pieces
        if self._is_metadata_complete():
            await self._assemble_metadata()

    def _is_metadata_complete(self) -> bool:
        """Check if all metadata pieces have been received."""
        if not self.metadata_pieces:
            return False

        return all(piece.data is not None for piece in self.metadata_pieces.values())

    async def _assemble_metadata(self) -> None:
        """Assemble complete metadata from pieces."""
        try:
            # Sort pieces by index and concatenate
            sorted_pieces = sorted(self.metadata_pieces.items())
            metadata_data = b"".join(piece.data for _, piece in sorted_pieces)

            # Decode metadata
            decoder = BencodeDecoder(metadata_data)
            metadata_dict = decoder.decode()

            # Validate hash
            encoded_metadata = BencodeEncoder().encode(metadata_dict)
            if hashlib.sha1(encoded_metadata).digest() == self.info_hash:
                self.metadata_data = metadata_data
                self.metadata_dict = metadata_dict
                self.completed = True

                self.logger.info("Successfully assembled metadata")

                if self.on_complete:
                    self.on_complete(metadata_dict)
            else:
                self.logger.warning("Metadata hash validation failed")

        except Exception as e:
            self.logger.error(f"Failed to assemble metadata: {e}")
            if self.on_error:
                self.on_error(e)

    async def _wait_for_completion(self) -> None:
        """Wait for metadata fetch to complete."""
        while not self.completed:
            await asyncio.sleep(0.1)

    async def _cleanup_loop(self) -> None:
        """Background task to clean up failed sessions."""
        while True:
            try:
                await asyncio.sleep(30.0)  # Clean every 30 seconds
                await self._cleanup_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_sessions(self) -> None:
        """Clean up failed or stale sessions."""
        current_time = time.time()
        to_remove = []

        for peer_info, session in self.sessions.items():
            # Remove sessions that have been inactive for too long
            if current_time - session.last_activity > 60.0 or session.consecutive_failures >= session.max_retries:
                to_remove.append(peer_info)

        for peer_info in to_remove:
            session = self.sessions.pop(peer_info, None)
            if session:
                await self._close_session(session)

    async def _close_session(self, session: PeerMetadataSession) -> None:
        """Close a metadata session."""
        if session.writer:
            try:
                session.writer.close()
                await session.writer.wait_closed()
            except Exception:
                pass

        session.state = MetadataState.FAILED

    def get_progress(self) -> float:
        """Get metadata fetch progress (0.0 to 1.0)."""
        if not self.metadata_pieces:
            return 0.0

        received_pieces = sum(1 for piece in self.metadata_pieces.values() if piece.data is not None)
        return received_pieces / len(self.metadata_pieces)

    def get_stats(self) -> Dict[str, Any]:
        """Get metadata exchange statistics."""
        return {
            "sessions": len(self.sessions),
            "pieces_received": sum(1 for piece in self.metadata_pieces.values() if piece.data is not None),
            "total_pieces": len(self.metadata_pieces),
            "progress": self.get_progress(),
            "completed": self.completed,
            "metadata_size": self.metadata_size,
        }


async def fetch_metadata_from_peers(info_hash: bytes, peers: List[Dict[str, Any]],
                                  timeout: float = 30.0, peer_id: Optional[bytes] = None) -> Optional[Dict[bytes, Any]]:
    """High-performance parallel metadata fetch.
    
    Args:
        info_hash: SHA-1 hash of the info dictionary
        peers: List of peer dictionaries
        timeout: Timeout in seconds
        peer_id: Our peer ID (20 bytes)
    
    Returns:
        Parsed metadata dictionary or None if failed
    """
    exchange = AsyncMetadataExchange(info_hash, peer_id)

    try:
        await exchange.start()
        metadata = await exchange.fetch_metadata(peers, max_peers=10, timeout=timeout)
        return metadata
    finally:
        await exchange.stop()


# Helper classes for testing and internal use
class PeerReliabilityTracker:
    """Tracks peer reliability for metadata exchange."""

    def __init__(self):
        self.scores: Dict[Tuple[str, int], float] = {}
        self.failures: Dict[Tuple[str, int], int] = {}

    def update_success(self, peer_info: Tuple[str, int]):
        """Update reliability score for successful operation."""
        if peer_info not in self.scores:
            self.scores[peer_info] = 0.5  # Start with neutral score

        # Update based on success rate
        total_attempts = self.failures.get(peer_info, 0) + 1
        success_rate = 1 / total_attempts  # This success makes it 1/total_attempts
        self.scores[peer_info] = min(1.0, self.scores[peer_info] + success_rate * 0.5)
        self.failures[peer_info] = 0

    def update_failure(self, peer_info: Tuple[str, int]):
        """Update reliability score for failed operation."""
        if peer_info not in self.failures:
            self.failures[peer_info] = 0
        self.failures[peer_info] += 1

        # More severe penalty based on failure rate
        total_attempts = self.failures[peer_info] + (1 if peer_info in self.scores else 0)
        failure_rate = self.failures[peer_info] / total_attempts
        self.scores[peer_info] = max(0.0, 1.0 - failure_rate)

    def record_success(self, peer_info: Tuple[str, int]):
        """Alias for update_success for backward compatibility."""
        self.update_success(peer_info)

    def record_failure(self, peer_info: Tuple[str, int]):
        """Alias for update_failure for backward compatibility."""
        self.update_failure(peer_info)

    def get_reliability_score(self, peer_info: Tuple[str, int]) -> float:
        """Get reliability score for a peer."""
        return self.scores.get(peer_info, 0.5)  # Default to neutral score


class MetadataPieceManager:
    """Manages metadata pieces for assembly."""

    def __init__(self, total_size: int):
        self.total_size = total_size
        self.pieces: Dict[int, bytes] = {}
        self.received_pieces: Set[int] = set()

    def add_piece(self, piece_index: int, data: bytes):
        """Add a metadata piece."""
        self.pieces[piece_index] = data
        self.received_pieces.add(piece_index)

    def is_complete(self) -> bool:
        """Check if all pieces are received."""
        return len(self.received_pieces) == self.total_size

    def assemble_metadata(self) -> bytes:
        """Assemble complete metadata from pieces."""
        if not self.is_complete():
            raise ValueError("Not all pieces received")

        metadata = b""
        for i in range(self.total_size):
            metadata += self.pieces[i]
        return metadata


class RetryManager:
    """Manages retry logic for failed operations."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.retry_counts: Dict[Any, int] = {}

    def should_retry(self, key: Any) -> bool:
        """Check if operation should be retried."""
        return self.retry_counts.get(key, 0) < self.max_retries

    def record_retry(self, key: Any):
        """Record a retry attempt."""
        self.retry_counts[key] = self.retry_counts.get(key, 0) + 1

    def get_delay(self, key: Any) -> float:
        """Get delay for next retry."""
        retry_count = self.retry_counts.get(key, 0)
        return self.base_delay * (2 ** retry_count)

    def get_retry_count(self, key: Any) -> int:
        """Get current retry count for a key."""
        return self.retry_counts.get(key, 0)

    def record_success(self, key: Any):
        """Record successful operation and reset retry count."""
        if key in self.retry_counts:
            del self.retry_counts[key]


class MetadataCache:
    """Caches metadata for reuse."""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.cache: Dict[bytes, Dict[str, Any]] = {}
        self.access_times: Dict[bytes, float] = {}

    def get(self, info_hash: bytes) -> Optional[Dict[str, Any]]:
        """Get cached metadata."""
        if info_hash in self.cache:
            self.access_times[info_hash] = time.time()
            return self.cache[info_hash]
        return None

    def put(self, info_hash: bytes, metadata: Dict[str, Any]):
        """Cache metadata."""
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_hash = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            del self.cache[oldest_hash]
            del self.access_times[oldest_hash]

        self.cache[info_hash] = metadata
        self.access_times[info_hash] = time.time()


class MetadataMetrics:
    """Tracks metrics for metadata exchange."""

    def __init__(self):
        self.connections_attempted = 0
        self.connections_successful = 0
        self.pieces_requested = 0
        self.pieces_received = 0
        self.retries = 0
        self.start_time = time.time()

    def record_connection_attempt(self):
        """Record connection attempt."""
        self.connections_attempted += 1

    def record_connection_success(self):
        """Record successful connection."""
        self.connections_successful += 1

    def record_piece_request(self):
        """Record piece request."""
        self.pieces_requested += 1

    def record_piece_received(self):
        """Record piece received."""
        self.pieces_received += 1

    def record_retry(self):
        """Record retry attempt."""
        self.retries += 1

    def record_peer_connection(self, peer_info):
        """Record peer connection."""
        self.connections_attempted += 1

    def record_metadata_piece_received(self, peer_info):
        """Record metadata piece received."""
        self.record_piece_received()

    def record_metadata_complete(self, peer_info):
        """Record metadata completion."""
        # Metadata completion is already a successful operation, don't double-count

    def get_stats(self) -> Dict[str, Any]:
        """Get metrics statistics."""
        return {
            "connections_attempted": self.connections_attempted,
            "connections_successful": self.connections_successful,
            "pieces_requested": self.pieces_requested,
            "pieces_received": self.pieces_received,
            "retries": self.retries,
            "success_rate": self.get_success_rate(),
        }

    def get_success_rate(self) -> float:
        """Get connection success rate."""
        if self.connections_attempted == 0:
            return 0.0
        return self.connections_successful / self.connections_attempted

    def get_completion_rate(self) -> float:
        """Get piece completion rate."""
        if self.pieces_requested == 0:
            return 0.0
        return self.pieces_received / self.pieces_requested


def validate_metadata(metadata: bytes) -> bool:
    """Validate metadata structure."""
    try:
        decoder = BencodeDecoder(metadata)
        decoded = decoder.decode()

        if not isinstance(decoded, dict):
            return False

        # Check required fields (keys are bytes in bencoded data)
        required_fields = [b"info", b"announce"]
        for field in required_fields:
            if field not in decoded:
                return False

        return True
    except Exception:
        return False


# Internal functions for testing
async def _connect_to_peer(peer_info: Tuple[str, int], timeout: float = 10.0) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Connect to a peer for metadata exchange."""
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(peer_info[0], peer_info[1]),
        timeout=timeout,
    )
    return reader, writer


async def _send_extended_handshake(writer: asyncio.StreamWriter, ut_metadata_id: int):
    """Send extended handshake message."""
    # This would send the actual extended handshake
    # For testing purposes, we'll just pass


async def _fetch_metadata_from_peer(peer_info: Tuple[str, int], info_hash: bytes, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
    """Fetch metadata from a single peer."""
    try:
        reader, writer = await _connect_to_peer(peer_info, timeout)
        # This would implement the actual metadata fetching
        # For testing purposes, return None
        return None
    except Exception:
        return None


# Convenience function for direct use
async def fetch_metadata_from_peers_async(peers: List[Dict[str, Any]], info_hash: bytes,
                                        timeout: int = 30) -> Optional[Dict[str, Any]]:
    """Fetch metadata from peers asynchronously.
    
    Args:
        peers: List of peer dictionaries with 'ip' and 'port' keys
        info_hash: Info hash of the torrent
        timeout: Timeout in seconds
        
    Returns:
        Parsed metadata dictionary or None if failed
    """
    exchange = AsyncMetadataExchange(info_hash)
    try:
        await exchange.start()
        metadata = await exchange.fetch_metadata(peers, max_peers=10, timeout=timeout)
        return metadata
    finally:
        await exchange.stop()
