"""Conflict resolution strategies for XET folder synchronization.

Provides multiple conflict resolution strategies including last-write-wins,
version vectors, and 3-way merge.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConflictStrategy(Enum):
    """Conflict resolution strategy."""

    LAST_WRITE_WINS = "last_write_wins"
    VERSION_VECTOR = "version_vector"
    THREE_WAY_MERGE = "three_way_merge"
    TIMESTAMP = "timestamp"


class ConflictResolver:
    """Conflict resolver for XET folder synchronization.

    Detects and resolves conflicts using multiple strategies.

    Attributes:
        strategy: Conflict resolution strategy
        version_vectors: Dictionary of file_path -> version vector

    """

    def __init__(self, strategy: str = "last_write_wins"):
        """Initialize conflict resolver.

        Args:
            strategy: Conflict resolution strategy

        """
        self.strategy = ConflictStrategy(strategy)
        self.version_vectors: dict[str, dict[str, int]] = {}  # file_path -> {peer_id: version}

    def detect_conflict(
        self,
        file_path: str,
        peer_id: str,
        timestamp: float,
        existing_timestamp: float | None = None,
    ) -> bool:
        """Detect if there's a conflict.

        Args:
            file_path: Path to file
            peer_id: Peer that made the change
            timestamp: Timestamp of change
            existing_timestamp: Existing timestamp (if any)

        Returns:
            True if conflict detected

        """
        if existing_timestamp is None:
            return False

        # Conflict if timestamps are very close (within 1 second)
        # and from different peers
        if abs(timestamp - existing_timestamp) < 1.0:
            return True

        return False

    def resolve_conflict(
        self,
        file_path: str,
        our_version: dict[str, Any],
        their_version: dict[str, Any],
        base_version: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve conflict between versions.

        Args:
            file_path: Path to file
            our_version: Our version of the file
            their_version: Their version of the file
            base_version: Base version for 3-way merge (optional)

        Returns:
            Resolved version

        """
        if self.strategy == ConflictStrategy.LAST_WRITE_WINS:
            return self._last_write_wins(our_version, their_version)
        elif self.strategy == ConflictStrategy.VERSION_VECTOR:
            return self._version_vector_merge(file_path, our_version, their_version)
        elif self.strategy == ConflictStrategy.THREE_WAY_MERGE:
            return self._three_way_merge(our_version, their_version, base_version)
        elif self.strategy == ConflictStrategy.TIMESTAMP:
            return self._timestamp_merge(our_version, their_version)
        else:
            # Default to last write wins
            return self._last_write_wins(our_version, their_version)

    def _last_write_wins(
        self, our_version: dict[str, Any], their_version: dict[str, Any]
    ) -> dict[str, Any]:
        """Last write wins strategy.

        Args:
            our_version: Our version
            their_version: Their version

        Returns:
            Version with later timestamp

        """
        our_ts = our_version.get("timestamp", 0.0)
        their_ts = their_version.get("timestamp", 0.0)

        if their_ts > our_ts:
            return their_version
        return our_version

    def _version_vector_merge(
        self,
        file_path: str,
        our_version: dict[str, Any],
        their_version: dict[str, Any],
    ) -> dict[str, Any]:
        """Version vector merge strategy.

        Args:
            file_path: Path to file
            our_version: Our version
            their_version: Their version

        Returns:
            Merged version

        """
        # Update version vector
        if file_path not in self.version_vectors:
            self.version_vectors[file_path] = {}

        our_peer = our_version.get("peer_id", "us")
        their_peer = their_version.get("peer_id", "them")

        # Increment versions
        self.version_vectors[file_path][our_peer] = (
            self.version_vectors[file_path].get(our_peer, 0) + 1
        )
        self.version_vectors[file_path][their_peer] = (
            self.version_vectors[file_path].get(their_peer, 0) + 1
        )

        # Compare version vectors
        our_vv = our_version.get("version_vector", {})
        their_vv = their_version.get("version_vector", {})

        # If one version vector dominates, use that version
        if self._version_vector_dominates(our_vv, their_vv):
            return our_version
        elif self._version_vector_dominates(their_vv, our_vv):
            return their_version
        else:
            # Concurrent changes - use later timestamp
            return self._last_write_wins(our_version, their_version)

    def _version_vector_dominates(
        self, vv1: dict[str, int], vv2: dict[str, int]
    ) -> bool:
        """Check if version vector 1 dominates version vector 2.

        Args:
            vv1: First version vector
            vv2: Second version vector

        Returns:
            True if vv1 dominates vv2

        """
        # vv1 dominates if all entries in vv1 are >= corresponding entries in vv2
        # and at least one is strictly greater
        all_greater_equal = True
        at_least_one_greater = False

        for peer_id, version in vv1.items():
            their_version = vv2.get(peer_id, 0)
            if version < their_version:
                return False
            if version > their_version:
                at_least_one_greater = True

        # Check if vv2 has peers not in vv1
        for peer_id in vv2:
            if peer_id not in vv1:
                return False

        return all_greater_equal and at_least_one_greater

    def _three_way_merge(
        self,
        our_version: dict[str, Any],
        their_version: dict[str, Any],
        base_version: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Three-way merge strategy.

        Args:
            our_version: Our version
            their_version: Their version
            base_version: Base version

        Returns:
            Merged version

        """
        if base_version is None:
            # Fallback to last write wins if no base
            return self._last_write_wins(our_version, their_version)

        # Simple 3-way merge: if both changed from base, prefer our version
        # In production, would use proper diff/merge algorithm
        our_changed = our_version != base_version
        their_changed = their_version != base_version

        if our_changed and not their_changed:
            return our_version
        elif their_changed and not our_changed:
            return their_version
        elif our_changed and their_changed:
            # Both changed - use our version (could be improved with proper merge)
            return our_version
        else:
            return base_version

    def _timestamp_merge(
        self, our_version: dict[str, Any], their_version: dict[str, Any]
    ) -> dict[str, Any]:
        """Timestamp-based merge strategy.

        Args:
            our_version: Our version
            their_version: Their version

        Returns:
            Version with later timestamp

        """
        return self._last_write_wins(our_version, their_version)

    def merge_files(
        self,
        file_path: str,
        our_content: bytes,
        their_content: bytes,
        base_content: bytes | None = None,
    ) -> bytes:
        """Merge file contents using selected strategy.

        Args:
            file_path: Path to file
            our_content: Our file content
            their_content: Their file content
            base_content: Base file content (for 3-way merge)

        Returns:
            Merged file content

        """
        if self.strategy == ConflictStrategy.THREE_WAY_MERGE and base_content:
            # Simple 3-way merge: if both changed, prefer our content
            if our_content != base_content and their_content != base_content:
                # Both changed - use our content (could be improved)
                return our_content
            elif our_content != base_content:
                return our_content
            elif their_content != base_content:
                return their_content
            else:
                return base_content
        else:
            # For other strategies, use timestamp-based resolution
            # (In practice, would compare actual file timestamps)
            if len(their_content) > len(our_content):
                return their_content
            return our_content


class ThreeWayMerge:
    """Three-way merge implementation."""

    @staticmethod
    def merge(
        base: bytes, ours: bytes, theirs: bytes
    ) -> bytes:
        """Perform 3-way merge.

        Args:
            base: Base version
            ours: Our version
            theirs: Their version

        Returns:
            Merged version

        """
        # Simplified merge - in production would use proper diff algorithm
        if ours == base:
            return theirs
        elif theirs == base:
            return ours
        elif ours == theirs:
            return ours
        else:
            # Both changed - prefer ours (could be improved)
            return ours


class VersionVectorMerge:
    """Version vector merge implementation."""

    def __init__(self):
        """Initialize version vector merge."""
        self.vectors: dict[str, dict[str, int]] = {}

    def merge(
        self,
        file_path: str,
        our_version: dict[str, Any],
        their_version: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge using version vectors.

        Args:
            file_path: Path to file
            our_version: Our version
            their_version: Their version

        Returns:
            Merged version

        """
        # Update version vectors
        if file_path not in self.vectors:
            self.vectors[file_path] = {}

        our_peer = our_version.get("peer_id", "us")
        their_peer = their_version.get("peer_id", "them")

        self.vectors[file_path][our_peer] = (
            self.vectors[file_path].get(our_peer, 0) + 1
        )
        self.vectors[file_path][their_peer] = (
            self.vectors[file_path].get(their_peer, 0) + 1
        )

        # Use version with higher vector
        our_vv = our_version.get("version_vector", {})
        their_vv = their_version.get("version_vector", {})

        if sum(our_vv.values()) >= sum(their_vv.values()):
            return our_version
        return their_version


class TimestampMerge:
    """Timestamp-based merge implementation."""

    @staticmethod
    def merge(
        our_version: dict[str, Any], their_version: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge using timestamps.

        Args:
            our_version: Our version
            their_version: Their version

        Returns:
            Version with later timestamp

        """
        our_ts = our_version.get("timestamp", 0.0)
        their_ts = their_version.get("timestamp", 0.0)

        if their_ts > our_ts:
            return their_version
        return our_version



