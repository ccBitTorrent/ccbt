"""File selection and prioritization for torrent downloads.

This module provides file selection state management and piece-to-file mapping
for selective downloading in multi-file torrents.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from ccbt.models import TorrentInfo


class FilePriority(IntEnum):
    """File download priority levels.

    Higher values indicate higher priority. Priority 0 means do not download.
    """

    DO_NOT_DOWNLOAD = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    MAXIMUM = 4


@dataclass
class FileSelectionState:
    """State information for a single file."""

    file_index: int
    selected: bool = True  # Whether file is selected for download
    priority: FilePriority = FilePriority.NORMAL
    bytes_downloaded: int = 0
    bytes_total: int = 0

    @property
    def progress(self) -> float:
        """Get download progress as fraction (0.0 to 1.0)."""
        if self.bytes_total == 0:
            return 1.0 if not self.selected else 0.0
        return self.bytes_downloaded / self.bytes_total


class PieceToFileMapper:
    """Maps pieces to files and vice versa."""

    def __init__(self, torrent_info: TorrentInfo):
        """Initialize mapper from torrent info.

        Args:
            torrent_info: Parsed torrent information

        """
        self.torrent_info = torrent_info
        self.piece_length = torrent_info.piece_length
        self.total_length = torrent_info.total_length
        self.files = torrent_info.files

        # Build mappings
        self.piece_to_files: dict[int, list[tuple[int, int, int]]] = {}
        # Format: {piece_index: [(file_index, file_offset, length), ...]}
        self.file_to_pieces: dict[int, list[int]] = {}
        # Format: {file_index: [piece_index, ...]}

        self._build_mappings()

    def _build_mappings(self) -> None:
        """Build piece-to-file and file-to-piece mappings.

        Note: Padding files (BEP 47 attr='p') are excluded from mappings
        but their length is still accounted for in piece alignment.
        """
        # Calculate cumulative file offsets (including padding files for alignment)
        file_offsets: list[int] = []
        current_offset = 0
        for file_info in self.files:
            file_offsets.append(current_offset)
            current_offset += (
                file_info.length
            )  # Include padding files in offset calculation

        # Map each piece to its containing files
        for piece_index in range(self.torrent_info.num_pieces):
            piece_start = piece_index * self.piece_length
            piece_end = min(piece_start + self.piece_length, self.total_length)

            self.piece_to_files[piece_index] = []

            # Find which files this piece overlaps
            for file_index, file_info in enumerate(self.files):
                # Skip padding files - they exist only for alignment, not for download
                if file_info.is_padding:
                    continue

                file_start = file_offsets[file_index]
                file_end = file_start + file_info.length

                # Calculate overlap
                overlap_start = max(piece_start, file_start)
                overlap_end = min(piece_end, file_end)

                if overlap_start < overlap_end:
                    # Piece overlaps with this file
                    file_offset = overlap_start - file_start
                    length = overlap_end - overlap_start
                    self.piece_to_files[piece_index].append(
                        (file_index, file_offset, length),
                    )

                    # Add to reverse mapping
                    if file_index not in self.file_to_pieces:
                        self.file_to_pieces[file_index] = []
                    if piece_index not in self.file_to_pieces[file_index]:
                        self.file_to_pieces[file_index].append(piece_index)

        # Sort piece lists for each file
        for file_index in self.file_to_pieces:
            self.file_to_pieces[file_index].sort()


class FileSelectionManager:
    """Manages file selection state and piece filtering."""

    def __init__(self, torrent_info: TorrentInfo):
        """Initialize file selection manager.

        Args:
            torrent_info: Parsed torrent information

        """
        self.torrent_info = torrent_info
        self.mapper = PieceToFileMapper(torrent_info)
        self.logger = logging.getLogger(__name__)

        # File selection states - indexed by file_index
        # Note: Padding files (BEP 47) are excluded from selection states
        self.file_states: dict[int, FileSelectionState] = {}

        # Initialize all non-padding files as selected by default
        for file_index, file_info in enumerate(torrent_info.files):
            # Skip padding files - they should never be downloaded
            if file_info.is_padding:
                self.logger.debug(
                    "Skipping padding file %s: %s",
                    file_index,
                    file_info.full_path or file_info.name,
                )
                continue

            self.file_states[file_index] = FileSelectionState(
                file_index=file_index,
                selected=True,
                priority=FilePriority.NORMAL,
                bytes_total=file_info.length,
            )

        self.lock = asyncio.Lock()

    async def select_file(self, file_index: int) -> None:
        """Select a file for download.

        Args:
            file_index: Index of file to select

        """
        async with self.lock:
            if file_index in self.file_states:
                self.file_states[file_index].selected = True
                self.logger.info(
                    "Selected file %s: %s",
                    file_index,
                    self.torrent_info.files[file_index].name,
                )
                # Emit FILE_SELECTION_CHANGED event
                try:
                    from ccbt.utils.events import Event, emit_event
                    
                    info_hash_hex = self.torrent_info.info_hash.hex() if hasattr(self.torrent_info, "info_hash") else ""
                    state = self.file_states[file_index]
                    await emit_event(
                        Event(
                            event_type="file_selection_changed",
                            data={
                                "info_hash": info_hash_hex,
                                "file_index": file_index,
                                "selected": True,
                                "priority": state.priority.name if state else "normal",
                                "progress": state.progress if state else 0.0,
                            },
                        )
                    )
                except Exception as e:
                    self.logger.debug("Failed to emit FILE_SELECTION_CHANGED event: %s", e)

    async def deselect_file(self, file_index: int) -> None:
        """Deselect a file from download.

        Args:
            file_index: Index of file to deselect

        """
        async with self.lock:
            if file_index in self.file_states:
                self.file_states[file_index].selected = False
                self.logger.info(
                    "Deselected file %s: %s",
                    file_index,
                    self.torrent_info.files[file_index].name,
                )
                # Emit FILE_SELECTION_CHANGED event
                try:
                    from ccbt.utils.events import Event, emit_event
                    
                    info_hash_hex = self.torrent_info.info_hash.hex() if hasattr(self.torrent_info, "info_hash") else ""
                    state = self.file_states[file_index]
                    await emit_event(
                        Event(
                            event_type="file_selection_changed",
                            data={
                                "info_hash": info_hash_hex,
                                "file_index": file_index,
                                "selected": False,
                                "priority": state.priority.name if state else "normal",
                                "progress": state.progress if state else 0.0,
                            },
                        )
                    )
                except Exception as e:
                    self.logger.debug("Failed to emit FILE_SELECTION_CHANGED event: %s", e)

    async def set_file_priority(self, file_index: int, priority: FilePriority) -> None:
        """Set priority for a file.

        Args:
            file_index: Index of file
            priority: Priority level

        """
        async with self.lock:
            if file_index in self.file_states:
                self.file_states[file_index].priority = priority
                self.logger.info(
                    "Set file %s priority to %s",
                    file_index,
                    priority,
                )
                # Emit FILE_PRIORITY_CHANGED event
                try:
                    from ccbt.utils.events import Event, emit_event
                    
                    info_hash_hex = self.torrent_info.info_hash.hex() if hasattr(self.torrent_info, "info_hash") else ""
                    state = self.file_states[file_index]
                    await emit_event(
                        Event(
                            event_type="file_priority_changed",
                            data={
                                "info_hash": info_hash_hex,
                                "file_index": file_index,
                                "priority": priority.name,
                                "selected": state.selected if state else True,
                                "progress": state.progress if state else 0.0,
                            },
                        )
                    )
                except Exception as e:
                    self.logger.debug("Failed to emit FILE_PRIORITY_CHANGED event: %s", e)

    async def select_files(self, file_indices: list[int]) -> None:
        """Select multiple files.

        Args:
            file_indices: List of file indices to select

        """
        async with self.lock:
            for file_index in file_indices:
                if file_index in self.file_states:
                    self.file_states[file_index].selected = True

    async def deselect_files(self, file_indices: list[int]) -> None:
        """Deselect multiple files.

        Args:
            file_indices: List of file indices to deselect

        """
        async with self.lock:
            for file_index in file_indices:
                if file_index in self.file_states:
                    self.file_states[file_index].selected = False

    async def select_all(self) -> None:
        """Select all files."""
        async with self.lock:
            for file_state in self.file_states.values():
                file_state.selected = True

    async def deselect_all(self) -> None:
        """Deselect all files."""
        async with self.lock:
            for file_state in self.file_states.values():
                file_state.selected = False

    def is_file_selected(self, file_index: int) -> bool:
        """Check if a file is selected.

        Args:
            file_index: Index of file

        Returns:
            True if file is selected

        """
        if file_index not in self.file_states:
            return False
        return self.file_states[file_index].selected

    def get_file_priority(self, file_index: int) -> FilePriority:
        """Get priority for a file.

        Args:
            file_index: Index of file

        Returns:
            File priority level

        """
        if file_index not in self.file_states:
            return FilePriority.NORMAL
        return self.file_states[file_index].priority

    def is_piece_needed(self, piece_index: int) -> bool:
        """Check if a piece is needed based on file selection.

        A piece is needed if at least one of its containing files is selected.

        Args:
            piece_index: Index of piece

        Returns:
            True if piece should be downloaded

        """
        if piece_index not in self.mapper.piece_to_files:
            return True  # Default to needed if not in mapping

        for file_index, _, _ in self.mapper.piece_to_files[piece_index]:
            if self.is_file_selected(file_index):
                return True

        return False

    def get_piece_priority(self, piece_index: int) -> int:
        """Get priority for a piece based on file priorities.

        Piece priority is the maximum priority of any selected file in the piece.

        Args:
            piece_index: Index of piece

        Returns:
            Priority value (higher = more important)

        """
        if piece_index not in self.mapper.piece_to_files:
            return 0

        max_priority = FilePriority.DO_NOT_DOWNLOAD
        for file_index, _, _ in self.mapper.piece_to_files[piece_index]:
            if self.is_file_selected(file_index):
                file_priority = self.get_file_priority(file_index)
                max_priority = max(max_priority, file_priority)

        return int(max_priority.value)

    def get_files_for_piece(self, piece_index: int) -> list[int]:
        """Get list of file indices that contain this piece.

        Args:
            piece_index: Index of piece

        Returns:
            List of file indices

        """
        if piece_index not in self.mapper.piece_to_files:
            return []
        return [
            file_index for file_index, _, _ in self.mapper.piece_to_files[piece_index]
        ]

    def get_pieces_for_file(self, file_index: int) -> list[int]:
        """Get list of piece indices that belong to this file.

        Args:
            file_index: Index of file

        Returns:
            List of piece indices

        """
        return self.mapper.file_to_pieces.get(file_index, [])

    async def update_file_progress(
        self, file_index: int, bytes_downloaded: int
    ) -> None:
        """Update download progress for a file.

        Args:
            file_index: Index of file
            bytes_downloaded: Number of bytes downloaded for this file

        """
        async with self.lock:
            if file_index in self.file_states:
                self.file_states[file_index].bytes_downloaded = bytes_downloaded

    def get_file_state(self, file_index: int) -> FileSelectionState | None:
        """Get selection state for a file.

        Args:
            file_index: Index of file

        Returns:
            FileSelectionState or None if not found

        """
        return self.file_states.get(file_index)

    def get_all_file_states(self) -> dict[int, FileSelectionState]:
        """Get all file selection states.

        Returns:
            Dictionary mapping file_index to FileSelectionState

        """
        return self.file_states.copy()

    def get_selected_files(self) -> list[int]:
        """Get list of selected file indices.

        Returns:
            List of file indices that are selected

        """
        return [
            file_index
            for file_index, state in self.file_states.items()
            if state.selected
        ]

    def get_statistics(self) -> dict[str, Any]:
        """Get file selection statistics.

        Returns:
            Dictionary with selection statistics

        """
        # Count non-padding files only
        non_padding_files = [
            (idx, f)
            for idx, f in enumerate(self.torrent_info.files)
            if not f.is_padding
        ]
        padding_files = [
            (idx, f) for idx, f in enumerate(self.torrent_info.files) if f.is_padding
        ]

        total_files = len(non_padding_files)
        selected_files = len(self.get_selected_files())
        total_size = sum(f.length for _, f in non_padding_files)
        selected_size = sum(
            self.torrent_info.files[file_index].length
            for file_index in self.get_selected_files()
        )
        padding_size = sum(f.length for _, f in padding_files)

        return {
            "total_files": total_files,
            "selected_files": selected_files,
            "deselected_files": total_files - selected_files,
            "padding_files": len(padding_files),
            "total_size": total_size,
            "selected_size": selected_size,
            "deselected_size": total_size - selected_size,
            "padding_size": padding_size,
        }


__all__ = [
    "FilePriority",
    "FileSelectionManager",
    "FileSelectionState",
    "PieceToFileMapper",
]
