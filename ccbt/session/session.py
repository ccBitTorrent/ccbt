# ccbt/session.py
"""High-performance async session manager for ccBitTorrent.

Manages multiple torrents (file or magnet), coordinates tracker announces,
DHT, PEX, and provides status aggregation with async event loop management.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, cast

if TYPE_CHECKING:
    from ccbt.discovery.dht import AsyncDHTClient
    from ccbt.utils.di import DIContainer

from ccbt import (
    session as _session_mod,
)
from ccbt.config.config import get_config
from ccbt.core.magnet import build_minimal_torrent_data, parse_magnet
from ccbt.core.torrent import TorrentParser as _TorrentParser
from ccbt.discovery.pex import PEXManager
from ccbt.discovery.tracker import AsyncTrackerClient
from ccbt.models import PieceState, TorrentCheckpoint
from ccbt.models import TorrentInfo as TorrentInfoModel
from ccbt.services.peer_service import PeerService
from ccbt.storage.checkpoint import CheckpointManager
from ccbt.storage.file_assembler import AsyncDownloadManager
from ccbt.utils.exceptions import ValidationError
from ccbt.utils.logging_config import get_logger
from ccbt.utils.metrics import Metrics

# Expose TorrentParser at module level for test patching
TorrentParser = _TorrentParser

# Constants
INFO_HASH_LENGTH = 20  # SHA-1 hash length in bytes


@dataclass
class TorrentSessionInfo:
    """Information about a torrent session."""

    info_hash: bytes
    name: str
    output_dir: str
    added_time: float
    status: str = "starting"  # starting, downloading, seeding, stopped, error
    priority: str | None = None  # Queue priority (TorrentPriority enum value as string)
    queue_position: int | None = (
        None  # Position in queue (0 = highest priority position)
    )


class AsyncTorrentSession:
    """Represents one active torrent's lifecycle with async operations."""

    def __init__(
        self,
        torrent_data: dict[str, Any] | TorrentInfoModel,
        output_dir: str | Path = ".",
        session_manager: AsyncSessionManager | None = None,
    ) -> None:
        """Initialize TorrentSession with torrent data and output directory."""
        self.config = get_config()
        self.torrent_data = torrent_data
        self.output_dir = Path(output_dir)
        self.session_manager = session_manager

        # Core components
        self.download_manager = AsyncDownloadManager(torrent_data, str(output_dir))

        # Create a proper piece manager for checkpoint operations
        from ccbt.piece.async_piece_manager import AsyncPieceManager

        self._normalized_td = self._normalize_torrent_data(torrent_data)
        self.piece_manager = AsyncPieceManager(self._normalized_td)

        # Set the piece manager on the download manager for compatibility
        self.download_manager.piece_manager = self.piece_manager

        # CRITICAL FIX: Pass session_manager to AsyncTrackerClient
        # This ensures it uses the daemon's initialized UDP tracker client
        # instead of creating a new one, preventing WinError 10048
        self.tracker = AsyncTrackerClient()
        # Store session_manager reference so tracker can use initialized UDP client
        if session_manager:
            self.tracker._session_manager = session_manager  # type: ignore[attr-defined]
        self.pex_manager: PEXManager | None = None
        self.checkpoint_manager = CheckpointManager(self.config.disk)

        # Session state
        if isinstance(torrent_data, TorrentInfoModel):
            name = torrent_data.name
            info_hash = torrent_data.info_hash
        else:
            name = torrent_data.get("name") or torrent_data.get("file_info", {}).get(
                "name",
                "Unknown",
            )
            info_hash = torrent_data["info_hash"]

        self.info = TorrentSessionInfo(
            info_hash=info_hash,
            name=name,
            output_dir=str(output_dir),
            added_time=time.time(),
        )

        # Source tracking for checkpoint metadata
        self.torrent_file_path: str | None = None
        self.magnet_uri: str | None = None

        # Background tasks
        self._announce_task: asyncio.Task[None] | None = None
        self._status_task: asyncio.Task[None] | None = None
        self._checkpoint_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        # Checkpoint state
        self.checkpoint_loaded = False
        self.resume_from_checkpoint = False

        # Callbacks
        self.on_status_update: Callable[[dict[str, Any]], None] | None = None
        self.on_complete: Callable[[], None] | None = None
        self.on_error: Callable[[Exception], None] | None = None

        self.logger = get_logger(__name__)

        # Extract is_private flag for DHT discovery
        if isinstance(torrent_data, dict):
            self.is_private = torrent_data.get("is_private", False)
        elif hasattr(torrent_data, "is_private"):
            self.is_private = getattr(torrent_data, "is_private", False)
        else:
            self.is_private = False

        # Per-torrent configuration options (overrides global config for this torrent)
        # These are set via UI or API and applied during session.start()
        self.options: dict[str, Any] = {}

    def _apply_per_torrent_options(self) -> None:
        """Apply per-torrent configuration options, overriding global config.

        This method applies per-torrent settings like piece_selection,
        max_peers_per_torrent, streaming_mode, etc. to the appropriate components.
        """
        # Apply piece selection strategy if set
        if "piece_selection" in self.options:
            piece_selection = self.options["piece_selection"]
            if hasattr(self.piece_manager, "selection_strategy"):
                try:
                    from ccbt.models import PieceSelectionStrategy

                    # Convert string to enum if needed
                    if isinstance(piece_selection, str):
                        piece_selection = PieceSelectionStrategy(piece_selection)
                    self.piece_manager.selection_strategy = piece_selection
                    self.logger.debug(
                        "Applied per-torrent piece_selection: %s", piece_selection
                    )
                except (ValueError, AttributeError) as e:
                    self.logger.warning(
                        "Invalid piece_selection '%s': %s, using global default",
                        piece_selection,
                        e,
                    )
            # Also try setting via config if available
            if hasattr(self.piece_manager, "config") and hasattr(
                self.piece_manager.config, "strategy"
            ):
                try:
                    from ccbt.models import PieceSelectionStrategy

                    if isinstance(piece_selection, str):
                        piece_selection = PieceSelectionStrategy(piece_selection)
                    self.piece_manager.config.strategy.piece_selection = piece_selection
                except (ValueError, AttributeError):
                    pass

        # Apply streaming mode if set
        if "streaming_mode" in self.options:
            streaming_mode = bool(self.options["streaming_mode"])
            if hasattr(self.piece_manager, "streaming_mode"):
                self.piece_manager.streaming_mode = streaming_mode
                self.logger.debug(
                    "Applied per-torrent streaming_mode: %s", streaming_mode
                )

        # Apply sequential window size if set
        if "sequential_window_size" in self.options:
            seq_window = int(self.options["sequential_window_size"])
            if seq_window > 0 and hasattr(self.piece_manager, "sequential_window_size"):
                self.piece_manager.sequential_window_size = seq_window
                self.logger.debug(
                    "Applied per-torrent sequential_window_size: %s", seq_window
                )

        # Note: max_peers_per_torrent is applied when peer manager is created
        # (see peer manager initialization below)

    def _normalize_torrent_data(
        self,
        td: dict[str, Any] | TorrentInfoModel,
    ) -> dict[str, Any]:
        """Convert TorrentInfoModel or legacy dict into a normalized dict expected by piece manager.

        Returns a dict with keys: 'file_info', 'pieces_info', and minimal metadata.
        """
        if isinstance(td, dict):
            # Assume already using legacy dict shape or at least includes needed fields
            # Best-effort fill pieces_info / file_info if missing
            pieces_info = td.get("pieces_info")
            file_info = td.get("file_info")
            result: dict[str, Any] = dict(td)
            if (
                not pieces_info
                and "pieces" in td
                and "piece_length" in td
                and "num_pieces" in td
            ):
                result["pieces_info"] = {
                    "piece_hashes": td.get("pieces", []),
                    "piece_length": td.get("piece_length", 0),
                    "num_pieces": td.get("num_pieces", 0),
                    "total_length": td.get("total_length", 0),
                }
            if not file_info:
                result.setdefault(
                    "file_info",
                    {"total_length": td.get("total_length", 0)},
                )
            return result
        # TorrentInfoModel
        return {
            "name": td.name,
            "info_hash": td.info_hash,
            "pieces_info": {
                "piece_hashes": list(td.pieces),
                "piece_length": td.piece_length,
                "num_pieces": td.num_pieces,
                "total_length": td.total_length,
            },
            "file_info": {
                "total_length": td.total_length,
            },
        }

    def _should_prompt_for_resume(self) -> bool:
        """Determine if we should prompt user for resume."""
        # Only prompt if auto_resume is disabled and we're in interactive mode
        return not self.config.disk.auto_resume

    async def start(self, resume: bool = False) -> None:
        """Start the async torrent session."""
        try:
            self.info.status = "starting"

            # Check for existing checkpoint only if resuming
            checkpoint = None
            if self.config.disk.checkpoint_enabled and (
                resume or self.config.disk.auto_resume
            ):
                try:
                    checkpoint = await self.checkpoint_manager.load_checkpoint(
                        self.info.info_hash,
                    )
                    if checkpoint:
                        self.logger.info("Found checkpoint for %s", self.info.name)
                        self.resume_from_checkpoint = True
                        self.logger.info("Resuming from checkpoint")
                except Exception as e:
                    self.logger.warning("Failed to load checkpoint: %s", e)
                    checkpoint = None

            # Start tracker client
            await self.tracker.start()

            # Apply per-torrent configuration options (override global config)
            self._apply_per_torrent_options()

            # Start piece manager
            self.logger.debug("Starting piece manager for torrent: %s", self.info.name)
            try:
                await self.piece_manager.start()
                self.logger.debug("Piece manager started successfully")
            except Exception as e:
                self.logger.exception("Failed to start piece manager: %s", e)
                raise  # Re-raise - piece manager is critical

            # CRITICAL FIX: Initialize peer manager early, even without peers
            # This ensures _peer_manager is set on piece manager before piece selection starts
            # The peer manager can wait for peers to arrive from tracker/DHT/PEX
            if (
                not hasattr(self.download_manager, "peer_manager")
                or self.download_manager.peer_manager is None
            ):
                from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager

                # Extract is_private flag
                is_private = False
                try:
                    if isinstance(self.torrent_data, dict):
                        is_private = self.torrent_data.get("is_private", False)
                    elif hasattr(self.torrent_data, "is_private"):
                        is_private = getattr(self.torrent_data, "is_private", False)
                except Exception:
                    pass

                # Normalize torrent_data for peer manager
                if isinstance(self.torrent_data, dict):
                    td_for_peer = self.torrent_data
                else:
                    # Convert to dict format
                    td_for_peer = {
                        "info_hash": getattr(self.torrent_data, "info_hash", b""),
                        "name": getattr(self.torrent_data, "name", "unknown"),
                        "pieces_info": {
                            "piece_hashes": getattr(self.torrent_data, "pieces", []),
                            "piece_length": getattr(
                                self.torrent_data, "piece_length", 0
                            ),
                            "num_pieces": getattr(self.torrent_data, "num_pieces", 0),
                            "total_length": getattr(
                                self.torrent_data, "total_length", 0
                            ),
                        },
                    }

                try:
                    self.logger.debug(
                        "Initializing peer manager for torrent: %s", self.info.name
                    )
                    our_peer_id = getattr(self.download_manager, "our_peer_id", None)
                    peer_manager = AsyncPeerConnectionManager(
                        td_for_peer,
                        self.piece_manager,
                        our_peer_id,
                    )
                    self.logger.debug(
                        "Peer manager created, setting security manager and flags"
                    )
                    peer_manager._security_manager = getattr(
                        self.download_manager, "security_manager", None
                    )  # type: ignore[attr-defined]
                    peer_manager._is_private = is_private  # type: ignore[attr-defined]

                    # Apply per-torrent max_peers_per_torrent if set (overrides global)
                    if "max_peers_per_torrent" in self.options:
                        max_peers = self.options["max_peers_per_torrent"]
                        if max_peers is not None and max_peers >= 0:
                            # Override the config value for this peer manager
                            # Store original and set per-torrent value
                            original_max = self.config.network.max_peers_per_torrent
                            self.config.network.max_peers_per_torrent = max_peers
                            self.logger.debug(
                                "Applied per-torrent max_peers_per_torrent: %s (global: %s)",
                                max_peers,
                                original_max,
                            )
                            # Note: This modifies the global config object, but only for this session
                            # A better approach would be to pass it to peer manager directly
                            # For now, we'll store it and peer manager will read from config
                            # TODO: Refactor to pass max_peers directly to peer manager

                    # Wire callbacks
                    self.logger.debug("Wiring peer manager callbacks")
                    if hasattr(self.download_manager, "_on_peer_connected"):
                        peer_manager.on_peer_connected = (
                            self.download_manager._on_peer_connected
                        )  # type: ignore[attr-defined]
                    if hasattr(self.download_manager, "_on_peer_disconnected"):
                        peer_manager.on_peer_disconnected = (
                            self.download_manager._on_peer_disconnected
                        )  # type: ignore[attr-defined]
                    if hasattr(self.download_manager, "_on_piece_received"):
                        peer_manager.on_piece_received = (
                            self.download_manager._on_piece_received
                        )  # type: ignore[attr-defined]
                    if hasattr(self.download_manager, "_on_bitfield_received"):
                        peer_manager.on_bitfield_received = (
                            self.download_manager._on_bitfield_received
                        )  # type: ignore[attr-defined]

                    # Set peer manager on download manager
                    self.download_manager.peer_manager = peer_manager  # type: ignore[assignment]

                    # Start peer manager
                    self.logger.debug("Starting peer manager")
                    if hasattr(peer_manager, "start"):
                        await peer_manager.start()  # type: ignore[misc]

                    # CRITICAL FIX: Set _peer_manager on piece manager immediately
                    # This allows piece selection to work even before peers are connected
                    self.piece_manager._peer_manager = peer_manager  # type: ignore[attr-defined]
                    self.logger.info(
                        "Peer manager initialized early (waiting for peers from tracker/DHT/PEX)"
                    )

                    # CRITICAL FIX: Start piece manager download with peer manager
                    # This sets is_downloading=True and allows piece selection to work
                    # CRITICAL FIX: For magnet links, this may set is_downloading=True even if num_pieces=0
                    # This is intentional - allows piece selector to be ready when metadata arrives
                    self.logger.debug("Starting piece manager download")
                    await self.piece_manager.start_download(peer_manager)
                    self.logger.info(
                        "Piece manager download started (is_downloading=%s, num_pieces=%d, waiting for peers)",
                        self.piece_manager.is_downloading,
                        self.piece_manager.num_pieces,
                    )
                except Exception as e:
                    self.logger.exception(
                        "Failed to initialize peer manager early: %s", e
                    )
                    # Continue without early initialization - will be created when peers arrive
                    # Don't re-raise - allow session to start even if peer manager init fails

            # Set up callbacks
            self.download_manager.on_download_complete = self._on_download_complete
            self.download_manager.on_piece_verified = self._on_piece_verified

            # Set up checkpoint callback
            if self.config.disk.checkpoint_enabled:
                self.download_manager.piece_manager.on_checkpoint_save = (
                    self._save_checkpoint
                )

            # Handle resume from checkpoint
            if self.resume_from_checkpoint and checkpoint:
                await self._resume_from_checkpoint(checkpoint)

            # Start PEX manager if enabled
            if self.config.discovery.enable_pex:
                self.pex_manager = PEXManager()
                await self.pex_manager.start()

            # CRITICAL FIX: Set up DHT peer discovery for magnet links and regular torrents
            # This must happen after session manager and DHT client are ready
            if self.config.discovery.enable_dht and self.session_manager:
                try:
                    from ccbt.session.dht_setup import DHTDiscoverySetup

                    dht_setup = DHTDiscoverySetup(self)
                    await dht_setup.setup_dht_discovery()
                except Exception as dht_error:
                    # Log but don't fail session start - DHT is best-effort
                    self.logger.warning(
                        "Failed to set up DHT peer discovery: %s (peer discovery may be limited)",
                        dht_error,
                    )

            # Start background tasks with error isolation
            # CRITICAL FIX: Wrap task creation to ensure exceptions don't crash the daemon
            # The event loop exception handler will catch any unhandled exceptions in these tasks
            try:
                self._announce_task = asyncio.create_task(self._announce_loop())
                self._status_task = asyncio.create_task(self._status_loop())

                # Start checkpoint task if enabled
                if self.config.disk.checkpoint_enabled:
                    self._checkpoint_task = asyncio.create_task(self._checkpoint_loop())
            except Exception as task_error:
                # Log error but don't fail session start - tasks will be handled by exception handler
                self.logger.warning(
                    "Error creating background tasks (will be handled by exception handler): %s",
                    task_error,
                )
                # Re-raise only if critical - but task creation shouldn't fail
                raise

            self.info.status = "downloading"
            self.logger.info("Started torrent session: %s", self.info.name)

        except Exception as e:
            self.info.status = "error"
            self.logger.exception("Failed to start torrent session")
            if self.on_error:
                await self.on_error(e)
            raise

    async def stop(self) -> None:
        """Stop the async torrent session."""
        self._stop_event.set()

        # Cancel background tasks
        if self._announce_task:
            self._announce_task.cancel()
        if self._status_task:
            self._status_task.cancel()
        if self._checkpoint_task:
            self._checkpoint_task.cancel()

        # Save final checkpoint before stopping
        if (
            self.config.disk.checkpoint_enabled
            and not self.download_manager.download_complete
        ):
            try:
                await self._save_checkpoint()
            except Exception as e:
                self.logger.warning("Failed to save final checkpoint: %s", e)

        # Stop components
        if self.pex_manager:
            await self.pex_manager.stop()

        await self.download_manager.stop()
        await self.piece_manager.stop()

        # CRITICAL FIX: Ensure tracker is properly stopped and session is closed
        # This prevents "Unclosed client session" warnings
        try:
            await self.tracker.stop()
        except Exception as e:
            self.logger.warning("Error stopping tracker: %s", e)
            # Try to force close session if stop() failed
            if hasattr(self.tracker, "session") and self.tracker.session:
                try:
                    if not self.tracker.session.closed:
                        await self.tracker.session.close()
                except Exception:
                    pass
                self.tracker.session = None

        self.info.status = "stopped"
        self.logger.info("Stopped torrent session: %s", self.info.name)

    async def pause(self) -> None:
        """Pause the torrent session by stopping background work and saving a checkpoint.

        Resume will restart the session using existing state.
        """
        try:
            # Save checkpoint before pausing
            if self.config.disk.checkpoint_enabled:
                try:
                    await self._save_checkpoint()
                except Exception as e:
                    self.logger.warning("Failed to save checkpoint on pause: %s", e)

            # Stop background tasks
            self._stop_event.set()
            if self._announce_task:
                self._announce_task.cancel()
            if self._status_task:
                self._status_task.cancel()
            if self._checkpoint_task:
                self._checkpoint_task.cancel()

            # Stop heavy components
            if self.pex_manager:
                await self.pex_manager.stop()
            await self.tracker.stop()
            await self.download_manager.stop()

            self.info.status = "paused"
            self.logger.info("Paused torrent session: %s", self.info.name)
        except Exception:
            self.logger.exception("Failed to pause torrent")
            raise

    async def resume(self) -> None:
        """Resume a previously paused torrent session."""
        try:
            await self.start(resume=True)
            self.info.status = "downloading"
            self.logger.info("Resumed torrent session: %s", self.info.name)
        except Exception:
            self.logger.exception("Failed to resume torrent")
            raise

    async def _announce_loop(self) -> None:
        """Background task for periodic tracker announces."""
        announce_interval = self.config.network.announce_interval

        while not self._stop_event.is_set():
            try:
                # Announce to tracker
                td: dict[str, Any]
                if isinstance(self.torrent_data, TorrentInfoModel):
                    td = {
                        "info_hash": self.torrent_data.info_hash,
                        "name": self.torrent_data.name,
                        "announce": getattr(self.torrent_data, "announce", ""),
                    }
                else:
                    td = self.torrent_data

                # CRITICAL FIX: Check for trackers before attempting announce
                # For magnet links without trackers, skip tracker announce and rely on DHT
                tracker_urls = self._collect_trackers(td)
                if not tracker_urls:
                    # No trackers available - this is normal for magnet links without tracker URLs
                    # Rely on DHT for peer discovery instead
                    self.logger.debug(
                        "No trackers found for %s; skipping tracker announce (relying on DHT)",
                        td.get("name", "unknown"),
                    )
                    # Wait longer when no trackers (DHT discovery is slower)
                    await asyncio.sleep(announce_interval * 2)
                    continue

                response = await self.tracker.announce(td)

                if (
                    response.peers
                    and self.download_manager
                    and hasattr(self.download_manager, "add_peers")
                    and callable(self.download_manager.add_peers)
                ):
                    # Update peer list in download manager
                    add_peers_method = cast(
                        "Callable[[Any], Any] | Callable[[Any], Awaitable[Any]]",
                        self.download_manager.add_peers,
                    )
                    if asyncio.iscoroutinefunction(add_peers_method):
                        await cast("Callable[[Any], Awaitable[Any]]", add_peers_method)(
                            response.peers
                        )
                    else:
                        cast("Callable[[Any], Any]", add_peers_method)(response.peers)

                # Wait for next announce
                await asyncio.sleep(announce_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning("Tracker announce failed: %s", e)
                await asyncio.sleep(60)  # Retry in 1 minute on error

    def _collect_trackers(self, td: dict[str, Any]) -> list[str]:
        """Collect and deduplicate tracker URLs from torrent_data.

        Args:
            td: Torrent data dictionary

        Returns:
            List of unique tracker URLs

        """
        urls: list[str] = []

        # BEP 12 tiers or flat list from magnet parsing
        announce_list = td.get("announce_list")
        if isinstance(announce_list, list):
            for item in announce_list:
                if isinstance(item, list):
                    urls.extend([u for u in item if isinstance(u, str)])
                elif isinstance(item, str):
                    urls.append(item)

        # Additional trackers key (magnet parsing)
        trackers = td.get("trackers")
        if isinstance(trackers, list):
            urls.extend([u for u in trackers if isinstance(u, str)])

        # Fallback to single announce
        announce = td.get("announce")
        if isinstance(announce, str) and announce.strip():
            urls.append(announce.strip())

        # Deduplicate, basic validation
        seen: set[str] = set()
        unique: list[str] = []
        for u in urls:
            if not isinstance(u, str):
                continue
            v = u.strip()
            if v and v not in seen:
                seen.add(v)
                unique.append(v)

        return unique

    async def _status_loop(self) -> None:
        """Background task for status monitoring."""
        while not self._stop_event.is_set():
            try:
                # Get current status
                status = await self.get_status()

                # Notify callback
                if self.on_status_update:
                    await self.on_status_update(status)

                # Update session manager metrics
                # Note: update_torrent_metrics method doesn't exist in AsyncSessionManager

                # Wait before next status check
                await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Status loop error")
                await asyncio.sleep(5)

    async def _on_download_complete(self) -> None:
        """Handle download completion."""
        self.info.status = "seeding"
        self.logger.info("Download complete, now seeding: %s", self.info.name)

        # Clean up checkpoint if configured to do so
        if (
            self.config.disk.checkpoint_enabled
            and self.config.disk.auto_delete_checkpoint_on_complete
        ):
            try:
                await self.delete_checkpoint()
                self.logger.info(
                    "Deleted checkpoint for completed download: %s",
                    self.info.name,
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to delete checkpoint after completion: %s",
                    e,
                )

        if self.on_complete:
            await self.on_complete()

    async def _on_piece_verified(self, _piece_index: int) -> None:
        """Handle piece verification."""
        # Update PEX manager if available
        if self.pex_manager:
            # PEX manager will handle peer discovery
            pass

        # Save checkpoint after piece verification if enabled
        if self.config.disk.checkpoint_enabled and self.config.disk.checkpoint_on_piece:
            try:
                await self._save_checkpoint()
            except Exception as e:
                self.logger.warning(
                    "Failed to save checkpoint after piece verification: %s",
                    e,
                )

    async def get_status(self) -> dict[str, Any]:
        """Get current torrent status."""
        status = self.download_manager.get_status()
        status.update(
            {
                "info_hash": self.info.info_hash.hex(),
                "name": self.info.name,
                "status": self.info.status,
                "added_time": self.info.added_time,
                "uptime": time.time() - self.info.added_time,
                "is_private": self.is_private,  # BEP 27: Include private flag in status
            },
        )
        return status

    async def _resume_from_checkpoint(self, checkpoint: TorrentCheckpoint) -> None:
        """Resume download from checkpoint."""
        try:
            self.logger.info(
                "Resuming download from checkpoint: %s",
                checkpoint.torrent_name,
            )

            # Validate existing files
            if (
                hasattr(self.download_manager, "file_assembler")
                and self.download_manager.file_assembler
            ):
                validation_results = (
                    await self.download_manager.file_assembler.verify_existing_pieces(
                        checkpoint,
                    )
                )

                if not validation_results["valid"]:
                    self.logger.warning(
                        "File validation failed, some files may need to be re-downloaded",
                    )
                    if validation_results.get("missing_files"):
                        self.logger.warning(
                            "Missing files: %s",
                            validation_results["missing_files"],
                        )
                    if validation_results.get("corrupted_pieces"):
                        self.logger.warning(
                            "Corrupted pieces: %s",
                            validation_results["corrupted_pieces"],
                        )

            # Skip preallocation for existing files
            if (
                hasattr(self.download_manager, "file_assembler")
                and self.download_manager.file_assembler
            ):
                # Mark pieces as already written if they exist
                written_pieces = (
                    self.download_manager.file_assembler.get_written_pieces()
                )
                for piece_idx in checkpoint.verified_pieces:
                    if piece_idx not in written_pieces:
                        written_pieces.add(piece_idx)

            # Restore piece manager state
            if self.piece_manager:
                await self.piece_manager.restore_from_checkpoint(checkpoint)
                self.logger.info("Restored piece manager state from checkpoint")

            self.checkpoint_loaded = True
            self.logger.info(
                "Successfully resumed from checkpoint: %s pieces verified",
                len(checkpoint.verified_pieces),
            )

        except Exception:
            self.logger.exception("Failed to resume from checkpoint")
            raise

    async def _save_checkpoint(self) -> None:
        """Save current download state to checkpoint."""
        try:
            # Get checkpoint state from piece manager
            checkpoint = await self.piece_manager.get_checkpoint_state(
                self.info.name,
                self.info.info_hash,
                str(self.output_dir),
            )

            # Add torrent source metadata to checkpoint
            if hasattr(self, "torrent_file_path") and self.torrent_file_path:
                checkpoint.torrent_file_path = self.torrent_file_path
            elif hasattr(self, "magnet_uri") and self.magnet_uri:
                checkpoint.magnet_uri = self.magnet_uri

            # Add announce URLs from torrent data
            if isinstance(self.torrent_data, dict):
                announce_urls = []
                if "announce" in self.torrent_data:
                    announce_urls.append(self.torrent_data["announce"])
                if "announce_list" in self.torrent_data:
                    for tier in self.torrent_data["announce_list"]:
                        announce_urls.extend(tier)
                checkpoint.announce_urls = announce_urls

                # Add display name
                checkpoint.display_name = self.torrent_data.get("name", self.info.name)

            await self.checkpoint_manager.save_checkpoint(checkpoint)
            self.logger.debug("Saved checkpoint for %s", self.info.name)

        except Exception:
            self.logger.exception("Failed to save checkpoint")
            raise

    async def _checkpoint_loop(self) -> None:
        """Background task for periodic checkpoint saving."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.config.disk.checkpoint_interval)

                if not self._stop_event.is_set():
                    await self._save_checkpoint()

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in checkpoint loop")

    async def delete_checkpoint(self) -> bool:
        """Delete checkpoint files for this torrent."""
        try:
            return await self.checkpoint_manager.delete_checkpoint(self.info.info_hash)
        except Exception:
            self.logger.exception("Failed to delete checkpoint")
            return False

    @property
    def downloaded_bytes(self) -> int:
        """Get downloaded bytes."""
        status = self.download_manager.get_status()
        return status.get("downloaded", 0)

    @property
    def uploaded_bytes(self) -> int:
        """Get uploaded bytes."""
        status = self.download_manager.get_status()
        return status.get("uploaded", 0)

    @property
    def left_bytes(self) -> int:
        """Get remaining bytes."""
        status = self.download_manager.get_status()
        return status.get("left", 0)

    @property
    def peers(self) -> dict[str, Any]:
        """Get connected peers."""
        status = self.download_manager.get_status()
        return {"count": status.get("peers", 0)}

    @property
    def download_rate(self) -> float:
        """Get download rate."""
        status = self.download_manager.get_status()
        return status.get("download_rate", 0.0)

    @property
    def upload_rate(self) -> float:
        """Get upload rate."""
        status = self.download_manager.get_status()
        return status.get("upload_rate", 0.0)

    @property
    def info_hash_hex(self) -> str:
        """Get info hash as hex string."""
        return self.info.info_hash.hex()


class AsyncSessionManager:
    """High-performance async session manager for multiple torrents."""

    def __init__(self, output_dir: str = "."):
        """Initialize async session manager."""
        self.config = get_config()
        self.output_dir = output_dir
        self.torrents: dict[bytes, AsyncTorrentSession] = {}
        self.lock = asyncio.Lock()

        # Global components
        self.dht_client: AsyncDHTClient | None = None
        self.metrics = Metrics()
        self.peer_service: PeerService | None = PeerService(
            max_peers=self.config.network.max_global_peers,
            connection_timeout=self.config.network.connection_timeout,
        )

        # Background tasks
        self._cleanup_task: asyncio.Task | None = None
        self._metrics_task: asyncio.Task | None = None

        # Callbacks
        self.on_torrent_added: Callable[[bytes, str], None] | None = None
        self.on_torrent_removed: Callable[[bytes], None] | None = None
        self.on_torrent_complete: Callable[[bytes, str], None] | None = None

        self.logger = logging.getLogger(__name__)

        # Simple per-torrent rate limits (not enforced yet, stored for reporting)
        self._per_torrent_limits: dict[bytes, dict[str, int]] = {}

        # Optional dependency injection container
        self._di: DIContainer | None = None

        # Components initialized by startup functions
        self.security_manager: Any | None = None
        self.nat_manager: Any | None = None
        self.tcp_server: Any | None = None
        # CRITICAL FIX: Store reference to initialized UDP tracker client
        # This ensures all torrent sessions use the same initialized socket
        # The UDP tracker client is a singleton, but we store the reference
        # to ensure it's accessible and to prevent any lazy initialization
        self.udp_tracker_client: Any | None = None

        # CRITICAL FIX: Store executor initialized at daemon startup
        # This ensures executor uses the session manager's initialized components
        # and prevents duplicate executor creation
        self.executor: Any | None = None

        # CRITICAL FIX: Store protocol manager initialized at daemon startup
        # Singleton pattern removed - protocol manager is now managed via session manager
        # This ensures proper lifecycle management and prevents conflicts
        self.protocol_manager: Any | None = None

        # CRITICAL FIX: Store WebTorrent WebSocket server initialized at daemon startup
        # WebSocket server socket must be initialized once and never recreated
        # This prevents port conflicts and socket recreation issues
        self.webtorrent_websocket_server: Any | None = None

        # CRITICAL FIX: Store WebRTC connection manager initialized at daemon startup
        # WebRTC manager should be shared across all WebTorrent protocol instances
        # This ensures proper resource management and prevents duplicate managers
        self.webrtc_manager: Any | None = None

        # CRITICAL FIX: Store uTP socket manager initialized at daemon startup
        # Singleton pattern removed - uTP socket manager is now managed via session manager
        # This ensures proper socket lifecycle management and prevents socket recreation
        self.utp_socket_manager: Any | None = None

        # CRITICAL FIX: Store extension manager initialized at daemon startup
        # Singleton pattern removed - extension manager is now managed via session manager
        # This ensures proper lifecycle management and prevents conflicts
        self.extension_manager: Any | None = None

        # CRITICAL FIX: Store disk I/O manager initialized at daemon startup
        # Singleton pattern removed - disk I/O manager is now managed via session manager
        # This ensures proper lifecycle management and prevents conflicts
        self.disk_io_manager: Any | None = None

        # Private torrents set (used by DHT client factory)
        self.private_torrents: set[bytes] = set()

    def _make_security_manager(self) -> Any | None:
        """Create security manager using ComponentFactory."""
        from ccbt.session.factories import ComponentFactory

        factory = ComponentFactory(self)
        return factory.create_security_manager()

    def _make_dht_client(self, bind_ip: str, bind_port: int) -> Any | None:
        """Create DHT client using ComponentFactory."""
        from ccbt.session.factories import ComponentFactory

        factory = ComponentFactory(self)
        return factory.create_dht_client(bind_ip=bind_ip, bind_port=bind_port)

    def _make_nat_manager(self) -> Any | None:
        """Create NAT manager using ComponentFactory."""
        from ccbt.session.factories import ComponentFactory

        factory = ComponentFactory(self)
        return factory.create_nat_manager()

    def _make_tcp_server(self) -> Any | None:
        """Create TCP server using ComponentFactory."""
        from ccbt.session.factories import ComponentFactory

        factory = ComponentFactory(self)
        return factory.create_tcp_server()

    async def start(self) -> None:
        """Start the async session manager.

        Startup order:
        1. NAT manager:
           a. Create NAT manager
           b. UPnP/NAT-PMP discovery (MUST complete first)
           c. Port mapping (only after discovery completes)
        2. TCP server (waits for NAT port mapping to complete)
        3. UDP tracker client (waits for NAT port mapping to complete)
        4. DHT client (waits for NAT port mapping to complete, especially DHT UDP port)
        5. Security manager (before peer service - used for IP filtering)
        6. Peer service (after NAT, TCP server, DHT, and security manager are ready)
        7. Queue manager (if enabled - manages torrent priorities)
        8. Background tasks
        """
        from ccbt.session.manager_startup import start_nat, start_tcp_server

        # CRITICAL: Start NAT manager first (UPnP/NAT-PMP discovery and port mapping)
        # This must happen before services that need incoming connections
        try:
            await start_nat(self)
        except Exception:
            # Best-effort: log and continue
            self.logger.warning(
                "NAT manager initialization failed. Port mapping may not work, which could prevent incoming connections.",
                exc_info=True,
            )

        # Start TCP server for incoming peer connections if enabled
        # TCP server waits for NAT port mapping to complete before starting
        try:
            await start_tcp_server(self)
        except Exception:
            # Best-effort: log and continue
            self.logger.warning(
                "TCP server initialization failed. Incoming peer connections may not work.",
                exc_info=True,
            )

        # CRITICAL FIX: Initialize UDP tracker client during daemon startup
        # This ensures the socket is created once and never recreated, preventing
        # daemon/executor sync issues. The socket must be ready before the executor
        # can use it, so initialize it here rather than lazily.
        try:
            from ccbt.session.manager_startup import start_udp_tracker_client

            await start_udp_tracker_client(self)
        except Exception:
            # Best-effort: log and continue
            self.logger.warning(
                "UDP tracker client initialization failed. UDP tracker operations may not work.",
                exc_info=True,
            )

        # Start DHT client if enabled (after NAT for better connectivity)
        # CRITICAL FIX: Use start_dht() which properly waits for NAT port mapping
        # and uses the correct factory method with proper bind_ip/bind_port
        if self.config.discovery.enable_dht:
            from ccbt.session.manager_startup import start_dht

            try:
                await start_dht(self)
            except Exception:
                # Best-effort: log and continue
                self.logger.warning(
                    "DHT client initialization failed. DHT peer discovery may not work.",
                    exc_info=True,
                )

        # CRITICAL FIX: Initialize security manager early (before peer service)
        # Security manager is used by peer managers for IP filtering and validation
        # It should be initialized during daemon startup to ensure it's ready before
        # any peer connections are established
        try:
            from ccbt.session.manager_startup import start_security_manager

            await start_security_manager(self)
        except Exception:
            # Best-effort: log and continue
            self.logger.warning(
                "Security manager initialization failed. IP filtering and peer validation may not work.",
                exc_info=True,
            )

        # Start peer service (after NAT, TCP server, and security manager are ready)
        try:
            from ccbt.session.manager_startup import start_peer_service

            await start_peer_service(self)
        except Exception:
            # Best-effort: log and continue
            self.logger.debug("Peer service start failed", exc_info=True)

        # CRITICAL FIX: Initialize queue manager if enabled
        # Queue manager manages torrent priorities and bandwidth allocation
        # It should be initialized during daemon startup to ensure it's ready before
        # any torrents are added or managed
        try:
            from ccbt.session.manager_startup import start_queue_manager

            await start_queue_manager(self)
        except Exception:
            # Best-effort: log and continue
            self.logger.warning(
                "Queue manager initialization failed. Queue management may not work.",
                exc_info=True,
            )

        # CRITICAL FIX: Initialize executor after all components are ready
        # This ensures executor has access to all initialized components (UDP tracker, DHT, etc.)
        # The executor will be used by IPC server and other components
        # Use ExecutorManager to ensure single executor instance per session manager
        try:
            from ccbt.executor.manager import ExecutorManager

            executor_manager = ExecutorManager.get_instance()
            self.executor = executor_manager.get_executor(session_manager=self)

            # CRITICAL FIX: Verify executor is properly initialized
            if not hasattr(self.executor, "adapter") or self.executor.adapter is None:
                raise RuntimeError("Executor adapter not initialized")
            if (
                not hasattr(self.executor.adapter, "session_manager")
                or self.executor.adapter.session_manager is None
            ):
                raise RuntimeError("Executor session_manager not initialized")
            if self.executor.adapter.session_manager is not self:
                raise RuntimeError("Executor session_manager reference mismatch")

            self.logger.info(
                "Command executor initialized successfully via ExecutorManager (adapter=%s, session_manager=%s)",
                type(self.executor.adapter).__name__,
                type(self.executor.adapter.session_manager).__name__,
            )
        except Exception as e:
            self.logger.warning(
                "Failed to initialize command executor: %s. "
                "Some operations may not work correctly.",
                e,
                exc_info=True,
            )
            # Don't fail startup - executor may not be needed in all scenarios
            self.executor = None

        # CRITICAL FIX: Initialize disk I/O manager at daemon startup
        # Singleton pattern removed - disk I/O manager is now managed via session manager
        try:
            from ccbt.config.config import get_config
            from ccbt.storage.disk_io import DiskIOManager

            config = get_config()
            disk_io_manager = DiskIOManager(
                max_workers=config.disk.disk_workers,
                queue_size=config.disk.disk_queue_size,
                cache_size_mb=getattr(config.disk, "cache_size_mb", 256),
            )
            await disk_io_manager.start()
            self.disk_io_manager = disk_io_manager
            self.logger.info(
                "Disk I/O manager initialized successfully (workers: %d, queue_size: %d, cache_size_mb: %d)",
                disk_io_manager.max_workers,
                disk_io_manager.queue_size,
                disk_io_manager.cache_size_mb,
            )
        except Exception as e:
            self.logger.warning(
                "Failed to initialize disk I/O manager: %s. "
                "Disk operations may not work correctly.",
                e,
                exc_info=True,
            )
            # Don't fail startup - disk I/O may not be needed in all scenarios
            self.disk_io_manager = None

        # CRITICAL FIX: Initialize extension manager at daemon startup
        # Singleton pattern removed - extension manager is now managed via session manager
        try:
            from ccbt.extensions.manager import ExtensionManager

            self.extension_manager = ExtensionManager()
            await self.extension_manager.start()
            self.logger.info("Extension manager initialized successfully")
        except Exception as e:
            self.logger.warning(
                "Failed to initialize extension manager: %s. "
                "BitTorrent extensions may not work correctly.",
                e,
                exc_info=True,
            )
            # Don't fail startup - extensions may not be needed in all scenarios
            self.extension_manager = None

        # CRITICAL FIX: Initialize protocol manager at daemon startup
        # Singleton pattern removed - protocol manager is now managed via session manager
        try:
            from ccbt.protocols.base import ProtocolManager

            self.protocol_manager = ProtocolManager()
            self.logger.info("Protocol manager initialized successfully")
        except Exception as e:
            self.logger.warning(
                "Failed to initialize protocol manager: %s. "
                "Protocol operations may not work correctly.",
                e,
                exc_info=True,
            )
            # Don't fail startup - protocol manager may not be needed in all scenarios
            self.protocol_manager = None

        # CRITICAL FIX: Initialize WebTorrent components at daemon startup if enabled
        # This ensures WebSocket server and WebRTC manager are initialized once
        if self.config.network.webtorrent.enable_webtorrent:
            try:
                from ccbt.session.manager_startup import start_webtorrent_components

                await start_webtorrent_components(self)
            except Exception as e:
                self.logger.warning(
                    "Failed to initialize WebTorrent components: %s. "
                    "WebTorrent operations may not work correctly.",
                    e,
                    exc_info=True,
                )

        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._metrics_task = asyncio.create_task(self._metrics_loop())

        self.logger.info("Async session manager started")

    async def stop(self) -> None:
        """Stop the async session manager."""
        # Clean up executor via ExecutorManager
        if self.executor:
            try:
                from ccbt.executor.manager import ExecutorManager

                executor_manager = ExecutorManager.get_instance()
                executor_manager.remove_executor(session_manager=self)
                self.executor = None
                self.logger.debug("Removed executor from ExecutorManager")
            except Exception as e:
                self.logger.debug("Error removing executor: %s", e, exc_info=True)

        # Stop all torrents
        async with self.lock:
            for session in self.torrents.values():
                await session.stop()
            self.torrents.clear()

        # Stop background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._metrics_task:
            self._metrics_task.cancel()

        # Stop TCP server (releases TCP port)
        if self.tcp_server:
            try:
                await self.tcp_server.stop()
                self.logger.debug("TCP server stopped (port released)")
            except Exception as e:
                self.logger.debug("Error stopping TCP server: %s", e, exc_info=True)

        # Stop UDP tracker client (releases UDP tracker port)
        if self.udp_tracker_client:
            try:
                await self.udp_tracker_client.stop()
                self.logger.debug("UDP tracker client stopped (port released)")
            except Exception as e:
                self.logger.debug(
                    "Error stopping UDP tracker client: %s", e, exc_info=True
                )

        # Stop DHT client (releases DHT UDP port)
        if self.dht_client:
            try:
                await self.dht_client.stop()
                self.logger.debug("DHT client stopped (port released)")
            except Exception as e:
                self.logger.debug("Error stopping DHT client: %s", e, exc_info=True)

        # Stop NAT manager (unmaps all ports)
        if self.nat_manager:
            try:
                await self.nat_manager.stop()
                self.logger.debug("NAT manager stopped (ports unmapped)")
            except Exception as e:
                self.logger.debug("Error stopping NAT manager: %s", e, exc_info=True)

        # Stop peer service
        try:
            if self.peer_service:
                await self.peer_service.stop()
        except Exception:
            # Best-effort: log and continue
            self.logger.debug("Peer service stop failed", exc_info=True)

        self.logger.info("Async session manager stopped (all ports released)")

    async def reload_config(self, new_config: Any) -> None:
        """Reload configuration and update affected components.

        Args:
            new_config: New Config instance to apply

        """
        old_config = self.config
        self.config = new_config

        reloaded_components = []

        try:
            # Reload security manager if IP filters changed
            if (
                old_config.security.ip_filter.filter_files
                != new_config.security.ip_filter.filter_files
                or old_config.security.ip_filter.enable_ip_filter
                != new_config.security.ip_filter.enable_ip_filter
            ) and self.security_manager:
                try:
                    await self.security_manager.load_ip_filter(new_config)
                    reloaded_components.append("security_manager")
                    self.logger.info("Reloaded security manager with new IP filters")
                except Exception as e:
                    self.logger.warning("Failed to reload security manager: %s", e)

            # Reload DHT client if DHT config changed
            dht_config_changed = (
                old_config.discovery.enable_dht != new_config.discovery.enable_dht
                or old_config.discovery.dht_port != new_config.discovery.dht_port
            )
            if dht_config_changed:
                # Stop existing DHT client
                if self.dht_client:
                    try:
                        await self.dht_client.stop()
                        self.dht_client = None
                        reloaded_components.append("dht_client (stopped)")
                    except Exception as e:
                        self.logger.warning("Failed to stop DHT client: %s", e)

                # Start new DHT client if enabled
                if new_config.discovery.enable_dht:
                    from ccbt.session.manager_startup import start_dht

                    try:
                        await start_dht(self)
                        reloaded_components.append("dht_client (started)")
                        self.logger.info("Reloaded DHT client")
                    except Exception as e:
                        self.logger.warning("Failed to start DHT client: %s", e)

            # Reload NAT manager if NAT config changed
            nat_config_changed = (
                old_config.nat.auto_map_ports != new_config.nat.auto_map_ports
                or old_config.nat.enable_nat_pmp != new_config.nat.enable_nat_pmp
                or old_config.nat.enable_upnp != new_config.nat.enable_upnp
            )
            if nat_config_changed:
                # Stop existing NAT manager
                if self.nat_manager:
                    try:
                        await self.nat_manager.stop()
                        self.nat_manager = None
                        reloaded_components.append("nat_manager (stopped)")
                    except Exception as e:
                        self.logger.warning("Failed to stop NAT manager: %s", e)

                # Start new NAT manager if enabled
                if new_config.nat.auto_map_ports:
                    from ccbt.session.manager_startup import start_nat

                    try:
                        await start_nat(self)
                        reloaded_components.append("nat_manager (started)")
                        self.logger.info("Reloaded NAT manager")
                    except Exception as e:
                        self.logger.warning("Failed to start NAT manager: %s", e)

            # Reload peer service if peer limits changed
            peer_config_changed = (
                old_config.network.max_global_peers
                != new_config.network.max_global_peers
                or old_config.network.connection_timeout
                != new_config.network.connection_timeout
            )
            if peer_config_changed and self.peer_service:
                try:
                    # Update peer service config
                    self.peer_service.max_peers = new_config.network.max_global_peers
                    self.peer_service.connection_timeout = (
                        new_config.network.connection_timeout
                    )
                    reloaded_components.append("peer_service")
                    self.logger.info("Reloaded peer service configuration")
                except Exception as e:
                    self.logger.warning("Failed to reload peer service: %s", e)

            # Reload TCP server if listen port changed
            tcp_config_changed = (
                old_config.network.listen_port != new_config.network.listen_port
                or old_config.network.enable_tcp != new_config.network.enable_tcp
            )
            if tcp_config_changed:
                # Stop existing TCP server
                if hasattr(self, "tcp_server") and self.tcp_server:
                    try:
                        await self.tcp_server.stop()
                        self.tcp_server = None
                        reloaded_components.append("tcp_server (stopped)")
                    except Exception as e:
                        self.logger.warning("Failed to stop TCP server: %s", e)

                # Start new TCP server if enabled
                if new_config.network.enable_tcp:
                    from ccbt.session.manager_startup import start_tcp_server

                    try:
                        await start_tcp_server(self)
                        reloaded_components.append("tcp_server (started)")
                        self.logger.info("Reloaded TCP server")
                    except Exception as e:
                        self.logger.warning("Failed to start TCP server: %s", e)

            if reloaded_components:
                self.logger.info(
                    "Configuration reloaded successfully. Components reloaded: %s",
                    ", ".join(reloaded_components),
                )
            else:
                self.logger.info("Configuration updated (no component reloads needed)")

        except Exception:
            self.logger.exception("Error during config reload")
            # Revert to old config on critical error
            self.config = old_config
            raise

    async def pause_torrent(self, info_hash_hex: str) -> bool:
        """Pause a torrent download by info hash.

        Returns True if paused, False otherwise.
        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        async with self.lock:
            session = self.torrents.get(info_hash)
        if not session:
            return False
        await session.pause()
        return True

    async def resume_torrent(self, info_hash_hex: str) -> bool:
        """Resume a paused torrent by info hash."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        async with self.lock:
            session = self.torrents.get(info_hash)
        if not session:
            return False
        await session.resume()
        return True

    async def set_rate_limits(
        self,
        info_hash_hex: str,
        download_kib: int,
        upload_kib: int,
    ) -> bool:
        """Set per-torrent rate limits (stored for reporting).

        Currently not enforced at I/O level, but stored for future enforcement
        and reporting purposes.

        Args:
            info_hash_hex: Torrent info hash (hex string)
            download_kib: Download limit in KiB/s (0 = unlimited)
            upload_kib: Upload limit in KiB/s (0 = unlimited)

        Returns:
            True if limits were set, False if torrent not found

        Note:
            Per-torrent limits should not exceed global limits. Validation
            is performed to ensure compliance.
        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        # Validate per-torrent limits against global limits
        global_down = self.config.limits.global_down_kib
        global_up = self.config.limits.global_up_kib

        if download_kib > 0 and global_down > 0 and download_kib > global_down:
            self.logger.warning(
                "Per-torrent download limit %d KiB/s exceeds global limit %d KiB/s, "
                "capping to global limit",
                download_kib,
                global_down,
            )
            download_kib = global_down

        if upload_kib > 0 and global_up > 0 and upload_kib > global_up:
            self.logger.warning(
                "Per-torrent upload limit %d KiB/s exceeds global limit %d KiB/s, "
                "capping to global limit",
                upload_kib,
                global_up,
            )
            upload_kib = global_up

        async with self.lock:
            if info_hash not in self.torrents:
                return False
            self._per_torrent_limits[info_hash] = {
                "down_kib": max(0, int(download_kib)),
                "up_kib": max(0, int(upload_kib)),
            }
            self.logger.debug(
                "Set per-torrent rate limits for %s: down=%d KiB/s, up=%d KiB/s",
                info_hash_hex[:8],
                download_kib,
                upload_kib,
            )
        return True

    async def get_global_stats(self) -> dict[str, Any]:
        """Aggregate global statistics across all torrents."""
        stats: dict[str, Any] = {
            "num_torrents": 0,
            "num_active": 0,
            "num_paused": 0,
            "num_seeding": 0,
            "download_rate": 0.0,
            "upload_rate": 0.0,
            "average_progress": 0.0,
        }
        aggregate_progress = 0.0
        async with self.lock:
            stats["num_torrents"] = len(self.torrents)
            for sess in self.torrents.values():
                st = await sess.get_status()
                s = st.get("status", "")
                if s == "paused":
                    stats["num_paused"] += 1
                elif s == "seeding":
                    stats["num_seeding"] += 1
                else:
                    stats["num_active"] += 1
                stats["download_rate"] += float(st.get("download_rate", 0.0))
                stats["upload_rate"] += float(st.get("upload_rate", 0.0))
                aggregate_progress += float(st.get("progress", 0.0))
        if stats["num_torrents"]:
            stats["average_progress"] = aggregate_progress / stats["num_torrents"]
        return stats

    async def export_session_state(self, path: Path) -> None:
        """Export current session state to a JSON file."""
        import json

        data: dict[str, Any] = {
            "torrents": {},
            "config": self.config.model_dump(mode="json"),
        }
        async with self.lock:
            for ih, sess in self.torrents.items():
                data["torrents"][ih.hex()] = await sess.get_status()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def import_session_state(self, path: Path) -> dict[str, Any]:
        """Import session state from a JSON file. Returns the parsed state.

        This does not automatically start torrents.
        """
        import json

        return json.loads(path.read_text(encoding="utf-8"))

    async def add_torrent(
        self,
        path: str | dict[str, Any],
        resume: bool = False,
    ) -> str:
        """Add a torrent file or torrent data to the session."""
        try:
            # Handle both file paths and torrent dictionaries
            if isinstance(path, dict):
                td = path  # Already parsed torrent data
                info_hash = td.get("info_hash") if isinstance(td, dict) else None
                if not info_hash:
                    error_msg = "Missing info_hash in torrent data"
                    raise ValueError(error_msg)
            else:
                parser = TorrentParser()
                td_model = parser.parse(path)
                # Accept both model objects and plain dicts from mocked parsers in tests
                if isinstance(td_model, dict):
                    name = (
                        td_model.get("name")
                        or td_model.get("torrent_name")
                        or "unknown"
                    )
                    ih = td_model.get("info_hash")
                    if isinstance(ih, str):
                        ih = bytes.fromhex(ih)
                    if not isinstance(ih, (bytes, bytearray)):
                        error_msg = "info_hash must be bytes"
                        raise TypeError(error_msg)
                    td = {
                        "name": name,
                        "info_hash": bytes(ih),
                        "pieces_info": td_model.get("pieces_info", {}),
                        "file_info": td_model.get(
                            "file_info",
                            {
                                "total_length": td_model.get("total_length", 0),
                            },
                        ),
                    }
                else:
                    td = {
                        "name": td_model.name,
                        "info_hash": td_model.info_hash,
                        "pieces_info": {
                            "piece_hashes": list(td_model.pieces),
                            "piece_length": td_model.piece_length,
                            "num_pieces": td_model.num_pieces,
                            "total_length": td_model.total_length,
                        },
                        "file_info": {
                            "total_length": td_model.total_length,
                        },
                    }
                info_hash = td["info_hash"]
                if isinstance(info_hash, str):
                    info_hash = bytes.fromhex(info_hash)
                if not isinstance(info_hash, bytes):
                    error_msg = "info_hash must be bytes"
                    raise TypeError(error_msg)

            # Check if already exists
            async with self.lock:
                if isinstance(info_hash, bytes) and info_hash in self.torrents:
                    msg = f"Torrent {info_hash.hex()} already exists"
                    raise ValueError(msg)

                # Create session
                session = AsyncTorrentSession(td, self.output_dir, self)

                # Set source information for checkpoint metadata
                if isinstance(path, str):
                    session.torrent_file_path = path

                self.torrents[info_hash] = session

                # BEP 27: Track private torrents for DHT/PEX/LSD enforcement
                if session.is_private:
                    self.private_torrents.add(info_hash)
                    self.logger.debug(
                        "Added private torrent %s to private_torrents set (BEP 27)",
                        info_hash.hex()[:8],
                    )

            # Start session
            await session.start(resume=resume)

            # Notify callback
            if self.on_torrent_added:
                await self.on_torrent_added(info_hash, session.info.name)

            self.logger.info("Added torrent: %s", session.info.name)
            return info_hash.hex()

        except Exception:
            path_desc = (
                getattr(path, "name", str(path)) if hasattr(path, "name") else str(path)
            )
            self.logger.exception("Failed to add torrent %s", path_desc)
            raise

    async def add_magnet(self, uri: str, resume: bool = False) -> str:
        """Add a magnet link to the session."""
        info_hash: bytes | None = None
        session: AsyncTorrentSession | None = None
        try:
            mi = _session_mod.parse_magnet(uri)
            td = _session_mod.build_minimal_torrent_data(
                mi.info_hash, mi.display_name, mi.trackers
            )
            info_hash = td["info_hash"]
            if isinstance(info_hash, str):
                info_hash = bytes.fromhex(info_hash)
            if not isinstance(info_hash, bytes):
                error_msg = "info_hash must be bytes"
                raise TypeError(error_msg)

            # Check if already exists
            async with self.lock:
                if isinstance(info_hash, bytes) and info_hash in self.torrents:
                    msg = f"Magnet {info_hash.hex()} already exists"
                    raise ValueError(msg)

                # Create session
                session = AsyncTorrentSession(td, self.output_dir, self)

                # Set source information for checkpoint metadata
                session.magnet_uri = uri

                self.torrents[info_hash] = session

                # BEP 27: Track private torrents for DHT/PEX/LSD enforcement
                if session.is_private:
                    self.private_torrents.add(info_hash)
                    self.logger.debug(
                        "Added private magnet torrent %s to private_torrents set (BEP 27)",
                        info_hash.hex()[:8],
                    )

            # CRITICAL FIX: Start session with cleanup on failure
            # If session.start() fails, remove the session from torrents dict
            # to prevent orphaned sessions that could cause issues
            try:
                await session.start(resume=resume)
            except Exception as start_error:
                # Clean up the session from torrents dict if start failed
                self.logger.exception(
                    "Failed to start session for magnet %s, cleaning up",
                    uri,
                )
                async with self.lock:
                    # Remove session from torrents dict if it's still there
                    if info_hash and info_hash in self.torrents:
                        removed_session = self.torrents.pop(info_hash, None)
                        if removed_session:
                            # Try to stop the session to clean up resources
                            try:
                                await removed_session.stop()
                            except Exception:
                                # Ignore errors during cleanup
                                pass
                # Re-raise the original error
                raise start_error

            # Notify callback
            if self.on_torrent_added:
                await self.on_torrent_added(info_hash, session.info.name)

            self.logger.info("Added magnet: %s", session.info.name)
            return info_hash.hex()

        except Exception:
            self.logger.exception("Failed to add magnet %s", uri)
            raise

    async def remove(self, info_hash_hex: str) -> bool:
        """Remove a torrent from the session."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        async with self.lock:
            session = self.torrents.pop(info_hash, None)
            # BEP 27: Remove from private_torrents set when torrent is removed
            self.private_torrents.discard(info_hash)

        if session:
            await session.stop()

            # Notify callback
            if self.on_torrent_removed:
                await self.on_torrent_removed(info_hash)

            self.logger.info("Removed torrent: %s", session.info.name)
            return True

        return False

    async def get_peers_for_torrent(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Return list of peers for a torrent (placeholder).

        Returns an empty list until peer tracking is wired.
        """
        try:
            _ = bytes.fromhex(info_hash_hex)
        except ValueError:
            return []
        if not self.peer_service:
            return []
        try:
            peers = await self.peer_service.list_peers()
            return [
                {
                    "ip": p.peer_info.ip,
                    "port": p.peer_info.port,
                    "download_rate": 0.0,
                    "upload_rate": 0.0,
                    "choked": False,
                    "client": "?",
                }
                for p in peers
            ]
        except Exception:
            return []

    async def force_announce(self, info_hash_hex: str) -> bool:
        """Force a tracker announce for a given torrent if possible."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False
        async with self.lock:
            sess = self.torrents.get(info_hash)
        if not sess:
            return False
        try:
            td: dict[str, Any]
            if isinstance(sess.torrent_data, dict):
                td = sess.torrent_data  # type: ignore[assignment]
            else:
                td = {
                    "info_hash": sess.info.info_hash,
                    "announce": "",
                    "name": sess.info.name,
                }
            await sess.tracker.announce(td)
        except Exception:
            return False
        else:
            return True

    async def checkpoint_backup_torrent(
        self,
        info_hash_hex: str,
        destination: Path,
        compress: bool = True,
        encrypt: bool = False,
    ) -> bool:
        """Create a checkpoint backup for a torrent to the destination path."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False
        try:
            cp = CheckpointManager(self.config.disk)
            await cp.backup_checkpoint(
                info_hash,
                destination,
                compress=compress,
                encrypt=encrypt,
            )
        except Exception:
            return False
        else:
            return True

    async def rehash_torrent(self, info_hash_hex: str) -> bool:
        """Rehash all pieces."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        # Integrate with piece manager to re-verify data
        torrent = self.torrents.get(info_hash)
        if (
            torrent
            and torrent.piece_manager
            and hasattr(torrent.piece_manager, "verify_all_pieces")
        ):
            verify_method = cast(
                "Callable[[], Awaitable[bool]] | Callable[[], bool]",
                torrent.piece_manager.verify_all_pieces,
            )
            if asyncio.iscoroutinefunction(verify_method):
                return await cast("Callable[[], Awaitable[bool]]", verify_method)()
            return cast("Callable[[], bool]", verify_method)()

        return False

    async def force_scrape(self, info_hash_hex: str) -> bool:
        """Force tracker scrape (placeholder)."""
        try:
            _ = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False
        return True

    async def refresh_pex(self, info_hash_hex: str) -> bool:
        """Refresh Peer Exchange (placeholder)."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False
        async with self.lock:
            sess = self.torrents.get(info_hash)
        if not sess or not sess.pex_manager:
            return False
        try:
            if hasattr(sess.pex_manager, "refresh"):
                await sess.pex_manager.refresh()  # type: ignore[attr-defined]
        except Exception:
            return False
        else:
            return True

    async def get_status(self) -> dict[str, Any]:
        """Get status of all torrents."""
        status = {}
        async with self.lock:
            for info_hash, session in self.torrents.items():
                status[info_hash.hex()] = await session.get_status()
        return status

    async def get_torrent_status(self, info_hash_hex: str) -> dict[str, Any] | None:
        """Get status of a specific torrent."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return None

        async with self.lock:
            session = self.torrents.get(info_hash)

        if session:
            return await session.get_status()

        return None

    async def get_session_for_info_hash(
        self, info_hash: bytes
    ) -> AsyncTorrentSession | None:
        """Get torrent session by info hash.

        Args:
            info_hash: Torrent info hash (20 bytes)

        Returns:
            AsyncTorrentSession instance if found, None otherwise

        """
        async with self.lock:
            return self.torrents.get(info_hash)

    async def _cleanup_loop(self) -> None:
        """Background task for cleanup operations."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                # Clean up stopped sessions
                async with self.lock:
                    to_remove = []
                    for info_hash, session in self.torrents.items():
                        if session.info.status == "stopped":
                            to_remove.append(info_hash)

                    for info_hash in to_remove:
                        session = self.torrents.pop(info_hash)
                        # BEP 27: Remove from private_torrents set during cleanup
                        self.private_torrents.discard(info_hash)
                        await session.stop()
                        if self.on_torrent_removed:
                            await self.on_torrent_removed(info_hash)

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Cleanup loop error")

    async def _metrics_loop(self) -> None:
        """Background task for metrics collection."""
        while True:
            try:
                await asyncio.sleep(10)  # Update every 10 seconds

                # Collect global metrics
                global_stats = self._aggregate_torrent_stats()
                await self._emit_global_metrics(global_stats)

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Metrics loop error")

    def _aggregate_torrent_stats(self) -> dict[str, Any]:
        """Aggregate statistics from all torrents."""
        total_downloaded = 0
        total_uploaded = 0
        total_left = 0
        total_peers = 0
        total_download_rate = 0.0
        total_upload_rate = 0.0

        for torrent in self.torrents.values():
            total_downloaded += torrent.downloaded_bytes
            total_uploaded += torrent.uploaded_bytes
            total_left += torrent.left_bytes
            total_peers += len(torrent.peers)
            total_download_rate += torrent.download_rate
            total_upload_rate += torrent.upload_rate

        return {
            "total_torrents": len(self.torrents),
            "total_downloaded": total_downloaded,
            "total_uploaded": total_uploaded,
            "total_left": total_left,
            "total_peers": total_peers,
            "total_download_rate": total_download_rate,
            "total_upload_rate": total_upload_rate,
            "timestamp": time.time(),
        }

    async def _emit_global_metrics(self, stats: dict[str, Any]) -> None:
        """Emit global metrics event."""
        from ccbt.utils.events import Event, EventType, emit_event

        await emit_event(
            Event(
                event_type=EventType.GLOBAL_METRICS_UPDATE.value,
                data=stats,
            ),
        )

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: TorrentCheckpoint,
        torrent_path: str | None = None,
    ) -> str:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Info hash hex string of resumed torrent

        Raises:
            ValueError: If torrent source cannot be determined
            FileNotFoundError: If torrent file doesn't exist
            ValidationError: If checkpoint is invalid

        """
        try:
            # Validate checkpoint
            if not await self.validate_checkpoint(checkpoint):
                error_msg = "Invalid checkpoint data"
                raise ValidationError(error_msg)

            # Priority order: explicit path -> stored file path -> magnet URI
            torrent_source = None
            source_type = None

            if torrent_path and Path(torrent_path).exists():
                torrent_source = torrent_path
                source_type = "file"
                self.logger.info("Using explicit torrent file: %s", torrent_path)
            elif (
                checkpoint.torrent_file_path
                and Path(checkpoint.torrent_file_path).exists()
            ):
                torrent_source = checkpoint.torrent_file_path
                source_type = "file"
                self.logger.info(
                    "Using stored torrent file: %s",
                    checkpoint.torrent_file_path,
                )
            elif checkpoint.magnet_uri:
                torrent_source = checkpoint.magnet_uri
                source_type = "magnet"
                self.logger.info("Using stored magnet URI: %s", checkpoint.magnet_uri)
            else:
                error_msg = (
                    f"Cannot resume torrent {info_hash.hex()}: "
                    "No valid torrent source found in checkpoint. "
                    "Please provide torrent file or magnet link."
                )
                raise ValueError(error_msg)

            # Validate info hash matches if using explicit torrent file
            if source_type == "file" and torrent_source:
                parser = TorrentParser()
                torrent_data_model = parser.parse(torrent_source)
                if isinstance(torrent_data_model, dict):
                    torrent_info_hash = torrent_data_model.get("info_hash")
                else:
                    torrent_info_hash = getattr(torrent_data_model, "info_hash", None)
                torrent_data = {
                    "info_hash": torrent_info_hash,
                }
                if torrent_data["info_hash"] != info_hash:
                    torrent_hash_hex = (
                        torrent_data["info_hash"].hex()
                        if torrent_data["info_hash"] is not None
                        else "None"
                    )
                    error_msg = (
                        f"Info hash mismatch: checkpoint is for {info_hash.hex()}, "
                        f"but torrent file is for {torrent_hash_hex}"
                    )
                    raise ValueError(error_msg)

            # Add torrent/magnet with resume=True
            if source_type == "file":
                return await self.add_torrent(torrent_source, resume=True)
            return await self.add_magnet(torrent_source, resume=True)

        except Exception:
            self.logger.exception("Failed to resume from checkpoint")
            raise

    async def list_resumable_checkpoints(self) -> list[TorrentCheckpoint]:
        """List all checkpoints that can be auto-resumed."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoints = await checkpoint_manager.list_checkpoints()

        resumable = []
        for checkpoint_info in checkpoints:
            try:
                checkpoint = await checkpoint_manager.load_checkpoint(
                    checkpoint_info.info_hash,
                )
                if checkpoint and (
                    checkpoint.torrent_file_path or checkpoint.magnet_uri
                ):
                    resumable.append(checkpoint)
            except Exception as e:
                self.logger.warning(
                    "Failed to load checkpoint %s: %s",
                    checkpoint_info.info_hash.hex(),
                    e,
                )
                continue

        return resumable

    async def find_checkpoint_by_name(self, name: str) -> TorrentCheckpoint | None:
        """Find checkpoint by torrent name."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoints = await checkpoint_manager.list_checkpoints()

        for checkpoint_info in checkpoints:
            try:
                checkpoint = await checkpoint_manager.load_checkpoint(
                    checkpoint_info.info_hash,
                )
                if checkpoint and checkpoint.torrent_name == name:
                    return checkpoint
            except Exception as e:
                self.logger.warning(
                    "Failed to load checkpoint %s: %s",
                    checkpoint_info.info_hash.hex(),
                    e,
                )
                continue

        return None

    async def get_checkpoint_info(self, info_hash: bytes) -> dict[str, Any] | None:
        """Get checkpoint summary information."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoint = await checkpoint_manager.load_checkpoint(info_hash)

        if not checkpoint:
            return None

        return {
            "info_hash": info_hash.hex(),
            "name": checkpoint.torrent_name,
            "progress": len(checkpoint.verified_pieces) / checkpoint.total_pieces
            if checkpoint.total_pieces > 0
            else 0,
            "verified_pieces": len(checkpoint.verified_pieces),
            "total_pieces": checkpoint.total_pieces,
            "total_size": checkpoint.total_length,
            "created_at": checkpoint.created_at,
            "updated_at": checkpoint.updated_at,
            "can_resume": bool(checkpoint.torrent_file_path or checkpoint.magnet_uri),
            "torrent_file_path": checkpoint.torrent_file_path,
            "magnet_uri": checkpoint.magnet_uri,
        }

    async def validate_checkpoint(self, checkpoint: TorrentCheckpoint) -> bool:
        """Validate checkpoint integrity."""
        try:
            # Basic validation
            if (
                not checkpoint.info_hash
                or len(checkpoint.info_hash) != INFO_HASH_LENGTH
            ):
                return False

            if checkpoint.total_pieces <= 0 or checkpoint.piece_length <= 0:
                return False

            if checkpoint.total_length <= 0:
                return False

            # Validate verified pieces are within bounds
            for piece_idx in checkpoint.verified_pieces:
                if piece_idx < 0 or piece_idx >= checkpoint.total_pieces:
                    return False

            # Validate piece states
            for piece_idx, state in checkpoint.piece_states.items():
                if piece_idx < 0 or piece_idx >= checkpoint.total_pieces:
                    return False
                if not isinstance(state, PieceState):
                    return False

        except Exception:
            return False
        else:
            return True

    async def cleanup_completed_checkpoints(self) -> int:
        """Remove checkpoints for completed downloads."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoints = await checkpoint_manager.list_checkpoints()

        cleaned = 0

        async def process_checkpoint(checkpoint_info):
            """Process a single checkpoint."""
            try:
                checkpoint = await checkpoint_manager.load_checkpoint(
                    checkpoint_info.info_hash,
                )
                if (
                    checkpoint
                    and len(checkpoint.verified_pieces) == checkpoint.total_pieces
                ):
                    # Download is complete, delete checkpoint
                    await checkpoint_manager.delete_checkpoint(
                        checkpoint_info.info_hash,
                    )
                    self.logger.info(
                        "Cleaned up completed checkpoint: %s",
                        checkpoint.torrent_name,
                    )
                    return True
            except Exception as e:
                self.logger.warning(
                    "Failed to process checkpoint %s: %s",
                    checkpoint_info.info_hash.hex(),
                    e,
                )
            return False

        for checkpoint_info in checkpoints:
            if await process_checkpoint(checkpoint_info):
                cleaned += 1

        return cleaned

    def load_torrent(self, torrent_path: str | Path) -> dict[str, Any] | None:
        """Load torrent file and return parsed data."""
        try:
            parser = TorrentParser()
            tdm = parser.parse(str(torrent_path))
            return {
                "name": tdm.name,
                "info_hash": tdm.info_hash,
                "pieces_info": {
                    "piece_hashes": list(tdm.pieces),
                    "piece_length": tdm.piece_length,
                    "num_pieces": tdm.num_pieces,
                    "total_length": tdm.total_length,
                },
                "file_info": {
                    "total_length": tdm.total_length,
                },
                "announce": getattr(tdm, "announce", ""),
            }
        except Exception:
            self.logger.exception("Failed to load torrent %s", torrent_path)
            return None

    def parse_magnet_link(self, magnet_uri: str) -> dict[str, Any] | None:
        """Parse magnet link and return torrent data."""
        try:
            magnet_info = parse_magnet(magnet_uri)
            return build_minimal_torrent_data(
                magnet_info.info_hash,
                magnet_info.display_name,
                magnet_info.trackers,
            )
        except Exception:
            self.logger.exception("Failed to parse magnet link")
            return None

    async def start_web_interface(
        self,
        host: str = "localhost",
        port: int = 9090,
    ) -> None:
        """Start web interface (placeholder implementation)."""
        self.logger.info("Web interface would start on http://%s:%s", host, port)
        # TODO: Implement actual web interface
        await asyncio.sleep(1)  # Placeholder to prevent immediate exit

    @property
    def peers(self) -> list[dict[str, Any]]:
        """Get list of connected peers (placeholder)."""
        return []

    @property
    def dht(self) -> Any | None:
        """Get DHT instance (placeholder)."""
        return None


# Backward compatibility
class SessionManager(AsyncSessionManager):
    """Backward compatibility wrapper for SessionManager."""

    def __init__(self, output_dir: str = "."):
        """Initialize SessionManager with output directory."""
        super().__init__(output_dir)
        self._session_started = False

    def add_torrent(self, path: str | dict[str, Any]) -> str:
        """Add torrent synchronously for backward compatibility."""
        if not self._session_started:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.start())
            self._session_started = True

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(super().add_torrent(path))

    def add_magnet(self, uri: str) -> str:
        """Add magnet synchronously for backward compatibility."""
        if not self._session_started:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.start())
            self._session_started = True

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(super().add_magnet(uri))

    def remove(self, info_hash_hex: str) -> bool:
        """Remove torrent synchronously for backward compatibility."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(super().remove(info_hash_hex))

    def status(self) -> dict[str, Any]:
        """Get status synchronously for backward compatibility."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(super().get_status())
