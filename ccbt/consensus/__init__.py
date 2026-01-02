"""Consensus mechanisms for distributed BitTorrent operations.

This package provides consensus protocols for coordinated operations across
multiple BitTorrent clients or peers, including:

- Byzantine Fault Tolerance for handling malicious peers
- Raft consensus for distributed state management
- Consensus-based tracker operations

Modules:
    byzantine: Byzantine fault-tolerant consensus implementation
    raft: Raft consensus protocol implementation
    raft_state: Raft state machine and state management
"""

from __future__ import annotations

from ccbt.consensus.byzantine import ByzantineConsensus
from ccbt.consensus.raft import RaftNode
from ccbt.consensus.raft_state import RaftState, RaftStateType

__all__ = [
    "ByzantineConsensus",
    "RaftNode",
    "RaftState",
    "RaftStateType",
]






