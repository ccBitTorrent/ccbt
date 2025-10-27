"""Peer Validator for ccBitTorrent.

Provides peer validation including:
- Handshake validation
- Peer ID validation
- Protocol compliance checking
- Connection quality assessment
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..models import PeerInfo


class ValidationResult(Enum):
    """Validation result types."""
    VALID = "valid"
    INVALID_HANDSHAKE = "invalid_handshake"
    INVALID_PEER_ID = "invalid_peer_id"
    PROTOCOL_VIOLATION = "protocol_violation"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


@dataclass
class ValidationMetrics:
    """Validation metrics for a peer."""
    peer_id: str
    ip: str
    handshake_time: float
    message_count: int
    bytes_sent: int
    bytes_received: int
    error_count: int
    last_activity: float
    connection_quality: float  # 0.0 to 1.0
    protocol_compliance: float  # 0.0 to 1.0


class PeerValidator:
    """Peer validation and quality assessment."""

    def __init__(self):
        self.validation_metrics: Dict[str, ValidationMetrics] = {}
        self.peer_id_patterns: Dict[str, int] = {}
        self.suspicious_patterns: List[str] = []

        # Configuration
        self.max_handshake_time = 10.0  # seconds
        self.min_connection_quality = 0.3
        self.min_protocol_compliance = 0.5
        self.max_error_rate = 0.1

        # Known malicious peer ID patterns
        self.malicious_patterns = [
            b"-AZ",  # Azureus
            b"-UT",  # uTorrent
            b"-TR",  # Transmission
            b"-LT",  # libtorrent
            b"-BT",  # BitTorrent
        ]

        # Suspicious peer ID patterns
        self.suspicious_patterns = [
            "00000000000000000000",  # All zeros
            "FFFFFFFFFFFFFFFFFFFF",  # All Fs
            "AAAAAAAAAAAAAAAAAAAA",  # All As
        ]

    async def validate_handshake(self, peer_info: PeerInfo, handshake_data: bytes) -> Tuple[bool, str]:
        """Validate peer handshake.
        
        Args:
            peer_info: Peer information
            handshake_data: Raw handshake data
            
        Returns:
            Tuple of (is_valid, reason)
        """
        try:
            # Check handshake length (68 bytes for BitTorrent)
            if len(handshake_data) != 68:
                return False, f"Invalid handshake length: {len(handshake_data)}"

            # Check protocol string (first 19 bytes should be "BitTorrent protocol")
            protocol_string = handshake_data[:19]
            if protocol_string != b"BitTorrent protocol":
                return False, f"Invalid protocol string: {protocol_string}"

            # Check reserved bytes (next 8 bytes)
            reserved_bytes = handshake_data[19:27]
            if not self._validate_reserved_bytes(reserved_bytes):
                return False, "Invalid reserved bytes"

            # Check info hash (next 20 bytes)
            info_hash = handshake_data[27:47]
            if not self._validate_info_hash(info_hash):
                return False, "Invalid info hash"

            # Check peer ID (last 20 bytes)
            peer_id = handshake_data[47:67]
            if not self._validate_peer_id(peer_id):
                return False, "Invalid peer ID"

            # Update validation metrics
            self._update_validation_metrics(peer_info, True, len(handshake_data))

            return True, "Valid handshake"

        except Exception as e:
            self._update_validation_metrics(peer_info, False, 0)
            return False, f"Handshake validation error: {e!s}"

    async def validate_message(self, peer_info: PeerInfo, message: bytes) -> Tuple[bool, str]:
        """Validate peer message.
        
        Args:
            peer_info: Peer information
            message: Raw message data
            
        Returns:
            Tuple of (is_valid, reason)
        """
        try:
            # Check message length
            if len(message) == 0:
                return False, "Empty message"

            if len(message) > 1024 * 1024:  # 1MB limit
                return False, "Message too large"

            # Check message format
            if not self._validate_message_format(message):
                return False, "Invalid message format"

            # Update validation metrics
            self._update_validation_metrics(peer_info, True, len(message))

            return True, "Valid message"

        except Exception as e:
            self._update_validation_metrics(peer_info, False, 0)
            return False, f"Message validation error: {e!s}"

    async def assess_peer_quality(self, peer_info: PeerInfo) -> Tuple[float, Dict[str, Any]]:
        """Assess peer connection quality.
        
        Args:
            peer_info: Peer information
            
        Returns:
            Tuple of (quality_score, assessment_details)
        """
        peer_id = peer_info.peer_id.hex() if peer_info.peer_id else ""

        if peer_id not in self.validation_metrics:
            return 0.0, {"reason": "No validation data available"}

        metrics = self.validation_metrics[peer_id]

        # Calculate quality score based on multiple factors
        quality_factors = {
            "handshake_time": self._assess_handshake_time(metrics.handshake_time),
            "message_efficiency": self._assess_message_efficiency(metrics),
            "error_rate": self._assess_error_rate(metrics),
            "activity_level": self._assess_activity_level(metrics),
            "protocol_compliance": self._assess_protocol_compliance(metrics),
        }

        # Weighted average of quality factors
        weights = {
            "handshake_time": 0.2,
            "message_efficiency": 0.3,
            "error_rate": 0.25,
            "activity_level": 0.15,
            "protocol_compliance": 0.1,
        }

        quality_score = sum(
            quality_factors[factor] * weights[factor]
            for factor in quality_factors
        )

        # Update metrics
        metrics.connection_quality = quality_score

        assessment_details = {
            "quality_score": quality_score,
            "factors": quality_factors,
            "metrics": {
                "handshake_time": metrics.handshake_time,
                "message_count": metrics.message_count,
                "bytes_sent": metrics.bytes_sent,
                "bytes_received": metrics.bytes_received,
                "error_count": metrics.error_count,
                "last_activity": metrics.last_activity,
            },
        }

        return quality_score, assessment_details

    def get_validation_metrics(self, peer_id: str) -> Optional[ValidationMetrics]:
        """Get validation metrics for a peer."""
        return self.validation_metrics.get(peer_id)

    def get_all_validation_metrics(self) -> Dict[str, ValidationMetrics]:
        """Get all validation metrics."""
        return self.validation_metrics.copy()

    def cleanup_old_metrics(self, max_age_seconds: int = 3600) -> None:
        """Clean up old validation metrics."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        to_remove = []
        for peer_id, metrics in self.validation_metrics.items():
            if metrics.last_activity < cutoff_time:
                to_remove.append(peer_id)

        for peer_id in to_remove:
            del self.validation_metrics[peer_id]

    def _validate_reserved_bytes(self, reserved_bytes: bytes) -> bool:
        """Validate reserved bytes in handshake."""
        # Check for known extension flags
        # Bit 0: DHT support
        # Bit 1: Fast extension
        # Bit 2: Extension protocol
        # Bit 3: Azureus messaging protocol

        # For now, accept any reserved bytes
        # In the future, we could validate specific extension support
        return True

    def _validate_info_hash(self, info_hash: bytes) -> bool:
        """Validate info hash."""
        # Check if info hash is valid SHA-1 (20 bytes)
        if len(info_hash) != 20:
            return False

        # Check if it's not all zeros or all Fs
        if info_hash == b"\x00" * 20 or info_hash == b"\xFF" * 20:
            return False

        return True

    def _validate_peer_id(self, peer_id: bytes) -> bool:
        """Validate peer ID."""
        if len(peer_id) != 20:
            return False

        # Check for malicious patterns
        for pattern in self.malicious_patterns:
            if peer_id.startswith(pattern):
                return False

        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if peer_id.hex() == pattern:
                return False

        # Check for duplicate peer IDs
        peer_id_str = peer_id.hex()
        if peer_id_str in self.peer_id_patterns:
            self.peer_id_patterns[peer_id_str] += 1
            # If we see the same peer ID too many times, it's suspicious
            if self.peer_id_patterns[peer_id_str] > 10:
                return False
        else:
            self.peer_id_patterns[peer_id_str] = 1

        return True

    def _validate_message_format(self, message: bytes) -> bool:
        """Validate message format."""
        # Check message length prefix
        if len(message) < 4:
            return False

        # First 4 bytes should be message length
        try:
            message_length = int.from_bytes(message[:4], "big")
            if message_length < 0 or message_length > len(message) - 4:
                return False
        except:
            return False

        return True

    def _update_validation_metrics(self, peer_info: PeerInfo, success: bool, bytes_count: int) -> None:
        """Update validation metrics for a peer."""
        peer_id = peer_info.peer_id.hex() if peer_info.peer_id else ""

        if peer_id not in self.validation_metrics:
            self.validation_metrics[peer_id] = ValidationMetrics(
                peer_id=peer_id,
                ip=peer_info.ip,
                handshake_time=0.0,
                message_count=0,
                bytes_sent=0,
                bytes_received=0,
                error_count=0,
                last_activity=time.time(),
                connection_quality=0.5,
                protocol_compliance=0.5,
            )

        metrics = self.validation_metrics[peer_id]
        metrics.message_count += 1
        metrics.last_activity = time.time()

        if success:
            metrics.bytes_received += bytes_count
        else:
            metrics.error_count += 1

    def _assess_handshake_time(self, handshake_time: float) -> float:
        """Assess handshake time quality."""
        if handshake_time <= 1.0:
            return 1.0
        if handshake_time <= 5.0:
            return 0.8
        if handshake_time <= 10.0:
            return 0.6
        return 0.2

    def _assess_message_efficiency(self, metrics: ValidationMetrics) -> float:
        """Assess message efficiency."""
        if metrics.message_count == 0:
            return 0.0

        # Calculate bytes per message
        total_bytes = metrics.bytes_sent + metrics.bytes_received
        bytes_per_message = total_bytes / metrics.message_count

        # Optimal range is 100-1000 bytes per message
        if 100 <= bytes_per_message <= 1000:
            return 1.0
        if 50 <= bytes_per_message <= 2000:
            return 0.8
        if 25 <= bytes_per_message <= 4000:
            return 0.6
        return 0.3

    def _assess_error_rate(self, metrics: ValidationMetrics) -> float:
        """Assess error rate."""
        if metrics.message_count == 0:
            return 1.0

        error_rate = metrics.error_count / metrics.message_count

        if error_rate <= 0.01:  # 1% or less
            return 1.0
        if error_rate <= 0.05:  # 5% or less
            return 0.8
        if error_rate <= 0.1:  # 10% or less
            return 0.6
        return 0.2

    def _assess_activity_level(self, metrics: ValidationMetrics) -> float:
        """Assess activity level."""
        current_time = time.time()
        time_since_activity = current_time - metrics.last_activity

        if time_since_activity <= 60:  # Active within last minute
            return 1.0
        if time_since_activity <= 300:  # Active within last 5 minutes
            return 0.8
        if time_since_activity <= 900:  # Active within last 15 minutes
            return 0.6
        return 0.3

    def _assess_protocol_compliance(self, metrics: ValidationMetrics) -> float:
        """Assess protocol compliance."""
        # This is a simplified assessment
        # In a real implementation, this would check for proper
        # BitTorrent protocol compliance

        if metrics.error_count == 0:
            return 1.0
        if metrics.error_count <= metrics.message_count * 0.05:
            return 0.8
        if metrics.error_count <= metrics.message_count * 0.1:
            return 0.6
        return 0.3
