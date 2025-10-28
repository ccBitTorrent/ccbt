"""Exception hierarchy for ccBitTorrent.

from __future__ import annotations

Provides a comprehensive exception hierarchy for better error handling
and debugging throughout the application.
"""

from __future__ import annotations

from typing import Any


class CCBTError(Exception):
    """Base exception for all ccBitTorrent errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        """Initialize CCBT error."""
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class NetworkError(CCBTError):
    """Network-related errors."""


class TrackerError(NetworkError):
    """Tracker communication errors."""


class PeerConnectionError(NetworkError):
    """Peer connection errors."""


class DHTError(NetworkError):
    """DHT (Distributed Hash Table) errors."""


class DiskError(CCBTError):
    """Disk I/O related errors."""


class FileSystemError(DiskError):
    """File system operation errors."""


class PreallocationError(DiskError):
    """File preallocation errors."""


class ProtocolError(CCBTError):
    """BitTorrent protocol errors."""


class HandshakeError(ProtocolError):
    """Handshake protocol errors."""


class MessageError(ProtocolError):
    """Message parsing/serialization errors."""


class ValidationError(CCBTError):
    """Data validation errors."""


class ConfigurationError(ValidationError):
    """Configuration validation errors."""


class TorrentError(ValidationError):
    """Torrent file validation errors."""


class BencodeError(ValidationError):
    """Bencode encoding/decoding errors."""


class ResourceError(CCBTError):
    """Resource management errors."""


class CCBTTimeoutError(CCBTError):
    """Timeout errors."""


class SecurityError(CCBTError):
    """Security-related errors."""


class PeerValidationError(SecurityError):
    """Peer validation errors."""


class RateLimitError(SecurityError):
    """Rate limiting errors."""


class CheckpointError(CCBTError):
    """Base checkpoint exception."""


class CheckpointNotFoundError(CheckpointError):
    """Checkpoint file not found."""


class CheckpointCorruptedError(CheckpointError):
    """Checkpoint data corrupted."""


class CheckpointVersionError(CheckpointError):
    """Incompatible checkpoint version."""
