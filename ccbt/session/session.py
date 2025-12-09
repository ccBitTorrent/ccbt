# ccbt/session.py
"""High-performance async session manager for ccBitTorrent.

Manages multiple torrents (file or magnet), coordinates tracker announces,
DHT, PEX, and provides status aggregation with async event loop management.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
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
from ccbt.piece.file_selection import FileSelectionManager
from ccbt.services.peer_service import PeerService
from ccbt.session.download_manager import AsyncDownloadManager
from ccbt.session.torrent_utils import get_torrent_info
from ccbt.storage.checkpoint import CheckpointManager
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
        self.logger = get_logger(__name__)

        # Core components
        self.download_manager = AsyncDownloadManager(torrent_data, str(output_dir))

        # Create a proper piece manager for checkpoint operations
        from ccbt.piece.async_piece_manager import AsyncPieceManager

        self._normalized_td = self._normalize_torrent_data(torrent_data)
        self.piece_manager = AsyncPieceManager(self._normalized_td)

        # Set the piece manager on the download manager for compatibility
        self.download_manager.piece_manager = self.piece_manager
        self.file_selection_manager: FileSelectionManager | None = None
        self.ensure_file_selection_manager()

        # CRITICAL FIX: Pass session_manager to AsyncTrackerClient
        # This ensures it uses the daemon's initialized UDP tracker client
        # instead of creating a new one, preventing WinError 10048
        self.tracker = AsyncTrackerClient()
        # Store session_manager reference so tracker can use initialized UDP client
        if session_manager:
            self.tracker._session_manager = session_manager  # type: ignore[attr-defined]

        # CRITICAL FIX: Register immediate connection callback for tracker responses
        # This connects peers IMMEDIATELY when tracker responses arrive, before announce loop
        # Note: Callback will be registered in start() after components are initialized
        self.pex_manager: PEXManager | None = None
        self.checkpoint_manager = CheckpointManager(self.config.disk)

        # CRITICAL FIX: Timestamp to track when tracker peers are being connected
        # This prevents DHT from starting until tracker connections complete
        # Use timestamp instead of boolean to handle multiple concurrent callbacks
        self._tracker_peers_connecting_until: float | None = None  # type: ignore[attr-defined]

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

        # Track announce count for aggressive initial discovery
        self._announce_count = 0

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
        self._seeding_stats_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._stopped = False  # Flag for incoming peer queue processor

        # CRITICAL FIX: Initialize incoming peer handler and queue
        # This allows the TCP server to route incoming connections to this session
        from ccbt.session.incoming import IncomingPeerHandler

        self._incoming_peer_queue: asyncio.Queue[
            tuple[
                asyncio.StreamReader,
                asyncio.StreamWriter,
                Any,  # Handshake
                str,  # peer_ip
                int,  # peer_port
            ]
        ] = asyncio.Queue()
        self._incoming_peer_handler = IncomingPeerHandler(self)
        self._incoming_queue_task: asyncio.Task[None] | None = None

        # Checkpoint state
        self.checkpoint_loaded = False
        self.resume_from_checkpoint = False

        # Callbacks
        self.on_status_update: Callable[[dict[str, Any]], None] | None = None
        self.on_complete: Callable[[], None] | None = None
        self.on_error: Callable[[Exception], None] | None = None

        # Cached status for synchronous property access
        # Updated periodically by _status_loop
        self._cached_status: dict[str, Any] = {}

        # Extract is_private flag for DHT discovery
        if isinstance(torrent_data, dict):
            self.is_private = torrent_data.get("is_private", False)
        elif hasattr(torrent_data, "is_private"):
            self.is_private = getattr(torrent_data, "is_private", False)
        else:
            self.is_private = False

        # Per-torrent configuration options (overrides global config for this torrent)
        # These are set via UI or API and applied during session.start()
        # Initialize with global defaults, which can be overridden per-torrent
        self.options: dict[str, Any] = {}
        if self.config.per_torrent_defaults:
            defaults_dict = self.config.per_torrent_defaults.model_dump(
                exclude_none=True
            )
            self.options.update(defaults_dict)

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
                    self.piece_manager.selection_strategy = piece_selection  # type: ignore[assignment]
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
                self.piece_manager.streaming_mode = streaming_mode  # type: ignore[assignment]
                self.logger.debug(
                    "Applied per-torrent streaming_mode: %s", streaming_mode
                )

        # Apply sequential window size if set
        if "sequential_window_size" in self.options:
            seq_window = int(self.options["sequential_window_size"])
            if seq_window > 0 and hasattr(self.piece_manager, "sequential_window_size"):
                self.piece_manager.sequential_window_size = seq_window  # type: ignore[assignment]
                self.logger.debug(
                    "Applied per-torrent sequential_window_size: %s", seq_window
                )

        # Note: max_peers_per_torrent is applied when peer manager is created
        # (see peer manager initialization below)

    def ensure_file_selection_manager(self) -> bool:
        """Ensure file selection manager exists and is wired into dependent components."""
        if self.file_selection_manager:
            return True

        torrent_info = get_torrent_info(self.torrent_data, self.logger)
        return self._attach_file_selection_manager(torrent_info)

    def _attach_file_selection_manager(
        self,
        torrent_info: TorrentInfoModel | None,
    ) -> bool:
        """Attach a file selection manager if torrent metadata is available."""
        if not torrent_info or not getattr(torrent_info, "files", None):
            return False

        try:
            self.file_selection_manager = FileSelectionManager(torrent_info)
        except Exception:
            self.logger.debug(
                "Failed to initialize file selection manager for %s",
                torrent_info.name if torrent_info else "unknown torrent",
                exc_info=True,
            )
            return False

        if self.piece_manager:
            self.piece_manager.file_selection_manager = self.file_selection_manager

        # Emit METADATA_READY event when file selection manager is successfully attached
        if self.file_selection_manager:
            try:
                from ccbt.daemon.ipc_protocol import FileInfo
                from ccbt.utils.events import Event, emit_event

                # Build file list
                files = []
                for file_index, file_info in enumerate(torrent_info.files):
                    if file_info.is_padding:
                        continue
                    state = self.file_selection_manager.get_file_state(file_index)
                    files.append(
                        FileInfo(
                            index=file_index,
                            name=file_info.name,
                            size=file_info.length,
                            selected=state.selected if state else True,
                            priority=state.priority.name if state else "normal",
                            progress=state.progress if state else 0.0,
                            attributes=None,
                        )
                    )

                # Emit event (using string value, will be bridged to IPC EventType)
                _ = asyncio.create_task(  # noqa: RUF006
                    emit_event(
                        Event(
                            event_type="metadata_ready",
                            data={
                                "info_hash": self.info.info_hash.hex() if hasattr(self, "info") and self.info else "",
                                "name": torrent_info.name if hasattr(torrent_info, "name") else "",
                                "file_count": len(files),
                                "total_size": torrent_info.total_length if hasattr(torrent_info, "total_length") else 0,
                                "files": [f.model_dump() for f in files],
                            },
                        )
                    )
                )
            except Exception as e:
                self.logger.debug("Failed to emit METADATA_READY event: %s", e)

        return True

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

            # CRITICAL FIX: Register immediate connection callback AFTER tracker is started
            # This connects peers IMMEDIATELY when tracker responses arrive, before announce loop
            self._register_immediate_connection_callback()

            # Apply per-torrent configuration options (override global config)
            self._apply_per_torrent_options()

            # Start piece manager
            self.logger.debug("Starting piece manager for torrent: %s", self.info.name)
            try:
                await self.piece_manager.start()
                self.logger.debug("Piece manager started successfully")
            except Exception:
                self.logger.exception("Failed to start piece manager")
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

                    # Get per-torrent max_peers_per_torrent if set (overrides global)
                    max_peers = None
                    if "max_peers_per_torrent" in self.options:
                        max_peers = self.options["max_peers_per_torrent"]
                        if max_peers is not None and max_peers >= 0:
                            self.logger.debug(
                                "Using per-torrent max_peers_per_torrent: %s (global: %s)",
                                max_peers,
                                self.config.network.max_peers_per_torrent,
                            )
                        else:
                            max_peers = None

                    peer_manager = AsyncPeerConnectionManager(
                        td_for_peer,
                        self.piece_manager,
                        our_peer_id,
                        max_peers_per_torrent=max_peers,
                    )
                    self.logger.debug(
                        "Peer manager created, setting security manager and flags"
                    )
                    # Private attribute set dynamically for dependency injection
                    # Type checker can't resolve private attributes set via setattr/getattr
                    peer_manager._security_manager = getattr(  # type: ignore[attr-defined]
                        self.download_manager, "security_manager", None
                    )
                    peer_manager._is_private = is_private  # type: ignore[attr-defined]

                    # Wire callbacks
                    self.logger.debug("Wiring peer manager callbacks")
                    if hasattr(self.download_manager, "_on_peer_connected"):
                        callback = self.download_manager._on_peer_connected
                        if callable(callback):
                            peer_manager.on_peer_connected = callback  # type: ignore[assignment]
                    if hasattr(self.download_manager, "_on_peer_disconnected"):
                        callback = self.download_manager._on_peer_disconnected
                        if callable(callback):
                            peer_manager.on_peer_disconnected = callback  # type: ignore[assignment]
                    # CRITICAL FIX: Directly access _on_piece_received method instead of using hasattr
                    # hasattr can fail for bound methods in some cases, so we use getattr with a default
                    if self.download_manager is not None:
                        callback = getattr(self.download_manager, "_on_piece_received", None)
                        if callable(callback):
                            peer_manager.on_piece_received = callback  # type: ignore[assignment]
                            self.logger.info(
                                "Set on_piece_received callback on peer_manager from download_manager (callback=%s)",
                                callback,
                            )
                        else:
                            self.logger.warning(
                                "download_manager._on_piece_received is not callable or missing: %s (download_manager=%s)",
                                callback,
                                self.download_manager,
                            )
                    else:
                        self.logger.error(
                            "download_manager is None! Cannot set on_piece_received callback. "
                            "PIECE messages will not be processed."
                        )
                    # CRITICAL FIX: Register bitfield callback early to ensure it's available when peers connect
                    # Use download_manager's callback if available, otherwise use session's callback
                    if hasattr(self.download_manager, "_on_bitfield_received"):
                        callback = self.download_manager._on_bitfield_received
                        if callable(callback):
                            peer_manager.on_bitfield_received = callback  # type: ignore[assignment]
                    elif hasattr(self, "_on_peer_bitfield_received"):
                        callback = self._on_peer_bitfield_received
                        if callable(callback):
                            peer_manager.on_bitfield_received = callback  # type: ignore[assignment]
                    else:
                        # Create a default callback that delegates to download_manager
                        def _default_bitfield_handler(connection, message):
                            if hasattr(self.download_manager, "_on_bitfield_received"):
                                # Handle both sync and async callbacks
                                callback = self.download_manager._on_bitfield_received
                                if callable(callback):
                                    # Call with proper arguments - callback signature varies
                                    result = callback(connection, message)  # type: ignore[call-arg]
                                    if asyncio.iscoroutine(result):
                                        # Schedule async callback (fire-and-forget)
                                        # Event loop keeps reference, no need to store
                                        asyncio.create_task(result)  # noqa: RUF006 - Fire-and-forget callback
                        peer_manager.on_bitfield_received = _default_bitfield_handler  # type: ignore[assignment]

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

                    # CRITICAL FIX: Set up callbacks BEFORE starting download
                    # This ensures callbacks are available when download operations start
                    self.download_manager.on_download_complete = self._on_download_complete
                    # CRITICAL FIX: Set piece manager's on_piece_verified callback to session's method
                    # This ensures verified pieces are written to disk
                    # Wrap async method in sync callback (fire-and-forget task)
                    if self.piece_manager:
                        def _wrap_piece_verified(piece_index: int):
                            """Wrap async _on_piece_verified for sync callback."""
                            task = asyncio.create_task(self._on_piece_verified(piece_index))
                            # Keep reference to prevent garbage collection
                            if not hasattr(self, "_piece_verified_tasks"):
                                self._piece_verified_tasks = set()
                            self._piece_verified_tasks.add(task)
                            task.add_done_callback(self._piece_verified_tasks.discard)
                        self.piece_manager.on_piece_verified = _wrap_piece_verified
                    # CRITICAL FIX: Set piece manager's on_download_complete callback
                    # This ensures download completion is properly handled when all pieces are verified
                    # Wrap async method in sync callback (fire-and-forget task)
                    def _wrap_download_complete():
                        """Wrap async _on_download_complete for sync callback."""
                        task = asyncio.create_task(self._on_download_complete())
                        # Keep reference to prevent garbage collection
                        if not hasattr(self, "_download_complete_tasks"):
                            self._download_complete_tasks = set()
                        self._download_complete_tasks.add(task)
                        task.add_done_callback(self._download_complete_tasks.discard)

                    # CRITICAL FIX: Initialize web seeds from magnet link (ws= parameters)
                    # Web seeds are stored in torrent_data and should be added to WebSeedExtension
                    if self.session_manager and self.session_manager.extension_manager:
                        web_seeds = None
                        if isinstance(self.torrent_data, dict):
                            web_seeds = self.torrent_data.get("web_seeds")
                        elif hasattr(self.torrent_data, "web_seeds"):
                            web_seeds = getattr(self.torrent_data, "web_seeds", None)

                        if web_seeds and isinstance(web_seeds, list):
                            try:
                                for web_seed_url in web_seeds:
                                    if isinstance(web_seed_url, str) and web_seed_url.strip():
                                        # Validate URL format
                                        if web_seed_url.startswith(("http://", "https://")):
                                            self.session_manager.extension_manager.add_webseed(
                                                web_seed_url.strip(),
                                                name=f"WebSeed: {self.info.name}",
                                            )
                                            self.logger.info(
                                                "Added web seed from magnet link: %s",
                                                web_seed_url.strip(),
                                            )
                                        else:
                                            self.logger.warning(
                                                "Invalid web seed URL format (must start with http:// or https://): %s",
                                                web_seed_url,
                                            )
                            except Exception as e:
                                self.logger.warning(
                                    "Failed to add web seeds from magnet link: %s",
                                    e,
                                    exc_info=True,
                                )

                    # Also set on download_manager for compatibility
                    self.download_manager.on_piece_verified = self._on_piece_verified

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
                except Exception:
                    self.logger.exception("Failed to initialize peer manager early")
                    # Continue without early initialization - will be created when peers arrive
                    # Don't re-raise - allow session to start even if peer manager init fails

            # Set up callbacks (if not already set above)
            if not hasattr(self.download_manager, "on_download_complete") or self.download_manager.on_download_complete is None:
                self.download_manager.on_download_complete = self._on_download_complete
            # CRITICAL FIX: Set piece manager's on_piece_verified callback to session's method
            # This ensures verified pieces are written to disk
            # Wrap async method in sync callback (fire-and-forget task)
            if self.piece_manager:
                if not hasattr(self.piece_manager, "on_piece_verified") or self.piece_manager.on_piece_verified is None:
                    def _wrap_piece_verified(piece_index: int):
                        """Wrap async _on_piece_verified for sync callback."""
                        task = asyncio.create_task(self._on_piece_verified(piece_index))
                        # Keep reference to prevent garbage collection
                        if not hasattr(self, "_piece_verified_tasks"):
                            self._piece_verified_tasks = set()
                        self._piece_verified_tasks.add(task)
                        task.add_done_callback(self._piece_verified_tasks.discard)
                    self.piece_manager.on_piece_verified = _wrap_piece_verified
                # CRITICAL FIX: Set piece manager's on_download_complete callback
                # This ensures download completion is properly handled when all pieces are verified
                # Wrap async method in sync callback (fire-and-forget task)
                if not hasattr(self.piece_manager, "on_download_complete") or self.piece_manager.on_download_complete is None:
                    def _wrap_download_complete():
                        """Wrap async _on_download_complete for sync callback."""
                        task = asyncio.create_task(self._on_download_complete())
                        # Keep reference to prevent garbage collection
                        if not hasattr(self, "_download_complete_tasks"):
                            self._download_complete_tasks = set()
                        self._download_complete_tasks.add(task)
                        task.add_done_callback(self._download_complete_tasks.discard)
                    self.piece_manager.on_download_complete = _wrap_download_complete
            # Also set on download_manager for compatibility
            # Wrap async method in sync callback (fire-and-forget task)
            if not hasattr(self.download_manager, "on_piece_verified") or self.download_manager.on_piece_verified is None:
                def _wrap_piece_verified_dm(piece_index: int):
                    """Wrap async _on_piece_verified for sync callback."""
                    task = asyncio.create_task(self._on_piece_verified(piece_index))
                    # Keep reference to prevent garbage collection
                    if not hasattr(self, "_piece_verified_tasks"):
                        self._piece_verified_tasks = set()
                    self._piece_verified_tasks.add(task)
                    task.add_done_callback(self._piece_verified_tasks.discard)
                self.download_manager.on_piece_verified = _wrap_piece_verified_dm

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

            # CRITICAL FIX: Set up DHT peer discovery ONLY when explicitly requested
            # DHT should not be initialized automatically just because enable_dht=True in config
            # It should only initialize when:
            # 1. Explicitly requested via CLI flag (--enable-dht)
            # 2. For magnet links (which need DHT for peer discovery)
            dht_explicitly_requested = getattr(self, "options", {}).get("enable_dht", False)
            is_magnet_link = (
                isinstance(self.torrent_data, dict)
                and self.torrent_data.get("is_magnet", False)
            )
            
            # Only initialize DHT if explicitly requested or for magnet links
            should_init_dht = (dht_explicitly_requested or is_magnet_link) and self.config.discovery.enable_dht and self.session_manager
            
            if should_init_dht:
                try:
                    from ccbt.session.dht_setup import DHTDiscoverySetup

                    dht_setup = DHTDiscoverySetup(self)
                    await dht_setup.setup_dht_discovery()
                    # CRITICAL FIX: Store dht_setup reference so announce loop can use it for metadata exchange
                    self._dht_setup = dht_setup
                    self.logger.info(
                        "DHT discovery initialized (explicitly requested=%s, magnet link=%s)",
                        dht_explicitly_requested,
                        is_magnet_link,
                    )
                except Exception as dht_error:
                    # Log but don't fail session start - DHT is best-effort
                    self.logger.warning(
                        "Failed to set up DHT peer discovery: %s (peer discovery may be limited)",
                        dht_error,
                    )
                    self._dht_setup = None
            elif self.config.discovery.enable_dht and self.session_manager:
                # DHT is enabled in config but not explicitly requested - log and skip
                self.logger.debug(
                    "DHT is enabled in config but not explicitly requested (enable_dht=%s, is_magnet=%s). "
                    "Skipping DHT initialization. Use --enable-dht flag to enable DHT discovery.",
                    dht_explicitly_requested,
                    is_magnet_link,
                )
                self._dht_setup = None

            # CRITICAL FIX: Start incoming peer queue processor
            # This processes queued incoming connections when peer manager isn't ready yet
            self._incoming_queue_task = asyncio.create_task(
                self._incoming_peer_handler.run_queue_processor()
            )

            # CRITICAL FIX: Set up event handler for peer_count_low events
            # This triggers immediate peer discovery when peer count drops critically low
            try:
                from ccbt.utils.events import EventHandler, get_event_bus

                class PeerCountLowHandler(EventHandler):
                    """Handler for peer_count_low events that triggers immediate discovery."""

                    def __init__(self, session: Any) -> None:
                        self.session = session
                        self.name = f"PeerCountLowHandler-{session.info.name}"

                    async def handle(self, event: Any) -> None:
                        """Handle peer_count_low event by triggering immediate discovery.

                        CRITICAL: Wait for tracker peers to connect before starting DHT.
                        User requirement: "always connect and request to peers before starting peer discovery at all"
                        """
                        event_data = event.data if hasattr(event, "data") else {}
                        info_hash = event_data.get("info_hash", "")
                        active_peer_count = event_data.get("active_peer_count", 0)

                        # Only handle events for this torrent
                        if (
                            info_hash
                            and hasattr(self.session.info, "info_hash")
                            and info_hash != self.session.info.info_hash.hex()
                        ):
                            return  # Not for this torrent

                        self.session.logger.info(
                            "Received peer_count_low event (active peers: %d). Checking if tracker peers are connecting before starting DHT...",
                            active_peer_count,
                        )

                        # CRITICAL FIX: Wait for connection batches to complete before starting DHT
                        # User requirement: "peer count low checks should only start basically after the first batches of connections are exhausted"
                        # Check if connection batches are currently in progress
                        if hasattr(self.session, "download_manager") and self.session.download_manager:
                            peer_manager = getattr(self.session.download_manager, "peer_manager", None)
                            if peer_manager:
                                connection_batches_in_progress = getattr(peer_manager, "_connection_batches_in_progress", False)
                                if connection_batches_in_progress:
                                    self.session.logger.info(
                                        "⏸️ DHT DELAY: Connection batches are in progress. Waiting for batches to complete before starting DHT..."
                                    )
                                    # Wait up to 30 seconds for batches to complete, checking every 2 seconds
                                    max_wait = 30.0
                                    check_interval = 2.0
                                    waited = 0.0
                                    while waited < max_wait:
                                        await asyncio.sleep(check_interval)
                                        waited += check_interval
                                        connection_batches_in_progress = getattr(peer_manager, "_connection_batches_in_progress", False)
                                        if not connection_batches_in_progress:
                                            self.session.logger.info(
                                                "✅ DHT DELAY: Connection batches completed after %.1fs. Proceeding with DHT discovery...",
                                                waited,
                                            )
                                            break
                                    else:
                                        self.session.logger.warning(
                                            "⏸️ DHT DELAY: Connection batches still in progress after %.1fs wait. Proceeding anyway...",
                                            max_wait,
                                        )

                        # CRITICAL FIX: Also check tracker peer connection timestamp (secondary check)
                        # This ensures we wait for tracker responses to be processed
                        import time as time_module
                        tracker_peers_connecting_until = getattr(self.session, "_tracker_peers_connecting_until", None)
                        if tracker_peers_connecting_until and time_module.time() < tracker_peers_connecting_until:
                            wait_time = tracker_peers_connecting_until - time_module.time()
                            self.session.logger.info(
                                "⏸️ DHT DELAY: Tracker peers are currently being connected. Waiting %.1fs before starting DHT to allow tracker connections to complete...",
                                wait_time,
                            )
                            await asyncio.sleep(min(wait_time, 5.0))  # Wait up to 5 seconds or until timestamp expires

                        # Check if we have active peers now (tracker connections may have succeeded)
                        if hasattr(self.session, "download_manager") and self.session.download_manager:
                            peer_manager = getattr(self.session.download_manager, "peer_manager", None)
                            if peer_manager and hasattr(peer_manager, "get_active_peers"):
                                current_active = len(peer_manager.get_active_peers())
                                if current_active > active_peer_count:
                                    self.session.logger.info(
                                        "✅ DHT SKIP: Active peer count increased from %d to %d (tracker connections succeeded). Skipping DHT for now.",
                                        active_peer_count,
                                        current_active,
                                    )
                                    return  # Skip DHT if tracker peers connected successfully

                        # CRITICAL FIX: Don't trigger immediate DHT if we have fewer than 50 peers
                        # This prevents aggressive DHT queries that can cause blacklisting
                        # EXCEPTION: Fail-fast mode - if active_peers == 0 for >30s, allow DHT even if <50 peers
                        min_peers_before_dht = 50
                        enable_fail_fast = getattr(
                            self.session.config.network,
                            "enable_fail_fast_dht",
                            True,
                        )
                        fail_fast_timeout = getattr(
                            self.session.config.network,
                            "fail_fast_dht_timeout",
                            30.0,
                        )
                        
                        # Check fail-fast condition: zero active peers for >30s
                        fail_fast_triggered = False
                        if enable_fail_fast and active_peer_count == 0:
                            # Check how long we've had zero peers
                            zero_peers_since = getattr(self.session, "_zero_peers_since", None)
                            current_time = time.time()
                            if zero_peers_since is None:
                                # First time we see zero peers - record timestamp
                                self.session._zero_peers_since = current_time
                                self.session.logger.debug(
                                    "Recording zero peers timestamp (fail-fast DHT will trigger after %.1fs if still zero)",
                                    fail_fast_timeout,
                                )
                            else:
                                # Check if we've been at zero for >30s
                                time_at_zero = current_time - zero_peers_since
                                if time_at_zero >= fail_fast_timeout:
                                    fail_fast_triggered = True
                                    self.session.logger.warning(
                                        "🚨 FAIL-FAST DHT: Active peer count has been 0 for %.1fs (>= %.1fs timeout). "
                                        "Triggering DHT discovery even though peer count < %d to prevent download stall.",
                                        time_at_zero,
                                        fail_fast_timeout,
                                        min_peers_before_dht,
                                    )
                        else:
                            # We have peers now - clear zero_peers_since
                            if hasattr(self.session, "_zero_peers_since"):
                                delattr(self.session, "_zero_peers_since")
                        
                        if active_peer_count < min_peers_before_dht and not fail_fast_triggered:
                            self.session.logger.info(
                                "⏸️ DHT SKIP: Active peer count (%d) is below minimum (%d). Skipping immediate DHT discovery to avoid blacklisting. "
                                "DHT will start automatically once minimum peer count is reached.",
                                active_peer_count,
                                min_peers_before_dht,
                            )
                            return  # Skip DHT until we have minimum peers

                        self.session.logger.info(
                            "Triggering immediate DHT discovery (active peers: %d >= %d, tracker connections completed)...",
                            active_peer_count,
                            min_peers_before_dht,
                        )

                        # Trigger immediate DHT query if DHT is enabled
                        # CRITICAL FIX: Rate limit immediate DHT queries to prevent peer disconnections
                        # Check if we've triggered an immediate query recently (within last 60 seconds)
                        current_time = time.time()
                        last_immediate_query_key = f"_last_immediate_dht_query_{self.session.info.info_hash.hex()}"
                        last_immediate_query = getattr(self.session, last_immediate_query_key, 0)
                        min_interval_between_immediate_queries = 60.0  # Increased from 10s to 60s to prevent blacklisting

                        if current_time - last_immediate_query < min_interval_between_immediate_queries:
                            self.session.logger.debug(
                                "Skipping immediate DHT query for %s: too soon after last query (%.1fs ago, min interval: %.1fs)",
                                self.session.info.name,
                                current_time - last_immediate_query,
                                min_interval_between_immediate_queries,
                            )
                            return

                        if self.session.config.discovery.enable_dht and hasattr(self.session, "_dht_setup") and self.session._dht_setup:
                            try:
                                dht_client = self.session.session_manager.dht_client if self.session.session_manager else None
                                if dht_client:
                                    # CRITICAL FIX: Use very conservative parameters to prevent blacklisting
                                    # Reduced query parameters to avoid overwhelming the DHT network
                                    setattr(self.session, last_immediate_query_key, current_time)
                                    self.session.logger.info(
                                        "Triggering immediate DHT get_peers query for %s (max_peers=50, conservative params to prevent blacklisting)",
                                        self.session.info.name
                                    )
                                    discovered_peers = await dht_client.get_peers(
                                        self.session.info.info_hash,
                                        max_peers=50,  # Reduced from 100 to prevent overwhelming
                                        alpha=3,  # Reduced from 6 to be more conservative (BEP 5 compliant)
                                        k=8,  # Reduced from 16 to be more conservative (BEP 5 compliant)
                                        max_depth=8,  # Reduced from 12 to be more conservative (BEP 5 compliant)
                                    )
                                    # CRITICAL FIX: Immediately connect to discovered peers
                                    if discovered_peers and self.session.download_manager:
                                        peer_manager = getattr(self.session.download_manager, "peer_manager", None)
                                        if peer_manager:
                                            peer_list = [
                                                {
                                                    "ip": ip,
                                                    "port": port,
                                                    "peer_source": "dht_immediate",
                                                }
                                                for ip, port in discovered_peers[:50]  # Connect to first 50
                                            ]
                                            if peer_list:
                                                await peer_manager.connect_to_peers(peer_list)
                                                self.session.logger.info(
                                                    "Immediate DHT query returned %d peer(s), connecting to %d",
                                                    len(discovered_peers),
                                                    len(peer_list),
                                                )
                            except Exception as e:
                                self.session.logger.warning("Failed to trigger immediate DHT query: %s", e, exc_info=True)

                        # Trigger immediate tracker announce if trackers are available
                        if hasattr(self.session, "_announce_task") and self.session._announce_task and not self.session._announce_task.done():
                            async def immediate_announce() -> None:
                                try:
                                    td: dict[str, Any]
                                    if isinstance(self.session.torrent_data, TorrentInfoModel):
                                        td = {
                                            "info_hash": self.session.torrent_data.info_hash,
                                            "name": self.session.torrent_data.name,
                                            "announce": getattr(self.session.torrent_data, "announce", ""),
                                        }
                                    else:
                                        td = self.session.torrent_data

                                    tracker_urls = self.session._collect_trackers(td)
                                    if tracker_urls:
                                        listen_port = (
                                            self.session.config.network.listen_port_tcp
                                            or self.session.config.network.listen_port
                                        )
                                        response = await self.session.tracker.announce(td, port=listen_port)
                                        if response and response.peers and self.session.download_manager:
                                            peer_manager = getattr(self.session.download_manager, "peer_manager", None)
                                            if peer_manager:
                                                peer_list = [
                                                    {
                                                        "ip": p.ip,
                                                        "port": p.port,
                                                        "peer_source": "tracker",
                                                    }
                                                    for p in response.peers
                                                    if hasattr(p, "ip") and hasattr(p, "port")
                                                ]
                                                if peer_list:
                                                    await peer_manager.connect_to_peers(peer_list)
                                                    self.session.logger.info(
                                                        "Immediate tracker announce returned %d peer(s)",
                                                        len(peer_list),
                                                    )
                                except Exception as e:
                                    self.session.logger.debug("Failed to perform immediate tracker announce: %s", e)

                            _ = asyncio.create_task(immediate_announce())  # noqa: RUF006

                # Register event handler
                handler = PeerCountLowHandler(self)
                event_bus = get_event_bus()
                event_bus.register_handler("peer_count_low", handler)
                self._peer_count_low_handler = handler  # Store reference for cleanup
            except Exception as e:
                self.logger.debug("Failed to set up peer_count_low event handler: %s", e)
                self._peer_count_low_handler = None

            # Start background tasks with error isolation
            # CRITICAL FIX: Wrap task creation to ensure exceptions don't crash the daemon
            # The event loop exception handler will catch any unhandled exceptions in these tasks
            try:
                self.logger.info(
                    "🔍 TRACKER DISCOVERY: Starting tracker announce loop for %s (initial intervals: 60s, 120s, 300s, then adaptive)",
                    self.info.name,
                )
                self._announce_task = asyncio.create_task(self._announce_loop())
                self._status_task = asyncio.create_task(self._status_loop())

                # Start checkpoint task if enabled
                if self.config.disk.checkpoint_enabled:
                    self._checkpoint_task = asyncio.create_task(self._checkpoint_loop())

                # Start seeding stats task if torrent is completed (seeding)
                # CRITICAL FIX: For new sessions (especially magnet links), status will be "starting" not "seeding"
                # Only start seeding stats task if status is actually "seeding"
                # Use defensive checks to avoid AttributeError on missing attributes
                try:
                    # Safely check if info exists and has status attribute
                    info_status = None
                    if hasattr(self, "info") and self.info is not None:
                        # Use getattr with default to safely access status
                        info_status = getattr(self.info, "status", None)

                    if info_status == "seeding":
                        self._seeding_stats_task = asyncio.create_task(self._seeding_stats_loop())
                except (AttributeError, TypeError) as attr_error:
                    # If info doesn't have expected attributes, log and continue
                    # This can happen during initialization before all attributes are set
                    self.logger.debug(
                        "Cannot check seeding status (info may not be fully initialized): %s",
                        attr_error,
                    )
            except Exception as task_error:
                # Log error but don't fail session start - tasks will be handled by exception handler
                # CRITICAL FIX: Don't re-raise AttributeError for missing attributes on TorrentSessionInfo
                # This can happen during initialization when attributes aren't fully set yet
                if isinstance(task_error, AttributeError) and "progress" in str(task_error):
                    self.logger.debug(
                        "Ignoring AttributeError for missing 'progress' attribute on TorrentSessionInfo "
                        "(this is expected during initialization): %s",
                        task_error,
                    )
                    # Don't re-raise - continue with session start
                else:
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

    async def accept_incoming_peer(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        handshake: Any,
        peer_ip: str,
        peer_port: int,
    ) -> None:
        """Accept an incoming peer connection.

        This method is called by the TCP server when a peer connects to us.
        It delegates to the IncomingPeerHandler to process the connection.

        Args:
            reader: Stream reader for the connection
            writer: Stream writer for the connection
            handshake: BitTorrent handshake data
            peer_ip: Peer IP address
            peer_port: Peer port

        """
        await self._incoming_peer_handler.accept_incoming_peer(
            reader, writer, handshake, peer_ip, peer_port
        )

    async def stop(self) -> None:
        """Stop the async torrent session."""
        self._stop_event.set()
        self._stopped = True  # Signal incoming queue processor to stop

        # Cancel background tasks and await completion
        tasks_to_cancel = []
        if self._incoming_queue_task:
            self._incoming_queue_task.cancel()
            tasks_to_cancel.append(self._incoming_queue_task)
        if self._announce_task:
            self._announce_task.cancel()
            tasks_to_cancel.append(self._announce_task)
        if self._status_task:
            self._status_task.cancel()
            tasks_to_cancel.append(self._status_task)
        if self._checkpoint_task:
            self._checkpoint_task.cancel()
            tasks_to_cancel.append(self._checkpoint_task)
        if self._seeding_stats_task:
            self._seeding_stats_task.cancel()
            tasks_to_cancel.append(self._seeding_stats_task)
        # CRITICAL FIX: Cancel DHT discovery task to prevent it from continuing during shutdown
        if hasattr(self, "_dht_discovery_task") and self._dht_discovery_task and not self._dht_discovery_task.done():
            self._dht_discovery_task.cancel()
            tasks_to_cancel.append(self._dht_discovery_task)

        # Await all task cancellations to complete with timeout to prevent hanging
        if tasks_to_cancel:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                self.logger.warning(
                    "Some background tasks did not cancel within timeout during torrent session stop"
                )

        # Save final checkpoint before stopping with full state
        if (
            self.config.disk.checkpoint_enabled
            and not self.download_manager.download_complete
        ):
            try:
                # Use checkpoint controller to save full state including new fields
                if hasattr(self, "checkpoint_controller") and self.checkpoint_controller:
                    await self.checkpoint_controller.save_checkpoint_state(self)
                else:
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
            # Save checkpoint before pausing with full state
            if self.config.disk.checkpoint_enabled:
                try:
                    # Use checkpoint controller to save full state including new fields
                    if hasattr(self, "checkpoint_controller") and self.checkpoint_controller:
                        await self.checkpoint_controller.save_checkpoint_state(self)
                    else:
                        await self._save_checkpoint()
                except Exception as e:
                    self.logger.warning("Failed to save checkpoint on pause: %s", e)

            # Stop background tasks
            self._stop_event.set()

            # Cancel background tasks and await completion
            tasks_to_cancel = []
            if self._announce_task:
                self._announce_task.cancel()
                tasks_to_cancel.append(self._announce_task)
            if self._status_task:
                self._status_task.cancel()
                tasks_to_cancel.append(self._status_task)
            if self._checkpoint_task:
                self._checkpoint_task.cancel()
                tasks_to_cancel.append(self._checkpoint_task)
            if self._seeding_stats_task:
                self._seeding_stats_task.cancel()
                tasks_to_cancel.append(self._seeding_stats_task)

            # Await all task cancellations to complete
            if tasks_to_cancel:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

            # Stop heavy components
            if self.pex_manager:
                await self.pex_manager.stop()
            await self.tracker.stop()
            await self.download_manager.stop()

            # Check if torrent was seeding before pausing
            was_seeding = hasattr(self, "info") and self.info.status == "seeding"

            self.info.status = "paused"
            self.logger.info("Paused torrent session: %s", self.info.name)

            # Emit SEEDING_STOPPED event if torrent was seeding (completed)
            if was_seeding:
                try:
                    from ccbt.utils.events import Event, emit_event

                    await emit_event(
                        Event(
                            event_type="seeding_stopped",
                            data={
                                "info_hash": self.info.info_hash.hex(),
                                "name": self.info.name,
                                "reason": "paused",
                            },
                        )
                    )
                except Exception as e:
                    self.logger.debug("Failed to emit SEEDING_STOPPED event: %s", e)
        except Exception:
            self.logger.exception("Failed to pause torrent")
            raise

    async def resume(self) -> None:
        """Resume a previously paused torrent session.

        Restores checkpoint state including peer lists, tracker state,
        and session configuration before restarting the session.
        """
        try:
            # Load and restore checkpoint state if available
            if self.config.disk.checkpoint_enabled and hasattr(self, "checkpoint_manager"):
                try:
                    checkpoint = await self.checkpoint_manager.load_checkpoint(
                        self.info.info_hash
                    )
                    if checkpoint and hasattr(self, "checkpoint_controller") and self.checkpoint_controller:
                        # Restore checkpoint state (peers, trackers, etc.)
                        await self.checkpoint_controller.resume_from_checkpoint(
                            checkpoint, self
                        )
                        self.logger.info(
                            "Restored checkpoint state before resuming: %s",
                            self.info.name,
                        )
                except Exception as e:
                    self.logger.debug(
                        "Could not restore checkpoint on resume (will use existing state): %s",
                        e,
                    )

            await self.start(resume=True)
            self.info.status = "downloading"
            self.logger.info("Resumed torrent session: %s", self.info.name)
        except Exception:
            self.logger.exception("Failed to resume torrent")
            raise

    async def cancel(self) -> None:
        """Cancel the torrent session (pause but keep in session).

        Similar to pause but sets status to 'cancelled' and keeps torrent
        in session manager for potential resume later. Does not remove
        downloaded data or remove torrent from session.
        """
        try:
            # Save checkpoint before cancelling with full state
            if self.config.disk.checkpoint_enabled:
                try:
                    # Use checkpoint controller to save full state including new fields
                    if hasattr(self, "checkpoint_controller") and self.checkpoint_controller:
                        await self.checkpoint_controller.save_checkpoint_state(self)
                    else:
                        await self._save_checkpoint()
                except Exception as e:
                    self.logger.warning("Failed to save checkpoint on cancel: %s", e)

            # Stop background tasks
            self._stop_event.set()

            # Cancel background tasks and await completion
            tasks_to_cancel = []
            if self._announce_task:
                self._announce_task.cancel()
                tasks_to_cancel.append(self._announce_task)
            if self._status_task:
                self._status_task.cancel()
                tasks_to_cancel.append(self._status_task)
            if self._checkpoint_task:
                self._checkpoint_task.cancel()
                tasks_to_cancel.append(self._checkpoint_task)
            if self._seeding_stats_task:
                self._seeding_stats_task.cancel()
                tasks_to_cancel.append(self._seeding_stats_task)

            # Await all task cancellations to complete
            if tasks_to_cancel:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

            # Stop heavy components
            if self.pex_manager:
                await self.pex_manager.stop()
            await self.tracker.stop()
            await self.download_manager.stop()

            # Check if torrent was seeding before cancelling
            was_seeding = hasattr(self, "info") and self.info.status == "seeding"

            # Set status to cancelled (different from paused)
            self.info.status = "cancelled"
            self.logger.info("Cancelled torrent session: %s", self.info.name)

            # Emit SEEDING_STOPPED event if torrent was seeding (completed)
            if was_seeding:
                try:
                    from ccbt.utils.events import Event, emit_event

                    await emit_event(
                        Event(
                            event_type="seeding_stopped",
                            data={
                                "info_hash": self.info.info_hash.hex(),
                                "name": self.info.name,
                                "reason": "cancelled",
                            },
                        )
                    )
                except Exception as e:
                    self.logger.debug("Failed to emit SEEDING_STOPPED event: %s", e)
        except Exception:
            self.logger.exception("Failed to cancel torrent")
            raise

    async def force_start(self) -> None:
        """Force start the torrent session (bypass queue limits).

        Forces the torrent to start immediately regardless of queue limits.
        Sets priority to maximum and starts/resumes the session.
        """
        try:
            # If paused or cancelled, resume
            if self.info.status in ("paused", "cancelled"):
                await self.resume()
                self.logger.info("Force started (resumed) torrent session: %s", self.info.name)
            # If stopped, start
            elif self.info.status == "stopped":
                await self.start(resume=True)
                self.info.status = "downloading"
                self.logger.info("Force started torrent session: %s", self.info.name)
            # If already active, just log
            elif self.info.status in ("downloading", "seeding", "starting"):
                self.logger.info("Torrent already active: %s", self.info.name)
            else:
                # For any other status, try to start
                await self.start(resume=True)
                self.info.status = "downloading"
                self.logger.info("Force started torrent session: %s", self.info.name)
        except Exception:
            self.logger.exception("Failed to force start torrent")
            raise

    def _register_immediate_connection_callback(self) -> None:
        """Register immediate connection callback for tracker responses.

        This connects peers IMMEDIATELY when tracker responses arrive,
        before the announce loop processes them. This is the highest priority
        connection path as requested by the user.
        """
        async def immediate_peer_connection(peers: list[dict[str, Any]], tracker_url: str) -> None:
            """Immediate peer connection callback - connects peers as soon as they arrive."""
            if not peers:
                return

            # CRITICAL FIX: Set timestamp to indicate tracker peers are being connected
            # This prevents DHT from starting until tracker connections complete
            # Use timestamp to handle multiple concurrent callbacks - extend the time if needed
            import time as time_module
            connection_start_time = time_module.time()
            max_wait_time = 10.0  # Maximum 10 seconds wait (reduced from 15)

            # If flag is already set, extend it if this callback started later
            if self._tracker_peers_connecting_until is None:  # type: ignore[attr-defined]
                self._tracker_peers_connecting_until = connection_start_time + max_wait_time  # type: ignore[attr-defined]
            else:
                # Extend the time if this callback started after the previous one
                current_until = self._tracker_peers_connecting_until  # type: ignore[attr-defined]
                new_until = connection_start_time + max_wait_time
                if new_until > current_until:
                    self._tracker_peers_connecting_until = new_until  # type: ignore[attr-defined]

            self.logger.info(
                "⚡ IMMEDIATE CONNECTION: Received %d peer(s) from %s - connecting IMMEDIATELY (bypassing announce loop, blocking DHT until %.1fs)",
                len(peers),
                tracker_url,
                self._tracker_peers_connecting_until - connection_start_time,  # type: ignore[attr-defined]
            )

            try:
                # Wait for peer_manager to be ready (up to 5 seconds)
                has_peer_manager = (
                    hasattr(self.download_manager, "peer_manager")
                    and self.download_manager.peer_manager is not None
                )

                if not has_peer_manager:
                    self.logger.warning(
                        "⚡ IMMEDIATE CONNECTION: peer_manager not ready, waiting up to 5 seconds...",
                    )
                    for retry in range(10):  # 10 retries * 0.5s = 5 seconds
                        await asyncio.sleep(0.5)
                        has_peer_manager = (
                            hasattr(self.download_manager, "peer_manager")
                            and self.download_manager.peer_manager is not None
                        )
                        if has_peer_manager:
                            self.logger.info(
                                "⚡ IMMEDIATE CONNECTION: peer_manager ready after %.1fs",
                                (retry + 1) * 0.5,
                            )
                            break

                if has_peer_manager and self.download_manager.peer_manager:
                    # Deduplicate peers
                    seen_peers = set()
                    unique_peer_list = []
                    for peer in peers:
                        peer_key = (peer.get("ip"), peer.get("port"))
                        if peer_key not in seen_peers:
                            seen_peers.add(peer_key)
                            unique_peer_list.append(peer)

                    if unique_peer_list:
                        self.logger.info(
                            "⚡ IMMEDIATE CONNECTION: Connecting %d unique peer(s) immediately for %s",
                            len(unique_peer_list),
                            self.info.name,
                        )
                        try:
                            # Type checker can't infer that peer_manager is not None
                            await self.download_manager.peer_manager.connect_to_peers(  # type: ignore[union-attr]
                                unique_peer_list
                            )
                            self.logger.info(
                                "✅ IMMEDIATE CONNECTION: Started connection attempts for %d peer(s) for %s (connections will continue in background)",
                                len(unique_peer_list),
                                self.info.name,
                            )
                            
                            # CRITICAL FIX: Ensure download starts immediately after connecting peers
                            # This ensures piece requests are sent as soon as connections are established
                            # For magnet links, metadata may have been received, so we need to restart download
                            if hasattr(self, "piece_manager") and self.piece_manager:
                                try:
                                    # Check if metadata is available (num_pieces > 0)
                                    num_pieces = getattr(self.piece_manager, "num_pieces", 0)
                                    is_downloading = getattr(self.piece_manager, "is_downloading", False)
                                    
                                    # If metadata is available and download hasn't started properly, restart it
                                    if num_pieces > 0 and hasattr(self.piece_manager, "start_download"):
                                        self.logger.info(
                                            "🚀 IMMEDIATE CONNECTION: Triggering download start after connecting %d peer(s) (num_pieces=%d, is_downloading=%s)",
                                            len(unique_peer_list),
                                            num_pieces,
                                            is_downloading,
                                        )
                                        # Use peer_manager from download_manager
                                        peer_manager = self.download_manager.peer_manager  # type: ignore[union-attr]
                                        if asyncio.iscoroutinefunction(self.piece_manager.start_download):
                                            await self.piece_manager.start_download(peer_manager)
                                        else:
                                            self.piece_manager.start_download(peer_manager)
                                        self.logger.info(
                                            "✅ IMMEDIATE CONNECTION: Download started after connecting peers (num_pieces=%d)",
                                            num_pieces,
                                        )
                                except Exception as e:
                                    self.logger.warning(
                                        "Failed to start download after immediate connection: %s",
                                        e,
                                        exc_info=True,
                                    )

                            # CRITICAL FIX: Wait until the timestamp expires (or shorter if connections complete)
                            # This prevents DHT from starting too early while allowing multiple callbacks
                            wait_until = self._tracker_peers_connecting_until  # type: ignore[attr-defined]
                            if wait_until:
                                wait_time = max(0.0, wait_until - time_module.time())
                                if wait_time > 0:
                                    self.logger.info(
                                        "⏸️ IMMEDIATE CONNECTION: Keeping DHT blocked for %.1fs to allow tracker connections to complete...",
                                        wait_time,
                                    )
                                    await asyncio.sleep(wait_time)

                        except Exception as e:
                            self.logger.warning(
                                "Failed to connect peers immediately: %s",
                                e,
                                exc_info=True,
                            )
                else:
                    self.logger.warning(
                        "⚡ IMMEDIATE CONNECTION: peer_manager still not ready after 5 seconds, peers will be connected via announce loop",
                    )
            finally:
                # CRITICAL FIX: Clear flag only if this callback's time has expired
                # This allows multiple callbacks to coordinate properly
                import time as time_module
                if self._tracker_peers_connecting_until:  # type: ignore[attr-defined]
                    if time_module.time() >= self._tracker_peers_connecting_until:  # type: ignore[attr-defined]
                        self._tracker_peers_connecting_until = None  # type: ignore[attr-defined]
                        self.logger.info(
                            "✅ IMMEDIATE CONNECTION: Tracker peer connection wait period expired (flag cleared, DHT can now start if needed)"
                        )
                    else:
                        self.logger.debug(
                            "⏸️ IMMEDIATE CONNECTION: Other callbacks still active, keeping flag set until %.1fs",
                            self._tracker_peers_connecting_until - time_module.time(),  # type: ignore[attr-defined]
                        )

        # Register callback on HTTP tracker client
        self.tracker.on_peers_received = immediate_peer_connection

        # Register callback on UDP tracker client (via session_manager)
        if self.session_manager and hasattr(self.session_manager, "udp_tracker_client"):
            udp_client = self.session_manager.udp_tracker_client
            if udp_client:
                udp_client.on_peers_received = immediate_peer_connection
                self.logger.info(
                    "✅ IMMEDIATE CONNECTION: Registered callback on HTTP and UDP tracker clients for %s",
                    self.info.name,
                )

    async def _announce_loop(self) -> None:
        """Background task for periodic tracker announces with adaptive intervals."""
        base_announce_interval = self.config.discovery.tracker_announce_interval

        # Aggressive initial discovery intervals for faster peer discovery
        # First 3 announces use shorter intervals: 60s, 120s, 300s
        # Then switch to adaptive intervals based on tracker performance
        initial_announce_intervals = [60.0, 120.0, 300.0]

        current_interval = base_announce_interval

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
                    self.logger.info(
                        "No trackers found for %s; skipping tracker announce (relying on DHT). "
                        "If this magnet link should have trackers, they may not have been parsed correctly.",
                        td.get("name", "unknown"),
                    )
                    # Wait longer when no trackers (DHT discovery is slower)
                    await asyncio.sleep(current_interval * 2)
                    continue

                # Log tracker count for debugging
                self.logger.info(
                    "TRACKER_COLLECTION: Found %d tracker(s) for %s, starting announce loop",
                    len(tracker_urls),
                    td.get("name", "unknown"),
                )

                # CRITICAL FIX: Use listen_port_tcp (or listen_port as fallback) and get external port from NAT
                listen_port = (
                    self.config.network.listen_port_tcp
                    or self.config.network.listen_port
                )
                announce_port = listen_port

                # Try to get external port from NAT manager if available
                if (
                    self.session_manager
                    and hasattr(self.session_manager, "nat_manager")
                    and self.session_manager.nat_manager
                ):
                    try:
                        external_port = (
                            await self.session_manager.nat_manager.get_external_port(
                                listen_port, "tcp"
                            )
                        )
                        if external_port is not None:
                            announce_port = external_port
                            self.logger.debug(
                                "Using external port %d (mapped from internal %d) for periodic announce",
                                external_port,
                                listen_port,
                            )
                    except Exception:
                        self.logger.debug(
                            "Failed to get external port from NAT manager, using internal port %d",
                            listen_port,
                            exc_info=True,
                        )

                # CRITICAL FIX: Use announce_to_multiple to announce to all trackers, not just one
                if hasattr(self.tracker, "announce_to_multiple"):
                    self.logger.info(
                        "🚨 ANNOUNCE_LOOP: Calling announce_to_multiple for %d tracker(s) (port=%d)",
                        len(tracker_urls),
                        announce_port,
                    )
                    responses = await self.tracker.announce_to_multiple(
                        td, tracker_urls, port=announce_port, event=""
                    )
                    self.logger.info(
                        "🚨 ANNOUNCE_LOOP: announce_to_multiple returned %d response(s) (responses type: %s)",
                        len(responses) if responses else 0,
                        type(responses).__name__ if responses else "None",
                    )
                    # Check if any tracker responded successfully
                    successful_responses = [r for r in responses if r is not None]
                    self.logger.info(
                        "🚨 ANNOUNCE_LOOP: Filtered to %d successful response(s) (from %d total)",
                        len(successful_responses),
                        len(responses) if responses else 0,
                    )
                    total_peers = sum(
                        len(getattr(r, "peers", []) or []) for r in successful_responses
                    )

                    if not successful_responses:
                        self.logger.debug(
                            "All tracker announces failed (%d trackers tried). "
                            "Continuing with next announce cycle.",
                            len(tracker_urls)
                        )
                        await asyncio.sleep(current_interval)
                        continue

                    # Success - at least one tracker responded
                    self.logger.info(
                        "Periodic announce: %d/%d tracker(s) responded, %d total peer(s)",
                        len(successful_responses),
                        len(tracker_urls),
                        total_peers,
                    )
                    # CRITICAL FIX: Aggregate peers from ALL successful responses, not just the first one
                    # This ensures we connect to peers from all trackers that responded
                    all_peers = []
                    for i, resp in enumerate(successful_responses):
                        if resp and hasattr(resp, "peers") and resp.peers:
                            peer_count = len(resp.peers)
                            all_peers.extend(resp.peers)
                            self.logger.info(
                                "✅ Response %d: extracted %d peer(s) (total aggregated: %d, response type: %s)",
                                i,
                                peer_count,
                                len(all_peers),
                                type(resp).__name__,
                            )
                        else:
                            # CRITICAL FIX: Log at INFO level to diagnose why peers aren't being aggregated
                            self.logger.warning(
                                "⚠️ Response %d: no peers extracted (has_peers_attr=%s, peers=%s, peers_type=%s, response_type=%s)",
                                i,
                                hasattr(resp, "peers") if resp else False,
                                getattr(resp, "peers", None) if resp else None,
                                type(getattr(resp, "peers", None)).__name__ if resp and hasattr(resp, "peers") else "N/A",
                                type(resp).__name__ if resp else "None",
                            )

                    # CRITICAL FIX: Log aggregation results for diagnostics
                    self.logger.info(
                        "🔍 AGGREGATION: Aggregated %d peer(s) from %d successful response(s) (total_peers reported: %d)",
                        len(all_peers),
                        len(successful_responses),
                        total_peers,
                    )

                    # CRITICAL FIX: If aggregation failed but total_peers > 0, log error
                    if len(all_peers) == 0 and total_peers > 0:
                        self.logger.error(
                            "❌ CRITICAL: Aggregation failed! total_peers=%d but all_peers is empty. This means peers are being counted but not extracted. Checking individual responses...",
                            total_peers,
                        )
                        for i, resp in enumerate(successful_responses):
                            if resp:
                                peers_attr = getattr(resp, "peers", None)
                                self.logger.error(
                                    "  Response %d: type=%s, has_peers=%s, peers=%s, peers_len=%s",
                                    i,
                                    type(resp).__name__,
                                    hasattr(resp, "peers"),
                                    peers_attr is not None,
                                    len(peers_attr) if peers_attr else 0,
                                )

                    # Create a synthetic response with all aggregated peers for compatibility
                    # Use the first response as a template (for interval, etc.)
                    response = successful_responses[0] if successful_responses else None
                    if response and all_peers:
                        # CRITICAL FIX: Replace peers with aggregated list from all trackers
                        # Ensure peers attribute exists and is set correctly
                        if not hasattr(response, "peers") or response.peers is None:
                            # Create new TrackerResponse if needed to ensure peers attribute exists
                            from ccbt.discovery.tracker import TrackerResponse
                            response = TrackerResponse(
                                interval=getattr(response, "interval", 1800),
                                peers=all_peers,
                                complete=getattr(response, "complete", getattr(response, "seeders", 0)),
                                incomplete=getattr(response, "incomplete", getattr(response, "leechers", 0)),
                            )
                        else:
                            # Replace existing peers list with aggregated peers
                            response.peers = all_peers
                        self.logger.info(
                            "Aggregated %d peer(s) from %d successful tracker response(s)",
                            len(all_peers),
                            len(successful_responses),
                        )
                        # CRITICAL FIX: Log confirmation that peers are set on response
                        self.logger.info(
                            "✅ AGGREGATION: Response has %d peer(s) after aggregation (response.peers type: %s, has_peers_attr: %s)",
                            len(response.peers) if response.peers else 0,
                            type(response.peers).__name__ if response.peers else "None",
                            hasattr(response, "peers"),
                        )
                    elif response and not all_peers:
                        # CRITICAL FIX: Log when response exists but has no peers
                        # This helps diagnose why peers aren't being connected
                        self.logger.warning(
                            "⚠️ TRACKER RESPONSE: Response received but no peers aggregated (response.peers=%s, successful_responses=%d)",
                            getattr(response, "peers", None),
                            len(successful_responses),
                        )
                        # Check individual responses for peers
                        for i, resp in enumerate(successful_responses):
                            peer_count = len(getattr(resp, "peers", []) or []) if resp else 0
                            self.logger.warning(
                                "  Response %d: peers=%d, type=%s",
                                i,
                                peer_count,
                                type(resp).__name__ if resp else "None",
                        )
                else:
                    # Fallback to single announce if announce_to_multiple not available
                    response = await self.tracker.announce(td, port=announce_port)

                # CRITICAL FIX: Handle None response (UDP tracker client unavailable)
                # When UDP tracker client is not initialized, announce() returns None
                # This is expected behavior - skip peer processing but continue loop
                if response is None:
                    self.logger.debug(
                        "Tracker announce returned None (UDP tracker client may be unavailable). "
                        "Continuing with next announce cycle."
                    )
                    await asyncio.sleep(current_interval)
                    continue

                # CRITICAL FIX: Log response details for diagnostics
                # This helps diagnose why peers aren't being connected
                if response:
                    peer_count = len(getattr(response, "peers", []) or []) if hasattr(response, "peers") else 0
                    self.logger.info(
                        "🔍 ANNOUNCE LOOP: Processing response (peers=%d, response_type=%s, has_peers_attr=%s)",
                        peer_count,
                        type(response).__name__,
                        hasattr(response, "peers"),
                    )

                # Increment announce count for aggressive initial discovery
                self._announce_count += 1

                # CRITICAL FIX: Use more aggressive initial intervals for faster peer discovery
                # Check current active peer count - if low, use even more aggressive intervals
                active_peer_count = 0
                if hasattr(self.download_manager, "peer_manager") and self.download_manager.peer_manager:
                    peer_manager = self.download_manager.peer_manager
                    if hasattr(peer_manager, "get_active_peers"):
                        active_peer_count = len(peer_manager.get_active_peers())

                # Use aggressive initial intervals for first 3 announces
                if self._announce_count <= len(initial_announce_intervals):
                    current_interval = initial_announce_intervals[self._announce_count - 1]
                    # CRITICAL FIX: Only use ULTRA-AGGRESSIVE intervals if:
                    # 1. We've had at least 2 announces (give connections time to establish)
                    # 2. Peer count is still critically low (<5) after connection attempts
                    # This prevents triggering too early before connections have a chance to complete
                    if self._announce_count >= 2 and active_peer_count < 5:
                        # Use shorter intervals: 30s, 60s, 120s instead of 60s, 120s, 300s
                        aggressive_intervals = [30.0, 60.0, 120.0]
                        if self._announce_count <= len(aggressive_intervals):
                            current_interval = aggressive_intervals[self._announce_count - 1]
                            self.logger.info(
                                "🔍 TRACKER DISCOVERY: Using ULTRA-AGGRESSIVE interval: %.1fs (announce #%d, active_peers=%d) for %s",
                                current_interval,
                                self._announce_count,
                                active_peer_count,
                                td.get("name", "unknown"),
                            )
                        else:
                            self.logger.info(
                                "🔍 TRACKER DISCOVERY: Using aggressive initial announce interval: %.1fs (announce #%d/%d, active_peers=%d) for %s",
                                current_interval,
                                self._announce_count,
                                len(initial_announce_intervals),
                                active_peer_count,
                                td.get("name", "unknown"),
                            )
                    else:
                        self.logger.info(
                            "🔍 TRACKER DISCOVERY: Using aggressive initial announce interval: %.1fs (announce #%d/%d) for %s",
                            current_interval,
                            self._announce_count,
                            len(initial_announce_intervals),
                            td.get("name", "unknown"),
                        )
                else:
                    # Calculate adaptive interval based on tracker performance and peer count
                    # Use tracker's suggested interval if available, otherwise use base interval
                    tracker_suggested_interval = response.interval if response else base_announce_interval

                    # Get current peer count for adaptive calculation
                    peer_count = 0
                    if (
                        self.download_manager
                        and hasattr(self.download_manager, "peer_manager")
                        and self.download_manager.peer_manager is not None
                    ):
                        peer_manager = self.download_manager.peer_manager
                        if hasattr(peer_manager, "connections"):
                            peer_count = len([
                                c for c in peer_manager.connections.values()  # type: ignore[attr-defined]
                                if hasattr(c, "is_active") and c.is_active()
                            ])

                    # Get primary tracker URL for adaptive interval calculation
                    primary_tracker_url = tracker_urls[0] if tracker_urls else ""

                    # Calculate adaptive interval
                    if primary_tracker_url:
                        current_interval = self.tracker._calculate_adaptive_interval(
                            primary_tracker_url,
                            float(tracker_suggested_interval),
                            peer_count,
                        )
                    else:
                        current_interval = float(tracker_suggested_interval)

                    # CRITICAL FIX: Make tracker announces more frequent when peer count OR seeder count is low
                    # This ensures we discover more peers and seeders quickly when needed
                    max_peers_per_torrent = self.config.network.max_peers_per_torrent
                    peer_count_ratio = peer_count / max_peers_per_torrent if max_peers_per_torrent > 0 else 0.0

                    # Count seeders from active connections
                    seeder_count = 0
                    if (
                        self.download_manager
                        and hasattr(self.download_manager, "peer_manager")
                        and self.download_manager.peer_manager is not None
                    ):
                        peer_manager = self.download_manager.peer_manager
                        if hasattr(peer_manager, "connections"):
                            for conn in peer_manager.connections.values():
                                # Check if peer is a seeder (100% complete)
                                if (
                                    hasattr(conn, "is_active")
                                    and conn.is_active()
                                    and hasattr(conn, "peer_state")
                                    and hasattr(conn.peer_state, "bitfield")
                                    and (bitfield := conn.peer_state.bitfield)
                                    and self.piece_manager
                                    and hasattr(self.piece_manager, "num_pieces")
                                    and self.piece_manager.num_pieces > 0
                                ):
                                        num_pieces = self.piece_manager.num_pieces
                                        bits_set = sum(1 for i in range(num_pieces) if i < len(bitfield) and bitfield[i])
                                        completion_percent = bits_set / num_pieces
                                        if completion_percent >= 1.0:
                                            seeder_count += 1

                    # CRITICAL FIX: Use ULTRA-AGGRESSIVE intervals when seeder count is low (< 2 seeders)
                    # Seeders are critical for downloads - we need to discover them ASAP
                    if seeder_count < 2:
                        # Very few seeders - announce every 15-20 seconds to discover seeders faster
                        current_interval = min(20.0, current_interval)
                        self.logger.warning(
                            "🌱 SEEDER_DISCOVERY: Very few seeders (%d), using ULTRA-AGGRESSIVE tracker interval: %.1fs to discover seeders",
                            seeder_count,
                            current_interval,
                        )
                    elif peer_count < 5:
                        # CRITICAL FIX: Critically low peer count - use very aggressive intervals
                        # Announce every 20 seconds to discover peers faster
                        current_interval = min(20.0, current_interval)
                        self.logger.info(
                            "🔍 TRACKER_DISCOVERY: Critically low peer count (%d/%d), using ULTRA-AGGRESSIVE interval: %.1fs",
                            peer_count,
                            max_peers_per_torrent,
                            current_interval,
                        )
                    elif peer_count_ratio < 0.3:
                        # Below 30% of max: announce every 30-45 seconds
                        current_interval = min(45.0, current_interval)
                        self.logger.debug(
                            "Tracker announce: Low peer count (%d/%d, %.1f%%), using shorter interval: %.1fs",
                            peer_count,
                            max_peers_per_torrent,
                            peer_count_ratio * 100,
                            current_interval,
                        )
                    elif peer_count_ratio < 0.5:
                        # Below 50% of max: announce every 45-60 seconds
                        current_interval = min(60.0, current_interval)

                # CRITICAL FIX: Connect peers from tracker response IMMEDIATELY - THIS IS THE HIGHEST PRIORITY
                # User requirement: "always connect and request to peers before starting peer discovery at all"
                # This means tracker peers should be connected FIRST, before DHT or any other mechanism
                # Do NOT wait for DHT, do NOT wait for anything - connect immediately
                if (
                    response
                    and hasattr(response, "peers")
                    and response.peers
                    and self.download_manager
                ):
                    # CRITICAL FIX: Log immediately to diagnose connection flow
                    peer_count = len(response.peers) if response.peers else 0
                    self.logger.info(
                        "🚨 IMMEDIATE CONNECTION: Processing %d peer(s) from tracker response for %s (response type: %s, peers type: %s) - CONNECTING IMMEDIATELY BEFORE ANY OTHER DISCOVERY",
                        peer_count,
                        self.info.name,
                        type(response).__name__,
                        type(response.peers).__name__ if response.peers else "None",
                    )

                    # CRITICAL FIX: Set timestamp to block DHT while tracker peers are connecting
                    # This ensures DHT doesn't start until tracker connections have had time to complete
                    import time as time_module
                    connection_start_time = time_module.time()
                    max_wait_time = 10.0  # Maximum 10 seconds wait

                    # If flag is already set, extend it if this started later
                    if self._tracker_peers_connecting_until is None:  # type: ignore[attr-defined]
                        self._tracker_peers_connecting_until = connection_start_time + max_wait_time  # type: ignore[attr-defined]
                    else:
                        current_until = self._tracker_peers_connecting_until  # type: ignore[attr-defined]
                        new_until = connection_start_time + max_wait_time
                        if new_until > current_until:
                            self._tracker_peers_connecting_until = new_until  # type: ignore[attr-defined]

                    # CRITICAL FIX: Check if peer manager exists (may have been initialized early)
                    has_peer_manager = (
                        hasattr(self.download_manager, "peer_manager")
                        and self.download_manager.peer_manager is not None
                    )

                    # CRITICAL FIX: Log peer manager status for diagnostics
                    self.logger.info(
                        "🔍 TRACKER PEER CONNECTION: response.peers=%d, download_manager=%s, has_peer_manager=%s, response_type=%s",
                        len(response.peers) if response.peers else 0,
                        self.download_manager is not None,
                        has_peer_manager,
                        type(response).__name__,
                    )

                    # CRITICAL FIX: If peer manager doesn't exist, wait with retry logic, then queue peers
                    # CRITICAL: Do NOT skip connection - wait longer and ensure peer_manager is ready
                    if not has_peer_manager:
                        # CRITICAL FIX: Wait longer for peer_manager (up to 5 seconds) since this is critical
                        self.logger.warning(
                            "⚠️ TRACKER PEER CONNECTION: peer_manager not ready for %s, waiting up to 5 seconds (CRITICAL: %d peers waiting)...",
                            self.info.name,
                            len(response.peers) if response.peers else 0,
                        )
                        for retry in range(10):  # 10 retries * 0.5s = 5 seconds total (increased from 2s)
                            await asyncio.sleep(0.5)
                            has_peer_manager = (
                                hasattr(self.download_manager, "peer_manager")
                                and self.download_manager.peer_manager is not None
                            )
                            if has_peer_manager:
                                self.logger.info(
                                    "✅ TRACKER PEER CONNECTION: peer_manager ready for %s after %.1fs",
                                    self.info.name,
                                    (retry + 1) * 0.5,
                                )
                                break

                        # If still not ready after retries, queue peers AND log error
                        if not has_peer_manager:
                            self.logger.error(
                                "❌ CRITICAL: peer_manager still not ready for %s after 5 seconds! This should not happen. Queuing %d peers for later connection",
                                self.info.name,
                                len(response.peers) if response.peers else 0,
                            )
                            # Build peer list for queuing
                            peer_list = []
                            for p in response.peers if (response and hasattr(response, "peers") and response.peers) else []:
                                try:
                                    if hasattr(p, "ip") and hasattr(p, "port"):
                                        peer_list.append(
                                            {
                                                "ip": p.ip,
                                                "port": p.port,
                                                "peer_source": "tracker",
                                                "ssl_capable": getattr(p, "ssl_capable", None),
                                            }
                                        )
                                    elif isinstance(p, dict) and "ip" in p and "port" in p:
                                        peer_list.append(
                                            {
                                                "ip": str(p["ip"]),
                                                "port": int(p["port"]),
                                                "peer_source": "tracker",
                                                "ssl_capable": p.get("ssl_capable"),
                                            }
                                        )
                                except (ValueError, TypeError, KeyError):
                                    pass

                            # Queue peers for later connection
                            if peer_list:
                                import time as time_module
                                current_time = time_module.time()
                                for peer in peer_list:
                                    peer["_queued_at"] = current_time

                                if not hasattr(self, "_queued_peers"):
                                    self._queued_peers = []  # type: ignore[attr-defined]
                                self._queued_peers.extend(peer_list)  # type: ignore[attr-defined]
                                self.logger.info(
                                    "📦 TRACKER PEER CONNECTION: Queued %d peer(s) for later connection (total queued: %d)",
                                    len(peer_list),
                                    len(self._queued_peers),  # type: ignore[attr-defined]
                                )
                            # CRITICAL FIX: Do NOT continue - try to connect anyway if peer_manager becomes available
                            # The check below will handle the case where peer_manager is still None

                # CRITICAL FIX: If peer manager exists (or became ready after retry), connect peers directly
                if (
                    response.peers
                    and self.download_manager
                    and hasattr(self.download_manager, "peer_manager")
                    and self.download_manager.peer_manager is not None
                ):
                    # Convert tracker response peers to peer_list format expected by connect_to_peers()
                    peer_list = []
                    for p in response.peers:
                        try:
                            if hasattr(p, "ip") and hasattr(p, "port"):
                                peer_list.append(
                                    {
                                        "ip": p.ip,
                                        "port": p.port,
                                        "peer_source": getattr(p, "peer_source", "tracker"),
                                        "ssl_capable": getattr(p, "ssl_capable", None),
                                    }
                                )
                            elif isinstance(p, dict) and "ip" in p and "port" in p:
                                peer_list.append(
                                    {
                                        "ip": str(p["ip"]),
                                        "port": int(p["port"]),
                                        "peer_source": p.get("peer_source", "tracker"),
                                        "ssl_capable": p.get("ssl_capable"),
                                    }
                                )
                            else:
                                self.logger.debug(
                                    "Skipping invalid peer from tracker response: %s (type: %s)",
                                    p,
                                    type(p).__name__,
                                )
                        except (ValueError, TypeError, KeyError) as peer_error:
                            self.logger.debug(
                                "Error processing peer from tracker: %s (error: %s)",
                                p,
                                peer_error,
                            )

                    if peer_list:
                        # CRITICAL FIX: Deduplicate peers before connecting
                        # Some trackers may return duplicate peers
                        seen_peers = set()
                        unique_peer_list = []
                        for peer in peer_list:
                            peer_key = (peer.get("ip"), peer.get("port"))
                            if peer_key not in seen_peers:
                                seen_peers.add(peer_key)
                                unique_peer_list.append(peer)

                        if len(unique_peer_list) < len(peer_list):
                            self.logger.debug(
                                "Deduplicated %d duplicate peer(s) from tracker response (%d -> %d unique)",
                                len(peer_list) - len(unique_peer_list),
                                len(peer_list),
                                len(unique_peer_list),
                            )

                        self.logger.info(
                            "🔗 TRACKER PEER CONNECTION: Connecting %d unique peer(s) from tracker to peer manager for %s (response had %d total peers)",
                            len(unique_peer_list),
                            self.info.name,
                            len(response.peers) if response.peers else 0,
                        )
                        try:
                            # Connect peers to existing peer manager
                            # Type checker can't infer that peer_manager is not None after checks above
                            await self.download_manager.peer_manager.connect_to_peers(  # type: ignore[union-attr]
                                unique_peer_list
                            )
                            self.logger.info(
                                "✅ TRACKER PEER CONNECTION: Successfully initiated connection to %d peer(s) from tracker for %s (connections will continue in background)",
                                len(unique_peer_list),
                                self.info.name,
                            )

                            # CRITICAL FIX: Wait until the timestamp expires (or shorter if connections complete)
                            # This prevents DHT from starting too early while allowing multiple callbacks
                            wait_until = self._tracker_peers_connecting_until  # type: ignore[attr-defined]
                            if wait_until:
                                wait_time = max(0.0, wait_until - time_module.time())
                                if wait_time > 0:
                                    self.logger.info(
                                        "⏸️ TRACKER PEER CONNECTION: Keeping DHT blocked for %.1fs to allow tracker connections to complete...",
                                        wait_time,
                                    )
                                    await asyncio.sleep(wait_time)

                            # Clear flag only if this callback's time has expired
                            if (
                                self._tracker_peers_connecting_until  # type: ignore[attr-defined]
                                and time_module.time() >= self._tracker_peers_connecting_until  # type: ignore[attr-defined]
                            ):
                                self._tracker_peers_connecting_until = None  # type: ignore[attr-defined]
                                self.logger.info(
                                    "✅ TRACKER PEER CONNECTION: Wait period expired, DHT can now start if needed"
                                )

                            # CRITICAL FIX: Also feed tracker-discovered peers into PEX system
                            # This allows these peers to be shared with other connected peers via PEX
                            if self.pex_manager and hasattr(self.pex_manager, "known_peers"):
                                try:
                                    # Add tracker peers to PEX known_peers for sharing
                                    added_count = 0
                                    for peer in unique_peer_list:
                                        try:
                                            ip = peer.get("ip")
                                            port = peer.get("port")
                                            if ip and port:
                                                # Create PEX peer entry
                                                peer_key = f"{ip}:{port}"
                                                if peer_key not in self.pex_manager.known_peers:
                                                    import time

                                                    from ccbt.discovery.pex import (
                                                        PexPeer,
                                                    )
                                                    pex_peer = PexPeer(
                                                        ip=ip,
                                                        port=int(port),
                                                        added_time=time.time(),
                                                        source="tracker"
                                                    )
                                                    self.pex_manager.known_peers[peer_key] = pex_peer
                                                    added_count += 1
                                        except (ValueError, TypeError):
                                            continue

                                    if added_count > 0:
                                        self.logger.debug(
                                            "Added %d tracker peer(s) to PEX system for sharing with connected peers",
                                            added_count
                                        )
                                except Exception as pex_error:
                                    self.logger.debug("Failed to add tracker peers to PEX: %s", pex_error)
                            self.logger.info(
                                "Successfully initiated connection to %d peer(s) from tracker for %s",
                                len(unique_peer_list),
                                self.info.name,
                            )
                            # CRITICAL FIX: Verify connections after a delay
                            await asyncio.sleep(
                                1.0
                            )  # Give connections time to establish
                            peer_manager = self.download_manager.peer_manager
                            if peer_manager and hasattr(
                                peer_manager, "connections"
                            ):
                                active_count = len(
                                    [
                                        c
                                        # Type checker can't infer dict-like interface from dynamic attributes
                                        for c in peer_manager.connections.values()  # type: ignore[attr-defined]
                                        if c.is_active()
                                    ]
                                )
                                self.logger.info(
                                    "Tracker peer connection status for %s: %d active connections after adding %d peers (success rate: %.1f%%)",
                                    self.info.name,
                                    active_count,
                                    len(unique_peer_list),
                                    (active_count / len(unique_peer_list) * 100) if unique_peer_list else 0.0,
                                )
                        except Exception as e:
                            self.logger.warning(
                                "Failed to connect %d peers from tracker for %s: %s",
                                len(peer_list),
                                self.info.name,
                                e,
                                exc_info=True,
                            )

                # Wait for next announce using adaptive interval
                await asyncio.sleep(current_interval)

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
            # CRITICAL FIX: Validate tracker URLs - must start with http://, https://, or udp://
            # This ensures only valid tracker URLs are used for announcements
            if not v or not v.startswith(("http://", "https://", "udp://")):
                continue
            if v not in seen:
                seen.add(v)
                unique.append(v)

        return unique

    async def add_tracker(self, tracker_url: str) -> bool:
        """Add a tracker URL to this torrent session.

        Args:
            tracker_url: Tracker URL to add (must start with http://, https://, or udp://)

        Returns:
            True if added, False if invalid or already exists

        """
        try:
            # Validate URL
            if not tracker_url or not tracker_url.startswith(("http://", "https://", "udp://")):
                self.logger.warning("Invalid tracker URL: %s", tracker_url)
                return False

            tracker_url = tracker_url.strip()

            # Get current trackers
            current_trackers = self._collect_trackers(self._normalized_td)

            # Check if already exists
            if tracker_url in current_trackers:
                self.logger.debug("Tracker already exists: %s", tracker_url)
                return True

            # Add to torrent data
            if "announce_list" not in self._normalized_td:
                self._normalized_td["announce_list"] = []

            # Add as a new tier
            if isinstance(self._normalized_td["announce_list"], list):
                self._normalized_td["announce_list"].append([tracker_url])

            # Create tracker session if tracker client is started
            if (
                self.tracker
                and hasattr(self.tracker, "sessions")
                and tracker_url not in self.tracker.sessions
            ):
                    from ccbt.discovery.tracker import TrackerSession

                    self.tracker.sessions[tracker_url] = TrackerSession(url=tracker_url)

            self.logger.info("Added tracker %s to torrent %s", tracker_url, self.info.name)
            return True
        except Exception:
            self.logger.exception("Failed to add tracker %s", tracker_url)
            return False

    async def remove_tracker(self, tracker_url: str) -> bool:
        """Remove a tracker URL from this torrent session.

        Args:
            tracker_url: Tracker URL to remove

        Returns:
            True if removed, False if not found

        """
        try:
            tracker_url = tracker_url.strip()

            # Get current trackers
            current_trackers = self._collect_trackers(self._normalized_td)

            # Check if exists
            if tracker_url not in current_trackers:
                self.logger.debug("Tracker not found: %s", tracker_url)
                return False

            # Remove from announce_list
            if "announce_list" in self._normalized_td and isinstance(
                self._normalized_td["announce_list"], list
            ):
                # Remove from all tiers
                new_announce_list = []
                for tier in self._normalized_td["announce_list"]:
                    if isinstance(tier, list):
                        filtered_tier = [u for u in tier if u != tracker_url]
                        if filtered_tier:  # Only keep non-empty tiers
                            new_announce_list.append(filtered_tier)
                    elif tier != tracker_url:
                        new_announce_list.append(tier)
                self._normalized_td["announce_list"] = new_announce_list

            # Remove from single announce if it matches
            if self._normalized_td.get("announce") == tracker_url:
                del self._normalized_td["announce"]

            # Remove from trackers list if it exists
            if "trackers" in self._normalized_td and isinstance(
                self._normalized_td["trackers"], list
            ):
                self._normalized_td["trackers"] = [
                    u for u in self._normalized_td["trackers"] if u != tracker_url
                ]

            # Remove tracker session if exists
            if self.tracker and hasattr(self.tracker, "sessions"):
                self.tracker.sessions.pop(tracker_url, None)

            self.logger.info("Removed tracker %s from torrent %s", tracker_url, self.info.name)
            return True
        except Exception:
            self.logger.exception("Failed to remove tracker %s", tracker_url)
            return False

    async def _status_loop(self) -> None:
        """Background task for status monitoring."""
        while not self._stop_event.is_set():
            try:
                # Get current status
                status = await self.get_status()

                # Cache status for synchronous property access
                self._cached_status = status

                # CRITICAL FIX: Safety check - if download is complete but files aren't finalized
                # This catches cases where completion was detected but finalization failed or was missed
                if (
                    self.piece_manager
                    and len(self.piece_manager.verified_pieces) == self.piece_manager.num_pieces
                    and hasattr(self.download_manager, "file_assembler")
                    and self.download_manager.file_assembler is not None
                ):
                    file_assembler = self.download_manager.file_assembler
                    written_count = len(file_assembler.written_pieces)
                    total_pieces = file_assembler.num_pieces

                    # If all pieces are verified and written, but status is still downloading, finalize
                    if (
                        written_count == total_pieces
                        and self.info.status not in {"seeding", "completed"}
                    ):
                        self.logger.info(
                            "Safety check: All pieces verified and written, but status is '%s'. "
                            "Finalizing files now.",
                            self.info.status,
                        )
                        try:
                            await file_assembler.finalize_files()
                            self.info.status = "seeding"
                            self.logger.info(
                                "Files finalized via safety check for: %s",
                                self.info.name,
                            )
                        except Exception as e:
                            self.logger.warning(
                                "Safety check finalization failed: %s",
                                e,
                                exc_info=True,
                            )

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

        # CRITICAL FIX: Create file_assembler if it doesn't exist
        # This handles the case where download completes before any pieces were written
        if not hasattr(self.download_manager, "file_assembler") or self.download_manager.file_assembler is None:
            self.logger.warning(
                "Download manager has no file_assembler for: %s. Creating it now to finalize files.",
                self.info.name,
            )
            # Create file assembler now
            from pathlib import Path

            from ccbt.storage.file_assembler import AsyncFileAssembler

            output_dir_path = Path(self.output_dir)
            if not output_dir_path.exists():
                output_dir_path.mkdir(parents=True, exist_ok=True)
                self.logger.info("Created output directory: %s", output_dir_path)

            self.download_manager.file_assembler = AsyncFileAssembler(
                self.torrent_data,
                str(self.output_dir),
            )
            # Initialize file assembler
            await self.download_manager.file_assembler.__aenter__()
            self.logger.info(
                "Created file assembler for completed download: %s (num_pieces=%d)",
                self.info.name,
                self.download_manager.file_assembler.num_pieces,
            )

            # CRITICAL FIX: Ensure file_segments are built
            if not self.download_manager.file_assembler.file_segments:
                self.logger.info(
                    "File segments empty, rebuilding from metadata for: %s",
                    self.info.name,
                )
                # Try to update from metadata
                if hasattr(self.download_manager.file_assembler, "update_from_metadata"):
                    self.download_manager.file_assembler.update_from_metadata(self.torrent_data)
                # If still empty, rebuild segments
                if not self.download_manager.file_assembler.file_segments:
                    self.logger.warning(
                        "File segments still empty after rebuild. Files may not be written correctly for: %s",
                        self.info.name,
                    )

            # CRITICAL FIX: Write all verified pieces to disk now
            # Since download is complete, all pieces should be verified
            if self.piece_manager:
                written_count = 0
                for piece_index in range(self.piece_manager.num_pieces):
                    piece = self.piece_manager.pieces[piece_index]
                    if (
                        piece.state.value == "verified"
                        and piece.is_complete()
                        and piece_index not in self.download_manager.file_assembler.written_pieces
                    ):
                            try:
                                piece_data = piece.get_data()
                                if piece_data:
                                    self.logger.info(
                                        "Writing verified piece %d to disk during completion (piece %d/%d)",
                                        piece_index,
                                        written_count + 1,
                                        self.piece_manager.num_pieces,
                                    )
                                    await self.download_manager.file_assembler.write_piece_to_file(
                                        piece_index,
                                        piece_data,
                                    )
                                    written_count += 1
                            except Exception as e:
                                self.logger.warning(
                                    "Failed to write piece %d during completion: %s",
                                    piece_index,
                                    e,
                                )

                self.logger.info(
                    "Wrote %d verified pieces to disk during completion for: %s",
                    written_count,
                    self.info.name,
                )

        # CRITICAL FIX: Finalize files after all pieces are written to disk
        # This ensures files are properly assembled and made accessible
        if (
            hasattr(self.download_manager, "file_assembler")
            and self.download_manager.file_assembler is not None
        ):
            file_assembler = self.download_manager.file_assembler
            try:
                # CRITICAL FIX: Wait for all verified pieces to be written to disk
                # This handles the race condition where completion is detected before all writes complete
                total_pieces = file_assembler.num_pieces
                max_wait_time = 30.0  # Maximum 30 seconds to wait for writes
                wait_interval = 0.1  # Check every 100ms
                elapsed_time = 0.0

                while elapsed_time < max_wait_time:
                    written_count = len(file_assembler.written_pieces)
                    verified_count = len(self.piece_manager.verified_pieces) if self.piece_manager else 0

                    self.logger.debug(
                        "Waiting for pieces to be written: %d/%d written, %d/%d verified (elapsed: %.1fs)",
                        written_count,
                        total_pieces,
                        verified_count,
                        total_pieces,
                        elapsed_time,
                    )

                    if written_count == total_pieces:
                        self.logger.info(
                            "All %d pieces written to disk, finalizing files for: %s",
                            total_pieces,
                            self.info.name,
                        )
                        # CRITICAL FIX: Wait a moment for any pending async writes to complete
                        await asyncio.sleep(0.5)  # Give disk I/O time to complete
                        await file_assembler.finalize_files()
                        self.logger.info(
                            "Files finalized successfully for completed download: %s (files should now be visible)",
                            self.info.name,
                        )
                        break

                    # If we have fewer written pieces than verified, pieces are still being written
                    if written_count < verified_count:
                        await asyncio.sleep(wait_interval)
                        elapsed_time += wait_interval
                        continue

                    # If written == verified but both < total, something is wrong
                    if written_count == verified_count and written_count < total_pieces:
                        self.logger.warning(
                            "Piece count mismatch: %d written, %d verified, %d total. "
                            "Some pieces may not have been verified yet.",
                            written_count,
                            verified_count,
                            total_pieces,
                        )
                        await asyncio.sleep(wait_interval)
                        elapsed_time += wait_interval
                        continue

                    # Fallback: if we've waited long enough, try finalizing anyway
                    if elapsed_time >= max_wait_time:
                        self.logger.warning(
                            "Timeout waiting for all pieces to be written (%d/%d written, %d/%d verified). "
                            "Attempting finalization anyway for: %s",
                            written_count,
                            total_pieces,
                            verified_count,
                            total_pieces,
                            self.info.name,
                        )
                        # Try to write any missing pieces that are verified but not written
                        if self.piece_manager:
                            for piece_index in range(total_pieces):
                                if piece_index not in file_assembler.written_pieces:
                                    piece = self.piece_manager.pieces[piece_index]
                                    if piece.state.value == "verified" and piece.is_complete():
                                        try:
                                            piece_data = piece.get_data()
                                            if piece_data:
                                                self.logger.info(
                                                    "Writing missing piece %d to disk during finalization",
                                                    piece_index,
                                                )
                                                await file_assembler.write_piece_to_file(
                                                    piece_index,
                                                    piece_data,
                                                )
                                        except Exception as e:
                                            self.logger.warning(
                                                "Failed to write missing piece %d during finalization: %s",
                                                piece_index,
                                                e,
                                            )

                        # CRITICAL FIX: Wait a moment for async writes to complete before finalizing
                        await asyncio.sleep(0.5)
                        # Finalize with whatever we have
                        await file_assembler.finalize_files()
                        self.logger.info(
                            "Files finalized (may be incomplete: %d/%d pieces written) - files should now be visible",
                            len(file_assembler.written_pieces),
                            total_pieces,
                        )
                        break
                else:
                    # Loop completed without breaking (shouldn't happen, but defensive)
                    self.logger.error(
                        "Failed to finalize files: timeout waiting for pieces to be written for: %s",
                        self.info.name,
                    )
            except Exception:
                self.logger.exception(
                    "Failed to finalize files after completion for %s",
                    self.info.name,
                )

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

        # CRITICAL FIX: Notify session manager of completion
        # This ensures WebSocket events are emitted and callbacks are triggered
        if self.session_manager and self.session_manager.on_torrent_complete:
            try:
                await self.session_manager.on_torrent_complete(
                    self.info.info_hash,
                    self.info.name,
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to notify session manager of completion: %s",
                    e,
                    exc_info=True,
                )

        # Emit TORRENT_COMPLETED event
        try:
            import time

            from ccbt.utils.events import Event, emit_event

            download_time = time.time() - (self.start_time if hasattr(self, "start_time") else time.time())
            total_size = self.info.total_size if hasattr(self.info, "total_size") else 0
            downloaded = self.info.downloaded if hasattr(self.info, "downloaded") else 0
            average_speed = downloaded / download_time if download_time > 0 else 0.0

            await emit_event(
                Event(
                    event_type="torrent_completed",
                    data={
                        "info_hash": self.info.info_hash.hex(),
                        "name": self.info.name,
                        "total_size": total_size,
                        "download_time": download_time,
                        "average_speed": average_speed,
                    },
                )
            )
        except Exception as e:
            self.logger.debug("Failed to emit TORRENT_COMPLETED event: %s", e)

        # Emit SEEDING_STARTED event if torrent should seed (not removed)
        if hasattr(self, "state") and self.state != "removed":
            try:
                from ccbt.utils.events import Event, emit_event

                await emit_event(
                    Event(
                        event_type="seeding_started",
                        data={
                            "info_hash": self.info.info_hash.hex(),
                            "name": self.info.name,
                            "upload_rate": 0.0,  # Will be updated by periodic stats
                            "connected_leechers": 0,
                            "total_uploaded": 0,
                            "ratio": 0.0,
                        },
                    )
                )
            except Exception as e:
                self.logger.debug("Failed to emit SEEDING_STARTED event: %s", e)

        if self.on_complete:
            await self.on_complete()

    async def _on_piece_verified(self, piece_index: int) -> None:
        """Handle piece verification."""
        self.logger.debug(
            "_on_piece_verified called for piece %d (torrent: %s)",
            piece_index,
            self.info.name,
        )

        # CRITICAL FIX: Broadcast HAVE message to all connected peers
        # This is important for peer relationships - some clients disconnect if we don't send HAVE messages
        # Per BEP 3, we should send HAVE messages when we complete a piece
        if self.download_manager and self.download_manager.peer_manager:
            try:
                await self.download_manager.peer_manager.broadcast_have(piece_index)
            except Exception as e:
                self.logger.debug(
                    "Failed to broadcast HAVE message for piece %d: %s",
                    piece_index,
                    e,
                )

        # CRITICAL FIX: Write verified piece to disk using file assembler
        if self.piece_manager and 0 <= piece_index < len(self.piece_manager.pieces):
            from ccbt.piece.async_piece_manager import PieceState as PieceStateEnum
            piece = self.piece_manager.pieces[piece_index]
            # Check if piece is verified (state is VERIFIED enum value)
            if piece.state == PieceStateEnum.VERIFIED and piece.is_complete():
                try:
                    # Get piece data
                    piece_data = piece.get_data()
                    if piece_data:
                        # CRITICAL FIX: Check if files are available before creating file assembler
                        # For magnet links, metadata (including files) may not be available yet
                        files_available = False
                        if isinstance(self.torrent_data, dict):
                            # Check if files are directly in torrent_data
                            files = self.torrent_data.get("files", [])
                            if not files:
                                # Check if files are in file_info
                                file_info = self.torrent_data.get("file_info", {})
                                if isinstance(file_info, dict):
                                    if "files" in file_info:
                                        files = file_info["files"]
                                    elif "type" in file_info and file_info["type"] == "single":
                                        # Single-file torrent
                                        files = [file_info]
                            files_available = bool(files)
                        elif hasattr(self.torrent_data, "files"):
                            files_available = bool(self.torrent_data.files)

                        if not files_available:
                            self.logger.debug(
                                "Skipping write for piece %d: files not available yet (metadata may not be fetched)",
                                piece_index,
                            )
                            return  # Skip writing until metadata is available

                        # Create file assembler if it doesn't exist
                        if not hasattr(self.download_manager, "file_assembler") or self.download_manager.file_assembler is None:
                            # CRITICAL FIX: Ensure output directory exists before creating file assembler
                            output_dir_path = Path(self.output_dir)
                            if not output_dir_path.exists():
                                output_dir_path.mkdir(parents=True, exist_ok=True)
                                self.logger.info(
                                    "Created output directory: %s", output_dir_path
                                )

                            from ccbt.storage.file_assembler import AsyncFileAssembler
                            self.download_manager.file_assembler = AsyncFileAssembler(
                                self.torrent_data,
                                str(self.output_dir),
                            )
                            # Initialize file assembler
                            await self.download_manager.file_assembler.__aenter__()
                            self.logger.info(
                                "Created file assembler for torrent: %s (num_pieces=%d)",
                                self.info.name,
                                self.download_manager.file_assembler.num_pieces,
                            )

                        # CRITICAL FIX: Check if file segments are built (may be empty if metadata wasn't available when created)
                        if not self.download_manager.file_assembler.file_segments:
                            # Rebuild file segments in case metadata became available after file assembler was created
                            self.logger.info(
                                "Rebuilding file segments for piece %d (file_segments was empty)",
                                piece_index,
                            )
                            self.download_manager.file_assembler.update_from_metadata(self.torrent_data)

                        # CRITICAL FIX: Ensure file segments exist before writing
                        if not self.download_manager.file_assembler.file_segments:
                            self.logger.error(
                                "Cannot write piece %d: file segments are still empty after rebuild. "
                                "Metadata may be incomplete.",
                                piece_index,
                            )
                            return

                        # Write piece to disk
                        await self.download_manager.file_assembler.write_piece_to_file(
                            piece_index,
                            piece_data,
                        )
                        self.logger.info(
                            "Wrote verified piece %d to disk (%d bytes, written_pieces: %d/%d)",
                            piece_index,
                            len(piece_data),
                            len(self.download_manager.file_assembler.written_pieces),
                            self.download_manager.file_assembler.num_pieces,
                        )
                    else:
                        self.logger.warning(
                            "Piece %d is verified but has no data to write",
                            piece_index,
                        )
                except Exception:
                    self.logger.exception(
                        "Failed to write verified piece %d to disk",
                        piece_index,
                    )

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
        status = await self.download_manager.get_status()
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

            # Restore per-torrent configuration options if they exist
            if checkpoint.per_torrent_options is not None and checkpoint.per_torrent_options:
                self.options.update(checkpoint.per_torrent_options)
                self.logger.info(
                    "Restored per-torrent options from checkpoint: %s",
                    list(checkpoint.per_torrent_options.keys()),
                )
                # Apply the restored options
                self._apply_per_torrent_options()

            # Restore per-torrent rate limits if they exist
            if checkpoint.rate_limits is not None and self.session_manager:
                down_kib = checkpoint.rate_limits.get("down_kib", 0)
                up_kib = checkpoint.rate_limits.get("up_kib", 0)
                info_hash_hex = checkpoint.info_hash.hex()
                await self.session_manager.set_rate_limits(
                    info_hash_hex, down_kib, up_kib
                )
                self.logger.info(
                    "Restored per-torrent rate limits from checkpoint: down=%d KiB/s, up=%d KiB/s",
                    down_kib,
                    up_kib,
                )

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

    async def _seeding_stats_loop(self) -> None:
        """Background task for periodic seeding stats updates."""
        stats_interval = 5.0  # Emit stats every 5 seconds

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(stats_interval)

                # Only emit if torrent is still completed (seeding) and not paused
                if hasattr(self, "info") and self.info.status == "seeding":
                    try:
                        from ccbt.utils.events import Event, emit_event

                        # Get current stats
                        upload_rate = self.info.upload_rate if hasattr(self.info, "upload_rate") else 0.0
                        uploaded = self.info.uploaded if hasattr(self.info, "uploaded") else 0
                        downloaded = self.info.downloaded if hasattr(self.info, "downloaded") else 1  # Avoid division by zero
                        ratio = uploaded / downloaded if downloaded > 0 else 0.0

                        # Count connected leechers (peers that are downloading from us)
                        connected_leechers = 0
                        if (
                            hasattr(self, "peer_manager")
                            and self.peer_manager
                            and hasattr(self.peer_manager, "connections")
                        ):
                                for conn in self.peer_manager.connections.values():
                                    if hasattr(conn, "peer_choking") and not conn.peer_choking:
                                        # Peer is not choking us, they might be downloading
                                        connected_leechers += 1

                        await emit_event(
                            Event(
                                event_type="seeding_stats_updated",
                                data={
                                    "info_hash": self.info.info_hash.hex(),
                                    "name": self.info.name,
                                    "upload_rate": upload_rate,
                                    "connected_leechers": connected_leechers,
                                    "total_uploaded": uploaded,
                                    "ratio": ratio,
                                },
                            )
                        )
                    except Exception as e:
                        self.logger.debug("Failed to emit SEEDING_STATS_UPDATED event: %s", e)
                else:
                    # Torrent is no longer seeding, stop the task
                    break

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in seeding stats loop")

    async def delete_checkpoint(self) -> bool:
        """Delete checkpoint files for this torrent."""
        try:
            return await self.checkpoint_manager.delete_checkpoint(self.info.info_hash)
        except Exception:
            self.logger.exception("Failed to delete checkpoint")
            return False

    @property
    def downloaded_bytes(self) -> int:
        """Get downloaded bytes from cached status."""
        return self._cached_status.get("downloaded", 0)

    @property
    def uploaded_bytes(self) -> int:
        """Get uploaded bytes from cached status."""
        return self._cached_status.get("uploaded", 0)

    @property
    def left_bytes(self) -> int:
        """Get remaining bytes from cached status."""
        return self._cached_status.get("left", 0)

    @property
    def peers(self) -> dict[str, Any]:
        """Get connected peers from cached status."""
        peers_count = self._cached_status.get("connected_peers", 0)
        return {"count": peers_count}

    @property
    def download_rate(self) -> float:
        """Get download rate from cached status."""
        return self._cached_status.get("download_rate", 0.0)

    @property
    def upload_rate(self) -> float:
        """Get upload rate from cached status."""
        return self._cached_status.get("upload_rate", 0.0)

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
        self._metrics_restart_task: asyncio.Task | None = None
        self._metrics_sample_interval = 1.0
        self._metrics_emit_interval = 10.0
        self._last_metrics_emit = 0.0
        self._rate_history: deque[dict[str, float]] = deque(maxlen=600)
        self._metrics_restart_backoff = 1.0
        self._metrics_shutdown = False
        self._metrics_heartbeat_counter = 0
        self._metrics_heartbeat_interval = 5

        # Callbacks
        self.on_torrent_added: Callable[[bytes, str], None] | None = None
        self.on_torrent_removed: Callable[[bytes], None] | None = None
        self.on_torrent_complete: Callable[[bytes, str], None] | None = None
        # XET folder callbacks
        self.on_xet_folder_added: Callable[[str, str], None] | None = None
        self.on_xet_folder_removed: Callable[[str], None] | None = None

        self.logger = logging.getLogger(__name__)

        # Simple per-torrent rate limits (not enforced yet, stored for reporting)
        self._per_torrent_limits: dict[bytes, dict[str, int]] = {}

        # Initialize global rate limits from config
        if self.config.limits.global_down_kib > 0 or self.config.limits.global_up_kib > 0:
            self.logger.debug(
                "Initialized global rate limits from config: down=%d KiB/s, up=%d KiB/s",
                self.config.limits.global_down_kib,
                self.config.limits.global_up_kib,
            )

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
        # Queue manager for priority-based torrent scheduling
        self.queue_manager: Any | None = None

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

        # XET folder synchronization components
        self._xet_sync_manager: Any | None = None
        self._xet_realtime_sync: Any | None = None
        # XET folder sessions (keyed by info_hash or folder_path)
        self.xet_folders: dict[str, Any] = {}  # folder_path or info_hash -> XetFolder
        self._xet_folders_lock = asyncio.Lock()

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
        # CRITICAL: Start NAT manager first (UPnP/NAT-PMP discovery and port mapping)
        # This must happen before services that need incoming connections
        try:
            self.nat_manager = self._make_nat_manager()
            if self.nat_manager:
                await self.nat_manager.start()
                # Map all required ports (TCP, UDP, DHT, etc.)
                if self.config.nat.auto_map_ports:
                    await self.nat_manager.map_listen_ports()
                    # Wait for port mappings to complete (with timeout)
                    await self.nat_manager.wait_for_mapping(timeout=60.0)
                    self.logger.info("NAT manager initialized and ports mapped successfully")
                else:
                    self.logger.info("NAT manager initialized (auto_map_ports disabled)")
                # Emit COMPONENT_STARTED event
                try:
                    from ccbt.utils.events import Event, emit_event
                    await emit_event(
                        Event(
                            event_type="component_started",
                            data={
                                "component_name": "nat_manager",
                                "status": "running",
                            },
                        )
                    )
                except Exception as e:
                    self.logger.debug("Failed to emit COMPONENT_STARTED event for NAT: %s", e)
            else:
                self.logger.warning("Failed to create NAT manager")
        except Exception:
            # Best-effort: log and continue
            self.logger.warning(
                "NAT manager initialization failed. Port mapping may not work, which could prevent incoming connections.",
                exc_info=True,
            )

        # OPTIMIZATION: Start network components in parallel (TCP server, UDP tracker, DHT)
        # These components don't need port mapping to complete - they only need external port
        # when announcing (which happens later). Starting them in parallel saves 2-5 seconds.
        network_tasks = []

        # TCP server for incoming peer connections
        async def start_tcp_server() -> None:
            try:
                if self.config.network.enable_tcp:
                    self.tcp_server = self._make_tcp_server()
                    if self.tcp_server:
                        await self.tcp_server.start()
                        self.logger.info("TCP server started successfully")
                        # Emit COMPONENT_STARTED event
                        try:
                            from ccbt.utils.events import Event, emit_event
                            await emit_event(
                                Event(
                                    event_type="component_started",
                                    data={
                                        "component_name": "tcp_server",
                                        "status": "running",
                                    },
                                )
                            )
                        except Exception as e:
                            self.logger.debug("Failed to emit COMPONENT_STARTED event for TCP server: %s", e)
                    else:
                        self.logger.warning("Failed to create TCP server")
                else:
                    self.logger.debug("TCP transport disabled, skipping TCP server startup")
            except Exception:
                # Best-effort: log and continue
                self.logger.warning(
                    "TCP server initialization failed. Incoming peer connections may not work.",
                    exc_info=True,
                )

        network_tasks.append(start_tcp_server())

        # UDP tracker client initialization
        async def start_udp_tracker_client() -> None:
            try:
                from ccbt.discovery.tracker_udp_client import AsyncUDPTrackerClient

                self.udp_tracker_client = AsyncUDPTrackerClient()
                await self.udp_tracker_client.start()
                self.logger.info("UDP tracker client initialized successfully")
            except Exception:
                # Best-effort: log and continue
                self.logger.warning(
                    "UDP tracker client initialization failed. UDP tracker operations may not work.",
                    exc_info=True,
                )

        network_tasks.append(start_udp_tracker_client())

        # DHT client initialization
        async def start_dht_client() -> None:
            if self.config.discovery.enable_dht:
                try:
                    dht_port = getattr(self.config.discovery, "dht_port", 64120)
                    bind_ip = self.config.network.listen_interface or "0.0.0.0"  # nosec B104
                    self.dht_client = self._make_dht_client(bind_ip=bind_ip, bind_port=dht_port)
                    if self.dht_client:
                        await self.dht_client.start()
                        self.logger.info("DHT client initialized successfully (port: %d)", dht_port)
                        # Emit COMPONENT_STARTED event
                        try:
                            from ccbt.utils.events import Event, emit_event
                            await emit_event(
                                Event(
                                    event_type="component_started",
                                    data={
                                        "component_name": "dht_client",
                                        "status": "running",
                                        "port": dht_port,
                                    },
                                )
                            )
                        except Exception as e:
                            self.logger.debug("Failed to emit COMPONENT_STARTED event for DHT: %s", e)
                    else:
                        self.logger.warning("Failed to create DHT client")
                except Exception:
                    # Best-effort: log and continue
                    self.logger.warning(
                        "DHT client initialization failed. DHT peer discovery may not work.",
                        exc_info=True,
                    )

        network_tasks.append(start_dht_client())

        # Start all network components in parallel
        if network_tasks:
            await asyncio.gather(*network_tasks, return_exceptions=True)

        # OPTIMIZATION: Start independent components in parallel
        # These components don't depend on each other and can be initialized concurrently
        # This saves 5-10 seconds compared to sequential initialization
        independent_tasks = []

        # Security manager (needed by peer service, but can start in parallel with others)
        async def start_security_manager() -> None:
            try:
                self.security_manager = self._make_security_manager()
                if self.security_manager:
                    self.logger.info("Security manager initialized successfully")
                else:
                    self.logger.warning("Failed to create security manager")
            except Exception:
                # Best-effort: log and continue
                self.logger.warning(
                    "Security manager initialization failed. IP filtering and peer validation may not work.",
                    exc_info=True,
                )

        independent_tasks.append(start_security_manager())

        # Disk I/O manager (completely independent)
        async def start_disk_io_manager() -> None:
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

        independent_tasks.append(start_disk_io_manager())

        # Extension manager (independent)
        async def start_extension_manager() -> None:
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

        independent_tasks.append(start_extension_manager())

        # Protocol manager (independent)
        async def start_protocol_manager() -> None:
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

        independent_tasks.append(start_protocol_manager())

        # Queue manager (depends only on session manager)
        async def start_queue_manager() -> None:
            try:
                from ccbt.models import QueueConfig
                from ccbt.queue.manager import TorrentQueueManager

                # Check if queue management is enabled in config
                queue_config = getattr(self.config, "queue", None)
                if queue_config is None:
                    # Create default queue config if not present
                    queue_config = QueueConfig()

                # Create and start queue manager
                self.queue_manager = TorrentQueueManager(self, config=queue_config)
                await self.queue_manager.start()
                self.logger.info("Queue manager initialized successfully")
            except Exception:
                # Best-effort: log and continue
                self.logger.warning(
                    "Queue manager initialization failed. Queue management may not work.",
                    exc_info=True,
                )

        independent_tasks.append(start_queue_manager())

        # Executor (depends on session manager and needs UDP/DHT initialized, but can start after they're created)
        async def start_executor() -> None:
            try:
                from ccbt.executor.manager import ExecutorManager

                executor_manager = ExecutorManager.get_instance()
                self.executor = executor_manager.get_executor(session_manager=self)

                # CRITICAL FIX: Verify executor is properly initialized
                adapter_error = "Executor adapter not initialized"
                if not hasattr(self.executor, "adapter") or self.executor.adapter is None:
                    raise RuntimeError(adapter_error)
                session_manager_error = "Executor session_manager not initialized"
                if (
                    not hasattr(self.executor.adapter, "session_manager")
                    or self.executor.adapter.session_manager is None
                ):
                    raise RuntimeError(session_manager_error)
                mismatch_error = "Executor session_manager reference mismatch"
                if self.executor.adapter.session_manager is not self:
                    raise RuntimeError(mismatch_error)

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

        independent_tasks.append(start_executor())

        # Start all independent components in parallel
        if independent_tasks:
            await asyncio.gather(*independent_tasks, return_exceptions=True)

        # Start peer service (after security manager is ready, which was started in parallel above)
        try:
            if self.peer_service:
                await self.peer_service.start()
                self.logger.info("Peer service started successfully")
            else:
                self.logger.warning("Peer service not available")
        except Exception:
            # Best-effort: log and continue
            self.logger.debug("Peer service start failed", exc_info=True)

        # CRITICAL FIX: Register XET protocol if enabled
        # XET protocol is needed for protocol.get_xet command and protocol info queries
        if (
            self.protocol_manager
            and (
                (hasattr(self.config, "disk") and getattr(self.config.disk, "xet_enabled", False))
                or (
                    hasattr(self.config, "xet_sync")
                    and self.config.xet_sync
                    and self.config.xet_sync.enable_xet
                )
            )
        ):
            try:
                from ccbt.protocols.xet import XetProtocol

                # Get DHT and tracker clients if available
                dht_client = getattr(self, "dht_client", None)
                tracker_client = getattr(self, "udp_tracker_client", None)

                # Create and register XET protocol
                xet_protocol = XetProtocol(dht_client=dht_client, tracker_client=tracker_client)
                self.protocol_manager.register_protocol(xet_protocol)

                # Start the protocol
                await xet_protocol.start()
                self.logger.info("XET protocol registered and started successfully")
            except Exception as e:
                self.logger.warning(
                    "Failed to register XET protocol: %s. "
                    "XET protocol operations may not work correctly.",
                    e,
                    exc_info=True,
                )
                # Don't fail startup - XET protocol may not be needed in all scenarios

        # CRITICAL FIX: Initialize WebTorrent components at daemon startup if enabled
        # This ensures WebSocket server and WebRTC manager are initialized once
        if self.config.network.webtorrent.enable_webtorrent:
            try:
                # Function may be dynamically defined or conditionally imported
                # Type checker can't resolve dynamic imports from refactored modules
                from ccbt.session.manager_startup import (
                    start_webtorrent_components,  # type: ignore[attr-defined]
                )

                await start_webtorrent_components(self)
            except Exception as e:
                self.logger.warning(
                    "Failed to initialize WebTorrent components: %s. "
                    "WebTorrent operations may not work correctly.",
                    e,
                    exc_info=True,
                )

        # CRITICAL FIX: Initialize XET sync manager if enabled
        # XET folder synchronization for real-time folder updates
        if (
            hasattr(self.config, "xet_sync")
            and self.config.xet_sync
            and self.config.xet_sync.enable_xet
        ):
            try:
                from ccbt.session.xet_sync_manager import XetSyncManager

                self._xet_sync_manager = XetSyncManager(
                    session_manager=self,
                    sync_mode=self.config.xet_sync.default_sync_mode,
                    check_interval=self.config.xet_sync.check_interval,
                    consensus_threshold=self.config.xet_sync.consensus_threshold,
                )
                await self._xet_sync_manager.start()
                self.logger.info("XET sync manager initialized successfully")
                # Note: XetSyncManager handles real-time sync internally
                self._xet_realtime_sync = None
            except Exception as e:
                self.logger.warning(
                    "Failed to initialize XET sync manager: %s. "
                    "XET folder synchronization may not work correctly.",
                    e,
                    exc_info=True,
                )
                # Don't fail startup - XET sync may not be needed in all scenarios
                self._xet_sync_manager = None
                self._xet_realtime_sync = None

        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._start_metrics_task()

        # Initialize global checkpoint manager
        if self.config.disk.checkpoint_enabled:
            try:
                from ccbt.storage.checkpoint import GlobalCheckpointManager

                self.global_checkpoint_manager = GlobalCheckpointManager(self.config.disk)
                # Load global checkpoint if exists
                global_checkpoint = await self.global_checkpoint_manager.load_global_checkpoint()
                if global_checkpoint:
                    self.logger.info("Loaded global checkpoint")
                    # Restore global state (queue, limits, etc.) if needed
            except Exception as e:
                self.logger.debug("Failed to initialize global checkpoint manager: %s", e)
                self.global_checkpoint_manager = None
        else:
            self.global_checkpoint_manager = None

        self.logger.info("Async session manager started")

    async def stop(self) -> None:
        """Stop the async session manager."""
        self._metrics_shutdown = True
        if self._metrics_restart_task:
            self._metrics_restart_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._metrics_restart_task
            self._metrics_restart_task = None

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

        # CRITICAL: Save checkpoints for all torrents BEFORE stopping them
        # This ensures checkpoints are saved even on abrupt shutdown
        if self.config.disk.checkpoint_enabled:
            try:
                async with self.lock:
                    for info_hash, session in list(self.torrents.items()):
                        try:
                            # Save checkpoint for each torrent before stopping
                            if hasattr(session, "checkpoint_controller") and session.checkpoint_controller:
                                await session.checkpoint_controller.save_checkpoint_state(session)
                                self.logger.debug(
                                    "Saved checkpoint for torrent %s before shutdown",
                                    info_hash.hex()[:16],
                                )
                            elif hasattr(session, "_save_checkpoint"):
                                await session._save_checkpoint()
                                self.logger.debug(
                                    "Saved checkpoint for torrent %s before shutdown (fallback)",
                                    info_hash.hex()[:16],
                                )
                        except Exception as e:
                            self.logger.warning(
                                "Failed to save checkpoint for torrent %s: %s",
                                info_hash.hex()[:16] if info_hash else "unknown",
                                e,
                            )
            except Exception as e:
                self.logger.warning("Error saving torrent checkpoints during shutdown: %s", e)

        # Save global checkpoint before stopping
        if self.config.disk.checkpoint_enabled and hasattr(self, "global_checkpoint_manager") and self.global_checkpoint_manager:
            try:

                from ccbt.models import GlobalCheckpoint

                # Collect global state
                active_torrents = []
                paused_torrents = []
                queued_torrents = []

                async with self.lock:
                    for info_hash, session in self.torrents.items():
                        status = await session.get_status()
                        torrent_status = status.get("status", "stopped")
                        if torrent_status == "paused":
                            paused_torrents.append(info_hash)
                        elif torrent_status not in ("stopped", "completed"):
                            active_torrents.append(info_hash)

                # Get queue state if queue manager exists
                if hasattr(self, "queue_manager") and self.queue_manager:
                    queue_state = await self.queue_manager.get_queue_state()
                    queued_torrents.extend(
                        {
                            "info_hash": entry.get("info_hash"),
                            "position": entry.get("position"),
                            "priority": entry.get("priority"),
                            "status": entry.get("status"),
                        }
                        for entry in queue_state.get("queue", [])
                    )

                # Get global rate limits
                global_rate_limits = None
                if self.config.limits.global_down_kib > 0 or self.config.limits.global_up_kib > 0:
                    global_rate_limits = {
                        "down_kib": self.config.limits.global_down_kib,
                        "up_kib": self.config.limits.global_up_kib,
                    }

                # Get global security state
                global_whitelist = []
                global_blacklist = []
                if hasattr(self, "security_manager") and self.security_manager:
                    if hasattr(self.security_manager, "ip_whitelist"):
                        global_whitelist = list(self.security_manager.ip_whitelist)
                    if hasattr(self.security_manager, "ip_blacklist"):
                        blacklist = self.security_manager.ip_blacklist
                        if isinstance(blacklist, dict):
                            global_blacklist = list(blacklist.keys())
                        elif isinstance(blacklist, set):
                            global_blacklist = list(blacklist)

                # Create global checkpoint
                global_checkpoint = GlobalCheckpoint(
                    active_torrents=active_torrents,
                    paused_torrents=paused_torrents,
                    queued_torrents=queued_torrents,
                    global_rate_limits=global_rate_limits,
                    global_peer_whitelist=global_whitelist,
                    global_peer_blacklist=global_blacklist,
                )

                await self.global_checkpoint_manager.save_global_checkpoint(global_checkpoint)
                self.logger.info("Saved global checkpoint")
            except Exception as e:
                self.logger.debug("Failed to save global checkpoint: %s", e)

        # Stop all torrents
        # CRITICAL FIX: Stop torrents with timeout to prevent hanging during shutdown
        async with self.lock:
            for session in list(self.torrents.values()):
                try:
                    # Use timeout to prevent individual torrent stop from hanging
                    await asyncio.wait_for(session.stop(), timeout=10.0)
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "Torrent session stop timed out for %s, forcing cleanup",
                        session.info.name if hasattr(session, "info") else "unknown"
                    )
                    # Force cancellation of any remaining tasks
                    if hasattr(session, "_dht_discovery_task") and session._dht_discovery_task and not session._dht_discovery_task.done():
                        session._dht_discovery_task.cancel()
                except Exception as e:
                    self.logger.warning(
                        "Error stopping torrent session %s: %s",
                        session.info.name if hasattr(session, "info") else "unknown",
                        e
                    )
            self.torrents.clear()

        # Stop XET folder sessions
        async with self._xet_folders_lock:
            for folder_key, folder in list(self.xet_folders.items()):
                try:
                    await folder.stop()
                    self.logger.debug("Stopped XET folder %s", folder_key)
                except Exception as e:
                    self.logger.debug(
                        "Error stopping XET folder %s: %s", folder_key, e, exc_info=True
                    )
            self.xet_folders.clear()

        # Stop XET sync components
        if self._xet_realtime_sync:
            try:
                await self._xet_realtime_sync.stop()
                self.logger.debug("XET real-time sync task stopped")
            except Exception as e:
                self.logger.debug("Error stopping XET real-time sync: %s", e, exc_info=True)

        if self._xet_sync_manager:
            try:
                await self._xet_sync_manager.stop()
                self.logger.debug("XET sync manager stopped")
            except Exception as e:
                self.logger.debug("Error stopping XET sync manager: %s", e, exc_info=True)

        # Stop XET protocol if registered
        if self.protocol_manager:
            try:
                from ccbt.protocols.base import ProtocolType

                xet_protocol = self.protocol_manager.get_protocol(ProtocolType.XET)
                if xet_protocol:
                    await xet_protocol.stop()
                    await self.protocol_manager.unregister_protocol(ProtocolType.XET)
                    self.logger.debug("XET protocol stopped and unregistered")
            except Exception as e:
                self.logger.debug("Error stopping XET protocol: %s", e, exc_info=True)

        # Stop background tasks and await completion
        # Note: contextlib is already imported at module level
        tasks_to_cancel = []
        if self._cleanup_task:
            self._cleanup_task.cancel()
            tasks_to_cancel.append(self._cleanup_task)
        if self._metrics_task:
            self._metrics_task.cancel()
            tasks_to_cancel.append(self._metrics_task)

        # Cancel piece verification tasks
        if hasattr(self, "_piece_verified_tasks"):
            for task in list(self._piece_verified_tasks):
                if not task.done():
                    task.cancel()
                    tasks_to_cancel.append(task)
            self._piece_verified_tasks.clear()

        # Cancel DHT peer processing tasks
        if hasattr(self, "_dht_peer_tasks"):
            for task in list(self._dht_peer_tasks):
                if not task.done():
                    task.cancel()
                    tasks_to_cancel.append(task)
            self._dht_peer_tasks.clear()

        # Cancel DHT discovery task
        if (
            hasattr(self, "_dht_discovery_task")
            and not self._dht_discovery_task.done()
        ):
                self._dht_discovery_task.cancel()
                tasks_to_cancel.append(self._dht_discovery_task)

        # Cancel download manager background tasks
        if hasattr(self, "download_manager") and self.download_manager and hasattr(self.download_manager, "_background_tasks"):
            for task in list(self.download_manager._background_tasks):
                if not task.done():
                    task.cancel()
                    tasks_to_cancel.append(task)

        # Cancel piece manager background tasks
        if (hasattr(self, "download_manager") and self.download_manager and self.download_manager.piece_manager and
            hasattr(self.download_manager.piece_manager, "_background_tasks")):
            for task in list(self.download_manager.piece_manager._background_tasks):
                if not task.done():
                    task.cancel()
                    tasks_to_cancel.append(task)

        # Await all task cancellations to complete
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        self._metrics_task = None

        # Stop TCP server (releases TCP port)
        if self.tcp_server:
            try:
                await self.tcp_server.stop()
                self.logger.debug("TCP server stopped (port released)")
                # CRITICAL FIX: Add delay on Windows to prevent socket buffer exhaustion
                import sys
                if sys.platform == "win32":
                    await asyncio.sleep(0.05)  # Small delay between socket closures
            except OSError as e:
                # CRITICAL FIX: Handle WinError 10055 gracefully during shutdown
                error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
                if error_code == 10055:
                    self.logger.debug(
                        "WinError 10055 (socket buffer exhaustion) during TCP server shutdown. "
                        "This is a transient Windows issue. Continuing..."
                    )
                else:
                    self.logger.debug("OSError stopping TCP server: %s", e, exc_info=True)
            except Exception as e:
                self.logger.debug("Error stopping TCP server: %s", e, exc_info=True)

        # Stop UDP tracker client (releases UDP tracker port)
        if self.udp_tracker_client:
            try:
                await self.udp_tracker_client.stop()
                self.logger.debug("UDP tracker client stopped (port released)")
                # CRITICAL FIX: Add delay on Windows to prevent socket buffer exhaustion
                import sys
                if sys.platform == "win32":
                    await asyncio.sleep(0.05)  # Small delay between socket closures
            except OSError as e:
                # CRITICAL FIX: Handle WinError 10055 gracefully during shutdown
                error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
                if error_code == 10055:
                    self.logger.debug(
                        "WinError 10055 (socket buffer exhaustion) during UDP tracker shutdown. "
                        "This is a transient Windows issue. Continuing..."
                    )
                else:
                    self.logger.debug(
                        "OSError stopping UDP tracker client: %s", e, exc_info=True
                    )
            except Exception as e:
                self.logger.debug(
                    "Error stopping UDP tracker client: %s", e, exc_info=True
                )

        # Stop DHT client (releases DHT UDP port)
        if self.dht_client:
            try:
                await self.dht_client.stop()
                self.logger.debug("DHT client stopped (port released)")
                # CRITICAL FIX: Add delay on Windows to prevent socket buffer exhaustion
                import sys
                if sys.platform == "win32":
                    await asyncio.sleep(0.05)  # Small delay between socket closures
            except OSError as e:
                # CRITICAL FIX: Handle WinError 10055 gracefully during shutdown
                error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
                if error_code == 10055:
                    self.logger.debug(
                        "WinError 10055 (socket buffer exhaustion) during DHT shutdown. "
                        "This is a transient Windows issue. Continuing..."
                    )
                else:
                    self.logger.debug("OSError stopping DHT client: %s", e, exc_info=True)
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
                    # Function may be dynamically defined or conditionally imported
                    # Type checker can't resolve dynamic imports from refactored modules
                    from ccbt.session.manager_startup import (
                        start_dht,  # type: ignore[attr-defined]
                    )

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
                    # Function may be dynamically defined or conditionally imported
                    # Type checker can't resolve dynamic imports from refactored modules
                    from ccbt.session.manager_startup import (
                        start_nat,  # type: ignore[attr-defined]
                    )

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

            # Apply rate limit changes
            limits_config_changed = (
                old_config.limits.global_down_kib != new_config.limits.global_down_kib
                or old_config.limits.global_up_kib != new_config.limits.global_up_kib
                or old_config.limits.per_torrent_down_kib
                != new_config.limits.per_torrent_down_kib
                or old_config.limits.per_torrent_up_kib
                != new_config.limits.per_torrent_up_kib
            )
            if limits_config_changed:
                try:
                    # Apply global rate limits to all torrents
                    if (
                        old_config.limits.global_down_kib
                        != new_config.limits.global_down_kib
                        or old_config.limits.global_up_kib
                        != new_config.limits.global_up_kib
                    ):
                        await self.global_set_rate_limits(
                            new_config.limits.global_down_kib,
                            new_config.limits.global_up_kib,
                        )
                        reloaded_components.append("global_rate_limits")
                        self.logger.info(
                            "Applied global rate limits: down=%d KiB/s, up=%d KiB/s",
                            new_config.limits.global_down_kib,
                            new_config.limits.global_up_kib,
                        )

                    # Apply per-torrent rate limits to all active torrents if default changed
                    if (
                        old_config.limits.per_torrent_down_kib
                        != new_config.limits.per_torrent_down_kib
                        or old_config.limits.per_torrent_up_kib
                        != new_config.limits.per_torrent_up_kib
                    ):
                        async with self.lock:
                            torrents = list(self.torrents.keys())

                        for info_hash in torrents:
                            info_hash_hex = info_hash.hex()
                            # Only apply if torrent doesn't have custom limits set
                            if info_hash not in self._per_torrent_limits:
                                await self.set_rate_limits(
                                    info_hash_hex,
                                    new_config.limits.per_torrent_down_kib,
                                    new_config.limits.per_torrent_up_kib,
                                )
                        reloaded_components.append("per_torrent_rate_limits")
                        self.logger.info(
                            "Applied per-torrent rate limits: down=%d KiB/s, up=%d KiB/s",
                            new_config.limits.per_torrent_down_kib,
                            new_config.limits.per_torrent_up_kib,
                        )

                    # Apply per-peer rate limits to all active peers if default changed
                    if (
                        old_config.limits.per_peer_up_kib
                        != new_config.limits.per_peer_up_kib
                    ):
                        updated_count = await self.set_all_peers_rate_limit(
                            new_config.limits.per_peer_up_kib
                        )
                        reloaded_components.append("per_peer_rate_limits")
                        self.logger.info(
                            "Applied per-peer upload rate limits: %d KiB/s to %d peers",
                            new_config.limits.per_peer_up_kib,
                            updated_count,
                        )
                except Exception as e:
                    self.logger.warning("Failed to apply rate limit changes: %s", e)

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
                    # Function may be dynamically defined or conditionally imported
                    # Type checker can't resolve dynamic imports from refactored modules
                    from ccbt.session.manager_startup import (
                        start_tcp_server,  # type: ignore[attr-defined]
                    )

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

    async def cancel_torrent(self, info_hash_hex: str) -> bool:
        """Cancel a torrent download by info hash (pause but keep in session).

        Returns True if cancelled, False otherwise.
        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        async with self.lock:
            session = self.torrents.get(info_hash)
        if not session:
            return False
        await session.cancel()
        return True

    async def force_start_torrent(self, info_hash_hex: str) -> bool:
        """Force start a torrent by info hash (bypass queue limits).

        Returns True if force started, False otherwise.
        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        # If queue manager exists, use it for force start
        if self.queue_manager:
            try:
                success = await self.queue_manager.force_start_torrent(info_hash)
                if success:
                    return True
            except Exception as e:
                self.logger.warning("Queue manager force_start failed: %s, trying direct start", e)

        # Fallback: direct session start/resume
        async with self.lock:
            session = self.torrents.get(info_hash)
        if not session:
            return False
        await session.force_start()
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

    async def get_rate_samples(
        self,
        seconds: int = 120,
        min_samples: int = 1,
    ) -> list[dict[str, float]]:
        """Return recent upload/download rate samples with optional zero-fill."""
        window = max(1, int(seconds))
        cutoff = time.time() - window
        samples: list[dict[str, float]] = [
            sample.copy() for sample in self._rate_history if sample["timestamp"] >= cutoff
        ]

        # Guarantee at least one sample so downstream graphs always render a line
        min_samples = max(1, min_samples)
        if len(samples) < min_samples:
            last_timestamp = samples[-1]["timestamp"] if samples else time.time()
            while len(samples) < min_samples:
                last_timestamp -= self._metrics_sample_interval
                samples.insert(
                    0,
                    {
                        "timestamp": last_timestamp,
                        "download_rate": 0.0,
                        "upload_rate": 0.0,
                    },
                )
        return samples

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
        output_dir: str | Path | None = None,
    ) -> str:
        """Add a torrent file or torrent data to the session.

        Args:
            path: Path to torrent file or torrent data dictionary
            resume: Whether to resume from checkpoint if available
            output_dir: Optional output directory for this torrent. If None, uses self.output_dir

        """
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

                # Create session - use provided output_dir or fall back to self.output_dir
                torrent_output_dir = output_dir if output_dir is not None else self.output_dir
                session = AsyncTorrentSession(td, torrent_output_dir, self)

                # Set source information for checkpoint metadata
                if isinstance(path, str):
                    session.torrent_file_path = path

                self.torrents[info_hash] = session
                self.logger.info(
                    "Registered torrent session %s (info_hash: %s) - now available for incoming connections",
                    session.info.name,
                    info_hash.hex()[:16],
                )

                # BEP 27: Track private torrents for DHT/PEX/LSD enforcement
                if session.is_private:
                    self.private_torrents.add(info_hash)
                    self.logger.debug(
                        "Added private torrent %s to private_torrents set (BEP 27)",
                        info_hash.hex()[:8],
                    )

                # Initialize per-torrent rate limits from config
                per_torrent_down = self.config.limits.per_torrent_down_kib
                per_torrent_up = self.config.limits.per_torrent_up_kib
                if per_torrent_down > 0 or per_torrent_up > 0:
                    info_hash_hex = info_hash.hex()
                    await self.set_rate_limits(
                        info_hash_hex, per_torrent_down, per_torrent_up
                    )
                    self.logger.debug(
                        "Initialized per-torrent rate limits for %s: down=%d KiB/s, up=%d KiB/s",
                        info_hash.hex()[:8],
                        per_torrent_down,
                        per_torrent_up,
                    )

            # CRITICAL FIX: Start session AFTER registration
            # This ensures incoming connections can find the session via get_session_for_info_hash()
            # even if session.start() is still in progress (e.g., fetching metadata for magnets)
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

    async def add_magnet(
        self, uri: str, resume: bool = False, output_dir: str | Path | None = None
    ) -> str:
        """Add a magnet link to the session.

        Args:
            uri: Magnet URI string
            resume: Whether to resume from checkpoint if available
            output_dir: Optional output directory for this magnet. If None, uses self.output_dir

        """
        info_hash: bytes | None = None
        session: AsyncTorrentSession | None = None
        try:
            mi = _session_mod.parse_magnet(uri)
            # CRITICAL FIX: Pass web_seeds to build_minimal_torrent_data
            # Also log trackers for debugging
            self.logger.info(
                "Parsed magnet link: info_hash=%s, name=%s, trackers=%d, web_seeds=%d",
                mi.info_hash.hex()[:16],
                mi.display_name or "Unknown",
                len(mi.trackers),
                len(mi.web_seeds) if mi.web_seeds else 0,
            )
            if mi.trackers:
                self.logger.debug(
                    "Magnet link trackers: %s",
                    ", ".join(mi.trackers[:5]) + ("..." if len(mi.trackers) > 5 else ""),
                )
            td = _session_mod.build_minimal_torrent_data(
                mi.info_hash, mi.display_name, mi.trackers, mi.web_seeds
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

                # Create session - use provided output_dir or fall back to self.output_dir
                magnet_output_dir = output_dir if output_dir is not None else self.output_dir
                session = AsyncTorrentSession(td, magnet_output_dir, self)

                # Set source information for checkpoint metadata
                session.magnet_uri = uri

                self.torrents[info_hash] = session
                self.logger.info(
                    "Registered magnet session %s (info_hash: %s) - now available for incoming connections",
                    session.info.name,
                    info_hash.hex()[:16],
                )

                # BEP 27: Track private torrents for DHT/PEX/LSD enforcement
                if session.is_private:
                    self.private_torrents.add(info_hash)
                    self.logger.debug(
                        "Added private magnet torrent %s to private_torrents set (BEP 27)",
                        info_hash.hex()[:8],
                    )

            # CRITICAL FIX: Start session AFTER registration
            # This ensures incoming connections can find the session via get_session_for_info_hash()
            # even if session.start() is still in progress (e.g., fetching metadata for magnets)
            # If session.start() fails, remove the session from torrents dict
            # to prevent orphaned sessions that could cause issues
            try:
                await session.start(resume=resume)
            except Exception:
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
                            with contextlib.suppress(Exception):
                                await removed_session.stop()  # Ignore errors during cleanup
                # Re-raise the original error
                raise  # TRY201: Use bare raise to re-raise exception

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

    async def get_global_peer_metrics(self) -> dict[str, Any]:
        """Get global peer metrics across all torrents.

        Returns:
            Dictionary with:
            - total_peers: Total number of unique peers
            - active_peers: Number of active peers
            - peers: List of peer metrics dictionaries

        """
        import time
        current_time = time.time()

        # Aggregate peers from all torrents
        peer_map: dict[tuple[str, int], dict[str, Any]] = {}
        total_peers = 0
        active_peers = 0

        async with self.lock:
            for info_hash, torrent_session in self.torrents.items():
                info_hash_hex = info_hash.hex()
                if not hasattr(torrent_session, "download_manager"):
                    continue

                download_manager = torrent_session.download_manager
                if not hasattr(download_manager, "peer_manager") or download_manager.peer_manager is None:
                    continue

                peer_manager = download_manager.peer_manager
                connected_peers = peer_manager.get_connected_peers()

                for connection in connected_peers:
                    if not hasattr(connection, "peer_info") or not hasattr(connection, "stats"):
                        continue

                    peer_info = connection.peer_info
                    peer_key = (peer_info.ip, peer_info.port)

                    # Get stats
                    stats = connection.stats
                    download_rate = getattr(stats, "download_rate", 0.0)
                    upload_rate = getattr(stats, "upload_rate", 0.0)
                    bytes_downloaded = getattr(stats, "bytes_downloaded", 0)
                    bytes_uploaded = getattr(stats, "bytes_uploaded", 0)

                    # Get connection duration
                    connection_start = getattr(connection, "connection_start_time", current_time)
                    connection_duration = current_time - connection_start if connection_start else 0.0

                    # Get client name
                    client = getattr(peer_info, "client_name", None) or getattr(connection, "client_name", None)

                    # Get choked status
                    choked = getattr(connection, "am_choking", True)

                    # Get pieces info
                    pieces_received = getattr(stats, "pieces_received", 0)
                    pieces_served = getattr(stats, "pieces_served", 0)

                    # Get latency
                    request_latency = getattr(stats, "request_latency", 0.0)

                    if peer_key not in peer_map:
                        peer_map[peer_key] = {
                            "peer_key": f"{peer_info.ip}:{peer_info.port}",
                            "ip": peer_info.ip,
                            "port": peer_info.port,
                            "info_hashes": [],
                            "total_download_rate": 0.0,
                            "total_upload_rate": 0.0,
                            "total_bytes_downloaded": 0,
                            "total_bytes_uploaded": 0,
                            "client": client,
                            "choked": choked,
                            "connection_duration": connection_duration,
                            "pieces_received": 0,
                            "pieces_served": 0,
                            "request_latency": request_latency,
                        }
                        total_peers += 1
                        if not choked and (download_rate > 0.0 or upload_rate > 0.0):
                            active_peers += 1

                    # Aggregate metrics across torrents
                    peer_data = peer_map[peer_key]
                    peer_data["info_hashes"].append(info_hash_hex)
                    peer_data["total_download_rate"] += download_rate
                    peer_data["total_upload_rate"] += upload_rate
                    peer_data["total_bytes_downloaded"] += bytes_downloaded
                    peer_data["total_bytes_uploaded"] += bytes_uploaded
                    peer_data["pieces_received"] += pieces_received
                    peer_data["pieces_served"] += pieces_served
                    # Use average latency
                    if request_latency > 0.0:
                        peer_data["request_latency"] = (peer_data["request_latency"] + request_latency) / 2.0

        return {
            "total_peers": total_peers,
            "active_peers": active_peers,
            "peers": list(peer_map.values()),
        }

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
            # CRITICAL FIX: Use listen_port_tcp (or listen_port as fallback) and get external port from NAT
            listen_port = (
                sess.config.network.listen_port_tcp
                or sess.config.network.listen_port
            )
            announce_port = listen_port

            # Try to get external port from NAT manager if available
            if (
                sess.session_manager
                and hasattr(sess.session_manager, "nat_manager")
                and sess.session_manager.nat_manager
            ):
                try:
                    external_port = (
                        await sess.session_manager.nat_manager.get_external_port(
                            listen_port, "tcp"
                        )
                    )
                    if external_port is not None:
                        announce_port = external_port
                except Exception:
                    pass  # Best-effort, use internal port

            await sess.tracker.announce(td, port=announce_port)
        except Exception:
            return False
        else:
            return True

    async def global_pause_all(self) -> dict[str, Any]:
        """Pause all torrents.

        Returns:
            Dict with success_count, failure_count, and results

        """
        results = []
        success_count = 0
        failure_count = 0

        async with self.lock:
            torrents = list(self.torrents.values())

        for session in torrents:
            try:
                await session.pause()
                results.append(
                    {
                        "info_hash": session.info.info_hash.hex(),
                        "success": True,
                        "message": "Paused",
                    }
                )
                success_count += 1
            except Exception as e:
                results.append(
                    {
                        "info_hash": session.info.info_hash.hex(),
                        "success": False,
                        "error": str(e),
                    }
                )
                failure_count += 1

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results,
        }

    async def global_resume_all(self) -> dict[str, Any]:
        """Resume all paused torrents.

        Returns:
            Dict with success_count, failure_count, and results

        """
        results = []
        success_count = 0
        failure_count = 0

        async with self.lock:
            torrents = list(self.torrents.values())

        for session in torrents:
            try:
                if session.info.status in ("paused", "cancelled"):
                    await session.resume()
                    results.append(
                        {
                            "info_hash": session.info.info_hash.hex(),
                            "success": True,
                            "message": "Resumed",
                        }
                    )
                    success_count += 1
            except Exception as e:
                results.append(
                    {
                        "info_hash": session.info.info_hash.hex(),
                        "success": False,
                        "error": str(e),
                    }
                )
                failure_count += 1

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results,
        }

    async def global_force_start_all(self) -> dict[str, Any]:
        """Force start all torrents (bypass queue limits).

        Returns:
            Dict with success_count, failure_count, and results

        """
        results = []
        success_count = 0
        failure_count = 0

        async with self.lock:
            torrents = list(self.torrents.values())

        for session in torrents:
            try:
                await session.force_start()
                results.append(
                    {
                        "info_hash": session.info.info_hash.hex(),
                        "success": True,
                        "message": "Force started",
                    }
                )
                success_count += 1
            except Exception as e:
                results.append(
                    {
                        "info_hash": session.info.info_hash.hex(),
                        "success": False,
                        "error": str(e),
                    }
                )
                failure_count += 1

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results,
        }

    async def global_set_rate_limits(self, download_kib: int, upload_kib: int) -> bool:
        """Set global rate limits for all torrents.

        Args:
            download_kib: Global download limit (KiB/s, 0 = unlimited)
            upload_kib: Global upload limit (KiB/s, 0 = unlimited)

        Returns:
            True if limits set successfully

        """
        # Update config
        self.config.limits.global_down_kib = download_kib
        self.config.limits.global_up_kib = upload_kib

        # Apply to all torrents using AsyncSessionManager.set_rate_limits
        async with self.lock:
            torrents = list(self.torrents.keys())

        for info_hash in torrents:
            try:
                info_hash_hex = info_hash.hex()
                await self.set_rate_limits(info_hash_hex, download_kib, upload_kib)
            except Exception as e:
                self.logger.warning("Failed to set rate limits for torrent %s: %s", info_hash.hex()[:8], e)

        return True

    async def set_per_peer_rate_limit(
        self, info_hash_hex: str, peer_key: str, upload_limit_kib: int
    ) -> bool:
        """Set per-peer upload rate limit for a specific peer in a torrent.

        Args:
            info_hash_hex: Torrent info hash (hex string)
            peer_key: Peer identifier (format: "ip:port")
            upload_limit_kib: Upload rate limit in KiB/s (0 = unlimited)

        Returns:
            True if peer found and limit set, False otherwise

        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        async with self.lock:
            session = self.torrents.get(info_hash)
            if not session:
                return False

        # Get peer manager from download manager
        if not hasattr(session, "download_manager"):
            return False

        download_manager = session.download_manager
        if not hasattr(download_manager, "peer_manager") or download_manager.peer_manager is None:
            return False

        peer_manager = download_manager.peer_manager
        return await peer_manager.set_per_peer_rate_limit(peer_key, upload_limit_kib)

    async def get_per_peer_rate_limit(
        self, info_hash_hex: str, peer_key: str
    ) -> int | None:
        """Get per-peer upload rate limit for a specific peer in a torrent.

        Args:
            info_hash_hex: Torrent info hash (hex string)
            peer_key: Peer identifier (format: "ip:port")

        Returns:
            Upload rate limit in KiB/s (0 = unlimited), or None if peer/torrent not found

        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return None

        async with self.lock:
            session = self.torrents.get(info_hash)
            if not session:
                return None

        # Get peer manager from download manager
        if not hasattr(session, "download_manager"):
            return None

        download_manager = session.download_manager
        if not hasattr(download_manager, "peer_manager") or download_manager.peer_manager is None:
            return None

        peer_manager = download_manager.peer_manager
        return await peer_manager.get_per_peer_rate_limit(peer_key)

    async def set_all_peers_rate_limit(self, upload_limit_kib: int) -> int:
        """Set per-peer upload rate limit for all active peers across all torrents.

        Args:
            upload_limit_kib: Upload rate limit in KiB/s (0 = unlimited)

        Returns:
            Number of peers updated

        """
        total_updated = 0

        async with self.lock:
            torrents = list(self.torrents.values())

        for session in torrents:
            # Get peer manager from download manager
            if not hasattr(session, "download_manager"):
                continue

            download_manager = session.download_manager
            if not hasattr(download_manager, "peer_manager") or download_manager.peer_manager is None:
                continue

            peer_manager = download_manager.peer_manager
            updated_count = await peer_manager.set_all_peers_rate_limit(upload_limit_kib)
            total_updated += updated_count

        return total_updated

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

    async def add_xet_folder(
        self,
        folder_path: str | Path,
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
            sync_mode: Synchronization mode (optional, uses default if not provided)
            source_peers: Designated source peer IDs (optional)
            check_interval: Check interval in seconds (optional)

        Returns:
            Folder identifier (folder_path or info_hash)

        """
        from ccbt.config.config import get_config
        from ccbt.storage.xet_folder_manager import XetFolder

        config = get_config()

        # Determine sync mode
        if sync_mode is None:
            sync_mode = config.xet_sync.default_sync_mode

        # Determine check interval
        if check_interval is None:
            check_interval = config.xet_sync.check_interval

        # Parse .tonic file or link if provided
        info_hash: str | None = None
        if tonic_file:
            from ccbt.core.tonic import TonicFile

            tonic_parser = TonicFile()
            parsed_data = tonic_parser.parse(tonic_file)
            info_hash = tonic_parser.get_info_hash(parsed_data).hex()
            # folder_name is parsed but not used - kept for potential future use
            _ = parsed_data["info"]["name"]
            sync_mode = sync_mode or parsed_data.get("sync_mode", sync_mode)
            source_peers = source_peers or parsed_data.get("source_peers")
        elif tonic_link:
            from ccbt.core.tonic_link import parse_tonic_link

            link_info = parse_tonic_link(tonic_link)
            info_hash = link_info.info_hash.hex()
            sync_mode = sync_mode or link_info.sync_mode or sync_mode
            source_peers = source_peers or link_info.source_peers

        # Create XET folder instance
        folder = XetFolder(
            folder_path=folder_path,
            sync_mode=sync_mode,
            source_peers=source_peers,
            check_interval=check_interval,
            enable_git=config.xet_sync.enable_git_versioning,
        )

        # Register folder
        async with self._xet_folders_lock:
            # Use info_hash as key if available, otherwise use folder_path
            folder_key = info_hash if info_hash else str(Path(folder_path).resolve())
            if folder_key in self.xet_folders:
                msg = f"XET folder {folder_key} already exists"
                raise ValueError(msg)

            self.xet_folders[folder_key] = folder
            self.logger.info(
                "Registered XET folder session %s (key: %s)",
                folder_path,
                folder_key[:16] if len(folder_key) > 16 else folder_key,
            )

        # Start folder sync
        await folder.start()

        # Notify callback if available
        if hasattr(self, "on_xet_folder_added") and self.on_xet_folder_added:
            await self.on_xet_folder_added(folder_key, str(folder_path))

        return folder_key

    async def remove_xet_folder(self, folder_key: str) -> bool:
        """Remove XET folder from synchronization.

        Args:
            folder_key: Folder identifier (folder_path or info_hash)

        Returns:
            True if removed, False if not found

        """
        async with self._xet_folders_lock:
            folder = self.xet_folders.get(folder_key)
            if not folder:
                return False

            # Stop folder sync
            try:
                await folder.stop()
            except Exception as e:
                self.logger.warning("Error stopping XET folder %s: %s", folder_key, e)

            # Remove from registry
            del self.xet_folders[folder_key]
            self.logger.info("Removed XET folder session %s", folder_key)

            # Notify callback if available
            if hasattr(self, "on_xet_folder_removed") and self.on_xet_folder_removed:
                await self.on_xet_folder_removed(folder_key)

            return True

    async def get_xet_folder(self, folder_key: str) -> Any | None:
        """Get XET folder by key.

        Args:
            folder_key: Folder identifier (folder_path or info_hash)

        Returns:
            XetFolder instance or None if not found

        """
        async with self._xet_folders_lock:
            return self.xet_folders.get(folder_key)

    async def list_xet_folders(self) -> list[dict[str, Any]]:
        """List all registered XET folders.

        Returns:
            List of folder information dictionaries

        """
        async with self._xet_folders_lock:
            folders = []
            for folder_key, folder in self.xet_folders.items():
                try:
                    status = folder.get_status()
                    folders.append(
                        {
                            "folder_key": folder_key,
                            "folder_path": str(folder.folder_path),
                            "sync_mode": status.sync_mode,
                            "is_syncing": status.is_syncing,
                            "connected_peers": status.connected_peers,
                            "sync_progress": status.sync_progress,
                            "current_git_ref": status.current_git_ref,
                            "last_sync_time": status.last_sync_time,
                        }
                    )
                except Exception as e:
                    self.logger.warning(
                        "Error getting status for XET folder %s: %s", folder_key, e
                    )
                    folders.append(
                        {
                            "folder_key": folder_key,
                            "folder_path": str(folder.folder_path),
                            "error": str(e),
                        }
                    )
            return folders

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

    async def set_dht_aggressive_mode(self, info_hash_hex: str, enabled: bool) -> bool:
        """Set DHT aggressive discovery mode for a torrent.

        Args:
            info_hash_hex: Torrent info hash in hex format
            enabled: Whether to enable aggressive mode

        Returns:
            True if set successfully, False otherwise

        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False
        async with self.lock:
            sess = self.torrents.get(info_hash)
        if not sess:
            return False
        try:
            dht_setup = getattr(sess, "_dht_setup", None)
            if not dht_setup:
                return False
            # Set aggressive mode
            dht_setup._aggressive_mode = enabled
            # Emit event for the change
            try:
                from ccbt.utils.events import Event, EventType, emit_event
                event_type = (
                    EventType.DHT_AGGRESSIVE_MODE_ENABLED.value
                    if enabled
                    else EventType.DHT_AGGRESSIVE_MODE_DISABLED.value
                )
                await emit_event(Event(
                    event_type=event_type,
                    data={
                        "info_hash": info_hash_hex,
                        "torrent_name": getattr(sess.info, "name", ""),
                        "reason": "manual",
                    },
                ))
            except Exception:
                pass  # Event emission is best-effort
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

        CRITICAL FIX: Also check for sessions that are still starting (metadata fetching for magnets).
        This allows incoming connections to be accepted even if metadata isn't ready yet.

        Args:
            info_hash: Torrent info hash (20 bytes)

        Returns:
            AsyncTorrentSession instance if found, None otherwise

        """
        async with self.lock:
            session = self.torrents.get(info_hash)
            if session is None:
                # CRITICAL FIX: Try case-insensitive and hex string matching for info_hash
                # Some peers might send info_hash in different format
                info_hash_hex = info_hash.hex()
                info_hash_hex_lower = info_hash_hex.lower()
                for ih, sess in self.torrents.items():
                    # Try multiple matching strategies
                    ih_hex = ih.hex()
                    ih_hex_lower = ih_hex.lower()
                    if (
                        ih == info_hash  # Direct bytes comparison
                        or ih_hex == info_hash_hex  # Hex string comparison
                        or ih_hex_lower == info_hash_hex_lower  # Case-insensitive hex
                        or bytes.fromhex(ih_hex) == info_hash  # Convert and compare
                    ):
                        session = sess
                        self.logger.debug(
                            "Found session for info_hash %s using alternative matching (matched: %s)",
                            info_hash_hex[:16],
                            "direct" if ih == info_hash else ("hex" if ih_hex == info_hash_hex else "case-insensitive"),
                        )
                        break

                if session is None:
                    # CRITICAL FIX: Throttle warnings to reduce log spam
                    # Log once per minute per info_hash to avoid flooding logs
                    info_hash_hex = info_hash.hex()[:16]
                    current_time = time.time()

                    # Initialize throttling dict if needed
                    if not hasattr(self, "_session_lookup_warnings"):
                        self._session_lookup_warnings: dict[str, float] = {}  # type: ignore[attr-defined]

                    # Check if we should log this warning (throttle to once per minute)
                    last_warning_time = self._session_lookup_warnings.get(info_hash_hex, 0)
                    should_log = (current_time - last_warning_time) >= 60.0  # 60 seconds throttle

                    if should_log:
                        # Log available sessions for debugging
                        available_hashes = [ih.hex()[:16] for ih in self.torrents]
                        if available_hashes:
                            # Sessions exist but this one wasn't found - this is a real issue
                            self.logger.warning(
                                "Session not found for info_hash %s. Available sessions: %s (total: %d). "
                                "This warning is throttled to once per minute per info_hash.",
                                info_hash_hex,
                                available_hashes,
                                len(self.torrents),
                            )
                        else:
                            # No sessions registered yet - this is expected during startup or when no torrents are active
                            # Use DEBUG level to avoid log spam during daemon startup
                            self.logger.debug(
                                "Session not found for info_hash %s. No active sessions registered yet (this is normal during startup or when no torrents are active).",
                                info_hash_hex,
                            )

                        # Update last warning time
                        self._session_lookup_warnings[info_hash_hex] = current_time

                        # Clean up old entries (older than 5 minutes) to prevent memory leak
                        cutoff_time = current_time - 300.0  # 5 minutes
                        self._session_lookup_warnings = {
                            k: v for k, v in self._session_lookup_warnings.items()
                            if v > cutoff_time
                        }
            return session

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

    def _start_metrics_task(self) -> None:
        """Start the metrics loop task with watchdog support."""
        if self._metrics_shutdown:
            return
        if self._metrics_task and not self._metrics_task.done():
            return
        self._metrics_task = asyncio.create_task(self._metrics_loop())
        self._metrics_task.add_done_callback(self._handle_metrics_task_done)
        # Reset restart cadence when loop is healthy again
        self._metrics_restart_backoff = 1.0

    def _handle_metrics_task_done(self, task: asyncio.Task[Any]) -> None:
        """Watchdog callback invoked when the metrics loop exits."""
        if self._metrics_shutdown:
            return
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            self.logger.error("Metrics loop stopped unexpectedly: %s", exc, exc_info=True)
        if self._metrics_restart_task and not self._metrics_restart_task.done():
            return
        self._metrics_restart_task = asyncio.create_task(self._schedule_metrics_restart())

    async def _schedule_metrics_restart(self) -> None:
        """Schedule a metrics loop restart with exponential backoff."""
        delay = min(self._metrics_restart_backoff, 30.0)
        self.logger.warning("Restarting metrics loop in %.1fs", delay)
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        if self._metrics_shutdown:
            return
        self._metrics_restart_backoff = min(self._metrics_restart_backoff * 2.0, 30.0)
        self._start_metrics_task()
        self._metrics_restart_task = None

    async def _metrics_loop(self) -> None:
        """Background task for metrics collection."""
        while True:
            try:
                start_time = time.time()

                # Collect global metrics
                global_stats = self._aggregate_torrent_stats()

                # Track per-second rate history for interface graphs
                sample = {
                    "timestamp": global_stats["timestamp"],
                    "download_rate": global_stats["total_download_rate"],
                    "upload_rate": global_stats["total_upload_rate"],
                }
                self._rate_history.append(sample)

                # Emit lightweight heartbeat events periodically so observers can detect stalls
                self._metrics_heartbeat_counter += 1
                if self._metrics_heartbeat_counter >= self._metrics_heartbeat_interval:
                    self._metrics_heartbeat_counter = 0
                    try:
                        from ccbt.utils.events import Event, EventType, emit_event

                        await emit_event(
                            Event(
                                event_type=EventType.MONITORING_HEARTBEAT.value,
                                data={
                                    "timestamp": sample["timestamp"],
                                    "download_rate": sample["download_rate"],
                                    "upload_rate": sample["upload_rate"],
                                    "history_size": len(self._rate_history),
                                },
                            ),
                        )
                    except Exception:  # pragma: no cover - best effort heartbeat
                        self.logger.debug("Failed to emit monitoring heartbeat", exc_info=True)

                # Emit aggregated metrics at a lower frequency
                if (
                    global_stats["timestamp"] - self._last_metrics_emit
                    >= self._metrics_emit_interval
                ):
                    await self._emit_global_metrics(global_stats)
                    self._last_metrics_emit = global_stats["timestamp"]

                sleep_for = max(
                    self._metrics_sample_interval - (time.time() - start_time), 0.0
                )
                await asyncio.sleep(sleep_for)

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

    async def get_network_timing_metrics(self) -> dict[str, Any]:
        """Get network timing metrics (uTP delay, RTT) from peer connections.

        Returns:
            Dictionary with network timing metrics:
            - utp_delay_ms: Average uTP delay in milliseconds
            - network_overhead_rate: Network overhead rate in KiB/s

        """
        utp_delays: list[float] = []
        total_overhead = 0.0

        # Collect metrics from all peer connections
        async with self.lock:
            for torrent_session in self.torrents.values():
                if hasattr(torrent_session, "peers"):
                    for peer in torrent_session.peers.values():
                        # Get RTT/latency from peer stats
                        if hasattr(peer, "stats"):
                            latency = getattr(peer.stats, "request_latency", 0.0)
                            if latency > 0:
                                # Convert to milliseconds
                                utp_delays.append(latency * 1000.0)

                        # Estimate overhead (simplified - would need actual overhead tracking)
                        if hasattr(peer, "upload_rate") and hasattr(peer, "download_rate"):
                            # Rough estimate: 5% overhead
                            peer_overhead = (peer.upload_rate + peer.download_rate) * 0.05
                            total_overhead += peer_overhead

        # Calculate average uTP delay
        avg_utp_delay = sum(utp_delays) / len(utp_delays) if utp_delays else 0.0

        # Convert overhead to KiB/s
        overhead_kib = total_overhead / 1024.0

        return {
            "utp_delay_ms": avg_utp_delay,
            "network_overhead_rate": overhead_kib,  # KiB/s
        }

    def get_disk_io_metrics(self) -> dict[str, Any]:
        """Get disk I/O metrics from disk I/O manager.

        Returns:
            Dictionary with disk I/O metrics (see DiskIOManager.get_disk_io_metrics)

        """
        if self.disk_io_manager and hasattr(self.disk_io_manager, "get_disk_io_metrics"):
            return self.disk_io_manager.get_disk_io_metrics()
        return {
            "read_throughput": 0.0,
            "write_throughput": 0.0,
            "cache_hit_rate": 0.0,
            "timing_ms": 0.0,
        }

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
                magnet_info.web_seeds,  # CRITICAL FIX: Pass web seeds from magnet link
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
