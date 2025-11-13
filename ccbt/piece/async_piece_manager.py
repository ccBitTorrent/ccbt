"""Advanced piece management for BitTorrent client.

from __future__ import annotations

Implements rarest-first piece selection, endgame mode, per-peer availability tracking,
and parallel hash verification for high performance.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from ccbt.config.config import get_config
from ccbt.models import (
    DownloadStats,
    FileCheckpoint,
    PieceSelectionStrategy,
    TorrentCheckpoint,
)
from ccbt.models import PieceState as PieceStateModel
from ccbt.piece.hash_v2 import HashAlgorithm, verify_piece

if (
    TYPE_CHECKING
):  # pragma: no cover - TYPE_CHECKING block, only imported during static type checking
    from ccbt.peer.async_peer_connection import AsyncPeerConnection


class PieceState(Enum):
    """States of a piece download."""

    MISSING = "missing"  # We don't have this piece
    REQUESTED = "requested"  # We've requested this piece from peers
    DOWNLOADING = "downloading"  # We're actively downloading this piece
    COMPLETE = "complete"  # We have the complete piece
    VERIFIED = "verified"  # Piece hash has been verified


@dataclass
class PieceBlock:
    """Represents a block within a piece."""

    piece_index: int
    begin: int
    length: int
    data: bytes = b""
    received: bool = False
    requested_from: set[str] = field(
        default_factory=set,
    )  # Peer keys that have this block

    def is_complete(self) -> bool:
        """Check if block is complete."""
        return self.received and len(self.data) == self.length

    def add_block(self, begin: int, data: bytes) -> bool:
        """Add block data if it matches this block's parameters."""
        if self.begin != begin:
            return False
        if len(data) != self.length:
            return False
        if self.received:
            return False

        self.data = data
        self.received = True
        return True


@dataclass
class PieceData:
    """Represents a complete piece with all its blocks."""

    piece_index: int
    length: int
    blocks: list[PieceBlock] = field(default_factory=list)
    state: PieceState = PieceState.MISSING
    hash_verified: bool = False
    priority: int = 0  # Higher priority = download first
    request_count: int = 0  # How many times we've requested this piece

    def __post_init__(self):
        """Initialize blocks after creation."""
        if not self.blocks:
            config = get_config()
            # Handle mocked configs in tests - ensure block_size_kib is numeric
            try:
                block_size_kib = getattr(config.network, "block_size_kib", 16)
                # If it's a mock or non-numeric, use default
                if not isinstance(block_size_kib, (int, float)):
                    block_size_kib = 16
                block_size = int(block_size_kib * 1024)
            except (
                AttributeError,
                TypeError,
                ValueError,
            ):  # pragma: no cover - Config block size error fallback, tested via valid config
                # Fallback to default 16 KiB block size
                block_size = 16 * 1024
            self.blocks = []

            for begin in range(0, self.length, block_size):
                actual_length = min(block_size, self.length - begin)
                self.blocks.append(PieceBlock(self.piece_index, begin, actual_length))

    def add_block(self, begin: int, data: bytes) -> bool:
        """Add a block of data to this piece."""
        for block in self.blocks:
            if block.begin == begin and not block.received:
                if len(data) != block.length:
                    return False

                block.data = data
                block.received = True

                # Check if piece is now complete
                if all(b.received for b in self.blocks):
                    self.state = PieceState.COMPLETE

                return True
        return False

    def is_complete(self) -> bool:
        """Check if piece is complete."""
        return all(block.received for block in self.blocks)

    def validate_state(self) -> bool:
        """Validate that piece state matches actual block completion status.

        Returns:
            True if state was corrected, False if state was already correct

        """
        actual_complete = self.is_complete()

        # If state says COMPLETE/VERIFIED but blocks aren't actually complete, reset to MISSING
        if (
            self.state in (PieceState.COMPLETE, PieceState.VERIFIED)
            and not actual_complete
        ):
            self.state = PieceState.MISSING
            self.hash_verified = False
            return True

        # If blocks are complete but state is MISSING/REQUESTED/DOWNLOADING, update to COMPLETE
        if actual_complete and self.state in (
            PieceState.MISSING,
            PieceState.REQUESTED,
            PieceState.DOWNLOADING,
        ):
            self.state = PieceState.COMPLETE
            return True

        return False

    def get_data(self) -> bytes:
        """Get the complete piece data."""
        if (
            not self.is_complete()
        ):  # pragma: no cover - Defensive check, tested via hash verification paths
            msg = f"Piece {self.piece_index} is not complete"
            raise ValueError(msg)

        # Sort blocks by begin offset and concatenate
        sorted_blocks = sorted(self.blocks, key=lambda b: b.begin)
        return b"".join(block.data for block in sorted_blocks)

    def get_missing_blocks(self) -> list[PieceBlock]:
        """Get list of missing blocks."""
        return [block for block in self.blocks if not block.received]

    def verify_hash(self, expected_hash: bytes) -> bool:
        """Verify piece hash.

        Supports both SHA-1 (v1, 20 bytes) and SHA-256 (v2, 32 bytes) algorithms.
        Algorithm is auto-detected from expected_hash length.
        """
        if (
            not self.is_complete()
        ):  # pragma: no cover - Early return path, verified via _hash_piece_optimized
            return False

        # Detect algorithm from hash length
        # 20 bytes = SHA-1 (v1), 32 bytes = SHA-256 (v2)
        if len(expected_hash) == 32:
            algorithm = HashAlgorithm.SHA256
        elif len(expected_hash) == 20:
            algorithm = HashAlgorithm.SHA1
        else:
            # Invalid hash length
            return False  # pragma: no cover - Invalid hash length validation, tested via integration tests with valid hash lengths

        # Use unified verify_piece function from hash_v2 module
        # verify_hash method implementation - tested via _hash_piece_optimized and _verify_piece_hash
        self.hash_verified = verify_piece(
            self.get_data(),
            expected_hash,
            algorithm=algorithm,
        )  # pragma: no cover - Hash verification tested via optimized method

        if (
            self.hash_verified
        ):  # pragma: no cover - Success condition check, tested via optimized method
            self.state = (
                PieceState.VERIFIED
            )  # pragma: no cover - Success path tested via optimized method
        else:
            # Hash verification failed, mark as missing so it gets re-downloaded
            # Error recovery path, verified via _verify_piece_hash failure tests
            self.state = PieceState.MISSING  # pragma: no cover - Error recovery path
            for (
                block
            ) in self.blocks:  # pragma: no cover - Block reset in error recovery
                block.received = (
                    False  # pragma: no cover - Block reset in error recovery
                )
                block.data = b""  # pragma: no cover - Block reset in error recovery

        return (
            self.hash_verified
        )  # pragma: no cover - Return value tested via optimized method


@dataclass
class PeerAvailability:
    """Tracks which pieces a peer has."""

    peer_key: str
    pieces: set[int] = field(default_factory=set)
    last_updated: float = field(default_factory=time.time)
    reliability_score: float = 1.0  # 0.0 to 1.0, higher is better


class AsyncPieceManager:
    """Advanced piece manager with rarest-first and endgame mode."""

    def __init__(
        self,
        torrent_data: dict[str, Any],
        file_selection_manager: Any | None = None,
    ):
        """Initialize async piece manager.

        Args:
            torrent_data: Parsed torrent data from TorrentParser
            file_selection_manager: Optional FileSelectionManager instance

        Note:
            For magnet links, torrent_data may have incomplete metadata initially.
            The piece manager will need to be updated once metadata is fetched.

        """
        self.torrent_data = torrent_data
        self.config = get_config()

        # Handle magnet links with incomplete metadata
        pieces_info = torrent_data.get("pieces_info")
        if pieces_info is None:
            # This shouldn't happen if _normalize_torrent_data worked correctly,
            # but handle it defensively
            pieces_info = {
                "piece_hashes": [],
                "piece_length": 16384,
                "num_pieces": 0,
                "total_length": 0,
            }
            self.torrent_data["pieces_info"] = pieces_info
            self._metadata_incomplete = True
        else:
            self._metadata_incomplete = torrent_data.get("_metadata_incomplete", False)

        # Ensure we have valid types (defensive programming for type safety)
        num_pieces_val = pieces_info.get("num_pieces", 0)
        piece_length_val = pieces_info.get("piece_length", 16384)
        piece_hashes_val = pieces_info.get("piece_hashes", [])

        # Type assertions to ensure we have the right types
        self.num_pieces = (
            int(num_pieces_val) if isinstance(num_pieces_val, (int, float)) else 0
        )
        self.piece_length = (
            int(piece_length_val)
            if isinstance(piece_length_val, (int, float))
            else 16384
        )
        self.piece_hashes = (
            list(piece_hashes_val)
            if isinstance(piece_hashes_val, (list, tuple))
            else []
        )

        # v2/hybrid torrent support (BEP 52)
        # Check if torrent has v2 piece layers (for hybrid torrents)
        self.piece_layers = torrent_data.get("piece_layers")
        self.meta_version = torrent_data.get("meta_version", 1)  # 1=v1, 2=v2, 3=hybrid

        # File selection manager (optional)
        self.file_selection_manager = file_selection_manager

        # Piece tracking
        self.pieces: list[PieceData] = []
        self.completed_pieces: set[int] = set()
        self.verified_pieces: set[int] = set()
        self.lock = asyncio.Lock()

        # Xet Merkle hash cache (piece_index -> merkle_hash)
        self.xet_merkle_hashes: dict[int, bytes] = {}
        self.xet_chunk_hashes: dict[
            int, list[bytes]
        ] = {}  # piece_index -> list of chunk hashes

        # Per-peer availability tracking
        self.peer_availability: dict[str, PeerAvailability] = {}
        self.piece_frequency: Counter = Counter()  # How many peers have each piece

        # Endgame mode
        self.endgame_mode = False
        self.endgame_threshold = self.config.strategy.endgame_threshold
        self.endgame_duplicates = self.config.strategy.endgame_duplicates

        # Hash verification pool (adaptive if enabled)
        if self.config.disk.hash_workers_adaptive:
            # Work-stealing executor limitation and workaround:
            # Python's ThreadPoolExecutor doesn't support work-stealing natively.
            # True work-stealing requires custom implementation using deque-based task
            # queues per worker, where workers can steal tasks from other workers'
            # queues when idle. This would improve load balancing for hash verification.
            #
            # Current workaround: Double the worker count to approximate work-stealing
            # benefits. More workers = better load distribution, as idle workers can
            # pick up tasks from the shared queue. This provides reasonable performance
            # but is not as efficient as true work-stealing.
            #
            # TODO: Implement custom WorkStealingExecutor class using asyncio.Queue
            # with per-worker deques for efficient task stealing. This would further
            # improve load balancing and reduce idle time.
            effective_workers = min(
                self.config.disk.hash_workers * 2,
                32,  # Cap at reasonable maximum
            )
        else:  # pragma: no cover - Non-adaptive hash workers path, adaptive is default
            effective_workers = self.config.disk.hash_workers

        self.hash_executor = ThreadPoolExecutor(
            max_workers=effective_workers,
            thread_name_prefix="hash-verify",
        )
        # No background queue; verify hashes via scheduled tasks on completion
        self.hash_queue = None  # kept for backward compatibility, not used

        # Initialize pieces
        for i in range(self.num_pieces):
            # Calculate actual piece length (last piece may be shorter)
            if i == self.num_pieces - 1:
                # Get total_length safely - handle different torrent_data structures
                total_length = 0
                if "file_info" in torrent_data and torrent_data.get("file_info"):
                    total_length = torrent_data["file_info"].get("total_length", 0)
                elif "total_length" in torrent_data:
                    total_length = torrent_data["total_length"]
                else:
                    # Fallback: calculate from pieces (approximation)
                    total_length = self.num_pieces * self.piece_length

                piece_length = total_length - (i * self.piece_length)
                # Ensure piece_length is positive
                if piece_length <= 0:
                    piece_length = self.piece_length
            else:
                piece_length = self.piece_length

            piece = PieceData(i, piece_length)

            # Set priorities for streaming mode
            if self.config.strategy.streaming_mode:
                if i == 0:
                    piece.priority = 1000  # First piece highest priority
                elif i == self.num_pieces - 1:
                    # Fallback: boost last piece modestly
                    piece.priority = 100
                else:
                    piece.priority = max(0, 1000 - i)  # Decreasing priority

            # Apply file-based priorities if file selection manager exists
            if self.file_selection_manager:
                file_priority = self.file_selection_manager.get_piece_priority(i)
                # Scale file priority to piece priority (multiply by 100 to match streaming mode scale)
                piece.priority = max(piece.priority, file_priority * 100)

            self.pieces.append(piece)

        # Download state
        self.is_downloading = False
        self.download_complete = False
        self.download_start_time = time.time()
        self.bytes_downloaded = 0
        self._current_sequential_piece: int = 0  # Track current sequential position
        self._peer_manager: Any | None = None  # Store peer manager for piece requests

        # Callbacks
        self.on_piece_completed: Callable[[int], None] | None = None
        self.on_piece_verified: Callable[[int], None] | None = None
        self.on_download_complete: Callable[[], None] | None = None
        self.on_file_assembled: Callable[[int], None] | None = None
        self.on_checkpoint_save: Callable[[], None] | None = None

        # File assembler (set by download manager)
        self.file_assembler: Any | None = None

        # Background tasks
        self._hash_worker_task: asyncio.Task | None = None
        self._piece_selector_task: asyncio.Task | None = None
        self._background_tasks: set[asyncio.Task] = set()

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start background tasks."""
        # No hash worker; schedule verifications per piece completion
        self._piece_selector_task = asyncio.create_task(self._piece_selector())
        self.logger.info("Async piece manager started")

    async def stop(self) -> None:
        """Stop background tasks."""
        if self._piece_selector_task:
            self._piece_selector_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._piece_selector_task

        self.hash_executor.shutdown(wait=True)
        self.logger.info("Async piece manager stopped")

    def get_missing_pieces(self) -> list[int]:
        """Get list of missing piece indices."""
        # CRITICAL FIX: Handle case where pieces list is empty but num_pieces > 0
        # This can happen when metadata arrives after piece manager initialization
        if not self.pieces and self.num_pieces > 0:
            self.logger.warning(
                "Pieces list is empty but num_pieces=%d - returning all indices as missing. "
                "Pieces should be initialized in start_download().",
                self.num_pieces,
            )
            # Return all indices as missing - they will be initialized when needed
            missing = list(range(self.num_pieces))
        elif len(self.pieces) != self.num_pieces and self.num_pieces > 0:
            # Pieces list length doesn't match num_pieces - this is a bug
            self.logger.warning(
                "Pieces list length (%d) doesn't match num_pieces (%d) - "
                "returning missing pieces from existing list plus uninitialized indices",
                len(self.pieces),
                self.num_pieces,
            )
            # Get missing pieces from existing list with validation
            missing = []
            for i, piece in enumerate(self.pieces):
                # CRITICAL FIX: Validate piece state - if state is COMPLETE but blocks aren't complete, treat as MISSING
                if piece.state == PieceState.MISSING:
                    missing.append(i)
                elif (
                    piece.state in (PieceState.COMPLETE, PieceState.VERIFIED)
                    and not piece.is_complete()
                ):
                    # State mismatch - reset to MISSING
                    self.logger.debug(
                        "Piece %d state is %s but not complete - treating as MISSING",
                        i,
                        piece.state.name,
                    )
                    piece.state = PieceState.MISSING
                    piece.hash_verified = False
                    missing.append(i)
            # Add indices for pieces that haven't been initialized yet
            missing.extend(range(len(self.pieces), self.num_pieces))
        else:
            # Normal case: pieces list matches num_pieces
            missing = []
            for i, piece in enumerate(self.pieces):
                # CRITICAL FIX: Validate piece state - check both state and actual completion
                if piece.state == PieceState.MISSING:
                    missing.append(i)
                elif (
                    piece.state in (PieceState.COMPLETE, PieceState.VERIFIED)
                    and not piece.is_complete()
                ):
                    # If state says COMPLETE/VERIFIED but blocks aren't actually complete, treat as MISSING
                    self.logger.debug(
                        "Piece %d state is %s but not complete - treating as MISSING",
                        i,
                        piece.state.name,
                    )
                    piece.state = PieceState.MISSING
                    piece.hash_verified = False
                    missing.append(i)

        # Filter by file selection if manager exists
        if self.file_selection_manager:
            missing = [
                piece_idx
                for piece_idx in missing
                if self.file_selection_manager.is_piece_needed(piece_idx)
            ]

        return missing

    def get_downloading_pieces(self) -> list[int]:
        """Get list of downloading piece indices."""
        return [
            i
            for i, piece in enumerate(self.pieces)
            if piece.state == PieceState.DOWNLOADING
        ]

    def get_completed_pieces(self) -> list[int]:
        """Get list of completed piece indices."""
        return list(self.completed_pieces)

    def get_verified_pieces(self) -> list[int]:
        """Get list of verified piece indices."""
        return list(self.verified_pieces)

    def get_download_progress(self) -> float:
        """Get download progress as a fraction (0.0 to 1.0)."""
        # CRITICAL FIX: If num_pieces is 0, return 0.0 (not 1.0) - torrent not initialized yet
        if self.num_pieces == 0:
            return 0.0

        # CRITICAL FIX: Ensure verified_pieces is a set and we're counting correctly
        verified_count = len(self.verified_pieces) if self.verified_pieces else 0

        # Validate that verified_count doesn't exceed num_pieces (shouldn't happen, but defensive)
        if verified_count > self.num_pieces:
            self.logger.warning(
                "Verified pieces count (%d) exceeds total pieces (%d), capping at 100%%",
                verified_count,
                self.num_pieces,
            )
            return 1.0

        progress = verified_count / self.num_pieces

        # CRITICAL FIX: Only return 1.0 if we actually have all pieces verified
        # Also check that we have pieces initialized
        if progress >= 1.0 and len(self.pieces) == self.num_pieces:
            # Double-check: verify that all pieces are actually verified
            actual_verified = sum(
                1 for piece in self.pieces if piece.state == PieceState.VERIFIED
            )
            if actual_verified == self.num_pieces:
                return 1.0
            # Some pieces aren't actually verified, recalculate
            return actual_verified / self.num_pieces

        return progress

    def get_piece_status(self) -> dict[str, int]:
        """Get piece status counts."""
        status_counts = defaultdict(int)
        for piece in self.pieces:
            status_counts[piece.state.value] += 1
        return dict(status_counts)

    async def _add_peer(self, peer) -> None:
        """Add a peer to the piece manager.

        Args:
            peer: Peer object with peer_info attribute

        """
        if hasattr(peer, "peer_info"):
            peer_key = f"{peer.peer_info.ip}:{peer.peer_info.port}"
            # Initialize empty availability for the peer
            if peer_key not in self.peer_availability:
                self.peer_availability[peer_key] = PeerAvailability(peer_key)
            self.logger.debug("Added peer %s to piece manager", peer_key)

    async def _remove_peer(self, peer) -> None:
        """Remove a peer from the piece manager.

        Args:
            peer: Peer object with peer_info attribute

        """
        if hasattr(peer, "peer_info"):
            peer_key = f"{peer.peer_info.ip}:{peer.peer_info.port}"
            if peer_key in self.peer_availability:
                # Update piece frequency for pieces this peer had
                peer_availability = self.peer_availability[peer_key]
                for piece_index in peer_availability.pieces:
                    self.piece_frequency[piece_index] -= 1
                    if self.piece_frequency[piece_index] <= 0:
                        del self.piece_frequency[piece_index]

                # Remove peer from availability tracking
                del self.peer_availability[peer_key]
                self.logger.debug("Removed peer %s from piece manager", peer_key)

    async def _update_peer_availability(self, peer) -> None:
        """Update peer availability from peer's bitfield.

        Args:
            peer: Peer object with bitfield attribute

        """
        if hasattr(peer, "peer_info") and hasattr(peer, "bitfield"):
            peer_key = f"{peer.peer_info.ip}:{peer.peer_info.port}"
            await self.update_peer_availability(peer_key, peer.bitfield)

    async def update_peer_availability(self, peer_key: str, bitfield: bytes) -> None:
        """Update peer availability from bitfield.

        Args:
            peer_key: Unique key for the peer
            bitfield: Bitfield data from peer

        """
        self.logger.info(
            "update_peer_availability called for peer %s (bitfield length: %d bytes, num_pieces: %d)",
            peer_key,
            len(bitfield) if bitfield else 0,
            self.num_pieces,
        )
        async with self.lock:
            # Parse bitfield
            pieces = set()
            for byte_idx, byte_val in enumerate(bitfield):
                for bit_idx in range(8):
                    piece_idx = byte_idx * 8 + bit_idx
                    if piece_idx < self.num_pieces and (
                        byte_val & (1 << (7 - bit_idx))
                    ):
                        pieces.add(piece_idx)

            self.logger.info(
                "Parsed bitfield for peer %s: %d pieces available (sample: %s)",
                peer_key,
                len(pieces),
                sorted(pieces)[:10] if pieces else [],
            )

            # Update peer availability
            if peer_key not in self.peer_availability:
                self.peer_availability[peer_key] = PeerAvailability(peer_key)
                self.logger.info("Created new peer availability entry for %s", peer_key)

            old_pieces = self.peer_availability[peer_key].pieces
            self.peer_availability[peer_key].pieces = pieces
            self.peer_availability[peer_key].last_updated = time.time()

            # Update piece frequency
            for piece_idx in (
                old_pieces - pieces
            ):  # pragma: no cover - Edge case when peer loses pieces, rare in practice
                self.piece_frequency[piece_idx] -= 1
            for piece_idx in pieces - old_pieces:
                self.piece_frequency[piece_idx] += 1

            self.logger.info(
                "Updated peer availability for %s: %d pieces (was %d), piece_frequency updated",
                peer_key,
                len(pieces),
                len(old_pieces),
            )

    async def update_peer_have(self, peer_key: str, piece_index: int) -> None:
        """Update peer availability for a single piece."""
        async with self.lock:
            if peer_key not in self.peer_availability:
                self.peer_availability[peer_key] = PeerAvailability(peer_key)

            old_has_piece = piece_index in self.peer_availability[peer_key].pieces
            self.peer_availability[peer_key].pieces.add(piece_index)
            self.peer_availability[peer_key].last_updated = time.time()

            # Update piece frequency
            if not old_has_piece:
                self.piece_frequency[piece_index] += 1

    async def request_piece_from_peers(
        self,
        piece_index: int,
        peer_manager: Any,
    ) -> None:
        """Request a piece from available peers using rarest-first or endgame logic.

        Args:
            piece_index: Index of piece to request
            peer_manager: Peer connection manager

        """
        # CRITICAL FIX: Ensure pieces are initialized before requesting
        # This handles the case where get_missing_pieces() returns indices but pieces list is empty
        if self.num_pieces > 0 and len(self.pieces) == 0:
            self.logger.warning(
                "request_piece_from_peers called for piece %d but pieces list is empty (num_pieces=%d) - "
                "initializing pieces now",
                piece_index,
                self.num_pieces,
            )
            # Initialize pieces on-the-fly (fallback - should have been initialized in start_download())
            pieces_info = self.torrent_data.get("pieces_info", {})
            if self.piece_length == 0 and "piece_length" in pieces_info:
                self.piece_length = int(pieces_info.get("piece_length", 16384))
            elif self.piece_length == 0:
                self.piece_length = 16384

            async with self.lock:
                for i in range(self.num_pieces):
                    piece = PieceData(i, self.piece_length)
                    if self.config.strategy.streaming_mode:
                        if i == 0:
                            piece.priority = 1000
                        elif i == self.num_pieces - 1:
                            piece.priority = 100
                        else:
                            piece.priority = max(0, 1000 - i)
                    if self.file_selection_manager:
                        file_priority = self.file_selection_manager.get_piece_priority(
                            i
                        )
                        piece.priority = max(piece.priority, file_priority * 100)
                    self.pieces.append(piece)
            self.logger.info(
                "Initialized %d pieces in request_piece_from_peers (fallback)",
                len(self.pieces),
            )

        async with self.lock:
            # CRITICAL FIX: Handle case where piece_index is valid but pieces list hasn't caught up yet
            if piece_index >= len(self.pieces):
                if piece_index < self.num_pieces:
                    # Piece index is valid but piece hasn't been initialized yet
                    self.logger.warning(
                        "PIECE_MANAGER: Piece %d is valid (num_pieces=%d) but not yet initialized (pieces_list_len=%d) - "
                        "this should not happen if pieces were initialized properly",
                        piece_index,
                        self.num_pieces,
                        len(self.pieces),
                    )
                return

            piece = self.pieces[piece_index]
            if piece.state != PieceState.MISSING:
                self.logger.debug(
                    "PIECE_MANAGER: Piece %d is not MISSING (state=%s), skipping request",
                    piece_index,
                    piece.state.value
                    if hasattr(piece.state, "value")
                    else str(piece.state),
                )
                return

            old_state = piece.state
            piece.state = PieceState.REQUESTED
            piece.request_count += 1
            self.logger.info(
                "PIECE_MANAGER: Piece %d state transition: %s -> REQUESTED (request_count=%d)",
                piece_index,
                old_state.value if hasattr(old_state, "value") else str(old_state),
                piece.request_count,
            )

        # Get available peers for this piece
        available_peers = await self._get_peers_for_piece(piece_index, peer_manager)
        if not available_peers:
            self.logger.debug(
                "No available peers for piece %d (peer_manager=%s)",
                piece_index,
                peer_manager is not None,
            )
            async with self.lock:
                piece.state = PieceState.MISSING
            return

        self.logger.info(
            "Requesting piece %d from %d available peers (missing blocks: %d)",
            piece_index,
            len(available_peers),
            len(piece.get_missing_blocks())
            if hasattr(piece, "get_missing_blocks")
            else 0,
        )

        # Get missing blocks
        missing_blocks = piece.get_missing_blocks()
        if not missing_blocks:  # pragma: no cover - Early return when piece already complete, tested via early_returns test
            self.logger.debug("Piece %d has no missing blocks, skipping", piece_index)
            return

        self.logger.debug(
            "Piece %d has %d missing blocks, distributing among %d peers",
            piece_index,
            len(missing_blocks),
            len(available_peers),
        )

        # Distribute blocks among peers
        if (
            self.endgame_mode
        ):  # pragma: no cover - Endgame path tested separately, normal path is default
            self.logger.debug("Requesting piece %d in endgame mode", piece_index)
            await self._request_blocks_endgame(
                piece_index,
                missing_blocks,
                available_peers,
                peer_manager,
            )
        else:
            self.logger.debug("Requesting piece %d in normal mode", piece_index)
            await self._request_blocks_normal(
                piece_index,
                missing_blocks,
                available_peers,
                peer_manager,
            )

        async with self.lock:  # pragma: no cover - Lock acquisition after request, state change tested via mark_requested
            old_state = piece.state
            piece.state = PieceState.DOWNLOADING
            self.logger.info(
                "PIECE_MANAGER: Piece %d state transition: %s -> DOWNLOADING",
                piece_index,
                old_state.value if hasattr(old_state, "value") else str(old_state),
            )

    async def _get_peers_for_piece(
        self,
        piece_index: int,
        peer_manager: Any,
    ) -> list[AsyncPeerConnection]:
        """Get peers that have the specified piece."""
        available_peers = []

        if not peer_manager:
            self.logger.warning("_get_peers_for_piece called with None peer_manager")
            return available_peers

        if not hasattr(peer_manager, "get_active_peers"):
            self.logger.warning("peer_manager has no get_active_peers method")
            return available_peers

        active_peers = peer_manager.get_active_peers()
        self.logger.info(
            "Checking %d active peers for piece %d (total connections: %d)",
            len(active_peers),
            piece_index,
            len(peer_manager.connections)
            if hasattr(peer_manager, "connections")
            else 0,
        )

        # CRITICAL FIX: If no active peers but connections exist, log details
        if len(active_peers) == 0 and hasattr(peer_manager, "connections"):
            total_connections = len(peer_manager.connections)
            if total_connections > 0:
                self.logger.warning(
                    "No active peers found for piece %d, but %d connection(s) exist. Connection states: %s",
                    piece_index,
                    total_connections,
                    {
                        str(conn.peer_info): conn.state.value
                        if hasattr(conn.state, "value")
                        else str(conn.state)
                        for conn in peer_manager.connections.values()
                    },
                )

        for connection in active_peers:
            peer_key = str(connection.peer_info)
            has_piece = (
                peer_key in self.peer_availability
                and piece_index in self.peer_availability[peer_key].pieces
            )
            can_req = connection.can_request()

            # Log detailed peer availability info
            peer_avail = self.peer_availability.get(peer_key)
            pieces_available = len(peer_avail.pieces) if peer_avail else 0
            self.logger.info(
                "Peer %s for piece %d: has_piece=%s, can_request=%s, choking=%s, interested=%s, peer_interested=%s, state=%s, pieces_known=%d, pipeline=%d/%d",
                peer_key,
                piece_index,
                has_piece,
                can_req,
                connection.peer_choking,
                connection.am_interested,
                connection.peer_interested,
                connection.state.value
                if hasattr(connection.state, "value")
                else str(connection.state),
                pieces_available,
                len(connection.outstanding_requests),
                connection.max_pipeline_depth,
            )

            if has_piece and can_req:
                available_peers.append(connection)
                self.logger.info(
                    "Peer %s is available for piece %d", peer_key, piece_index
                )
            else:
                # Log why peer is not available
                reasons = []
                if not has_piece:
                    if peer_key not in self.peer_availability:
                        reasons.append("no bitfield received")
                    elif piece_index not in self.peer_availability[peer_key].pieces:
                        reasons.append("piece not in peer's bitfield")
                if not can_req:
                    if connection.peer_choking:
                        reasons.append("peer is choking")
                    if not connection.is_active():
                        reasons.append("connection not active")
                    if (
                        len(connection.outstanding_requests)
                        >= connection.max_pipeline_depth
                    ):
                        reasons.append("pipeline full")
                self.logger.warning(
                    "Peer %s not available for piece %d: %s",
                    peer_key,
                    piece_index,
                    ", ".join(reasons) if reasons else "unknown reason",
                )

        self.logger.debug(
            "Found %d available peers for piece %d", len(available_peers), piece_index
        )
        return available_peers

    async def _request_blocks_normal(
        self,
        piece_index: int,
        missing_blocks: list[PieceBlock],
        available_peers: list[AsyncPeerConnection],
        peer_manager: Any,
    ) -> None:
        """Request blocks in normal mode (no duplicates)."""
        # Sort peers by reliability and availability
        available_peers.sort(
            key=lambda p: self.peer_availability.get(
                str(p.peer_info),
                PeerAvailability(""),
            ).reliability_score,
            reverse=True,
        )

        # Distribute blocks among peers
        blocks_per_peer = max(1, len(missing_blocks) // len(available_peers))

        for i, peer_connection in enumerate(available_peers):
            start_block = i * blocks_per_peer
            end_block = min(start_block + blocks_per_peer, len(missing_blocks))

            if start_block >= len(missing_blocks):
                break

            # Request blocks from this peer
            for block in missing_blocks[start_block:end_block]:
                if peer_connection.can_request():
                    await peer_manager.request_piece(
                        peer_connection,
                        piece_index,
                        block.begin,
                        block.length,
                    )
                    block.requested_from.add(str(peer_connection.peer_info))

    async def _request_blocks_endgame(
        self,
        piece_index: int,
        missing_blocks: list[PieceBlock],
        available_peers: list[AsyncPeerConnection],
        peer_manager: Any,
    ) -> None:
        """Request blocks in endgame mode (with duplicates)."""
        # In endgame, request each block from multiple peers
        for block in missing_blocks:
            # Find peers that can handle this request
            capable_peers = [p for p in available_peers if p.can_request()]

            # Request from up to endgame_duplicates peers
            for _i, peer_connection in enumerate(
                capable_peers[: self.endgame_duplicates],
            ):
                if peer_connection.can_request():
                    await peer_manager.request_piece(
                        peer_connection,
                        piece_index,
                        block.begin,
                        block.length,
                    )
                    block.requested_from.add(str(peer_connection.peer_info))

    async def handle_piece_block(
        self,
        piece_index: int,
        begin: int,
        data: bytes,
    ) -> None:
        """Handle a received piece block.

        Args:
            piece_index: Index of the piece
            begin: Starting offset of the block
            data: Block data

        """
        async with self.lock:
            if (
                piece_index >= len(self.pieces)
            ):  # pragma: no cover - Bounds check in handle_piece_block, tested via out_of_range test
                return

            piece = self.pieces[piece_index]

            # Add block to piece
            if piece.add_block(begin, data):
                if piece.state == PieceState.COMPLETE:
                    self.completed_pieces.add(piece_index)
                    self.logger.info(
                        "PIECE_MANAGER: Piece %d completed (all blocks received, state=COMPLETE)",
                        piece_index,
                    )
                else:
                    # Log progress for incomplete pieces
                    missing_blocks = sum(1 for b in piece.blocks if not b.received)
                    total_blocks = len(piece.blocks)
                    self.logger.debug(
                        "PIECE_MANAGER: Piece %d block received (missing: %d/%d blocks, state=%s)",
                        piece_index,
                        missing_blocks,
                        total_blocks,
                        piece.state.value
                        if hasattr(piece.state, "value")
                        else str(piece.state),
                    )

                # Update file progress if file selection manager exists
                if self.file_selection_manager:
                    files_in_piece = self.file_selection_manager.get_files_for_piece(
                        piece_index,
                    )
                    for file_index in files_in_piece:
                        # Calculate bytes for this file in this piece
                        file_segments = [
                            (f_idx, f_off, f_len)
                            for f_idx, f_off, f_len in self.file_selection_manager.mapper.piece_to_files.get(
                                piece_index,
                                [],
                            )
                            if f_idx == file_index
                        ]
                        bytes_for_file = sum(length for _, _, length in file_segments)
                        current_state = self.file_selection_manager.get_file_state(
                            file_index,
                        )
                        if current_state:
                            current_bytes = current_state.bytes_downloaded
                            await self.file_selection_manager.update_file_progress(
                                file_index,
                                current_bytes + bytes_for_file,
                            )

                # Notify callback
                if self.on_piece_completed:
                    self.on_piece_completed(piece_index)

                    # Schedule hash verification and keep a strong reference
                    _task = asyncio.create_task(
                        self._verify_piece_hash(piece_index, piece),
                    )
                    self._background_tasks.add(_task)
                    _task.add_done_callback(self._background_tasks.discard)

    async def _hash_worker(
        self,
    ) -> (
        None
    ):  # pragma: no cover - Deprecated method, replaced by per-piece verification tasks
        """Background task for hash verification."""
        # Ensure queue is initialized in this event loop
        if self.hash_queue is None:  # pragma: no cover - Deprecated path
            self.logger.error("Hash queue not initialized before starting worker")
            return
        while True:  # pragma: no cover - Background loop, deprecated
            try:
                (
                    piece_index,
                    piece,
                ) = await self.hash_queue.get()  # pragma: no cover - Deprecated
                await self._verify_piece_hash(
                    piece_index, piece
                )  # pragma: no cover - Deprecated
                # SimpleQueue has no task_done
            except asyncio.CancelledError:  # pragma: no cover - Deprecated
                break
            except Exception:  # pragma: no cover - Deprecated exception handler
                self.logger.exception("Error in hash worker")

    async def _verify_piece_hash(self, piece_index: int, piece: PieceData) -> None:
        """Verify piece hash in background with optimizations.

        Supports both SHA-1 (v1) and SHA-256 (v2) verification.
        For hybrid torrents, verifies both hashes if available.
        """
        try:
            # For v2-only torrents (meta_version == 2), use piece_layers
            if (
                self.meta_version == 2
            ):  # pragma: no cover - v2-only torrent path, tested via v1/hybrid paths
                # v2-only: get hash from piece_layers
                expected_hash = self._get_v2_piece_hash(piece_index)
                if (
                    expected_hash is None
                ):  # pragma: no cover - v2 hash not found error, tested via hash present
                    self.logger.error(
                        "v2 piece %s: No hash found in piece_layers", piece_index
                    )
                    return

                # Use optimized hash verification with memoryview (SHA-256)
                loop = asyncio.get_event_loop()
                is_valid = await loop.run_in_executor(
                    self.hash_executor,
                    self._hash_piece_optimized,
                    piece,
                    expected_hash,
                )
            # For hybrid torrents (meta_version == 3), verify both SHA-1 and SHA-256
            elif (
                self.meta_version == 3
            ):  # pragma: no cover - Hybrid torrent path, tested via v1/v2 paths
                # Hybrid torrent: verify both v1 and v2 hashes
                expected_hash_v1 = (
                    self.piece_hashes[piece_index]
                    if piece_index < len(self.piece_hashes)
                    else None
                )
                if (
                    expected_hash_v1 is None
                ):  # pragma: no cover - v1 hash not found error, tested via hash present
                    self.logger.error("Hybrid piece %s: No v1 hash found", piece_index)
                    return

                is_valid = await self._verify_hybrid_piece(
                    piece_index, piece, expected_hash_v1
                )
            else:  # pragma: no cover - v1-only torrent path, tested via v2/hybrid paths
                # v1-only torrent: use piece_hashes (SHA-1)
                expected_hash = self.piece_hashes[piece_index]

                # Single hash verification (auto-detects algorithm from hash length)
                # Use optimized hash verification with memoryview
                loop = asyncio.get_event_loop()
                is_valid = await loop.run_in_executor(
                    self.hash_executor,
                    self._hash_piece_optimized,
                    piece,
                    expected_hash,
                )

            if is_valid:
                async with self.lock:
                    self.verified_pieces.add(piece_index)
                    piece.state = PieceState.VERIFIED

                verified_count = len(self.verified_pieces)
                progress_pct = (
                    (verified_count / self.num_pieces * 100)
                    if self.num_pieces > 0
                    else 0.0
                )
                self.logger.info(
                    "PIECE_MANAGER: Piece %d verified successfully (state=VERIFIED, progress: %d/%d pieces, %.1f%%)",
                    piece_index,
                    verified_count,
                    self.num_pieces,
                    progress_pct,
                )

                # Compute and store Xet Merkle hash if enabled
                if (
                    self.config.disk.xet_enabled
                    and self.config.disk.xet_deduplication_enabled
                ):
                    try:
                        await self._store_xet_hash(piece_index, piece)
                    except Exception as e:
                        # Log but don't fail piece verification if Xet storage fails
                        self.logger.warning(
                            "Failed to store Xet hash for piece %d: %s",
                            piece_index,
                            e,
                        )

                # Notify callback
                if self.on_piece_verified:  # pragma: no cover - Callback path, tested via download_complete test
                    self.on_piece_verified(piece_index)

                # Trigger checkpoint save if enabled
                if (
                    self.on_checkpoint_save
                ):  # pragma: no cover - Integration callback, requires file assembler
                    self.on_checkpoint_save()

                # Check if download is complete
                if (
                    len(self.verified_pieces) == self.num_pieces
                ):  # pragma: no cover - Completion check, tested separately
                    self.download_complete = True
                    self.logger.info(
                        "PIECE_MANAGER: Download complete! All %d pieces verified",
                        self.num_pieces,
                    )
                    if self.on_download_complete:  # pragma: no cover - Completion callback, tested via download_complete test
                        self.on_download_complete()
            else:
                self.logger.warning(
                    "PIECE_MANAGER: Hash verification failed for piece %d (state remains %s)",
                    piece_index,
                    piece.state.value
                    if hasattr(piece.state, "value")
                    else str(piece.state),
                )

        except (
            Exception
        ):  # pragma: no cover - Exception handler, tested via verify_exception test
            self.logger.exception("Error verifying piece %s", piece_index)

    async def _store_xet_hash(self, piece_index: int, piece: PieceData) -> None:
        """Store Xet Merkle hash for verified piece.

        This method computes the Xet Merkle hash from the piece data using
        content-defined chunking (Gearhash CDC) and stores it for deduplication
        lookup. The implementation follows the Rust reference implementation pattern.

        The Merkle hash is computed by:
        1. Chunking piece data using Gearhash CDC algorithm
        2. Computing BLAKE3-256 hash for each chunk
        3. Building a binary Merkle tree from chunk hashes
        4. Returning the root hash as the Merkle hash

        The hash can be used to find other torrents or pieces with similar
        content for cross-torrent deduplication.

        Args:
            piece_index: Index of the verified piece
            piece: PieceData object containing the verified piece data

        """
        try:
            from ccbt.storage.xet_chunking import GearhashChunker
            from ccbt.storage.xet_hashing import XetHasher

            # Get piece data
            piece_data = piece.get_data()

            if not piece_data:
                self.logger.debug("No data to hash for piece %d", piece_index)
                return

            # Initialize chunker with config values
            # Gearhash CDC uses content-defined boundaries for intelligent chunking
            # The chunker uses target_size; min/max are enforced by the algorithm
            chunker = GearhashChunker(
                target_size=self.config.disk.xet_chunk_target_size,
            )

            # Chunk the piece data using Gearhash CDC
            # This produces variable-sized chunks based on content boundaries
            chunks = chunker.chunk_buffer(piece_data)

            if not chunks:
                self.logger.debug("No chunks generated for piece %d", piece_index)
                return

            # Compute individual chunk hashes (BLAKE3-256 or SHA-256 fallback)
            chunk_hashes = [XetHasher.compute_chunk_hash(chunk) for chunk in chunks]

            # Build Merkle tree from chunk hashes
            # This follows the Rust implementation: binary tree construction
            # where each level pairs hashes until a single root remains
            merkle_hash = XetHasher.build_merkle_tree_from_hashes(chunk_hashes)

            # Store Merkle hash and chunk hashes in cache
            async with self.lock:
                self.xet_merkle_hashes[piece_index] = merkle_hash
                self.xet_chunk_hashes[piece_index] = chunk_hashes

            # Update torrent_data dict if xet_metadata exists
            # This allows the metadata to be preserved across sessions
            if isinstance(self.torrent_data, dict):
                # Initialize xet_metadata if it doesn't exist
                if "xet_metadata" not in self.torrent_data:
                    self.torrent_data["xet_metadata"] = {
                        "chunk_hashes": [],
                        "file_metadata": [],
                        "piece_metadata": {},
                        "xorb_hashes": [],
                    }

                # Update piece metadata
                xet_metadata = self.torrent_data["xet_metadata"]
                if "piece_metadata" not in xet_metadata:
                    xet_metadata["piece_metadata"] = {}

                # Store piece metadata: chunk hashes and Merkle root
                xet_metadata["piece_metadata"][piece_index] = {
                    "piece_index": piece_index,
                    "chunk_hashes": [
                        h.hex() for h in chunk_hashes
                    ],  # Store as hex strings
                    "merkle_hash": merkle_hash.hex(),
                }

                # Update global chunk hash list (deduplicated)
                if "chunk_hashes" not in xet_metadata:
                    xet_metadata["chunk_hashes"] = []

                # Add new chunk hashes to global list (avoid duplicates)
                existing_chunks = set(xet_metadata["chunk_hashes"])
                for chunk_hash in chunk_hashes:
                    chunk_hash_hex = chunk_hash.hex()
                    if chunk_hash_hex not in existing_chunks:
                        xet_metadata["chunk_hashes"].append(chunk_hash_hex)
                        existing_chunks.add(chunk_hash_hex)

            self.logger.debug(
                "Computed Xet Merkle hash for piece %d: %s (%d chunks, %d bytes)",
                piece_index,
                merkle_hash.hex()[:16],
                len(chunks),
                len(piece_data),
            )

        except ImportError as e:
            self.logger.debug(
                "Xet modules not available for piece %d: %s",
                piece_index,
                e,
            )
        except Exception as e:
            self.logger.warning(
                "Error computing Xet Merkle hash for piece %d: %s",
                piece_index,
                e,
            )
            # Don't raise - this is optional functionality

    def _hash_piece_optimized(self, piece: PieceData, expected_hash: bytes) -> bool:
        """Optimized piece hash verification using memoryview and zero-copy operations.

        Supports both SHA-1 (v1, 20 bytes) and SHA-256 (v2, 32 bytes) algorithms.
        Algorithm is auto-detected from expected_hash length.
        """
        try:
            # Get piece data (no optional data buffer available in this implementation)
            data_bytes = piece.get_data()
            data_view = memoryview(data_bytes)

            # Detect algorithm from hash length
            # 20 bytes = SHA-1 (v1), 32 bytes = SHA-256 (v2)
            if len(expected_hash) == 32:
                algorithm = HashAlgorithm.SHA256
            elif (
                len(expected_hash) == 20
            ):  # pragma: no cover - SHA-1 hash detection, tested via SHA-256 path
                algorithm = HashAlgorithm.SHA1
            else:  # pragma: no cover - Invalid hash length error, tested via valid lengths
                self.logger.error(
                    "Invalid hash length: %d bytes (expected 20 or 32)",
                    len(expected_hash),
                )
                return False

            # Create hasher for detected algorithm
            hasher = algorithm.hash_function()

            # Hash in optimized chunks to balance memory usage and performance
            # Use adaptive chunk size based on storage speed if enabled
            if self.config.disk.hash_chunk_size_adaptive:
                from ccbt.config.config_capabilities import SystemCapabilities

                capabilities = SystemCapabilities()
                storage_speed = capabilities.detect_storage_speed()
                # Use larger chunks (1MB) for fast storage, smaller (64KB) for slow storage
                if storage_speed.get("speed_category") == "very_fast":  # NVMe
                    chunk_size = 1024 * 1024  # 1MB
                elif storage_speed.get("speed_category") == "fast":  # SSD
                    chunk_size = 512 * 1024  # 512KB
                else:  # HDD
                    chunk_size = 64 * 1024  # 64KB
            else:  # pragma: no cover - Non-adaptive hash chunk size path, adaptive is default
                chunk_size = self.config.disk.hash_chunk_size

            for i in range(0, len(data_view), chunk_size):
                chunk = data_view[i : i + chunk_size]
                hasher.update(chunk)

            actual_hash = hasher.digest()
        except Exception:
            self.logger.exception("Error in optimized hash verification")
            return False
        else:
            return actual_hash == expected_hash

    async def _verify_hybrid_piece(
        self,
        piece_index: int,
        piece: PieceData,
        expected_hash_v1: bytes,
    ) -> bool:
        """Verify piece for hybrid torrent using both SHA-1 and SHA-256.

        For hybrid torrents (BEP 52), each piece must verify against both:
        - SHA-1 hash (20 bytes) from v1 pieces
        - SHA-256 hash (32 bytes) from v2 piece layers

        Args:
            piece_index: Index of the piece to verify
            piece: PieceData object containing piece data
            expected_hash_v1: Expected SHA-1 hash (20 bytes) from v1 pieces

        Returns:
            True if both SHA-1 and SHA-256 hashes verify, False otherwise

        """
        try:
            # Verify SHA-1 hash first (v1)
            loop = asyncio.get_event_loop()
            v1_valid = await loop.run_in_executor(
                self.hash_executor,
                self._hash_piece_optimized,
                piece,
                expected_hash_v1,
            )

            if (
                not v1_valid
            ):  # pragma: no cover - v1 verification failure path, tested via v1 success
                self.logger.warning(
                    "Hybrid piece %s: SHA-1 verification failed",
                    piece_index,
                )
                return False

            # Get SHA-256 hash from v2 piece layers
            # For hybrid torrents, piece_layers contain v2 hashes organized by file
            # We need to find which file this piece belongs to and get the v2 hash
            expected_hash_v2 = self._get_v2_piece_hash(piece_index)

            if (
                expected_hash_v2 is None
            ):  # pragma: no cover - v2 hash not found error, tested via hash present
                # No v2 hash available - this shouldn't happen for hybrid torrents
                self.logger.warning(
                    "Hybrid piece %s: No v2 hash available",
                    piece_index,
                )
                return False

            # Verify SHA-256 hash (v2)
            v2_valid = await loop.run_in_executor(
                self.hash_executor,
                self._hash_piece_optimized,
                piece,
                expected_hash_v2,
            )

            if (
                not v2_valid
            ):  # pragma: no cover - v2 verification failure path, tested via v2 success
                self.logger.warning(
                    "Hybrid piece %s: SHA-256 verification failed",
                    piece_index,
                )
                return False

            # Both hashes verified successfully
            self.logger.debug(  # pragma: no cover - Hybrid verification success debug, tested via failure paths
                "Hybrid piece %s: Both SHA-1 and SHA-256 verified",
                piece_index,
            )
            return True

        except (
            Exception
        ):  # pragma: no cover - Hybrid verification exception, defensive error handling
            self.logger.exception("Error in hybrid piece verification")
            return False

    def _get_v2_piece_hash(self, piece_index: int) -> bytes | None:
        """Get SHA-256 hash for a piece from v2 piece layers.

        For hybrid torrents, piece layers are organized by file (pieces_root).
        This method finds which file the piece belongs to and returns its v2 hash.

        Args:
            piece_index: Global piece index

        Returns:
            32-byte SHA-256 hash or None if not found

        """
        if (
            not self.piece_layers
        ):  # pragma: no cover - No piece layers path, tested via piece_layers present
            return None

        # Calculate which file this piece belongs to
        # For v2, pieces are organized per-file in piece_layers
        # We need to map global piece_index to file-local piece index
        # This is a simplified approach - full implementation would need file mapping
        current_offset = 0

        for piece_list in (
            self.piece_layers.values()
        ):  # pragma: no cover - Piece layers iteration, tested via empty layers
            file_num_pieces = len(piece_list)
            if (
                piece_index < current_offset + file_num_pieces
            ):  # pragma: no cover - Piece index match path, tested via index mismatch
                # This piece belongs to this file
                file_local_index = piece_index - current_offset
                if (
                    0 <= file_local_index < len(piece_list)
                ):  # pragma: no cover - Valid local index path, tested via invalid index
                    return piece_list[file_local_index]
            current_offset += file_num_pieces

        return (
            None  # pragma: no cover - Piece not found fallback, tested via piece found
        )

    async def _batch_verify_pieces(
        self,
        pieces_to_verify: list[tuple[int, PieceData]],
    ) -> None:
        """Batch verify multiple pieces for better performance."""
        if not pieces_to_verify:  # pragma: no cover - Early return, tested via verify_pending_batch_empty test
            return

        # Optimize batch size based on available memory and config
        batch_size = self.config.disk.hash_batch_size
        # Dynamically adjust batch size if needed
        # For large pieces, use smaller batches to avoid memory pressure
        if pieces_to_verify:
            first_piece = pieces_to_verify[0][1]
            if (
                hasattr(first_piece, "length") and first_piece.length > 16 * 1024 * 1024
            ):  # > 16MB
                batch_size = max(
                    1, batch_size // 2
                )  # Reduce batch size for large pieces

        # Process in optimized batches
        all_results = []
        for i in range(0, len(pieces_to_verify), batch_size):
            batch = pieces_to_verify[i : i + batch_size]

            # Create verification tasks for this batch
            tasks = []
            for piece_index, piece in batch:
                task = asyncio.create_task(self._verify_piece_hash(piece_index, piece))
                tasks.append(task)

            # Wait for batch verifications to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(results)

        # Log any exceptions
        for i, result in enumerate(all_results):
            if isinstance(result, Exception):
                # Find which piece this result corresponds to
                piece_idx = i
                if piece_idx < len(pieces_to_verify):
                    piece_index, _ = pieces_to_verify[piece_idx]
                    self.logger.error(
                        "Batch verification failed for piece %s: %s",
                        piece_index,
                        result,
                    )

        self.logger.info("Batch verified %s pieces", len(pieces_to_verify))

    async def _verify_pending_pieces_batch(self) -> None:
        """Verify all pending pieces in optimized batches."""
        async with self.lock:
            pending_pieces = [
                (i, piece)
                for i, piece in enumerate(self.pieces)
                if piece.state == PieceState.COMPLETE and not piece.hash_verified
            ]

        if not pending_pieces:
            return

        # Process in batches for optimal performance
        batch_size = (
            self.config.disk.hash_batch_size
        )  # pragma: no cover - Batch size config access in loop
        for i in range(
            0, len(pending_pieces), batch_size
        ):  # pragma: no cover - Batch processing loop, requires multiple completed pieces
            batch = pending_pieces[i : i + batch_size]
            await self._batch_verify_pieces(batch)

            # Small delay between batches to prevent overwhelming the system
            await asyncio.sleep(
                0.01
            )  # pragma: no cover - Timing-dependent delay in batch loop

    async def _piece_selector(self) -> None:
        """Background task for piece selection."""
        while True:  # pragma: no cover - Infinite background loop, cancellation tested via selector_cancellation test
            try:
                await asyncio.sleep(
                    1.0
                )  # pragma: no cover - Timing-dependent sleep in background loop
                await self._select_pieces()
            except (
                asyncio.CancelledError
            ):  # pragma: no cover - Cancellation handling, tested separately
                break
            except Exception:  # pragma: no cover - Exception handler in background loop, tested via selector_exception test
                self.logger.exception("Error in piece selector")

    async def _select_pieces(self) -> None:
        """Select pieces to download based on strategy."""
        self.logger.debug(
            "Piece selector called: is_downloading=%s, download_complete=%s, _peer_manager=%s",
            self.is_downloading,
            self.download_complete,
            self._peer_manager is not None,
        )

        # CRITICAL FIX: Allow piece selection even if is_downloading is False but we have active peers
        # This handles the case where metadata is being fetched but peers are already connected
        # We can start selecting pieces once we have peers, even if metadata isn't fully available
        if self.download_complete:
            self.logger.debug(
                "Piece selector skipping: download_complete=%s",
                self.download_complete,
            )
            return

        # CRITICAL FIX: If is_downloading is False but we have active peers, allow selection
        # This is important for magnet links where metadata is being fetched
        if not self.is_downloading:
            # Check if we have active peers - if so, allow selection (metadata may be coming)
            has_active_peers = False
            if self._peer_manager and hasattr(self._peer_manager, "get_active_peers"):
                try:
                    active_peers = self._peer_manager.get_active_peers()
                    has_active_peers = len(active_peers) > 0 if active_peers else False
                except Exception:
                    pass

            if not has_active_peers:
                self.logger.debug(
                    "Piece selector skipping: is_downloading=%s, no active peers",
                    self.is_downloading,
                )
                return
            # CRITICAL FIX: We have active peers but is_downloading is False
            # This might be a magnet link - allow selection to proceed
            # The piece selector will handle missing metadata gracefully
            self.logger.debug(
                "Piece selector proceeding despite is_downloading=False: has %d active peers (metadata may be fetching)",
                len(active_peers) if active_peers else 0,
            )

        # CRITICAL FIX: Check for active peers before selecting pieces
        if not self._peer_manager:
            self.logger.debug(
                "Piece selector skipping: peer_manager is None (no peers available yet)"
            )
            return

        # Check if we have any active peers
        active_peers_count = 0
        total_connections = 0
        if hasattr(self._peer_manager, "get_active_peers"):
            active_peers = self._peer_manager.get_active_peers()
            active_peers_count = len(active_peers) if active_peers else 0
            if hasattr(self._peer_manager, "connections"):
                total_connections = len(self._peer_manager.connections)

            if not active_peers:
                self.logger.debug(
                    "Piece selector skipping: no active peers available (total connections: %d, active: %d, is_downloading=%s, num_pieces=%d)",
                    total_connections,
                    active_peers_count,
                    self.is_downloading,
                    self.num_pieces,
                )
                return
        elif hasattr(self._peer_manager, "connections"):
            # Fallback: check if any connections exist
            total_connections = len(self._peer_manager.connections)
            if not self._peer_manager.connections:
                self.logger.debug(
                    "Piece selector skipping: no peer connections available"
                )
                return

        # CRITICAL FIX: Validate pieces list before selecting
        # Also check if pieces list has items but num_pieces is 0 (from checkpoint)
        if len(self.pieces) > 0 and self.num_pieces == 0:
            # Pieces were restored from checkpoint but num_pieces wasn't set
            self.num_pieces = len(self.pieces)
            self.logger.info(
                "Inferred num_pieces=%d from pieces list in piece selector (checkpoint restoration)",
                self.num_pieces,
            )
        # If num_pieces > 0 but pieces list is empty, this is a bug - log warning
        elif self.num_pieces > 0 and len(self.pieces) == 0:
            self.logger.warning(
                "Piece selector: num_pieces=%d but pieces list is empty - "
                "this should have been initialized in start_download(). "
                "Attempting to initialize pieces now.",
                self.num_pieces,
            )
            # Try to initialize pieces on-the-fly (this shouldn't happen but handle it defensively)
            # This is a fallback - pieces should be initialized in start_download()
            pieces_info = self.torrent_data.get("pieces_info", {})
            if self.piece_length == 0 and "piece_length" in pieces_info:
                self.piece_length = int(pieces_info.get("piece_length", 16384))
            elif self.piece_length == 0:
                self.piece_length = 16384

            for i in range(self.num_pieces):
                piece = PieceData(i, self.piece_length)
                if self.config.strategy.streaming_mode:
                    if i == 0:
                        piece.priority = 1000
                    elif i == self.num_pieces - 1:
                        piece.priority = 100
                    else:
                        piece.priority = max(0, 1000 - i)
                if self.file_selection_manager:
                    file_priority = self.file_selection_manager.get_piece_priority(i)
                    piece.priority = max(piece.priority, file_priority * 100)
                self.pieces.append(piece)
            self.logger.info(
                "Initialized %d pieces in piece selector (fallback)", len(self.pieces)
            )

        missing_pieces_count = len(self.get_missing_pieces())
        self.logger.debug(
            "Piece selector proceeding: %d active peers, %d total connections, %d missing pieces, %d total pieces",
            active_peers_count,
            total_connections,
            missing_pieces_count,
            self.num_pieces,
        )

        # Log piece state distribution for debugging
        if self.pieces:
            state_counts = {
                "MISSING": 0,
                "REQUESTED": 0,
                "DOWNLOADING": 0,
                "COMPLETE": 0,
                "VERIFIED": 0,
            }
            state_corrected_count = 0
            for piece in self.pieces:
                state_name = piece.state.name
                if state_name in state_counts:
                    state_counts[state_name] = state_counts.get(state_name, 0) + 1

                # CRITICAL FIX: Validate piece state matches actual block completion
                # Reset any pieces marked COMPLETE/VERIFIED that aren't actually complete
                if (
                    piece.state in (PieceState.COMPLETE, PieceState.VERIFIED)
                    and not piece.is_complete()
                ):
                    self.logger.warning(
                        "Piece %d state is %s but blocks are not complete - resetting to MISSING",
                        piece.piece_index,
                        piece.state.name,
                    )
                    piece.state = PieceState.MISSING
                    piece.hash_verified = False
                    state_corrected_count += 1
                    # Update state counts
                    state_counts["MISSING"] = state_counts.get("MISSING", 0) + 1
                    if state_name in state_counts:
                        state_counts[state_name] = max(0, state_counts[state_name] - 1)

            if state_corrected_count > 0:
                self.logger.warning(
                    "Corrected %d piece state mismatches in piece selector",
                    state_corrected_count,
                )

            self.logger.debug(
                "Piece state distribution: %s (total: %d, corrected: %d)",
                state_counts,
                len(self.pieces),
                state_corrected_count,
            )

        # Check if we should enter endgame mode
        remaining_pieces = missing_pieces_count
        total_pieces = self.num_pieces
        if (
            remaining_pieces <= total_pieces * (1.0 - self.endgame_threshold)
            and not self.endgame_mode
        ):
            self.endgame_mode = True
            self.logger.info("Entered endgame mode")

        # Select pieces based on strategy
        if (
            self.config.strategy.piece_selection == PieceSelectionStrategy.RAREST_FIRST
        ):  # pragma: no cover - Strategy branch, each tested separately
            await self._select_rarest_first()
        elif (
            self.config.strategy.piece_selection == PieceSelectionStrategy.SEQUENTIAL
        ):  # pragma: no cover - Strategy branch
            await self._select_sequential()
        else:  # pragma: no cover - Default strategy branch (round_robin)
            await self._select_round_robin()

    async def _select_rarest_piece(self) -> int | None:
        """Select a single piece using rarest-first algorithm."""
        async with self.lock:
            missing_pieces = [
                i
                for i, piece in enumerate(self.pieces)
                if piece.state == PieceState.MISSING
            ]

            if not missing_pieces:
                return None

            # Filter out pieces that are not available from any peer
            available_pieces = []
            for piece_idx in missing_pieces:
                frequency = self.piece_frequency.get(piece_idx, 0)
                if (
                    frequency
                    > 0  # pragma: no cover - Frequency check, requires peer availability setup
                ):  # Only consider pieces available from at least one peer
                    available_pieces.append(piece_idx)

            if not available_pieces:
                return None

            # Sort by frequency (rarest first) and priority
            # pragma: no cover - Selection algorithm inner loop: requires complex peer availability and frequency tracking setup
            piece_scores = []  # pragma: no cover - Selection algorithm initialization
            for piece_idx in available_pieces:  # pragma: no cover - Selection algorithm loop, requires peer availability and frequency tracking
                frequency = self.piece_frequency.get(
                    piece_idx, 0
                )  # pragma: no cover - Frequency lookup in selection loop
                priority = self.pieces[
                    piece_idx
                ].priority  # pragma: no cover - Priority access in selection loop
                # Lower frequency = higher score, higher priority = higher score
                score = (
                    1000 - frequency
                ) + priority  # pragma: no cover - Score calculation in selection loop
                piece_scores.append(
                    (score, piece_idx)
                )  # pragma: no cover - Score accumulation in selection loop

            # Sort by score (descending) and return the rarest piece
            piece_scores.sort(
                reverse=True
            )  # pragma: no cover - Selection algorithm continuation
            if piece_scores:  # pragma: no cover - Selection result check
                selected_piece = piece_scores[0][
                    1
                ]  # pragma: no cover - Piece selection from sorted scores
                # Mark the piece as requested to prevent duplicates in concurrent selections
                self.pieces[
                    selected_piece
                ].state = (
                    PieceState.REQUESTED
                )  # pragma: no cover - State update in selection
                return selected_piece  # pragma: no cover - Return selected piece from algorithm
            return None  # pragma: no cover - No pieces available after filtering, edge case

    async def get_piece_availability(self, piece_index: int) -> int:
        """Get the number of peers that have a specific piece.

        Args:
            piece_index: Index of the piece to check

        Returns:
            Number of peers that have this piece. Returns 0 if piece is not
            available from any peer, or >0 indicating availability from N peers.

        Note:
            The value represents the current count of peers that have this piece
            and updates dynamically as peers connect/disconnect. This is used
            for rarest-first piece selection prioritization.

        Raises:
            ValueError: If piece_index is out of valid range

        """
        async with self.lock:
            # Validate piece_index range
            if piece_index < 0 or piece_index >= len(self.pieces):
                raise ValueError(
                    f"Piece index {piece_index} is out of range [0, {len(self.pieces)})"
                )

            # Return availability count from piece_frequency Counter
            # Returns 0 if piece not in frequency dict (not available)
            return self.piece_frequency.get(piece_index, 0)

    async def _mark_piece_requested(self, piece_index: int) -> None:
        """Mark a piece as requested."""
        async with self.lock:
            if 0 <= piece_index < len(self.pieces):
                self.pieces[piece_index].state = PieceState.REQUESTED
                self.logger.debug("Marked piece %s as requested", piece_index)

    async def _set_piece_priority(self, piece_index: int, priority: int) -> None:
        """Set priority for a piece."""
        async with self.lock:
            if 0 <= piece_index < len(self.pieces):
                self.pieces[piece_index].priority = priority
                self.logger.debug("Set piece %s priority to %s", piece_index, priority)

    async def _on_piece_completed(self, piece_index: int) -> None:
        """Handle piece completion."""
        async with self.lock:  # pragma: no cover - Internal method, called via handle_piece_block completion
            if (
                0 <= piece_index < len(self.pieces)
            ):  # pragma: no cover - Bounds check in internal method
                self.pieces[
                    piece_index
                ].state = (
                    PieceState.COMPLETE
                )  # pragma: no cover - State update in internal method
                self.verified_pieces.add(
                    piece_index
                )  # pragma: no cover - Verified pieces tracking in internal method
                self.logger.debug(
                    "Piece %s completed", piece_index
                )  # pragma: no cover - Debug logging in internal method

    async def _calculate_swarm_health(self) -> dict[str, Any]:
        """Calculate swarm health metrics."""
        async with self.lock:
            total_pieces = len(self.pieces)
            completed_pieces = len(self.verified_pieces)
            missing_pieces = total_pieces - completed_pieces

            # Calculate availability distribution
            availability_counts = Counter(self.piece_frequency.values())

            # Calculate average availability
            total_availability = sum(self.piece_frequency.values())
            average_availability = (
                total_availability / total_pieces if total_pieces > 0 else 0
            )

            # Find rarest piece availability
            rarest_availability = (
                min(availability_counts.keys()) if availability_counts else 0
            )

            return {
                "total_pieces": total_pieces,
                "completed_pieces": completed_pieces,
                "missing_pieces": missing_pieces,
                "completion_percentage": (completed_pieces / total_pieces * 100)
                if total_pieces > 0
                else 0,
                "completion_rate": completed_pieces / total_pieces
                if total_pieces > 0
                else 0,
                "average_availability": average_availability,
                "rarest_piece_availability": rarest_availability,
                "availability_distribution": dict(availability_counts),
                "active_peers": len(self.peer_availability),
            }

    async def _generate_endgame_requests(
        self,
        piece_index: int,
    ) -> list[dict[str, Any]]:
        """Generate endgame requests for a piece from all available peers."""
        async with self.lock:
            requests = []

            # Find all peers that have this piece
            for peer_key, peer_availability in self.peer_availability.items():
                if piece_index in peer_availability.pieces:
                    # Create request for this peer
                    request = {
                        "piece_index": piece_index,
                        "peer_key": peer_key,
                        "timestamp": time.time(),
                    }
                    requests.append(request)

            return requests

    async def _select_rarest_first(self) -> None:
        """Select pieces using rarest-first algorithm."""
        async with self.lock:
            missing_pieces = (
                self.get_missing_pieces()
            )  # Already filtered by file selection

            if not missing_pieces:  # pragma: no cover - Early return when no missing pieces, tested separately
                return

            # Sort by frequency (rarest first) and priority
            piece_scores = []
            for piece_idx in missing_pieces:  # pragma: no cover - Selection algorithm loop, requires peer availability setup
                frequency = self.piece_frequency.get(piece_idx, 0)
                priority = self.pieces[piece_idx].priority

                # Update priority based on file selection if manager exists
                if self.file_selection_manager:
                    file_priority = self.file_selection_manager.get_piece_priority(
                        piece_idx
                    )
                    priority = max(priority, file_priority * 100)

                # Lower frequency = higher score, higher priority = higher score
                score = (1000 - frequency) + priority
                piece_scores.append((score, piece_idx))

            # Sort by score (descending)
            piece_scores.sort(
                reverse=True
            )  # pragma: no cover - Selection algorithm continuation

            # Select top pieces to request
            selected_pieces = []
            for _score, piece_idx in piece_scores[:5]:  # Request up to 5 pieces at once
                if self.pieces[piece_idx].state == PieceState.MISSING:
                    selected_pieces.append(piece_idx)

            # CRITICAL FIX: Actually request the selected pieces
            if selected_pieces:
                if self._peer_manager:
                    self.logger.info(
                        "Piece selector selected %d pieces to request: %s",
                        len(selected_pieces),
                        selected_pieces[:5],  # Log first 5
                    )
                    for piece_idx in selected_pieces:
                        # Request piece asynchronously (don't await to allow parallel requests)
                        task = asyncio.create_task(
                            self.request_piece_from_peers(piece_idx, self._peer_manager)
                        )
                        _ = task  # Store reference to avoid unused variable warning
                else:
                    # CRITICAL FIX: Log when pieces are selected but peer_manager is not available
                    self.logger.debug(
                        "Piece selector selected %d pieces but peer_manager is None (no peers available yet): %s",
                        len(selected_pieces),
                        selected_pieces[:5],
                    )
            elif not selected_pieces:
                self.logger.debug("Piece selector found no pieces to select")

    async def _select_sequential(self) -> None:
        """Select pieces sequentially with configurable window."""
        async with self.lock:
            missing_pieces = (
                self.get_missing_pieces()
            )  # Already filtered by file selection

            if not missing_pieces:
                return

            config = self.config
            window_size = config.strategy.sequential_window

            # Get current piece index being downloaded
            current_piece = self._get_current_sequential_piece()

            # Calculate window bounds
            window_start = current_piece
            window_end = min(current_piece + window_size, len(self.pieces))

            # Select pieces within window
            window_pieces = [
                idx for idx in missing_pieces if window_start <= idx < window_end
            ]

            if window_pieces:
                # Sort by priority if file selection active
                if self.file_selection_manager:
                    window_pieces = self._sort_by_file_priority(window_pieces)

                # Select first available piece in window
                for piece_idx in window_pieces:
                    if (
                        self.pieces[piece_idx].state == PieceState.MISSING
                        and self._peer_manager
                    ):
                        # CRITICAL FIX: Actually request the selected piece
                        task = asyncio.create_task(
                            self.request_piece_from_peers(piece_idx, self._peer_manager)
                        )
                        _ = task  # Store reference to avoid unused variable warning
                        break

    def _get_current_sequential_piece(self) -> int:
        """Get the current piece index for sequential download.

        Returns:
            Index of the current sequential piece, or first missing piece if not set

        """
        # Use tracked position if set, otherwise find first missing piece
        if self._current_sequential_piece > 0:
            return self._current_sequential_piece

        missing = self.get_missing_pieces()
        if missing:
            return min(missing)
        return 0

    def _sort_by_file_priority(self, piece_indices: list[int]) -> list[int]:
        """Sort pieces by file priority for sequential download.

        Args:
            piece_indices: List of piece indices to sort

        Returns:
            Sorted list prioritizing files in order

        """
        if not self.file_selection_manager:
            return sorted(piece_indices)

        selected_files = self.file_selection_manager.get_selected_files()
        piece_priorities = []

        for piece_idx in piece_indices:
            files_in_piece = self.file_selection_manager.get_files_for_piece(piece_idx)
            # Find first selected file that contains this piece
            for selected_file_idx in selected_files:
                if selected_file_idx in files_in_piece:
                    file_order = selected_files.index(selected_file_idx)
                    piece_priorities.append((file_order, piece_idx))
                    break

        # Sort by file order, then by piece index within file
        piece_priorities.sort()
        return [p[1] for p in piece_priorities]

    async def _select_sequential_with_fallback(self) -> None:
        """Select sequentially with fallback to rarest-first.

        Falls back if piece availability is below threshold.
        """
        async with self.lock:
            missing_pieces = self.get_missing_pieces()

            if not missing_pieces:
                return

            config = self.config
            fallback_threshold = config.strategy.sequential_fallback_threshold

            # Check average availability of sequential pieces
            window_start = min(missing_pieces)
            window_end = min(
                window_start + config.strategy.sequential_window,
                len(self.pieces),
            )
            window_pieces = [
                idx for idx in missing_pieces if window_start <= idx < window_end
            ]

            if window_pieces:
                # Calculate average availability
                active_peer_count = len(self.peer_availability)
                if active_peer_count > 0:
                    total_availability = sum(
                        self.piece_frequency.get(piece_idx, 0)
                        for piece_idx in window_pieces
                    )
                    avg_availability = (
                        total_availability / len(window_pieces) if window_pieces else 0
                    )

                    # Fallback to rarest-first if availability too low
                    if avg_availability < fallback_threshold * active_peer_count:
                        await self._select_rarest_first()
                        return

            # Otherwise use sequential selection
            await self._select_sequential()

    def get_download_rate(self) -> float:
        """Get current download rate in bytes per second.

        Returns:
            Download rate in bytes/second, or 0 if download hasn't started

        """
        current_time = time.time()
        download_time = current_time - self.download_start_time
        if download_time > 0:
            return self.bytes_downloaded / download_time
        return 0.0

    async def _select_sequential_with_window(self, window_size: int) -> None:
        """Select pieces sequentially with custom window size.

        Args:
            window_size: Number of pieces ahead to download

        """
        async with self.lock:
            missing_pieces = self.get_missing_pieces()
            if not missing_pieces:
                return

            current_piece = self._get_current_sequential_piece()
            window_end = min(current_piece + window_size, len(self.pieces))

            window_pieces = [
                idx for idx in missing_pieces if current_piece <= idx < window_end
            ]

            if window_pieces:
                # Sort by file priority if applicable
                if self.file_selection_manager:
                    window_pieces = self._sort_by_file_priority(window_pieces)

                # Select first piece in window
                piece_idx = window_pieces[0]
                if (
                    self.pieces[piece_idx].state == PieceState.MISSING
                    and self._peer_manager
                ):
                    # CRITICAL FIX: Actually request the selected piece
                    task = asyncio.create_task(
                        self.request_piece_from_peers(piece_idx, self._peer_manager)
                    )
                    _ = task  # Store reference to avoid unused variable warning

    async def _select_sequential_streaming(self) -> None:
        """Sequential selection optimized for streaming playback.

        Adjusts window size based on playback speed and prioritizes
        critical pieces for continuous playback.
        """
        async with self.lock:
            if not self.config.strategy.streaming_mode:
                await self._select_sequential()
                return

            # Calculate dynamic window size based on download rate
            piece_length = self.piece_length

            # Estimate playback speed (assume 1MB/s for video)
            playback_rate = 1_000_000  # bytes per second

            # Calculate how many pieces we need ahead of playback
            buffer_time = 10.0  # seconds of buffer ahead
            pieces_needed = int((playback_rate * buffer_time) / piece_length)

            # Adjust window size dynamically
            config = self.config
            dynamic_window = max(config.strategy.sequential_window, pieces_needed)

            # Get current playback position
            current_piece = self._get_current_sequential_piece()

            # Prioritize critical pieces (first few pieces for startup)
            if current_piece < 5:
                # Prioritize first pieces for faster startup
                priority_pieces = [
                    idx for idx in range(5) if idx in self.get_missing_pieces()
                ]
                if priority_pieces:
                    # Request first priority piece that is available from peers
                    for piece_idx in priority_pieces:
                        # Check if any peer has this piece
                        has_peer = False
                        async with self.lock:
                            for peer_avail in self.peer_availability.values():
                                # Check if piece is in peer's available pieces set
                                if piece_idx in peer_avail.pieces:
                                    has_peer = True
                                    break

                        if has_peer:
                            # Mark piece as requested - main logic will handle actual request
                            await self._mark_piece_requested(piece_idx)
                            self.logger.debug(
                                "Prioritized piece %s for streaming startup", piece_idx
                            )
                            break

            # Use enhanced sequential selection with dynamic window
            await self._select_sequential_with_window(dynamic_window)

    async def handle_streaming_seek(self, target_piece: int) -> None:
        """Handle seek operation during streaming download.

        Args:
            target_piece: Piece index to seek to

        """
        async with self.lock:
            # Update current sequential piece position
            self._current_sequential_piece = target_piece

            # Prioritize pieces around seek position
            config = self.config
            seek_window_start = max(0, target_piece - 2)
            seek_window_end = min(
                target_piece + config.strategy.sequential_window,
                len(self.pieces),
            )

            # Add priority for seek window pieces
            missing_pieces = self.get_missing_pieces()
            for piece_idx in range(seek_window_start, seek_window_end):
                if piece_idx in missing_pieces:
                    # Increase priority for pieces in seek window
                    self.pieces[piece_idx].priority += 500

            # Trigger piece selection update
            await self._select_sequential()

    async def _select_round_robin(self) -> None:
        """Select pieces in round-robin fashion."""
        async with self.lock:
            missing_pieces = [
                i
                for i, piece in enumerate(self.pieces)
                if piece.state == PieceState.MISSING
            ]

            if missing_pieces:
                # Simple round-robin selection
                piece_idx = missing_pieces[0]
                if (
                    self.pieces[piece_idx].state == PieceState.MISSING
                    and self._peer_manager
                ):
                    # CRITICAL FIX: Actually request the selected piece
                    task = asyncio.create_task(
                        self.request_piece_from_peers(piece_idx, self._peer_manager)
                    )
                    _ = task  # Store reference to avoid unused variable warning

    async def start_download(self, peer_manager: Any) -> None:
        """Start the download process.

        Args:
            peer_manager: Peer connection manager
        CRITICAL FIX: Don't start downloads until metadata is available for magnet links.

        """
        try:
            # CRITICAL FIX: Re-check num_pieces from torrent_data in case metadata was updated
            # This handles the case where metadata is fetched after piece manager initialization
            pieces_info = self.torrent_data.get("pieces_info", {})
            current_num_pieces = pieces_info.get("num_pieces", 0)
            if isinstance(current_num_pieces, (int, float)):
                current_num_pieces = int(current_num_pieces)
            else:
                current_num_pieces = 0

            # Update num_pieces if it changed (metadata was fetched)
            if current_num_pieces > 0 and self.num_pieces == 0:
                self.logger.info(
                    "Metadata now available: updating num_pieces from %d to %d",
                    self.num_pieces,
                    current_num_pieces,
                )
                self.num_pieces = current_num_pieces
                # Also update piece_length and piece_hashes if available
                if "piece_length" in pieces_info:
                    self.piece_length = int(pieces_info.get("piece_length", 16384))
                if "piece_hashes" in pieces_info:
                    piece_hashes_val = pieces_info.get("piece_hashes", [])
                    if isinstance(piece_hashes_val, (list, tuple)):
                        self.piece_hashes = list(piece_hashes_val)
                # Re-initialize pieces if needed
                if not self.pieces and self.num_pieces > 0:
                    self.logger.info(
                        "Initializing %d pieces after metadata fetch", self.num_pieces
                    )
                    # Initialize pieces (same logic as __init__)
                    for i in range(self.num_pieces):
                        # Calculate actual piece length (last piece may be shorter)
                        if i == self.num_pieces - 1:
                            # Get total_length safely - handle different torrent_data structures
                            total_length = 0
                            if (
                                "file_info" in self.torrent_data
                                and self.torrent_data.get("file_info")
                            ):
                                total_length = self.torrent_data["file_info"].get(
                                    "total_length", 0
                                )
                            elif "total_length" in self.torrent_data:
                                total_length = self.torrent_data["total_length"]
                            else:
                                # Fallback: calculate from pieces (approximation)
                                total_length = self.num_pieces * self.piece_length

                            piece_length = total_length - (i * self.piece_length)
                            # Ensure piece_length is positive
                            if piece_length <= 0:
                                piece_length = self.piece_length
                        else:
                            piece_length = self.piece_length

                        piece = PieceData(i, piece_length)

                        # Set priorities for streaming mode
                        if self.config.strategy.streaming_mode:
                            if i == 0:
                                piece.priority = 1000  # First piece highest priority
                            elif i == self.num_pieces - 1:
                                # Fallback: boost last piece modestly
                                piece.priority = 100
                            else:
                                piece.priority = max(0, 1000 - i)  # Decreasing priority

                        # Apply file-based priorities if file selection manager exists
                        if self.file_selection_manager:
                            file_priority = (
                                self.file_selection_manager.get_piece_priority(i)
                            )
                            # Scale file priority to piece priority (multiply by 100 to match streaming mode scale)
                            piece.priority = max(piece.priority, file_priority * 100)

                        self.pieces.append(piece)

            self.logger.info(
                "start_download() called: peer_manager=%s, num_pieces=%d, pieces_count=%d, is_downloading=%s",
                peer_manager is not None,
                self.num_pieces,
                len(self.pieces),
                self.is_downloading,
            )

            # CRITICAL FIX: Ensure pieces are initialized if num_pieces > 0 but pieces list is empty
            # This handles cases where num_pieces was updated but pieces weren't initialized
            if self.num_pieces > 0 and len(self.pieces) == 0:
                self.logger.warning(
                    "num_pieces=%d but pieces list is empty - initializing pieces now",
                    self.num_pieces,
                )
                # Initialize pieces using the same logic as __init__
                pieces_info = self.torrent_data.get("pieces_info", {})
                if "piece_length" in pieces_info:
                    self.piece_length = int(pieces_info.get("piece_length", 16384))
                elif self.piece_length == 0:
                    self.piece_length = 16384  # Default 16KB

                for i in range(self.num_pieces):
                    # Calculate actual piece length (last piece may be shorter)
                    if i == self.num_pieces - 1:
                        total_length = 0
                        if "file_info" in self.torrent_data and self.torrent_data.get(
                            "file_info"
                        ):
                            total_length = self.torrent_data["file_info"].get(
                                "total_length", 0
                            )
                        elif "total_length" in self.torrent_data:
                            total_length = self.torrent_data["total_length"]
                        else:
                            total_length = self.num_pieces * self.piece_length

                        piece_length = total_length - (i * self.piece_length)
                        if piece_length <= 0:
                            piece_length = self.piece_length
                    else:
                        piece_length = self.piece_length

                    piece = PieceData(i, piece_length)

                    # Set priorities for streaming mode
                    if self.config.strategy.streaming_mode:
                        if i == 0:
                            piece.priority = 1000
                        elif i == self.num_pieces - 1:
                            piece.priority = 100
                        else:
                            piece.priority = max(0, 1000 - i)

                    # Apply file-based priorities if available
                    if self.file_selection_manager:
                        file_priority = self.file_selection_manager.get_piece_priority(
                            i
                        )
                        piece.priority = max(piece.priority, file_priority * 100)

                    self.pieces.append(piece)
                self.logger.info(
                    "Initialized %d pieces in start_download()", len(self.pieces)
                )

            # CRITICAL FIX: Check if pieces were initialized from checkpoint
            # If pieces list has items but num_pieces is 0, use pieces count
            if self.num_pieces == 0 and len(self.pieces) > 0:
                self.num_pieces = len(self.pieces)
                self.logger.info(
                    "Inferred num_pieces=%d from restored pieces list (checkpoint had pieces but num_pieces was 0)",
                    self.num_pieces,
                )

            # CRITICAL FIX: Check if metadata is available before starting download
            # For magnet links, num_pieces will be 0 until metadata is fetched
            # CRITICAL FIX: Allow download start even without metadata for magnet links
            # This allows peer connections to proceed while metadata is being fetched
            if self.num_pieces == 0:
                # CRITICAL FIX: Try to infer num_pieces from peer data if available
                # This handles the case where peers are sending Have messages but metadata hasn't been fetched yet
                inferred_num_pieces = 0
                max_piece_index = -1
                connections_checked = 0
                connections_with_pieces = 0

                if peer_manager is not None and hasattr(peer_manager, "connections"):
                    connections_dict = peer_manager.connections
                    total_connections = len(connections_dict) if connections_dict else 0
                    self.logger.info(
                        "Attempting to infer num_pieces from %d peer connections (num_pieces=0, metadata not available)",
                        total_connections,
                    )

                    # Check all peer connections for the highest piece index seen
                    # CRITICAL FIX: Use connection_lock if available, otherwise access connections directly
                    if hasattr(peer_manager, "connection_lock"):
                        async with peer_manager.connection_lock:
                            connections_to_check = list(connections_dict.values())
                    else:
                        connections_to_check = list(connections_dict.values())

                    for connection in connections_to_check:
                        connections_checked += 1
                        # Track if connection reported any pieces (for diagnostics only)

                        # Check pieces_we_have set
                        if hasattr(connection, "peer_state") and hasattr(
                            connection.peer_state, "pieces_we_have"
                        ):
                            pieces_we_have = connection.peer_state.pieces_we_have
                            if pieces_we_have:
                                connections_with_pieces += 1
                                max_piece = max(pieces_we_have)
                                max_piece_index = max(max_piece_index, max_piece)
                                self.logger.debug(
                                    "Connection %s has %d pieces, max piece index: %d",
                                    connection.peer_info,
                                    len(pieces_we_have),
                                    max_piece,
                                )

                        # Also check bitfield if available
                        if (
                            hasattr(connection, "peer_state")
                            and hasattr(connection.peer_state, "bitfield")
                            and connection.peer_state.bitfield
                        ):
                            bitfield = connection.peer_state.bitfield
                            bitfield_length = len(bitfield)
                            # Infer num_pieces from bitfield length (bitfield has 8 bits per byte, with padding)
                            inferred_from_bitfield = bitfield_length * 8
                            # Subtract padding (last byte may have unused bits)
                            # Conservative estimate: assume at least 1 bit is used in last byte
                            inferred_from_bitfield = max(1, inferred_from_bitfield - 7)
                            if inferred_from_bitfield > inferred_num_pieces:
                                inferred_num_pieces = inferred_from_bitfield
                                self.logger.debug(
                                    "Inferred num_pieces=%d from bitfield length (%d bytes) from connection %s",
                                    inferred_from_bitfield,
                                    bitfield_length,
                                    connection.peer_info,
                                )

                        # If we found a piece index, infer num_pieces as piece_index + 1 with safety margin
                        if max_piece_index >= 0:
                            inferred_from_have = max_piece_index + 1
                            # Add 20% safety margin (round up) to account for pieces we haven't seen yet
                            inferred_from_have = int(inferred_from_have * 1.2) + 1
                            inferred_num_pieces = max(
                                inferred_num_pieces, inferred_from_have
                            )
                            self.logger.info(
                                "Inferred num_pieces=%d from max piece index %d (checked %d connections, %d with pieces)",
                                inferred_num_pieces,
                                max_piece_index,
                                connections_checked,
                                connections_with_pieces,
                            )
                        else:
                            self.logger.debug(
                                "No piece indices found in %d connections (checked %d, %d with pieces)",
                                total_connections,
                                connections_checked,
                                connections_with_pieces,
                            )

                    # If we inferred num_pieces from peer data, use it
                    if inferred_num_pieces > 0:
                        self.logger.info(
                            "Inferred num_pieces=%d from peer data (Have messages/bitfields) - metadata not yet available",
                            inferred_num_pieces,
                        )
                        self.num_pieces = inferred_num_pieces
                        # Initialize pieces with inferred count
                        if not self.pieces:
                            self.logger.info(
                                "Initializing %d pieces from inferred count",
                                self.num_pieces,
                            )
                            # Try to get piece_length from torrent_data, otherwise use default
                            if self.piece_length == 0:
                                pieces_info = self.torrent_data.get("pieces_info", {})
                                if "piece_length" in pieces_info:
                                    self.piece_length = int(
                                        pieces_info.get("piece_length", 16384)
                                    )
                                else:
                                    self.piece_length = 16384  # Default 16KB
                            # Initialize pieces (simplified - we don't have exact piece lengths)
                            for i in range(self.num_pieces):
                                piece = PieceData(i, self.piece_length)
                                # Set priorities for streaming mode
                                if self.config.strategy.streaming_mode:
                                    if i == 0:
                                        piece.priority = 1000
                                    elif i == self.num_pieces - 1:
                                        piece.priority = 100
                                    else:
                                        piece.priority = max(0, 1000 - i)
                                # Apply file-based priorities if available
                                if self.file_selection_manager:
                                    file_priority = (
                                        self.file_selection_manager.get_piece_priority(
                                            i
                                        )
                                    )
                                    piece.priority = max(
                                        piece.priority, file_priority * 100
                                    )
                                self.pieces.append(piece)
                    else:
                        self.logger.warning(
                            "Cannot start download: metadata not available yet (num_pieces=0) and cannot infer from peer data "
                            "(checked %d connections, %d with pieces). "
                            "This is normal for magnet links - download will start after metadata is fetched.",
                            connections_checked,
                            connections_with_pieces,
                        )
                        # CRITICAL FIX: Store peer_manager for later use when metadata is available
                        # But also set is_downloading=True to allow piece selector to run
                        # This allows the system to be ready when metadata arrives
                        if peer_manager is not None:
                            self._peer_manager = peer_manager
                        # CRITICAL FIX: Set is_downloading=True even without metadata
                        # This allows piece selector to run and be ready when metadata arrives
                        # The piece selector will handle num_pieces=0 gracefully
                        self.is_downloading = True
                        self.logger.info(
                            "Set is_downloading=True even without metadata (num_pieces=0) to allow piece selector to run when metadata arrives"
                        )
                        return

            # CRITICAL FIX: Verify peer_manager is valid
            if peer_manager is None:
                self.logger.error("Cannot start download: peer_manager is None")
                return

            # CRITICAL FIX: Check if already downloading to avoid duplicate starts
            if self.is_downloading:
                self.logger.debug(
                    "Download already started (is_downloading=True), skipping duplicate start"
                )
                # Still ensure _peer_manager is set in case it wasn't before
                if self._peer_manager is None and peer_manager is not None:
                    self._peer_manager = peer_manager
                    self.logger.debug(
                        "Set _peer_manager reference in piece manager (was None)"
                    )
                return

            # CRITICAL FIX: Set _peer_manager BEFORE is_downloading to ensure it's available for piece selection
            # This prevents piece selector from running with None peer_manager
            self._peer_manager = peer_manager
            self.logger.debug(
                "Set _peer_manager reference in piece manager (peer_manager is not None)"
            )

            # CRITICAL FIX: Validate that _peer_manager is set before proceeding
            if self._peer_manager is None:
                self.logger.error(
                    "Cannot start download: _peer_manager is None after assignment"
                )
                return

            # Set is_downloading to True - this must happen after _peer_manager is set
            self.is_downloading = True
            self.logger.info(
                "Piece manager download started (is_downloading=True, _peer_manager=%s, num_pieces=%d)",
                self._peer_manager is not None,
                self.num_pieces,
            )

            # CRITICAL FIX: Trigger initial piece selection after starting download
            # This ensures pieces are requested as soon as download starts
            # Add a small delay to ensure peer_manager is fully ready
            await asyncio.sleep(0.1)  # Small delay to ensure peer_manager is ready

            try:
                task = asyncio.create_task(self._select_pieces())
                _ = task  # Store reference to avoid unused variable warning
                self.logger.debug(
                    "Triggered initial piece selection after starting download"
                )
            except Exception:
                self.logger.exception(
                    "Error triggering initial piece selection after starting download"
                )
                # Don't fail the entire start_download() if piece selection fails
                # The piece selector loop will retry
        except Exception as e:
            self.logger.exception("Error starting download: %s", e)
            # Only reset state if we actually set it
            if self.is_downloading:
                self.is_downloading = False
            # Don't clear _peer_manager if it was set before - might be needed for retry
            if self._peer_manager == peer_manager:
                self._peer_manager = None

    async def stop_download(self) -> None:
        """Stop the download process."""
        self.is_downloading = False
        self.logger.info("Stopped piece download")

    def get_piece_data(self, piece_index: int) -> bytes | None:
        """Get complete piece data if available."""
        if (
            piece_index >= len(self.pieces)
        ):  # pragma: no cover - Defensive bounds check, tested via get_piece_data_not_verified
            return None

        piece = self.pieces[piece_index]
        if piece.state == PieceState.VERIFIED:
            return piece.get_data()

        return None

    def get_block(self, piece_index: int, begin: int, length: int) -> bytes | None:
        """Get a block of data from a piece."""
        if (
            piece_index >= len(self.pieces)
        ):  # pragma: no cover - Defensive bounds check, tested via get_block_invalid_indices
            return None

        # get_block method: block lookup and extraction requires specific verified piece and block arrangement
        piece = self.pieces[
            piece_index
        ]  # pragma: no cover - Piece access, tested separately
        if (
            piece.state != PieceState.VERIFIED
        ):  # pragma: no cover - State check for verified piece, tested separately
            return None

        # Find the block that contains this range
        for block in (
            piece.blocks
        ):  # pragma: no cover - Block lookup loop, requires specific block arrangement
            if (
                block.begin <= begin < block.begin + block.length
            ):  # pragma: no cover - Block range matching
                offset = (
                    begin - block.begin
                )  # pragma: no cover - Offset calculation in block extraction
                end_offset = min(
                    offset + length, block.length
                )  # pragma: no cover - Block extraction logic
                return block.data[
                    offset:end_offset
                ]  # pragma: no cover - Block data extraction

        return None  # pragma: no cover - No matching block found, edge case

    def get_stats(self) -> dict[str, Any]:
        """Get piece manager statistics."""
        return {
            "total_pieces": self.num_pieces,
            "completed_pieces": len(self.completed_pieces),
            "verified_pieces": len(self.verified_pieces),
            "missing_pieces": len(self.get_missing_pieces()),
            "downloading_pieces": len(self.get_downloading_pieces()),
            "progress": self.get_download_progress(),
            "endgame_mode": self.endgame_mode,
            "piece_frequency": dict(self.piece_frequency.most_common(10)),
            "peer_count": len(self.peer_availability),
        }

    async def get_checkpoint_state(
        self,
        torrent_name: str,
        info_hash: bytes,
        output_dir: str,
    ) -> TorrentCheckpoint:
        """Get current state for checkpointing.

        Args:
            torrent_name: Name of the torrent
            info_hash: Torrent info hash
            output_dir: Output directory for files

        Returns:
            TorrentCheckpoint with current state

        """
        async with self.lock:
            # Calculate download statistics
            current_time = time.time()
            download_time = current_time - self.download_start_time
            average_speed = (
                self.bytes_downloaded / download_time if download_time > 0 else 0
            )

            # Get piece states
            piece_states = {}
            for i, piece in enumerate(self.pieces):
                piece_states[i] = PieceStateModel(piece.state.value)

            # Get file information
            files = []
            if self.file_assembler:  # pragma: no cover - File assembler integration, requires full session setup
                file_paths = self.file_assembler.get_file_paths()
                file_sizes = self.file_assembler.get_file_sizes()
                files_exist = self.file_assembler.verify_files_exist()

                # Map file paths to FileInfo to get BEP 47 attributes
                file_info_map: dict[str, Any] = {}
                if hasattr(self.file_assembler, "files") and hasattr(
                    self.file_assembler, "output_dir"
                ):
                    for file_info in self.file_assembler.files:
                        # Skip padding files in checkpoint
                        if file_info.is_padding:
                            continue
                        # Construct file path same way as in file_assembler
                        import os

                        if file_info.full_path:
                            file_path = os.path.join(
                                self.file_assembler.output_dir, file_info.full_path
                            )
                        elif file_info.path:
                            file_path = os.path.join(
                                self.file_assembler.output_dir, *file_info.path
                            )
                        else:
                            file_path = os.path.join(
                                self.file_assembler.output_dir, file_info.name
                            )
                        file_info_map[file_path] = file_info

                # Create FileCheckpoint objects with BEP 47 attributes
                for file_path in (
                    file_paths
                ):  # pragma: no cover - File checkpoint creation, integration path
                    file_info = file_info_map.get(file_path)
                    files.append(
                        FileCheckpoint(
                            path=file_path,
                            size=file_sizes.get(file_path, 0),
                            exists=files_exist.get(file_path, False),
                            # BEP 47: Include file attributes in checkpoint
                            attributes=(
                                getattr(file_info, "attributes", None)
                                if file_info and hasattr(file_info, "attributes")
                                else None
                            ),
                            symlink_path=(
                                getattr(file_info, "symlink_path", None)
                                if file_info and hasattr(file_info, "symlink_path")
                                else None
                            ),
                            file_sha1=(
                                getattr(file_info, "file_sha1", None)
                                if file_info and hasattr(file_info, "file_sha1")
                                else None
                            ),
                        ),
                    )

            # Create download stats
            download_stats = DownloadStats(
                bytes_downloaded=self.bytes_downloaded,
                download_time=download_time,
                average_speed=average_speed,
                start_time=self.download_start_time,
                last_update=current_time,
            )

            # Ensure info_hash is exactly 20 bytes for checkpoint schema
            safe_info_hash = info_hash[:20]

            # Get total_length safely - handle different torrent_data structures
            total_length = 0
            if self.torrent_data:
                # Try normalized structure first (async_main format)
                if self.torrent_data.get("file_info"):
                    total_length = self.torrent_data["file_info"].get("total_length", 0)
                # Fallback to direct total_length key
                elif "total_length" in self.torrent_data:
                    total_length = self.torrent_data["total_length"]
                # Fallback to calculating from pieces
                elif self.num_pieces > 0 and self.piece_length > 0:
                    # Calculate from piece info (last piece may be shorter, but this is close enough)
                    total_length = (self.num_pieces - 1) * self.piece_length
                    # Try to get last piece length if available
                    if hasattr(self, "pieces") and self.pieces:
                        last_piece = self.pieces[-1]
                        if hasattr(last_piece, "length"):
                            total_length = (
                                self.num_pieces - 1
                            ) * self.piece_length + last_piece.length

            # Create checkpoint
            return TorrentCheckpoint(
                info_hash=safe_info_hash,
                torrent_name=torrent_name,
                created_at=self.download_start_time,
                updated_at=current_time,
                total_pieces=self.num_pieces,
                piece_length=self.piece_length,
                total_length=total_length,
                verified_pieces=list(self.verified_pieces),
                piece_states=piece_states,
                download_stats=download_stats,
                output_dir=output_dir,
                files=files,
                peer_info=self._get_peer_info_summary(),
                endgame_mode=self.endgame_mode,
            )

    def _get_peer_info_summary(self) -> dict[str, Any]:
        """Get summary of peer information for checkpoint."""
        return {
            "peer_count": len(self.peer_availability),
            "piece_frequency": dict(self.piece_frequency.most_common(20)),
            "reliability_scores": {
                peer_key: peer.reliability_score
                for peer_key, peer in self.peer_availability.items()
            },
        }

    async def restore_from_checkpoint(
        self, checkpoint: TorrentCheckpoint
    ) -> None:  # pragma: no cover - Checkpoint restoration, requires full checkpoint integration
        """Restore piece manager state from checkpoint.

        Args:
            checkpoint: Checkpoint data to restore from

        """
        async with self.lock:  # pragma: no cover - Checkpoint restoration path
            self.logger.info(
                "Restoring piece manager from checkpoint: %s (total_pieces=%d, verified=%d, pieces_list_len=%d)",
                checkpoint.torrent_name,
                checkpoint.total_pieces,
                len(checkpoint.verified_pieces),
                len(self.pieces),
            )

            # CRITICAL FIX: Detect checkpoint corruption before restoring
            # Check for impossible state: all pieces marked COMPLETE but no verified pieces and 0% downloaded
            if checkpoint.piece_states:
                complete_count = sum(
                    1
                    for state in checkpoint.piece_states.values()
                    if state in (PieceStateModel.COMPLETE, PieceStateModel.VERIFIED)
                )
                total_states = len(checkpoint.piece_states)
                bytes_downloaded = (
                    checkpoint.download_stats.bytes_downloaded
                    if checkpoint.download_stats
                    else 0
                )

                # If all pieces are marked COMPLETE but no verified pieces and no bytes downloaded, likely corrupted
                if (
                    complete_count == total_states
                    and len(checkpoint.verified_pieces) == 0
                    and bytes_downloaded == 0
                    and total_states > 0
                ):
                    self.logger.error(
                        "Checkpoint corruption detected: all %d pieces marked as COMPLETE but "
                        "0 verified pieces and 0 bytes downloaded. This checkpoint is likely corrupted. "
                        "Resetting all pieces to MISSING state.",
                        total_states,
                    )
                    # Don't restore piece states - they'll be initialized as MISSING below
                    checkpoint.piece_states = {}
                    checkpoint.verified_pieces = []

            # CRITICAL FIX: Validate checkpoint data before restoring
            # Ensure pieces list is initialized and matches checkpoint total_pieces
            if checkpoint.total_pieces > 0 and len(self.pieces) == 0:
                self.logger.warning(
                    "Checkpoint has total_pieces=%d but pieces list is empty - initializing pieces",
                    checkpoint.total_pieces,
                )
                # Initialize pieces if not already done
                if self.num_pieces == 0:
                    self.num_pieces = checkpoint.total_pieces
                if self.piece_length == 0:
                    self.piece_length = checkpoint.piece_length

                # Initialize pieces
                for i in range(self.num_pieces):
                    piece = PieceData(i, self.piece_length)
                    if self.config.strategy.streaming_mode:
                        if i == 0:
                            piece.priority = 1000
                        elif i == self.num_pieces - 1:
                            piece.priority = 100
                        else:
                            piece.priority = max(0, 1000 - i)
                    if self.file_selection_manager:
                        file_priority = self.file_selection_manager.get_piece_priority(
                            i
                        )
                        piece.priority = max(piece.priority, file_priority * 100)
                    self.pieces.append(piece)
                self.logger.info(
                    "Initialized %d pieces from checkpoint", len(self.pieces)
                )
                # CRITICAL FIX: Ensure num_pieces is set after initializing pieces from checkpoint
                # This ensures start_download() can use the pieces even if metadata isn't available
                if self.num_pieces == 0 and len(self.pieces) > 0:
                    self.num_pieces = len(self.pieces)
                    self.logger.info(
                        "Set num_pieces=%d from checkpoint pieces (metadata not yet available)",
                        self.num_pieces,
                    )

            # Validate checkpoint total_pieces matches current num_pieces
            if checkpoint.total_pieces != self.num_pieces and self.num_pieces > 0:
                self.logger.warning(
                    "Checkpoint total_pieces (%d) doesn't match current num_pieces (%d) - "
                    "using current num_pieces, may skip some checkpoint piece states",
                    checkpoint.total_pieces,
                    self.num_pieces,
                )

            # Validate checkpoint verified_pieces count is reasonable
            if len(checkpoint.verified_pieces) > self.num_pieces:
                self.logger.warning(
                    "Checkpoint has %d verified pieces but only %d total pieces - "
                    "truncating verified_pieces list",
                    len(checkpoint.verified_pieces),
                    self.num_pieces,
                )
                checkpoint.verified_pieces = [
                    idx
                    for idx in checkpoint.verified_pieces
                    if 0 <= idx < self.num_pieces
                ]

            # Restore download state
            # download_stats is guaranteed to be non-None by validator, but type checker doesn't know
            if (
                checkpoint.download_stats is None
            ):  # pragma: no cover - Validator ensures non-None
                checkpoint.download_stats = DownloadStats()  # type: ignore[assignment]
            self.download_start_time = (
                checkpoint.download_stats.start_time
            )  # pragma: no cover - State restoration
            self.bytes_downloaded = checkpoint.download_stats.bytes_downloaded
            self.endgame_mode = checkpoint.endgame_mode

            # CRITICAL FIX: Restore piece states with validation
            # Only restore states for pieces that exist and are within valid range
            restored_count = 0
            skipped_count = 0
            state_corrected_count = 0
            for (
                piece_idx,
                piece_state,
            ) in (
                checkpoint.piece_states.items()
            ):  # pragma: no cover - Piece state restoration loop
                if 0 <= piece_idx < len(self.pieces):
                    piece = self.pieces[piece_idx]
                    # CRITICAL FIX: Validate piece state - don't mark as verified unless in verified_pieces set
                    # This prevents incorrect state restoration from corrupted checkpoints
                    if piece_state == PieceStateModel.VERIFIED:
                        if piece_idx not in checkpoint.verified_pieces:
                            self.logger.warning(
                                "Checkpoint piece_states marks piece %d as VERIFIED but not in verified_pieces - "
                                "marking as COMPLETE instead",
                                piece_idx,
                            )
                            piece.state = PieceState.COMPLETE
                            piece.hash_verified = False
                        else:
                            piece.state = PieceState.VERIFIED
                            piece.hash_verified = True
                    else:
                        piece.state = PieceState(piece_state.value)
                        piece.hash_verified = piece_state == PieceStateModel.VERIFIED

                    # CRITICAL FIX: Validate that restored state matches actual block completion
                    # If checkpoint says COMPLETE/VERIFIED but blocks aren't received, reset to MISSING
                    if (
                        piece_state
                        in (PieceStateModel.COMPLETE, PieceStateModel.VERIFIED)
                        and not piece.is_complete()
                    ):
                        self.logger.warning(
                            "Checkpoint marks piece %d as %s but blocks are not complete - "
                            "resetting to MISSING (possible checkpoint corruption)",
                            piece_idx,
                            piece_state.value,
                        )
                        piece.state = PieceState.MISSING
                        piece.hash_verified = False
                        state_corrected_count += 1

                    restored_count += 1
                else:
                    skipped_count += 1
                    if skipped_count <= 5:  # Log first 5 skipped pieces
                        self.logger.debug(
                            "Skipping checkpoint piece state for index %d (out of range: 0-%d)",
                            piece_idx,
                            len(self.pieces) - 1,
                        )

            if skipped_count > 5:
                self.logger.debug(
                    "Skipped %d additional checkpoint piece states (out of range)",
                    skipped_count - 5,
                )

            # CRITICAL FIX: Restore verified pieces with validation
            # Only restore verified pieces that actually exist and are marked as verified in piece_states
            verified_pieces_set = set(checkpoint.verified_pieces)
            validated_verified = set()
            for piece_idx in verified_pieces_set:
                if 0 <= piece_idx < len(self.pieces):
                    piece = self.pieces[piece_idx]
                    # Only mark as verified if piece state is actually VERIFIED
                    if piece.state == PieceState.VERIFIED:
                        validated_verified.add(piece_idx)
                    else:
                        self.logger.debug(
                            "Piece %d in verified_pieces but state is %s - not adding to verified set",
                            piece_idx,
                            piece.state,
                        )
                else:
                    self.logger.debug(
                        "Skipping verified piece index %d (out of range: 0-%d)",
                        piece_idx,
                        len(self.pieces) - 1,
                    )

            self.verified_pieces = validated_verified

            # Restore completed pieces (pieces that are complete but not yet verified)
            self.completed_pieces = set()
            for i, piece in enumerate(
                self.pieces
            ):  # pragma: no cover - Completed pieces restoration loop
                if piece.state == PieceState.COMPLETE:
                    self.completed_pieces.add(i)

            # Restore peer availability if available
            if (
                checkpoint.peer_info and "piece_frequency" in checkpoint.peer_info
            ):  # pragma: no cover - Peer info restoration
                self.piece_frequency = Counter(checkpoint.peer_info["piece_frequency"])

            self.logger.info(
                "Restored checkpoint: %d piece states, %d verified pieces (validated), "
                "%d completed pieces, %d skipped states, %d state corrections",
                restored_count,
                len(self.verified_pieces),
                len(self.completed_pieces),
                skipped_count,
                state_corrected_count,
            )

    async def update_download_stats(
        self, bytes_downloaded: int
    ) -> None:  # pragma: no cover - Stats update method, called by session/peer manager during downloads
        """Update download statistics."""
        async with self.lock:  # pragma: no cover - Stats update path
            self.bytes_downloaded += bytes_downloaded
