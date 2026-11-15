"""XET folder synchronization manager with multiple sync modes.

This module manages different synchronization modes for XET folders:
- Designated Source: Single/multiple designated peers as source of truth
- Best Effort Queued: All nodes attempt updates, queued by priority
- Broadcast Queued: One/more nodes broadcast updates with queuing
- Consensus: Consensus-based update validation (majority vote)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from ccbt.models import PeerInfo, XetFileMetadata, XetSyncStatus

logger = logging.getLogger(__name__)


class SyncMode(Enum):
    """Synchronization modes."""

    DESIGNATED = "designated"
    BEST_EFFORT = "best_effort"
    BROADCAST = "broadcast"
    CONSENSUS = "consensus"


@dataclass
class UpdateEntry:
    """Entry in the update queue."""

    file_path: str
    chunk_hash: bytes
    git_ref: Optional[str]
    timestamp: float
    priority: int = 0  # Higher priority = processed first
    source_peer: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    file_metadata: Optional[XetFileMetadata] = None
    deleted: bool = False


@dataclass
class PeerSyncState:
    """Synchronization state for a peer."""

    peer_id: str
    peer_info: PeerInfo
    last_sync_time: Optional[float] = None
    current_git_ref: Optional[str] = None
    chunk_hashes: set[bytes] = field(default_factory=set)
    is_source: bool = False  # For designated mode
    sync_progress: float = 0.0
    last_contact: float = field(default_factory=time.time)
    source_term: int = 0  # Designated election term announced by peer


@dataclass
class SourceAnnouncement:
    """Designated-source election announcement (WS8)."""

    peer_id: str
    term: int
    announced_at: float = field(default_factory=time.time)


@dataclass
class Tombstone:
    """Delete tombstone with version vector (WS8)."""

    file_path: str
    version_vector: dict[str, int]
    deleted_at: float
    peer_id: str
    file_hash: Optional[bytes] = None


class XetSyncManager:
    """Manager for XET folder synchronization with multiple modes."""

    def __init__(
        self,
        session_manager: Optional[Any] = None,
        folder_path: Optional[str] = None,
        sync_mode: str = "best_effort",
        source_peers: Optional[list[str]] = None,
        consensus_threshold: float = 0.5,
        max_queue_size: int = 100,
        check_interval: float = 5.0,
    ) -> None:
        """Initialize sync manager.

        Args:
            session_manager: Session manager instance (optional)
            folder_path: Path to synced folder (optional, can be set later)
            sync_mode: Synchronization mode
            source_peers: List of designated source peer IDs (for designated mode)
            consensus_threshold: Majority threshold for consensus (0.0 to 1.0)
            max_queue_size: Maximum update queue size
            check_interval: Check interval in seconds

        """
        self.session_manager = session_manager
        self.folder_path = folder_path
        self.sync_mode = SyncMode(sync_mode)
        self.source_peers = set(source_peers or [])
        self.consensus_threshold = consensus_threshold
        self.max_queue_size = max_queue_size
        self.check_interval = check_interval

        # Consensus components
        self.raft_node: Optional[Any] = None  # RaftNode
        self.byzantine_consensus: Optional[Any] = None  # ByzantineConsensus
        self.conflict_resolver: Optional[Any] = None  # ConflictResolver

        # Source peer election (announcement / term / failover)
        self.source_election_interval = 300.0  # 5 minutes
        self.source_failover_timeout = 60.0  # source silent → elect new
        self._source_election_task: Optional[asyncio.Task] = None
        self.source_term: int = 0
        self.local_peer_id: Optional[str] = None
        self._source_announcements: dict[str, SourceAnnouncement] = {}

        # Update queue
        self.update_queue: deque[UpdateEntry] = deque(maxlen=max_queue_size)
        self.queue_lock = asyncio.Lock()

        # Peer states
        self.peer_states: dict[str, PeerSyncState] = {}
        self.file_metadata_by_path: dict[str, XetFileMetadata] = {}
        self.tombstones: dict[str, Tombstone] = {}
        self.version_vectors: dict[str, dict[str, int]] = {}

        # Consensus tracking
        self.consensus_votes: dict[
            bytes, dict[str, bool]
        ] = {}  # chunk_hash -> {peer_id: vote}

        # State persistence paths
        self._state_dir: Optional[Path] = None
        if folder_path:
            self._state_dir = Path(folder_path) / ".xet"
            self._state_dir.mkdir(parents=True, exist_ok=True)

        # Load persisted state
        self._load_consensus_state()

        # Statistics
        self.stats = {
            "updates_processed": 0,
            "updates_failed": 0,
            "consensus_reached": 0,
            "consensus_failed": 0,
        }

        # Allowlist and git tracking
        self.allowlist_hash: Optional[bytes] = None
        self.current_git_ref: Optional[str] = None
        self.last_error: Optional[str] = None
        self._running = False

        self.logger = logging.getLogger(__name__)

    def _has_healthy_propagation_backend(self) -> bool:
        """Return True when at least one propagation backend is healthy."""
        if self.session_manager is None:
            return False
        getter = getattr(self.session_manager, "get_xet_discovery_status", None)
        if not callable(getter):
            return False
        try:
            status = getter()
        except Exception:
            return False
        if not isinstance(status, dict):
            return False
        for backend in ("lpd", "multicast", "gossip", "flooding"):
            backend_state = status.get(backend)
            if isinstance(backend_state, dict) and backend_state.get("health"):
                return True
        return False

    def _has_verified_designated_source(self) -> bool:
        """Return True if at least one designated source is XET-authorized."""
        if self.session_manager is None or not self.source_peers:
            return False
        torrents = getattr(self.session_manager, "torrents", {})
        if not isinstance(torrents, dict):
            return False
        for session in torrents.values():
            peer_manager = getattr(
                getattr(session, "download_manager", None), "peer_manager", None
            )
            if peer_manager is None or not hasattr(
                peer_manager, "is_peer_xet_authorized"
            ):
                continue
            for peer_id in self.source_peers:
                with contextlib.suppress(Exception):
                    if peer_manager.is_peer_xet_authorized(peer_id, None):
                        return True
        return False

    async def start(self) -> None:
        """Start the sync manager."""
        if self._running:
            return

        if self.sync_mode == SyncMode.CONSENSUS:
            self.logger.warning(
                "Consensus mode is not transport-backed yet; downgrading to best_effort"
            )
            self.sync_mode = SyncMode.BEST_EFFORT
            self.set_last_error(
                "Consensus mode is disabled until transport-backed RPCs exist"
            )
        elif self.sync_mode == SyncMode.BROADCAST:
            if not self._has_healthy_propagation_backend():
                self.logger.warning(
                    "Broadcast mode has no healthy propagation backend; downgrading to best_effort"
                )
                self.sync_mode = SyncMode.BEST_EFFORT
                self.set_last_error(
                    "Broadcast mode requires at least one healthy propagation backend"
                )
        elif self.sync_mode == SyncMode.DESIGNATED and not self.source_peers:
            self.logger.warning(
                "Designated mode requires source peers; downgrading to best_effort"
            )
            self.sync_mode = SyncMode.BEST_EFFORT
            self.set_last_error(
                "Designated mode requires at least one configured source peer"
            )
        elif self.sync_mode == SyncMode.DESIGNATED:
            if not self._has_verified_designated_source():
                self.logger.warning(
                    "Designated mode source peers are not XET-authorized; downgrading to best_effort"
                )
                self.sync_mode = SyncMode.BEST_EFFORT
                self.set_last_error(
                    "Designated mode requires at least one verified source peer"
                )

        self._running = True

        # Initialize consensus components if in consensus mode
        if self.sync_mode == SyncMode.CONSENSUS:
            await self._initialize_consensus()

        # Start source peer election task if in designated mode
        if self.sync_mode == SyncMode.DESIGNATED:
            self._source_election_task = asyncio.create_task(
                self._source_election_loop()
            )

        self.logger.info("XET sync manager started")

    async def stop(self) -> None:
        """Stop the sync manager."""
        if not self._running:
            return

        self._running = False

        # Stop source election task
        if self._source_election_task:
            self._source_election_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._source_election_task
            self._source_election_task = None

        # Stop consensus components
        if self.raft_node:
            await self.raft_node.stop()
            self.raft_node = None

        if self.byzantine_consensus:
            # Byzantine consensus doesn't have async stop, just clear
            self.byzantine_consensus = None

        # Save consensus state before stopping
        self._save_consensus_state()

        await self.clear_queue()
        self.logger.info("XET sync manager stopped")

    def get_allowlist_hash(self) -> Optional[bytes]:
        """Get allowlist hash.

        Returns:
            Allowlist hash or None

        """
        return self.allowlist_hash

    def set_allowlist_hash(self, allowlist_hash: Optional[bytes]) -> None:
        """Set allowlist hash.

        Args:
            allowlist_hash: Allowlist hash to set

        """
        self.allowlist_hash = allowlist_hash

    def get_sync_mode(self) -> str:
        """Get current sync mode.

        Returns:
            Sync mode string

        """
        return self.sync_mode.value

    def get_current_git_ref(self) -> Optional[str]:
        """Get current git reference.

        Returns:
            Git commit hash/ref or None

        """
        return self.current_git_ref

    def set_current_git_ref(self, git_ref: Optional[str]) -> None:
        """Set current git reference.

        Args:
            git_ref: Git commit hash/ref to set

        """
        self.current_git_ref = git_ref

    def set_last_error(self, error: Optional[str]) -> None:
        """Record the most recent sync/runtime error for status surfaces."""
        self.last_error = error

    async def add_peer(self, peer_info: PeerInfo, is_source: bool = False) -> None:
        """Add peer to sync manager.

        Args:
            peer_info: Peer information
            is_source: Whether peer is a designated source (for designated mode)

        """
        peer_id = peer_info.peer_id.hex() if peer_info.peer_id else str(peer_info)

        peer_state = PeerSyncState(
            peer_id=peer_id,
            peer_info=peer_info,
            is_source=is_source,
        )

        self.peer_states[peer_id] = peer_state

        # If designated mode and this is a source peer, add to source set
        if self.sync_mode == SyncMode.DESIGNATED and is_source:
            self.source_peers.add(peer_id)

        self.logger.info(
            "Added peer %s to sync manager (mode=%s, is_source=%s)",
            peer_id,
            self.sync_mode.value,
            is_source,
        )

    async def remove_peer(self, peer_id: str) -> None:
        """Remove peer from sync manager.

        Args:
            peer_id: Peer identifier

        """
        if peer_id in self.peer_states:
            del self.peer_states[peer_id]
            self.source_peers.discard(peer_id)
            self.logger.info("Removed peer %s from sync manager", peer_id)

    async def register_discovered_peer(
        self,
        peer_info: PeerInfo,
        *,
        chunk_hash: Optional[bytes] = None,
        git_ref: Optional[str] = None,
    ) -> None:
        """Record a peer discovered during workspace or chunk lookup.

        This keeps best-effort runtime state aligned with discovery results so the
        status model reflects actual remote availability even before a file transfer
        occurs.
        """
        peer_id = peer_info.peer_id.hex() if peer_info.peer_id else str(peer_info)
        peer_state = self.peer_states.get(peer_id)
        if peer_state is None:
            peer_state = PeerSyncState(peer_id=peer_id, peer_info=peer_info)
            self.peer_states[peer_id] = peer_state
        else:
            peer_state.peer_info = peer_info
        peer_state.last_contact = time.time()
        if git_ref is not None:
            peer_state.current_git_ref = git_ref
        if chunk_hash is not None:
            peer_state.chunk_hashes.add(chunk_hash)

    async def get_pending_updates_snapshot(self) -> list[UpdateEntry]:
        """Return a stable snapshot of queued updates for discovery/inspection."""
        async with self.queue_lock:
            return list(self.update_queue)

    async def queue_update(
        self,
        file_path: str,
        chunk_hash: bytes,
        git_ref: Optional[str] = None,
        priority: int = 0,
        source_peer: Optional[str] = None,
        file_metadata: Optional[XetFileMetadata] = None,
        deleted: bool = False,
    ) -> bool:
        """Queue an update for synchronization.

        Args:
            file_path: Path to updated file
            chunk_hash: Hash of updated chunk
            git_ref: Git commit reference
            priority: Update priority (higher = processed first)
            source_peer: Peer that originated the update
            file_metadata: Optional file metadata snapshot for sync application
            deleted: Whether this update represents a deletion

        Returns:
            True if queued successfully, False if queue is full

        """
        async with self.queue_lock:
            # Keep only the most recent update per file path to avoid replaying stale
            # manifests behind fresher updates during bursty propagation.
            self.update_queue = deque(
                [entry for entry in self.update_queue if entry.file_path != file_path],
                maxlen=self.max_queue_size,
            )
            if len(self.update_queue) >= self.max_queue_size:
                self.logger.warning("Update queue is full, dropping update")
                return False

            entry = UpdateEntry(
                file_path=file_path,
                chunk_hash=chunk_hash,
                git_ref=git_ref,
                timestamp=time.time(),
                priority=priority,
                source_peer=source_peer,
                file_metadata=file_metadata,
                deleted=deleted,
            )

            if file_metadata is not None:
                self.file_metadata_by_path[file_path] = file_metadata
            elif deleted:
                self.file_metadata_by_path.pop(file_path, None)

            # Insert based on priority
            inserted = False
            for i, existing in enumerate(self.update_queue):
                if priority > existing.priority:
                    self.update_queue.insert(i, entry)
                    inserted = True
                    break

            if not inserted:
                self.update_queue.append(entry)

            self.logger.debug(
                "Queued update: %s (priority=%d, queue_size=%d)",
                file_path,
                priority,
                len(self.update_queue),
            )

            return True

    def get_file_metadata(self, file_path: str) -> Optional[XetFileMetadata]:
        """Return the latest known file manifest for a workspace path."""
        return self.file_metadata_by_path.get(file_path)

    async def process_updates(
        self,
        update_handler: Any,  # Callable that processes updates
    ) -> int:
        """Process queued updates based on sync mode.

        Args:
            update_handler: Handler function for processing updates

        Returns:
            Number of updates processed

        """
        if not self._running:
            return 0

        processed = 0

        try:
            async with self.queue_lock:
                if not self.update_queue:
                    return 0

                queue_len = len(self.update_queue)

                # Process based on sync mode with timeout
                if self.sync_mode == SyncMode.DESIGNATED:
                    processed = await asyncio.wait_for(
                        self._process_designated_updates(update_handler),
                        timeout=300.0,  # 5 minutes max
                    )
                elif self.sync_mode == SyncMode.BEST_EFFORT:
                    processed = await asyncio.wait_for(
                        self._process_best_effort_updates(update_handler),
                        timeout=300.0,
                    )
                elif self.sync_mode == SyncMode.BROADCAST:
                    processed = await asyncio.wait_for(
                        self._process_broadcast_updates(update_handler),
                        timeout=300.0,
                    )
                elif self.sync_mode == SyncMode.CONSENSUS:
                    processed = await asyncio.wait_for(
                        self._process_consensus_updates(update_handler),
                        timeout=600.0,  # 10 minutes for consensus (may take longer)
                    )
                else:
                    self.logger.warning("Unknown sync mode: %s", self.sync_mode)
                    return 0

            self.stats["updates_processed"] += processed
            if queue_len > 0 and processed == 0:
                self.logger.warning(
                    "process_updates had %d queued update(s) but processed 0 (handler may have raised)",
                    queue_len,
                )
            return processed

        except asyncio.TimeoutError:
            self.logger.exception(
                "Timeout processing updates in %s mode", self.sync_mode.value
            )
            return 0
        except Exception:
            self.logger.exception(
                "Error processing updates in %s mode", self.sync_mode.value
            )
            return 0

    async def _process_designated_updates(self, update_handler: Any) -> int:
        """Process updates in designated source mode.

        Only updates from designated source peers are processed.

        Args:
            update_handler: Handler function

        Returns:
            Number of updates processed

        """
        processed = 0
        to_remove: list[UpdateEntry] = []

        for entry in self.update_queue:
            # Only process if from designated source; reject non-source updates
            if entry.source_peer and entry.source_peer in self.source_peers:
                try:
                    if entry.deleted:
                        self.record_tombstone(
                            entry.file_path,
                            entry.source_peer,
                            file_hash=entry.chunk_hash or None,
                        )
                    await update_handler(entry)
                    to_remove.append(entry)
                    processed += 1
                except Exception:
                    self.logger.exception("Error processing update")
                    entry.retry_count += 1
                    if entry.retry_count >= entry.max_retries:
                        to_remove.append(entry)
                        self.stats["updates_failed"] += 1
            else:
                # Non-source update: drop (never apply)
                to_remove.append(entry)
                self.logger.debug(
                    "Rejected non-source update from %s for %s",
                    entry.source_peer,
                    entry.file_path,
                )
                continue

        # Remove processed entries
        for entry in to_remove:
            if entry in self.update_queue:
                self.update_queue.remove(entry)

        return processed

    async def _process_best_effort_updates(self, update_handler: Any) -> int:
        """Process updates in best-effort queued mode.

        All nodes attempt updates, processed by priority.
        Includes conflict detection and resolution.

        Args:
            update_handler: Handler function

        Returns:
            Number of updates processed

        """
        processed = 0
        to_remove: list[UpdateEntry] = []

        # Group updates by file path to detect conflicts
        updates_by_file: dict[str, list[UpdateEntry]] = {}
        for entry in self.update_queue:
            if entry.file_path not in updates_by_file:
                updates_by_file[entry.file_path] = []
            updates_by_file[entry.file_path].append(entry)

        # Process updates, resolving conflicts if needed
        for file_path, entries in updates_by_file.items():
            if len(entries) > 1 and self.conflict_resolver:
                # Multiple updates to same file - resolve conflict
                entries.sort(key=lambda e: e.priority, reverse=True)
                resolved_entry = entries[0]  # Start with highest priority

                for other_entry in entries[1:]:
                    # Detect conflict
                    conflict = self.conflict_resolver.detect_conflict(
                        file_path,
                        other_entry.source_peer or "unknown",
                        other_entry.timestamp,
                        resolved_entry.timestamp,
                    )

                    if conflict:
                        # Resolve conflict
                        our_version = {
                            "file_path": resolved_entry.file_path,
                            "chunk_hash": resolved_entry.chunk_hash.hex(),
                            "timestamp": resolved_entry.timestamp,
                            "peer_id": resolved_entry.source_peer,
                        }
                        their_version = {
                            "file_path": other_entry.file_path,
                            "chunk_hash": other_entry.chunk_hash.hex(),
                            "timestamp": other_entry.timestamp,
                            "peer_id": other_entry.source_peer,
                        }

                        resolved_version = self.conflict_resolver.resolve_conflict(
                            file_path, our_version, their_version
                        )

                        # Update resolved entry
                        if resolved_version == their_version:
                            resolved_entry = other_entry

                # Process resolved entry
                try:
                    await update_handler(resolved_entry)
                    to_remove.extend(entries)  # Remove all conflicting entries
                    processed += 1
                except Exception:
                    self.logger.exception("Error processing resolved update")
                    for entry in entries:
                        entry.retry_count += 1
                        if entry.retry_count >= entry.max_retries:
                            to_remove.append(entry)
            else:
                # Single update or no conflict resolver - process normally
                for entry in entries:
                    try:
                        await update_handler(entry)
                        to_remove.append(entry)
                        processed += 1
                    except Exception:
                        self.logger.exception("Error processing update")
                        entry.retry_count += 1
                        if entry.retry_count >= entry.max_retries:
                            to_remove.append(entry)
                            self.stats["updates_failed"] += 1

        # Remove processed entries
        for entry in to_remove:
            if entry in self.update_queue:
                self.update_queue.remove(entry)

        return processed

    async def _process_broadcast_updates(self, update_handler: Any) -> int:
        """Process updates in broadcast queued mode.

        Updates are broadcast to all peers with queuing.

        Args:
            update_handler: Handler function

        Returns:
            Number of updates processed

        """
        processed = 0
        to_remove: list[UpdateEntry] = []

        # Group updates by source peer
        updates_by_source: dict[Optional[str], list[UpdateEntry]] = {}
        for entry in self.update_queue:
            source = entry.source_peer
            if source not in updates_by_source:
                updates_by_source[source] = []
            updates_by_source[source].append(entry)

        # Process updates from each source
        for entries in updates_by_source.values():
            for entry in entries:
                try:
                    # Broadcast to all peers
                    await update_handler(entry)
                    to_remove.append(entry)
                    processed += 1
                except Exception:
                    self.logger.exception("Error broadcasting update")
                    entry.retry_count += 1
                    if entry.retry_count >= entry.max_retries:
                        to_remove.append(entry)
                        self.stats["updates_failed"] += 1

        # Remove processed entries
        for entry in to_remove:
            if entry in self.update_queue:
                self.update_queue.remove(entry)

        return processed

    async def _process_consensus_updates(self, update_handler: Any) -> int:
        """Process updates in consensus mode.

        Updates require majority vote before processing.

        Args:
            update_handler: Handler function

        Returns:
            Number of updates processed

        """
        # Use Raft if available, otherwise use simple consensus
        if self.raft_node:
            # Raft-based consensus
            return await self._process_raft_consensus(update_handler)

        # Use Byzantine consensus if available
        if self.byzantine_consensus:
            return await self._process_byzantine_consensus(update_handler)

        # Fallback to simple consensus
        processed = 0
        to_remove: list[UpdateEntry] = []

        for entry in list(self.update_queue):
            chunk_hash = entry.chunk_hash

            # Check if we have consensus for this chunk
            votes = self.consensus_votes.get(chunk_hash, {})
            total_peers = len(self.peer_states)
            if total_peers == 0:
                # No peers, process immediately
                try:
                    await update_handler(entry)
                    to_remove.append(entry)
                    processed += 1
                except Exception:
                    self.logger.exception("Error processing update")
                    entry.retry_count += 1
                    if entry.retry_count >= entry.max_retries:
                        to_remove.append(entry)
                        self.stats["updates_failed"] += 1
                continue

            # Count votes
            yes_votes = sum(1 for vote in votes.values() if vote)
            vote_ratio = yes_votes / total_peers if total_peers > 0 else 0.0

            if vote_ratio >= self.consensus_threshold:
                # Consensus reached
                try:
                    await update_handler(entry)
                    to_remove.append(entry)
                    processed += 1
                    self.stats["consensus_reached"] += 1
                except Exception:
                    self.logger.exception("Error processing update")
                    entry.retry_count += 1
                    if entry.retry_count >= entry.max_retries:
                        to_remove.append(entry)
                        self.stats["updates_failed"] += 1
            else:
                # No consensus yet, keep in queue
                self.stats["consensus_failed"] += 1

        # Remove processed entries
        for entry in to_remove:
            if entry in self.update_queue:
                self.update_queue.remove(entry)
                # Clean up consensus votes
                if entry.chunk_hash in self.consensus_votes:
                    del self.consensus_votes[entry.chunk_hash]

        return processed

    def announce_as_source(self, peer_id: str, term: Optional[int] = None) -> int:
        """Announce ``peer_id`` as designated source for ``term`` (monotonic)."""
        next_term = term if term is not None else self.source_term + 1
        if next_term < self.source_term:
            msg = f"source term {next_term} is stale (current {self.source_term})"
            raise ValueError(msg)
        self.source_term = next_term
        self._source_announcements[peer_id] = SourceAnnouncement(
            peer_id=peer_id, term=next_term
        )
        self.source_peers = {peer_id}
        for pid, state in self.peer_states.items():
            state.is_source = pid == peer_id
            if pid == peer_id:
                state.source_term = next_term
        self.logger.info("Source announcement: peer=%s term=%d", peer_id, next_term)
        return next_term

    def apply_source_announcement(self, peer_id: str, term: int) -> bool:
        """Accept a remote source announcement if ``term`` is newer."""
        if term < self.source_term:
            return False
        if term == self.source_term and peer_id not in self.source_peers:
            # Same term, different announcer → reject (split-brain)
            return False
        self.announce_as_source(peer_id, term=term)
        if peer_id in self.peer_states:
            self.peer_states[peer_id].last_contact = time.time()
        return True

    def record_tombstone(
        self,
        file_path: str,
        peer_id: str,
        version_vector: Optional[dict[str, int]] = None,
        file_hash: Optional[bytes] = None,
    ) -> Tombstone:
        """Record a delete as a tombstone (never silent drop)."""
        vv = dict(version_vector or self.version_vectors.get(file_path, {}))
        vv[peer_id] = vv.get(peer_id, 0) + 1
        self.version_vectors[file_path] = vv
        ts = Tombstone(
            file_path=file_path,
            version_vector=vv,
            deleted_at=time.time(),
            peer_id=peer_id,
            file_hash=file_hash,
        )
        self.tombstones[file_path] = ts
        self.file_metadata_by_path.pop(file_path, None)
        return ts

    def apply_rename(self, old_path: str, new_path: str, peer_id: str) -> None:
        """Rename = tombstone old path + add at new path metadata slot."""
        meta = self.file_metadata_by_path.get(old_path)
        self.record_tombstone(
            old_path,
            peer_id,
            file_hash=getattr(meta, "file_hash", None) if meta else None,
        )
        if meta is not None:
            # Preserve content identity under the new path until bytes arrive
            updated = meta.model_copy(update={"file_path": new_path})
            self.file_metadata_by_path[new_path] = updated

    def _source_needs_failover(self) -> bool:
        """True when no live designated source has contacted us recently."""
        if not self.source_peers:
            return True
        now = time.time()
        for pid in self.source_peers:
            state = self.peer_states.get(pid)
            if state is None:
                continue
            if now - state.last_contact <= self.source_failover_timeout:
                return False
        return True

    async def _elect_source_peer(self) -> Optional[str]:
        """Elect a source via failover when the current source times out.

        Uses announcement term protocol: winner is the peer with highest
        (term, peer_id) among healthy peers; local node may self-announce.
        """
        if not self._source_needs_failover() and self.source_peers:
            return next(iter(self.source_peers))

        candidates = [
            pid
            for pid, st in self.peer_states.items()
            if time.time() - st.last_contact <= self.source_failover_timeout
        ]
        if self.local_peer_id and self.local_peer_id not in candidates:
            candidates.append(self.local_peer_id)
        if not candidates:
            return None

        def _key(pid: str) -> tuple[int, str]:
            term = 0
            ann = self._source_announcements.get(pid)
            if ann is not None:
                term = ann.term
            state = self.peer_states.get(pid)
            if state is not None:
                term = max(term, state.source_term)
            return (term, pid)

        winner = max(candidates, key=_key)
        new_term = self.source_term + 1
        self.announce_as_source(winner, term=new_term)
        self.logger.info("Failover elected source peer: %s (term=%d)", winner, new_term)
        return winner

    async def _initialize_consensus(self) -> None:
        """Initialize consensus components (Raft or Byzantine).

        This method initializes either Raft or Byzantine consensus based on
        configuration and available peers.
        """
        from pathlib import Path

        try:
            # Determine node ID (use folder path hash or generate)
            if self.folder_path:
                import hashlib

                node_id = hashlib.sha256(str(self.folder_path).encode()).hexdigest()[
                    :16
                ]
            else:
                import uuid

                node_id = uuid.uuid4().hex[:16]

            # Try to initialize Raft first (preferred for strong consistency)
            try:
                from ccbt.consensus.raft import RaftNode

                # Determine state path
                if self.folder_path:
                    state_dir = Path(self.folder_path) / ".xet" / "raft"
                    state_dir.mkdir(parents=True, exist_ok=True)
                    state_path = state_dir / "raft_state.json"
                else:
                    state_path = None

                # Create Raft node
                self.raft_node = RaftNode(
                    node_id=node_id,
                    state_path=state_path,
                    election_timeout=2.0,
                    heartbeat_interval=0.5,
                    apply_command_callback=self._apply_raft_command,
                )

                # Add peers from peer_states
                for peer_id in self.peer_states:
                    self.raft_node.add_peer(peer_id)

                # Set up RPC handlers (simplified - would use network in production)
                self.raft_node.send_vote_request = self._send_raft_vote_request
                self.raft_node.send_append_entries = self._send_raft_append_entries

                # Start Raft node
                await self.raft_node.start()

                self.logger.info(
                    "Initialized Raft consensus (node_id=%s, peers=%d)",
                    node_id,
                    len(self.peer_states),
                )
                return

            except Exception as e:
                self.logger.warning("Failed to initialize Raft consensus: %s", e)

            # Fallback to Byzantine consensus (requires n >= 3f+1)
            try:
                from ccbt.consensus.byzantine import ByzantineConsensus

                fault_threshold = 0.33
                cluster_size = max(1, len(self.peer_states) + 1)
                max_faulty = int(cluster_size * fault_threshold)
                self.byzantine_consensus = ByzantineConsensus(
                    node_id=node_id,
                    fault_threshold=fault_threshold,
                    weighted_voting=False,
                    cluster_size=cluster_size,
                    max_faulty=max_faulty,
                )

                self.logger.info(
                    "Initialized Byzantine consensus (node_id=%s, n=%d, f=%d)",
                    node_id,
                    cluster_size,
                    max_faulty,
                )
                return

            except Exception as e:
                self.logger.warning("Failed to initialize Byzantine consensus: %s", e)

            # If both fail, log error but continue (will use simple consensus)
            self.logger.error(
                "Failed to initialize any consensus mechanism. "
                "Falling back to simple consensus."
            )

        except Exception:
            self.logger.exception("Error initializing consensus")

    def _apply_raft_command(self, command: dict[str, Any]) -> None:
        """Apply a committed Raft command.

        This callback is called when a Raft log entry is committed.

        Args:
            command: Command to apply

        """
        try:
            if command.get("type") == "update":
                # Find corresponding update entry
                chunk_hash_hex = command.get("chunk_hash")
                if chunk_hash_hex:
                    chunk_hash = bytes.fromhex(chunk_hash_hex)
                    file_path = command.get("file_path")

                    # Find entry in queue
                    for entry in list(self.update_queue):
                        if (
                            entry.chunk_hash == chunk_hash
                            and entry.file_path == file_path
                        ):
                            # Apply update using stored handler
                            update_handler = getattr(entry, "_update_handler", None)
                            if update_handler:
                                # Schedule async application - fire-and-forget
                                asyncio.create_task(  # noqa: RUF006
                                    self._apply_update_entry(entry, update_handler)
                                )
                            else:
                                self.logger.warning(
                                    "No update handler for Raft-committed update: %s",
                                    file_path,
                                )
                            break

        except Exception:
            self.logger.exception("Error applying Raft command")

    async def _apply_update_entry(
        self, entry: UpdateEntry, update_handler: Any
    ) -> None:
        """Apply an update entry using the provided handler.

        Args:
            entry: Update entry to apply
            update_handler: Handler function

        """
        try:
            await update_handler(entry)
            # Remove from queue after successful application
            async with self.queue_lock:
                if entry in self.update_queue:
                    self.update_queue.remove(entry)
            self.stats["updates_processed"] += 1
            self.stats["consensus_reached"] += 1
        except Exception:
            self.logger.exception("Error applying update entry")
            entry.retry_count += 1
            if entry.retry_count >= entry.max_retries:
                async with self.queue_lock:
                    if entry in self.update_queue:
                        self.update_queue.remove(entry)
                self.stats["updates_failed"] += 1

    async def _send_raft_rpc(
        self,
        peer_id: str,
        msg_type: int,
        request: dict[str, Any],
        response_type: int,
        timeout: float = 5.0,
    ) -> Optional[dict[str, Any]]:
        """Send a Raft RPC over XetTransport and wait for the matching response."""
        import asyncio

        from ccbt.extensions.xet import XetExtension

        transport = None
        if self.session_manager is not None:
            transport = getattr(self.session_manager, "xet_transport", None)
        if transport is None or getattr(transport, "_send", None) is None:
            self.logger.debug(
                "Raft RPC skipped: no XetTransport sender for %s", peer_id
            )
            return None
        ext = getattr(transport, "extension", None) or XetExtension()
        message = ext.encode_raft_message(msg_type, request)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()

        async def _on_response(pid: str, payload: bytes) -> Optional[bytes]:
            if pid != peer_id:
                return None
            try:
                rtype, body = ext.decode_raft_message(payload)
            except ValueError:
                return None
            if rtype != response_type:
                return None
            if not future.done():
                future.set_result(body)
            return None

        transport.set_raft_handler(response_type, _on_response)
        try:
            if not await transport.send(peer_id, message):
                return None
            return await asyncio.wait_for(future, timeout=timeout)
        except (asyncio.TimeoutError, Exception) as e:
            self.logger.debug("Raft RPC to %s failed: %s", peer_id, e)
            return None
        finally:
            transport.clear_raft_handler(response_type, _on_response)

    async def _send_raft_vote_request(
        self, peer_id: str, request: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Send Raft RequestVote over the XET extension wire."""
        from ccbt.extensions.xet import XetMessageType

        return await self._send_raft_rpc(
            peer_id,
            XetMessageType.RAFT_VOTE_REQUEST,
            request,
            XetMessageType.RAFT_VOTE_RESPONSE,
        )

    async def _send_raft_append_entries(
        self, peer_id: str, request: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Send Raft AppendEntries over the XET extension wire."""
        from ccbt.extensions.xet import XetMessageType

        return await self._send_raft_rpc(
            peer_id,
            XetMessageType.RAFT_APPEND_ENTRIES,
            request,
            XetMessageType.RAFT_APPEND_ENTRIES_RESPONSE,
        )

    async def _process_raft_consensus(self, update_handler: Any) -> int:
        """Process updates using Raft consensus.

        Args:
            update_handler: Handler function

        Returns:
            Number of updates processed

        """
        if not self.raft_node:
            return 0

        processed = 0
        to_remove: list[UpdateEntry] = []

        async with self.queue_lock:
            for entry in list(self.update_queue):
                try:
                    # Append to Raft log
                    command = {
                        "type": "update",
                        "file_path": entry.file_path,
                        "chunk_hash": entry.chunk_hash.hex(),
                        "git_ref": entry.git_ref,
                    }

                    success = await self.raft_node.append_entry(command)
                    if success:
                        # Entry will be applied when committed via _apply_raft_command
                        # Store update handler for later use
                        entry._update_handler = update_handler  # noqa: SLF001  # type: ignore[attr-defined]
                        # Don't remove yet - wait for commit
                        # Entry will be removed when committed and applied
                        processed += 1
                    else:
                        # Failed to append, retry
                        entry.retry_count += 1
                        if entry.retry_count >= entry.max_retries:
                            to_remove.append(entry)
                            self.stats["updates_failed"] += 1
                except Exception:
                    self.logger.exception("Error in Raft consensus")
                    entry.retry_count += 1
                    if entry.retry_count >= entry.max_retries:
                        to_remove.append(entry)
                        self.stats["updates_failed"] += 1

        # Remove failed entries
        for entry in to_remove:
            if entry in self.update_queue:
                self.update_queue.remove(entry)

        return processed

    async def _process_byzantine_consensus(self, update_handler: Any) -> int:
        """Process updates using Byzantine consensus.

        Args:
            update_handler: Handler function

        Returns:
            Number of updates processed

        """
        if not self.byzantine_consensus:
            return 0

        processed = 0
        to_remove: list[UpdateEntry] = []

        async with self.queue_lock:
            for entry in list(self.update_queue):
                try:
                    # Create proposal
                    proposal = {
                        "type": "update",
                        "file_path": entry.file_path,
                        "chunk_hash": entry.chunk_hash.hex(),
                        "git_ref": entry.git_ref,
                    }

                    proposal_data = self.byzantine_consensus.propose(proposal)

                    # Collect votes from consensus_votes dictionary
                    # This tracks votes received from peers via vote_on_update()
                    chunk_hash = entry.chunk_hash
                    votes: list[dict[str, Any]] = []

                    if chunk_hash in self.consensus_votes:
                        # Convert consensus_votes to format expected by aggregate_votes
                        for peer_id, vote_value in self.consensus_votes[
                            chunk_hash
                        ].items():
                            votes.append(
                                {
                                    "voter": peer_id,
                                    "vote": vote_value,
                                    "proposal": proposal_data,
                                }
                            )

                    # Add our own vote (we vote yes for our own proposals)
                    votes.append(
                        {
                            "voter": self.byzantine_consensus.node_id,
                            "vote": True,
                            "proposal": proposal_data,
                        }
                    )

                    # Check consensus
                    consensus_reached, _agreement_ratio, _vote_dict = (
                        self.byzantine_consensus.aggregate_votes(votes)
                    )

                    if consensus_reached:
                        await update_handler(entry)
                        to_remove.append(entry)
                        processed += 1
                        self.stats["consensus_reached"] += 1
                        # Clear votes for this chunk
                        if chunk_hash in self.consensus_votes:
                            del self.consensus_votes[chunk_hash]
                    else:
                        # Not enough votes yet, keep in queue
                        entry.retry_count += 1
                        if entry.retry_count >= entry.max_retries:
                            to_remove.append(entry)
                            self.stats["consensus_failed"] += 1
                            # Clear votes for failed entry
                            if chunk_hash in self.consensus_votes:
                                del self.consensus_votes[chunk_hash]

                except Exception:
                    self.logger.exception("Error in Byzantine consensus")
                    entry.retry_count += 1
                    if entry.retry_count >= entry.max_retries:
                        to_remove.append(entry)
                        # Clear votes for failed entry
                        chunk_hash = entry.chunk_hash
                        if chunk_hash in self.consensus_votes:
                            del self.consensus_votes[chunk_hash]

        # Remove processed entries
        for entry in to_remove:
            if entry in self.update_queue:
                self.update_queue.remove(entry)

        return processed

    async def vote_on_update(self, chunk_hash: bytes, peer_id: str, vote: bool) -> bool:
        """Vote on an update in consensus mode.

        Args:
            chunk_hash: Hash of chunk being voted on
            peer_id: Peer casting vote
            vote: True to accept, False to reject

        Returns:
            True if consensus reached after this vote

        """
        if self.sync_mode != SyncMode.CONSENSUS:
            return False

        if chunk_hash not in self.consensus_votes:
            self.consensus_votes[chunk_hash] = {}

        self.consensus_votes[chunk_hash][peer_id] = vote

        # Check if consensus reached
        votes = self.consensus_votes[chunk_hash]
        total_peers = len(self.peer_states)
        # Never apply immediately with zero peers (Byzantine/WS8).
        if total_peers == 0:
            return False

        if self.byzantine_consensus is not None:
            ok, _ = self.byzantine_consensus.check_byzantine_threshold(votes)
            return ok

        yes_votes = sum(1 for v in votes.values() if v)
        vote_ratio = yes_votes / total_peers

        return vote_ratio >= self.consensus_threshold

    async def _source_election_loop(self) -> None:
        """Periodic source failover / re-announcement loop."""
        while self._running:
            try:
                await asyncio.sleep(self.source_election_interval)

                if (
                    self.sync_mode == SyncMode.DESIGNATED
                    and self._source_needs_failover()
                ):
                    elected_peer = await self._elect_source_peer()
                    if elected_peer:
                        self.logger.info(
                            "Designated failover → %s term=%d",
                            elected_peer,
                            self.source_term,
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    self.logger.warning("Error in source election loop: %s", e)
                await asyncio.sleep(1)

    def get_status(self) -> XetSyncStatus:
        """Get current synchronization status.

        Returns:
            XetSyncStatus object

        """
        synced_peers = sum(
            1 for state in self.peer_states.values() if state.sync_progress >= 1.0
        )

        return XetSyncStatus(
            folder_path=self.folder_path or "",  # type: ignore[arg-type]
            sync_mode=self.sync_mode.value,
            is_syncing=len(self.update_queue) > 0,
            last_sync_time=max(
                (
                    s.last_sync_time
                    for s in self.peer_states.values()
                    if s.last_sync_time
                ),
                default=None,
            ),
            current_git_ref=None,  # Will be set by caller
            pending_changes=len(self.update_queue),
            connected_peers=len(self.peer_states),
            synced_peers=synced_peers,
            sync_progress=(
                synced_peers / len(self.peer_states) if self.peer_states else 0.0
            ),
            error=self.last_error,
            last_check_time=time.time(),
        )

    def get_queue_size(self) -> int:
        """Get current update queue size.

        Returns:
            Number of queued updates

        """
        return len(self.update_queue)

    def _save_consensus_state(self) -> None:
        """Save consensus state to disk."""
        if not self._state_dir:
            return

        try:
            state_file = self._state_dir / "consensus_state.json"

            # Convert consensus_votes to serializable format
            votes_serializable = {
                chunk_hash.hex(): dict(votes.items())
                for chunk_hash, votes in self.consensus_votes.items()
            }

            state_data = {
                "consensus_votes": votes_serializable,
                "sync_mode": self.sync_mode.value,
                "consensus_threshold": self.consensus_threshold,
            }

            with open(state_file, "w") as f:
                json.dump(state_data, f, indent=2)

            self.logger.debug("Saved consensus state to %s", state_file)
        except Exception as e:
            self.logger.warning("Failed to save consensus state: %s", e)

    def _load_consensus_state(self) -> None:
        """Load consensus state from disk."""
        if not self._state_dir:
            return

        try:
            state_file = self._state_dir / "consensus_state.json"
            if not state_file.exists():
                return

            with open(state_file) as f:
                state_data = json.load(f)

            # Restore consensus_votes
            votes_serializable = state_data.get("consensus_votes", {})
            self.consensus_votes = {
                bytes.fromhex(chunk_hash_hex): dict(votes.items())
                for chunk_hash_hex, votes in votes_serializable.items()
            }

            self.logger.debug("Loaded consensus state from %s", state_file)
        except Exception as e:
            self.logger.warning("Failed to load consensus state: %s", e)

    async def clear_queue(self) -> None:
        """Clear the update queue."""
        async with self.queue_lock:
            self.update_queue.clear()
