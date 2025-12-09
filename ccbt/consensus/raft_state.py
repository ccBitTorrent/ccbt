"""Raft state machine for persistent state storage.

Provides persistent state management for Raft consensus algorithm.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """Raft log entry."""

    term: int
    index: int
    command: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class RaftState:
    """Raft persistent state.

    Attributes:
        current_term: Current term number
        voted_for: Candidate ID that received vote in current term (or None)
        log: List of log entries
        commit_index: Index of highest log entry known to be committed

    """

    current_term: int = 0
    voted_for: str | None = None
    log: list[LogEntry] = field(default_factory=list)
    commit_index: int = -1
    last_applied: int = -1

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for serialization.

        Returns:
            Dictionary representation of state

        """
        return {
            "current_term": self.current_term,
            "voted_for": self.voted_for,
            "log": [
                {
                    "term": entry.term,
                    "index": entry.index,
                    "command": entry.command,
                    "timestamp": entry.timestamp,
                }
                for entry in self.log
            ],
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RaftState:
        """Create state from dictionary.

        Args:
            data: Dictionary representation of state

        Returns:
            RaftState instance

        """
        log_entries = [
            LogEntry(
                term=entry["term"],
                index=entry["index"],
                command=entry["command"],
                timestamp=entry.get("timestamp", time.time()),
            )
            for entry in data.get("log", [])
        ]

        return cls(
            current_term=data.get("current_term", 0),
            voted_for=data.get("voted_for"),
            log=log_entries,
            commit_index=data.get("commit_index", -1),
            last_applied=data.get("last_applied", -1),
        )

    def save(self, state_path: Path) -> None:
        """Save state to persistent storage.

        Args:
            state_path: Path to state file

        """
        try:
            # Ensure directory exists
            state_path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize state
            state_dict = self.to_dict()
            with open(state_path, "w") as f:
                json.dump(state_dict, f, indent=2)

            logger.debug("Saved Raft state to %s", state_path)
        except Exception as e:
            logger.error("Failed to save Raft state: %s", e)
            raise

    @classmethod
    def load(cls, state_path: Path) -> RaftState:
        """Load state from persistent storage.

        Args:
            state_path: Path to state file

        Returns:
            RaftState instance (default if file doesn't exist)

        """
        if not state_path.exists():
            logger.debug("Raft state file not found, using default state")
            return cls()

        try:
            with open(state_path) as f:
                state_dict = json.load(f)

            state = cls.from_dict(state_dict)
            logger.debug("Loaded Raft state from %s", state_path)
            return state
        except Exception as e:
            logger.warning("Failed to load Raft state: %s, using default", e)
            return cls()

    def append_entry(self, term: int, command: dict[str, Any]) -> LogEntry:
        """Append entry to log.

        Args:
            term: Term number
            command: Command data

        Returns:
            Created log entry

        """
        index = len(self.log)
        entry = LogEntry(term=term, index=index, command=command)
        self.log.append(entry)
        return entry

    def get_entry(self, index: int) -> LogEntry | None:
        """Get log entry by index.

        Args:
            index: Entry index

        Returns:
            Log entry or None if not found

        """
        if 0 <= index < len(self.log):
            return self.log[index]
        return None

    def get_last_log_term(self) -> int:
        """Get term of last log entry.

        Returns:
            Term number, or 0 if log is empty

        """
        if not self.log:
            return 0
        return self.log[-1].term

    def get_last_log_index(self) -> int:
        """Get index of last log entry.

        Returns:
            Index, or -1 if log is empty

        """
        return len(self.log) - 1



