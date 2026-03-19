# ccbt/session.py
"""High-performance async session manager for ccBitTorrent.

Manages multiple torrents (file or magnet), coordinates tracker announces,
DHT, PEX, and provides status aggregation with async event loop management.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Optional,
    TypedDict,
    Union,
    cast,
)

if TYPE_CHECKING:
    from ccbt.discovery.dht import AsyncDHTClient
    from ccbt.discovery.pex import AsyncPexManager
    from ccbt.session.types import PieceManagerProtocol, TrackerClientProtocol
    from ccbt.utils.di import DIContainer

from ccbt.config.config import get_config
from ccbt.core.magnet import build_minimal_torrent_data, parse_magnet
from ccbt.core.torrent import TorrentParser as _TorrentParser
from ccbt.discovery.flooding import ControlledFlooding
from ccbt.discovery.lpd import LocalPeerDiscovery
from ccbt.discovery.pex import AsyncPexManager, PexPeer
from ccbt.discovery.tracker import AsyncTrackerClient
from ccbt.discovery.xet_bloom import XetChunkBloomFilter
from ccbt.discovery.xet_cas import P2PCASClient
from ccbt.discovery.xet_catalog import XetChunkCatalog
from ccbt.discovery.xet_gossip import XetGossipManager
from ccbt.discovery.xet_multicast import XetMulticastBroadcaster
from ccbt.extensions.xet_metadata import XetMetadataExchange
from ccbt.models import AddXetFolderResult, TorrentCheckpoint
from ccbt.models import TorrentInfo as TorrentInfoModel
from ccbt.monitoring import get_metrics_collector
from ccbt.piece.file_selection import FileSelectionManager
from ccbt.security.xet_allowlist import XetAllowlist
from ccbt.services.peer_service import PeerService
from ccbt.session.announce import AnnounceLoop
from ccbt.session.checkpoint_operations import CheckpointOperations
from ccbt.session.checkpointing import CheckpointController
from ccbt.session.download_manager import AsyncDownloadManager
from ccbt.session.lifecycle import LifecycleController
from ccbt.session.magnet_handling import MagnetHandler
from ccbt.session.manager_background import ManagerBackgroundTasks
from ccbt.session.media_stream_manager import MediaStreamManager
from ccbt.session.metrics_status import StatusLoop
from ccbt.session.models import SessionContext
from ccbt.session.peer_events import PeerEventsBinder
from ccbt.session.peers import PeerConnectionHelper, PeerManagerInitializer, PexBinder
from ccbt.session.scrape import ScrapeManager
from ccbt.session.status_aggregation import StatusAggregator
from ccbt.session.tasks import TaskSupervisor
from ccbt.session.torrent_addition import TorrentAdditionHandler
from ccbt.session.torrent_utils import get_torrent_info
from ccbt.session.xet_folder_runtime import XetFolderRuntime
from ccbt.session.xet_metadata_resolver import XetMetadataResolver
from ccbt.storage.checkpoint import CheckpointManager
from ccbt.storage.xet_folder_manager import XetFolder
from ccbt.utils.compat import sha1_compat
from ccbt.utils.events import Event, EventType, emit_event
from ccbt.utils.logging_config import get_logger
from ccbt.utils.metrics import Metrics
from ccbt.session.swarm_stability_defaults import PEER_DISCOVERY_DEFAULTS

# Expose TorrentParser at module level for test patching
TorrentParser = _TorrentParser

# Constants
INFO_HASH_LENGTH = 20  # SHA-1 hash length in bytes


class XetTransportState(TypedDict, total=False):
    """Typed structure for XET transport state used in handshake and IPC."""

    workspace_id: Any
    workspace_id_hex: str
    sync_mode: str
    git_ref: Optional[str]
    allowlist_hash: Optional[str]
    source_peers: list[tuple[str, int]]
    hash_algorithm: str
    auth_scope: str
    allowlist_path: Optional[str]
    require_signed_metadata: bool
    backend_status: dict[str, Any]
    allowlist: Optional[Any]
    downgrade_reason: Optional[str]
    backend_eligibility: dict[str, bool]


@dataclass
class TorrentSessionInfo:
    """Information about a torrent session."""

    info_hash: bytes
    name: str
    output_dir: str
    added_time: float
    status: str = "stopped"  # starting, downloading, seeding, stopped, error
    priority: Optional[str] = (
        None  # Queue priority (TorrentPriority enum value as string)
    )
    queue_position: Optional[int] = (
        None  # Position in queue (0 = highest priority position)
    )


class AsyncTorrentSession:
    """Represents one active torrent's lifecycle with async operations."""

    def __init__(
        self,
        torrent_data: Union[dict[str, Any], TorrentInfoModel],
        output_dir: Union[str, Path] = ".",
        session_manager: Optional[AsyncSessionManager] = None,
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
        self.file_selection_manager: Optional[FileSelectionManager] = None
        self.ensure_file_selection_manager()

        # Note: Pass session_manager to AsyncTrackerClient
        # This ensures it uses the daemon's initialized UDP tracker client
        # instead of creating a new one, preventing WinError 10048
        self.tracker = AsyncTrackerClient()
        # Store session_manager reference so tracker can use initialized UDP client
        if session_manager:
            self.tracker._session_manager = session_manager  # type: ignore[attr-defined]

        # Note: Register immediate connection callback for tracker responses
        # This connects peers IMMEDIATELY when tracker responses arrive, before announce loop
        # Note: Callback will be registered in start() after components are initialized
        self.pex_manager: Optional[AsyncPexManager] = None
        self.checkpoint_manager = CheckpointManager(self.config.disk)

        # Initialize checkpoint controller (will be fully initialized after ctx is created)
        self.checkpoint_controller: Optional[CheckpointController] = None

        # Note: Timestamp to track when tracker peers are being connected
        # This prevents DHT from starting until tracker connections complete
        # Use timestamp instead of boolean to handle multiple concurrent callbacks
        self._tracker_peers_connecting_until: Optional[float] = None  # type: ignore[attr-defined]
        self._tracker_immediate_connection_cooldown_until: Optional[float] = None
        self._tracker_immediate_connect_burst_per_source = 12
        self._tracker_immediate_connect_burst_total = 24
        self._last_tracker_metadata_fallback_at: float = 0.0
        self._tracker_metadata_fallback_in_progress: bool = False
        self._piece_map_revalidated_after_metadata: bool = False
        self._low_peers_since: Optional[float] = None
        self._low_peers_lock = asyncio.Lock()
        self._low_peer_recovery_suppressed_until: float = 0.0

        # Task tracking for piece verification and download completion
        # These are sets to track asyncio tasks and prevent garbage collection
        self._piece_verified_tasks: set[asyncio.Task[None]] = set()
        self._download_complete_tasks: set[asyncio.Task[None]] = set()

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

        # Note: Normalize info_hash to exactly 20 bytes (SHA-1 length)
        # Truncate if too long, pad with zeros if too short, and log warnings
        if isinstance(info_hash, str):
            # Convert hex string to bytes
            try:
                info_hash = bytes.fromhex(info_hash)
            except ValueError as e:
                self.logger.exception("Invalid info_hash hex string: %s", info_hash)
                msg = f"Invalid info_hash hex string: {info_hash}"
                raise ValueError(msg) from e

        if not isinstance(info_hash, bytes):
            error_msg = f"info_hash must be bytes, got {type(info_hash)}"
            self.logger.error(error_msg)
            raise TypeError(error_msg)

        original_length = len(info_hash)
        if original_length > INFO_HASH_LENGTH:
            # Truncate to 20 bytes and log warning
            self.logger.warning(
                "info_hash too long (%d bytes), truncating to %d bytes",
                original_length,
                INFO_HASH_LENGTH,
            )
            info_hash = info_hash[:INFO_HASH_LENGTH]
        elif original_length < INFO_HASH_LENGTH:
            # Pad with zeros to 20 bytes and log warning
            self.logger.warning(
                "info_hash too short (%d bytes), padding with zeros to %d bytes",
                original_length,
                INFO_HASH_LENGTH,
            )
            info_hash = info_hash + b"\x00" * (INFO_HASH_LENGTH - original_length)

        # Track announce count for aggressive initial discovery
        self._announce_count = 0

        self.info = TorrentSessionInfo(
            info_hash=info_hash,
            name=name,
            output_dir=str(output_dir),
            added_time=time.time(),
        )

        # Source tracking for checkpoint metadata
        self.torrent_file_path: Optional[str] = None
        self.magnet_uri: Optional[str] = None

        # Background tasks
        self._task_supervisor = TaskSupervisor()
        self._announce_task: Optional[asyncio.Task[None]] = None
        self._status_task: Optional[asyncio.Task[None]] = None
        self._checkpoint_task: Optional[asyncio.Task[None]] = None
        self._seeding_stats_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._stopped = False  # Flag for incoming peer queue processor

        # Note: Initialize incoming peer handler and queue
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
        self._incoming_queue_task: Optional[asyncio.Task[None]] = None

        # Checkpoint state
        self.checkpoint_loaded = False
        self.resume_from_checkpoint = False

        # Callbacks
        self.on_status_update: Optional[Callable[[dict[str, Any]], None]] = None
        self.on_complete: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None

        # Cached status for synchronous property access
        # Updated periodically by _status_loop
        self._cached_status: dict[str, Any] = {}

        # Peer discovery metrics used by PeerConnectionHelper and diagnostics.
        self._peer_discovery_metrics: dict[str, Any] = {
            "peers_discovered_by_source": {
                "tracker": 0,
                "dht": 0,
                "pex": 0,
                "lsd": 0,
                "incoming": 0,
                "unknown": 0,
            },
            "connection_attempts": 0,
            "connection_successes": 0,
            "connection_failures": 0,
            "peers_returned_by_source": {
                "tracker": 0,
                "dht": 0,
                "pex": 0,
                "lsd": 0,
                "incoming": 0,
                "unknown": 0,
            },
            "peers_converted_to_attempts_by_source": {
                "tracker": 0,
                "dht": 0,
                "pex": 0,
                "lsd": 0,
                "incoming": 0,
                "unknown": 0,
            },
            "usable_peers_formed_by_source": {
                "tracker": 0,
                "dht": 0,
                "pex": 0,
                "lsd": 0,
                "incoming": 0,
                "unknown": 0,
            },
            "usable_live_peers_by_source": {
                "tracker": 0,
                "dht": 0,
                "pex": 0,
                "lsd": 0,
                "incoming": 0,
                "unknown": 0,
            },
            "payload_capable_live_peers_by_source": {
                "tracker": 0,
                "dht": 0,
                "pex": 0,
                "lsd": 0,
                "incoming": 0,
                "unknown": 0,
            },
            "metadata_starvation_started_at": 0.0,
            "metadata_starvation_seconds": 0.0,
            "last_peer_discovery_time": 0.0,
        }

        # Discovery controller is initialized lazily by DHT setup.
        self.discovery_controller = None

        # Extract is_private flag for DHT discovery (BEP 27)
        # Use extract_is_private utility to handle both dict and TorrentInfoModel,
        # including checking info dict for private field
        from ccbt.session.torrent_utils import extract_is_private

        self.is_private = extract_is_private(torrent_data)

        # Per-torrent configuration options (overrides global config for this torrent)
        # These are set via UI or API and applied during session.start()
        # Initialize with global defaults, which can be overridden per-torrent
        self.options: dict[str, Any] = {}
        if self.config.per_torrent_defaults:
            defaults_dict = self.config.per_torrent_defaults.model_dump(
                exclude_none=True
            )
            # Type cast: model_dump() returns dict[str, Any], but type checker may not recognize it
            from typing import cast

            self.options.update(cast("dict[str, Any]", defaults_dict))  # type: ignore[arg-type]

        # Create session context for controllers (composition root)
        # Use normalized torrent_data which is always dict[str, Any]
        self.ctx = SessionContext(
            config=self.config,
            torrent_data=self._normalized_td,
            output_dir=self.output_dir,
            info=self.info,
            session_manager=self.session_manager,
            logger=self.logger,
            piece_manager=self.piece_manager,
            peer_manager=None,  # Set later in start()
            tracker=self.tracker,
            dht_client=None,  # Set later if DHT initialized
            checkpoint_manager=self.checkpoint_manager,
            download_manager=self.download_manager,
            file_selection_manager=self.file_selection_manager,
        )
        # Initialize lifecycle controller for start/pause/resume/stop sequencing
        self.lifecycle_controller = LifecycleController(self.ctx, self._task_supervisor)
        # Initialize status aggregator
        self.status_aggregator = StatusAggregator(self)

        # Initialize checkpoint controller
        self.checkpoint_controller = CheckpointController(
            self.ctx, self._task_supervisor, self.checkpoint_manager
        )

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

    def apply_per_torrent_options(self) -> None:
        """Apply per-torrent configuration options (public API).

        This is a public wrapper around _apply_per_torrent_options() to allow
        external code (e.g., session adapters) to apply options without accessing
        private members.

        See _apply_per_torrent_options() for implementation details.
        """
        self._apply_per_torrent_options()

    def ensure_file_selection_manager(self) -> bool:
        """Ensure file selection manager exists and is wired into dependent components."""
        if self.file_selection_manager:
            return True

        torrent_info = get_torrent_info(self.torrent_data, self.logger)
        return self._attach_file_selection_manager(torrent_info)

    def _attach_file_selection_manager(
        self,
        torrent_info: Optional[TorrentInfoModel],
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
                                "info_hash": self.info.info_hash.hex()
                                if hasattr(self, "info") and self.info
                                else "",
                                "name": torrent_info.name
                                if hasattr(torrent_info, "name")
                                else "",
                                "file_count": len(files),
                                "total_size": torrent_info.total_length
                                if hasattr(torrent_info, "total_length")
                                else 0,
                                "files": [f.model_dump() for f in files],
                            },
                        )
                    )
                )
            except Exception as e:
                self.logger.debug("Failed to emit METADATA_READY event: %s", e)

        return True

    def _get_torrent_info(
        self,
        torrent_data: Union[dict[str, Any], TorrentInfoModel],
    ) -> Optional[TorrentInfoModel]:
        """Get TorrentInfo from torrent data.

        Args:
            torrent_data: Torrent data in dict or TorrentInfoModel format

        Returns:
            TorrentInfoModel if conversion successful, None otherwise

        """
        return get_torrent_info(torrent_data, self.logger)

    async def _apply_magnet_file_selection_if_needed(self) -> None:
        """Apply file selection from magnet URI indices if available (BEP 53).

        This method recreates the file selection manager if it's missing and applies
        file selection from magnet_info. It skips single-file torrents.
        """
        # Check if magnet_info exists
        if not hasattr(self, "magnet_info") or not self.magnet_info:
            return

        # Get torrent info to check file count
        torrent_info = get_torrent_info(self.torrent_data, self.logger)
        if not torrent_info or not torrent_info.files:
            return

        # Skip single-file torrents (no selection needed)
        num_files = len(torrent_info.files)
        if num_files <= 1:
            return

        # Note: Recreate file selection manager if missing
        # This can happen when metadata is fetched after session creation
        if not self.file_selection_manager:
            # Recreate from current torrent_data
            torrent_info = get_torrent_info(self.torrent_data, self.logger)
            if torrent_info:
                self._attach_file_selection_manager(torrent_info)

        # Ensure file selection manager exists
        if not self.file_selection_manager:
            return

        # Apply magnet file selection using MagnetHandler

        magnet_handler = MagnetHandler(self)
        await magnet_handler.apply_file_selection()

    async def apply_magnet_file_selection_if_needed(self) -> None:
        """Apply file selection from magnet URI (BEP 53). Public API for DHT/session callers."""
        await self._apply_magnet_file_selection_if_needed()

    def _normalize_torrent_data(
        self,
        td: Union[dict[str, Any], TorrentInfoModel],
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

            # Note: Rebuild invalid pieces_info from legacy fields
            # Check if pieces_info exists but is invalid (missing required fields)
            if pieces_info is not None:
                if (
                    not isinstance(pieces_info, dict)
                    or not all(
                        key in pieces_info
                        for key in ["piece_hashes", "piece_length", "num_pieces"]
                    )
                ) and ("pieces" in td and "piece_length" in td and "num_pieces" in td):
                    # Rebuild from available legacy data
                    result["pieces_info"] = {
                        "piece_hashes": td.get(
                            "pieces",
                            pieces_info.get("piece_hashes", [])
                            if isinstance(pieces_info, dict)
                            else [],
                        ),
                        "piece_length": td.get(
                            "piece_length",
                            pieces_info.get("piece_length", 0)
                            if isinstance(pieces_info, dict)
                            else 0,
                        ),
                        "num_pieces": td.get(
                            "num_pieces",
                            pieces_info.get("num_pieces", 0)
                            if isinstance(pieces_info, dict)
                            else 0,
                        ),
                        "total_length": td.get(
                            "total_length",
                            pieces_info.get("total_length", 0)
                            if isinstance(pieces_info, dict)
                            else 0,
                        ),
                    }
            elif (
                not pieces_info
                and "pieces" in td
                and "piece_length" in td
                and "num_pieces" in td
            ):
                # Build pieces_info from legacy fields
                result["pieces_info"] = {
                    "piece_hashes": td.get("pieces", []),
                    "piece_length": td.get("piece_length", 0),
                    "num_pieces": td.get("num_pieces", 0),
                    "total_length": td.get("total_length", 0),
                }

            if not file_info:
                # Try to get total_length from pieces_info first, then top level
                total_length = 0
                if pieces_info and isinstance(pieces_info, dict):
                    total_length = pieces_info.get("total_length", 0)
                if total_length == 0:
                    total_length = td.get("total_length", 0)
                result.setdefault(
                    "file_info",
                    {"total_length": total_length},
                )
            return result
        # TorrentInfoModel
        result = {
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
        # Preserve tracker-related fields if they exist in TorrentInfoModel
        if hasattr(td, "announce") and td.announce:
            result["announce"] = td.announce
        if hasattr(td, "announce_list") and td.announce_list:
            result["announce_list"] = td.announce_list
        # Note: Preserve v2 fields (BEP 52) if present
        if hasattr(td, "meta_version") and td.meta_version:
            result["meta_version"] = td.meta_version
        if hasattr(td, "piece_layers") and td.piece_layers:
            result["piece_layers"] = td.piece_layers
        if hasattr(td, "file_tree") and td.file_tree:
            result["file_tree"] = td.file_tree
        return result

    def _should_prompt_for_resume(self) -> bool:
        """Determine if we should prompt user for resume."""
        # Only prompt if auto_resume is disabled and we're in interactive mode
        return not self.config.disk.auto_resume

    def _validate_announce_urls(self) -> bool:
        """Validate that torrent has at least one announce URL.

        For magnet links, allow starting even without announce URLs since they
        can use DHT for peer discovery. Regular torrents require at least one tracker.

        Returns:
            True if at least one announce URL is present, or if it's a magnet link, False otherwise

        """
        torrent_data = self._normalized_td

        # Note: Allow magnet links to start without announce URLs
        # Magnet links can use DHT for peer discovery even without trackers
        is_magnet = torrent_data.get("is_magnet", False)
        if is_magnet:
            # Magnet links can proceed without announce URLs (will use DHT)
            # But if they have trackers, validate them
            pass  # Continue to validation below, but don't fail if empty

        # Check for single announce URL
        announce = torrent_data.get("announce")
        if announce and isinstance(announce, str) and announce.strip():
            return True

        # Check for announce_list (BEP 12 format: list[list[str]])
        announce_list = torrent_data.get("announce_list")
        if announce_list and isinstance(announce_list, list):
            # Check if it's a list of lists (BEP 12 format)
            if len(announce_list) > 0:
                for tier in announce_list:
                    if isinstance(tier, list) and len(tier) > 0:
                        # Check if any URL in this tier is non-empty
                        for url in tier:
                            if isinstance(url, str) and url.strip():
                                return True
                    elif isinstance(tier, str) and tier.strip():
                        # Flat list format (legacy)
                        return True
            # Check if it's a flat list of strings (legacy format)
            for url in announce_list:
                if isinstance(url, str) and url.strip():
                    return True

        # If it's a magnet link, allow starting without announce URLs (DHT will be used)
        return bool(is_magnet)

    async def start(self, resume: bool = False) -> None:
        """Start the async torrent session."""
        try:
            self.info.status = "starting"

            # Note: Validate announce URLs before starting
            # This prevents session from getting stuck in 'starting' state
            if not self._validate_announce_urls():
                error_msg = (
                    f"Cannot start session for '{self.info.name}': "
                    "No announce URL in torrent data. "
                    "Torrent must have at least one tracker URL to connect to peers."
                )
                self.logger.error(error_msg)
                self.info.status = "error"
                raise ValueError(error_msg)

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

            # Note: Register immediate connection callback AFTER tracker is started
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

            # Note: Initialize peer manager early, even without peers
            # This ensures _peer_manager is set on piece manager before piece selection starts
            # The peer manager can wait for peers to arrive from tracker/DHT/PEX
            if (
                not hasattr(self.download_manager, "peer_manager")
                or self.download_manager.peer_manager is None
            ):
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

                # Ensure normalized torrent_data is set on download_manager
                self.download_manager.torrent_data = td_for_peer

                try:
                    self.logger.debug(
                        "Initializing peer manager for torrent: %s", self.info.name
                    )

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

                    # Use PeerManagerInitializer to create and bind peer manager
                    initializer = PeerManagerInitializer()
                    peer_manager = await initializer.init_and_bind(
                        self.download_manager,
                        is_private=is_private,
                        session_ctx=self.ctx,
                        on_peer_connected=getattr(
                            self.download_manager, "_on_peer_connected", None
                        ),
                        on_peer_disconnected=getattr(
                            self.download_manager, "_on_peer_disconnected", None
                        ),
                        on_piece_received=getattr(
                            self.download_manager, "_on_piece_received", None
                        ),
                        on_bitfield_received=getattr(
                            self.download_manager, "_on_bitfield_received", None
                        )
                        or (
                            getattr(self, "_on_peer_bitfield_received", None)
                            if hasattr(self, "_on_peer_bitfield_received")
                            else None
                        ),
                        logger=self.logger,
                        max_peers_per_torrent=max_peers,
                    )

                    # Note: Set default bitfield handler if no callback was set
                    if (
                        not hasattr(peer_manager, "on_bitfield_received")
                        or peer_manager.on_bitfield_received is None
                    ):

                        def _default_bitfield_handler(connection, message):
                            if hasattr(self.download_manager, "_on_bitfield_received"):
                                callback = self.download_manager._on_bitfield_received
                                if callable(callback):
                                    result = callback(connection, message)  # type: ignore[call-arg]
                                    if asyncio.iscoroutine(result):
                                        asyncio.create_task(result)  # noqa: RUF006 - Fire-and-forget callback

                        peer_manager.on_bitfield_received = _default_bitfield_handler  # type: ignore[assignment]

                    # Note: Set _peer_manager on piece manager immediately
                    # This allows piece selection to work even before peers are connected
                    self.piece_manager._peer_manager = peer_manager  # type: ignore[attr-defined]

                    # ctx.peer_manager is already set by PeerEventsBinder in init_and_bind
                    self.logger.info(
                        "Peer manager initialized early (waiting for peers from tracker/DHT/PEX)"
                    )
                    extension_manager = getattr(self, "extension_manager", None)
                    if (
                        extension_manager is not None
                        and getattr(peer_manager, "is_peer_xet_authorized", None)
                        is not None
                    ):
                        extension_manager._xet_auth_check = (
                            peer_manager.is_peer_xet_authorized
                        )

                    # Note: Set up callbacks BEFORE starting download using PeerEventsBinder
                    # This ensures callbacks are available when download operations start
                    # Use PeerEventsBinder for consistent event binding
                    binder = PeerEventsBinder(self.ctx)

                    # Wrap async callbacks for sync callback interface
                    def _wrap_piece_verified(piece_index: int):
                        """Wrap async _on_piece_verified for sync callback."""
                        task: asyncio.Task[None] = asyncio.create_task(
                            self._on_piece_verified(piece_index)
                        )
                        # Keep reference to prevent garbage collection
                        self._piece_verified_tasks.add(task)  # type: ignore[assignment]
                        task.add_done_callback(self._piece_verified_tasks.discard)

                    def _wrap_download_complete():
                        """Wrap async _on_download_complete for sync callback."""
                        task: asyncio.Task[None] = asyncio.create_task(
                            self._on_download_complete()
                        )
                        # Keep reference to prevent garbage collection
                        self._download_complete_tasks.add(task)  # type: ignore[assignment]
                        task.add_done_callback(self._download_complete_tasks.discard)

                    # Bind piece manager callbacks using PeerEventsBinder
                    if self.piece_manager:
                        # Type cast: AsyncPieceManager implements PieceManagerProtocol
                        from typing import cast

                        binder.bind_piece_manager(
                            cast("PieceManagerProtocol", self.piece_manager),
                            on_piece_verified=_wrap_piece_verified,
                            on_download_complete=_wrap_download_complete,
                        )

                    # Also set on download_manager for compatibility
                    self.download_manager.on_download_complete = (
                        self._on_download_complete
                    )
                    # Type ignore: on_piece_verified is a dynamic attribute on download_manager
                    self.download_manager.on_piece_verified = _wrap_piece_verified  # type: ignore[attr-defined]

                    # Note: Initialize web seeds from magnet link (ws= parameters)
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
                                    if (
                                        isinstance(web_seed_url, str)
                                        and web_seed_url.strip()
                                    ):
                                        # Validate URL format
                                        if web_seed_url.startswith(
                                            ("http://", "https://")
                                        ):
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

                    # Note: Start piece manager download with peer manager
                    # This sets is_downloading=True and allows piece selection to work
                    # Note: For magnet links, this may set is_downloading=True even if num_pieces=0
                    # This is intentional - allows piece selector to be ready when metadata arrives
                    self.logger.debug("Starting piece manager download")
                    await self.piece_manager.start_download(peer_manager)
                    setattr(self.download_manager, "_started", True)  # noqa: B010
                    setattr(self.download_manager, "_download_started", True)  # noqa: B010
                    if self.info.status == "starting":
                        self.info.status = "downloading"
                    self.logger.info(
                        "Piece manager download started (is_downloading=%s, num_pieces=%d, waiting for peers)",
                        self.piece_manager.is_downloading,
                        self.piece_manager.num_pieces,
                    )
                except Exception:
                    self.logger.exception("Failed to initialize peer manager early")
                    # Continue without early initialization - will be created when peers arrive
                    # Don't re-raise - allow session to start even if peer manager init fails

            # Set up callbacks (if not already set above) using PeerEventsBinder
            # Use PeerEventsBinder for consistent event binding
            if self.piece_manager:
                binder = PeerEventsBinder(self.ctx)

                # Wrap async callbacks for sync callback interface
                def _wrap_piece_verified(piece_index: int):
                    """Wrap async _on_piece_verified for sync callback."""
                    task: asyncio.Task[None] = asyncio.create_task(
                        self._on_piece_verified(piece_index)
                    )
                    # Keep reference to prevent garbage collection
                    self._piece_verified_tasks.add(task)  # type: ignore[assignment]
                    task.add_done_callback(self._piece_verified_tasks.discard)

                def _wrap_download_complete():
                    """Wrap async _on_download_complete for sync callback."""
                    task: asyncio.Task[None] = asyncio.create_task(
                        self._on_download_complete()
                    )
                    # Keep reference to prevent garbage collection
                    self._download_complete_tasks.add(task)  # type: ignore[assignment]
                    task.add_done_callback(self._download_complete_tasks.discard)

                # Bind piece manager callbacks using PeerEventsBinder (only if not already set)
                if (
                    not hasattr(self.piece_manager, "on_piece_verified")
                    or self.piece_manager.on_piece_verified is None
                ):
                    from typing import cast

                    binder.bind_piece_manager(
                        cast("PieceManagerProtocol", self.piece_manager),
                        on_piece_verified=_wrap_piece_verified,
                        on_download_complete=_wrap_download_complete,
                    )

            # Also set on download_manager for compatibility
            if (
                not hasattr(self.download_manager, "on_download_complete")
                or self.download_manager.on_download_complete is None
            ):
                self.download_manager.on_download_complete = self._on_download_complete
            if (
                not hasattr(self.download_manager, "on_piece_verified")
                or self.download_manager.on_piece_verified is None
            ):

                def _wrap_piece_verified_dm(piece_index: int):
                    """Wrap async _on_piece_verified for sync callback."""
                    task: asyncio.Task[None] = asyncio.create_task(
                        self._on_piece_verified(piece_index)
                    )
                    # Keep reference to prevent garbage collection
                    self._piece_verified_tasks.add(task)  # type: ignore[assignment]
                    task.add_done_callback(self._piece_verified_tasks.discard)

                # Type ignore: on_piece_verified is a dynamic attribute on download_manager
                self.download_manager.on_piece_verified = _wrap_piece_verified_dm  # type: ignore[attr-defined]

            # Set up checkpoint callback
            if self.config.disk.checkpoint_enabled and self.checkpoint_controller:
                self.checkpoint_controller.bind_piece_manager_checkpoint_hook()

            # Handle resume from checkpoint
            if self.resume_from_checkpoint and checkpoint:
                await self._resume_from_checkpoint(checkpoint)

            # Start PEX manager if enabled
            if self.config.discovery.enable_pex:
                pex_binder = PexBinder()
                await pex_binder.bind_and_start(self)

            # DHT initialization: init only when config enables DHT and either the user
            # explicitly requested DHT (e.g. --enable-dht) or this is a magnet link.
            # This avoids silently enabling DHT for every .torrent when enable_dht=True.
            dht_explicitly_requested = getattr(self, "options", {}).get(
                "enable_dht", False
            )
            is_magnet_link = isinstance(
                self.torrent_data, dict
            ) and self.torrent_data.get("is_magnet", False)

            # CRITICAL: Hydrate from trackers first - run DHT setup in background so we don't
            # block session start. Tracker announces can start immediately and peers connect
            # while DHT bootstraps; status transitions to "downloading" without waiting for DHT.
            allow_dht_recovery_fallback = getattr(
                self.config.discovery,
                "enable_dht_recovery_fallback",
                True,
            )
            should_init_dht = (
                self.config.discovery.enable_dht
                and self.session_manager
                and (
                    dht_explicitly_requested
                    or is_magnet_link
                    or (allow_dht_recovery_fallback and not self.is_private)
                )
            )
            if should_init_dht:

                async def _dht_setup_background() -> None:
                    try:
                        from ccbt.session.dht_setup import DHTDiscoverySetup

                        dht_setup = DHTDiscoverySetup(self)
                        await dht_setup.setup_dht_discovery()
                        self._dht_setup = dht_setup
                        self._handle_magnet_metadata_exchange = (
                            dht_setup._handle_magnet_metadata_exchange
                        )
                        if self.session_manager and self.session_manager.dht_client:
                            self.ctx.dht_client = self.session_manager.dht_client
                        self.logger.info(
                            "DHT discovery initialized (config enabled; explicit=%s, magnet=%s)",
                            dht_explicitly_requested,
                            is_magnet_link,
                        )
                    except Exception as dht_error:
                        self.logger.warning(
                            "Failed to set up DHT peer discovery: %s (peer discovery may be limited)",
                            dht_error,
                        )
                        self._dht_setup = None
                        self._handle_magnet_metadata_exchange = None

                self._dht_setup = None
                self._handle_magnet_metadata_exchange = None
                self._task_supervisor.create_task(
                    _dht_setup_background(), name="dht_setup_background"
                )
                self.logger.info(
                    "DHT setup running in background (tracker-first: download ready, announces will start immediately)"
                )
            else:
                self._dht_setup = None
                self._handle_magnet_metadata_exchange = None

            # Note: Start incoming peer queue processor
            # This processes queued incoming connections when peer manager isn't ready yet
            self._incoming_queue_task = self._task_supervisor.create_task(
                self._incoming_peer_handler.run_queue_processor(),
                name="incoming_queue_processor",
            )

            # Note: Set up event handler for peer_count_low events
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
                        active_peer_count = event_data.get("active_peer_count")
                        if active_peer_count is None:
                            active_peer_count = event_data.get("active_peers", 0)

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

                        swarm_state = await self.session._get_swarm_recovery_state()
                        metadata_incomplete = bool(swarm_state["metadata_incomplete"])
                        active_peer_count = int(swarm_state["active_peers"])
                        productive_peers = int(swarm_state["productive_peers"])
                        requestable_peers = int(swarm_state["requestable_peers"])
                        peers_with_piece_info = int(
                            swarm_state["peers_with_piece_info"]
                        )
                        active_block_requests = int(
                            swarm_state["active_block_requests"]
                        )
                        self.session.logger.info(
                            "peer_count_low recovery state: active=%d, productive=%d, requestable=%d, piece_info=%d, active_requests=%d, metadata_incomplete=%s",
                            active_peer_count,
                            productive_peers,
                            requestable_peers,
                            peers_with_piece_info,
                            active_block_requests,
                            metadata_incomplete,
                        )
                        fast_recovery = self.session._swarm_requires_fast_recovery(
                            swarm_state
                        )

                        min_peers_before_dht = getattr(
                            self.session.config.discovery,
                            "min_peers_before_dht",
                            10,
                        )
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
                        low_peer_threshold = self.session._low_peer_threshold()
                        low_peer_window = self.session._low_peer_suppression_window_s()
                        low_peer_state = (
                            not metadata_incomplete
                            and active_peer_count <= low_peer_threshold
                        )
                        if low_peer_state and low_peer_window > 0.0:
                            low_peer_recovery_now = time.time()
                            if (
                                low_peer_recovery_now
                                < self.session._low_peer_recovery_suppressed_until
                            ):
                                self.session.logger.debug(
                                    "🧱 DHT SKIP: Low-peer recovery for %s is suppressed for %.1fs more",
                                    self.session.info.name,
                                    self.session._low_peer_recovery_suppressed_until
                                    - low_peer_recovery_now,
                                )
                                return
                        fail_fast_triggered = False
                        current_time = time.monotonic()
                        if (
                            enable_fail_fast
                            and active_peer_count < min_peers_before_dht
                            and not metadata_incomplete
                        ):
                            async with self.session._low_peers_lock:
                                if self.session._low_peers_since is None:
                                    self.session._low_peers_since = current_time
                                    self.session.logger.debug(
                                        "Recording low peers timestamp (DHT will trigger after %.1fs if still < %d peers)",
                                        fail_fast_timeout,
                                        min_peers_before_dht,
                                    )

                        # Note: Wait for connection batches to complete before starting DHT
                        # User requirement: "peer count low checks should only start basically after the first batches of connections are exhausted"
                        # Check if connection batches are currently in progress
                        if (
                            hasattr(self.session, "download_manager")
                            and self.session.download_manager
                        ):
                            peer_manager = getattr(
                                self.session.download_manager, "peer_manager", None
                            )
                            if peer_manager:
                                connection_batches_in_progress = getattr(
                                    peer_manager,
                                    "_connection_batches_in_progress",
                                    False,
                                )
                                if connection_batches_in_progress:
                                    self.session.logger.info(
                                        "⏸️ DHT DELAY: Connection batches are in progress. Waiting for batches to complete before starting DHT..."
                                    )
                                    max_wait = self.session._recovery_wait_budget(
                                        swarm_state,
                                        base_wait=15.0,
                                        fast_wait=min(fail_fast_timeout, 2.0),
                                    )
                                    check_interval = 2.0
                                    waited = 0.0
                                    while waited < max_wait:
                                        await asyncio.sleep(check_interval)
                                        waited += check_interval
                                        connection_batches_in_progress = getattr(
                                            peer_manager,
                                            "_connection_batches_in_progress",
                                            False,
                                        )
                                        active_peer_count_during_wait = (
                                            active_peer_count
                                        )
                                        if hasattr(peer_manager, "get_active_peers"):
                                            with contextlib.suppress(Exception):
                                                active_peer_count_during_wait = len(
                                                    peer_manager.get_active_peers()
                                                )
                                        swarm_state = await self.session._get_swarm_recovery_state()
                                        fast_recovery = (
                                            self.session._swarm_requires_fast_recovery(
                                                swarm_state
                                            )
                                        )
                                        if (
                                            connection_batches_in_progress
                                            and active_peer_count_during_wait == 0
                                        ):
                                            self.session.logger.warning(
                                                "⏸️ DHT DELAY: Connection batches are still marked in progress but no active peers remain after %.1fs. Proceeding with DHT recovery now.",
                                                waited,
                                            )
                                            break
                                        if (
                                            connection_batches_in_progress
                                            and fast_recovery
                                        ):
                                            self.session.logger.warning(
                                                "⏸️ DHT DELAY: Connection batches still in progress after %.1fs but swarm remains degraded (active=%d, productive=%d, requestable=%d, piece_info=%d). Proceeding with DHT recovery now.",
                                                waited,
                                                int(swarm_state.get("active_peers", 0)),
                                                int(
                                                    swarm_state.get(
                                                        "productive_peers", 0
                                                    )
                                                ),
                                                int(
                                                    swarm_state.get(
                                                        "requestable_peers", 0
                                                    )
                                                ),
                                                int(
                                                    swarm_state.get(
                                                        "peers_with_piece_info", 0
                                                    )
                                                ),
                                            )
                                            break
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

                        # Note: Also check tracker peer connection timestamp (secondary check)
                        # This ensures we wait for tracker responses to be processed
                        import time as time_module

                        tracker_peers_connecting_until = getattr(
                            self.session, "_tracker_peers_connecting_until", None
                        )
                        if (
                            tracker_peers_connecting_until
                            and time_module.time() < tracker_peers_connecting_until
                        ):
                            wait_time = (
                                tracker_peers_connecting_until - time_module.time()
                            )
                            capped_wait = (
                                min(wait_time, 1.0)
                                if fast_recovery
                                else min(wait_time, 5.0)
                            )
                            self.session.logger.info(
                                "⏸️ DHT DELAY: Tracker peers are currently being connected. Waiting %.1fs before starting DHT to allow tracker connections to complete...",
                                capped_wait,
                            )
                            await asyncio.sleep(capped_wait)

                        # Check if we have active peers now (tracker connections may have succeeded)
                        if (
                            hasattr(self.session, "download_manager")
                            and self.session.download_manager
                        ):
                            current_active = active_peer_count
                            current_requestable = requestable_peers
                            current_productive = productive_peers
                            current_piece_info = peers_with_piece_info
                            peer_manager = getattr(
                                self.session.download_manager, "peer_manager", None
                            )
                            if peer_manager and hasattr(
                                peer_manager, "get_connection_summary"
                            ):
                                with contextlib.suppress(Exception):
                                    connection_summary = (
                                        await peer_manager.get_connection_summary()
                                    )
                                    current_active = int(
                                        connection_summary.get("active_connections", 0)
                                        or 0
                                    )
                                    current_requestable = int(
                                        connection_summary.get(
                                            "requestable_connections", 0
                                        )
                                        or 0
                                    )
                                    current_productive = int(
                                        connection_summary.get(
                                            "productive_connections", 0
                                        )
                                        or 0
                                    )
                                    current_piece_info = int(
                                        connection_summary.get(
                                            "peers_with_piece_info", 0
                                        )
                                        or 0
                                    )
                            elif peer_manager and hasattr(
                                peer_manager, "get_active_peers"
                            ):
                                current_active = len(peer_manager.get_active_peers())
                            if (
                                current_active > active_peer_count
                                and not metadata_incomplete
                                and (
                                    current_requestable > 0
                                    or current_productive > 0
                                    or current_piece_info > 0
                                )
                            ):
                                self.session.logger.info(
                                    "✅ DHT SKIP: Swarm became more usable after tracker connections (active=%d->%d, requestable=%d, productive=%d, piece_info=%d). Skipping DHT for now.",
                                    active_peer_count,
                                    current_active,
                                    current_requestable,
                                    current_productive,
                                    current_piece_info,
                                )
                                return  # Skip DHT if tracker peers connected successfully
                            if (
                                current_active > active_peer_count
                                and metadata_incomplete
                            ):
                                self.session.logger.info(
                                    "🧲 DHT CONTINUE: Active peer count increased from %d to %d, but metadata is still incomplete. Continuing DHT evaluation.",
                                    active_peer_count,
                                    current_active,
                                )
                            active_peer_count = current_active
                            requestable_peers = current_requestable
                            productive_peers = current_productive
                            peers_with_piece_info = current_piece_info

                        # Degraded-state trigger: low peers (including zero) for > timeout => allow DHT
                        if active_peer_count == 0 and not metadata_incomplete:
                            fail_fast_triggered = True
                            self.session.logger.warning(
                                "🚨 ZERO-PEER DHT: No active peers remain. Bypassing low-peer grace period and triggering immediate DHT recovery."
                            )
                        elif (
                            not metadata_incomplete
                            and peers_with_piece_info == 0
                            and active_block_requests == 0
                        ):
                            fail_fast_triggered = True
                            self.session.logger.warning(
                                "🚨 PIECE-INFO DHT: Active peers exist but none have advertised piece availability (active=%d, productive=%d, requestable=%d). Triggering DHT recovery immediately.",
                                active_peer_count,
                                productive_peers,
                                requestable_peers,
                            )
                        if (
                            enable_fail_fast
                            and active_peer_count < min_peers_before_dht
                        ):
                            if metadata_incomplete:
                                fail_fast_triggered = True
                                self.session.logger.info(
                                    "🧲 DHT FALLBACK: Metadata is still incomplete with only %d active peer(s). Allowing immediate DHT discovery.",
                                    active_peer_count,
                                )
                            elif not fail_fast_triggered:
                                async with self.session._low_peers_lock:
                                    low_peers_since = self.session._low_peers_since
                                    if low_peers_since is None:
                                        self.session._low_peers_since = current_time
                                    else:
                                        time_at_low = current_time - low_peers_since
                                        if time_at_low >= fail_fast_timeout:
                                            fail_fast_triggered = True
                                            self.session.logger.warning(
                                                "🚨 DEGRADED DHT: Active peers (%d) below minimum (%d) for %.1fs. "
                                                "Triggering DHT discovery to prevent stall.",
                                                active_peer_count,
                                                min_peers_before_dht,
                                                time_at_low,
                                            )
                        elif active_peer_count >= min_peers_before_dht:
                            async with self.session._low_peers_lock:
                                self.session._low_peers_since = None
                            self.session._low_peer_recovery_suppressed_until = 0.0

                        if (
                            active_peer_count < min_peers_before_dht
                            and not fail_fast_triggered
                        ):
                            if low_peer_state and low_peer_window > 0.0:
                                self.session._low_peer_recovery_suppressed_until = (
                                    time.time() + low_peer_window
                                )
                            self.session.logger.info(
                                "DHT skip: swarm still below DHT threshold (active=%d, productive=%d, requestable=%d, piece_info=%d; minimum=%d). "
                                "Skipping immediate DHT discovery to avoid blacklisting.",
                                active_peer_count,
                                productive_peers,
                                requestable_peers,
                                peers_with_piece_info,
                                min_peers_before_dht,
                            )
                            return  # Skip DHT until we have minimum peers

                        if (
                            fail_fast_triggered
                            and active_peer_count < min_peers_before_dht
                        ):
                            self.session.logger.info(
                                "Preparing source-tier tracker handoff: trying tracker recovery before DHT fallback (active=%d, productive=%d, requestable=%d, piece_info=%d, threshold=%d)...",
                                active_peer_count,
                                productive_peers,
                                requestable_peers,
                                peers_with_piece_info,
                                min_peers_before_dht,
                            )
                        else:
                            self.session.logger.info(
                                "Preparing source-tier tracker handoff: trying tracker recovery before DHT fallback (active=%d, productive=%d, requestable=%d, piece_info=%d, threshold=%d)...",
                                active_peer_count,
                                productive_peers,
                                requestable_peers,
                                peers_with_piece_info,
                                min_peers_before_dht,
                            )

                        async def immediate_announce() -> bool:
                            """Run immediate tracker batch; return True when tracker source is exhausted."""
                            try:
                                td: dict[str, Any]
                                if isinstance(self.session.torrent_data, TorrentInfoModel):
                                    td = {
                                        "info_hash": self.session.torrent_data.info_hash,
                                        "name": self.session.torrent_data.name,
                                        "announce": getattr(
                                            self.session.torrent_data,
                                            "announce",
                                            "",
                                        ),
                                    }
                                else:
                                    td = self.session.torrent_data

                                tracker_urls = self.session._collect_trackers(td)
                                if not tracker_urls:
                                    self.session.logger.debug(
                                        "Tracker handoff source exhausted: no tracker URLs available for %s",
                                        self.session.info.name,
                                    )
                                    return True

                                listen_port = (
                                    self.session.config.network.listen_port_tcp
                                    or self.session.config.network.listen_port
                                )
                                announce_port = listen_port
                                nat_manager = getattr(
                                    self.session.session_manager, "nat_manager", None
                                )
                                if nat_manager is not None:
                                    with contextlib.suppress(Exception):
                                        external_port = await nat_manager.get_external_port(
                                            listen_port,
                                            "tcp",
                                        )
                                        if external_port is not None:
                                            announce_port = external_port
                                responses = await self.session.tracker.announce_to_multiple(
                                    td,
                                    tracker_urls,
                                    port=announce_port,
                                )
                                aggregated_peers = []
                                for response in responses:
                                    if response and getattr(response, "peers", None):
                                        aggregated_peers.extend(response.peers)
                                if not aggregated_peers:
                                    self.session.logger.info(
                                        "Immediate tracker handoff batch exhausted for %s: %d tracker response(s), %d usable peers",
                                        self.session.info.name,
                                        len(responses),
                                        len(aggregated_peers),
                                    )
                                    return True

                                if not self.session.download_manager:
                                    self.session.logger.warning(
                                        "Skipping immediate tracker connection handoff for %s because download manager is not available",
                                        self.session.info.name,
                                    )
                                    return False

                                peer_manager = getattr(
                                    self.session.download_manager,
                                    "peer_manager",
                                    None,
                                )
                                if peer_manager:
                                    peer_list = [
                                        {
                                            "ip": p.ip,
                                            "port": p.port,
                                            "peer_source": "tracker",
                                        }
                                        for p in aggregated_peers
                                        if hasattr(p, "ip") and hasattr(p, "port")
                                    ]
                                    if peer_list:
                                        helper = PeerConnectionHelper(self.session)
                                        await helper.connect_peers_to_download(peer_list)
                                        self.session.logger.info(
                                            "Immediate tracker handoff returned %d peer(s) across %d successful tracker response(s)",
                                            len(peer_list),
                                            len(responses),
                                        )
                                        return False

                                # Fallback: queue peers for later connection attempts.
                                self.session.logger.warning(
                                    "Immediate tracker handoff queued %d peer(s) for later connection because peer manager is not ready for %s",
                                    len(aggregated_peers),
                                    self.session.info.name,
                                )
                                return False
                            except Exception as e:
                                self.session.logger.debug(
                                    "Failed to perform immediate tracker announce: %s",
                                    e,
                                )
                                return True

                        tracker_batch_exhausted = True
                        if (
                            hasattr(self.session, "_announce_task")
                            and self.session._announce_task
                            and not self.session._announce_task.done()
                        ):
                            tracker_batch_exhausted = await immediate_announce()
                        elif (
                            hasattr(self.session, "_announce_task")
                            and self.session._announce_task
                            and self.session._announce_task.done()
                        ):
                            self.session.logger.debug(
                                "Skipping immediate tracker handoff: announce loop task has completed (periodic announces no longer running)"
                            )

                        if not tracker_batch_exhausted:
                            self.session.logger.info(
                                "Tracker handoff for %s returned usable peers; skipping DHT fallback for this cycle",
                                self.session.info.name,
                            )
                            return

                        # Trigger immediate DHT query if tracker batch was exhausted and DHT is enabled
                        # Note: Rate limit immediate DHT queries to prevent peer disconnections
                        # Check if we've triggered an immediate query recently (within last 60 seconds)
                        current_time = time.time()
                        last_immediate_query_key = f"_last_immediate_dht_query_{self.session.info.info_hash.hex()}"
                        last_immediate_query = getattr(
                            self.session, last_immediate_query_key, 0
                        )
                        min_interval_between_immediate_queries = (
                            low_peer_window
                            if low_peer_state and low_peer_window > 0.0
                            else 60.0  # Increased from 10s to 60s to prevent blacklisting
                        )

                        if (
                            current_time - last_immediate_query
                            < min_interval_between_immediate_queries
                        ):
                            self.session.logger.debug(
                                "Skipping immediate DHT query for %s: too soon after last query (%.1fs ago, min interval: %.1fs)",
                                self.session.info.name,
                                current_time - last_immediate_query,
                                min_interval_between_immediate_queries,
                            )
                            return

                        if (
                            self.session.config.discovery.enable_dht
                            and hasattr(self.session, "_dht_setup")
                            and self.session._dht_setup
                        ):
                            try:
                                dht_client = (
                                    self.session.session_manager.dht_client
                                    if self.session.session_manager
                                    else None
                                )
                                if dht_client:
                                    if (
                                        low_peer_state
                                        and low_peer_window > 0.0
                                    ):
                                        self.session._low_peer_recovery_suppressed_until = (
                                            current_time + low_peer_window
                                        )

                                    # Note: Use very conservative parameters to prevent
                                    # blacklisting while still recovering quickly.
                                    setattr(
                                        self.session,
                                        last_immediate_query_key,
                                        current_time,
                                    )
                                    self.session.logger.info(
                                        "Tracker handoff exhausted for %s; triggering immediate DHT get_peers query (max_peers=50, conservative params to prevent blacklisting)",
                                        self.session.info.name,
                                    )
                                    discovered_peers = await dht_client.get_peers(
                                        self.session.info.info_hash,
                                        max_peers=50,  # Reduced from 100 to prevent overwhelming
                                        alpha=3,  # Reduced from 6 to be more conservative (BEP 5 compliant)
                                        k=8,  # Reduced from 16 to be more conservative (BEP 5 compliant)
                                        max_depth=8,  # Reduced from 12 to be more conservative (BEP 5 compliant)
                                    )
                                    # Note: Immediately connect to discovered peers
                                    if (
                                        discovered_peers
                                        and self.session.download_manager
                                    ):
                                        peer_manager = getattr(
                                            self.session.download_manager,
                                            "peer_manager",
                                            None,
                                        )
                                        if peer_manager:
                                            peer_list = [
                                                {
                                                    "ip": ip,
                                                    "port": port,
                                                    "peer_source": "dht_immediate",
                                                }
                                                for ip, port in discovered_peers[
                                                    :50
                                                ]  # Connect to first 50
                                            ]
                                            if peer_list:
                                                helper = PeerConnectionHelper(
                                                    self.session
                                                )
                                                await helper.connect_peers_to_download(
                                                    peer_list
                                                )
                                                self.session.logger.info(
                                                    "Immediate DHT query returned %d peer(s), connecting to %d",
                                                    len(discovered_peers),
                                                    len(peer_list),
                                                )
                                else:
                                    self.session.logger.warning(
                                        "Immediate DHT query skipped: DHT client is unavailable"
                                    )
                            except Exception as e:
                                self.session.logger.warning(
                                    "Failed to trigger immediate DHT query: %s",
                                    e,
                                    exc_info=True,
                                )

                # Register event handler
                handler = PeerCountLowHandler(self)
                event_bus = get_event_bus()
                event_bus.register_handler("peer_count_low", handler)
                self._peer_count_low_handler = handler  # Store reference for cleanup
            except Exception as e:
                self.logger.debug(
                    "Failed to set up peer_count_low event handler: %s", e
                )
                self._peer_count_low_handler = None

            # Start background tasks with error isolation
            # Note: Wrap task creation to ensure exceptions don't crash the daemon
            # The event loop exception handler will catch any unhandled exceptions in these tasks
            try:
                self.logger.info(
                    "🔍 TRACKER DISCOVERY: Starting tracker announce loop for %s (initial intervals: 60s, 120s, 300s, then adaptive)",
                    self.info.name,
                )
                # Use AnnounceLoop class for periodic tracker announces
                announce_loop = AnnounceLoop(self)
                self._announce_task = self._task_supervisor.create_task(
                    announce_loop.run(), name="announce_loop"
                )
                # Use StatusLoop class for periodic status monitoring
                status_loop = StatusLoop(self)
                self._status_task = self._task_supervisor.create_task(
                    status_loop.run(), name="status_loop"
                )

                # Start checkpoint task if enabled
                if self.config.disk.checkpoint_enabled and self.checkpoint_controller:
                    self._checkpoint_task = (
                        self.checkpoint_controller.start_periodic_loop()
                    )

                # Start seeding stats task if torrent is completed (seeding)
                # Note: For new sessions (especially magnet links), status will be "starting" not "seeding"
                # Only start seeding stats task if status is actually "seeding"
                # Use defensive checks to avoid AttributeError on missing attributes
                try:
                    # Safely check if info exists and has status attribute
                    info_status = None
                    if hasattr(self, "info") and self.info is not None:
                        # Use getattr with default to safely access status
                        info_status = getattr(self.info, "status", None)

                    if info_status == "seeding":
                        self._seeding_stats_task = self._task_supervisor.create_task(
                            self._seeding_stats_loop(), name="seeding_stats_loop"
                        )
                except (AttributeError, TypeError) as attr_error:
                    # If info doesn't have expected attributes, log and continue
                    # This can happen during initialization before all attributes are set
                    self.logger.debug(
                        "Cannot check seeding status (info may not be fully initialized): %s",
                        attr_error,
                    )
            except Exception as task_error:
                # Log error but don't fail session start - tasks will be handled by exception handler
                # Note: Don't re-raise AttributeError for missing attributes on TorrentSessionInfo
                # This can happen during initialization when attributes aren't fully set yet
                if isinstance(task_error, AttributeError) and "progress" in str(
                    task_error
                ):
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

        # Note: Cancel any background start() task that might still be running
        # This prevents the background task from continuing and potentially causing issues during shutdown
        if hasattr(self, "_background_start_task") and self._background_start_task:
            task = self._background_start_task
            if not task.done():
                self.logger.info(
                    "Cancelling background start() task during stop() for %s",
                    self.info.name if hasattr(self, "info") else "unknown",
                )
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass  # Expected when cancelling
                except Exception as cancel_error:
                    self.logger.debug(
                        "Error cancelling background start task during stop: %s",
                        cancel_error,
                    )
            # Clear the reference
            delattr(self, "_background_start_task")

        # Cancel background tasks and await completion
        tasks_to_cancel = []
        if self._incoming_queue_task:
            self._incoming_queue_task.cancel()
            tasks_to_cancel.append(self._incoming_queue_task)
        if hasattr(self, "_metadata_tasks"):
            for metadata_task in list(self._metadata_tasks):
                if metadata_task and not metadata_task.done():
                    metadata_task.cancel()
                    tasks_to_cancel.append(metadata_task)
        # Note: Cancel DHT discovery task to prevent it from continuing during shutdown
        if (
            hasattr(self, "_dht_discovery_task")
            and self._dht_discovery_task
            and not self._dht_discovery_task.done()
        ):
            self._dht_discovery_task.cancel()
            tasks_to_cancel.append(self._dht_discovery_task)
        # Cancel announce, status, and checkpoint tasks if they exist
        for task_attr in ["_announce_task", "_status_task", "_checkpoint_task"]:
            if hasattr(self, task_attr):
                task = getattr(self, task_attr)
                if task and not task.done():
                    task.cancel()
                    tasks_to_cancel.append(task)

        # Use lifecycle controller for task cancellation sequencing
        await self.lifecycle_controller.on_stop(self)

        self._tracker_peers_connecting_until = None
        self._tracker_metadata_fallback_in_progress = False

        # Await other tasks (incoming queue, DHT discovery) with timeout to prevent hanging
        if tasks_to_cancel:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                    timeout=5.0,
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
                if (
                    hasattr(self, "checkpoint_controller")
                    and self.checkpoint_controller
                ):
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

        # Note: Ensure tracker is properly stopped and session is closed
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
                    if (
                        hasattr(self, "checkpoint_controller")
                        and self.checkpoint_controller
                    ):
                        await self.checkpoint_controller.save_checkpoint_state(self)
                    else:
                        await self._save_checkpoint()
                except Exception as e:
                    self.logger.warning("Failed to save checkpoint on pause: %s", e)

            # Stop background tasks
            self._stop_event.set()

            # Use lifecycle controller for task cancellation sequencing
            await self.lifecycle_controller.on_pause(self)

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
            if self.config.disk.checkpoint_enabled and hasattr(
                self, "checkpoint_manager"
            ):
                try:
                    checkpoint = await self.checkpoint_manager.load_checkpoint(
                        self.info.info_hash
                    )
                    if (
                        checkpoint
                        and hasattr(self, "checkpoint_controller")
                        and self.checkpoint_controller
                    ):
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

            # Use lifecycle controller for resume sequencing
            await self.lifecycle_controller.on_resume(self)

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
                    if (
                        hasattr(self, "checkpoint_controller")
                        and self.checkpoint_controller
                    ):
                        await self.checkpoint_controller.save_checkpoint_state(self)
                    else:
                        await self._save_checkpoint()
                except Exception as e:
                    self.logger.warning("Failed to save checkpoint on cancel: %s", e)

            # Stop background tasks
            self._stop_event.set()

            # Use lifecycle controller for task cancellation sequencing
            await self.lifecycle_controller.on_stop(self)

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
                self.logger.info(
                    "Force started (resumed) torrent session: %s", self.info.name
                )
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

        async def immediate_peer_connection(
            peers: list[dict[str, Any]], tracker_url: str
        ) -> None:
            """Immediate peer connection callback - connects peers as soon as they arrive."""
            if not peers or self.is_stopped():
                return

            import time as time_module
            connection_start_time = time_module.time()

            cooldown_until = self._tracker_immediate_connection_cooldown_until
            if cooldown_until is not None and connection_start_time < cooldown_until:
                self.logger.debug(
                    "⚡ IMMEDIATE CONNECTION: In debounce cooldown until %.1fs; skipping %d peer(s) from %s",
                    cooldown_until - connection_start_time,
                    len(peers),
                    tracker_url,
                )
                return

            self.record_discovered_peers(peers, source="tracker")

            # Note: Set timestamp to indicate tracker peers are being connected
            # This prevents DHT from starting until tracker connections complete
            # Use timestamp to handle multiple concurrent callbacks - extend the time if needed
            max_wait_time = 4.0 if self._metadata_is_incomplete() else 2.0
            max_peers_per_torrent = getattr(
                self.config.network, "max_peers_per_torrent", self._tracker_immediate_connect_burst_total
            )
            configured_max_peers = (
                max_peers_per_torrent
                if isinstance(max_peers_per_torrent, int) and max_peers_per_torrent > 0
                else self._tracker_immediate_connect_burst_total
            )
            per_source_limit = min(
                self._tracker_immediate_connect_burst_per_source,
                max(1, configured_max_peers // 4),
            )
            per_torrent_limit = min(
                self._tracker_immediate_connect_burst_total,
                configured_max_peers,
            )

            # If flag is already set, extend it if this callback started later
            if self._tracker_peers_connecting_until is None:  # type: ignore[attr-defined]
                self._tracker_peers_connecting_until = (
                    connection_start_time + max_wait_time
                )  # type: ignore[attr-defined]
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

                    peer_connection_capacity = max(
                        0,
                        configured_max_peers
                        - len(self.download_manager.peer_manager.connections),
                    )
                    if peer_connection_capacity <= 0:
                        self._tracker_immediate_connection_cooldown_until = (
                            connection_start_time + 1.5
                        )
                        self.logger.debug(
                            "⚡ IMMEDIATE CONNECTION: Tracker peer queue saturated for %s (connected=%d, max=%d)",
                            self.info.name,
                            len(self.download_manager.peer_manager.connections),
                            configured_max_peers,
                        )
                        return

                    bounded_peer_list: list[dict[str, Any]] = []
                    source_counts: dict[str, int] = {}
                    for peer in unique_peer_list:
                        source = str(peer.get("peer_source", "tracker") or "tracker")
                        if source_counts.get(source, 0) >= per_source_limit:
                            continue
                        if len(bounded_peer_list) >= per_torrent_limit:
                            break
                        if len(bounded_peer_list) >= peer_connection_capacity:
                            break
                        source_counts[source] = source_counts.get(source, 0) + 1
                        bounded_peer_list.append(peer)

                    unique_peer_list = bounded_peer_list
                    if unique_peer_list:
                        self.logger.info(
                            "⚡ IMMEDIATE CONNECTION: Connecting %d bounded peer(s) immediately for %s",
                            len(unique_peer_list),
                            self.info.name,
                        )
                        try:
                            # Use PeerConnectionHelper for consistent peer connection handling
                            helper = PeerConnectionHelper(self)
                            await helper.connect_peers_to_download(unique_peer_list)
                            self.logger.info(
                                "✅ IMMEDIATE CONNECTION: Started connection attempts for %d peer(s) for %s (connections will continue in background)",
                                len(unique_peer_list),
                                self.info.name,
                            )

                            metadata_incomplete = self._metadata_is_incomplete()
                            severe_metadata_starvation = False
                            with contextlib.suppress(Exception):
                                swarm_state_for_metadata = (
                                    await self._get_swarm_recovery_state()
                                )
                                severe_metadata_starvation = bool(
                                    swarm_state_for_metadata["metadata_incomplete"]
                                    and int(
                                        swarm_state_for_metadata["requestable_peers"]
                                    )
                                    == 0
                                    and int(
                                        swarm_state_for_metadata["productive_peers"]
                                    )
                                    == 0
                                    and int(
                                        swarm_state_for_metadata[
                                            "peers_with_piece_info"
                                        ]
                                    )
                                    == 0
                                )

                            now = time_module.time()
                            fallback_cooldown = 15.0
                            if (
                                metadata_incomplete
                                and not self._tracker_metadata_fallback_in_progress
                                and (
                                    severe_metadata_starvation
                                    or now - self._last_tracker_metadata_fallback_at
                                    >= fallback_cooldown
                                )
                            ):
                                peer_subset = unique_peer_list[
                                    : min(50, len(unique_peer_list))
                                ]
                                self._last_tracker_metadata_fallback_at = now
                                self._tracker_metadata_fallback_in_progress = True

                                async def tracker_metadata_fallback() -> None:
                                    try:
                                        self.logger.info(
                                            "🧲 TRACKER METADATA FALLBACK: Starting standalone metadata fetch against %d tracker peer(s) for %s",
                                            len(peer_subset),
                                            self.info.name,
                                        )
                                        await self.handle_magnet_metadata_exchange(
                                            peer_subset
                                        )
                                    finally:
                                        self._tracker_metadata_fallback_in_progress = (
                                            False
                                        )

                                metadata_task = asyncio.create_task(
                                    tracker_metadata_fallback()
                                )
                                self.add_metadata_task(metadata_task)
                                metadata_task.add_done_callback(
                                    self.remove_metadata_task
                                )

                            # Note: Ensure download starts immediately after connecting peers
                            # This ensures piece requests are sent as soon as connections are established
                            # For magnet links, metadata may have been received, so we need to restart download
                            if hasattr(self, "piece_manager") and self.piece_manager:
                                try:
                                    # Check if metadata is available (num_pieces > 0)
                                    num_pieces = getattr(
                                        self.piece_manager, "num_pieces", 0
                                    )
                                    is_downloading = getattr(
                                        self.piece_manager, "is_downloading", False
                                    )

                                    # If metadata is available and download hasn't started properly, restart it
                                    if num_pieces > 0 and hasattr(
                                        self.piece_manager, "start_download"
                                    ):
                                        self.logger.info(
                                            "🚀 IMMEDIATE CONNECTION: Triggering download start after connecting %d peer(s) (num_pieces=%d, is_downloading=%s)",
                                            len(unique_peer_list),
                                            num_pieces,
                                            is_downloading,
                                        )
                                        # Use peer_manager from download_manager
                                        peer_manager = (
                                            self.download_manager.peer_manager
                                        )  # type: ignore[union-attr]
                                        if asyncio.iscoroutinefunction(
                                            self.piece_manager.start_download
                                        ):
                                            await self.piece_manager.start_download(
                                                peer_manager
                                            )
                                        else:
                                            self.piece_manager.start_download(
                                                peer_manager
                                            )
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

                            swarm_state = await self._get_swarm_recovery_state()
                            if self._swarm_requires_fast_recovery(swarm_state):
                                accelerated_until = time_module.time() + 0.25
                                current_until = self._tracker_peers_connecting_until  # type: ignore[attr-defined]
                                if (
                                    current_until is not None
                                    and accelerated_until < current_until
                                ):
                                    self._tracker_peers_connecting_until = (
                                        accelerated_until  # type: ignore[attr-defined]
                                    )
                                self.logger.info(
                                    "⚡ IMMEDIATE CONNECTION: Tracker peers connected but swarm is still not payload-capable (active=%d, productive=%d, requestable=%d, piece_info=%d). Shortening DHT delay.",
                                    int(swarm_state["active_peers"]),
                                    int(swarm_state["productive_peers"]),
                                    int(swarm_state["requestable_peers"]),
                                    int(swarm_state["peers_with_piece_info"]),
                                )

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
                # Note: Clear flag only if this callback's time has expired
                # This allows multiple callbacks to coordinate properly
                import time as time_module

                if self._tracker_peers_connecting_until:  # type: ignore[attr-defined]
                    if time_module.time() >= self._tracker_peers_connecting_until:  # type: ignore[attr-defined]
                        self._tracker_peers_connecting_until = None  # type: ignore[attr-defined]
                        self._tracker_immediate_connection_cooldown_until = None
                        self.logger.info(
                            "✅ IMMEDIATE CONNECTION: Tracker peer connection wait period expired (flag cleared, DHT can now start if needed)"
                        )
                    else:
                        peer_manager = (
                            getattr(self.download_manager, "peer_manager", None)
                        )
                        batches_active = bool(
                            getattr(peer_manager, "_connection_batches_in_progress", False)
                            if peer_manager
                            else False
                        )
                        if not batches_active:
                            self._tracker_immediate_connection_cooldown_until = (
                                time_module.time() + 1.0
                            )
                        self.logger.debug(
                            "⏸️ IMMEDIATE CONNECTION: Other callbacks still active, keeping flag set until %.1fs",
                            self._tracker_peers_connecting_until - time_module.time(),  # type: ignore[attr-defined]
                        )

        # Register callback on HTTP tracker client
        # Type ignore: immediate_peer_connection is async but tracker handles both sync and async callbacks
        self.tracker.on_peers_received = immediate_peer_connection  # type: ignore[assignment]

        # Register callback on UDP tracker client (via session_manager)
        if self.session_manager and hasattr(self.session_manager, "udp_tracker_client"):
            udp_client = self.session_manager.udp_tracker_client
            if udp_client:
                # Type ignore: immediate_peer_connection is async but tracker handles both sync and async callbacks
                udp_client.on_peers_received = immediate_peer_connection  # type: ignore[assignment]
                self.logger.info(
                    "✅ IMMEDIATE CONNECTION: Registered callback on HTTP and UDP tracker clients for %s",
                    self.info.name,
                )

    async def _announce_loop(self) -> None:
        """Background task for periodic tracker announces with adaptive intervals.

        NOTE: This method is now delegated to AnnounceLoop class.
        Kept for backward compatibility.
        """
        # Delegate to AnnounceLoop class
        announce_loop = AnnounceLoop(self)
        await announce_loop.run()

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
            # Note: Validate tracker URLs - must start with http://, https://, or udp://
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
            if not tracker_url or not tracker_url.startswith(
                ("http://", "https://", "udp://")
            ):
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

            self.logger.info(
                "Added tracker %s to torrent %s", tracker_url, self.info.name
            )
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

            self.logger.info(
                "Removed tracker %s from torrent %s", tracker_url, self.info.name
            )
            return True
        except Exception:
            self.logger.exception("Failed to remove tracker %s", tracker_url)
            return False

    async def _status_loop(self) -> None:
        """Background task for status monitoring.

        NOTE: This method is now delegated to StatusLoop class.
        Kept for backward compatibility.
        """
        # Delegate to StatusLoop class
        status_loop = StatusLoop(self)
        await status_loop.run()

    async def _on_download_complete(self) -> None:
        """Handle download completion."""
        self.info.status = "seeding"
        self.logger.info("Download complete, now seeding: %s", self.info.name)

        # Note: Create file_assembler if it doesn't exist
        # This handles the case where download completes before any pieces were written
        if (
            not hasattr(self.download_manager, "file_assembler")
            or self.download_manager.file_assembler is None
        ):
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

            # Type ignore: file_assembler is a dynamic attribute on download_manager
            self.download_manager.file_assembler = AsyncFileAssembler(  # type: ignore[attr-defined]
                self.torrent_data,
                str(self.output_dir),
            )
            # Initialize file assembler
            await self.download_manager.file_assembler.__aenter__()  # type: ignore[attr-defined]
            self.logger.info(
                "Created file assembler for completed download: %s (num_pieces=%d)",
                self.info.name,
                self.download_manager.file_assembler.num_pieces,  # type: ignore[attr-defined]
            )

            # Note: Ensure file_segments are built
            if not self.download_manager.file_assembler.file_segments:  # type: ignore[attr-defined]
                self.logger.info(
                    "File segments empty, rebuilding from metadata for: %s",
                    self.info.name,
                )
                # Try to update from metadata
                # Type guard: file_assembler exists at this point (created above)
                file_assembler = self.download_manager.file_assembler  # type: ignore[attr-defined]
                if hasattr(
                    file_assembler,
                    "update_from_metadata",
                ):
                    file_assembler.update_from_metadata(self.torrent_data)
                # If still empty, rebuild segments
                if not self.download_manager.file_assembler.file_segments:  # type: ignore[attr-defined]
                    self.logger.warning(
                        "File segments still empty after rebuild. Files may not be written correctly for: %s",
                        self.info.name,
                    )

            # Note: Write all verified pieces to disk now
            # Since download is complete, all pieces should be verified
            if self.piece_manager:
                written_count = 0
                for piece_index in range(self.piece_manager.num_pieces):
                    piece = self.piece_manager.pieces[piece_index]
                    if (
                        piece.state.value == "verified"
                        and piece.is_complete()
                        and piece_index
                        not in self.download_manager.file_assembler.written_pieces  # type: ignore[attr-defined]
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
                                await self.download_manager.file_assembler.write_piece_to_file(  # type: ignore[attr-defined]
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

        # Note: Finalize files after all pieces are written to disk
        # This ensures files are properly assembled and made accessible
        if (
            hasattr(self.download_manager, "file_assembler")
            and self.download_manager.file_assembler is not None
        ):
            file_assembler = self.download_manager.file_assembler  # type: ignore[attr-defined]
            try:
                # Note: Wait for all verified pieces to be written to disk
                # This handles the race condition where completion is detected before all writes complete
                total_pieces = file_assembler.num_pieces  # type: ignore[union-attr]

                # Early exit if no pieces to finalize (test scenarios)
                if total_pieces == 0:
                    self.logger.info("No pieces to finalize for: %s", self.info.name)
                    # Skip file finalization, proceed to callback
                else:
                    max_wait_time = 30.0  # Maximum 30 seconds to wait for writes
                    wait_interval = 0.1  # Check every 100ms
                    elapsed_time = 0.0

                    # Get initial counts
                    written_count = len(file_assembler.written_pieces)  # type: ignore[union-attr]
                    verified_count = (
                        len(self.piece_manager.verified_pieces)
                        if self.piece_manager
                        else 0
                    )

                    # Early exit for test scenarios: no pieces written/verified and none expected
                    if written_count == 0 and verified_count == 0 and total_pieces > 0:
                        # Test scenario: pieces exist but none are written/verified
                        # Skip polling loop to prevent infinite wait
                        self.logger.info(
                            "No pieces written/verified for: %s (total_pieces=%d), skipping finalization",
                            self.info.name,
                            total_pieces,
                        )
                        # Skip file finalization, proceed to callback
                    else:
                        while elapsed_time < max_wait_time:
                            written_count = len(file_assembler.written_pieces)  # type: ignore[union-attr]
                            verified_count = (
                                len(self.piece_manager.verified_pieces)
                                if self.piece_manager
                                else 0
                            )

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
                                # Note: Wait a moment for any pending async writes to complete
                                await asyncio.sleep(
                                    0.5
                                )  # Give disk I/O time to complete
                                await file_assembler.finalize_files()  # type: ignore[union-attr]
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
                            if (
                                written_count == verified_count
                                and written_count < total_pieces
                            ):
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
                                if self.piece_manager and file_assembler is not None:
                                    # Type cast to help type checker understand file_assembler is not None
                                    # file_assembler is guaranteed to be not None due to the check above
                                    from ccbt.storage.file_assembler import (
                                        AsyncFileAssembler,
                                    )

                                    file_assembler_typed = cast(
                                        "AsyncFileAssembler", file_assembler
                                    )
                                    for piece_index in range(total_pieces):
                                        if (
                                            piece_index
                                            not in file_assembler_typed.written_pieces
                                        ):
                                            piece = self.piece_manager.pieces[
                                                piece_index
                                            ]
                                            if (
                                                piece.state.value == "verified"
                                                and piece.is_complete()
                                            ):
                                                try:
                                                    piece_data = piece.get_data()
                                                    if piece_data:
                                                        self.logger.info(
                                                            "Writing missing piece %d to disk during finalization",
                                                            piece_index,
                                                        )
                                                        await file_assembler.write_piece_to_file(  # type: ignore[union-attr]
                                                            piece_index,
                                                            piece_data,
                                                        )
                                                except Exception as e:
                                                    self.logger.warning(
                                                        "Failed to write missing piece %d during finalization: %s",
                                                        piece_index,
                                                        e,
                                                    )

                                # Note: Wait a moment for async writes to complete before finalizing
                                await asyncio.sleep(0.5)
                                # Finalize with whatever we have
                                await file_assembler.finalize_files()  # type: ignore[union-attr]
                                self.logger.info(
                                    "Files finalized (may be incomplete: %d/%d pieces written) - files should now be visible",
                                    len(file_assembler.written_pieces),  # type: ignore[union-attr]
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

        # Note: Notify session manager of completion
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

            download_time = time.time() - (  # type: ignore[operator]
                self.start_time if hasattr(self, "start_time") else time.time()
            )
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

        # Note: Broadcast HAVE message to all connected peers
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

        # Note: Write verified piece to disk using file assembler
        if self.piece_manager and 0 <= piece_index < len(self.piece_manager.pieces):
            from ccbt.piece.async_piece_manager import PieceState as PieceStateEnum

            piece = self.piece_manager.pieces[piece_index]
            # Check if piece is verified (state is VERIFIED enum value)
            if piece.state == PieceStateEnum.VERIFIED and piece.is_complete():
                try:
                    # Get piece data
                    piece_data = piece.get_data()
                    if piece_data:
                        # Note: Check if files are available before creating file assembler
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
                                    elif (
                                        "type" in file_info
                                        and file_info["type"] == "single"
                                    ):
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
                            # Continue to checkpoint saving even if file write is skipped

                        # Create file assembler if it doesn't exist
                        if (
                            not hasattr(self.download_manager, "file_assembler")
                            or self.download_manager.file_assembler is None
                        ):
                            # Note: Ensure output directory exists before creating file assembler
                            output_dir_path = Path(self.output_dir)
                            if not output_dir_path.exists():
                                output_dir_path.mkdir(parents=True, exist_ok=True)
                                self.logger.info(
                                    "Created output directory: %s", output_dir_path
                                )

                            from ccbt.storage.file_assembler import AsyncFileAssembler

                            # Type ignore: file_assembler is a dynamic attribute on download_manager
                            self.download_manager.file_assembler = AsyncFileAssembler(  # type: ignore[attr-defined]
                                self.torrent_data,
                                str(self.output_dir),
                            )
                            # Initialize file assembler
                            await self.download_manager.file_assembler.__aenter__()  # type: ignore[attr-defined]
                            self.logger.info(
                                "Created file assembler for torrent: %s (num_pieces=%d)",
                                self.info.name,
                                self.download_manager.file_assembler.num_pieces,  # type: ignore[attr-defined]
                            )

                        # Note: Check if file segments are built (may be empty if metadata wasn't available when created)
                        if not self.download_manager.file_assembler.file_segments:  # type: ignore[attr-defined]
                            # Rebuild file segments in case metadata became available after file assembler was created
                            self.logger.info(
                                "Rebuilding file segments for piece %d (file_segments was empty)",
                                piece_index,
                            )
                            self.download_manager.file_assembler.update_from_metadata(  # type: ignore[attr-defined]
                                self.torrent_data
                            )

                        # Note: Ensure file segments exist before writing
                        if not self.download_manager.file_assembler.file_segments:  # type: ignore[attr-defined]
                            self.logger.error(
                                "Cannot write piece %d: file segments are still empty after rebuild. "
                                "Metadata may be incomplete.",
                                piece_index,
                            )
                            # Continue to checkpoint saving even if file write fails

                        # Write piece to disk
                        await self.download_manager.file_assembler.write_piece_to_file(  # type: ignore[attr-defined]
                            piece_index,
                            piece_data,
                        )
                        self.logger.info(
                            "Wrote verified piece %d to disk (%d bytes, written_pieces: %d/%d)",
                            piece_index,
                            len(piece_data),
                            len(self.download_manager.file_assembler.written_pieces),  # type: ignore[attr-defined]
                            self.download_manager.file_assembler.num_pieces,  # type: ignore[attr-defined]
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
        status = await self.status_aggregator.get_torrent_status()
        # Add is_private flag (BEP 27)
        status["is_private"] = self.is_private
        return status

    async def _resume_from_checkpoint(self, checkpoint: TorrentCheckpoint) -> None:
        """Resume download from checkpoint."""
        if self.checkpoint_controller:
            await self.checkpoint_controller.resume_from_checkpoint(checkpoint, self)
        else:
            self.logger.error("Checkpoint controller not initialized")
            msg = "Checkpoint controller not initialized"
            raise RuntimeError(msg)

    async def _save_checkpoint(self) -> None:
        """Save current download state to checkpoint."""
        if self.checkpoint_controller:
            await self.checkpoint_controller.save_checkpoint_state(self)
        else:
            self.logger.error("Checkpoint controller not initialized")
            msg = "Checkpoint controller not initialized"
            raise RuntimeError(msg)

    async def _checkpoint_loop(self) -> None:
        """Background task for periodic checkpoint saving."""
        if self.checkpoint_controller:
            await self.checkpoint_controller.run_periodic_loop()
        else:
            self.logger.error("Checkpoint controller not initialized")
            msg = "Checkpoint controller not initialized"
            raise RuntimeError(msg)

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
                        upload_rate = (
                            self.info.upload_rate
                            if hasattr(self.info, "upload_rate")
                            else 0.0
                        )
                        uploaded = (
                            self.info.uploaded if hasattr(self.info, "uploaded") else 0
                        )
                        downloaded = (
                            self.info.downloaded
                            if hasattr(self.info, "downloaded")
                            else 1
                        )  # Avoid division by zero
                        ratio = uploaded / downloaded if downloaded > 0 else 0.0  # type: ignore[operator]

                        # Count connected leechers (peers that are downloading from us)
                        connected_leechers = 0
                        if (
                            hasattr(self, "peer_manager")
                            and self.peer_manager
                            and hasattr(self.peer_manager, "connections")
                        ):
                            for conn in self.peer_manager.connections.values():  # type: ignore[union-attr]
                                if (
                                    hasattr(conn, "peer_choking")
                                    and not conn.peer_choking
                                ):
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
                        self.logger.debug(
                            "Failed to emit SEEDING_STATS_UPDATED event: %s", e
                        )
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

    def is_ready(self) -> bool:
        """Check if session is ready (has all necessary components initialized).

        Returns:
            True if session has all required components, False otherwise

        """
        return (
            hasattr(self, "info")
            and self.info is not None
            and hasattr(self, "download_manager")
            and self.download_manager is not None
            and hasattr(self, "piece_manager")
            and self.piece_manager is not None
            and isinstance(self.torrent_data, dict)
        )

    @property
    def info_hash_hex(self) -> str:
        """Get info hash as hex string."""
        return self.info.info_hash.hex()

    def is_stopped(self) -> bool:
        """Check if session is stopped.

        Returns:
            True if session stop event is set, False otherwise.

        """
        return self._stop_event.is_set()

    @property
    def tracker_connection_status(self) -> str:
        """Get current tracker connection status.

        Returns:
            Current tracker connection status string.

        """
        return getattr(self, "_tracker_connection_status", "unknown")

    @tracker_connection_status.setter
    def tracker_connection_status(self, value: str) -> None:
        """Set tracker connection status.

        Args:
            value: Status string to set.

        """
        self._tracker_connection_status = value

    @property
    def last_tracker_error(self) -> Optional[str]:
        """Get last tracker error.

        Returns:
            Last tracker error message, or None if no error.

        """
        return getattr(self, "_last_tracker_error", None)

    @last_tracker_error.setter
    def last_tracker_error(self, value: Optional[str]) -> None:
        """Set last tracker error.

        Args:
            value: Error message to set, or None to clear.

        """
        self._last_tracker_error = value

    @property
    def tracker_consecutive_failures(self) -> int:
        """Get consecutive tracker failures count.

        Returns:
            Number of consecutive tracker failures.

        """
        return getattr(self, "_tracker_consecutive_failures", 0)

    @tracker_consecutive_failures.setter
    def tracker_consecutive_failures(self, value: int) -> None:
        """Set consecutive tracker failures count.

        Args:
            value: Number of consecutive failures.

        """
        self._tracker_consecutive_failures = value

    def get_queued_peers(self) -> list[Any]:
        """Get queued peers.

        Returns:
            List of queued peers. Returns empty list if not initialized.

        """
        if not hasattr(self, "_queued_peers"):
            return []
        return list(getattr(self, "_queued_peers", []))

    def add_queued_peer(self, peer: Any) -> None:
        """Add peer to queue.

        Args:
            peer: Peer to add to queue.

        """
        if not hasattr(self, "_queued_peers"):
            self._queued_peers: list[Any] = []
        self._queued_peers.append(peer)

    def clear_queued_peers(self) -> None:
        """Clear queued peers."""
        if hasattr(self, "_queued_peers"):
            self._queued_peers.clear()

    def collect_trackers(self, td: dict[str, Any]) -> list[str]:
        """Collect and deduplicate tracker URLs from torrent_data (public API).

        Args:
            td: Torrent data dictionary

        Returns:
            List of unique tracker URLs

        """
        return self._collect_trackers(td)

    @property
    def dht_setup(self) -> Optional[Any]:
        """Get DHT setup instance.

        Returns:
            DHT setup instance, or None if not initialized.

        """
        return getattr(self, "_dht_setup", None)

    @property
    def magnet_info(self) -> Any:
        """Get MagnetInfo from torrent_data when present (BEP 53)."""
        if isinstance(self.torrent_data, dict):
            return self.torrent_data.get("magnet_info")
        return getattr(self.torrent_data, "magnet_info", None)

    def invoke_peer_callbacks(self, *args: Any, **kwargs: Any) -> None:
        """Invoke peer callbacks (public API wrapper).

        Args:
            *args: Positional arguments for callback
            **kwargs: Keyword arguments for callback

        """
        invoke_cb = getattr(self, "_invoke_peer_callbacks", None)
        if invoke_cb:
            invoke_cb(*args, **kwargs)

    async def handle_magnet_metadata_exchange(self, *args: Any, **kwargs: Any) -> Any:
        """Handle magnet metadata exchange (public API wrapper).

        Delegates to DHT setup's handler when set so announce loop can run
        the same metadata exchange logic. Returns handler result (e.g. bool).

        Args:
            *args: Positional arguments (e.g. peer_list)
            **kwargs: Keyword arguments

        Returns:
            Result from handler (e.g. True if metadata fetched), or None if no handler.

        """
        handler = getattr(self, "_handle_magnet_metadata_exchange", None)
        if handler:
            return await handler(*args, **kwargs)
        return None

    def get_queued_dht_peers(self) -> list[Any]:
        """Get queued DHT peers.

        Returns:
            List of queued DHT peers. Returns empty list if not initialized.

        """
        if not hasattr(self, "_queued_dht_peers"):
            return []
        return list(getattr(self, "_queued_dht_peers", []))

    def add_queued_dht_peers(self, peers: list[Any]) -> None:
        """Add DHT peers to queue.

        Args:
            peers: List of peers to add to queue.

        """
        if not hasattr(self, "_queued_dht_peers"):
            self._queued_dht_peers: list[Any] = []
        self._queued_dht_peers.extend(peers)

    def get_pending_dht_peers(self) -> list[Any]:
        """Get pending DHT peers.

        Returns:
            List of pending DHT peers. Returns empty list if not initialized.

        """
        if not hasattr(self, "_pending_dht_peers"):
            return []
        return list(getattr(self, "_pending_dht_peers", []))

    def add_pending_dht_peer(self, peer: Any) -> None:
        """Add peer to pending DHT peers list.

        Args:
            peer: Peer to add.

        """
        if not hasattr(self, "_pending_dht_peers"):
            self._pending_dht_peers: list[Any] = []
        self._pending_dht_peers.append(peer)

    def remove_pending_dht_peer(self, peer: Any) -> None:
        """Remove peer from pending DHT peers list.

        Args:
            peer: Peer to remove.

        """
        if hasattr(self, "_pending_dht_peers"):
            with contextlib.suppress(ValueError):
                self._pending_dht_peers.remove(peer)

    @property
    def dht_download_start_lock(self) -> asyncio.Lock:
        """Get DHT download start lock.

        Returns:
            Lock for synchronizing DHT download start operations.

        """
        if not hasattr(self, "_dht_download_start_lock"):
            self._dht_download_start_lock = asyncio.Lock()
        return self._dht_download_start_lock

    @property
    def dht_download_starting(self) -> bool:
        """Check if DHT download is starting.

        Returns:
            True if DHT download is in progress, False otherwise.

        """
        return getattr(self, "_dht_download_starting", False)

    @dht_download_starting.setter
    def dht_download_starting(self, value: bool) -> None:
        """Set DHT download starting flag.

        Args:
            value: True if starting, False otherwise.

        """
        self._dht_download_starting = value

    def _recently_processed_ttl_seconds(self) -> float:
        """TTL in seconds for recently processed peers (default 5 minutes)."""
        return getattr(
            self.config.discovery,
            "discovery_cache_ttl",
            300,
        )

    def _peer_discovery_setting(self, setting_name: str, fallback: float | int) -> float | int:
        """Read peer discovery tuning values from config if available."""
        discovery = getattr(self.config, "discovery", None)
        return getattr(discovery, setting_name, fallback)

    def _low_peer_threshold(self) -> int:
        """Configured threshold for the low-peer suppression path."""
        return int(
            self._peer_discovery_setting(
                "low_peer_threshold",
                int(PEER_DISCOVERY_DEFAULTS["low_peer_threshold"]),
            )
        )

    def _low_peer_suppression_window_s(self) -> float:
        """Suppression window in seconds for repeated low-peer recovery actions."""
        return float(
            self._peer_discovery_setting(
                "low_peer_suppression_window_s",
                float(PEER_DISCOVERY_DEFAULTS["low_peer_suppression_window_s"]),
            )
        )

    def get_recently_processed_peers(self) -> set[Any]:
        """Get recently processed peers set (keys only; for backward compatibility).

        Returns:
            Set of recently processed peer keys. Returns empty set if not initialized.

        """
        if not hasattr(self, "_recently_processed_peers"):
            return set()
        data = getattr(self, "_recently_processed_peers", None)
        if isinstance(data, dict):
            return set(data.keys())
        return set() if data is None else set(data)

    def is_peer_recently_processed(self, peer: Any) -> bool:
        """Check if peer was recently processed and not yet expired (TTL-based).

        Args:
            peer: Peer to check (tuple (ip, port) or dict with ip/port).

        Returns:
            True if peer was recently processed and TTL has not expired.

        """
        if not hasattr(self, "_recently_processed_peers"):
            return False
        data = getattr(self, "_recently_processed_peers", None)
        if data is None:
            return False
        key = (
            (peer[0], peer[1])
            if isinstance(peer, (list, tuple))
            else (peer.get("ip"), peer.get("port"))
        )
        if isinstance(data, dict):
            if key not in data:
                return False
            ttl = self._recently_processed_ttl_seconds()
            return (time.time() - data[key]) <= ttl
        # Legacy set-based checkpoint: treat as non-expiring entries
        return key in data

    def add_recently_processed_peer(self, peer: Any) -> None:
        """Add peer to recently processed map with current timestamp.

        Args:
            peer: Peer to add (tuple (ip, port) or dict with ip/port).

        """
        if not hasattr(self, "_recently_processed_peers"):
            self._recently_processed_peers: dict[tuple[str, int], float] = {}
        key = (
            (peer[0], peer[1])
            if isinstance(peer, (list, tuple))
            else (str(peer.get("ip", "")), int(peer.get("port", 0)))
        )
        self._recently_processed_peers[key] = time.time()

    def cleanup_recently_processed_peers(self, keep_count: int = 500) -> None:
        """Remove expired entries (TTL) and optionally trim by size (oldest first).

        Args:
            keep_count: Max number of entries to keep when trimming by size.

        """
        if not hasattr(self, "_recently_processed_peers"):
            return
        data = getattr(self, "_recently_processed_peers", None)
        if not isinstance(data, dict):
            return
        ttl = self._recently_processed_ttl_seconds()
        now = time.time()
        expired = [k for k, ts in data.items() if (now - ts) > ttl]
        for k in expired:
            del data[k]
        if len(data) > 1000:
            by_time = sorted(data.items(), key=lambda x: x[1])
            for k, _ in by_time[: len(data) - keep_count]:
                del data[k]

    def get_recently_processed_peers_lock(self) -> asyncio.Lock:
        """Get lock for recently processed peers.

        Returns:
            Lock for synchronizing access to recently processed peers.

        """
        if not hasattr(self, "_recently_processed_peers_lock"):
            self._recently_processed_peers_lock = asyncio.Lock()
        return self._recently_processed_peers_lock

    def on_peer_connected_callback(self, *args: Any, **kwargs: Any) -> None:
        """Invoke peer connected callback (public API wrapper).

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        """
        callback = getattr(self, "_on_peer_connected", None)
        if callback:
            callback(*args, **kwargs)

    def on_peer_disconnected_callback(self, *args: Any, **kwargs: Any) -> None:
        """Invoke peer disconnected callback (public API wrapper).

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        """
        callback = getattr(self, "_on_peer_disconnected", None)
        if callback:
            callback(*args, **kwargs)

    def on_piece_received_callback(self, *args: Any, **kwargs: Any) -> None:
        """Invoke piece received callback (public API wrapper).

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        """
        callback = getattr(self, "_on_piece_received", None)
        if callback:
            callback(*args, **kwargs)

    def on_bitfield_received_callback(self, *args: Any, **kwargs: Any) -> None:
        """Invoke bitfield received callback (public API wrapper).

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        """
        callback = getattr(self, "_on_bitfield_received", None)
        if callback:
            callback(*args, **kwargs)

    @property
    def dht_callback_invocation_count(self) -> int:
        """Get DHT callback invocation count.

        Returns:
            Number of times DHT callback has been invoked.

        """
        return getattr(self, "_dht_callback_invocation_count", 0)

    @dht_callback_invocation_count.setter
    def dht_callback_invocation_count(self, value: int) -> None:
        """Set DHT callback invocation count.

        Args:
            value: Count value to set.

        """
        self._dht_callback_invocation_count = value

    def increment_dht_callback_count(self) -> None:
        """Increment DHT callback invocation count."""
        current = getattr(self, "_dht_callback_invocation_count", 0)
        self._dht_callback_invocation_count = current + 1

    def get_dht_peer_tasks(self) -> set[asyncio.Task]:
        """Get DHT peer tasks set.

        Returns:
            Set of DHT peer tasks. Returns empty set if not initialized.

        """
        if not hasattr(self, "_dht_peer_tasks"):
            return set()
        return getattr(self, "_dht_peer_tasks", set()).copy()

    def add_dht_peer_task(self, task: asyncio.Task) -> None:
        """Add DHT peer task to tracking set.

        Args:
            task: Task to add.

        """
        if not hasattr(self, "_dht_peer_tasks"):
            self._dht_peer_tasks: set[asyncio.Task] = set()
        self._dht_peer_tasks.add(task)

    def remove_dht_peer_task(self, task: asyncio.Task) -> None:
        """Remove DHT peer task from tracking set.

        Args:
            task: Task to remove.

        """
        if hasattr(self, "_dht_peer_tasks"):
            self._dht_peer_tasks.discard(task)

    @property
    def discovery_controller(self) -> Optional[Any]:
        """Get discovery controller instance.

        Returns:
            Discovery controller instance, or None if not initialized.

        """
        return getattr(self, "_discovery_controller", None)

    @discovery_controller.setter
    def discovery_controller(self, value: Optional[Any]) -> None:
        """Set discovery controller instance.

        Args:
            value: Discovery controller instance, or None.

        """
        self._discovery_controller = value

    def get_metadata_tasks(self) -> set[asyncio.Task]:
        """Get metadata tasks set.

        Returns:
            Set of metadata tasks. Returns empty set if not initialized.

        """
        if not hasattr(self, "_metadata_tasks"):
            return set()
        return getattr(self, "_metadata_tasks", set()).copy()

    def add_metadata_task(self, task: asyncio.Task) -> None:
        """Add metadata task to tracking set.

        Args:
            task: Task to add.

        """
        if not hasattr(self, "_metadata_tasks"):
            self._metadata_tasks: set[asyncio.Task] = set()
        self._metadata_tasks.add(task)

    def remove_metadata_task(self, task: asyncio.Task) -> None:
        """Remove metadata task from tracking set.

        Args:
            task: Task to remove.

        """
        if hasattr(self, "_metadata_tasks"):
            self._metadata_tasks.discard(task)

    def _normalize_peer_source(self, source: Any) -> str:
        """Normalize a peer source label for metrics bucketing."""
        if isinstance(source, str) and source in {
            "tracker",
            "dht",
            "pex",
            "lsd",
            "incoming",
            "unknown",
        }:
            return source
        return "unknown"

    def _record_peer_source_counts(
        self, metric_name: str, counts: dict[str, int]
    ) -> None:
        """Accumulate peer source counts into a session metric bucket."""
        metric_bucket = self._peer_discovery_metrics.get(metric_name)
        if not isinstance(metric_bucket, dict):
            return
        for raw_source, count in counts.items():
            source = self._normalize_peer_source(raw_source)
            metric_bucket[source] = int(metric_bucket.get(source, 0)) + int(count)

    def record_discovered_peers(
        self,
        peers: list[dict[str, Any]] | list[tuple[str, int]],
        *,
        source: Optional[str] = None,
    ) -> None:
        """Record peer discovery ingress counts before ranking/filtering."""
        source_counts: dict[str, int] = {}
        if source is not None:
            normalized = self._normalize_peer_source(source)
            source_counts[normalized] = len(peers)
        else:
            for peer in peers:
                peer_source = "unknown"
                if isinstance(peer, dict):
                    peer_source = self._normalize_peer_source(peer.get("peer_source"))
                source_counts[peer_source] = source_counts.get(peer_source, 0) + 1

        self._record_peer_source_counts("peers_discovered_by_source", source_counts)
        self._record_peer_source_counts("peers_returned_by_source", source_counts)

    def update_usable_live_peers_by_source(self, connections: dict[str, Any]) -> None:
        """Replace usable-live-peer source snapshot using actual connection state."""
        source_counts = {
            "tracker": 0,
            "dht": 0,
            "pex": 0,
            "lsd": 0,
            "incoming": 0,
            "unknown": 0,
        }
        payload_capable_counts = source_counts.copy()
        for connection in connections.values():
            peer_info = getattr(connection, "peer_info", None)
            source = self._normalize_peer_source(
                getattr(peer_info, "peer_source", "unknown")
            )
            has_piece_info = bool(
                getattr(getattr(connection, "peer_state", None), "bitfield", None)
            ) or bool(
                getattr(getattr(connection, "peer_state", None), "pieces_we_have", None)
            )
            stats = getattr(connection, "stats", None)
            productive = bool(
                getattr(stats, "blocks_delivered", 0) > 0
                or getattr(stats, "bytes_downloaded", 0) > 0
                or has_piece_info
            )
            requestable = False
            with contextlib.suppress(Exception):
                requestable = bool(connection.can_request())
            if productive or requestable:
                source_counts[source] += 1
            if has_piece_info:
                payload_capable_counts[source] += 1

        self._peer_discovery_metrics["usable_live_peers_by_source"] = source_counts
        self._peer_discovery_metrics["payload_capable_live_peers_by_source"] = (
            payload_capable_counts
        )
        # Keep the legacy metric aligned with exact live counts instead of heuristic estimation.
        self._peer_discovery_metrics["usable_peers_formed_by_source"] = (
            source_counts.copy()
        )

    def _metadata_is_incomplete(self) -> bool:
        """Return True when torrent metadata is still incomplete."""
        if bool(
            getattr(getattr(self, "piece_manager", None), "_metadata_incomplete", False)
        ):
            return True

        if not isinstance(self.torrent_data, dict):
            return False

        file_info = self.torrent_data.get("file_info")
        if file_info is None:
            return True
        return bool(
            isinstance(file_info, dict)
            and int(file_info.get("total_length", 0) or 0) == 0
        )

    def _session_metadata_is_available(self) -> bool:
        """Check whether session metadata is sufficient to rebuild piece maps."""
        if not isinstance(self.torrent_data, dict):
            return False

        if self.torrent_data.get("_metadata_incomplete"):
            return False
        pieces_info = self.torrent_data.get("pieces_info")
        if not isinstance(pieces_info, dict):
            return False

        if int(pieces_info.get("piece_length", 0) or 0) <= 0:
            return False

        total_length = int(pieces_info.get("total_length", 0) or 0)
        num_pieces = int(pieces_info.get("num_pieces", 0) or 0)
        if total_length > 0 or num_pieces > 0:
            return True

        piece_hashes = pieces_info.get("piece_hashes")
        return isinstance(piece_hashes, (list, tuple)) and len(piece_hashes) > 0

    async def _get_swarm_recovery_state(self) -> dict[str, Any]:
        """Summarize swarm usefulness for recovery and stall decisions."""
        await self._revalidate_piece_maps_if_metadata_available()
        metadata_incomplete = self._metadata_is_incomplete()
        state: dict[str, Any] = {
            "metadata_incomplete": metadata_incomplete,
            "active_peers": 0,
            "productive_peers": 0,
            "requestable_peers": 0,
            "peers_with_piece_info": 0,
            "handshake_complete_peers": 0,
            "extension_capable_peers": 0,
            "bitfield_complete_peers": 0,
            "metadata_capable_peers": 0,
            "active_block_requests": 0,
            "download_rate": 0.0,
        }

        peer_manager = getattr(
            getattr(self, "download_manager", None), "peer_manager", None
        ) or getattr(self, "peer_manager", None)
        if peer_manager and hasattr(peer_manager, "get_connection_summary"):
            with contextlib.suppress(Exception):
                summary = await peer_manager.get_connection_summary()
                if hasattr(peer_manager, "connections"):
                    self.update_usable_live_peers_by_source(
                        getattr(peer_manager, "connections", {})
                    )
                state["active_peers"] = int(summary.get("active_connections", 0) or 0)
                state["productive_peers"] = int(
                    summary.get("productive_connections", 0) or 0
                )
                state["requestable_peers"] = int(
                    summary.get("requestable_connections", 0) or 0
                )
                state["peers_with_piece_info"] = int(
                    summary.get("peers_with_piece_info", 0) or 0
                )
                state["handshake_complete_peers"] = int(
                    summary.get("handshake_complete_connections", 0) or 0
                )
                state["extension_capable_peers"] = int(
                    summary.get("extension_capable_connections", 0) or 0
                )
                state["bitfield_complete_peers"] = int(
                    summary.get("bitfield_complete_connections", 0) or 0
                )
                state["metadata_capable_peers"] = int(
                    summary.get("metadata_capable_connections", 0) or 0
                )

        if (
            state["active_peers"] == 0
            and peer_manager
            and hasattr(peer_manager, "get_active_peers")
        ):
            with contextlib.suppress(Exception):
                state["active_peers"] = len(peer_manager.get_active_peers())

        piece_manager = getattr(self, "piece_manager", None)
        if piece_manager:
            with contextlib.suppress(Exception):
                state["peers_with_piece_info"] = max(
                    state["peers_with_piece_info"],
                    len(getattr(piece_manager, "peer_availability", {})),
                )
            with contextlib.suppress(Exception):
                piece_metrics = piece_manager.get_piece_selection_metrics()
                state["active_block_requests"] = int(
                    piece_metrics.get("active_block_requests", 0) or 0
                )
            with contextlib.suppress(Exception):
                stats = getattr(piece_manager, "stats", None)
                state["download_rate"] = float(
                    getattr(stats, "download_rate", 0.0) or 0.0
                )

        state["has_metadata_progress_path"] = bool(
            metadata_incomplete
            and state.get("handshake_complete_peers", 0) > 0
            and (
                state.get("extension_capable_peers", 0) > 0
                or state.get("metadata_capable_peers", 0) > 0
            )
        )
        state["has_usable_download_path"] = bool(
            state["download_rate"] > 0.0
            or state["active_block_requests"] > 0
            or (state["requestable_peers"] > 0 and state["peers_with_piece_info"] > 0)
            or state["has_metadata_progress_path"]
            or (
                state.get("handshake_complete_peers", 0) > 0
                and state.get("metadata_capable_peers", 0) > 0
            )
        )
        state["degraded_swarm"] = bool(
            not metadata_incomplete
            and state["active_peers"] > 0
            and not state["has_usable_download_path"]
        )
        metrics = getattr(self, "_peer_discovery_metrics", None)
        if isinstance(metrics, dict):
            if (
                metadata_incomplete
                and int(state.get("requestable_peers", 0)) == 0
                and int(state.get("productive_peers", 0)) == 0
                and not bool(state.get("has_metadata_progress_path", False))
            ):
                now = time.time()
                started_at = float(metrics.get("metadata_starvation_started_at", 0.0))
                if started_at <= 0.0:
                    metrics["metadata_starvation_started_at"] = now
                    metrics["metadata_starvation_seconds"] = 0.0
                else:
                    metrics["metadata_starvation_seconds"] = max(0.0, now - started_at)
            else:
                metrics["metadata_starvation_started_at"] = 0.0
                metrics["metadata_starvation_seconds"] = 0.0
        return state

    async def _revalidate_piece_maps_if_metadata_available(self) -> None:
        """Refresh piece maps after metadata becomes available."""
        if self._piece_map_revalidated_after_metadata:
            return

        if not self._session_metadata_is_available():
            return

        piece_manager = getattr(self, "piece_manager", None)
        if piece_manager is None:
            return

        update_from_metadata = getattr(piece_manager, "update_from_metadata", None)
        if not callable(update_from_metadata):
            return

        try:
            await update_from_metadata(self.torrent_data)
            self._piece_map_revalidated_after_metadata = True
            self.logger.info(
                "SESSION_METADATA_REVALIDATE: Piece maps rebuilt after metadata availability for %s",
                self.info.name,
            )
        except Exception as exc:
            self.logger.warning(
                "SESSION_METADATA_REVALIDATE: failed to rebuild piece maps for %s: %s",
                self.info.name,
                exc,
                exc_info=True,
            )

    async def get_swarm_recovery_state(self) -> dict[str, Any]:
        """Public wrapper for swarm recovery state."""
        return await self._get_swarm_recovery_state()

    def _swarm_requires_fast_recovery(self, state: dict[str, Any]) -> bool:
        """Return whether recovery paths should bypass tracker-first delays."""
        if bool(state.get("metadata_incomplete", False)):
            return True
        if (
            int(state.get("requestable_peers", 0) or 0) == 0
            and int(state.get("productive_peers", 0) or 0) == 0
        ):
            return True
        if bool(state.get("degraded_swarm", False)):
            return True
        if not bool(state.get("has_usable_download_path", False)):
            return True
        return int(state.get("active_peers", 0) or 0) == 0

    def swarm_requires_fast_recovery(self, state: dict[str, Any]) -> bool:
        """Public wrapper for fast-recovery classification."""
        return self._swarm_requires_fast_recovery(state)

    def _recovery_wait_budget(
        self,
        state: dict[str, Any],
        *,
        base_wait: float,
        fast_wait: float,
    ) -> float:
        """Return the maximum delay to tolerate before forcing recovery."""
        return fast_wait if self._swarm_requires_fast_recovery(state) else base_wait

    def recovery_wait_budget(
        self,
        state: dict[str, Any],
        *,
        base_wait: float,
        fast_wait: float,
    ) -> float:
        """Public wrapper for recovery wait budgeting."""
        return self._recovery_wait_budget(
            state,
            base_wait=base_wait,
            fast_wait=fast_wait,
        )

    @property
    def dht_discovery_task(self) -> Optional[asyncio.Task]:
        """Get DHT discovery task.

        Returns:
            DHT discovery task, or None if not started.

        """
        return getattr(self, "_dht_discovery_task", None)

    @dht_discovery_task.setter
    def dht_discovery_task(self, value: Optional[asyncio.Task]) -> None:
        """Set DHT discovery task.

        Args:
            value: Task to set, or None.

        """
        self._dht_discovery_task = value

    @property
    def stopped(self) -> bool:
        """Check if session is stopped.

        Returns:
            True if session is stopped, False otherwise.

        """
        return getattr(self, "_stopped", False)

    @stopped.setter
    def stopped(self, value: bool) -> None:
        """Set stopped flag.

        Args:
            value: True if stopped, False otherwise.

        """
        self._stopped = value

    @property
    def last_query_metrics(self) -> Optional[dict[str, Any]]:
        """Get last query metrics.

        Returns:
            Last query metrics dictionary, or None if not available.

        """
        return getattr(self, "_last_query_metrics", None)

    @last_query_metrics.setter
    def last_query_metrics(self, value: Optional[dict[str, Any]]) -> None:
        """Set last query metrics.

        Args:
            value: Metrics dictionary, or None.

        """
        self._last_query_metrics = value

    @property
    def background_start_task(self) -> Optional[asyncio.Task]:
        """Get background start task.

        Returns:
            Background start task, or None if not set.

        """
        return getattr(self, "_background_start_task", None)

    @background_start_task.setter
    def background_start_task(self, value: Optional[asyncio.Task]) -> None:
        """Set background start task.

        Args:
            value: Task to set, or None to clear.

        """
        if value is None:
            if hasattr(self, "_background_start_task"):
                delattr(self, "_background_start_task")
        else:
            self._background_start_task = value

    def get_incoming_peer_queue(self) -> asyncio.Queue[tuple[Any, ...]]:
        """Get incoming peer queue.

        Returns:
            Incoming peer queue. Creates queue if not initialized.

        """
        if not hasattr(self, "_incoming_peer_queue"):
            self._incoming_peer_queue = asyncio.Queue[
                tuple[
                    asyncio.StreamReader,
                    asyncio.StreamWriter,
                    Any,
                    str,
                    int,
                ]
            ]()
        return self._incoming_peer_queue


class AsyncSessionManager:
    """High-performance async session manager for multiple torrents."""

    def __init__(self, output_dir: str = ".", key_manager: Optional[Any] = None):
        """Initialize async session manager."""
        self.config = get_config()
        self.output_dir = output_dir
        self.key_manager = key_manager
        self.torrents: dict[bytes, AsyncTorrentSession] = {}
        self.lock = asyncio.Lock()
        # Backward-compatibility flag used by sync wrapper tests.
        self._session_started = False

        # Global components
        self.dht_client: Optional[AsyncDHTClient] = None
        self.metrics: Optional[Metrics] = None  # Initialized in start() if enabled
        self.peer_service: Optional[PeerService] = PeerService(
            max_peers=self.config.network.max_global_peers,
            connection_timeout=self.config.network.connection_timeout,
        )

        # Background tasks
        self._task_supervisor = TaskSupervisor()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._metrics_restart_task: Optional[asyncio.Task] = None
        self._metrics_sample_interval = 1.0
        self._metrics_emit_interval = 10.0
        self._last_metrics_emit = 0.0
        self._rate_history: deque[dict[str, float]] = deque(maxlen=600)
        self._metrics_restart_backoff = 1.0
        self._metrics_shutdown = False
        self._metrics_heartbeat_counter = 0
        self._metrics_heartbeat_interval = 5

        # Callbacks
        self.on_torrent_added: Optional[Callable[[bytes, str], None]] = None
        self.on_torrent_removed: Optional[Callable[[bytes], None]] = None
        self.on_torrent_complete: Optional[
            Callable[[bytes, str], None]
            | Callable[[bytes, str], Coroutine[Any, Any, None]]
        ] = None
        # XET folder callbacks
        self.on_xet_folder_added: Optional[Callable[[str, str], None]] = None
        self.on_xet_folder_removed: Optional[Callable[[str], None]] = None

        self.logger = logging.getLogger(__name__)

        # Simple per-torrent rate limits (not enforced yet, stored for reporting)
        self._per_torrent_limits: dict[bytes, dict[str, int]] = {}

        # Initialize global rate limits from config
        # Safeguard: Ensure values are integers (not MagicMock) for comparison
        global_down_kib = (
            int(self.config.limits.global_down_kib)
            if hasattr(self.config.limits, "global_down_kib")
            else 0
        )
        global_up_kib = (
            int(self.config.limits.global_up_kib)
            if hasattr(self.config.limits, "global_up_kib")
            else 0
        )
        if global_down_kib > 0 or global_up_kib > 0:
            self.logger.debug(
                "Initialized global rate limits from config: down=%d KiB/s, up=%d KiB/s",
                global_down_kib,
                global_up_kib,
            )

        # Optional dependency injection container
        self._di: Optional[DIContainer] = None

        # Components initialized by startup functions
        self.security_manager: Optional[Any] = None
        self.nat_manager: Optional[Any] = None
        self.tcp_server: Optional[Any] = None
        # Note: Store reference to initialized UDP tracker client
        # This ensures all torrent sessions use the same initialized socket
        # The UDP tracker client is a singleton, but we store the reference
        # to ensure it's accessible and to prevent any lazy initialization
        self.udp_tracker_client: Optional[Any] = None
        # Queue manager for priority-based torrent scheduling
        self.queue_manager: Optional[Any] = None
        self.key_manager: Optional[Any] = None

        # Note: Store executor initialized at daemon startup
        # This ensures executor uses the session manager's initialized components
        # and prevents duplicate executor creation
        self.executor: Optional[Any] = None

        # Note: Store protocol manager initialized at daemon startup
        # Singleton pattern removed - protocol manager is now managed via session manager
        # This ensures proper lifecycle management and prevents conflicts
        self.protocol_manager: Optional[Any] = None

        # Note: Store WebTorrent WebSocket server initialized at daemon startup
        # WebSocket server socket must be initialized once and never recreated
        # This prevents port conflicts and socket recreation issues
        self.webtorrent_websocket_server: Optional[Any] = None

        # Note: Store WebRTC connection manager initialized at daemon startup
        # WebRTC manager should be shared across all WebTorrent protocol instances
        # This ensures proper resource management and prevents duplicate managers
        self.webrtc_manager: Optional[Any] = None

        # Note: Store uTP socket manager initialized at daemon startup
        # Singleton pattern removed - uTP socket manager is now managed via session manager
        # This ensures proper socket lifecycle management and prevents socket recreation
        self.utp_socket_manager: Optional[Any] = None

        # Note: Store extension manager initialized at daemon startup
        # Singleton pattern removed - extension manager is now managed via session manager
        # This ensures proper lifecycle management and prevents conflicts
        self.extension_manager: Optional[Any] = None

        # Note: Store disk I/O manager initialized at daemon startup
        # Singleton pattern removed - disk I/O manager is now managed via session manager
        # This ensures proper lifecycle management and prevents conflicts
        self.disk_io_manager: Optional[Any] = None

        # Private torrents set (used by DHT client factory)
        self.private_torrents: set[bytes] = set()

        # XET folder synchronization components
        self._xet_transport_registry: dict[str, dict[str, Any]] = {}
        self._xet_realtime_sync: Optional[Any] = None
        self.xet_cas_client: Optional[P2PCASClient] = None
        self.xet_catalog: Optional[XetChunkCatalog] = None
        self.xet_bloom_filter: Optional[XetChunkBloomFilter] = None
        self.xet_lpd_client: Optional[LocalPeerDiscovery] = None
        self.xet_multicast_broadcaster: Optional[XetMulticastBroadcaster] = None
        self.xet_gossip_manager: Optional[XetGossipManager] = None
        self.xet_flooding_client: Optional[ControlledFlooding] = None
        # Shared PEX manager for XET discovery (created in _ensure_xet_discovery_graph if needed)
        self.pex_manager: Optional[AsyncPexManager] = None
        self._xet_discovery_status: dict[str, Any] = {}
        # XET folder sessions (keyed by info_hash or folder_path)
        self.xet_folders: dict[str, Any] = {}  # folder_path or info_hash -> XetFolder
        self._xet_folders_lock = asyncio.Lock()
        self._xet_metadata_registry: dict[str, bytes] = {}
        self._xet_metadata_version_registry: dict[str, str] = {}
        self._xet_metadata_resolver = XetMetadataResolver()
        self.media_stream_manager = MediaStreamManager(self)

        # Initialize checkpoint operations
        self.checkpoint_ops = CheckpointOperations(self)

        # Initialize background tasks handler
        self.background_tasks = ManagerBackgroundTasks(self)

        # Initialize scrape manager
        self.scrape_manager = ScrapeManager(self)

        # Initialize scrape cache and lock for BEP 48 tracker scrape statistics
        self.scrape_cache: dict[bytes, Any] = {}
        self.scrape_cache_lock = asyncio.Lock()

        # Periodic scrape task (started in start() if auto-scrape enabled)
        self.scrape_task: Optional[asyncio.Task] = None

        # Initialize torrent addition handler
        self.torrent_addition_handler = TorrentAdditionHandler(self)

    def _make_security_manager(self) -> Optional[Any]:
        """Create security manager using ComponentFactory."""
        from ccbt.session.factories import ComponentFactory

        factory = ComponentFactory(self)
        return factory.create_security_manager()

    def _make_dht_client(self, bind_ip: str, bind_port: int) -> Optional[Any]:
        """Create DHT client using ComponentFactory."""
        from ccbt.session.factories import ComponentFactory

        factory = ComponentFactory(self)
        return factory.create_dht_client(bind_ip=bind_ip, bind_port=bind_port)

    def _make_nat_manager(self) -> Optional[Any]:
        """Create NAT manager using ComponentFactory."""
        from ccbt.session.factories import ComponentFactory

        factory = ComponentFactory(self)
        return factory.create_nat_manager()

    def _make_tcp_server(self) -> Optional[Any]:
        """Create TCP server using ComponentFactory."""
        from ccbt.session.factories import ComponentFactory

        factory = ComponentFactory(self)
        return factory.create_tcp_server()

    async def _get_peers_from_trackers(
        self, tracker_urls: list[str], info_hash: bytes, port: int
    ) -> list[dict[str, Any]]:
        """Fetch peers from a list of tracker URLs.

        Args:
            tracker_urls: List of tracker URLs.
            info_hash: The info hash of the torrent.
            port: The port the client is listening on.

        Returns:
            A list of unique peer dictionaries.

        """
        if not tracker_urls:
            return []

        all_peers: list[dict[str, Any]] = []
        seen_peers: set[tuple[str, int]] = set()
        # CRITICAL: Import here to ensure test patches work (patches apply before this import)
        from ccbt.discovery.tracker import AsyncTrackerClient

        tracker_client = AsyncTrackerClient()
        try:
            await tracker_client.start()
            torrent_data = {
                "info_hash": info_hash,
                "peer_id": tracker_client._generate_peer_id(),
                "file_info": {"total_length": 0},  # Minimal info for announce
            }
            # Call announce for each tracker URL (test mocks announce, not announce_to_multiple)
            for tracker_url in tracker_urls:
                try:
                    torrent_data_copy = torrent_data.copy()
                    torrent_data_copy["announce"] = tracker_url
                    response = await tracker_client.announce(
                        torrent_data_copy,
                        port=port,
                        event="started",
                    )
                    if response and response.peers:
                        for peer_info in response.peers:
                            peer_key = (peer_info.ip, peer_info.port)  # type: ignore[union-attr]
                            if peer_key not in seen_peers:
                                seen_peers.add(peer_key)
                                all_peers.append(
                                    {
                                        "ip": peer_info.ip,  # type: ignore[union-attr]
                                        "port": peer_info.port,  # type: ignore[union-attr]
                                        "peer_source": peer_info.peer_source  # type: ignore[union-attr]
                                        or "tracker",
                                    }
                                )
                except Exception as e:
                    # Continue to next tracker if this one fails
                    self.logger.debug("Tracker %s failed: %s", tracker_url, e)
                    continue
        except Exception as e:
            self.logger.warning("Error fetching peers from trackers: %s", e)
        finally:
            await tracker_client.stop()
        return all_peers

    def _build_xet_node_id(self) -> str:
        """Build a stable-ish node identifier for XET propagation helpers."""
        public_key_hex = None
        if self.key_manager is not None and hasattr(
            self.key_manager, "get_public_key_hex"
        ):
            with contextlib.suppress(Exception):
                public_key_hex = self.key_manager.get_public_key_hex()
        seed = public_key_hex or f"{self.output_dir}:{id(self)}"
        return sha1_compat(seed.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]

    def _on_lpd_peer_discovered(self, ip: str, port: int) -> None:
        """Callback when LPD discovers a peer on the LAN; register for XET discovery."""
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._add_lpd_peer(ip, port))
            task.add_done_callback(lambda _finished: None)
        except RuntimeError:
            pass

    async def _add_lpd_peer(self, ip: str, port: int) -> None:
        """Add an LPD-discovered peer to PEX known set for XET connection attempts."""
        if not hasattr(self, "pex_manager") or self.pex_manager is None:
            return
        peer = PexPeer(ip=ip, port=port, source="lpd")
        await self.pex_manager.add_peers([peer])

    def _is_xet_peer_authorized(
        self, peer_id: str, workspace_id_hex: Optional[str] = None
    ) -> bool:
        """Return whether any active peer manager recognizes peer_id as XET-authorized."""
        for session in self.torrents.values():
            peer_manager = getattr(session.download_manager, "peer_manager", None)
            if peer_manager is not None and hasattr(
                peer_manager, "is_peer_xet_authorized"
            ):
                with contextlib.suppress(Exception):
                    if peer_manager.is_peer_xet_authorized(peer_id, workspace_id_hex):
                        return True
        return False

    def _mark_xet_discovery_success(self, backend: str) -> None:
        """Record successful use timestamp for a discovery backend."""
        now = time.time()
        last_success = getattr(self, "_xet_discovery_last_success", None)
        if not isinstance(last_success, dict):
            last_success = {}
        last_success[backend] = now
        self._xet_discovery_last_success = last_success

    def _on_peer_bloom_response(self, peer_id: str, bloom_bytes: bytes) -> None:
        """Merge a peer's bloom filter into discovery state (from BLOOM_FILTER_RESPONSE)."""
        if self.xet_bloom_filter is not None:
            self.xet_bloom_filter.merge_peer_bloom(peer_id, bloom_bytes)

    def _on_xet_multicast_chunk(
        self, chunk_hash: bytes, peer_ip: str, peer_port: int
    ) -> None:
        """Record chunk announcement from multicast into CAS catalog."""
        if self.xet_cas_client is not None:
            self.xet_cas_client.record_chunk_peer(chunk_hash, peer_ip, peer_port)

    def _on_xet_multicast_update(
        self,
        update_data: dict[str, Any],
        peer_ip: str,
        peer_port: int,
    ) -> None:
        """Forward folder update from multicast into session XET update handler."""
        peer_id = f"{peer_ip}:{peer_port}"
        workspace_id_hex = update_data.get("workspace_id_hex") or update_data.get(
            "workspace_id"
        )
        file_path = update_data.get("file_path") or update_data.get("path", "")
        chunk_hex = update_data.get("chunk_hash")
        chunk_hash = bytes(32)
        if isinstance(chunk_hex, str):
            with contextlib.suppress(ValueError):
                chunk_hash = bytes.fromhex(chunk_hex)
        git_ref = update_data.get("git_ref")
        operation = update_data.get("operation", "upsert")
        metadata_version = update_data.get("metadata_version")

        async def _apply() -> None:
            await self._handle_incoming_xet_update(
                peer_id=peer_id,
                workspace_id_hex=workspace_id_hex,
                file_path=file_path,
                chunk_hash=chunk_hash,
                git_ref=git_ref,
                operation=operation,
                metadata_version=metadata_version,
            )

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_apply())
            task.add_done_callback(lambda _finished: None)
        except RuntimeError:
            pass

    def _update_xet_discovery_status(self) -> None:
        """Refresh a lightweight session-owned XET discovery status snapshot.

        Each backend has enabled, injected, health (True if enabled and no known
        failure), and last_success (timestamp of last successful use, or None).
        """
        last_success = getattr(self, "_xet_discovery_last_success", None) or {}
        if not isinstance(last_success, dict):
            last_success = {}

        self._xet_discovery_status = {
            "dht": {
                "enabled": self.dht_client is not None,
                "injected": self.dht_client is not None,
                "health": self.dht_client is not None,
                "last_success": last_success.get("dht"),
            },
            "tracker": {
                "enabled": getattr(self, "udp_tracker_client", None) is not None,
                "injected": getattr(self, "udp_tracker_client", None) is not None,
                "health": getattr(self, "udp_tracker_client", None) is not None,
                "last_success": last_success.get("tracker"),
            },
            "catalog": {
                "enabled": self.xet_catalog is not None,
                "injected": self.xet_catalog is not None,
                "health": self.xet_catalog is not None,
                "last_success": last_success.get("catalog"),
            },
            "bloom": {
                "enabled": self.xet_bloom_filter is not None,
                "injected": self.xet_bloom_filter is not None,
                "health": self.xet_bloom_filter is not None,
                "last_success": last_success.get("bloom"),
            },
            "lpd": {
                "enabled": self.xet_lpd_client is not None,
                "injected": self.xet_lpd_client is not None,
                "health": self.xet_lpd_client is not None,
                "last_success": last_success.get("lpd"),
            },
            "multicast": {
                "enabled": self.xet_multicast_broadcaster is not None,
                "injected": self.xet_multicast_broadcaster is not None,
                "health": self.xet_multicast_broadcaster is not None,
                "last_success": last_success.get("multicast"),
            },
            "gossip": {
                "enabled": self.xet_gossip_manager is not None,
                "injected": self.xet_gossip_manager is not None,
                "health": self.xet_gossip_manager is not None,
                "last_success": last_success.get("gossip"),
            },
            "flooding": {
                "enabled": self.xet_flooding_client is not None,
                "injected": self.xet_flooding_client is not None,
                "health": self.xet_flooding_client is not None,
                "last_success": last_success.get("flooding"),
            },
            "pex": {
                "enabled": hasattr(self, "pex_manager")
                and self.pex_manager is not None,
                "injected": self.xet_cas_client is not None
                and hasattr(self.xet_cas_client, "pex_manager"),
                "health": hasattr(self, "pex_manager")
                and self.pex_manager is not None
                and self.xet_cas_client is not None
                and hasattr(self.xet_cas_client, "pex_manager"),
                "last_success": last_success.get("pex"),
            },
        }

    def _ensure_xet_discovery_graph(self) -> None:
        """Initialize the shared XET discovery graph once per session manager."""
        if self.xet_catalog is None:
            self.xet_catalog = XetChunkCatalog()
        if self.xet_bloom_filter is None:
            self.xet_bloom_filter = XetChunkBloomFilter()
        if self.pex_manager is None:
            self.pex_manager = AsyncPexManager()
        if self.xet_lpd_client is None:
            xet_port = self.config.network.xet_port or self.config.network.listen_port
            self.xet_lpd_client = LocalPeerDiscovery(listen_port=xet_port)
        if self.xet_multicast_broadcaster is None:
            self.xet_multicast_broadcaster = XetMulticastBroadcaster(
                multicast_address=self.config.network.xet_multicast_address,
                multicast_port=self.config.network.xet_multicast_port,
            )
        if self.xet_gossip_manager is None:
            self.xet_gossip_manager = XetGossipManager(
                node_id=self._build_xet_node_id()
            )
        if self.xet_flooding_client is None:
            self.xet_flooding_client = ControlledFlooding(
                node_id=self._build_xet_node_id()
            )
        if self.xet_cas_client is None:
            self.xet_cas_client = P2PCASClient(
                dht_client=getattr(self, "dht_client", None),
                tracker_client=getattr(self, "udp_tracker_client", None),
                key_manager=self.key_manager,
                bloom_filter=self.xet_bloom_filter,
                catalog=self.xet_catalog,
                extension_manager=self.extension_manager,
            )
        if hasattr(self, "pex_manager") and self.pex_manager is not None:
            self.xet_cas_client.register_pex_manager(self.pex_manager)
        if self.xet_cas_client is not None:
            self.xet_cas_client.set_peer_authorizer(self._is_xet_peer_authorized)
            self.xet_cas_client.set_discovery_backend_success_notifier(
                self._mark_xet_discovery_success
            )
        if self.xet_lpd_client is not None:
            self.xet_lpd_client.peer_callback = self._on_lpd_peer_discovered
        if self.xet_multicast_broadcaster is not None:
            self.xet_multicast_broadcaster.chunk_callback = self._on_xet_multicast_chunk
            self.xet_multicast_broadcaster.update_callback = (
                self._on_xet_multicast_update
            )
        if self.xet_gossip_manager is not None:
            self.xet_gossip_manager.chunk_callbacks.append(self._on_xet_multicast_chunk)
            self.xet_gossip_manager.folder_callbacks.append(
                self._on_xet_multicast_update
            )
        self._update_xet_discovery_status()

    def get_xet_discovery_status(self) -> dict[str, Any]:
        """Return the current shared XET discovery status snapshot."""
        self._update_xet_discovery_status()
        return dict(self._xet_discovery_status)

    def get_dht_client_for_xet(self) -> Optional[Any]:
        """Return the session DHT client for cold tonic link discovery, or None."""
        return getattr(self, "dht_client", None)

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
                    self.logger.info(
                        "NAT manager initialized and ports mapped successfully"
                    )
                else:
                    self.logger.info(
                        "NAT manager initialized (auto_map_ports disabled)"
                    )
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
                    self.logger.debug(
                        "Failed to emit COMPONENT_STARTED event for NAT: %s", e
                    )
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
                            self.logger.debug(
                                "Failed to emit COMPONENT_STARTED event for TCP server: %s",
                                e,
                            )
                    else:
                        self.logger.warning("Failed to create TCP server")
                else:
                    self.logger.debug(
                        "TCP transport disabled, skipping TCP server startup"
                    )
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
                    from ccbt.discovery.dht import AsyncDHTClient

                    # Get DHT port from config (default to 6881 if not set)
                    dht_port = self.config.discovery.dht_port
                    # Bind to all interfaces for P2P networking (DHT must accept peer connections)
                    bind_ip = getattr(self.config.network, "bind_ip", "0.0.0.0")  # nosec B104
                    self.dht_client = AsyncDHTClient(
                        bind_ip=bind_ip,
                        bind_port=dht_port,
                    )
                    if self.dht_client:
                        await self.dht_client.start()
                        self.logger.info("DHT client started on port %d", dht_port)
                        # Emit COMPONENT_STARTED event
                        try:
                            if self.on_component_started:  # type: ignore[has-type]
                                await self.on_component_started(  # type: ignore[misc]
                                    "dht_client", {"port": dht_port}
                                )
                        except Exception as e:
                            self.logger.debug(
                                "Failed to emit COMPONENT_STARTED event for DHT client: %s",
                                e,
                            )
                except Exception:
                    # Best-effort: log and continue
                    self.logger.warning(
                        "DHT client initialization failed. DHT peer discovery may not work.",
                        exc_info=True,
                    )

        network_tasks.append(start_dht_client())

        # Wait for all network tasks to complete
        await asyncio.gather(*network_tasks, return_exceptions=True)

        # Initialize protocol manager
        try:
            from ccbt.protocols.base import ProtocolManager

            if self.protocol_manager is None:
                self.protocol_manager = ProtocolManager()
                self.logger.info("Protocol manager initialized")
        except Exception:
            # Best-effort: log and continue
            self.logger.warning(
                "Protocol manager initialization failed. Protocol support may not work.",
                exc_info=True,
            )

        try:
            from ccbt.extensions.manager import get_extension_manager

            # Set extension_manager before _ensure_xet_discovery_graph so P2PCASClient
            # receives it via injection (avoids deprecated get_extension_manager() in
            # download_chunk) and uses the same lifecycle-bound instance.
            self.extension_manager = get_extension_manager()
            self._ensure_xet_discovery_graph()
            xet_ext = self.extension_manager.extensions.get("xet")
            if xet_ext is not None:
                metadata_exchange = XetMetadataExchange(xet_ext)
                metadata_exchange.set_metadata_provider(
                    lambda info_hash: self._xet_metadata_registry.get(info_hash.hex())
                )
                metadata_exchange.set_piece_requester(self._request_xet_metadata_piece)
                xet_ext.set_metadata_exchange(metadata_exchange)
                xet_ext.set_chunk_provider(self._provide_any_xet_chunk)
                xet_ext.set_version_provider(
                    lambda _peer_id: self._get_any_xet_git_ref()
                )
                xet_ext.set_sync_mode_provider(
                    lambda _peer_id: self.config.xet_sync.default_sync_mode
                )
                xet_ext.set_bloom_provider(
                    lambda _peer_id: self.xet_bloom_filter.get_peer_bloom()
                    if self.xet_bloom_filter is not None
                    else b""
                )
                xet_ext.on_bloom_response = self._on_peer_bloom_response
                if self.xet_gossip_manager is not None:
                    self.extension_manager._xet_gossip_received = (
                        self.xet_gossip_manager.handle_gossip_message
                    )
                xet_ext.set_message_sender(self._send_xet_message)
                xet_ext.set_update_handler(self._handle_incoming_xet_update)
        except Exception:
            self.logger.warning(
                "Failed to initialize XET extension transport hooks",
                exc_info=True,
            )

        if self.protocol_manager is not None:
            try:
                from ccbt.protocols.base import ProtocolType
                from ccbt.protocols.xet import XetProtocol

                if self.protocol_manager.get_protocol(ProtocolType.XET) is None:
                    xet_protocol = XetProtocol(
                        cas_client=self.xet_cas_client,
                        dht_client=getattr(self, "dht_client", None),
                        tracker_client=getattr(self, "udp_tracker_client", None),
                        pex_manager=self.pex_manager,
                        lpd_client=self.xet_lpd_client,
                        multicast_broadcaster=self.xet_multicast_broadcaster,
                        gossip_manager=self.xet_gossip_manager,
                        flooding_client=self.xet_flooding_client,
                        catalog=self.xet_catalog,
                        bloom_filter=self.xet_bloom_filter,
                    )
                    self.protocol_manager.register_protocol(xet_protocol)
                    await self.protocol_manager.start_protocol(ProtocolType.XET)
                    self.logger.info("XET protocol registered with protocol manager")
            except Exception:
                self.logger.warning(
                    "Failed to register XET protocol with protocol manager",
                    exc_info=True,
                )

        # Initialize queue manager if enabled
        if self.config.queue.auto_manage_queue:
            try:
                from ccbt.queue.manager import TorrentQueueManager

                self.queue_manager = TorrentQueueManager(self, self.config.queue)
                await self.queue_manager.start()
                self.logger.info("Queue manager started")
            except Exception:
                # Best-effort: log and continue
                self.logger.warning(
                    "Queue manager initialization failed. Queue management may not work.",
                    exc_info=True,
                )

        # Start periodic scrape loop if auto-scrape enabled
        if self.config.discovery.tracker_auto_scrape:
            try:
                self.scrape_task = self._task_supervisor.create_task(
                    self.scrape_manager.start_periodic_loop(),
                    name="periodic_scrape_loop",
                )
                self.logger.info("Periodic scrape loop started")
            except Exception:
                self.logger.warning(
                    "Failed to start periodic scrape loop",
                    exc_info=True,
                )

        # Initialize metrics if enabled
        if self.config.observability.enable_metrics:
            try:
                self.metrics = Metrics()
                self.logger.info("Metrics initialized")
            except Exception:
                self.logger.warning(
                    "Failed to initialize metrics",
                    exc_info=True,
                )
                self.metrics = None
        else:
            self.metrics = None

        # Start background tasks (cleanup and metrics)
        try:
            self._cleanup_task = self._task_supervisor.create_task(
                self.background_tasks.cleanup_loop(),
                name="manager_cleanup_loop",
            )
            self.logger.info("Manager cleanup loop started")
        except Exception:
            self.logger.warning(
                "Failed to start manager cleanup loop",
                exc_info=True,
            )

        try:
            self._metrics_task = self._task_supervisor.create_task(
                self.background_tasks.metrics_loop(),
                name="manager_metrics_loop",
            )
            self.logger.info("Manager metrics loop started")
        except Exception:
            self.logger.warning(
                "Failed to start manager metrics loop",
                exc_info=True,
            )

        self._session_started = True
        self.logger.info("Async session manager started")

    async def stop(self) -> None:
        """Stop the async session manager and all components."""
        # Stop background tasks first (in correct order)
        if self._cleanup_task:
            try:
                if not self._cleanup_task.done():
                    self._cleanup_task.cancel()
                    with contextlib.suppress(
                        asyncio.CancelledError, asyncio.TimeoutError
                    ):
                        await asyncio.wait_for(self._cleanup_task, timeout=2.0)
                self.logger.info("Manager cleanup loop stopped")
            except Exception:
                self.logger.warning(
                    "Error stopping manager cleanup loop", exc_info=True
                )

        if self._metrics_task:
            try:
                if not self._metrics_task.done():
                    self._metrics_task.cancel()
                    with contextlib.suppress(
                        asyncio.CancelledError, asyncio.TimeoutError
                    ):
                        await asyncio.wait_for(self._metrics_task, timeout=2.0)
                self.logger.info("Manager metrics loop stopped")
            except Exception:
                self.logger.warning(
                    "Error stopping manager metrics loop", exc_info=True
                )

        # Stop periodic scrape loop
        if self.scrape_task:
            try:
                if not self.scrape_task.done():
                    self.scrape_task.cancel()
                    with contextlib.suppress(
                        asyncio.CancelledError, asyncio.TimeoutError
                    ):
                        await asyncio.wait_for(self.scrape_task, timeout=2.0)
                self.logger.info("Periodic scrape loop stopped")
            except Exception:
                self.logger.warning(
                    "Error stopping periodic scrape loop", exc_info=True
                )

        # Stop queue manager if enabled
        if self.queue_manager:
            try:
                await self.queue_manager.stop()
                self.logger.info("Queue manager stopped")
            except Exception:
                self.logger.warning("Error stopping queue manager", exc_info=True)

        try:
            await self.media_stream_manager.stop_all_streams()
        except Exception:
            self.logger.warning("Error stopping media streams", exc_info=True)

        # Stop all XET folder runtimes
        async with self._xet_folders_lock:
            for runtime in list(self.xet_folders.values()):
                if isinstance(runtime, XetFolderRuntime):
                    with contextlib.suppress(Exception):
                        await runtime.stop()

        # Stop all torrent sessions
        async with self.lock:
            for info_hash, session in list(self.torrents.items()):
                try:
                    await session.stop()
                except Exception:
                    self.logger.warning(
                        "Error stopping torrent session %s",
                        info_hash.hex()[:12],
                        exc_info=True,
                    )

        # Stop DHT client
        if self.dht_client:
            try:
                await self.dht_client.stop()
            except Exception:
                self.logger.warning("Error stopping DHT client", exc_info=True)

        # Stop TCP server
        if self.tcp_server:
            try:
                await self.tcp_server.stop()
            except Exception:
                self.logger.warning("Error stopping TCP server", exc_info=True)

        # Stop UDP tracker client
        if self.udp_tracker_client:
            try:
                await self.udp_tracker_client.stop()
            except Exception:
                self.logger.warning("Error stopping UDP tracker client", exc_info=True)

        # Stop protocol manager (unregister all protocols)
        if self.protocol_manager:
            try:
                # Unregister all protocols
                for protocol_type in list(self.protocol_manager.protocols.keys()):
                    try:
                        protocol = self.protocol_manager.protocols[protocol_type]
                        if hasattr(protocol, "stop"):
                            await protocol.stop()
                        await self.protocol_manager.unregister_protocol(protocol_type)
                    except Exception:
                        self.logger.warning(
                            "Error stopping protocol %s", protocol_type, exc_info=True
                        )
                self.logger.info("Protocol manager stopped")
            except Exception:
                self.logger.warning("Error stopping protocol manager", exc_info=True)

        # Stop NAT manager
        if self.nat_manager:
            try:
                await self.nat_manager.stop()
            except Exception:
                self.logger.warning("Error stopping NAT manager", exc_info=True)

        # Clear metrics reference
        self.metrics = None

        self._session_started = False
        self.logger.info("Async session manager stopped")

    async def start_web_interface(
        self, host: str = "127.0.0.1", port: int = 9090
    ) -> None:
        """Start web interface (IPC server) for this session manager.

        Args:
            host: Host to bind to (default: 127.0.0.1)
            port: Port to bind to (default: 9090)

        """
        # Ensure session manager is started
        # Check if already started by looking for initialized components
        if self.dht_client is None and self.tcp_server is None:
            await self.start()

        # Get API key from config or generate a default one for local use
        api_key = (
            getattr(self.config.daemon, "api_key", None)
            if hasattr(self.config, "daemon") and self.config.daemon
            else None
        )
        if not api_key:
            # Generate a simple API key for local web interface
            import secrets

            api_key = secrets.token_urlsafe(32)

        # Create and start IPC server
        from ccbt.daemon.ipc_server import IPCServer

        self.ipc_server = IPCServer(
            session_manager=self,
            api_key=api_key,
            host=host,
            port=port,
            websocket_enabled=True,
        )
        await self.ipc_server.start()
        self.logger.info("Web interface started on http://%s:%d", host, port)

        # Keep running until stopped
        try:
            # Wait indefinitely (server runs in background)
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Web interface stopped by user")
            if self.ipc_server:
                await self.ipc_server.stop()

    async def add_torrent(
        self,
        torrent_path: Union[str, dict[str, Any]],
        output_dir: Optional[str] = None,
        resume: bool = False,
    ) -> str:
        """Add a torrent file or torrent data dictionary.

        Args:
            torrent_path: Path to torrent file or torrent data dictionary
            output_dir: Optional output directory override
            resume: Whether to resume from checkpoint if available

        Returns:
            Info hash as hex string

        """
        from ccbt.core.torrent import TorrentParser

        # Parse torrent file or use provided data
        if isinstance(torrent_path, dict):
            torrent_data = torrent_path
            # When dict has is_magnet but no magnet_info, set it so BEP 53 can apply after metadata
            if (
                isinstance(torrent_data, dict)
                and torrent_data.get("is_magnet")
                and not torrent_data.get("magnet_info")
            ):
                from ccbt.core.magnet import magnet_info_from_minimal_torrent_data

                try:
                    torrent_data["magnet_info"] = magnet_info_from_minimal_torrent_data(
                        torrent_data
                    )
                except (ValueError, KeyError) as e:
                    self.logger.debug(
                        "Could not build magnet_info from minimal torrent_data: %s",
                        e,
                    )
        else:
            parser = TorrentParser()
            torrent_data = parser.parse(torrent_path)

        # Get info hash - handle both dict and model objects
        if isinstance(torrent_data, dict):
            info_hash = torrent_data.get("info_hash")
            if info_hash is None:
                msg = "Missing info_hash"
                raise ValueError(msg)  # Specific error for debugging
        else:
            # TorrentInfo model object
            info_hash = getattr(torrent_data, "info_hash", None)
            if info_hash is None:
                msg = "Missing info_hash in torrent data"
                raise ValueError(msg)  # Specific error for debugging

        if isinstance(info_hash, str):
            info_hash = bytes.fromhex(info_hash)

        # Check if already exists
        async with self.lock:
            if info_hash in self.torrents:
                error_msg = f"Torrent already exists: {info_hash.hex()}"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)

            # Create session
            session_output_dir = output_dir or self.output_dir
            session = AsyncTorrentSession(torrent_data, session_output_dir, self)
            self.torrents[info_hash] = session

        # Add to private_torrents set if torrent is private (BEP 27)
        if session.is_private:
            self.private_torrents.add(info_hash)

        # Get torrent name for callback
        if isinstance(torrent_data, dict):
            torrent_name = torrent_data.get("name", "Unknown")
        else:
            torrent_name = getattr(torrent_data, "name", "Unknown")

        # Invoke callback if set
        if self.on_torrent_added:
            try:
                if asyncio.iscoroutinefunction(self.on_torrent_added):
                    await self.on_torrent_added(info_hash, torrent_name)
                else:
                    self.on_torrent_added(info_hash, torrent_name)
            except Exception:
                self.logger.exception("Error in on_torrent_added callback")

        # Start session in background
        await self.torrent_addition_handler.add_torrent_background(
            session, info_hash, resume
        )

        # Trigger auto-scrape if enabled
        if self.config.discovery.tracker_auto_scrape:
            # Start auto-scrape in background (non-blocking) - fire-and-forget
            asyncio.create_task(self._auto_scrape_torrent(info_hash.hex()))  # noqa: RUF006

        return info_hash.hex()

    async def add_magnet(
        self,
        magnet_uri: str,
        output_dir: Optional[str] = None,
        resume: bool = False,
    ) -> str:
        """Add a magnet link.

        Args:
            magnet_uri: Magnet URI string
            output_dir: Optional output directory override
            resume: Whether to resume from checkpoint if available

        Returns:
            Info hash as hex string

        """
        # Parse magnet URI
        magnet_info = parse_magnet(magnet_uri)
        info_hash = magnet_info.info_hash

        # Check if already exists
        async with self.lock:
            if info_hash in self.torrents:
                error_msg = f"Torrent already exists: {info_hash.hex()}"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)

            # Build minimal torrent data from magnet
            torrent_data = build_minimal_torrent_data(
                magnet_info.info_hash,
                magnet_info.display_name or "Unknown",
                magnet_info.trackers or [],
                magnet_info.web_seeds or [],
            )
            # Store magnet info in torrent_data for later use
            torrent_data["magnet_uri"] = magnet_uri
            torrent_data["magnet_info"] = magnet_info

            # Create session
            session_output_dir = output_dir or self.output_dir
            session = AsyncTorrentSession(torrent_data, session_output_dir, self)
            self.torrents[info_hash] = session

        # Get torrent name for callback
        torrent_name = magnet_info.display_name or "Unknown"

        # Invoke callback if set
        if self.on_torrent_added:
            try:
                if asyncio.iscoroutinefunction(self.on_torrent_added):
                    await self.on_torrent_added(info_hash, torrent_name)
                else:
                    self.on_torrent_added(info_hash, torrent_name)
            except Exception:
                self.logger.exception("Error in on_torrent_added callback")

        # Start session in background (will handle magnet metadata fetch)
        await self.torrent_addition_handler.add_torrent_background(
            session, info_hash, resume
        )

        # Trigger auto-scrape if enabled
        if self.config.discovery.tracker_auto_scrape:
            # Start auto-scrape in background (non-blocking) - fire-and-forget
            asyncio.create_task(self._auto_scrape_torrent(info_hash.hex()))  # noqa: RUF006

        return info_hash.hex()

    async def cleanup_completed_checkpoints(self) -> int:
        """Clean up checkpoints for completed downloads.

        Returns:
            Number of checkpoints cleaned up

        """
        return await self.checkpoint_ops.cleanup_completed()

    async def force_scrape(self, info_hash_hex: str) -> bool:
        """Force tracker scrape for a torrent.

        Args:
            info_hash_hex: Info hash in hex format (40 characters)

        Returns:
            True if scrape was successful, False otherwise

        """
        return await self.scrape_manager.force_scrape(info_hash_hex)

    async def get_scrape_result(self, info_hash_hex: str) -> Optional[Any]:
        """Get cached scrape result for a torrent.

        Args:
            info_hash_hex: Info hash in hex format (40 characters)

        Returns:
            ScrapeResult if cached, None otherwise

        """
        return await self.scrape_manager.get_cached_result(info_hash_hex)

    def _is_scrape_stale(self, scrape_result: Any) -> bool:
        """Check if scrape result is stale based on interval.

        Args:
            scrape_result: Cached scrape result (ScrapeResult)

        Returns:
            True if scrape is stale and should be refreshed

        """
        return self.scrape_manager.is_stale(scrape_result)

    async def _auto_scrape_torrent(self, info_hash_hex: str) -> None:
        """Auto-scrape a torrent after adding (background task).

        Args:
            info_hash_hex: Info hash in hex format

        """
        try:
            # Wait a short delay to ensure torrent is fully initialized
            await asyncio.sleep(2.0)

            # Perform scrape using session manager's force_scrape method
            # This allows tests to mock force_scrape on the session manager
            await self.force_scrape(info_hash_hex)

            self.logger.debug("Auto-scrape completed for %s", info_hash_hex)
        except Exception:
            self.logger.debug("Auto-scrape failed for %s", info_hash_hex, exc_info=True)

    def parse_magnet_link(self, magnet_uri: str) -> Optional[dict[str, Any]]:
        """Parse magnet link and return torrent data.

        Args:
            magnet_uri: Magnet URI string

        Returns:
            Dictionary with minimal torrent data or None if parsing fails

        """
        from ccbt.session.torrent_utils import parse_magnet_link as parse_magnet

        return parse_magnet(magnet_uri, logger=self.logger)

    async def set_rate_limits(
        self, info_hash_hex: str, download_kib: int, upload_kib: int
    ) -> bool:
        """Set per-torrent rate limits.

        Args:
            info_hash_hex: Info hash in hex format
            download_kib: Download limit in KiB/s (0 = unlimited, negative values rejected)
            upload_kib: Upload limit in KiB/s (0 = unlimited, negative values rejected)

        Returns:
            True if limits were set, False if torrent not found or invalid values

        """
        # Reject negative values
        if download_kib < 0 or upload_kib < 0:
            self.logger.warning(
                "Rate limits must be non-negative: download_kib=%d, upload_kib=%d",
                download_kib,
                upload_kib,
            )
            return False

        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            self.logger.debug("Invalid info_hash format: %s", info_hash_hex)
            return False

        with contextlib.suppress(Exception):
            await self.media_stream_manager.stop_stream_for_torrent(info_hash_hex)

        async with self.lock:
            session = self.torrents.get(info_hash)
            if not session:
                self.logger.debug("Torrent not found: %s", info_hash_hex)
                return False

            if download_kib == 0 and upload_kib == 0:
                # Remove entry if both limits are zero (treat as unlimited)
                self._per_torrent_limits.pop(info_hash, None)
            else:
                # Store limits for reporting (use both key formats for compatibility)
                self._per_torrent_limits[info_hash] = {  # type: ignore[assignment]
                    "download_kib": download_kib,
                    "upload_kib": upload_kib,
                    "down_kib": download_kib,  # Compatibility key
                    "up_kib": upload_kib,  # Compatibility key
                }

            # TODO: Apply limits to session's peer manager when rate limiting is implemented
            # For now, just store the limits

        return True

    def get_per_torrent_limits(self, info_hash: bytes) -> Optional[dict[str, int]]:
        """Get per-torrent rate limits (public API).

        Args:
            info_hash: Torrent info hash as bytes

        Returns:
            Dictionary with rate limits (download_kib, upload_kib) or None if not set

        """
        return self._per_torrent_limits.get(info_hash)

    async def global_set_rate_limits(self, download_kib: int, upload_kib: int) -> bool:
        """Set global rate limits.

        Args:
            download_kib: Global download limit in KiB/s (0 = unlimited)
            upload_kib: Global upload limit in KiB/s (0 = unlimited)

        Returns:
            True if limits were set

        """
        # Update config
        self.config.limits.global_down_kib = download_kib
        self.config.limits.global_up_kib = upload_kib

        self.logger.info(
            "Global rate limits updated: down=%d KiB/s, up=%d KiB/s",
            download_kib,
            upload_kib,
        )

        # TODO: Apply limits to peer service when rate limiting is implemented

        return True

    async def get_peers_for_torrent(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Get list of connected peers for a torrent.

        Args:
            info_hash_hex: Info hash in hex format

        Returns:
            List of peer dictionaries with ip, port, and status

        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            self.logger.debug("Invalid info_hash format: %s", info_hash_hex)
            return []

        async with self.lock:
            session = self.torrents.get(info_hash)
            if not session:
                self.logger.debug("Torrent not found: %s", info_hash_hex)
                return []

            # Get peers from peer manager
            if hasattr(session, "peer_manager") and session.peer_manager:
                return [
                    {
                        "ip": peer.ip,
                        "port": peer.port,
                        "client": getattr(peer, "client", "Unknown"),
                        "uploaded": getattr(peer, "uploaded", 0),
                        "downloaded": getattr(peer, "downloaded", 0),
                        "left": getattr(peer, "left", 0),
                        "state": getattr(peer, "state", "unknown"),
                    }
                    for peer in session.peer_manager.get_peers()  # type: ignore[union-attr]
                ]

        return []

    async def force_announce(self, info_hash_hex: str) -> bool:
        """Force immediate tracker announce for a torrent.

        Args:
            info_hash_hex: Info hash in hex format

        Returns:
            True if announce was triggered, False if torrent not found

        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            self.logger.debug("Invalid info_hash format: %s", info_hash_hex)
            return False

        async with self.lock:
            session = self.torrents.get(info_hash)
            if not session:
                self.logger.debug("Torrent not found: %s", info_hash_hex)
                return False

            # Trigger immediate announce
            if hasattr(session, "tracker") and session.tracker:
                try:
                    # Get torrent_data for announce
                    # Use _normalized_td if available, otherwise normalize torrent_data
                    if hasattr(session, "_normalized_td"):
                        normalized_td = session._normalized_td
                    elif hasattr(session, "torrent_data"):
                        # Normalize torrent_data on the fly
                        if isinstance(session.torrent_data, dict):
                            normalized_td = session.torrent_data
                        else:
                            # Convert model to dict
                            normalized_td = {
                                "info_hash": getattr(
                                    session.torrent_data, "info_hash", None
                                ),
                                "name": getattr(session.torrent_data, "name", ""),
                                "announce": getattr(
                                    session.torrent_data, "announce", ""
                                ),
                            }
                    else:
                        # Fallback: create minimal dict from info
                        normalized_td = {
                            "info_hash": getattr(session.info, "info_hash", info_hash),
                            "name": getattr(session.info, "name", ""),
                            "announce": "",
                        }

                    # Try to use AnnounceController if we have all required attributes
                    # Otherwise, call tracker.announce() directly (for tests/mocks)
                    has_all_attrs = all(
                        hasattr(session, attr)
                        for attr in [
                            "config",
                            "output_dir",
                            "info",
                            "logger",
                            "piece_manager",
                            "checkpoint_manager",
                            "download_manager",
                        ]
                    )

                    if has_all_attrs:
                        from typing import cast

                        from ccbt.session.announce import AnnounceController
                        from ccbt.session.models import SessionContext

                        ctx = SessionContext(
                            config=session.config,
                            torrent_data=normalized_td,
                            output_dir=session.output_dir,
                            info=session.info,
                            session_manager=self,
                            logger=session.logger,
                            piece_manager=session.piece_manager,
                            peer_manager=getattr(session, "peer_manager", None),
                            tracker=session.tracker,
                            dht_client=self.dht_client,
                            checkpoint_manager=session.checkpoint_manager,
                            download_manager=session.download_manager,
                            file_selection_manager=getattr(
                                session, "file_selection_manager", None
                            ),
                        )
                        announce_controller = AnnounceController(
                            ctx, cast("TrackerClientProtocol", session.tracker)
                        )  # type: ignore[arg-type]
                        await announce_controller.announce_initial()
                    # For mock sessions or when attributes are missing, call tracker.announce() directly
                    elif asyncio.iscoroutinefunction(session.tracker.announce):
                        await session.tracker.announce(normalized_td)
                    else:
                        session.tracker.announce(normalized_td)
                    return True
                except Exception:
                    self.logger.exception(
                        "Error forcing announce for %s", info_hash_hex
                    )
                    return False

        return False

    async def export_session_state(self, path: Union[Path, str]) -> None:
        """Export session state to JSON file.

        Args:
            path: Path to output JSON file

        """
        import json

        path = Path(path)

        # Collect session state
        state = {
            "torrents": [],
            "global_limits": {
                "download_kib": self.config.limits.global_down_kib,
                "upload_kib": self.config.limits.global_up_kib,
            },
            "config": {
                "network": {
                    "port": self.config.network.listen_port,
                },
            },
        }

        async with self.lock:
            for info_hash, session in self.torrents.items():
                # Get peers count safely (may fail if peer_service is not initialized)
                peers_count = 0
                try:
                    # Note: Add timeout to prevent hanging in tests or when peer_service is slow
                    peers = await asyncio.wait_for(
                        self.get_peers_for_torrent(info_hash.hex()),
                        timeout=5.0,
                    )
                    peers_count = len(peers) if peers else 0
                except (Exception, asyncio.TimeoutError):
                    # If get_peers_for_torrent fails (e.g., peer_service not initialized) or times out, use 0
                    peers_count = 0

                torrent_state = {
                    "info_hash": info_hash.hex(),
                    "name": getattr(session.info, "name", "Unknown")
                    if hasattr(session, "info")
                    else "Unknown",
                    "status": getattr(session, "state", "unknown"),
                    "progress": getattr(session, "progress", 0.0),
                    "downloaded": getattr(session, "downloaded", 0),
                    "uploaded": getattr(session, "uploaded", 0),
                    "peers": peers_count,
                }
                state["torrents"].append(torrent_state)  # type: ignore[union-attr]

        # Write to file
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(state, f, indent=2)

        self.logger.info("Session state exported to %s", path)

    async def import_session_state(self, path: Union[Path, str]) -> dict[str, Any]:
        """Import session state from JSON file.

        Args:
            path: Path to input JSON file

        Returns:
            Dictionary containing imported session state

        Raises:
            FileNotFoundError: If the file does not exist
            json.JSONDecodeError: If the JSON is malformed

        """
        import json

        path = Path(path)
        if not path.exists():
            error_msg = f"Session state file not found: {path}"
            raise FileNotFoundError(error_msg)  # Detailed path for debugging

        # Read and parse JSON file
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.logger.info("Session state imported from %s", path)
        return data

    @property
    def peers(self) -> list[Any]:
        """Get all connected peers from all torrents.

        Returns:
            List of peer objects from all active torrents

        """
        all_peers = []
        # Note: This is a synchronous property, so we can't use async lock
        # For thread safety, this should ideally be async, but status command expects sync
        # We'll access torrents directly (they should be stable during status display)
        for session in self.torrents.values():
            if hasattr(session, "peer_manager") and session.peer_manager:
                try:
                    peers = session.peer_manager.get_peers()  # type: ignore[union-attr]
                    all_peers.extend(peers)
                except Exception:
                    # Ignore errors when accessing peer manager
                    pass
        return all_peers

    @property
    def dht(self) -> Optional[Any]:
        """Get DHT client for status display compatibility.

        Returns:
            DHT client instance or None

        """
        return self.dht_client

    async def remove(self, info_hash_hex: str) -> bool:
        """Remove a torrent from the session manager.

        Args:
            info_hash_hex: Info hash in hex format

        Returns:
            True if torrent was removed, False if not found

        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            self.logger.debug("Invalid info_hash format: %s", info_hash_hex)
            return False

        async with self.lock:
            session = self.torrents.get(info_hash)
            if not session:
                self.logger.debug("Torrent not found: %s", info_hash_hex)
                return False

            # Stop the session
            try:
                await session.stop()
            except Exception:
                self.logger.warning(
                    "Error stopping torrent session %s",
                    info_hash_hex[:12],
                    exc_info=True,
                )

            # Remove from torrents dict
            del self.torrents[info_hash]

            # Clear per-torrent rate limits
            self._per_torrent_limits.pop(info_hash, None)

            # Clear scrape cache for this torrent
            async with self.scrape_cache_lock:
                self.scrape_cache.pop(info_hash, None)

            # Remove from queue manager if enabled
            if self.queue_manager:
                try:
                    await self.queue_manager.remove_torrent(info_hash)
                except Exception:
                    self.logger.debug(
                        "Error removing torrent from queue", exc_info=True
                    )

            # Call callback if set
            # Invoke callback if set
            if self.on_torrent_removed:
                try:
                    if asyncio.iscoroutinefunction(self.on_torrent_removed):
                        await self.on_torrent_removed(info_hash)
                    else:
                        self.on_torrent_removed(info_hash)
                except Exception:
                    self.logger.exception("Error in on_torrent_removed callback")

            self.logger.info("Torrent removed: %s", info_hash_hex)
            return True

    async def start_media_stream(
        self,
        info_hash_hex: str,
        file_index: int,
        port: Optional[int] = None,
    ) -> dict[str, Any]:
        """Start a media stream for a torrent file."""
        return await self.media_stream_manager.start_stream(
            info_hash_hex,
            file_index=file_index,
            port=port,
        )

    async def stop_media_stream(self, stream_id: str) -> bool:
        """Stop an active media stream."""
        return await self.media_stream_manager.stop_stream(stream_id)

    async def get_media_stream_status(
        self,
        *,
        stream_id: Optional[str] = None,
        info_hash_hex: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Return the status for an active media stream."""
        return await self.media_stream_manager.get_status(
            stream_id=stream_id,
            info_hash_hex=info_hash_hex,
        )

    async def stop_all_media_streams(self) -> None:
        """Stop all active media streams."""
        await self.media_stream_manager.stop_all_streams()

    async def register_xet_metadata(
        self, workspace_id_hex: str, metadata_bytes: bytes
    ) -> None:
        """Register the latest metadata snapshot for a workspace."""
        async with self._xet_folders_lock:
            self._xet_metadata_registry[workspace_id_hex] = metadata_bytes
            self._xet_metadata_version_registry[workspace_id_hex] = (
                self._compute_xet_metadata_version(metadata_bytes)
            )

    async def get_registered_xet_metadata(
        self, workspace_id_hex: str
    ) -> Optional[bytes]:
        """Return cached tonic metadata for a workspace."""
        async with self._xet_folders_lock:
            return self._xet_metadata_registry.get(workspace_id_hex)

    def _compute_xet_metadata_version(self, metadata_bytes: bytes) -> str:
        """Return a stable version string for a metadata snapshot."""
        return hashlib.sha256(metadata_bytes).hexdigest()

    async def get_registered_xet_metadata_version(
        self, workspace_id_hex: str
    ) -> Optional[str]:
        """Return the current metadata version string for a workspace."""
        async with self._xet_folders_lock:
            return self._xet_metadata_version_registry.get(workspace_id_hex)

    async def fetch_xet_metadata(
        self, workspace_id_hex: str, expected_version: Optional[str] = None
    ) -> Optional[bytes]:
        """Fetch tonic metadata for a workspace.

        Resolve against the live local registry first, then attempt transport-backed
        retrieval from currently connected XET-capable peers.
        """
        async with self._xet_folders_lock:
            cached = self._xet_metadata_registry.get(workspace_id_hex)
            cached_version = self._xet_metadata_version_registry.get(workspace_id_hex)
            if cached is not None and (
                expected_version is None or cached_version == expected_version
            ):
                return cached
            for runtime in self.xet_folders.values():
                if (
                    isinstance(runtime, XetFolderRuntime)
                    and runtime.workspace_id.hex() == workspace_id_hex
                    and runtime.folder is not None
                    and runtime.folder.metadata_bytes
                ):
                    if expected_version is None:
                        return runtime.folder.metadata_bytes
                    runtime_version = self._compute_xet_metadata_version(
                        runtime.folder.metadata_bytes
                    )
                    if runtime_version == expected_version:
                        return runtime.folder.metadata_bytes
        xet_ext = getattr(self, "extension_manager", None)
        if xet_ext is None:
            return None
        xet_ext = (
            self.extension_manager.extensions.get("xet")
            if self.extension_manager
            else None
        )
        if xet_ext is None or xet_ext.metadata_exchange is None:
            return None

        workspace_id = bytes.fromhex(workspace_id_hex)
        peers = self._get_xet_peer_ids(workspace_id_hex)
        if not peers:
            return None

        futures = [
            xet_ext.metadata_exchange.request_metadata(peer_id, workspace_id)
            for peer_id in peers
        ]
        if not futures:
            return None

        done, pending = await asyncio.wait(
            [asyncio.create_task(future) for future in futures],
            timeout=10.0,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            with contextlib.suppress(Exception):
                metadata_bytes = task.result()
                if metadata_bytes:
                    await self.register_xet_metadata(workspace_id_hex, metadata_bytes)
                    return metadata_bytes
        return None

    def _get_any_xet_git_ref(self) -> Optional[str]:
        """Return a representative git ref for XET transport responses."""
        for runtime in self.xet_folders.values():
            if isinstance(runtime, XetFolderRuntime) and runtime.folder is not None:
                git_ref = runtime.folder.sync_manager.get_current_git_ref()
                if git_ref:
                    return git_ref
        return None

    def get_xet_transport_state(
        self, workspace_id_hex: Optional[str] = None
    ) -> Optional[XetTransportState]:
        """Return live XET transport state for handshake construction.

        When workspace_id_hex is None and multiple XET runtimes exist, returns
        None and logs (caller must pass workspace_id_hex for multi-workspace).
        """
        from ccbt.storage.xet_hashing import XetHasher

        if workspace_id_hex is not None:
            state = self._xet_transport_registry.get(workspace_id_hex)
            if state is not None:
                return cast("XetTransportState", dict(state))

        matching_runtimes = [
            runtime
            for runtime in self.xet_folders.values()
            if isinstance(runtime, XetFolderRuntime)
        ]
        if len(matching_runtimes) == 0:
            return None
        if len(matching_runtimes) > 1:
            self.logger.debug(
                "get_xet_transport_state(workspace_id_hex=None) with %d runtimes: "
                "returning None; pass workspace_id_hex for multi-workspace",
                len(matching_runtimes),
            )
            return None
        runtime = matching_runtimes[0]
        folder = runtime.folder
        git_ref = runtime.git_ref
        allowlist_hash = runtime.allowlist_hash
        if folder is not None:
            git_ref = folder.sync_manager.get_current_git_ref() or git_ref
            allowlist_hash = folder.sync_manager.get_allowlist_hash() or allowlist_hash
        reg = self._xet_transport_registry.get(runtime.workspace_id.hex(), {})
        result: XetTransportState = {
            "workspace_id": runtime.workspace_id,
            "workspace_id_hex": runtime.workspace_id.hex(),
            "sync_mode": runtime.sync_mode,
            "git_ref": git_ref,
            "allowlist_hash": allowlist_hash,
            "source_peers": list(runtime.source_peers),
            "hash_algorithm": runtime.hash_algorithm or XetHasher.get_hash_algorithm(),
            "auth_scope": runtime.auth_scope,
            "allowlist_path": runtime.allowlist_path,
            "require_signed_metadata": runtime.require_signed_metadata,
            "backend_status": self.get_xet_discovery_status(),
            "allowlist": reg.get("allowlist"),
        }
        if reg.get("downgrade_reason") is not None:
            result["downgrade_reason"] = reg["downgrade_reason"]
        if reg.get("backend_eligibility") is not None:
            result["backend_eligibility"] = reg["backend_eligibility"]
        return result

    async def _load_xet_allowlist(
        self, allowlist_path: Optional[str]
    ) -> Optional[XetAllowlist]:
        """Load a workspace allowlist when a path is configured."""
        if not allowlist_path:
            return None
        allowlist = XetAllowlist(
            allowlist_path=allowlist_path,
            key_manager=self.key_manager,
        )
        await allowlist.load()
        return allowlist

    async def _handle_incoming_xet_update(
        self,
        peer_id: str,
        workspace_id_hex: Optional[str],
        file_path: str,
        chunk_hash: bytes,
        git_ref: Optional[str],
        operation: str = "upsert",
        metadata_version: Optional[str] = None,
        metadata_root: Optional[str] = None,
    ) -> None:
        """Route an incoming XET update to the matching workspace runtime."""
        runtimes: list[XetFolderRuntime] = []
        async with self._xet_folders_lock:
            if workspace_id_hex:
                runtimes = [
                    runtime
                    for runtime in self.xet_folders.values()
                    if isinstance(runtime, XetFolderRuntime)
                    and runtime.workspace_id.hex() == workspace_id_hex
                    and runtime.folder is not None
                ]
            else:
                runtimes = [
                    runtime
                    for runtime in self.xet_folders.values()
                    if isinstance(runtime, XetFolderRuntime)
                    and runtime.folder is not None
                ]
        if workspace_id_hex is None and len(runtimes) > 1:
            self.logger.warning(
                "Ignoring legacy XET update without workspace id for %d runtimes",
                len(runtimes),
            )
            return

        metadata_bytes: Optional[bytes] = None
        if workspace_id_hex is not None:
            if metadata_version is not None:
                current_version = await self.get_registered_xet_metadata_version(
                    workspace_id_hex
                )
                if current_version != metadata_version:
                    metadata_bytes = await self.fetch_xet_metadata(
                        workspace_id_hex,
                        expected_version=metadata_version,
                    )
                    refreshed_version = await self.get_registered_xet_metadata_version(
                        workspace_id_hex
                    )
                    if refreshed_version != metadata_version:
                        self.logger.warning(
                            "Ignoring XET update for workspace %s due to metadata version mismatch (expected=%s got=%s)",
                            workspace_id_hex,
                            metadata_version,
                            refreshed_version,
                        )
                        return
            if metadata_root is not None:
                # Reserved for future strict root checks once metadata root storage is
                # persisted in session/runtime state.
                self.logger.debug(
                    "Received metadata_root=%s for workspace %s",
                    metadata_root,
                    workspace_id_hex,
                )
            metadata_bytes = await self.fetch_xet_metadata(workspace_id_hex)
        for runtime in runtimes:
            folder = runtime.folder
            if folder is None:
                continue
            file_metadata = folder.sync_manager.get_file_metadata(file_path)
            if file_metadata is None:
                file_metadata = folder._get_file_metadata_from_snapshot(file_path)
            if file_metadata is None and metadata_bytes is not None:
                await folder.apply_remote_metadata_snapshot(metadata_bytes)
                file_metadata = folder.sync_manager.get_file_metadata(file_path)
                if file_metadata is None:
                    file_metadata = folder._get_file_metadata_from_snapshot(file_path)
            deleted = operation == "delete"
            if file_metadata is None and not deleted and chunk_hash != bytes(32):
                folder.sync_manager.set_last_error(
                    f"Missing metadata for incoming update: {file_path}"
                )
                self.logger.warning(
                    "Skipping XET update for %s in workspace %s because metadata is unavailable",
                    file_path,
                    workspace_id_hex or runtime.workspace_id.hex(),
                )
                continue
            await folder.sync_manager.queue_update(
                file_path=file_path,
                chunk_hash=chunk_hash,
                git_ref=git_ref,
                source_peer=peer_id,
                file_metadata=file_metadata,
                deleted=deleted,
            )

    def _provide_any_xet_chunk(self, chunk_hash: bytes) -> Optional[bytes]:
        """Serve chunk bytes from any active local XET workspace runtime."""
        for runtime in self.xet_folders.values():
            if not isinstance(runtime, XetFolderRuntime) or runtime.folder is None:
                continue
            with contextlib.suppress(Exception):
                cursor = runtime.folder.dedup.db.execute(
                    "SELECT storage_path FROM chunks WHERE hash = ?",
                    (chunk_hash,),
                )
                row = cursor.fetchone()
                if row:
                    return Path(row[0]).read_bytes()
        return None

    def _get_xet_peer_ids(self, workspace_id_hex: Optional[str] = None) -> list[str]:
        """Return currently connected peer identifiers that may carry XET messages."""
        peer_ids: set[str] = set()
        for session in self.torrents.values():
            peer_manager = getattr(session, "peer_manager", None)
            connections = getattr(peer_manager, "connections", None)
            if not isinstance(connections, dict):
                continue
            for connection in connections.values():
                peer_info = getattr(connection, "peer_info", None)
                if peer_info is None:
                    continue
                peer_id = str(peer_info)
                if hasattr(
                    peer_manager, "is_peer_xet_authorized"
                ) and not peer_manager.is_peer_xet_authorized(  # type: ignore[attr-defined]
                    peer_id,
                    workspace_id_hex=workspace_id_hex,
                ):
                    continue
                if peer_info is not None:
                    peer_ids.add(str(peer_info))
        return sorted(peer_ids)

    async def get_xet_connection_manager(self, peer: Any) -> Optional[Any]:
        """Return the live peer manager for a matching connected peer if present."""
        peer_ip = getattr(peer, "ip", None)
        peer_port = getattr(peer, "port", None)
        if peer_ip is None or peer_port is None:
            return None
        for session in self.torrents.values():
            peer_manager = getattr(session, "peer_manager", None)
            connections = getattr(peer_manager, "connections", None)
            if peer_manager is None or not isinstance(connections, dict):
                continue
            for connection in connections.values():
                peer_info = getattr(connection, "peer_info", None)
                if (
                    peer_info is not None
                    and getattr(peer_info, "ip", None) == peer_ip
                    and getattr(peer_info, "port", None) == peer_port
                ):
                    return peer_manager
        return None

    async def _send_xet_message(self, peer_id: str, payload: bytes) -> bool:
        """Send an outbound XET BEP 10 message to an active peer connection."""
        if self.extension_manager is None:
            return False
        protocol_ext = self.extension_manager.extensions.get("protocol")
        if protocol_ext is None:
            return False
        peer_xet_message_id = protocol_ext.get_peer_message_id(peer_id, "xet")
        if peer_xet_message_id is None:
            return False
        from ccbt.protocols.bittorrent_v2 import _send_extension_message

        for session in self.torrents.values():
            peer_manager = getattr(session, "peer_manager", None)
            connections = getattr(peer_manager, "connections", None)
            if not isinstance(connections, dict):
                continue
            for connection in connections.values():
                peer_info = getattr(connection, "peer_info", None)
                if peer_info is None or str(peer_info) != peer_id:
                    continue
                if getattr(connection, "writer", None) is None:
                    continue
                return await _send_extension_message(
                    connection,
                    peer_xet_message_id,
                    payload,
                )
        return False

    async def _request_xet_metadata_piece(
        self, peer_id: str, info_hash: bytes, piece: int
    ) -> bool:
        """Request a single workspace metadata piece from an active peer."""
        if self.extension_manager is None:
            return False
        xet_ext = self.extension_manager.extensions.get("xet")
        if xet_ext is None:
            return False
        request = xet_ext.metadata_exchange.encode_metadata_request(info_hash, piece)
        return await self._send_xet_message(peer_id, request)

    async def fetch_xet_chunk(
        self,
        workspace_id_hex: str,
        chunk_hash: bytes,
        exclude_folder_key: Optional[str] = None,
    ) -> Optional[bytes]:
        """Return chunk bytes from another active runtime for the same workspace."""
        async with self._xet_folders_lock:
            runtimes = [
                runtime
                for runtime in self.xet_folders.values()
                if isinstance(runtime, XetFolderRuntime)
                and runtime.workspace_id.hex() == workspace_id_hex
                and runtime.folder is not None
                and runtime.folder_key != exclude_folder_key
            ]
        for runtime in runtimes:
            with contextlib.suppress(Exception):
                chunk_bytes = await runtime.folder.get_chunk_bytes(chunk_hash)
                if chunk_bytes is not None:
                    return chunk_bytes
        return None

    async def broadcast_xet_update(
        self,
        workspace_id_hex: str,
        source_folder_key: Optional[str],
        file_path: str,
        chunk_hash: bytes,
        git_ref: Optional[str],
        file_metadata: Optional[Any] = None,
        deleted: bool = False,
    ) -> None:
        """Broadcast a workspace update to sibling runtimes and active peers."""
        async with self._xet_folders_lock:
            runtimes = [
                runtime
                for runtime in self.xet_folders.values()
                if isinstance(runtime, XetFolderRuntime)
                and runtime.workspace_id.hex() == workspace_id_hex
                and runtime.folder is not None
                and runtime.folder_key != source_folder_key
            ]
        for runtime in runtimes:
            await runtime.folder.sync_manager.queue_update(
                file_path=file_path,
                chunk_hash=chunk_hash,
                git_ref=git_ref,
                source_peer=source_folder_key,
                file_metadata=file_metadata,
                deleted=deleted,
            )

        if self.extension_manager is None:
            return
        xet_ext = self.extension_manager.extensions.get("xet")
        if xet_ext is None:
            return
        payload = xet_ext.encode_update_notify(
            file_path=file_path,
            chunk_hash=chunk_hash,
            git_ref=git_ref,
            workspace_id=bytes.fromhex(workspace_id_hex),
            operation="delete" if deleted else "upsert",
            metadata_version=await self.get_registered_xet_metadata_version(
                workspace_id_hex
            ),
        )
        for peer_id in self._get_xet_peer_ids(workspace_id_hex):
            with contextlib.suppress(Exception):
                await self._send_xet_message(peer_id, payload)

    async def add_xet_folder(
        self,
        folder_path: str,
        tonic_file: Optional[str] = None,
        tonic_link: Optional[str] = None,
        sync_mode: Optional[str] = None,
        source_peers: Optional[list[str]] = None,
        check_interval: Optional[float] = None,
        folder_key: Optional[str] = None,
        metadata_bytes: Optional[bytes] = None,
        allowlist_path: Optional[str] = None,
        auth_scope: Optional[str] = None,
        require_signed_metadata: Optional[bool] = None,
        hash_algorithm: Optional[str] = None,
    ) -> AddXetFolderResult:
        """Register and start an XET workspace runtime."""
        from ccbt.storage.xet_hashing import XetHasher

        resolved_folder_path = Path(folder_path).resolve()
        tonic_input = tonic_link or tonic_file
        if metadata_bytes is not None and folder_key is not None:
            parsed_metadata = self._xet_metadata_resolver._tonic_file.parse_bytes(
                metadata_bytes
            )
            workspace_id = bytes.fromhex(folder_key)
            tonic_source = tonic_input or str(resolved_folder_path)
        elif tonic_input:
            resolved = await self._xet_metadata_resolver.resolve(
                tonic_input, session_manager=self
            )
            workspace_id = resolved.workspace_id
            metadata_bytes = resolved.metadata_bytes
            parsed_metadata = resolved.parsed_metadata
            tonic_source = resolved.tonic_source
        else:
            preview_folder = XetFolder(
                folder_path=resolved_folder_path,
                sync_mode=sync_mode or self.config.xet_sync.default_sync_mode,
                source_peers=source_peers,
                check_interval=check_interval or self.config.xet_sync.check_interval,
                enable_git=self.config.xet_sync.enable_git_versioning,
                session_manager=self,
                tonic_source=str(resolved_folder_path),
                allowlist_path=allowlist_path or self.config.xet_sync.allowlist_path,
                auth_scope=auth_scope or self.config.xet_sync.auth_scope,
                require_signed_metadata=(
                    self.config.xet_sync.require_signed_metadata
                    if require_signed_metadata is None
                    else require_signed_metadata
                ),
            )
            try:
                await preview_folder._refresh_metadata_snapshot()
                if preview_folder.workspace_id is None:
                    msg = "Failed to derive canonical XET workspace id"
                    raise RuntimeError(msg)
                workspace_id = preview_folder.workspace_id
                metadata_bytes = preview_folder.metadata_bytes or b""
                parsed_metadata = preview_folder.parsed_metadata or {}
            finally:
                preview_folder.dedup.close()
            tonic_source = str(resolved_folder_path)

        workspace_id_hex = workspace_id.hex()
        if folder_key is None:
            path_suffix = sha1_compat(
                str(resolved_folder_path).encode("utf-8"),
                usedforsecurity=False,
            ).hexdigest()[:12]
            folder_key = workspace_id_hex
            async with self._xet_folders_lock:
                existing = self.xet_folders.get(folder_key)
                if (
                    isinstance(existing, XetFolderRuntime)
                    and existing.folder_path != resolved_folder_path
                ):
                    folder_key = f"{workspace_id_hex}:{path_suffix}"
        effective_allowlist_path = allowlist_path or self.config.xet_sync.allowlist_path
        allowlist = await self._load_xet_allowlist(effective_allowlist_path)
        allowlist_hash = parsed_metadata.get("allowlist_hash")
        if allowlist is not None:
            allowlist_hash = allowlist.get_allowlist_hash()

        runtime = XetFolderRuntime(
            folder_key=folder_key,
            folder_path=resolved_folder_path,
            sync_mode=sync_mode or parsed_metadata.get("sync_mode", "best_effort"),
            workspace_id=workspace_id,
            tonic_source=tonic_source,
            metadata_bytes=metadata_bytes,
            parsed_metadata=parsed_metadata,
            source_peers=source_peers or parsed_metadata.get("source_peers") or [],
            allowlist_hash=allowlist_hash,
            allowlist_path=effective_allowlist_path,
            auth_scope=auth_scope or self.config.xet_sync.auth_scope,
            require_signed_metadata=(
                self.config.xet_sync.require_signed_metadata
                if require_signed_metadata is None
                else require_signed_metadata
            ),
            hash_algorithm=hash_algorithm
            or parsed_metadata.get("hash_algorithm")
            or XetHasher.get_hash_algorithm(),
            git_ref=(parsed_metadata.get("git_refs") or [None])[0],
            bootstrap_pending=bool(parsed_metadata),
            metadata_source=(
                "tonic_link" if tonic_link else "tonic_file" if tonic_file else "local"
            ),
            backend_status=self.get_xet_discovery_status(),
        )
        runtime.folder = XetFolder(
            folder_path=resolved_folder_path,
            sync_mode=runtime.sync_mode,
            source_peers=runtime.source_peers,
            check_interval=check_interval or self.config.xet_sync.check_interval,
            enable_git=self.config.xet_sync.enable_git_versioning,
            session_manager=self,
            workspace_id=workspace_id,
            folder_key=folder_key,
            metadata_bytes=metadata_bytes or None,
            parsed_metadata=parsed_metadata or None,
            tonic_source=tonic_source,
            allowlist_path=runtime.allowlist_path,
            auth_scope=runtime.auth_scope,
            require_signed_metadata=runtime.require_signed_metadata,
            hash_algorithm=runtime.hash_algorithm,
        )

        def _make_add_result(rt: XetFolderRuntime) -> AddXetFolderResult:
            return AddXetFolderResult(
                folder_key=rt.folder_key,
                workspace_id=rt.workspace_id.hex(),
                sync_mode=rt.sync_mode,
                folder_name=rt.folder_path.name,
                allowlist_hash=rt.allowlist_hash.hex() if rt.allowlist_hash else None,
            )

        async with self._xet_folders_lock:
            existing_runtime = self.xet_folders.get(folder_key)
            if isinstance(existing_runtime, XetFolderRuntime):
                return _make_add_result(existing_runtime)
            for other_runtime in self.xet_folders.values():
                if (
                    isinstance(other_runtime, XetFolderRuntime)
                    and other_runtime.workspace_id == workspace_id
                    and other_runtime.folder_path == resolved_folder_path
                ):
                    return _make_add_result(other_runtime)
            self.xet_folders[folder_key] = runtime
            if metadata_bytes:
                self._xet_metadata_registry[workspace_id_hex] = metadata_bytes
            xet_sync = self.config.xet_sync
            self._xet_transport_registry[workspace_id_hex] = {
                "workspace_id": workspace_id,
                "workspace_id_hex": workspace_id_hex,
                "sync_mode": runtime.sync_mode,
                "git_ref": runtime.git_ref,
                "allowlist_hash": runtime.allowlist_hash,
                "source_peers": list(runtime.source_peers),
                "hash_algorithm": runtime.hash_algorithm,
                "auth_scope": runtime.auth_scope,
                "allowlist_path": runtime.allowlist_path,
                "require_signed_metadata": runtime.require_signed_metadata,
                "allowlist": allowlist,
                "backend_status": self.get_xet_discovery_status(),
                "backend_eligibility": {
                    "enable_dht": xet_sync.enable_dht,
                    "enable_tracker": xet_sync.enable_tracker,
                    "enable_pex": xet_sync.enable_pex,
                    "enable_catalog": xet_sync.enable_catalog,
                    "enable_bloom": xet_sync.enable_bloom,
                    "enable_lpd": xet_sync.enable_lpd,
                    "enable_gossip": xet_sync.enable_gossip,
                    "enable_multicast": xet_sync.enable_multicast,
                    "enable_flooding": xet_sync.enable_flooding,
                },
                "downgrade_reason": None,
            }

        await runtime.start()
        effective_sync_mode = runtime.folder.sync_manager.get_sync_mode()
        downgrade_reason = runtime.folder.sync_manager.last_error
        runtime.sync_mode = effective_sync_mode
        async with self._xet_folders_lock:
            transport_state = self._xet_transport_registry.get(workspace_id_hex)
            if transport_state is not None:
                transport_state["sync_mode"] = effective_sync_mode
                transport_state["downgrade_reason"] = downgrade_reason
        await self.register_xet_metadata(
            workspace_id_hex,
            runtime.folder.metadata_bytes or metadata_bytes,
        )
        await emit_event(
            Event(
                event_type=EventType.XET_FOLDER_ADDED.value,
                data={
                    "folder_key": folder_key,
                    "folder_path": str(resolved_folder_path),
                    "workspace_id": workspace_id_hex,
                    "sync_mode": runtime.sync_mode,
                    "tonic_source": tonic_source,
                },
            )
        )
        return AddXetFolderResult(
            folder_key=folder_key,
            workspace_id=workspace_id_hex,
            sync_mode=runtime.sync_mode,
            folder_name=resolved_folder_path.name,
            allowlist_hash=runtime.allowlist_hash.hex()
            if runtime.allowlist_hash
            else None,
        )

    async def get_xet_folder_metadata_bytes(self, folder_key: str) -> Optional[bytes]:
        """Return metadata bytes for a registered XET folder, or None if unknown."""
        async with self._xet_folders_lock:
            runtime = self.xet_folders.get(folder_key)
            if not isinstance(runtime, XetFolderRuntime):
                return None
            if runtime.metadata_bytes:
                return runtime.metadata_bytes
            return self._xet_metadata_registry.get(runtime.workspace_id.hex())

    async def remove_xet_folder(self, folder_key: str) -> bool:
        """Stop and remove an XET workspace runtime."""
        async with self._xet_folders_lock:
            runtime = self.xet_folders.get(folder_key)
            if not isinstance(runtime, XetFolderRuntime):
                return False
            del self.xet_folders[folder_key]
            remaining_workspace_runtimes = [
                other_runtime
                for other_runtime in self.xet_folders.values()
                if isinstance(other_runtime, XetFolderRuntime)
                and other_runtime.workspace_id == runtime.workspace_id
            ]
            if not remaining_workspace_runtimes:
                self._xet_metadata_registry.pop(runtime.workspace_id.hex(), None)
                self._xet_metadata_version_registry.pop(
                    runtime.workspace_id.hex(), None
                )
                self._xet_transport_registry.pop(runtime.workspace_id.hex(), None)

        await runtime.stop()
        await emit_event(
            Event(
                event_type=EventType.XET_FOLDER_REMOVED.value,
                data={
                    "folder_key": folder_key,
                    "folder_path": str(runtime.folder_path),
                    "workspace_id": runtime.workspace_id.hex(),
                },
            )
        )
        return True

    async def list_xet_folders(self) -> list[dict[str, Any]]:
        """Return all active XET workspaces."""
        async with self._xet_folders_lock:
            runtimes = [
                runtime
                for runtime in self.xet_folders.values()
                if isinstance(runtime, XetFolderRuntime)
            ]
        return [runtime.to_record() for runtime in runtimes]

    async def get_xet_folder(self, folder_key: str) -> Optional[XetFolder]:
        """Return the live folder object for a workspace key."""
        async with self._xet_folders_lock:
            runtime = self.xet_folders.get(folder_key)
            if isinstance(runtime, XetFolderRuntime):
                return runtime.folder
        return None

    async def get_xet_folder_status(self, folder_key: str) -> Optional[dict[str, Any]]:
        """Return the live status snapshot for a workspace key."""
        async with self._xet_folders_lock:
            runtime = self.xet_folders.get(folder_key)
            if not isinstance(runtime, XetFolderRuntime) or runtime.folder is None:
                return None
            status = runtime.folder.get_status().model_dump()
            transport_state = self._xet_transport_registry.get(
                runtime.workspace_id.hex()
            )
        if transport_state is not None:
            status["downgrade_reason"] = transport_state.get("downgrade_reason")
            status["backend_status"] = transport_state.get(
                "backend_status", self.get_xet_discovery_status()
            )
        return status

    async def set_xet_folder_sync_mode(
        self,
        folder_key: str,
        sync_mode: str,
        source_peers: Optional[list[str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Update the live sync mode for a registered XET workspace."""
        async with self._xet_folders_lock:
            runtime = self.xet_folders.get(folder_key)
            if not isinstance(runtime, XetFolderRuntime) or runtime.folder is None:
                return None
            runtime.sync_mode = sync_mode
            runtime.source_peers = list(source_peers or [])
            transport_state = self._xet_transport_registry.get(
                runtime.workspace_id.hex()
            )
            if transport_state is not None:
                transport_state["sync_mode"] = sync_mode
                transport_state["source_peers"] = list(runtime.source_peers)

        runtime.folder.set_sync_mode(sync_mode, runtime.source_peers)
        effective_sync_mode = runtime.folder.sync_manager.get_sync_mode()
        downgrade_reason = runtime.folder.sync_manager.last_error
        runtime.sync_mode = effective_sync_mode
        async with self._xet_folders_lock:
            transport_state = self._xet_transport_registry.get(
                runtime.workspace_id.hex()
            )
            if transport_state is not None:
                transport_state["sync_mode"] = effective_sync_mode
                transport_state["source_peers"] = list(runtime.source_peers)
                transport_state["downgrade_reason"] = downgrade_reason
        return {
            "folder_key": folder_key,
            "workspace_id": runtime.workspace_id.hex(),
            "sync_mode": effective_sync_mode,
            "source_peers": list(runtime.source_peers),
            "downgrade_reason": downgrade_reason,
        }

    async def set_xet_workspace_policy(
        self,
        workspace_id_hex: str,
        *,
        sync_mode: Optional[str] = None,
        source_peers: Optional[list[str]] = None,
        auth_scope: Optional[str] = None,
        allowlist_path: Optional[str] = None,
        require_signed_metadata: Optional[bool] = None,
        hash_algorithm: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Update live policy for all active runtimes in a workspace."""
        from ccbt.storage.xet_hashing import XetHasher

        normalized_hash_algorithm: Optional[str] = None
        if hash_algorithm is not None:
            normalized_hash_algorithm = XetHasher.normalize_hash_algorithm(
                hash_algorithm
            )

        async with self._xet_folders_lock:
            runtimes = [
                runtime
                for runtime in self.xet_folders.values()
                if isinstance(runtime, XetFolderRuntime)
                and runtime.workspace_id.hex() == workspace_id_hex
                and runtime.folder is not None
            ]
            if not runtimes:
                return None
            transport_state = self._xet_transport_registry.get(workspace_id_hex)
            for runtime in runtimes:
                if sync_mode is not None:
                    runtime.sync_mode = sync_mode
                if source_peers is not None:
                    runtime.source_peers = list(source_peers)
                if auth_scope is not None:
                    runtime.auth_scope = auth_scope
                if allowlist_path is not None:
                    runtime.allowlist_path = allowlist_path
                if require_signed_metadata is not None:
                    runtime.require_signed_metadata = require_signed_metadata
                if normalized_hash_algorithm is not None:
                    runtime.hash_algorithm = normalized_hash_algorithm

            if transport_state is not None:
                if sync_mode is not None:
                    transport_state["sync_mode"] = sync_mode
                if source_peers is not None:
                    transport_state["source_peers"] = list(source_peers)
                if auth_scope is not None:
                    transport_state["auth_scope"] = auth_scope
                if allowlist_path is not None:
                    transport_state["allowlist_path"] = allowlist_path
                if require_signed_metadata is not None:
                    transport_state["require_signed_metadata"] = require_signed_metadata
                if normalized_hash_algorithm is not None:
                    transport_state["hash_algorithm"] = normalized_hash_algorithm

        if sync_mode is not None or source_peers is not None:
            for runtime in runtimes:
                runtime.folder.set_sync_mode(runtime.sync_mode, runtime.source_peers)

        effective_sync_mode = runtimes[0].folder.sync_manager.get_sync_mode()
        downgrade_reason = runtimes[0].folder.sync_manager.last_error
        async with self._xet_folders_lock:
            updated_transport_state = self._xet_transport_registry.get(workspace_id_hex)
            if updated_transport_state is not None:
                updated_transport_state["sync_mode"] = effective_sync_mode
                updated_transport_state["downgrade_reason"] = downgrade_reason
            policy_snapshot = (
                dict(updated_transport_state)
                if isinstance(updated_transport_state, dict)
                else {}
            )

        return {
            "workspace_id": workspace_id_hex,
            "sync_mode": effective_sync_mode,
            "downgrade_reason": downgrade_reason,
            "updated_folders": len(runtimes),
            "policy": policy_snapshot,
        }

    async def pause_torrent(self, info_hash_hex: str) -> bool:
        """Pause a torrent by info hash.

        Args:
            info_hash_hex: Info hash as hex string

        Returns:
            True if paused successfully, False if torrent not found or invalid hash

        """
        try:
            if len(info_hash_hex) != 40:
                return False
            info_hash = bytes.fromhex(info_hash_hex)
        except (ValueError, TypeError):
            return False

        async with self.lock:
            if info_hash not in self.torrents:
                return False
            session = self.torrents[info_hash]

        try:
            await session.pause()
            return True
        except Exception:
            self.logger.exception("Error pausing torrent %s", info_hash_hex)
            return False

    async def resume_torrent(self, info_hash_hex: str) -> bool:
        """Resume a torrent by info hash.

        Args:
            info_hash_hex: Info hash as hex string

        Returns:
            True if resumed successfully, False if torrent not found or invalid hash

        """
        try:
            if len(info_hash_hex) != 40:
                return False
            info_hash = bytes.fromhex(info_hash_hex)
        except (ValueError, TypeError):
            return False

        async with self.lock:
            if info_hash not in self.torrents:
                return False
            session = self.torrents[info_hash]

        try:
            await session.resume()
            return True
        except Exception:
            self.logger.exception("Error resuming torrent %s", info_hash_hex)
            return False

    def get_rate_history(self) -> deque[dict[str, float]]:
        """Get rate history deque.

        Returns:
            Rate history deque. Returns empty deque if not initialized.

        """
        if not hasattr(self, "_rate_history"):
            from collections import deque

            self._rate_history = deque(maxlen=600)
        return self._rate_history

    async def get_rate_samples(self, seconds: int = 120) -> list[dict[str, float]]:
        """Get recent upload/download rate samples.

        Args:
            seconds: Lookback window in seconds.

        Returns:
            List of samples with timestamp/download_rate/upload_rate.
        """
        now = time.time()
        window = max(1, int(seconds))
        cutoff = now - float(window)
        return [
            {
                "timestamp": float(sample.get("timestamp", 0.0)),
                "download_rate": float(sample.get("download_rate", 0.0)),
                "upload_rate": float(sample.get("upload_rate", 0.0)),
            }
            for sample in self.get_rate_history()
            if float(sample.get("timestamp", 0.0)) >= cutoff
        ]

    def get_disk_io_metrics(self) -> dict[str, Any]:
        """Get disk I/O metrics for IPC monitoring endpoints."""
        manager = self.disk_io_manager
        if manager is not None:
            for attr in ("get_metrics", "get_disk_io_metrics", "get_stats"):
                method = getattr(manager, attr, None)
                if callable(method):
                    with contextlib.suppress(Exception):
                        data = method()
                        if isinstance(data, dict):
                            return data
        return {
            "read_bytes_per_sec": 0.0,
            "write_bytes_per_sec": 0.0,
            "queue_depth": 0,
            "read_ops_per_sec": 0.0,
            "write_ops_per_sec": 0.0,
        }

    async def get_network_timing_metrics(self) -> dict[str, Any]:
        """Get network timing metrics for IPC monitoring endpoints."""
        metrics_collector = get_metrics_collector()
        if metrics_collector is not None:
            with contextlib.suppress(Exception):
                perf = metrics_collector.get_performance_metrics()
                return {
                    "rtt_ms": float(perf.get("network_rtt_ms", 0.0)),
                    "rtt_min_ms": float(perf.get("network_rtt_min_ms", 0.0)),
                    "rtt_max_ms": float(perf.get("network_rtt_max_ms", 0.0)),
                    "rtt_avg_ms": float(perf.get("network_rtt_avg_ms", 0.0)),
                    "bandwidth_bps": float(perf.get("network_bandwidth_bps", 0.0)),
                    "bandwidth_mbps": float(perf.get("network_bandwidth_mbps", 0.0)),
                    "bytes_sent": int(perf.get("network_bytes_sent", 0)),
                    "bytes_received": int(perf.get("network_bytes_received", 0)),
                    "total_connections": int(perf.get("network_total_connections", 0)),
                    "active_connections": int(
                        perf.get("network_active_connections", 0)
                    ),
                    "failed_connections": int(
                        perf.get("network_failed_connections", 0)
                    ),
                    "bdp_bytes": int(perf.get("network_bdp_bytes", 0)),
                }
        return {
            "rtt_ms": 0.0,
            "rtt_min_ms": 0.0,
            "rtt_max_ms": 0.0,
            "rtt_avg_ms": 0.0,
            "bandwidth_bps": 0.0,
            "bandwidth_mbps": 0.0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "total_connections": 0,
            "active_connections": 0,
            "failed_connections": 0,
            "bdp_bytes": 0,
        }

    async def get_global_peer_metrics(self) -> dict[str, Any]:
        """Get aggregated global peer metrics across all torrents."""
        metrics_collector = get_metrics_collector()
        if metrics_collector is not None:
            with contextlib.suppress(Exception):
                return metrics_collector.get_global_peer_metrics()
        return {
            "total_peers": 0,
            "active_peers": 0,
            "peers": [],
            "average_download_rate": 0.0,
            "average_upload_rate": 0.0,
            "total_bytes_downloaded": 0,
            "total_bytes_uploaded": 0,
        }

    @property
    def metrics_heartbeat_counter(self) -> int:
        """Get metrics heartbeat counter.

        Returns:
            Current heartbeat counter value.

        """
        return getattr(self, "_metrics_heartbeat_counter", 0)

    @metrics_heartbeat_counter.setter
    def metrics_heartbeat_counter(self, value: int) -> None:
        """Set metrics heartbeat counter.

        Args:
            value: Counter value to set.

        """
        self._metrics_heartbeat_counter = value

    @property
    def metrics_heartbeat_interval(self) -> int:
        """Get metrics heartbeat interval.

        Returns:
            Heartbeat interval value.

        """
        return getattr(self, "_metrics_heartbeat_interval", 5)

    @metrics_heartbeat_interval.setter
    def metrics_heartbeat_interval(self, value: int) -> None:
        """Set metrics heartbeat interval.

        Args:
            value: Interval value to set.

        """
        self._metrics_heartbeat_interval = value

    @property
    def last_metrics_emit(self) -> float:
        """Get last metrics emit timestamp.

        Returns:
            Last metrics emit timestamp.

        """
        return getattr(self, "_last_metrics_emit", 0.0)

    @last_metrics_emit.setter
    def last_metrics_emit(self, value: float) -> None:
        """Set last metrics emit timestamp.

        Args:
            value: Timestamp value to set.

        """
        self._last_metrics_emit = value

    @property
    def metrics_emit_interval(self) -> float:
        """Get metrics emit interval.

        Returns:
            Metrics emit interval value.

        """
        return getattr(self, "_metrics_emit_interval", 10.0)

    @metrics_emit_interval.setter
    def metrics_emit_interval(self, value: float) -> None:
        """Set metrics emit interval.

        Args:
            value: Interval value to set.

        """
        self._metrics_emit_interval = value

    @property
    def metrics_sample_interval(self) -> float:
        """Get metrics sample interval.

        Returns:
            Metrics sample interval value.

        """
        return getattr(self, "_metrics_sample_interval", 1.0)

    @metrics_sample_interval.setter
    def metrics_sample_interval(self, value: float) -> None:
        """Set metrics sample interval.

        Args:
            value: Interval value to set.

        """
        self._metrics_sample_interval = value

    def get_webtorrent_protocols(self) -> list[Any]:
        """Get WebTorrent protocol instances.

        Returns:
            List of WebTorrent protocol instances. Returns empty list if not initialized.

        """
        if not hasattr(self, "_webtorrent_protocols"):
            return []
        return list(getattr(self, "_webtorrent_protocols", []))

    def add_webtorrent_protocol(self, protocol: Any) -> None:
        """Add WebTorrent protocol instance.

        Args:
            protocol: WebTorrent protocol instance to add.

        """
        if not hasattr(self, "_webtorrent_protocols"):
            self._webtorrent_protocols: list[Any] = []
        if protocol not in self._webtorrent_protocols:
            self._webtorrent_protocols.append(protocol)

    def remove_webtorrent_protocol(self, protocol: Any) -> None:
        """Remove WebTorrent protocol instance.

        Args:
            protocol: WebTorrent protocol instance to remove.

        """
        if hasattr(self, "_webtorrent_protocols"):
            with contextlib.suppress(ValueError):
                self._webtorrent_protocols.remove(protocol)

    def get_session_metrics(self) -> Optional[Metrics]:
        """Get session metrics collector.

        Returns:
            Metrics collector instance for accessing session metrics, or None if not initialized.

        """
        return self.metrics

    async def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all torrents.

        Returns:
            Dictionary with aggregated stats including:
            - num_torrents: Total number of torrents
            - num_active: Number of active (downloading) torrents
            - num_paused: Number of paused torrents
            - num_seeding: Number of seeding torrents
            - download_rate: Total download rate across all torrents
            - upload_rate: Total upload rate across all torrents
            - average_progress: Average progress across all torrents
            - total_downloaded: Total bytes downloaded
            - total_uploaded: Total bytes uploaded

        """
        async with self.lock:
            num_torrents = len(self.torrents)
            num_active = 0
            num_paused = 0
            num_seeding = 0
            total_download_rate = 0.0
            total_upload_rate = 0.0
            total_progress = 0.0
            total_downloaded = 0
            total_uploaded = 0
            total_left = 0
            connected_peers = 0

            for torrent in self.torrents.values():
                info_obj = getattr(torrent, "info", None)
                status = getattr(info_obj, "status", None)
                status_payload: Optional[dict[str, Any]] = None
                if status is None:
                    cached_status = getattr(torrent, "_cached_status", None)
                    if isinstance(cached_status, dict):
                        status = cached_status.get("status", "unknown")
                        status_payload = cached_status
                    else:
                        get_status_fn = getattr(torrent, "get_status", None)
                        if callable(get_status_fn):
                            try:
                                maybe_status = get_status_fn()
                                if asyncio.iscoroutine(maybe_status):
                                    maybe_status = await maybe_status
                                if isinstance(maybe_status, dict):
                                    status = maybe_status.get("status", "unknown")
                                    status_payload = maybe_status
                                else:
                                    status = "unknown"
                            except Exception:
                                status = "unknown"
                        else:
                            status = "unknown"
                if status == "paused":
                    num_paused += 1
                elif status == "seeding":
                    num_seeding += 1
                elif status in ("downloading", "starting"):
                    num_active += 1

                total_download_rate += float(
                    getattr(torrent, "download_rate", 0.0) or 0.0
                )
                total_upload_rate += float(getattr(torrent, "upload_rate", 0.0) or 0.0)
                cached_status = status_payload
                if cached_status is None:
                    cached_status = getattr(torrent, "_cached_status", None)
                if not isinstance(cached_status, dict):
                    get_status_fn = getattr(torrent, "get_status", None)
                    if callable(get_status_fn):
                        try:
                            maybe_status = get_status_fn()
                            if asyncio.iscoroutine(maybe_status):
                                maybe_status = await maybe_status
                            if isinstance(maybe_status, dict):
                                cached_status = maybe_status
                        except Exception:
                            cached_status = None
                progress = (
                    cached_status.get("progress", 0.0)
                    if isinstance(cached_status, dict)
                    else 0.0
                )
                total_progress += progress
                total_downloaded += int(getattr(torrent, "downloaded_bytes", 0) or 0)
                total_uploaded += int(getattr(torrent, "uploaded_bytes", 0) or 0)
                total_left += int(getattr(torrent, "left_bytes", 0) or 0)
                if isinstance(cached_status, dict):
                    cached_peer_count = cached_status.get("connected_peers", None)
                else:
                    cached_peer_count = None
                if cached_peer_count is None:
                    peer_state = getattr(torrent, "peers", None)
                    if isinstance(peer_state, dict):
                        cached_peer_count = peer_state.get("count", 0)
                    else:
                        cached_peer_count = len(peer_state) if peer_state else 0
                if isinstance(cached_peer_count, (int, float)):
                    connected_peers += int(cached_peer_count)

            average_progress = (
                total_progress / num_torrents if num_torrents > 0 else 0.0
            )

            return {
                "num_torrents": num_torrents,
                "num_active": num_active,
                "num_paused": num_paused,
                "num_seeding": num_seeding,
                "download_rate": total_download_rate,
                "upload_rate": total_upload_rate,
                "average_progress": average_progress,
                "total_downloaded": total_downloaded,
                "total_uploaded": total_uploaded,
                "total_left": total_left,
                "connected_peers": connected_peers,
            }

    async def get_status(self) -> dict[str, Any]:
        """Get status for all torrents.

        Returns:
            Dictionary mapping info_hash (hex) to status dict for each torrent

        """
        async with self.lock:
            sessions = list(self.torrents.items())
        status_dict: dict[str, Any] = {}
        for info_hash, session in sessions:
            try:
                status = await session.get_status()
                status_dict[info_hash.hex()] = status
            except Exception as e:
                self.logger.exception(
                    "Error getting status for torrent %s", info_hash.hex()
                )
                status_dict[info_hash.hex()] = {
                    "error": str(e),
                    "status": "error",
                }
        return status_dict

    async def get_torrent_status(self, info_hash_hex: str) -> Optional[dict[str, Any]]:
        """Get status for a specific torrent.

        Args:
            info_hash_hex: Info hash as hex string

        Returns:
            Status dictionary or None if torrent not found

        """
        try:
            if len(info_hash_hex) != 40:
                return None
            info_hash = bytes.fromhex(info_hash_hex)
        except (ValueError, TypeError):
            return None

        async with self.lock:
            session = self.torrents.get(info_hash)
            if not session:
                return None

        try:
            return await session.get_status()
        except Exception as e:
            self.logger.exception("Error getting status for torrent %s", info_hash_hex)
            return {"error": str(e), "status": "error"}

    async def get_session_for_info_hash(
        self, info_hash: bytes
    ) -> Optional[AsyncTorrentSession]:
        """Return the torrent session for the given info hash, or None.

        Used by the TCP server (and other inbound connection handlers) to resolve
        an incoming peer connection to the correct session. Safe to call from
        any task; uses the manager lock for consistency.

        Args:
            info_hash: 20-byte info hash (v1) or 32-byte (v2) as bytes.

        Returns:
            The AsyncTorrentSession for that torrent, or None if not found.
        """
        async with self.lock:
            return self.torrents.get(info_hash)

    async def rehash_torrent(self, info_hash: str) -> bool:
        """Rehash all pieces for a torrent.

        Args:
            info_hash: Torrent info hash as hex string

        Returns:
            True if rehash succeeded, False otherwise (invalid hash, torrent not found,
            missing piece_manager, or verification failed)

        """
        # Validate and convert hex string to bytes
        try:
            if len(info_hash) != 40:
                return False
            info_hash_bytes = bytes.fromhex(info_hash)
        except (ValueError, TypeError):
            return False

        # Find torrent session
        async with self.lock:
            session = self.torrents.get(info_hash_bytes)
            if not session:
                return False

            # Get piece_manager
            piece_manager = getattr(session, "piece_manager", None)
            if piece_manager is None:
                return False

        # Check if verify_all_pieces method exists
        verify_method = getattr(piece_manager, "verify_all_pieces", None)
        if verify_method is None:
            return False

        # Call verify_all_pieces (handle both async and sync)
        try:
            if asyncio.iscoroutinefunction(verify_method):
                result = await verify_method()
            else:
                result = verify_method()
            # Return True if verification succeeded (result is truthy)
            return bool(result)
        except Exception:
            self.logger.exception("Error rehashing torrent %s", info_hash)
            return False

    async def refresh_pex(self, info_hash_hex: str) -> bool:
        """Refresh PEX (Peer Exchange) for a torrent.

        Args:
            info_hash_hex: Info hash in hex format

        Returns:
            True if PEX refresh was triggered, False if torrent not found or PEX not available

        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            self.logger.debug("Invalid info_hash format: %s", info_hash_hex)
            return False

        async with self.lock:
            session = self.torrents.get(info_hash)
            if not session:
                self.logger.debug("Torrent not found: %s", info_hash_hex)
                return False

            # Check if session has PEX manager
            pex_manager = getattr(session, "pex_manager", None)
            if not pex_manager:
                self.logger.debug(
                    "PEX manager not available for torrent: %s", info_hash_hex
                )
                return False

        # Trigger PEX refresh
        try:
            if hasattr(pex_manager, "refresh"):
                if asyncio.iscoroutinefunction(pex_manager.refresh):
                    await pex_manager.refresh()
                else:
                    pex_manager.refresh()
                return True
            self.logger.debug("PEX manager has no refresh method: %s", info_hash_hex)
            return False
        except Exception:
            self.logger.exception("Failed to refresh PEX for torrent %s", info_hash_hex)
            return False

    async def checkpoint_backup_torrent(
        self, info_hash_hex: str, destination: Union[Path, str]
    ) -> bool:
        """Backup checkpoint for a torrent.

        Args:
            info_hash_hex: Info hash in hex format
            destination: Path where checkpoint backup should be saved

        Returns:
            True if backup succeeded, False if torrent not found or backup failed

        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            self.logger.debug("Invalid info_hash format: %s", info_hash_hex)
            return False

        async with self.lock:
            session = self.torrents.get(info_hash)
            if not session:
                self.logger.debug("Torrent not found: %s", info_hash_hex)
                return False

            # Check if session has checkpoint manager
            checkpoint_manager = getattr(session, "checkpoint_manager", None)
            if not checkpoint_manager:
                self.logger.debug(
                    "Checkpoint manager not available for torrent: %s", info_hash_hex
                )
                return False

        # Trigger checkpoint backup
        try:
            dest_path = Path(destination)
            if hasattr(checkpoint_manager, "backup_checkpoint"):
                if asyncio.iscoroutinefunction(checkpoint_manager.backup_checkpoint):
                    await checkpoint_manager.backup_checkpoint(info_hash, dest_path)
                else:
                    checkpoint_manager.backup_checkpoint(info_hash, dest_path)
                return True
            self.logger.debug(
                "Checkpoint manager has no backup_checkpoint method: %s", info_hash_hex
            )
            return False
        except Exception:
            self.logger.exception(
                "Failed to backup checkpoint for torrent %s", info_hash_hex
            )
            return False

    def _aggregate_torrent_stats(self) -> dict[str, Any]:
        """Aggregate statistics from all torrents.

        Delegates to ManagerBackgroundTasks._aggregate_torrent_stats() for
        API compatibility with integration tests.

        Returns:
            Dictionary with aggregated statistics including:
            - total_torrents: Total number of torrents
            - total_downloaded: Total bytes downloaded
            - total_uploaded: Total bytes uploaded
            - total_left: Total bytes remaining
            - total_peers: Total number of peers
            - total_download_rate: Total download rate
            - total_upload_rate: Total upload rate
            - timestamp: Current timestamp

        """
        return self.background_tasks._aggregate_torrent_stats()

    async def validate_checkpoint(self, checkpoint: TorrentCheckpoint) -> bool:
        """Validate checkpoint integrity via checkpoint operations delegate."""
        return await self.checkpoint_ops.validate(checkpoint)

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: TorrentCheckpoint,
        torrent_path: Optional[str] = None,
    ) -> str:
        """Resume torrent from checkpoint via checkpoint operations delegate."""
        return await self.checkpoint_ops.resume_from_checkpoint(
            info_hash, checkpoint, torrent_path
        )

    async def find_checkpoint_by_name(self, name: str) -> Optional[TorrentCheckpoint]:
        """Find checkpoint by torrent name with robust load-error handling."""
        checkpoint_manager = getattr(self, "checkpoint_manager", None)
        if checkpoint_manager is None:
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
        return None

    async def _cleanup_loop(self) -> None:
        """Compatibility alias for manager cleanup loop."""
        await self.background_tasks.cleanup_loop()

    async def _metrics_loop(self) -> None:
        """Compatibility alias for manager metrics loop."""
        await self.background_tasks.metrics_loop()

    async def _emit_global_metrics(self, stats: dict[str, Any]) -> None:
        """Compatibility alias for metrics emission hook."""
        await self.background_tasks._emit_global_metrics(stats)

    def status(self) -> dict[str, Any]:
        """Synchronous status wrapper for backwards compatibility."""
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop and running_loop.is_running():
            # Avoid nested event-loop execution in the same thread.
            return {}

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.get_status())
        finally:
            asyncio.set_event_loop(None)
            loop.close()


# Alias for backward compatibility
SessionManager = AsyncSessionManager
