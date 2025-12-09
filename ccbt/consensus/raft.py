"""Raft consensus algorithm implementation.

Provides leader election, log replication, and safety guarantees for distributed consensus.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from ccbt.consensus.raft_state import LogEntry, RaftState

logger = logging.getLogger(__name__)


class RaftRole(Enum):
    """Raft node role."""

    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class RaftNode:
    """Raft consensus node.

    Implements Raft consensus algorithm with leader election,
    log replication, and safety guarantees.

    Attributes:
        node_id: Unique identifier for this node
        state: Persistent Raft state
        role: Current node role
        leader_id: ID of current leader (if known)
        peers: Set of peer node IDs

    """

    def __init__(
        self,
        node_id: str,
        state_path: Path | str | None = None,
        election_timeout: float = 1.0,
        heartbeat_interval: float = 0.1,
        apply_command_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        """Initialize Raft node.

        Args:
            node_id: Unique identifier for this node
            state_path: Path to persistent state file
            election_timeout: Election timeout in seconds (randomized)
            heartbeat_interval: Heartbeat interval in seconds
            apply_command_callback: Callback for applying committed commands

        """
        self.node_id = node_id
        self.state_path = Path(state_path) if state_path else None

        # Load or create state
        if self.state_path:
            self.state = RaftState.load(self.state_path)
        else:
            self.state = RaftState()

        self.role = RaftRole.FOLLOWER
        self.leader_id: str | None = None
        self.peers: set[str] = set()

        self.election_timeout = election_timeout
        self.heartbeat_interval = heartbeat_interval
        self.apply_command_callback = apply_command_callback

        # Timers
        self.last_heartbeat = time.time()
        self.election_deadline: float | None = None

        # Running state
        self.running = False
        self._election_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._apply_task: asyncio.Task | None = None

        # RPC handlers (would be network calls in production)
        self.send_vote_request: Callable[[str, dict[str, Any]], Any] | None = None
        self.send_append_entries: Callable[[str, dict[str, Any]], Any] | None = None

    async def start(self) -> None:
        """Start Raft node."""
        if self.running:
            return

        self.running = True
        self._reset_election_timer()

        # Start background tasks
        self._election_task = asyncio.create_task(self._election_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._apply_task = asyncio.create_task(self._apply_committed_loop())

        logger.info("Started Raft node %s (term: %d)", self.node_id, self.state.current_term)

    async def stop(self) -> None:
        """Stop Raft node."""
        if not self.running:
            return

        self.running = False

        # Cancel tasks
        for task in [self._election_task, self._heartbeat_task, self._apply_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Save state
        if self.state_path:
            self.state.save(self.state_path)

        logger.info("Stopped Raft node %s", self.node_id)

    def add_peer(self, peer_id: str) -> None:
        """Add peer to cluster.

        Args:
            peer_id: Peer node identifier

        """
        if peer_id != self.node_id:
            self.peers.add(peer_id)

    def remove_peer(self, peer_id: str) -> None:
        """Remove peer from cluster.

        Args:
            peer_id: Peer node identifier

        """
        self.peers.discard(peer_id)

    async def append_entry(self, command: dict[str, Any]) -> bool:
        """Append entry to log (leader only).

        Args:
            command: Command data to append

        Returns:
            True if entry was appended, False if not leader

        """
        if self.role != RaftRole.LEADER:
            return False

        # Append to local log
        entry = self.state.append_entry(self.state.current_term, command)

        # Replicate to followers (simplified - would use network calls)
        logger.debug("Appended entry %d to log", entry.index)

        return True

    async def vote_request(
        self, candidate_id: str, term: int, last_log_index: int, last_log_term: int
    ) -> bool:
        """Handle vote request RPC.

        Args:
            candidate_id: ID of candidate requesting vote
            term: Candidate's term
            last_log_index: Index of candidate's last log entry
            last_log_term: Term of candidate's last log entry

        Returns:
            True if vote granted, False otherwise

        """
        # Reply false if term < currentTerm
        if term < self.state.current_term:
            return False

        # If term > currentTerm, update term and become follower
        if term > self.state.current_term:
            self.state.current_term = term
            self.state.voted_for = None
            self.role = RaftRole.FOLLOWER
            self._reset_election_timer()

        # Vote if haven't voted for another candidate in this term
        # and candidate's log is at least as up-to-date
        can_vote = (
            self.state.voted_for is None or self.state.voted_for == candidate_id
        )

        if can_vote:
            # Check if candidate's log is at least as up-to-date
            our_last_term = self.state.get_last_log_term()
            our_last_index = self.state.get_last_log_index()

            log_ok = (last_log_term > our_last_term) or (
                last_log_term == our_last_term and last_log_index >= our_last_index
            )

            if log_ok:
                self.state.voted_for = candidate_id
                self._reset_election_timer()
                logger.info("Voted for %s in term %d", candidate_id, term)
                return True

        return False

    async def append_entries_rpc(
        self,
        leader_id: str,
        term: int,
        prev_log_index: int,
        prev_log_term: int,
        entries: list[dict[str, Any]],
        leader_commit: int,
    ) -> bool:
        """Handle append entries RPC.

        Args:
            leader_id: ID of leader sending entries
            term: Leader's term
            prev_log_index: Index of log entry immediately preceding new ones
            prev_log_term: Term of prev_log_index entry
            entries: Log entries to append
            leader_commit: Leader's commit_index

        Returns:
            True if entries were appended, False otherwise

        """
        # Reply false if term < currentTerm
        if term < self.state.current_term:
            return False

        # If term > currentTerm, update term and become follower
        if term > self.state.current_term:
            self.state.current_term = term
            self.state.voted_for = None
            self.role = RaftRole.FOLLOWER

        # Reset election timer (heartbeat received)
        self._reset_election_timer()
        self.leader_id = leader_id

        # Reply false if log doesn't contain an entry at prev_log_index
        # whose term matches prev_log_term
        if prev_log_index >= 0:
            prev_entry = self.state.get_entry(prev_log_index)
            if prev_entry is None or prev_entry.term != prev_log_term:
                return False

        # Append new entries (simplified - would handle conflicts)
        if entries:
            for entry_data in entries:
                self.state.append_entry(term, entry_data["command"])

        # Update commit_index
        if leader_commit > self.state.commit_index:
            self.state.commit_index = min(leader_commit, self.state.get_last_log_index())

        return True

    def _reset_election_timer(self) -> None:
        """Reset election timer with random timeout."""
        timeout = self.election_timeout + random.uniform(0, self.election_timeout)
        self.election_deadline = time.time() + timeout

    async def _election_loop(self) -> None:
        """Election loop for candidate role."""
        while self.running:
            try:
                if self.role == RaftRole.FOLLOWER:
                    # Wait for election timeout
                    if self.election_deadline and time.time() >= self.election_deadline:
                        # Start election
                        self.state.current_term += 1
                        self.state.voted_for = self.node_id
                        self.role = RaftRole.CANDIDATE
                        self.leader_id = None

                        logger.info(
                            "Starting election for term %d",
                            self.state.current_term,
                        )

                        # Request votes from peers (simplified)
                        votes = 1  # Vote for self
                        for peer_id in self.peers:
                            if self.send_vote_request:
                                try:
                                    result = await self.send_vote_request(
                                        peer_id,
                                        {
                                            "term": self.state.current_term,
                                            "candidate_id": self.node_id,
                                            "last_log_index": self.state.get_last_log_index(),
                                            "last_log_term": self.state.get_last_log_term(),
                                        },
                                    )
                                    if result:
                                        votes += 1
                                except Exception as e:
                                    logger.warning("Error requesting vote from %s: %s", peer_id, e)

                        # Check if we won election
                        if votes > len(self.peers) / 2:
                            self.role = RaftRole.LEADER
                            self.leader_id = self.node_id
                            logger.info("Elected as leader in term %d", self.state.current_term)
                        else:
                            # Lost election, become follower
                            self.role = RaftRole.FOLLOWER
                            self._reset_election_timer()

                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.running:
                    logger.warning("Error in election loop: %s", e)
                await asyncio.sleep(0.1)

    async def _heartbeat_loop(self) -> None:
        """Heartbeat loop for leader role."""
        while self.running:
            try:
                if self.role == RaftRole.LEADER:
                    # Send heartbeats to followers
                    for peer_id in self.peers:
                        if self.send_append_entries:
                            try:
                                await self.send_append_entries(
                                    peer_id,
                                    {
                                        "term": self.state.current_term,
                                        "leader_id": self.node_id,
                                        "prev_log_index": self.state.get_last_log_index(),
                                        "prev_log_term": self.state.get_last_log_term(),
                                        "entries": [],
                                        "leader_commit": self.state.commit_index,
                                    },
                                )
                            except Exception as e:
                                logger.warning("Error sending heartbeat to %s: %s", peer_id, e)

                    await asyncio.sleep(self.heartbeat_interval)
                else:
                    await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.running:
                    logger.warning("Error in heartbeat loop: %s", e)
                await asyncio.sleep(0.1)

    async def _apply_committed_loop(self) -> None:
        """Apply committed entries loop."""
        while self.running:
            try:
                # Apply committed entries
                while self.state.last_applied < self.state.commit_index:
                    self.state.last_applied += 1
                    entry = self.state.get_entry(self.state.last_applied)
                    if entry and self.apply_command_callback:
                        try:
                            self.apply_command_callback(entry.command)
                        except Exception as e:
                            logger.error("Error applying command: %s", e)

                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.running:
                    logger.warning("Error in apply loop: %s", e)
                await asyncio.sleep(0.1)

