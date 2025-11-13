"""Fast Resume Data for ccBitTorrent.

Provides enhanced resume data structures for fast resume functionality,
including piece completion bitmaps, peer state, upload statistics,
file selection state, and queue position.
"""

from __future__ import annotations

import gzip
import time
from typing import Any

from pydantic import BaseModel, Field

from ccbt.models import DownloadStats


class FastResumeData(BaseModel):
    """Enhanced resume data for fast resume functionality."""

    version: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Resume data format version",
    )
    info_hash: bytes = Field(
        ...,
        min_length=20,
        max_length=20,
        description="Torrent info hash",
    )

    # Piece completion bitmap (compressed)
    piece_completion_bitmap: bytes = Field(
        default_factory=bytes,
        description="Compressed bitfield of verified pieces",
    )

    # Peer state
    peer_connections_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Peer connection state for resume",
    )

    # Statistics
    upload_statistics: dict[str, Any] = Field(
        default_factory=dict,
        description="Upload statistics (bytes, peers, rate history)",
    )
    download_stats: DownloadStats = Field(
        default_factory=DownloadStats,
        description="Download statistics",
    )

    # File selection
    file_selection_state: dict[int, dict[str, Any]] = Field(
        default_factory=dict,
        description="File selection state (file_index -> {selected, priority})",
    )

    # Queue state
    queue_position: int | None = Field(
        default=None,
        description="Torrent position in queue",
    )
    queue_priority: str | None = Field(
        default=None,
        description="Torrent queue priority",
    )

    # Metadata
    created_at: float = Field(
        default_factory=time.time,
        description="Resume data creation timestamp",
    )
    updated_at: float = Field(
        default_factory=time.time,
        description="Last update timestamp",
    )

    model_config = {"arbitrary_types_allowed": True}

    @staticmethod
    def encode_piece_bitmap(verified_pieces: set[int], total_pieces: int) -> bytes:
        """Encode piece completion as compressed bitfield.

        Args:
            verified_pieces: Set of verified piece indices
            total_pieces: Total number of pieces in torrent

        Returns:
            Compressed bitfield as bytes

        """
        if total_pieces == 0:
            return gzip.compress(b"")

        # Create bitfield
        bitfield = bytearray((total_pieces + 7) // 8)
        for piece_idx in verified_pieces:
            if 0 <= piece_idx < total_pieces:
                byte_idx = piece_idx // 8
                bit_idx = piece_idx % 8
                if byte_idx < len(bitfield):
                    bitfield[byte_idx] |= 1 << (7 - bit_idx)

        # Compress with gzip
        return gzip.compress(bytes(bitfield))

    @staticmethod
    def decode_piece_bitmap(bitmap_data: bytes, total_pieces: int) -> set[int]:
        """Decode compressed bitfield to piece set.

        Args:
            bitmap_data: Compressed bitfield data
            total_pieces: Total number of pieces in torrent

        Returns:
            Set of verified piece indices (empty set on corruption)

        """
        if not bitmap_data or total_pieces == 0:
            return set()

        try:
            # Decompress
            bitfield = gzip.decompress(bitmap_data)

            # Parse bits
            verified_pieces = set()
            for byte_idx, byte_val in enumerate(bitfield):
                for bit_idx in range(8):
                    piece_idx = byte_idx * 8 + bit_idx
                    if piece_idx < total_pieces and (byte_val & (1 << (7 - bit_idx))):
                        verified_pieces.add(piece_idx)

            return verified_pieces
        except Exception:
            return set()  # Return empty set on corruption

    def set_peer_connections_state(self, peer_states: list[dict[str, Any]]) -> None:
        """Store peer connection state for resume.

        Args:
            peer_states: List of peer state dictionaries with keys like:
                - peer_key: str (peer identifier)
                - pieces: set[int] (pieces peer has)
                - connection_time: float
                - bytes_sent: int
                - bytes_received: int

        """
        self.peer_connections_state = {
            "peers": peer_states,
            "total_peers": len(peer_states),
            "timestamp": time.time(),
        }
        self.updated_at = time.time()

    def get_peer_connections_state(self) -> list[dict[str, Any]]:
        """Retrieve peer connection state.

        Returns:
            List of peer state dictionaries

        """
        return self.peer_connections_state.get("peers", [])

    def set_upload_statistics(
        self,
        bytes_uploaded: int,
        peers_uploaded_to: set[str],
        upload_rate_history: list[float],
    ) -> None:
        """Store upload statistics.

        Args:
            bytes_uploaded: Total bytes uploaded
            peers_uploaded_to: Set of peer keys we've uploaded to
            upload_rate_history: History of upload rates (KiB/s)

        """
        self.upload_statistics = {
            "bytes_uploaded": bytes_uploaded,
            "peers_uploaded_to": list(peers_uploaded_to),
            "upload_rate_history": upload_rate_history[-100:],  # Keep last 100
            "average_upload_rate": (
                sum(upload_rate_history) / len(upload_rate_history)
                if upload_rate_history
                else 0.0
            ),
            "last_updated": time.time(),
        }
        self.updated_at = time.time()

    def get_upload_statistics(self) -> dict[str, Any]:
        """Retrieve upload statistics.

        Returns:
            Dictionary with upload statistics

        """
        return self.upload_statistics

    def set_file_selection_state(
        self,
        selected_files: dict[int, dict[str, Any]],
    ) -> None:
        """Store file selection state.

        Args:
            selected_files: Dictionary mapping file_index -> {
                'selected': bool,
                'priority': str (high/normal/low/do_not_download)
            }

        """
        self.file_selection_state = selected_files
        self.updated_at = time.time()

    def get_file_selection_state(self) -> dict[int, dict[str, Any]]:
        """Retrieve file selection state.

        Returns:
            Dictionary mapping file_index -> selection info

        """
        return self.file_selection_state

    def set_queue_state(self, position: int, priority: str) -> None:
        """Store queue position and priority.

        Args:
            position: Queue position (0 = highest priority)
            priority: Queue priority (maximum/high/normal/low/paused)

        """
        self.queue_position = position
        self.queue_priority = priority
        self.updated_at = time.time()

    def get_queue_state(self) -> tuple[int | None, str | None]:
        """Retrieve queue state.

        Returns:
            Tuple of (position, priority) or (None, None)

        """
        return (self.queue_position, self.queue_priority)

    def is_compatible(self, current_version: int) -> bool:
        """Check if resume data version is compatible.

        Args:
            current_version: Current resume data format version

        Returns:
            True if compatible, False otherwise

        """
        # Version 1 is baseline, forward compatible within reason
        return self.version >= 1 and self.version <= current_version

    def needs_migration(self, current_version: int) -> bool:
        """Check if resume data needs migration.

        Args:
            current_version: Current resume data format version

        Returns:
            True if migration needed, False otherwise

        """
        return self.version < current_version

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = time.time()
