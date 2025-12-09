"""Session adapters for command executor.

Provides adapters that abstract local session vs daemon session (IPC client).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from ccbt.daemon.ipc_protocol import (
        FileListResponse,
        NATStatusResponse,
        ProtocolInfo,
        QueueListResponse,
        ScrapeListResponse,
        ScrapeResult,
        TorrentStatusResponse,
    )


class SessionAdapter(ABC):
    """Abstract interface for session adapters.

    Provides unified interface for both local and daemon sessions.

    Note: All info_hash parameters and return values use hex strings (e.g., "a1b2c3..."),
    not bytes. Internal implementations may convert between hex strings and bytes as needed.
    """

    @abstractmethod
    async def add_torrent(
        self,
        path_or_magnet: str,
        output_dir: str | None = None,
        resume: bool = False,
    ) -> str:
        """Add torrent or magnet.

        Args:
            path_or_magnet: Torrent file path or magnet URI
            output_dir: Optional output directory override
            resume: Whether to resume from checkpoint

        Returns:
            Info hash (hex string)

        """

    @abstractmethod
    async def remove_torrent(self, info_hash: str) -> bool:
        """Remove torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if removed, False otherwise

        """

    @abstractmethod
    async def list_torrents(self) -> list[TorrentStatusResponse]:
        """List all torrents.

        Returns:
            List of torrent status responses

        """

    @abstractmethod
    async def get_torrent_status(self, info_hash: str) -> TorrentStatusResponse | None:
        """Get torrent status.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Torrent status response or None if not found

        """

    @abstractmethod
    async def pause_torrent(self, info_hash: str) -> bool:
        """Pause torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if paused, False otherwise

        """

    @abstractmethod
    async def resume_torrent(self, info_hash: str) -> bool:
        """Resume torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if resumed, False otherwise

        """

    @abstractmethod
    async def cancel_torrent(self, info_hash: str) -> bool:
        """Cancel torrent (pause but keep in session).

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if cancelled, False otherwise

        """

    @abstractmethod
    async def force_start_torrent(self, info_hash: str) -> bool:
        """Force start torrent (bypass queue limits).

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if force started, False otherwise

        """

    @abstractmethod
    async def get_torrent_files(self, info_hash: str) -> FileListResponse:
        """Get file list for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            File list response

        """

    @abstractmethod
    async def select_files(
        self, info_hash: str, file_indices: list[int]
    ) -> dict[str, Any]:
        """Select files for download.

        Args:
            info_hash: Torrent info hash (hex string)
            file_indices: List of file indices to select

        Returns:
            Response dict

        """

    @abstractmethod
    async def deselect_files(
        self, info_hash: str, file_indices: list[int]
    ) -> dict[str, Any]:
        """Deselect files.

        Args:
            info_hash: Torrent info hash (hex string)
            file_indices: List of file indices to deselect

        Returns:
            Response dict

        """

    @abstractmethod
    async def set_file_priority(
        self,
        info_hash: str,
        file_index: int,
        priority: str,
    ) -> dict[str, Any]:
        """Set file priority.

        Args:
            info_hash: Torrent info hash (hex string)
            file_index: File index
            priority: Priority level

        Returns:
            Response dict

        """

    @abstractmethod
    async def verify_files(self, info_hash: str) -> dict[str, Any]:
        """Verify torrent files.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Response dict

        """

    @abstractmethod
    async def get_queue(self) -> QueueListResponse:
        """Get queue status.

        Returns:
            Queue list response

        """

    @abstractmethod
    async def add_to_queue(self, info_hash: str, priority: str) -> dict[str, Any]:
        """Add torrent to queue.

        Args:
            info_hash: Torrent info hash (hex string)
            priority: Priority level

        Returns:
            Response dict

        """

    @abstractmethod
    async def remove_from_queue(self, info_hash: str) -> dict[str, Any]:
        """Remove torrent from queue.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Response dict

        """

    @abstractmethod
    async def move_in_queue(self, info_hash: str, new_position: int) -> dict[str, Any]:
        """Move torrent in queue.

        Args:
            info_hash: Torrent info hash (hex string)
            new_position: New position in queue

        Returns:
            Response dict

        """

    @abstractmethod
    async def clear_queue(self) -> dict[str, Any]:
        """Clear queue.

        Returns:
            Response dict

        """

    @abstractmethod
    async def pause_torrent_in_queue(self, info_hash: str) -> dict[str, Any]:
        """Pause torrent in queue.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Response dict

        """

    @abstractmethod
    async def resume_torrent_in_queue(self, info_hash: str) -> dict[str, Any]:
        """Resume torrent in queue.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Response dict

        """

    @abstractmethod
    async def get_nat_status(self) -> NATStatusResponse:
        """Get NAT status.

        Returns:
            NAT status response

        """

    @abstractmethod
    async def discover_nat(self) -> dict[str, Any]:
        """Discover NAT devices.

        Returns:
            Response dict

        """

    @abstractmethod
    async def map_nat_port(
        self,
        internal_port: int,
        external_port: int | None = None,
        protocol: str = "tcp",
    ) -> dict[str, Any]:
        """Map a port via NAT.

        Args:
            internal_port: Internal port
            external_port: External port (optional)
            protocol: Protocol (tcp/udp)

        Returns:
            Response dict

        """

    @abstractmethod
    async def unmap_nat_port(self, port: int, protocol: str = "tcp") -> dict[str, Any]:
        """Unmap a port via NAT.

        Args:
            port: Port to unmap
            protocol: Protocol (tcp/udp)

        Returns:
            Response dict

        """

    @abstractmethod
    async def refresh_nat_mappings(self) -> dict[str, Any]:
        """Refresh NAT mappings.

        Returns:
            Response dict

        """

    @abstractmethod
    async def scrape_torrent(self, info_hash: str, force: bool = False) -> ScrapeResult:
        """Scrape a torrent.

        Args:
            info_hash: Torrent info hash (hex string)
            force: Force scrape even if recently scraped

        Returns:
            Scrape result

        """

    @abstractmethod
    async def list_scrape_results(self) -> ScrapeListResponse:
        """List all cached scrape results.

        Returns:
            Scrape list response

        """

    @abstractmethod
    async def get_config(self) -> dict[str, Any]:
        """Get current config.

        Returns:
            Config dictionary

        """

    @abstractmethod
    async def update_config(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Update config.

        Args:
            config_dict: Config updates (nested dict)

        Returns:
            Updated config dictionary

        """

    @abstractmethod
    async def get_xet_protocol(self) -> ProtocolInfo:
        """Get Xet protocol information.

        Returns:
            Protocol info

        """

    @abstractmethod
    async def get_ipfs_protocol(self) -> ProtocolInfo:
        """Get IPFS protocol information.

        Returns:
            Protocol info

        """

    @abstractmethod
    async def get_peers_for_torrent(self, info_hash: str) -> list[dict[str, Any]]:
        """Get list of peers for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            List of peer dictionaries with keys: ip, port, download_rate, upload_rate, choked, client

        """

    @abstractmethod
    async def add_tracker(self, info_hash: str, tracker_url: str) -> dict[str, Any]:
        """Add a tracker URL to a torrent.

        Args:
            info_hash: Torrent info hash (hex string)
            tracker_url: Tracker URL to add

        Returns:
            Dict with success status

        """

    @abstractmethod
    async def remove_tracker(self, info_hash: str, tracker_url: str) -> dict[str, Any]:
        """Remove a tracker URL from a torrent.

        Args:
            info_hash: Torrent info hash (hex string)
            tracker_url: Tracker URL to remove

        Returns:
            Dict with success status

        """

    @abstractmethod
    async def add_xet_folder(
        self,
        folder_path: str,
        tonic_file: str | None = None,
        tonic_link: str | None = None,
        sync_mode: str | None = None,
        source_peers: list[str] | None = None,
        check_interval: float | None = None,
    ) -> str:
        """Add XET folder for synchronization.

        Args:
            folder_path: Path to folder (or output directory if syncing from tonic)
            tonic_file: Path to .tonic file (optional)
            tonic_link: tonic?: link (optional)
            sync_mode: Synchronization mode (optional)
            source_peers: Designated source peer IDs (optional)
            check_interval: Check interval in seconds (optional)

        Returns:
            Folder identifier (folder_path or info_hash)

        """

    @abstractmethod
    async def remove_xet_folder(self, folder_key: str) -> bool:
        """Remove XET folder from synchronization.

        Args:
            folder_key: Folder identifier (folder_path or info_hash)

        Returns:
            True if removed, False if not found

        """

    @abstractmethod
    async def list_xet_folders(self) -> list[dict[str, Any]]:
        """List all registered XET folders.

        Returns:
            List of folder information dictionaries

        """

    @abstractmethod
    async def get_xet_folder_status(self, folder_key: str) -> dict[str, Any] | None:
        """Get XET folder status.

        Args:
            folder_key: Folder identifier (folder_path or info_hash)

        Returns:
            Folder status dictionary or None if not found

        """

    @abstractmethod
    async def set_rate_limits(
        self,
        info_hash: str,
        download_kib: int,
        upload_kib: int,
    ) -> bool:
        """Set per-torrent rate limits.

        Args:
            info_hash: Torrent info hash (hex string)
            download_kib: Download limit in KiB/s
            upload_kib: Upload limit in KiB/s

        Returns:
            True if set successfully, False otherwise

        """

    @abstractmethod
    async def force_announce(self, info_hash: str) -> bool:
        """Force a tracker announce for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if announced, False otherwise

        """

    @abstractmethod
    async def export_session_state(self, path: str) -> None:
        """Export session state to a file.

        Args:
            path: File path to export to

        """

    @abstractmethod
    async def import_session_state(self, path: str) -> dict[str, Any]:
        """Import session state from a file.

        Args:
            path: File path to import from

        Returns:
            Parsed session state dictionary

        """

    @abstractmethod
    async def refresh_pex(self, info_hash: str) -> dict[str, Any]:
        """Refresh PEX (Peer Exchange) for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Dictionary with refresh result

        """

    @abstractmethod
    async def rehash_torrent(self, info_hash: str) -> dict[str, Any]:
        """Rehash all pieces for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            Dictionary with rehash result

        """

    @abstractmethod
    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all torrents.

        Returns:
            Dictionary with aggregated stats (num_torrents, num_active, etc.)

        """

    @abstractmethod
    async def global_pause_all(self) -> dict[str, Any]:
        """Pause all torrents.

        Returns:
            Dict with success_count, failure_count, and results

        """

    @abstractmethod
    async def global_resume_all(self) -> dict[str, Any]:
        """Resume all paused torrents.

        Returns:
            Dict with success_count, failure_count, and results

        """

    @abstractmethod
    async def global_force_start_all(self) -> dict[str, Any]:
        """Force start all torrents (bypass queue limits).

        Returns:
            Dict with success_count, failure_count, and results

        """

    @abstractmethod
    async def global_set_rate_limits(self, download_kib: int, upload_kib: int) -> bool:
        """Set global rate limits for all torrents.

        Args:
            download_kib: Global download limit (KiB/s, 0 = unlimited)
            upload_kib: Global upload limit (KiB/s, 0 = unlimited)

        Returns:
            True if limits set successfully

        """

    @abstractmethod
    async def set_per_peer_rate_limit(
        self, info_hash: str, peer_key: str, upload_limit_kib: int
    ) -> bool:
        """Set per-peer upload rate limit for a specific peer.

        Args:
            info_hash: Torrent info hash (hex string)
            peer_key: Peer identifier (format: "ip:port")
            upload_limit_kib: Upload rate limit in KiB/s (0 = unlimited)

        Returns:
            True if peer found and limit set, False otherwise

        """

    @abstractmethod
    async def get_per_peer_rate_limit(
        self, info_hash: str, peer_key: str
    ) -> int | None:
        """Get per-peer upload rate limit for a specific peer.

        Args:
            info_hash: Torrent info hash (hex string)
            peer_key: Peer identifier (format: "ip:port")

        Returns:
            Upload rate limit in KiB/s (0 = unlimited), or None if peer not found

        """

    @abstractmethod
    async def set_all_peers_rate_limit(self, upload_limit_kib: int) -> int:
        """Set per-peer upload rate limit for all active peers.

        Args:
            upload_limit_kib: Upload rate limit in KiB/s (0 = unlimited)

        Returns:
            Number of peers updated

        """

    @abstractmethod
    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: Any,
        torrent_path: str | None = None,
    ) -> str:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash (bytes) - Note: This method uses bytes instead of hex string
                for compatibility with checkpoint data structures. The return value is a hex string.
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Info hash hex string of resumed torrent

        """

    @abstractmethod
    async def get_scrape_result(self, info_hash: str) -> Any | None:
        """Get cached scrape result for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            ScrapeResult if cached, None otherwise

        """


class LocalSessionAdapter(SessionAdapter):
    """Adapter for local AsyncSessionManager."""

    def __init__(self, session_manager: Any):
        """Initialize local session adapter.

        Args:
            session_manager: AsyncSessionManager instance

        """
        self.session_manager = session_manager
        self.config = getattr(session_manager, "config", None)
        self.logger = logging.getLogger(__name__)

    async def add_torrent(
        self,
        path_or_magnet: str,
        output_dir: str | None = None,
        resume: bool = False,
    ) -> str:
        """Add torrent or magnet."""
        if path_or_magnet.startswith("magnet:"):
            return await self.session_manager.add_magnet(
                path_or_magnet, output_dir=output_dir, resume=resume
            )
        return await self.session_manager.add_torrent(
            path_or_magnet,
            output_dir=output_dir,
            resume=resume,
        )

    async def remove_torrent(self, info_hash: str) -> bool:
        """Remove torrent."""
        return await self.session_manager.remove(info_hash)

    async def list_torrents(self) -> list[TorrentStatusResponse]:
        """List all torrents."""
        from ccbt.daemon.ipc_protocol import TorrentStatusResponse

        status_dict = await self.session_manager.get_status()
        torrents = []
        for info_hash_hex, status in status_dict.items():
            torrents.append(
                TorrentStatusResponse(
                    info_hash=info_hash_hex,
                    name=status.get("name", "Unknown"),
                    status=status.get("status", "unknown"),
                    progress=status.get("progress", 0.0),
                    download_rate=status.get("download_rate", 0.0),
                    upload_rate=status.get("upload_rate", 0.0),
                    num_peers=status.get("num_peers", 0),
                    num_seeds=status.get("num_seeds", 0),
                    total_size=status.get("total_size", 0),
                    downloaded=status.get("downloaded", 0),
                    uploaded=status.get("uploaded", 0),
                    is_private=status.get("is_private", False),  # BEP 27: Include private flag
                    output_dir=status.get("output_dir"),  # Output directory where files are saved
                ),
            )
        return torrents

    async def get_torrent_status(self, info_hash: str) -> TorrentStatusResponse | None:
        """Get torrent status."""
        from ccbt.daemon.ipc_protocol import TorrentStatusResponse

        status = await self.session_manager.get_torrent_status(info_hash)
        if not status:
            return None

        return TorrentStatusResponse(
            info_hash=info_hash,
            name=status.get("name", "Unknown"),
            status=status.get("status", "unknown"),
            progress=status.get("progress", 0.0),
            download_rate=status.get("download_rate", 0.0),
            upload_rate=status.get("upload_rate", 0.0),
            num_peers=status.get("num_peers", 0),
            num_seeds=status.get("num_seeds", 0),
            total_size=status.get("total_size", 0),
            downloaded=status.get("downloaded", 0),
            uploaded=status.get("uploaded", 0),
            is_private=status.get("is_private", False),  # BEP 27: Include private flag
            output_dir=status.get("output_dir"),  # Output directory where files are saved
        )

    async def pause_torrent(self, info_hash: str) -> bool:
        """Pause torrent."""
        return await self.session_manager.pause_torrent(info_hash)

    async def resume_torrent(self, info_hash: str) -> bool:
        """Resume torrent."""
        return await self.session_manager.resume_torrent(info_hash)

    async def cancel_torrent(self, info_hash: str) -> bool:
        """Cancel torrent."""
        return await self.session_manager.cancel_torrent(info_hash)

    async def force_start_torrent(self, info_hash: str) -> bool:
        """Force start torrent."""
        return await self.session_manager.force_start_torrent(info_hash)

    async def get_torrent_files(self, info_hash: str) -> FileListResponse:
        """Get file list for a torrent."""
        from ccbt.daemon.ipc_protocol import FileInfo, FileListResponse

        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            raise ValueError(f"Invalid info hash format: {info_hash}") from None

        async with self.session_manager.lock:
            torrent_session = self.session_manager.torrents.get(info_hash_bytes)

        if not torrent_session:
            raise ValueError(f"Torrent not found: {info_hash}")

        if not torrent_session.ensure_file_selection_manager():
            raise ValueError(
                f"File selection not available for torrent: {info_hash} (metadata pending)"
            )

        manager = torrent_session.file_selection_manager
        if manager is None:
            raise ValueError(f"File selection not available for torrent: {info_hash}")
        files = []
        for file_index, file_info in enumerate(manager.torrent_info.files):
            if file_info.is_padding:
                continue
            state = manager.get_file_state(file_index)
            files.append(
                FileInfo(
                    index=file_index,
                    name=file_info.name,
                    size=file_info.length,
                    selected=state.selected if state else True,
                    priority=state.priority.name if state else "normal",
                    progress=state.progress if state else 0.0,
                    attributes=None,
                ),
            )

        return FileListResponse(info_hash=info_hash, files=files)

    async def select_files(
        self, info_hash: str, file_indices: list[int]
    ) -> dict[str, Any]:
        """Select files for download."""
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            raise ValueError(f"Invalid info hash format: {info_hash}") from None

        async with self.session_manager.lock:
            torrent_session = self.session_manager.torrents.get(info_hash_bytes)

        if not torrent_session:
            raise ValueError(f"Torrent not found or file selection not available: {info_hash}")

        if not torrent_session.ensure_file_selection_manager():
            raise ValueError(
                f"Torrent not found or file selection not available: {info_hash}"
            )

        manager = torrent_session.file_selection_manager
        if manager is None:
            raise ValueError(
                f"Torrent not found or file selection not available: {info_hash}"
            )
        for file_index in file_indices:
            manager.select_file(file_index)

        return {"status": "selected", "file_indices": file_indices}

    async def deselect_files(
        self, info_hash: str, file_indices: list[int]
    ) -> dict[str, Any]:
        """Deselect files."""
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            raise ValueError(f"Invalid info hash format: {info_hash}") from None

        async with self.session_manager.lock:
            torrent_session = self.session_manager.torrents.get(info_hash_bytes)

        if not torrent_session:
            raise ValueError(
                f"Torrent not found or file selection not available: {info_hash}"
            )

        if not torrent_session.ensure_file_selection_manager():
            raise ValueError(
                f"Torrent not found or file selection not available: {info_hash}"
            )

        manager = torrent_session.file_selection_manager
        if manager is None:
            raise ValueError(
                f"Torrent not found or file selection not available: {info_hash}"
            )
        for file_index in file_indices:
            manager.deselect_file(file_index)

        return {"status": "deselected", "file_indices": file_indices}

    async def set_file_priority(
        self,
        info_hash: str,
        file_index: int,
        priority: str,
    ) -> dict[str, Any]:
        """Set file priority."""
        from ccbt.piece.file_selection import FilePriority

        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            raise ValueError(f"Invalid info hash format: {info_hash}") from None

        async with self.session_manager.lock:
            torrent_session = self.session_manager.torrents.get(info_hash_bytes)

        if not torrent_session or not torrent_session.file_selection_manager:
            raise ValueError(
                f"Torrent not found or file selection not available: {info_hash}"
            )

        try:
            priority_enum = FilePriority[priority.upper()]
        except KeyError:
            raise ValueError(f"Invalid priority: {priority}") from None

        manager = torrent_session.file_selection_manager
        manager.set_file_priority(file_index, priority_enum)

        return {
            "status": "priority_set",
            "file_index": file_index,
            "priority": priority,
        }

    async def verify_files(
        self,
        info_hash: str,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Verify torrent files.

        Args:
            info_hash: Torrent info hash (hex string)
            progress_callback: Optional callback for progress reporting.
                Called with (current_file, total_files, file_path) during iteration.
                Return False to cancel verification.

        Returns:
            Dictionary with verification results:
            {
                "status": "completed" | "cancelled" | "error",
                "info_hash": info_hash,
                "verified_files": [...],  # List of file paths that passed
                "failed_files": [...],     # List of file paths that failed
                "total_files": N,
                "verified_count": M,
                "failed_count": K
            }

        """
        from pathlib import Path

        from ccbt.core.torrent_attributes import verify_file_sha1

        try:
            # Convert hex string to bytes
            try:
                info_hash_bytes = bytes.fromhex(info_hash)
            except ValueError:
                return {
                    "status": "error",
                    "info_hash": info_hash,
                    "error": "Invalid info hash format",
                    "verified_files": [],
                    "failed_files": [],
                    "total_files": 0,
                    "verified_count": 0,
                    "failed_count": 0,
                }

            # Get torrent session
            torrent_session = await self.session_manager.get_session_for_info_hash(
                info_hash_bytes
            )
            if not torrent_session:
                return {
                    "status": "error",
                    "info_hash": info_hash,
                    "error": "Torrent not found",
                    "verified_files": [],
                    "failed_files": [],
                    "total_files": 0,
                    "verified_count": 0,
                    "failed_count": 0,
                }

            # Get torrent info/metadata
            torrent_data = torrent_session.torrent_data
            if not isinstance(torrent_data, dict):
                return {
                    "status": "error",
                    "info_hash": info_hash,
                    "error": "Invalid torrent data",
                    "verified_files": [],
                    "failed_files": [],
                    "total_files": 0,
                    "verified_count": 0,
                    "failed_count": 0,
                }

            # Extract file list from torrent info
            files_to_verify: list[dict[str, Any]] = []
            file_info = torrent_data.get("file_info")
            output_dir = Path(torrent_session.output_dir)

            if file_info:
                if file_info.get("type") == "single":
                    # Single file torrent
                    file_name = file_info.get("name", "")
                    file_path = output_dir / file_name
                    file_sha1 = file_info.get("file_sha1")  # v2 torrents may have this
                    files_to_verify.append(
                        {
                            "path": file_path,
                            "sha1": file_sha1,
                            "length": file_info.get("length", 0),
                        }
                    )
                elif file_info.get("type") == "multi":
                    # Multi-file torrent
                    files_list = file_info.get("files", [])
                    base_name = file_info.get("name", "")
                    for file_entry in files_list:
                        if isinstance(file_entry, dict):
                            file_path_parts = file_entry.get("path", [])
                            if isinstance(file_path_parts, list):
                                file_path = (
                                    output_dir / base_name / Path(*file_path_parts)
                                )
                            else:
                                file_path = output_dir / base_name / file_path_parts
                            file_sha1 = file_entry.get("file_sha1")  # v2 torrents
                            files_to_verify.append(
                                {
                                    "path": file_path,
                                    "sha1": file_sha1,
                                    "length": file_entry.get("length", 0),
                                }
                            )

            # Also check file_tree for v2 torrents
            file_tree = torrent_data.get("file_tree")
            if file_tree and isinstance(file_tree, dict):
                # v2 torrent file tree structure
                base_name = torrent_data.get("name", "")
                for file_path_str, file_data in file_tree.items():
                    if isinstance(file_data, dict):
                        file_path = output_dir / base_name / file_path_str
                        file_sha1 = file_data.get("file_sha1")
                        files_to_verify.append(
                            {
                                "path": file_path,
                                "sha1": file_sha1,
                                "length": file_data.get("length", 0),
                            }
                        )

            total_files = len(files_to_verify)
            verified_files: list[str] = []
            failed_files: list[str] = []

            # Get piece manager for piece-based verification
            piece_manager = torrent_session.piece_manager if hasattr(torrent_session, 'piece_manager') else None
            
            # Verify each file
            for idx, file_entry in enumerate(files_to_verify):
                file_path = file_entry["path"]
                file_sha1 = file_entry.get("sha1")
                file_length = file_entry.get("length", 0)
                
                # Check for cancellation
                if progress_callback:
                    should_continue = progress_callback(
                        idx, total_files, str(file_entry["path"])
                    )
                    if should_continue is False:
                        # Cancellation requested
                        return {
                            "status": "cancelled",
                            "info_hash": info_hash,
                            "verified_files": verified_files,
                            "failed_files": failed_files,
                            "total_files": total_files,
                            "verified_count": len(verified_files),
                            "failed_count": len(failed_files),
                        }

                # Check if file exists
                if not file_path.exists():
                    failed_files.append(str(file_path))
                    continue

                # Verify file
                try:
                    verified = False
                    
                    # For v2 torrents with file_sha1, verify directly
                    if file_sha1 and len(file_sha1) == 20:
                        # Use SHA-1 verification if available
                        verified = verify_file_sha1(file_path, file_sha1)
                    # For v1 torrents or files without file_sha1, verify using piece manager
                    elif piece_manager and hasattr(piece_manager, 'pieces'):
                        # Get file selection manager to map file to pieces
                        file_selection_manager = torrent_session.file_selection_manager
                        if file_selection_manager and hasattr(file_selection_manager, 'mapper'):
                            mapper = file_selection_manager.mapper
                            # Find file index
                            file_index = None
                            for f_idx, f_info in enumerate(mapper.files):
                                if f_info.name == file_path.name or str(file_path).endswith(f_info.name):
                                    file_index = f_idx
                                    break
                            
                            if file_index is not None and file_index in mapper.file_to_pieces:
                                # Get pieces for this file
                                piece_indices = mapper.file_to_pieces[file_index]
                                
                                # Get file assembler for reading piece data from disk
                                file_assembler = None
                                if hasattr(torrent_session, 'download_manager') and torrent_session.download_manager:
                                    file_assembler = getattr(torrent_session.download_manager, 'file_assembler', None)
                                
                                # Verify all pieces for this file
                                all_pieces_verified = True
                                for piece_idx in piece_indices:
                                    if piece_idx < len(piece_manager.pieces):
                                        piece = piece_manager.pieces[piece_idx]
                                        # Check if piece is already verified
                                        if piece.hash_verified and piece.state.name == "VERIFIED":
                                            continue  # Already verified, skip
                                        
                                        # Try to verify piece by reading from disk
                                        from ccbt.piece.hash_v2 import HashAlgorithm, verify_piece
                                        from ccbt.models import PieceState as PieceStateModel
                                        
                                        # Get expected hash from piece manager
                                        if piece_idx < len(piece_manager.piece_hashes):
                                            expected_hash = piece_manager.piece_hashes[piece_idx]
                                            
                                            # Read piece data from disk using file_assembler
                                            piece_data = None
                                            if file_assembler:
                                                try:
                                                    # Read the complete piece (begin=0, length=piece_length)
                                                    piece_data = await file_assembler.read_block(
                                                        piece_idx, 0, piece_manager.piece_length
                                                    )
                                                except Exception as e:
                                                    self.logger.debug(
                                                        "Failed to read piece %d from disk: %s",
                                                        piece_idx,
                                                        e,
                                                    )
                                            
                                            # If file_assembler read failed, try reading from piece if complete
                                            if not piece_data and piece.is_complete():
                                                try:
                                                    piece_data = piece.get_data()
                                                except Exception:
                                                    piece_data = None
                                            
                                            # Verify piece hash if we have data
                                            if piece_data:
                                                # Detect algorithm from hash length
                                                if len(expected_hash) == 32:
                                                    algorithm = HashAlgorithm.SHA256
                                                elif len(expected_hash) == 20:
                                                    algorithm = HashAlgorithm.SHA1
                                                else:
                                                    all_pieces_verified = False
                                                    break
                                                
                                                # Verify piece hash
                                                if verify_piece(piece_data, expected_hash, algorithm=algorithm):
                                                    # Mark piece as verified
                                                    piece.hash_verified = True
                                                    if piece.state.name != "VERIFIED":
                                                        piece.state = PieceStateModel.VERIFIED
                                                else:
                                                    all_pieces_verified = False
                                                    break
                                            else:
                                                # Cannot read piece data, mark as unverified
                                                all_pieces_verified = False
                                                break
                                        else:
                                            # No hash available for this piece
                                            all_pieces_verified = False
                                            break
                                
                                verified = all_pieces_verified
                            else:
                                # Fallback: check file size matches
                                expected_length = file_entry.get("length", 0)
                                verified = file_path.stat().st_size == expected_length if file_path.exists() else False
                        else:
                            # Fallback: check file size matches
                            expected_length = file_entry.get("length", 0)
                            verified = file_path.stat().st_size == expected_length if file_path.exists() else False
                    else:
                        # Fallback: check file size matches
                        expected_length = file_entry.get("length", 0)
                        verified = file_path.stat().st_size == expected_length if file_path.exists() else False
                    
                    if verified:
                        verified_files.append(str(file_path))
                    else:
                        failed_files.append(str(file_path))
                except Exception as e:
                    # Log error and mark as failed
                    self.logger.exception("Error verifying file %s: %s", file_path, e)
                    failed_files.append(str(file_path))
                    failed_files.append(str(file_path))

            return {
                "status": "completed",
                "info_hash": info_hash,
                "verified_files": verified_files,
                "failed_files": failed_files,
                "total_files": total_files,
                "verified_count": len(verified_files),
                "failed_count": len(failed_files),
            }

        except Exception as e:
            self.logger.exception("Error during file verification")
            return {
                "status": "error",
                "info_hash": info_hash,
                "error": str(e),
                "verified_files": [],
                "failed_files": [],
                "total_files": 0,
                "verified_count": 0,
                "failed_count": 0,
            }

    async def get_queue(self) -> QueueListResponse:
        """Get queue status."""
        from ccbt.daemon.ipc_protocol import QueueEntry, QueueListResponse

        if not self.session_manager.queue_manager:
            raise ValueError("Queue manager not initialized")

        status = await self.session_manager.queue_manager.get_queue_status()
        entries = []
        for entry in status["entries"]:
            entries.append(
                QueueEntry(
                    info_hash=entry["info_hash"],
                    queue_position=entry["queue_position"],
                    priority=entry["priority"],
                    status=entry["status"],
                    allocated_down_kib=entry["allocated_down_kib"],
                    allocated_up_kib=entry["allocated_up_kib"],
                ),
            )

        return QueueListResponse(entries=entries, statistics=status["statistics"])

    async def add_to_queue(self, info_hash: str, priority: str) -> dict[str, Any]:
        """Add torrent to queue."""
        from ccbt.models import TorrentPriority

        if not self.session_manager.queue_manager:
            raise ValueError("Queue manager not initialized")

        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            raise ValueError(f"Invalid info hash format: {info_hash}") from None

        try:
            priority_enum = TorrentPriority[priority.upper()]
        except KeyError:
            raise ValueError(f"Invalid priority: {priority}") from None

        success = await self.session_manager.queue_manager.add_to_queue(
            info_hash_bytes,
            priority_enum,
        )

        if not success:
            raise ValueError("Failed to add to queue")

        return {"status": "added", "info_hash": info_hash}

    async def remove_from_queue(self, info_hash: str) -> dict[str, Any]:
        """Remove torrent from queue."""
        if not self.session_manager.queue_manager:
            raise ValueError("Queue manager not initialized")

        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            raise ValueError(f"Invalid info hash format: {info_hash}") from None

        success = await self.session_manager.queue_manager.remove_from_queue(
            info_hash_bytes
        )
        if not success:
            raise ValueError("Torrent not found in queue")

        return {"status": "removed", "info_hash": info_hash}

    async def move_in_queue(self, info_hash: str, new_position: int) -> dict[str, Any]:
        """Move torrent in queue."""
        if not self.session_manager.queue_manager:
            raise ValueError("Queue manager not initialized")

        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            raise ValueError(f"Invalid info hash format: {info_hash}") from None

        success = await self.session_manager.queue_manager.move_in_queue(
            info_hash_bytes,
            new_position,
        )
        if not success:
            raise ValueError("Failed to move in queue")

        return {"status": "moved", "info_hash": info_hash, "new_position": new_position}

    async def clear_queue(self) -> dict[str, Any]:
        """Clear queue."""
        if not self.session_manager.queue_manager:
            raise ValueError("Queue manager not initialized")

        await self.session_manager.queue_manager.clear_queue()
        return {"status": "cleared"}

    async def pause_torrent_in_queue(self, info_hash: str) -> dict[str, Any]:
        """Pause torrent in queue."""
        success = await self.session_manager.pause_torrent(info_hash)
        if not success:
            raise ValueError("Torrent not found")

        return {"status": "paused", "info_hash": info_hash}

    async def resume_torrent_in_queue(self, info_hash: str) -> dict[str, Any]:
        """Resume torrent in queue."""
        success = await self.session_manager.resume_torrent(info_hash)
        if not success:
            raise ValueError("Torrent not found")

        return {"status": "resumed", "info_hash": info_hash}

    async def get_nat_status(self) -> NATStatusResponse:
        """Get NAT status."""
        from ccbt.daemon.ipc_protocol import NATStatusResponse

        nat_manager = getattr(self.session_manager, "nat_manager", None)
        if not nat_manager:
            return NATStatusResponse(
                enabled=False,
                method=None,
                external_ip=None,
                mapped_port=None,
                mappings=[],
            )

        status = await nat_manager.get_status()
        return NATStatusResponse(
            enabled=status.get("enabled", False),
            method=status.get("method"),
            external_ip=status.get("external_ip"),
            mapped_port=status.get("mapped_port"),
            mappings=status.get("mappings", []),
        )

    async def discover_nat(self) -> dict[str, Any]:
        """Discover NAT devices."""
        nat_manager = getattr(self.session_manager, "nat_manager", None)
        if not nat_manager:
            raise ValueError("NAT manager not available")

        result = await nat_manager.discover()
        return {"status": "discovered", "result": result}

    async def map_nat_port(
        self,
        internal_port: int,
        external_port: int | None = None,
        protocol: str = "tcp",
    ) -> dict[str, Any]:
        """Map a port via NAT."""
        nat_manager = getattr(self.session_manager, "nat_manager", None)
        if not nat_manager:
            raise ValueError("NAT manager not available")

        result = await nat_manager.map_port(
            internal_port,
            external_port,
            protocol,
        )
        return {"status": "mapped", "result": result}

    async def unmap_nat_port(self, port: int, protocol: str = "tcp") -> dict[str, Any]:
        """Unmap a port via NAT."""
        nat_manager = getattr(self.session_manager, "nat_manager", None)
        if not nat_manager:
            raise ValueError("NAT manager not available")

        result = await nat_manager.unmap_port(port, protocol)
        return {"status": "unmapped", "result": result}

    async def refresh_nat_mappings(self) -> dict[str, Any]:
        """Refresh NAT mappings."""
        nat_manager = getattr(self.session_manager, "nat_manager", None)
        if not nat_manager:
            raise ValueError("NAT manager not available")

        result = await nat_manager.refresh_mappings()
        return {"status": "refreshed", "result": result}

    async def scrape_torrent(self, info_hash: str, force: bool = False) -> ScrapeResult:
        """Scrape a torrent."""
        from ccbt.daemon.ipc_protocol import ScrapeResult

        if force:
            success = await self.session_manager.force_scrape(info_hash)
        else:
            # Check cache first
            result = await self.session_manager.get_scrape_result(info_hash)
            if result:
                return ScrapeResult(
                    info_hash=info_hash,
                    seeders=result.seeders,
                    leechers=result.leechers,
                    completed=result.completed,
                    last_scrape_time=result.last_scrape_time,
                    scrape_count=result.scrape_count,
                )

            success = await self.session_manager.force_scrape(info_hash)

        if not success:
            raise ValueError("Scrape failed")

        result = await self.session_manager.get_scrape_result(info_hash)
        if not result:
            raise ValueError("Scrape succeeded but no result found")

        return ScrapeResult(
            info_hash=info_hash,
            seeders=result.seeders,
            leechers=result.leechers,
            completed=result.completed,
            last_scrape_time=result.last_scrape_time,
            scrape_count=result.scrape_count,
        )

    async def list_scrape_results(self) -> ScrapeListResponse:
        """List all cached scrape results."""
        from ccbt.daemon.ipc_protocol import ScrapeListResponse, ScrapeResult

        async with self.session_manager.scrape_cache_lock:
            results = list(self.session_manager.scrape_cache.values())

        scrape_results = []
        for result in results:
            scrape_results.append(
                ScrapeResult(
                    info_hash=result.info_hash,
                    seeders=result.seeders,
                    leechers=result.leechers,
                    completed=result.completed,
                    last_scrape_time=result.last_scrape_time,
                    scrape_count=result.scrape_count,
                ),
            )

        return ScrapeListResponse(results=scrape_results)

    async def get_config(self) -> dict[str, Any]:
        """Get current config."""
        return self.session_manager.config.model_dump(mode="json")

    async def update_config(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Update config."""
        from ccbt.config.config_templates import ConfigTemplates
        from ccbt.models import Config

        current_config = self.session_manager.config
        current_dict = current_config.model_dump(mode="json")
        merged_dict = ConfigTemplates._deep_merge(current_dict, config_dict)  # noqa: SLF001

        try:
            new_config = Config.model_validate(merged_dict)
        except Exception as validation_error:
            raise ValueError(
                f"Invalid configuration: {validation_error}"
            ) from validation_error

        from ccbt.cli.config_utils import requires_daemon_restart

        needs_restart = requires_daemon_restart(current_config, new_config)

        if not needs_restart:
            try:
                await self.session_manager.reload_config(new_config)
                return {
                    "status": "updated",
                    "restart_required": False,
                    "config": new_config.model_dump(mode="json"),
                }
            except Exception as reload_error:
                raise ValueError(
                    f"Failed to reload configuration: {reload_error}"
                ) from reload_error
        else:
            return {
                "status": "updated",
                "restart_required": True,
                "message": "Configuration updated but daemon restart is required to apply changes",
                "config": new_config.model_dump(mode="json"),
            }

    async def get_xet_protocol(self) -> ProtocolInfo:
        """Get Xet protocol information."""
        from ccbt.daemon.ipc_protocol import ProtocolInfo
        from ccbt.protocols.base import ProtocolType

        protocol_manager = getattr(self.session_manager, "protocol_manager", None)
        if not protocol_manager:
            return ProtocolInfo(
                enabled=False,
                status="not_available",
                details={},
            )

        xet_protocol = protocol_manager.get_protocol(ProtocolType.XET)
        if not xet_protocol:
            return ProtocolInfo(
                enabled=False,
                status="not_configured",
                details={},
            )

        # Get protocol info
        protocol_info = (
            xet_protocol.get_protocol_info()
            if hasattr(xet_protocol, "get_protocol_info")
            else {}
        )
        return ProtocolInfo(
            enabled=True,
            status="active",
            details={
                "protocol_type": "xet",
                **protocol_info,
            },
        )

    async def get_ipfs_protocol(self) -> ProtocolInfo:
        """Get IPFS protocol information."""
        from ccbt.daemon.ipc_protocol import ProtocolInfo
        from ccbt.protocols.base import ProtocolType

        protocol_manager = getattr(self.session_manager, "protocol_manager", None)
        if not protocol_manager:
            return ProtocolInfo(
                enabled=False,
                status="not_available",
                details={},
            )

        ipfs_protocol = protocol_manager.get_protocol(ProtocolType.IPFS)
        if not ipfs_protocol:
            return ProtocolInfo(
                enabled=False,
                status="not_configured",
                details={},
            )

        # Get protocol info
        protocol_info = (
            ipfs_protocol.get_protocol_info()
            if hasattr(ipfs_protocol, "get_protocol_info")
            else {}
        )
        return ProtocolInfo(
            enabled=True,
            status="active",
            details={
                "protocol_type": "ipfs",
                **protocol_info,
            },
        )

    async def get_peers_for_torrent(self, info_hash: str) -> list[dict[str, Any]]:
        """Get list of peers for a torrent."""
        return await self.session_manager.get_peers_for_torrent(info_hash)

    async def add_tracker(self, info_hash: str, tracker_url: str) -> dict[str, Any]:
        """Add a tracker URL to a torrent."""
        success = await self.session_manager.add_tracker(info_hash, tracker_url)
        return {"success": success}

    async def remove_tracker(self, info_hash: str, tracker_url: str) -> dict[str, Any]:
        """Remove a tracker URL from a torrent."""
        success = await self.session_manager.remove_tracker(info_hash, tracker_url)
        return {"success": success}

    async def add_xet_folder(
        self,
        folder_path: str,
        tonic_file: str | None = None,
        tonic_link: str | None = None,
        sync_mode: str | None = None,
        source_peers: list[str] | None = None,
        check_interval: float | None = None,
    ) -> str:
        """Add XET folder for synchronization."""
        return await self.session_manager.add_xet_folder(
            folder_path=folder_path,
            tonic_file=tonic_file,
            tonic_link=tonic_link,
            sync_mode=sync_mode,
            source_peers=source_peers,
            check_interval=check_interval,
        )

    async def remove_xet_folder(self, folder_key: str) -> bool:
        """Remove XET folder from synchronization."""
        return await self.session_manager.remove_xet_folder(folder_key)

    async def list_xet_folders(self) -> list[dict[str, Any]]:
        """List all registered XET folders."""
        return await self.session_manager.list_xet_folders()

    async def get_xet_folder_status(self, folder_key: str) -> dict[str, Any] | None:
        """Get XET folder status."""
        folder = await self.session_manager.get_xet_folder(folder_key)
        if not folder:
            return None

        status = folder.get_status()
        return status.model_dump()

    async def set_rate_limits(
        self,
        info_hash: str,
        download_kib: int,
        upload_kib: int,
    ) -> bool:
        """Set per-torrent rate limits."""
        return await self.session_manager.set_rate_limits(
            info_hash, download_kib, upload_kib
        )

    async def force_announce(self, info_hash: str) -> bool:
        """Force a tracker announce for a torrent."""
        return await self.session_manager.force_announce(info_hash)

    async def refresh_pex(self, info_hash: str) -> dict[str, Any]:
        """Refresh PEX (Peer Exchange) for a torrent."""
        success = await self.session_manager.refresh_pex(info_hash)
        return {"success": success, "info_hash": info_hash}

    async def rehash_torrent(self, info_hash: str) -> dict[str, Any]:
        """Rehash all pieces for a torrent."""
        success = await self.session_manager.rehash_torrent(info_hash)
        return {"success": success, "info_hash": info_hash}

    async def export_session_state(self, path: str) -> None:
        """Export session state to a file."""
        from pathlib import Path

        await self.session_manager.export_session_state(Path(path))

    async def import_session_state(self, path: str) -> dict[str, Any]:
        """Import session state from a file."""
        from pathlib import Path

        return await self.session_manager.import_session_state(Path(path))

    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all torrents."""
        return await self.session_manager.get_global_stats()

    async def global_pause_all(self) -> dict[str, Any]:
        """Pause all torrents."""
        return await self.session_manager.global_pause_all()

    async def global_resume_all(self) -> dict[str, Any]:
        """Resume all paused torrents."""
        return await self.session_manager.global_resume_all()

    async def global_force_start_all(self) -> dict[str, Any]:
        """Force start all torrents."""
        return await self.session_manager.global_force_start_all()

    async def global_set_rate_limits(self, download_kib: int, upload_kib: int) -> bool:
        """Set global rate limits."""
        return await self.session_manager.global_set_rate_limits(download_kib, upload_kib)

    async def set_per_peer_rate_limit(
        self, info_hash: str, peer_key: str, upload_limit_kib: int
    ) -> bool:
        """Set per-peer upload rate limit."""
        return await self.session_manager.set_per_peer_rate_limit(
            info_hash, peer_key, upload_limit_kib
        )

    async def get_per_peer_rate_limit(
        self, info_hash: str, peer_key: str
    ) -> int | None:
        """Get per-peer upload rate limit."""
        return await self.session_manager.get_per_peer_rate_limit(info_hash, peer_key)

    async def set_all_peers_rate_limit(self, upload_limit_kib: int) -> int:
        """Set per-peer upload rate limit for all peers."""
        return await self.session_manager.set_all_peers_rate_limit(upload_limit_kib)

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: Any,
        torrent_path: str | None = None,
    ) -> str:
        """Resume download from checkpoint."""
        return await self.session_manager.resume_from_checkpoint(
            info_hash,
            checkpoint,
            torrent_path=torrent_path,
        )

    async def get_scrape_result(self, info_hash: str) -> Any | None:
        """Get cached scrape result for a torrent."""
        # Access scrape_cache via scrape_cache_lock
        if not hasattr(self.session_manager, "scrape_cache") or not hasattr(
            self.session_manager, "scrape_cache_lock"
        ):
            return None
        try:
            info_hash_bytes = bytes.fromhex(info_hash)
        except ValueError:
            return None

        try:
            async with self.session_manager.scrape_cache_lock:
                return self.session_manager.scrape_cache.get(info_hash_bytes)
        except (AttributeError, KeyError):
            return None


class DaemonSessionAdapter(SessionAdapter):
    """Adapter for daemon IPC client."""

    def __init__(self, ipc_client: Any):
        """Initialize daemon session adapter.

        Args:
            ipc_client: IPCClient instance

        """
        self.ipc_client = ipc_client
        # Try to get config from IPC client if available
        self.config = None
        self.logger = logging.getLogger(__name__)

    def _convert_peer_list_response(
        self, peer_list_response: Any
    ) -> list[dict[str, Any]]:
        """Convert PeerListResponse to list of peer dictionaries.

        Args:
            peer_list_response: PeerListResponse from IPC client

        Returns:
            List of peer dictionaries with keys: ip, port, download_rate, upload_rate, choked, client

        """
        peers = []
        for peer_info in peer_list_response.peers:
            peers.append(
                {
                    "ip": peer_info.ip,
                    "port": peer_info.port,
                    "download_rate": peer_info.download_rate,
                    "upload_rate": peer_info.upload_rate,
                    "choked": peer_info.choked,
                    "client": peer_info.client,
                }
            )
        return peers

    def _convert_global_stats_response(self, stats_response: Any) -> dict[str, Any]:
        """Convert GlobalStatsResponse to dictionary.

        Args:
            stats_response: GlobalStatsResponse from IPC client

        Returns:
            Dictionary with aggregated stats (num_torrents, num_active, etc.)

        """
        return {
            "num_torrents": stats_response.num_torrents,
            "num_active": stats_response.num_active,
            "num_paused": stats_response.num_paused,
            "download_rate": stats_response.total_download_rate,
            "upload_rate": stats_response.total_upload_rate,
            "total_downloaded": stats_response.total_downloaded,
            "total_uploaded": stats_response.total_uploaded,
            **stats_response.stats,
        }

    async def add_tracker(self, info_hash: str, tracker_url: str) -> dict[str, Any]:
        """Add a tracker URL to a torrent."""
        return await self.ipc_client.add_tracker(info_hash, tracker_url)

    async def remove_tracker(self, info_hash: str, tracker_url: str) -> dict[str, Any]:
        """Remove a tracker URL from a torrent."""
        return await self.ipc_client.remove_tracker(info_hash, tracker_url)

    async def global_pause_all(self) -> dict[str, Any]:
        """Pause all torrents."""
        return await self.ipc_client.global_pause_all()

    async def global_resume_all(self) -> dict[str, Any]:
        """Resume all paused torrents."""
        return await self.ipc_client.global_resume_all()

    async def global_force_start_all(self) -> dict[str, Any]:
        """Force start all torrents."""
        return await self.ipc_client.global_force_start_all()

    async def global_set_rate_limits(self, download_kib: int, upload_kib: int) -> bool:
        """Set global rate limits for all torrents."""
        return await self.ipc_client.global_set_rate_limits(download_kib, upload_kib)

    async def set_per_peer_rate_limit(
        self,
        info_hash: str,
        peer_key: str,
        upload_limit_kib: int,
    ) -> bool:
        """Set upload rate limit for a specific peer."""
        return await self.ipc_client.set_per_peer_rate_limit(
            info_hash, peer_key, upload_limit_kib
        )

    async def get_per_peer_rate_limit(
        self,
        info_hash: str,
        peer_key: str,
    ) -> int:
        """Get upload rate limit for a specific peer."""
        return await self.ipc_client.get_per_peer_rate_limit(info_hash, peer_key)

    async def set_all_peers_rate_limit(self, upload_limit_kib: int) -> int:
        """Set upload rate limit for all peers across all torrents."""
        return await self.ipc_client.set_all_peers_rate_limit(upload_limit_kib)

    async def add_torrent(
        self,
        path_or_magnet: str,
        output_dir: str | None = None,
        resume: bool = False,
    ) -> str:
        """Add torrent or magnet."""
        try:
            return await self.ipc_client.add_torrent(
                path_or_magnet, output_dir=output_dir, resume=resume
            )
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to add torrent: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            self.logger.error(
                "Daemon returned error %d when adding torrent: %s",
                e.status,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when adding torrent: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors
            self.logger.error(
                "Error adding torrent to daemon: %s",
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def remove_torrent(self, info_hash: str) -> bool:
        """Remove torrent."""
        return await self.ipc_client.remove_torrent(info_hash)

    async def list_torrents(self) -> list[TorrentStatusResponse]:
        """List all torrents."""
        return await self.ipc_client.list_torrents()

    async def get_torrent_status(self, info_hash: str) -> TorrentStatusResponse | None:
        """Get torrent status."""
        return await self.ipc_client.get_torrent_status(info_hash)

    async def pause_torrent(self, info_hash: str) -> bool:
        """Pause torrent."""
        return await self.ipc_client.pause_torrent(info_hash)

    async def resume_torrent(self, info_hash: str) -> bool:
        """Resume torrent."""
        return await self.ipc_client.resume_torrent(info_hash)

    async def cancel_torrent(self, info_hash: str) -> bool:
        """Cancel torrent."""
        return await self.ipc_client.cancel_torrent(info_hash)

    async def force_start_torrent(self, info_hash: str) -> bool:
        """Force start torrent."""
        return await self.ipc_client.force_start_torrent(info_hash)

    async def batch_pause_torrents(
        self, info_hashes: list[str]
    ) -> dict[str, Any]:
        """Pause multiple torrents in a single request."""
        return await self.ipc_client.batch_pause_torrents(info_hashes)

    async def batch_resume_torrents(
        self, info_hashes: list[str]
    ) -> dict[str, Any]:
        """Resume multiple torrents in a single request."""
        return await self.ipc_client.batch_resume_torrents(info_hashes)

    async def batch_restart_torrents(
        self, info_hashes: list[str]
    ) -> dict[str, Any]:
        """Restart multiple torrents in a single request."""
        return await self.ipc_client.batch_restart_torrents(info_hashes)

    async def batch_remove_torrents(
        self, info_hashes: list[str], remove_data: bool = False
    ) -> dict[str, Any]:
        """Remove multiple torrents in a single request."""
        return await self.ipc_client.batch_remove_torrents(
            info_hashes, remove_data=remove_data
        )

    async def get_services_status(self) -> dict[str, Any]:
        """Get status of all services."""
        return await self.ipc_client.get_services_status()

    async def get_torrent_files(self, info_hash: str) -> FileListResponse:
        """Get file list for a torrent."""
        return await self.ipc_client.get_torrent_files(info_hash)

    async def select_files(
        self, info_hash: str, file_indices: list[int]
    ) -> dict[str, Any]:
        """Select files for download."""
        return await self.ipc_client.select_files(info_hash, file_indices)

    async def deselect_files(
        self, info_hash: str, file_indices: list[int]
    ) -> dict[str, Any]:
        """Deselect files."""
        return await self.ipc_client.deselect_files(info_hash, file_indices)

    async def set_file_priority(
        self,
        info_hash: str,
        file_index: int,
        priority: str,
    ) -> dict[str, Any]:
        """Set file priority."""
        return await self.ipc_client.set_file_priority(info_hash, file_index, priority)

    async def verify_files(self, info_hash: str) -> dict[str, Any]:
        """Verify torrent files."""
        return await self.ipc_client.verify_files(info_hash)

    async def get_queue(self) -> QueueListResponse:
        """Get queue status."""
        return await self.ipc_client.get_queue()

    async def add_to_queue(self, info_hash: str, priority: str) -> dict[str, Any]:
        """Add torrent to queue."""
        return await self.ipc_client.add_to_queue(info_hash, priority)

    async def remove_from_queue(self, info_hash: str) -> dict[str, Any]:
        """Remove torrent from queue."""
        return await self.ipc_client.remove_from_queue(info_hash)

    async def move_in_queue(self, info_hash: str, new_position: int) -> dict[str, Any]:
        """Move torrent in queue."""
        return await self.ipc_client.move_in_queue(info_hash, new_position)

    async def clear_queue(self) -> dict[str, Any]:
        """Clear queue."""
        return await self.ipc_client.clear_queue()

    async def pause_torrent_in_queue(self, info_hash: str) -> dict[str, Any]:
        """Pause torrent in queue."""
        return await self.ipc_client.pause_torrent_in_queue(info_hash)

    async def resume_torrent_in_queue(self, info_hash: str) -> dict[str, Any]:
        """Resume torrent in queue."""
        return await self.ipc_client.resume_torrent_in_queue(info_hash)

    async def get_nat_status(self) -> NATStatusResponse:
        """Get NAT status."""
        return await self.ipc_client.get_nat_status()

    async def discover_nat(self) -> dict[str, Any]:
        """Discover NAT devices."""
        return await self.ipc_client.discover_nat()

    async def map_nat_port(
        self,
        internal_port: int,
        external_port: int | None = None,
        protocol: str = "tcp",
    ) -> dict[str, Any]:
        """Map a port via NAT."""
        return await self.ipc_client.map_nat_port(
            internal_port, external_port, protocol
        )

    async def unmap_nat_port(self, port: int, protocol: str = "tcp") -> dict[str, Any]:
        """Unmap a port via NAT."""
        return await self.ipc_client.unmap_nat_port(port, protocol)

    async def refresh_nat_mappings(self) -> dict[str, Any]:
        """Refresh NAT mappings."""
        return await self.ipc_client.refresh_nat_mappings()

    async def scrape_torrent(self, info_hash: str, force: bool = False) -> ScrapeResult:
        """Scrape a torrent."""
        return await self.ipc_client.scrape_torrent(info_hash, force=force)

    async def list_scrape_results(self) -> ScrapeListResponse:
        """List all cached scrape results."""
        return await self.ipc_client.list_scrape_results()

    async def get_config(self) -> dict[str, Any]:
        """Get current config."""
        return await self.ipc_client.get_config()

    async def update_config(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Update config."""
        return await self.ipc_client.update_config(config_dict)

    async def get_xet_protocol(self) -> ProtocolInfo:
        """Get Xet protocol information."""
        return await self.ipc_client.get_xet_protocol()

    async def get_ipfs_protocol(self) -> ProtocolInfo:
        """Get IPFS protocol information."""
        return await self.ipc_client.get_ipfs_protocol()

    async def get_peers_for_torrent(self, info_hash: str) -> list[dict[str, Any]]:
        """Get list of peers for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            List of peer dictionaries with keys: ip, port, download_rate, upload_rate, choked, client

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            peer_list_response = await self.ipc_client.get_peers_for_torrent(info_hash)
            return self._convert_peer_list_response(peer_list_response)
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get peers for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Torrent not found - return empty list
                return []
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when getting peers for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting peers: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting peers for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def set_rate_limits(
        self,
        info_hash: str,
        download_kib: int,
        upload_kib: int,
    ) -> bool:
        """Set per-torrent rate limits.

        Args:
            info_hash: Torrent info hash (hex string)
            download_kib: Download limit in KiB/s
            upload_kib: Upload limit in KiB/s

        Returns:
            True if set successfully, False if torrent not found or operation failed

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            result = await self.ipc_client.set_rate_limits(
                info_hash,
                download_kib,
                upload_kib,
            )
            # IPC client returns dict, check if operation was successful
            return result.get("status") == "updated" or result.get("set", False)
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to set rate limits for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Torrent not found - return False as per interface
                return False
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when setting rate limits for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when setting rate limits: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error setting rate limits for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def refresh_pex(self, info_hash: str) -> dict[str, Any]:
        """Refresh PEX (Peer Exchange) for a torrent via daemon IPC."""
        if hasattr(self.ipc_client, "refresh_pex"):
            try:
                result = await self.ipc_client.refresh_pex(info_hash)
                if isinstance(result, dict):
                    success = bool(
                        result.get("success")
                        or result.get("refreshed")
                        or result.get("status") in {"ok", "refreshed"}
                    )
                    result.setdefault("success", success)
                    return result
                return {"success": bool(result), "result": result}
            except Exception as exc:  # pragma: no cover - best-effort logging
                self.logger.error(
                    "Daemon error while refreshing PEX for %s: %s", info_hash, exc
                )
                return {"success": False, "error": str(exc)}

        self.logger.warning(
            "Daemon IPC client does not implement refresh_pex; returning not supported."
        )
        return {
            "success": False,
            "error": "refresh_pex not supported by daemon session",
        }

    async def rehash_torrent(self, info_hash: str) -> dict[str, Any]:
        """Rehash all pieces for a torrent via daemon IPC."""
        if hasattr(self.ipc_client, "rehash_torrent"):
            try:
                result = await self.ipc_client.rehash_torrent(info_hash)
                if isinstance(result, dict):
                    success = bool(
                        result.get("success")
                        or result.get("status") in {"started", "rehashing", "ok"}
                    )
                    result.setdefault("success", success)
                    return result
                return {"success": bool(result), "result": result}
            except Exception as exc:  # pragma: no cover - best-effort logging
                self.logger.error(
                    "Daemon error while rehashing torrent %s: %s", info_hash, exc
                )
                return {"success": False, "error": str(exc)}

        self.logger.warning(
            "Daemon IPC client does not implement rehash_torrent; returning not supported."
        )
        return {
            "success": False,
            "error": "rehash_torrent not supported by daemon session",
        }

    async def add_xet_folder(
        self,
        folder_path: str,
        tonic_file: str | None = None,
        tonic_link: str | None = None,
        sync_mode: str | None = None,
        source_peers: list[str] | None = None,
        check_interval: float | None = None,
    ) -> str:
        """Add XET folder for synchronization."""
        try:
            session = await self.ipc_client._ensure_session()
            from ccbt.daemon.ipc_protocol import API_BASE_PATH

            url = f"{self.ipc_client.base_url}{API_BASE_PATH}/xet/folders/add"

            payload = {
                "folder_path": folder_path,
            }
            if tonic_file:
                payload["tonic_file"] = tonic_file
            if tonic_link:
                payload["tonic_link"] = tonic_link
            if sync_mode:
                payload["sync_mode"] = sync_mode
            if source_peers:
                payload["source_peers"] = source_peers
            if check_interval:
                payload["check_interval"] = check_interval

            async with session.post(
                url, json=payload, headers=self.ipc_client._get_headers("POST", url)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("folder_key", folder_path)
        except Exception as e:
            self.logger.exception("Error adding XET folder")
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def remove_xet_folder(self, folder_key: str) -> bool:
        """Remove XET folder from synchronization."""
        try:
            session = await self.ipc_client._ensure_session()
            from ccbt.daemon.ipc_protocol import API_BASE_PATH

            url = f"{self.ipc_client.base_url}{API_BASE_PATH}/xet/folders/{folder_key}"

            async with session.delete(
                url, headers=self.ipc_client._get_headers("DELETE", url)
            ) as resp:
                if resp.status == 404:
                    return False
                resp.raise_for_status()
                data = await resp.json()
                return data.get("status") == "removed"
        except Exception as e:
            self.logger.exception("Error removing XET folder")
            return False

    async def list_xet_folders(self) -> list[dict[str, Any]]:
        """List all registered XET folders."""
        try:
            session = await self.ipc_client._ensure_session()
            from ccbt.daemon.ipc_protocol import API_BASE_PATH

            url = f"{self.ipc_client.base_url}{API_BASE_PATH}/xet/folders"

            async with session.get(
                url, headers=self.ipc_client._get_headers("GET", url)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("folders", [])
        except Exception as e:
            self.logger.exception("Error listing XET folders")
            return []

    async def get_xet_folder_status(self, folder_key: str) -> dict[str, Any] | None:
        """Get XET folder status."""
        try:
            session = await self.ipc_client._ensure_session()
            from ccbt.daemon.ipc_protocol import API_BASE_PATH

            url = f"{self.ipc_client.base_url}{API_BASE_PATH}/xet/folders/{folder_key}"

            async with session.get(
                url, headers=self.ipc_client._get_headers("GET", url)
            ) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                data = await resp.json()
                return data
        except Exception as e:
            self.logger.exception("Error getting XET folder status")
            return None

    async def force_announce(self, info_hash: str) -> bool:
        """Force a tracker announce for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            True if announced successfully, False if torrent not found or operation failed

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            result = await self.ipc_client.force_announce(info_hash)
            # IPC client returns dict, check if operation was successful
            return result.get("status") == "announced" or result.get("announced", False)
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to force announce for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Torrent not found - return False as per interface
                return False
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when forcing announce for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when forcing announce: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error forcing announce for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def export_session_state(self, path: str) -> None:
        """Export session state to a file."""
        try:
            # IPC client returns dict with export info, but adapter interface expects None
            await self.ipc_client.export_session_state(path)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error exporting session state to %s: %s", path, e)
            raise

    async def import_session_state(self, path: str) -> dict[str, Any]:
        """Import session state from a file."""
        try:
            result = await self.ipc_client.import_session_state(path)
            # IPC client returns dict with imported state
            return result.get("state", result)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error importing session state from %s: %s", path, e)
            raise

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: Any,
        torrent_path: str | None = None,
    ) -> str:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash (bytes) - Note: This method uses bytes instead of hex string
                for compatibility with checkpoint data structures. Internally converts to hex string
                for IPC communication.
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Info hash hex string of resumed torrent

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            # Convert bytes to hex string for IPC client (IPC protocol uses hex strings)
            info_hash_hex = info_hash.hex()
            result = await self.ipc_client.resume_from_checkpoint(
                info_hash_hex,
                checkpoint,
                torrent_path=torrent_path,
            )
            # IPC client returns dict with info_hash
            return result.get("info_hash", info_hash_hex)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(
                "Error resuming from checkpoint for torrent %s: %s", info_hash.hex(), e
            )
            raise

    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all torrents.

        Returns:
            Dictionary with aggregated stats (num_torrents, num_active, etc.)

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            stats_response = await self.ipc_client.get_global_stats()
            return self._convert_global_stats_response(stats_response)
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get global stats: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            self.logger.error(
                "Daemon returned error %d when getting global stats: %s",
                e.status,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting global stats: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting global stats: %s",
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def get_scrape_result(self, info_hash: str) -> Any | None:
        """Get cached scrape result for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            ScrapeResult if cached, None if not found

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            result = await self.ipc_client.get_scrape_result(info_hash)
            return result
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get scrape result for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Scrape result not found - return None as per interface
                return None
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when getting scrape result for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting scrape result: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting scrape result for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to force announce for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Torrent not found - return False as per interface
                return False
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when forcing announce for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when forcing announce: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error forcing announce for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def export_session_state(self, path: str) -> None:
        """Export session state to a file."""
        try:
            # IPC client returns dict with export info, but adapter interface expects None
            await self.ipc_client.export_session_state(path)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error exporting session state to %s: %s", path, e)
            raise

    async def import_session_state(self, path: str) -> dict[str, Any]:
        """Import session state from a file."""
        try:
            result = await self.ipc_client.import_session_state(path)
            # IPC client returns dict with imported state
            return result.get("state", result)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error importing session state from %s: %s", path, e)
            raise

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: Any,
        torrent_path: str | None = None,
    ) -> str:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash (bytes) - Note: This method uses bytes instead of hex string
                for compatibility with checkpoint data structures. Internally converts to hex string
                for IPC communication.
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Info hash hex string of resumed torrent

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            # Convert bytes to hex string for IPC client (IPC protocol uses hex strings)
            info_hash_hex = info_hash.hex()
            result = await self.ipc_client.resume_from_checkpoint(
                info_hash_hex,
                checkpoint,
                torrent_path=torrent_path,
            )
            # IPC client returns dict with info_hash
            return result.get("info_hash", info_hash_hex)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(
                "Error resuming from checkpoint for torrent %s: %s", info_hash.hex(), e
            )
            raise

    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all torrents.

        Returns:
            Dictionary with aggregated stats (num_torrents, num_active, etc.)

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            stats_response = await self.ipc_client.get_global_stats()
            return self._convert_global_stats_response(stats_response)
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get global stats: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            self.logger.error(
                "Daemon returned error %d when getting global stats: %s",
                e.status,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting global stats: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting global stats: %s",
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def get_scrape_result(self, info_hash: str) -> Any | None:
        """Get cached scrape result for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            ScrapeResult if cached, None if not found

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            result = await self.ipc_client.get_scrape_result(info_hash)
            return result
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get scrape result for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Scrape result not found - return None as per interface
                return None
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when getting scrape result for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting scrape result: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting scrape result for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to force announce for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Torrent not found - return False as per interface
                return False
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when forcing announce for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when forcing announce: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error forcing announce for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def export_session_state(self, path: str) -> None:
        """Export session state to a file."""
        try:
            # IPC client returns dict with export info, but adapter interface expects None
            await self.ipc_client.export_session_state(path)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error exporting session state to %s: %s", path, e)
            raise

    async def import_session_state(self, path: str) -> dict[str, Any]:
        """Import session state from a file."""
        try:
            result = await self.ipc_client.import_session_state(path)
            # IPC client returns dict with imported state
            return result.get("state", result)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error importing session state from %s: %s", path, e)
            raise

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: Any,
        torrent_path: str | None = None,
    ) -> str:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash (bytes) - Note: This method uses bytes instead of hex string
                for compatibility with checkpoint data structures. Internally converts to hex string
                for IPC communication.
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Info hash hex string of resumed torrent

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            # Convert bytes to hex string for IPC client (IPC protocol uses hex strings)
            info_hash_hex = info_hash.hex()
            result = await self.ipc_client.resume_from_checkpoint(
                info_hash_hex,
                checkpoint,
                torrent_path=torrent_path,
            )
            # IPC client returns dict with info_hash
            return result.get("info_hash", info_hash_hex)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(
                "Error resuming from checkpoint for torrent %s: %s", info_hash.hex(), e
            )
            raise

    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all torrents.

        Returns:
            Dictionary with aggregated stats (num_torrents, num_active, etc.)

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            stats_response = await self.ipc_client.get_global_stats()
            return self._convert_global_stats_response(stats_response)
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get global stats: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            self.logger.error(
                "Daemon returned error %d when getting global stats: %s",
                e.status,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting global stats: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting global stats: %s",
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def get_scrape_result(self, info_hash: str) -> Any | None:
        """Get cached scrape result for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            ScrapeResult if cached, None if not found

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            result = await self.ipc_client.get_scrape_result(info_hash)
            return result
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get scrape result for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Scrape result not found - return None as per interface
                return None
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when getting scrape result for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting scrape result: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting scrape result for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to force announce for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Torrent not found - return False as per interface
                return False
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when forcing announce for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when forcing announce: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error forcing announce for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def export_session_state(self, path: str) -> None:
        """Export session state to a file."""
        try:
            # IPC client returns dict with export info, but adapter interface expects None
            await self.ipc_client.export_session_state(path)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error exporting session state to %s: %s", path, e)
            raise

    async def import_session_state(self, path: str) -> dict[str, Any]:
        """Import session state from a file."""
        try:
            result = await self.ipc_client.import_session_state(path)
            # IPC client returns dict with imported state
            return result.get("state", result)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error importing session state from %s: %s", path, e)
            raise

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: Any,
        torrent_path: str | None = None,
    ) -> str:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash (bytes) - Note: This method uses bytes instead of hex string
                for compatibility with checkpoint data structures. Internally converts to hex string
                for IPC communication.
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Info hash hex string of resumed torrent

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            # Convert bytes to hex string for IPC client (IPC protocol uses hex strings)
            info_hash_hex = info_hash.hex()
            result = await self.ipc_client.resume_from_checkpoint(
                info_hash_hex,
                checkpoint,
                torrent_path=torrent_path,
            )
            # IPC client returns dict with info_hash
            return result.get("info_hash", info_hash_hex)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(
                "Error resuming from checkpoint for torrent %s: %s", info_hash.hex(), e
            )
            raise

    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all torrents.

        Returns:
            Dictionary with aggregated stats (num_torrents, num_active, etc.)

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            stats_response = await self.ipc_client.get_global_stats()
            return self._convert_global_stats_response(stats_response)
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get global stats: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            self.logger.error(
                "Daemon returned error %d when getting global stats: %s",
                e.status,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting global stats: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting global stats: %s",
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def get_scrape_result(self, info_hash: str) -> Any | None:
        """Get cached scrape result for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            ScrapeResult if cached, None if not found

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            result = await self.ipc_client.get_scrape_result(info_hash)
            return result
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get scrape result for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Scrape result not found - return None as per interface
                return None
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when getting scrape result for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting scrape result: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting scrape result for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to force announce for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Torrent not found - return False as per interface
                return False
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when forcing announce for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when forcing announce: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error forcing announce for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def export_session_state(self, path: str) -> None:
        """Export session state to a file."""
        try:
            # IPC client returns dict with export info, but adapter interface expects None
            await self.ipc_client.export_session_state(path)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error exporting session state to %s: %s", path, e)
            raise

    async def import_session_state(self, path: str) -> dict[str, Any]:
        """Import session state from a file."""
        try:
            result = await self.ipc_client.import_session_state(path)
            # IPC client returns dict with imported state
            return result.get("state", result)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error importing session state from %s: %s", path, e)
            raise

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: Any,
        torrent_path: str | None = None,
    ) -> str:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash (bytes) - Note: This method uses bytes instead of hex string
                for compatibility with checkpoint data structures. Internally converts to hex string
                for IPC communication.
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Info hash hex string of resumed torrent

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            # Convert bytes to hex string for IPC client (IPC protocol uses hex strings)
            info_hash_hex = info_hash.hex()
            result = await self.ipc_client.resume_from_checkpoint(
                info_hash_hex,
                checkpoint,
                torrent_path=torrent_path,
            )
            # IPC client returns dict with info_hash
            return result.get("info_hash", info_hash_hex)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(
                "Error resuming from checkpoint for torrent %s: %s", info_hash.hex(), e
            )
            raise

    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all torrents.

        Returns:
            Dictionary with aggregated stats (num_torrents, num_active, etc.)

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            stats_response = await self.ipc_client.get_global_stats()
            return self._convert_global_stats_response(stats_response)
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get global stats: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            self.logger.error(
                "Daemon returned error %d when getting global stats: %s",
                e.status,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting global stats: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting global stats: %s",
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def get_scrape_result(self, info_hash: str) -> Any | None:
        """Get cached scrape result for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            ScrapeResult if cached, None if not found

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            result = await self.ipc_client.get_scrape_result(info_hash)
            return result
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get scrape result for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Scrape result not found - return None as per interface
                return None
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when getting scrape result for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting scrape result: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting scrape result for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to force announce for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Torrent not found - return False as per interface
                return False
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when forcing announce for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when forcing announce: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error forcing announce for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def export_session_state(self, path: str) -> None:
        """Export session state to a file."""
        try:
            # IPC client returns dict with export info, but adapter interface expects None
            await self.ipc_client.export_session_state(path)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error exporting session state to %s: %s", path, e)
            raise

    async def import_session_state(self, path: str) -> dict[str, Any]:
        """Import session state from a file."""
        try:
            result = await self.ipc_client.import_session_state(path)
            # IPC client returns dict with imported state
            return result.get("state", result)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Error importing session state from %s: %s", path, e)
            raise

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: Any,
        torrent_path: str | None = None,
    ) -> str:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash (bytes) - Note: This method uses bytes instead of hex string
                for compatibility with checkpoint data structures. Internally converts to hex string
                for IPC communication.
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Info hash hex string of resumed torrent

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            # Convert bytes to hex string for IPC client (IPC protocol uses hex strings)
            info_hash_hex = info_hash.hex()
            result = await self.ipc_client.resume_from_checkpoint(
                info_hash_hex,
                checkpoint,
                torrent_path=torrent_path,
            )
            # IPC client returns dict with info_hash
            return result.get("info_hash", info_hash_hex)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(
                "Error resuming from checkpoint for torrent %s: %s", info_hash.hex(), e
            )
            raise

    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all torrents.

        Returns:
            Dictionary with aggregated stats (num_torrents, num_active, etc.)

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            stats_response = await self.ipc_client.get_global_stats()
            return self._convert_global_stats_response(stats_response)
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get global stats: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            self.logger.error(
                "Daemon returned error %d when getting global stats: %s",
                e.status,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting global stats: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting global stats: %s",
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e

    async def get_scrape_result(self, info_hash: str) -> Any | None:
        """Get cached scrape result for a torrent.

        Args:
            info_hash: Torrent info hash (hex string)

        Returns:
            ScrapeResult if cached, None if not found

        Raises:
            RuntimeError: If daemon connection fails or IPC communication error occurs

        """
        try:
            result = await self.ipc_client.get_scrape_result(info_hash)
            return result
        except aiohttp.ClientConnectorError as e:
            # Connection refused - daemon not running or IPC server not accessible
            self.logger.error(
                "Cannot connect to daemon IPC server to get scrape result for torrent %s: %s. "
                "Is the daemon running? Try 'btbt daemon start'",
                info_hash,
                e,
            )
            raise RuntimeError(
                f"Cannot connect to daemon IPC server: {e}. "
                "Is the daemon running? Try 'btbt daemon start'"
            ) from e
        except aiohttp.ClientResponseError as e:
            # HTTP error response from daemon
            if e.status == 404:
                # Scrape result not found - return None as per interface
                return None
            # Other HTTP errors - raise exception
            self.logger.error(
                "Daemon returned error %d when getting scrape result for torrent %s: %s",
                e.status,
                info_hash,
                e.message,
            )
            raise RuntimeError(
                f"Daemon error when getting scrape result: HTTP {e.status}: {e.message}"
            ) from e
        except Exception as e:
            # Other errors - raise exception
            self.logger.error(
                "Error getting scrape result for torrent %s: %s",
                info_hash,
                e,
                exc_info=True,
            )
            raise RuntimeError(f"Error communicating with daemon: {e}") from e
