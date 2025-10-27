"""Piece management for BitTorrent client.
"""

import hashlib
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class PieceState(Enum):
    """States of a piece download."""
    MISSING = "missing"
    REQUESTED = "requested"
    DOWNLOADING = "downloading"
    COMPLETE = "complete"
    VERIFIED = "verified"


@dataclass
class PieceBlock:
    """Represents a block within a piece."""
    piece_index: int
    begin: int
    length: int
    data: bytes = b""
    received: bool = False

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
    blocks: List[PieceBlock] = field(default_factory=list)
    state: PieceState = PieceState.MISSING
    hash_verified: bool = False
    data_buffer: Optional[bytearray] = None

    def __post_init__(self):
        """Initialize blocks after creation."""
        if not self.blocks:
            block_size = 16384  # 16KB
            self.blocks = []
            for begin in range(0, self.length, block_size):
                actual_length = min(block_size, self.length - begin)
                self.blocks.append(PieceBlock(self.piece_index, begin, actual_length))

    def add_block(self, begin: int, data: bytes) -> bool:
        """Add a block of data to this piece."""
        for block in self.blocks:
            if block.begin == begin and not block.received:
                if block.add_block(begin, data):
                    if self.is_complete():
                        self.state = PieceState.COMPLETE
                    return True
        return False

    def is_complete(self) -> bool:
        """Check if all blocks are complete."""
        return all(block.is_complete() for block in self.blocks)

    def get_data(self) -> bytes:
        """Get the complete piece data."""
        if not self.is_complete():
            raise ValueError(f"Piece {self.piece_index} is not complete")

        if self.data_buffer is not None:
            return bytes(self.data_buffer)

        data = b""
        for block in sorted(self.blocks, key=lambda b: b.begin):
            data += block.data
        return data

    def verify_hash(self, expected_hash: bytes) -> bool:
        """Verify the piece hash."""
        if not self.is_complete():
            return False

        data = self.get_data()
        actual_hash = hashlib.sha1(data).digest()

        self.hash_verified = (actual_hash == expected_hash)

        if self.hash_verified:
            self.state = PieceState.VERIFIED
        else:
            self.state = PieceState.MISSING
            for block in self.blocks:
                block.data = b""
                block.received = False
            self.data_buffer = None

        return self.hash_verified


class PieceManager:
    """Manages piece downloads and verification."""

    def __init__(self, torrent_data: Dict[str, Any]):
        """Initialize piece manager."""
        self.torrent_data = torrent_data
        self.pieces_info = torrent_data["pieces_info"]
        self.file_info = torrent_data["file_info"]

        self.num_pieces = self.pieces_info["num_pieces"]
        self.piece_length = self.pieces_info["piece_length"]
        self.piece_hashes = self.pieces_info["piece_hashes"]
        self.total_length = self.file_info["total_length"]

        # Initialize pieces
        self.pieces = []
        for i in range(self.num_pieces):
            actual_length = min(self.piece_length, self.total_length - i * self.piece_length)
            piece = PieceData(i, actual_length)
            self.pieces.append(piece)

        # State tracking
        self.completed_pieces: Set[int] = set()
        self.verified_pieces: Set[int] = set()
        self.is_downloading = False
        self.download_complete = False

        # Threading
        self.lock = threading.Lock()

        # Callbacks
        self.on_piece_completed: Optional[Callable[[int], None]] = None
        self.on_piece_verified: Optional[Callable[[int], None]] = None
        self.on_file_assembled: Optional[Callable[[int], None]] = None
        self.on_download_complete: Optional[Callable[[], None]] = None

        # File assembler
        self.file_assembler = None

        # Test mode for synchronous verification
        self.test_mode = False

    def get_missing_pieces(self) -> List[int]:
        """Get list of missing piece indices."""
        with self.lock:
            return [i for i, piece in enumerate(self.pieces)
                   if piece.state == PieceState.MISSING]

    def get_random_missing_piece(self) -> Optional[int]:
        """Get a random missing piece index."""
        missing = self.get_missing_pieces()
        if not missing:
            return None
        import random
        return random.choice(missing)

    def handle_piece_block(self, piece_index: int, begin: int, data: bytes) -> bool:
        """Handle incoming piece block data."""
        if piece_index >= self.num_pieces:
            return False

        piece = self.pieces[piece_index]

        if piece.add_block(begin, data):
            # Mark piece as downloading if it's not already complete
            if piece.state == PieceState.MISSING:
                piece.state = PieceState.DOWNLOADING

            if piece.is_complete():
                with self.lock:
                    self.completed_pieces.add(piece_index)

                if self.on_piece_completed:
                    self.on_piece_completed(piece_index)

                if self.test_mode:
                    self._verify_piece_hash_sync(piece)
                else:
                    self._verify_piece_hash(piece)

            return True

        return False

    def _verify_piece_hash(self, piece: PieceData) -> None:
        """Verify piece hash in background thread."""
        def verify():
            expected_hash = self.piece_hashes[piece.piece_index]
            if piece.verify_hash(expected_hash):
                with self.lock:
                    self.verified_pieces.add(piece.piece_index)
                self._check_download_complete()
                if self.on_piece_verified:
                    self.on_piece_verified(piece.piece_index)
            else:
                with self.lock:
                    piece.state = PieceState.MISSING
                    self.completed_pieces.discard(piece.piece_index)

        thread = threading.Thread(target=verify)
        thread.daemon = True
        thread.start()

    def _verify_piece_hash_sync(self, piece: PieceData) -> None:
        """Verify piece hash synchronously (for testing)."""
        expected_hash = self.piece_hashes[piece.piece_index]
        if self._hash_piece_optimized(piece, expected_hash):
            self.verified_pieces.add(piece.piece_index)
            self._check_download_complete()
            if self.on_piece_verified:
                self.on_piece_verified(piece.piece_index)
        else:
            piece.state = PieceState.MISSING
            self.completed_pieces.discard(piece.piece_index)

    def _hash_piece_optimized(self, piece: PieceData, expected_hash: bytes) -> bool:
        """Optimized piece hash verification using memoryview and zero-copy operations."""
        try:
            if piece.data_buffer is not None:
                data_view = memoryview(piece.data_buffer)
            else:
                data_bytes = piece.get_data()
                data_view = memoryview(data_bytes)

            hasher = hashlib.sha1()

            # For small pieces (< 1MB), use more appropriate chunk size for testing
            if piece.length < 1024 * 1024:  # 1MB
                chunk_size = min(8192, piece.length)  # 8KB chunks for small data
            else:
                chunk_size = 64 * 1024  # 64KB for larger data

            for i in range(0, len(data_view), chunk_size):
                chunk = data_view[i:i + chunk_size]
                hasher.update(chunk)

            actual_hash = hasher.digest()
            piece.hash_verified = (actual_hash == expected_hash)

            if piece.hash_verified:
                piece.state = PieceState.VERIFIED
            else:
                piece.state = PieceState.MISSING
                for block in piece.blocks:
                    block.data = b""
                    block.received = False
                piece.data_buffer = None

            return piece.hash_verified

        except Exception as e:
            print(f"Error in hash verification: {e}")
            return False

    def _check_download_complete(self) -> None:
        """Check if all pieces have been downloaded and verified."""
        with self.lock:
            if len(self.verified_pieces) == self.num_pieces and not self.download_complete:
                self.download_complete = True
                if self.on_download_complete:
                    self.on_download_complete()

    def get_piece_data(self, piece_index: int) -> Optional[bytes]:
        """Get data for a verified piece."""
        if piece_index >= self.num_pieces:
            return None

        piece = self.pieces[piece_index]
        if piece.state == PieceState.VERIFIED:
            return piece.get_data()

        return None

    def get_all_piece_data(self) -> bytes:
        """Get all verified piece data concatenated."""
        data = b""
        for piece in self.pieces:
            if piece.state == PieceState.VERIFIED:
                data += piece.get_data()
        return data

    def get_download_progress(self) -> float:
        """Get download progress as a fraction (0.0 to 1.0)."""
        if self.num_pieces == 0:
            return 1.0
        return len(self.verified_pieces) / self.num_pieces

    def get_piece_status(self) -> Dict[str, int]:
        """Get status counts for pieces."""
        missing = 0
        complete = 0
        verified = 0

        for piece in self.pieces:
            if piece.state == PieceState.MISSING:
                missing += 1
            elif piece.state == PieceState.COMPLETE:
                complete += 1
            elif piece.state == PieceState.VERIFIED:
                verified += 1

        return {
            "missing": missing,
            "complete": complete,
            "verified": verified,
        }

    def reset(self) -> None:
        """Reset all pieces to missing state."""
        with self.lock:
            for piece in self.pieces:
                piece.state = PieceState.MISSING
                piece.hash_verified = False
                piece.data_buffer = None
                for block in piece.blocks:
                    block.data = b""
                    block.received = False

            self.completed_pieces.clear()
            self.verified_pieces.clear()
            self.is_downloading = False
            self.download_complete = False

    def request_piece_from_peers(self, piece_index: int, peer_manager) -> None:
        """Request a piece from available peers."""
        if piece_index >= self.num_pieces:
            return

        piece = self.pieces[piece_index]
        if piece.state != PieceState.MISSING:
            return

        active_peers = peer_manager.get_active_peers()
        if not active_peers:
            return

        piece.state = PieceState.DOWNLOADING

        for block in piece.blocks:
            if not block.received:
                for peer in active_peers:
                    if hasattr(peer, "peer_state") and not peer.peer_state.am_choking:
                        peer_manager.request_piece(piece_index, block.begin, block.length, peer)
                        break

    def start_download(self, peer_manager) -> None:
        """Start the download process."""
        self.is_downloading = True

    def stop_download(self) -> None:
        """Stop the download process."""
        self.is_downloading = False
