"""XET folder synchronization manager with multiple sync modes.

This module manages different synchronization modes for XET folders:
- Designated Source: Single/multiple designated peers as source of truth
- Best Effort Queued: All nodes attempt updates, queued by priority
- Broadcast Queued: One/more nodes broadcast updates with queuing
- Consensus: Consensus-based update validation (majority vote)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ccbt.models import PeerInfo, XetSyncStatus

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
    git_ref: str | None
    timestamp: float
    priority: int = 0  # Higher priority = processed first
    source_peer: str | None = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class PeerSyncState:
    """Synchronization state for a peer."""

    peer_id: str
    peer_info: PeerInfo
    last_sync_time: float | None = None
    current_git_ref: str | None = None
    chunk_hashes: set[bytes] = field(default_factory=set)
    is_source: bool = False  # For designated mode
    sync_progress: float = 0.0
    last_contact: float = field(default_factory=time.time)


class XetSyncManager:
    """Manager for XET folder synchronization with multiple modes."""

    def __init__(
        self,
        session_manager: Any | None = None,
        folder_path: str | None = None,
        sync_mode: str = "best_effort",
        source_peers: list[str] | None = None,
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
        self.raft_node: Any | None = None  # RaftNode
        self.byzantine_consensus: Any | None = None  # ByzantineConsensus

        # Source peer election
        self.source_election_interval = 300.0  # 5 minutes
        self._source_election_task: asyncio.Task | None = None

        # Update queue
        self.update_queue: deque[UpdateEntry] = deque(maxlen=max_queue_size)
        self.queue_lock = asyncio.Lock()

        # Peer states
        self.peer_states: dict[str, PeerSyncState] = {}

        # Consensus tracking
        self.consensus_votes: dict[bytes, dict[str, bool]] = {}  # chunk_hash -> {peer_id: vote}
        
        # State persistence paths
        self._state_dir: Path | None = None
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
        self.allowlist_hash: bytes | None = None
        self.current_git_ref: str | None = None
        self._running = False

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start the sync manager."""
        if self._running:
            return

        self._running = True

        # Initialize consensus components if in consensus mode
        if self.sync_mode == SyncMode.CONSENSUS:
            await self._initialize_consensus()

        # Start source peer election task if in designated mode
        if self.sync_mode == SyncMode.DESIGNATED:
            self._source_election_task = asyncio.create_task(self._source_election_loop())

        self.logger.info("XET sync manager started")

    async def stop(self) -> None:
        """Stop the sync manager."""
        if not self._running:
            return

        self._running = False

        # Stop source election task
        if self._source_election_task:
            self._source_election_task.cancel()
            try:
                await self._source_election_task
            except asyncio.CancelledError:
                pass
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

    def get_allowlist_hash(self) -> bytes | None:
        """Get allowlist hash.

        Returns:
            Allowlist hash or None

        """
        return self.allowlist_hash

    def set_allowlist_hash(self, allowlist_hash: bytes | None) -> None:
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

    def get_current_git_ref(self) -> str | None:
        """Get current git reference.

        Returns:
            Git commit hash/ref or None

        """
        return self.current_git_ref

    def set_current_git_ref(self, git_ref: str | None) -> None:
        """Set current git reference.

        Args:
            git_ref: Git commit hash/ref to set

        """
        self.current_git_ref = git_ref

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

    async def queue_update(
        self,
        file_path: str,
        chunk_hash: bytes,
        git_ref: str | None = None,
        priority: int = 0,
        source_peer: str | None = None,
    ) -> bool:
        """Queue an update for synchronization.

        Args:
            file_path: Path to updated file
            chunk_hash: Hash of updated chunk
            git_ref: Git commit reference
            priority: Update priority (higher = processed first)
            source_peer: Peer that originated the update

        Returns:
            True if queued successfully, False if queue is full

        """
        async with self.queue_lock:
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
            )

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

    async def process_updates(
        self, update_handler: Any  # Callable that processes updates
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
            return processed

        except asyncio.TimeoutError:
            self.logger.error(
                "Timeout processing updates in %s mode", self.sync_mode.value
            )
            return 0
        except Exception as e:
            self.logger.exception(
                "Error processing updates in %s mode: %s", self.sync_mode.value, e
            )
            return 0

    async def _process_designated_updates(
        self, update_handler: Any
    ) -> int:
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
            # Only process if from designated source
            if entry.source_peer and entry.source_peer in self.source_peers:
                try:
                    await update_handler(entry)
                    to_remove.append(entry)
                    processed += 1
                except Exception as e:
                    self.logger.exception("Error processing update")
                    entry.retry_count += 1
                    if entry.retry_count >= entry.max_retries:
                        to_remove.append(entry)
                        self.stats["updates_failed"] += 1
            else:
                # Not from designated source, skip
                continue

        # Remove processed entries
        for entry in to_remove:
            if entry in self.update_queue:
                self.update_queue.remove(entry)

        return processed

    async def _process_best_effort_updates(
        self, update_handler: Any
    ) -> int:
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
                except Exception as e:
                    self.logger.error("Error processing resolved update: %s", e)
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
                    except Exception as e:
                        self.logger.error("Error processing update: %s", e)
                        entry.retry_count += 1
                        if entry.retry_count >= entry.max_retries:
                            to_remove.append(entry)
                            self.stats["updates_failed"] += 1

        # Remove processed entries
        for entry in to_remove:
            if entry in self.update_queue:
                self.update_queue.remove(entry)

        return processed

    async def _process_broadcast_updates(
        self, update_handler: Any
    ) -> int:
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
        updates_by_source: dict[str | None, list[UpdateEntry]] = {}
        for entry in self.update_queue:
            source = entry.source_peer
            if source not in updates_by_source:
                updates_by_source[source] = []
            updates_by_source[source].append(entry)

        # Process updates from each source
        for source, entries in updates_by_source.items():
            for entry in entries:
                try:
                    # Broadcast to all peers
                    await update_handler(entry)
                    to_remove.append(entry)
                    processed += 1
                except Exception as e:
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

    async def _process_consensus_updates(
        self, update_handler: Any
    ) -> int:
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
                except Exception as e:
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
                except Exception as e:
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

    async def _elect_source_peer(self) -> str | None:
        """Elect source peer based on criteria.

        Criteria: uptime, bandwidth, chunk availability

        Returns:
            Elected peer ID or None if no suitable peer

        """
        if not self.peer_states:
            return None

        best_peer_id = None
        best_score = -1.0

        for peer_id, peer_state in self.peer_states.items():
            # Calculate score based on multiple factors
            score = 0.0

            # Uptime factor (0.0 to 1.0)
            if peer_state.last_contact:
                uptime_factor = min(
                    1.0, (time.time() - peer_state.last_contact) / 3600.0
                )  # Normalize to 1 hour
                score += uptime_factor * 0.3

            # Chunk availability factor (0.0 to 1.0)
            chunk_count = len(peer_state.chunk_hashes)
            chunk_factor = min(1.0, chunk_count / 100.0)  # Normalize to 100 chunks
            score += chunk_factor * 0.4

            # Sync progress factor (0.0 to 1.0)
            score += peer_state.sync_progress * 0.3

            if score > best_score:
                best_score = score
                best_peer_id = peer_id

        if best_peer_id and best_score > 0.5:  # Minimum threshold
            self.logger.info(
                "Elected source peer: %s (score: %.2f)",
                best_peer_id,
                best_score,
            )
            return best_peer_id

        return None

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
                node_id = hashlib.sha256(str(self.folder_path).encode()).hexdigest()[:16]
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

            # Fallback to Byzantine consensus
            try:
                from ccbt.consensus.byzantine import ByzantineConsensus

                # Calculate fault threshold from consensus threshold
                # Byzantine requires 2f+1 nodes, so f < n/3
                fault_threshold = 0.33  # Default

                # Create Byzantine consensus
                self.byzantine_consensus = ByzantineConsensus(
                    node_id=node_id,
                    fault_threshold=fault_threshold,
                    weighted_voting=False,  # Can be enabled via config
                )

                self.logger.info(
                    "Initialized Byzantine consensus (node_id=%s)",
                    node_id,
                )
                return

            except Exception as e:
                self.logger.warning("Failed to initialize Byzantine consensus: %s", e)

            # If both fail, log error but continue (will use simple consensus)
            self.logger.error(
                "Failed to initialize any consensus mechanism. "
                "Falling back to simple consensus."
            )

        except Exception as e:
            self.logger.exception("Error initializing consensus: %s", e)

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
                                # Schedule async application
                                asyncio.create_task(self._apply_update_entry(entry, update_handler))
                            else:
                                self.logger.warning(
                                    "No update handler for Raft-committed update: %s",
                                    file_path,
                                )
                            break

        except Exception as e:
            self.logger.exception("Error applying Raft command: %s", e)

    async def _apply_update_entry(self, entry: UpdateEntry, update_handler: Any) -> None:
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
        except Exception as e:
            self.logger.exception("Error applying update entry: %s", e)
            entry.retry_count += 1
            if entry.retry_count >= entry.max_retries:
                async with self.queue_lock:
                    if entry in self.update_queue:
                        self.update_queue.remove(entry)
                self.stats["updates_failed"] += 1

    async def _send_raft_vote_request(
        self, peer_id: str, request: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Send Raft vote request to peer (simplified - would use network in production).

        Args:
            peer_id: Peer to send request to
            request: Vote request data

        Returns:
            Vote response or None
        """
        # In production, this would send a network RPC
        # For now, return None (would be handled by network layer)
        self.logger.debug("Would send Raft vote request to %s", peer_id)
        return None

    async def _send_raft_append_entries(
        self, peer_id: str, request: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Send Raft append entries to peer (simplified - would use network in production).

        Args:
            peer_id: Peer to send request to
            request: Append entries data

        Returns:
            Append entries response or None
        """
        # In production, this would send a network RPC
        # For now, return None (would be handled by network layer)
        self.logger.debug("Would send Raft append entries to %s", peer_id)
        return None

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
                        entry._update_handler = update_handler
                        # Don't remove yet - wait for commit
                        # Entry will be removed when committed and applied
                        processed += 1
                    else:
                        # Failed to append, retry
                        entry.retry_count += 1
                        if entry.retry_count >= entry.max_retries:
                            to_remove.append(entry)
                            self.stats["updates_failed"] += 1
                except Exception as e:
                    self.logger.error("Error in Raft consensus: %s", e)
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
                        for peer_id, vote_value in self.consensus_votes[chunk_hash].items():
                            votes.append({
                                "voter": peer_id,
                                "vote": vote_value,
                                "proposal": proposal_data,
                            })

                    # Add our own vote (we vote yes for our own proposals)
                    votes.append({
                        "voter": self.byzantine_consensus.node_id,
                        "vote": True,
                        "proposal": proposal_data,
                    })

                    # Check consensus
                    consensus_reached, agreement_ratio, vote_dict = (
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

                except Exception as e:
                    self.logger.error("Error in Byzantine consensus: %s", e)
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

    async def vote_on_update(
        self, chunk_hash: bytes, peer_id: str, vote: bool
    ) -> bool:
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
        if total_peers == 0:
            return True

        yes_votes = sum(1 for v in votes.values() if v)
        vote_ratio = yes_votes / total_peers

        return vote_ratio >= self.consensus_threshold

    async def _source_election_loop(self) -> None:
        """Periodic source peer election loop."""
        while self._running:
            try:
                await asyncio.sleep(self.source_election_interval)

                if self.sync_mode == SyncMode.DESIGNATED:
                    # Elect new source peer if needed
                    elected_peer = await self._elect_source_peer()
                    if elected_peer and elected_peer not in self.source_peers:
                        # Update source peers
                        self.source_peers.add(elected_peer)
                        if elected_peer in self.peer_states:
                            self.peer_states[elected_peer].is_source = True
                        self.logger.info("Elected new source peer: %s", elected_peer)

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
            1
            for state in self.peer_states.values()
            if state.sync_progress >= 1.0
        )

        return XetSyncStatus(
            folder_path=self.folder_path,
            sync_mode=self.sync_mode.value,
            is_syncing=len(self.update_queue) > 0,
            last_sync_time=max(
                (s.last_sync_time for s in self.peer_states.values() if s.last_sync_time),
                default=None,
            ),
            current_git_ref=None,  # Will be set by caller
            pending_changes=len(self.update_queue),
            connected_peers=len(self.peer_states),
            synced_peers=synced_peers,
            sync_progress=(
                synced_peers / len(self.peer_states)
                if self.peer_states
                else 0.0
            ),
            error=None,
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
                chunk_hash.hex(): {
                    peer_id: vote for peer_id, vote in votes.items()
                }
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
                bytes.fromhex(chunk_hash_hex): {
                    peer_id: vote for peer_id, vote in votes.items()
                }
                for chunk_hash_hex, votes in votes_serializable.items()
            }

            self.logger.debug("Loaded consensus state from %s", state_file)
        except Exception as e:
            self.logger.warning("Failed to load consensus state: %s", e)

    async def clear_queue(self) -> None:
        """Clear the update queue."""
        async with self.queue_lock:
            self.update_queue.clear()

