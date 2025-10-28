"""Async file assembler for BitTorrent downloads."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from ccbt.config import get_config
from ccbt.disk_io import DiskIOManager
from ccbt.models import TorrentCheckpoint, TorrentInfo


class FileSegment:
    """Represents a segment of a file that belongs to a specific piece."""

    def __init__(
        self,
        file_path: str,
        start_offset: int,
        end_offset: int,
        piece_index: int,
        piece_offset: int,
    ):
        """Initialize file block for piece assembly."""
        self.file_path = file_path
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.piece_index = piece_index
        self.piece_offset = piece_offset


class FileAssemblerError(Exception):
    """Exception raised for file assembler errors."""


class AsyncDownloadManager:
    """High-level async download manager that coordinates multiple file assemblers."""

    def __init__(
        self,
        torrent_data: dict[str, Any] | TorrentInfo | None = None,
        output_dir: str = ".",
        config: Any | None = None,
    ):
        """Initialize async download manager.

        Args:
            torrent_data: Optional torrent data to start download immediately
            output_dir: Directory to save files
            config: Configuration object (uses default if None)
        """
        self.config = config or get_config()
        self.assemblers: dict[str, AsyncFileAssembler] = {}
        self.lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)

        # For backward compatibility with session usage
        if torrent_data is not None:
            self.torrent_data = torrent_data
            self.output_dir = output_dir
            self.file_assembler = None  # Will be set when start_download is called

        # Initialize session-compatible attributes
        self.on_download_complete = None
        self.on_piece_verified = None

    async def start_download(
        self,
        torrent_data: dict[str, Any] | TorrentInfo,
        output_dir: str = ".",
    ) -> AsyncFileAssembler:
        """Start a new download for the given torrent.

        Args:
            torrent_data: Parsed torrent data (dict or TorrentInfo)
            output_dir: Directory to save files

        Returns:
            AsyncFileAssembler instance for the torrent
        """
        # Get info hash regardless of format
        if isinstance(torrent_data, TorrentInfo):
            info_hash = torrent_data.info_hash.hex()
        else:
            info_hash = torrent_data.get("info_hash", b"").hex()
            if not info_hash:
                info_hash = str(hash(str(torrent_data)))

        async with self.lock:
            if info_hash in self.assemblers:
                return self.assemblers[info_hash]

            assembler = AsyncFileAssembler(torrent_data, output_dir)
            self.assemblers[info_hash] = assembler

            # Start the disk I/O manager
            await assembler.__aenter__()

            return assembler

    async def stop_download(
        self,
        torrent_data: dict[str, Any] | TorrentInfo,
    ) -> None:
        """Stop a download and clean up resources.

        Args:
            torrent_data: Parsed torrent data (dict or TorrentInfo)
        """
        # Get info hash regardless of format
        if isinstance(torrent_data, TorrentInfo):
            info_hash = torrent_data.info_hash.hex()
        else:
            info_hash = torrent_data.get("info_hash", b"").hex()
            if not info_hash:
                info_hash = str(hash(str(torrent_data)))

        async with self.lock:
            if info_hash in self.assemblers:
                assembler = self.assemblers[info_hash]
                await assembler.__aexit__(None, None, None)
                del self.assemblers[info_hash]

    def get_assembler(
        self,
        torrent_data: dict[str, Any] | TorrentInfo,
    ) -> AsyncFileAssembler | None:
        """Get the assembler for a torrent.

        Args:
            torrent_data: Parsed torrent data (dict or TorrentInfo)

        Returns:
            AsyncFileAssembler instance or None if not found
        """
        # Get info hash regardless of format
        if isinstance(torrent_data, TorrentInfo):
            info_hash = torrent_data.info_hash.hex()
        else:
            info_hash = torrent_data.get("info_hash", b"").hex()
            if not info_hash:
                info_hash = str(hash(str(torrent_data)))

        return self.assemblers.get(info_hash)

    async def stop_all(self) -> None:
        """Stop all downloads and clean up resources."""
        async with self.lock:
            for assembler in self.assemblers.values():
                await assembler.__aexit__(None, None, None)
            self.assemblers.clear()

    # Session compatibility methods
    async def start(self) -> None:
        """Start the download manager (for session compatibility)."""
        if self.file_assembler is None and hasattr(self, "torrent_data"):
            self.file_assembler = await self.start_download(
                self.torrent_data,
                self.output_dir,
            )

    async def stop(self) -> None:
        """Stop the download manager (for session compatibility)."""
        await self.stop_all()

    def get_status(self) -> dict[str, Any]:
        """Get download status (for session compatibility)."""
        if self.file_assembler:
            # Calculate actual progress
            total_pieces = len(self.file_assembler.pieces)
            completed_pieces = sum(
                1 for piece in self.file_assembler.pieces if piece.completed
            )
            progress = completed_pieces / total_pieces if total_pieces > 0 else 0.0

            return {
                "progress": progress,
                "download_rate": self.file_assembler.download_rate,
                "upload_rate": self.file_assembler.upload_rate,
                "peers": len(self.file_assembler.peers),
                "pieces": total_pieces,
                "completed": total_pieces in {0, completed_pieces},
            }
        return {
            "progress": 0.0,
            "download_rate": 0.0,
            "upload_rate": 0.0,
            "peers": 0,
            "pieces": 0,
            "completed": False,
        }

    @property
    def piece_manager(self):
        """Get the piece manager (for session compatibility)."""
        if hasattr(self, "_piece_manager"):
            return self._piece_manager
        if self.file_assembler:
            return self.file_assembler
        return None

    @piece_manager.setter
    def piece_manager(self, value):
        """Set the piece manager (for session compatibility)."""
        # This is used for testing/mocking
        self._piece_manager = value

    @property
    def download_complete(self) -> bool:
        """Check if download is complete (for session compatibility)."""
        if self.file_assembler:
            return (
                len(self.file_assembler.written_pieces)
                == self.file_assembler.num_pieces
            )
        return False


class AsyncFileAssembler:
    """High-performance async file assembler with disk I/O optimizations."""

    def __init__(
        self,
        torrent_data: dict[str, Any] | TorrentInfo,
        output_dir: str = ".",
        disk_io_manager: DiskIOManager | None = None,
    ):
        """Initialize async file assembler.

        Args:
            torrent_data: Parsed torrent data from TorrentParser (dict or TorrentInfo)
            output_dir: Directory to save downloaded files
            disk_io_manager: Optional DiskIOManager instance
        """
        self.config = get_config()
        self.torrent_data = torrent_data
        self.output_dir = output_dir

        # Handle both old dict format and new TorrentInfo format
        if isinstance(torrent_data, TorrentInfo):
            self.name = torrent_data.name
            self.info_hash = torrent_data.info_hash
            self.files = torrent_data.files
            self.total_length = torrent_data.total_length
            self.piece_length = torrent_data.piece_length
            self.pieces = torrent_data.pieces
            self.num_pieces = torrent_data.num_pieces
        else:
            # Legacy dict format
            self.name = torrent_data.get("name", "unknown")
            self.info_hash = torrent_data.get("info_hash", b"")
            self.files = torrent_data.get("files", [])
            self.total_length = torrent_data.get("total_length", 0)
            self.piece_length = torrent_data.get("piece_length", 0)
            self.pieces = torrent_data.get("pieces", [])
            self.num_pieces = torrent_data.get("num_pieces", 0)

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Build file segments mapping
        self.file_segments = self._build_file_segments()

        # Track which pieces have been written to disk
        self.written_pieces: set = set()
        self.lock = asyncio.Lock()

        # Disk I/O manager
        self.disk_io = disk_io_manager or DiskIOManager(
            max_workers=self.config.disk.disk_workers,
            queue_size=self.config.disk.disk_queue_size,
            cache_size_mb=self.config.disk.cache_size_mb,
        )
        self._disk_io_started = False

        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Async context manager entry."""
        if not self._disk_io_started:
            await self.disk_io.start()
            self._disk_io_started = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._disk_io_started:
            await self.disk_io.stop()
            self._disk_io_started = False

    def _build_file_segments(self) -> list[FileSegment]:
        """Build mapping of file segments to pieces."""
        segments = []

        # Handle single file torrents
        if len(self.files) == 1:
            # Single file torrent
            file_info = self.files[0]
            file_path = os.path.join(self.output_dir, file_info.name)
            total_length = self.total_length

            # Calculate how many pieces fit in this file
            piece_length = self.piece_length
            current_offset = 0

            for piece_index in range(self.num_pieces):
                if piece_index == self.num_pieces - 1:
                    # Last piece may be smaller
                    piece_end = total_length
                else:
                    piece_end = current_offset + piece_length

                segments.append(
                    FileSegment(
                        file_path=file_path,
                        start_offset=current_offset,
                        end_offset=piece_end,
                        piece_index=piece_index,
                        piece_offset=0,
                    ),
                )
                current_offset = piece_end
        else:
            # Multi-file torrent
            current_offset = 0
            current_piece = 0
            piece_length = self.piece_length

            for file_info in self.files:
                file_path = os.path.join(self.output_dir, file_info.name)
                file_start = current_offset
                file_end = current_offset + file_info.length

                # Find pieces that overlap with this file
                while current_piece < self.num_pieces:
                    piece_start = current_piece * piece_length
                    piece_end = min(piece_start + piece_length, self.total_length)

                    # Check if piece overlaps with file
                    overlap_start = max(piece_start, file_start)
                    overlap_end = min(piece_end, file_end)

                    if overlap_start < overlap_end:
                        # Piece overlaps with file
                        segments.append(
                            FileSegment(
                                file_path=file_path,
                                start_offset=overlap_start - file_start,
                                end_offset=overlap_end - file_start,
                                piece_index=current_piece,
                                piece_offset=overlap_start - piece_start,
                            ),
                        )

                    if piece_end >= file_end:
                        break
                    current_piece += 1

                current_offset = file_end

        return segments

    async def write_piece_to_file(
        self,
        piece_index: int,
        piece_data: bytes | memoryview,
    ) -> None:
        """Write a verified piece to its corresponding file(s) asynchronously.

        Args:
            piece_index: Index of the piece to write
            piece_data: Complete piece data (bytes or memoryview)

        Raises:
            FileAssemblerError: If writing fails
        """
        # Ensure disk I/O manager is started
        if not self._disk_io_started:
            # Check if disk_io is a mock (for testing)
            if hasattr(self.disk_io, "start") and callable(self.disk_io.start):
                if asyncio.iscoroutinefunction(self.disk_io.start):
                    await self.disk_io.start()
                else:
                    self.disk_io.start()
            self._disk_io_started = True

        async with self.lock:
            if piece_index in self.written_pieces:
                return  # Already written

        # Find all file segments that belong to this piece
        piece_segments = [
            seg for seg in self.file_segments if seg.piece_index == piece_index
        ]

        if not piece_segments:
            msg = f"No file segments found for piece {piece_index}"
            raise FileAssemblerError(msg)

        # Write each segment to its file
        for segment in piece_segments:
            await self._write_segment_to_file_async(segment, piece_data)

        # Wait a bit for async writes to complete
        await asyncio.sleep(0.01)

        async with self.lock:
            self.written_pieces.add(piece_index)

    async def _write_segment_to_file_async(
        self,
        segment: FileSegment,
        piece_data: bytes | memoryview,
    ) -> None:
        """Write a segment of piece data to a file asynchronously.

        Args:
            segment: File segment information
            piece_data: Complete piece data
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(segment.file_path), exist_ok=True)

            # Extract the relevant portion of piece data for this segment
            # For single-file torrents, the entire piece data goes to the segment
            if isinstance(piece_data, memoryview):
                segment_data = bytes(piece_data)
            else:
                segment_data = piece_data

            # Use DiskIOManager for async writing
            from pathlib import Path

            await self.disk_io.write_block(
                Path(segment.file_path),
                segment.start_offset,
                segment_data,
            )

        except Exception as e:
            msg = f"Failed to write segment for {segment.file_path}: {e}"
            raise FileAssemblerError(
                msg,
            ) from e

    async def read_block(
        self,
        piece_index: int,
        begin: int,
        length: int,
    ) -> bytes | None:
        """Read a block of data for a given piece directly from files asynchronously.

        Args:
            piece_index: Index of the piece
            begin: Byte offset within the piece
            length: Number of bytes to read

        Returns:
            The requested bytes if available on disk, otherwise None.
        """
        # Ensure disk I/O manager is started
        if not self._disk_io_started:
            # Check if disk_io is a mock (for testing)
            if hasattr(self.disk_io, "start") and callable(self.disk_io.start):
                if asyncio.iscoroutinefunction(self.disk_io.start):
                    await self.disk_io.start()
                else:
                    self.disk_io.start()
            self._disk_io_started = True

        if piece_index < 0 or piece_index >= self.num_pieces:
            return None

        # Find the file segment for this piece
        piece_segments = [
            seg for seg in self.file_segments if seg.piece_index == piece_index
        ]

        if not piece_segments:
            return None

        # For single-file torrents, read directly from the file
        if len(piece_segments) == 1:
            seg = piece_segments[0]
            file_offset = seg.start_offset + begin
            try:
                from pathlib import Path

                return await self.disk_io.read_block(
                    Path(seg.file_path),
                    file_offset,
                    length,
                )
            except Exception:
                return None

        # For multi-file torrents, combine segments
        remaining = length
        current_offset_in_piece = begin
        parts: list[bytes] = []

        for seg in sorted(piece_segments, key=lambda s: s.piece_offset):
            if remaining <= 0:
                break

            seg_piece_start = seg.piece_offset
            seg_length = seg.end_offset - seg.start_offset
            seg_piece_end = seg_piece_start + seg_length

            # Compute overlap of requested range with this segment within the piece
            overlap_start = max(current_offset_in_piece, seg_piece_start)
            overlap_end = min(current_offset_in_piece + remaining, seg_piece_end)

            if overlap_start < overlap_end:
                # Read the overlapping portion
                read_len = overlap_end - overlap_start
                file_offset = seg.start_offset + (overlap_start - seg_piece_start)

                try:
                    from pathlib import Path

                    chunk = await self.disk_io.read_block(
                        Path(seg.file_path),
                        file_offset,
                        read_len,
                    )
                    if len(chunk) != read_len:
                        return None
                    parts.append(chunk)
                except Exception:
                    return None

                remaining -= read_len
                current_offset_in_piece = overlap_end

        if remaining != 0:
            return None

        return b"".join(parts)

    def get_file_paths(self) -> list[str]:
        """Get list of all file paths that will be created."""
        return list({seg.file_path for seg in self.file_segments})

    def is_piece_written(self, piece_index: int) -> bool:
        """Check if a piece has been written to disk."""
        return piece_index in self.written_pieces

    def get_written_pieces(self) -> set:
        """Get set of written piece indices."""
        return self.written_pieces.copy()

    async def verify_existing_pieces(
        self,
        checkpoint: TorrentCheckpoint,
    ) -> dict[str, Any]:
        """Verify that pieces mentioned in checkpoint actually exist and are valid.

        Args:
            checkpoint: TorrentCheckpoint with piece information

        Returns:
            Dict with validation results
        """
        validation_results: dict[str, Any] = {
            "valid": True,
            "missing_files": [],  # type: list[str]
            "corrupted_pieces": [],  # type: list[str]
            "missing_pieces": [],  # type: list[int]
        }

        # Ensure disk I/O manager is started
        if not self._disk_io_started:
            # Check if disk_io is a mock (for testing)
            if hasattr(self.disk_io, "start") and callable(self.disk_io.start):
                if asyncio.iscoroutinefunction(self.disk_io.start):
                    await self.disk_io.start()
                else:
                    self.disk_io.start()
            self._disk_io_started = True

        # Check if all files mentioned in checkpoint exist
        for file_checkpoint in checkpoint.files:
            if not os.path.exists(file_checkpoint.path):
                validation_results["missing_files"].append(file_checkpoint.path)
                validation_results["valid"] = False
            else:
                # Check file size
                actual_size = os.path.getsize(file_checkpoint.path)
                if actual_size != file_checkpoint.size:
                    validation_results["corrupted_pieces"].extend(
                        [
                            piece
                            for piece in checkpoint.verified_pieces
                            if any(
                                seg.file_path == file_checkpoint.path
                                for seg in self.file_segments
                                if seg.piece_index == piece
                            )
                        ],
                    )
                    validation_results["valid"] = False

        # Check if all verified pieces are actually written
        for piece_index in checkpoint.verified_pieces:
            if piece_index not in self.written_pieces:
                validation_results["missing_pieces"].append(piece_index)
                validation_results["valid"] = False

        return validation_results

    def cleanup_incomplete_files(self) -> None:
        """Clean up any incomplete files that were created during assembly."""
        for file_path in self.get_file_paths():
            try:
                if os.path.exists(file_path):
                    # Check if file is complete by comparing size
                    actual_size = os.path.getsize(file_path)
                    expected_size = self.total_length

                    if actual_size != expected_size:
                        self.logger.warning("Removing incomplete file: %s", file_path)
                        os.remove(file_path)
            except Exception:
                self.logger.exception("Error cleaning up file %s", file_path)


# Export the main download manager class
DownloadManager = AsyncDownloadManager
