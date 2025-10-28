"""Advanced piece management for BitTorrent client.

from __future__ import annotations

Implements rarest-first piece selection, endgame mode, per-peer availability tracking,
and parallel hash verification for high performance.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from ccbt.config import get_config
from ccbt.models import (
    DownloadStats,
    FileCheckpoint,
    PieceSelectionStrategy,
    TorrentCheckpoint,
)
from ccbt.models import PieceState as PieceStateModel

if TYPE_CHECKING:
    from ccbt.async_peer_connection import AsyncPeerConnection


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
            block_size = config.network.block_size_kib * 1024
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

    def get_data(self) -> bytes:
        """Get the complete piece data."""
        if not self.is_complete():
            msg = f"Piece {self.piece_index} is not complete"
            raise ValueError(msg)

        # Sort blocks by begin offset and concatenate
        sorted_blocks = sorted(self.blocks, key=lambda b: b.begin)
        return b"".join(block.data for block in sorted_blocks)

    def get_missing_blocks(self) -> list[PieceBlock]:
        """Get list of missing blocks."""
        return [block for block in self.blocks if not block.received]

    def verify_hash(self, expected_hash: bytes) -> bool:
        """Verify piece hash."""
        if not self.is_complete():
            return False

        actual_hash = hashlib.sha1(self.get_data()).digest()  # nosec B324 - SHA-1 required by BitTorrent protocol (BEP 3)
        self.hash_verified = actual_hash == expected_hash

        if self.hash_verified:
            self.state = PieceState.VERIFIED
        else:
            # Hash verification failed, mark as missing so it gets re-downloaded
            self.state = PieceState.MISSING
            for block in self.blocks:
                block.received = False
                block.data = b""

        return self.hash_verified


@dataclass
class PeerAvailability:
    """Tracks which pieces a peer has."""

    peer_key: str
    pieces: set[int] = field(default_factory=set)
    last_updated: float = field(default_factory=time.time)
    reliability_score: float = 1.0  # 0.0 to 1.0, higher is better


class AsyncPieceManager:
    """Advanced piece manager with rarest-first and endgame mode."""

    def __init__(self, torrent_data: dict[str, Any]):
        """Initialize async piece manager.

        Args:
            torrent_data: Parsed torrent data from TorrentParser
        """
        self.torrent_data = torrent_data
        self.config = get_config()

        self.num_pieces = torrent_data["pieces_info"]["num_pieces"]
        self.piece_length = torrent_data["pieces_info"]["piece_length"]
        self.piece_hashes = torrent_data["pieces_info"]["piece_hashes"]

        # Piece tracking
        self.pieces: list[PieceData] = []
        self.completed_pieces: set[int] = set()
        self.verified_pieces: set[int] = set()
        self.lock = asyncio.Lock()

        # Per-peer availability tracking
        self.peer_availability: dict[str, PeerAvailability] = {}
        self.piece_frequency: Counter = Counter()  # How many peers have each piece

        # Endgame mode
        self.endgame_mode = False
        self.endgame_threshold = self.config.strategy.endgame_threshold
        self.endgame_duplicates = self.config.strategy.endgame_duplicates

        # Hash verification pool
        self.hash_executor = ThreadPoolExecutor(
            max_workers=self.config.disk.hash_workers,
            thread_name_prefix="hash-verify",
        )
        self.hash_queue = asyncio.Queue(maxsize=self.config.disk.hash_queue_size)

        # Initialize pieces
        for i in range(self.num_pieces):
            # Calculate actual piece length (last piece may be shorter)
            if i == self.num_pieces - 1:
                total_length = torrent_data["file_info"]["total_length"]
                piece_length = total_length - (i * self.piece_length)
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

            self.pieces.append(piece)

        # Download state
        self.is_downloading = False
        self.download_complete = False
        self.download_start_time = time.time()
        self.bytes_downloaded = 0

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

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start background tasks."""
        self._hash_worker_task = asyncio.create_task(self._hash_worker())
        self._piece_selector_task = asyncio.create_task(self._piece_selector())
        self.logger.info("Async piece manager started")

    async def stop(self) -> None:
        """Stop background tasks."""
        if self._hash_worker_task:
            self._hash_worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._hash_worker_task

        if self._piece_selector_task:
            self._piece_selector_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._piece_selector_task

        self.hash_executor.shutdown(wait=True)
        self.logger.info("Async piece manager stopped")

    def get_missing_pieces(self) -> list[int]:
        """Get list of missing piece indices."""
        return [
            i
            for i, piece in enumerate(self.pieces)
            if piece.state == PieceState.MISSING
        ]

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
        if self.num_pieces == 0:
            return 1.0
        return len(self.verified_pieces) / self.num_pieces

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

            # Update peer availability
            if peer_key not in self.peer_availability:
                self.peer_availability[peer_key] = PeerAvailability(peer_key)

            old_pieces = self.peer_availability[peer_key].pieces
            self.peer_availability[peer_key].pieces = pieces
            self.peer_availability[peer_key].last_updated = time.time()

            # Update piece frequency
            for piece_idx in old_pieces - pieces:
                self.piece_frequency[piece_idx] -= 1
            for piece_idx in pieces - old_pieces:
                self.piece_frequency[piece_idx] += 1

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
        async with self.lock:
            if piece_index >= len(self.pieces):
                return

            piece = self.pieces[piece_index]
            if piece.state != PieceState.MISSING:
                return

            piece.state = PieceState.REQUESTED
            piece.request_count += 1

        # Get available peers for this piece
        available_peers = await self._get_peers_for_piece(piece_index, peer_manager)
        if not available_peers:
            async with self.lock:
                piece.state = PieceState.MISSING
            return

        # Get missing blocks
        missing_blocks = piece.get_missing_blocks()
        if not missing_blocks:
            return

        # Distribute blocks among peers
        if self.endgame_mode:
            await self._request_blocks_endgame(
                piece_index,
                missing_blocks,
                available_peers,
                peer_manager,
            )
        else:
            await self._request_blocks_normal(
                piece_index,
                missing_blocks,
                available_peers,
                peer_manager,
            )

        async with self.lock:
            piece.state = PieceState.DOWNLOADING

    async def _get_peers_for_piece(
        self,
        piece_index: int,
        peer_manager: Any,
    ) -> list[AsyncPeerConnection]:
        """Get peers that have the specified piece."""
        available_peers = []

        for connection in peer_manager.get_active_peers():
            peer_key = str(connection.peer_info)
            if (
                peer_key in self.peer_availability
                and piece_index in self.peer_availability[peer_key].pieces
                and connection.can_request()
            ):
                available_peers.append(connection)

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
            if piece_index >= len(self.pieces):
                return

            piece = self.pieces[piece_index]

            # Add block to piece
            if piece.add_block(begin, data) and piece.state == PieceState.COMPLETE:
                self.completed_pieces.add(piece_index)

                # Notify callback
                if self.on_piece_completed:
                    self.on_piece_completed(piece_index)

                    # Queue for hash verification
                    await self.hash_queue.put((piece_index, piece))

    async def _hash_worker(self) -> None:
        """Background task for hash verification."""
        while True:
            try:
                piece_index, piece = await self.hash_queue.get()
                await self._verify_piece_hash(piece_index, piece)
                self.hash_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in hash worker")

    async def _verify_piece_hash(self, piece_index: int, piece: PieceData) -> None:
        """Verify piece hash in background with optimizations."""
        try:
            expected_hash = self.piece_hashes[piece_index]

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

                # Notify callback
                if self.on_piece_verified:
                    self.on_piece_verified(piece_index)

                # Trigger checkpoint save if enabled
                if self.on_checkpoint_save:
                    self.on_checkpoint_save()

                # Check if download is complete
                if len(self.verified_pieces) == self.num_pieces:
                    self.download_complete = True
                    if self.on_download_complete:
                        self.on_download_complete()

                self.logger.info("Verified piece %s", piece_index)
            else:
                self.logger.warning(
                    "Hash verification failed for piece %s",
                    piece_index,
                )

        except Exception:
            self.logger.exception("Error verifying piece %s", piece_index)

    def _hash_piece_optimized(self, piece: PieceData, expected_hash: bytes) -> bool:
        """Optimized piece hash verification using memoryview and zero-copy operations."""
        try:
            # Get piece data (no optional data buffer available in this implementation)
            data_bytes = piece.get_data()
            data_view = memoryview(data_bytes)

            # Create SHA-1 hasher
            hasher = hashlib.sha1()  # nosec B324 - SHA-1 required by BitTorrent protocol (BEP 3)

            # Hash in optimized chunks to balance memory usage and performance
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

    async def _batch_verify_pieces(
        self,
        pieces_to_verify: list[tuple[int, PieceData]],
    ) -> None:
        """Batch verify multiple pieces for better performance."""
        if not pieces_to_verify:
            return

        # Create verification tasks for parallel execution
        tasks = []
        for piece_index, piece in pieces_to_verify:
            task = asyncio.create_task(self._verify_piece_hash(piece_index, piece))
            tasks.append(task)

        # Wait for all verifications to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                piece_index, _ = pieces_to_verify[i]
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
        batch_size = self.config.disk.hash_batch_size
        for i in range(0, len(pending_pieces), batch_size):
            batch = pending_pieces[i : i + batch_size]
            await self._batch_verify_pieces(batch)

            # Small delay between batches to prevent overwhelming the system
            await asyncio.sleep(0.01)

    async def _piece_selector(self) -> None:
        """Background task for piece selection."""
        while True:
            try:
                await asyncio.sleep(1.0)  # Select pieces every second
                await self._select_pieces()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in piece selector")

    async def _select_pieces(self) -> None:
        """Select pieces to download based on strategy."""
        if not self.is_downloading or self.download_complete:
            return

        # Check if we should enter endgame mode
        remaining_pieces = len(self.get_missing_pieces())
        total_pieces = self.num_pieces
        if (
            remaining_pieces <= total_pieces * (1.0 - self.endgame_threshold)
            and not self.endgame_mode
        ):
            self.endgame_mode = True
            self.logger.info("Entered endgame mode")

        # Select pieces based on strategy
        if self.config.strategy.piece_selection == PieceSelectionStrategy.RAREST_FIRST:
            await self._select_rarest_first()
        elif self.config.strategy.piece_selection == PieceSelectionStrategy.SEQUENTIAL:
            await self._select_sequential()
        else:
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
                    frequency > 0
                ):  # Only consider pieces available from at least one peer
                    available_pieces.append(piece_idx)

            if not available_pieces:
                return None

            # Sort by frequency (rarest first) and priority
            piece_scores = []
            for piece_idx in available_pieces:
                frequency = self.piece_frequency.get(piece_idx, 0)
                priority = self.pieces[piece_idx].priority
                # Lower frequency = higher score, higher priority = higher score
                score = (1000 - frequency) + priority
                piece_scores.append((score, piece_idx))

            # Sort by score (descending) and return the rarest piece
            piece_scores.sort(reverse=True)
            if piece_scores:
                selected_piece = piece_scores[0][1]
                # Mark the piece as requested to prevent duplicates in concurrent selections
                self.pieces[selected_piece].state = PieceState.REQUESTED
                return selected_piece
            return None

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
        async with self.lock:
            if 0 <= piece_index < len(self.pieces):
                self.pieces[piece_index].state = PieceState.COMPLETE
                self.verified_pieces.add(piece_index)
                self.logger.debug("Piece %s completed", piece_index)

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
            missing_pieces = [
                i
                for i, piece in enumerate(self.pieces)
                if piece.state == PieceState.MISSING
            ]

            if not missing_pieces:
                return

            # Sort by frequency (rarest first) and priority
            piece_scores = []
            for piece_idx in missing_pieces:
                frequency = self.piece_frequency.get(piece_idx, 0)
                priority = self.pieces[piece_idx].priority
                # Lower frequency = higher score, higher priority = higher score
                score = (1000 - frequency) + priority
                piece_scores.append((score, piece_idx))

            # Sort by score (descending)
            piece_scores.sort(reverse=True)

            # Select top pieces to request
            for _score, piece_idx in piece_scores[:5]:  # Request up to 5 pieces at once
                if self.pieces[piece_idx].state == PieceState.MISSING:
                    # This will be handled by the main request logic
                    pass

    async def _select_sequential(self) -> None:
        """Select pieces sequentially."""
        async with self.lock:
            missing_pieces = [
                i
                for i, piece in enumerate(self.pieces)
                if piece.state == PieceState.MISSING
            ]

            if missing_pieces:
                # Request first missing piece
                piece_idx = min(missing_pieces)
                if self.pieces[piece_idx].state == PieceState.MISSING:
                    pass  # Will be handled by main request logic

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
                if self.pieces[piece_idx].state == PieceState.MISSING:
                    pass  # Will be handled by main request logic

    async def start_download(self, _peer_manager: Any) -> None:
        """Start the download process."""
        self.is_downloading = True
        self.logger.info("Started piece download")

    async def stop_download(self) -> None:
        """Stop the download process."""
        self.is_downloading = False
        self.logger.info("Stopped piece download")

    def get_piece_data(self, piece_index: int) -> bytes | None:
        """Get complete piece data if available."""
        if piece_index >= len(self.pieces):
            return None

        piece = self.pieces[piece_index]
        if piece.state == PieceState.VERIFIED:
            return piece.get_data()

        return None

    def get_block(self, piece_index: int, begin: int, length: int) -> bytes | None:
        """Get a block of data from a piece."""
        if piece_index >= len(self.pieces):
            return None

        piece = self.pieces[piece_index]
        if piece.state != PieceState.VERIFIED:
            return None

        # Find the block that contains this range
        for block in piece.blocks:
            if block.begin <= begin < block.begin + block.length:
                offset = begin - block.begin
                end_offset = min(offset + length, block.length)
                return block.data[offset:end_offset]

        return None

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
            if self.file_assembler:
                file_paths = self.file_assembler.get_file_paths()
                file_sizes = self.file_assembler.get_file_sizes()
                files_exist = self.file_assembler.verify_files_exist()

                files.extend(
                    [
                        FileCheckpoint(
                            path=file_path,
                            size=file_sizes.get(file_path, 0),
                            exists=files_exist.get(file_path, False),
                        )
                        for file_path in file_paths
                    ]
                )

            # Create download stats
            download_stats = DownloadStats(
                bytes_downloaded=self.bytes_downloaded,
                download_time=download_time,
                average_speed=average_speed,
                start_time=self.download_start_time,
                last_update=current_time,
            )

            # Create checkpoint
            return TorrentCheckpoint(
                info_hash=info_hash,
                torrent_name=torrent_name,
                created_at=self.download_start_time,
                updated_at=current_time,
                total_pieces=self.num_pieces,
                piece_length=self.piece_length,
                total_length=self.torrent_data["file_info"]["total_length"],
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

    async def restore_from_checkpoint(self, checkpoint: TorrentCheckpoint) -> None:
        """Restore piece manager state from checkpoint.

        Args:
            checkpoint: Checkpoint data to restore from
        """
        async with self.lock:
            self.logger.info(
                "Restoring piece manager from checkpoint: %s",
                checkpoint.torrent_name,
            )

            # Restore download state
            self.download_start_time = checkpoint.download_stats.start_time
            self.bytes_downloaded = checkpoint.download_stats.bytes_downloaded
            self.endgame_mode = checkpoint.endgame_mode

            # Restore piece states
            for piece_idx, piece_state in checkpoint.piece_states.items():
                if 0 <= piece_idx < len(self.pieces):
                    piece = self.pieces[piece_idx]
                    piece.state = PieceState(piece_state.value)
                    piece.hash_verified = piece_state == PieceStateModel.VERIFIED

            # Restore verified pieces
            self.verified_pieces = set(checkpoint.verified_pieces)

            # Restore completed pieces (pieces that are complete but not yet verified)
            self.completed_pieces = set()
            for i, piece in enumerate(self.pieces):
                if piece.state == PieceState.COMPLETE:
                    self.completed_pieces.add(i)

            # Restore peer availability if available
            if checkpoint.peer_info and "piece_frequency" in checkpoint.peer_info:
                self.piece_frequency = Counter(checkpoint.peer_info["piece_frequency"])

            self.logger.info(
                "Restored %s verified pieces from checkpoint",
                len(self.verified_pieces),
            )

    async def update_download_stats(self, bytes_downloaded: int) -> None:
        """Update download statistics."""
        async with self.lock:
            self.bytes_downloaded += bytes_downloaded
