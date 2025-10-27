"""Exception hierarchy for ccBitTorrent.

Provides a comprehensive exception hierarchy for better error handling
and debugging throughout the application.
"""

from typing import Any, Dict, Optional


class CCBTException(Exception):
    """Base exception for all ccBitTorrent errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class NetworkError(CCBTException):
    """Network-related errors."""


class TrackerError(NetworkError):
    """Tracker communication errors."""


class PeerConnectionError(NetworkError):
    """Peer connection errors."""


class DHTError(NetworkError):
    """DHT (Distributed Hash Table) errors."""


class DiskError(CCBTException):
    """Disk I/O related errors."""


class FileSystemError(DiskError):
    """File system operation errors."""


class PreallocationError(DiskError):
    """File preallocation errors."""


class ProtocolError(CCBTException):
    """BitTorrent protocol errors."""


class HandshakeError(ProtocolError):
    """Handshake protocol errors."""


class MessageError(ProtocolError):
    """Message parsing/serialization errors."""


class ValidationError(CCBTException):
    """Data validation errors."""


class ConfigurationError(ValidationError):
    """Configuration validation errors."""


class TorrentError(ValidationError):
    """Torrent file validation errors."""


class BencodeError(ValidationError):
    """Bencode encoding/decoding errors."""


class ResourceError(CCBTException):
    """Resource management errors."""


class TimeoutError(CCBTException):
    """Timeout errors."""


class SecurityError(CCBTException):
    """Security-related errors."""


class PeerValidationError(SecurityError):
    """Peer validation errors."""


class RateLimitError(SecurityError):
    """Rate limiting errors."""


class CheckpointError(CCBTException):
    """Base checkpoint exception."""


class CheckpointNotFoundError(CheckpointError):
    """Checkpoint file not found."""


class CheckpointCorruptedError(CheckpointError):
    """Checkpoint data corrupted."""


class CheckpointVersionError(CheckpointError):
    """Incompatible checkpoint version."""
