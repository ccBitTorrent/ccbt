"""Anomaly Detector for ccBitTorrent.

from __future__ import annotations

Provides anomaly detection including:
- Statistical anomaly detection
- Behavioral pattern analysis
- Network anomaly detection
- Machine learning-based detection
"""

from __future__ import annotations

import math
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypedDict

from ccbt.utils.events import Event, EventType, emit_event


class AnomalyType(Enum):
    """Types of anomalies."""

    STATISTICAL = "statistical"
    BEHAVIORAL = "behavioral"
    NETWORK = "network"
    PROTOCOL = "protocol"
    PERFORMANCE = "performance"


class AnomalySeverity(Enum):
    """Anomaly severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyDetection:
    """Anomaly detection result."""

    anomaly_type: AnomalyType
    severity: AnomalySeverity
    peer_id: str
    ip: str
    description: str
    confidence: float  # 0.0 to 1.0
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BehavioralPattern:
    """Behavioral pattern for a peer."""

    peer_id: str
    ip: str
    message_frequency: list[float]  # Messages per minute over time
    bytes_per_message: list[float]  # Average bytes per message
    connection_duration: list[float]  # Connection durations
    error_rate: list[float]  # Error rates over time
    request_patterns: list[str]  # Types of requests made
    last_updated: float


class AnomalyDetector:
    """Anomaly detection system."""

    class _BaselineStats(TypedDict):
        mean: float
        std: float
        count: int

    class _Stats(TypedDict):
        total_anomalies: int
        anomalies_by_type: dict[str, int]
        anomalies_by_severity: dict[str, int]
        false_positives: int
        true_positives: int

    def __init__(self):
        """Initialize anomaly detector."""
        self.behavioral_patterns: dict[str, BehavioralPattern] = {}
        # peer_id -> metric_name -> baseline stats
        self.statistical_baselines: dict[
            str, dict[str, AnomalyDetector._BaselineStats]
        ] = defaultdict(dict)
        self.anomaly_history: deque = deque(maxlen=10000)

        # Detection thresholds
        self.thresholds = {
            "statistical_z_score": 3.0,  # Z-score threshold
            "behavioral_deviation": 0.5,  # Behavioral deviation threshold
            "network_anomaly_rate": 0.1,  # Network anomaly rate threshold
            "protocol_violation_rate": 0.05,  # Protocol violation rate threshold
            "performance_degradation": 0.3,  # Performance degradation threshold
        }

        # Statistical analysis parameters
        self.statistical_window = 3600  # 1 hour window for statistical analysis
        self.behavioral_window = 1800  # 30 minutes window for behavioral analysis

        # Machine learning features
        self.feature_vectors: dict[str, list[float]] = defaultdict(list)
        self.cluster_centers: dict[str, list[float]] = {}

        # Anomaly statistics
        self.stats: AnomalyDetector._Stats = {
            "total_anomalies": 0,
            "anomalies_by_type": {},
            "anomalies_by_severity": {},
            "false_positives": 0,
            "true_positives": 0,
        }

    async def detect_anomalies(
        self,
        peer_id: str,
        ip: str,
        data: dict[str, Any],
    ) -> list[AnomalyDetection]:
        """Detect anomalies for a peer.

        Args:
            peer_id: Peer identifier
            ip: Peer IP address
            data: Peer activity data

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Update behavioral pattern
        await self._update_behavioral_pattern(peer_id, ip, data)

        # Statistical anomaly detection
        statistical_anomalies = await self._detect_statistical_anomalies(
            peer_id,
            ip,
            data,
        )
        anomalies.extend(statistical_anomalies)

        # Behavioral anomaly detection
        behavioral_anomalies = await self._detect_behavioral_anomalies(
            peer_id,
            ip,
            data,
        )
        anomalies.extend(behavioral_anomalies)

        # Network anomaly detection
        network_anomalies = await self._detect_network_anomalies(peer_id, ip, data)
        anomalies.extend(network_anomalies)

        # Protocol anomaly detection
        protocol_anomalies = await self._detect_protocol_anomalies(peer_id, ip, data)
        anomalies.extend(protocol_anomalies)

        # Performance anomaly detection
        performance_anomalies = await self._detect_performance_anomalies(
            peer_id,
            ip,
            data,
        )
        anomalies.extend(performance_anomalies)

        # Record anomalies
        for anomaly in anomalies:
            self.anomaly_history.append(anomaly)
            self.stats["total_anomalies"] += 1
            # Update type/severity counters using setdefault to avoid defaultdict typing issues
            self.stats["anomalies_by_type"][anomaly.anomaly_type.value] = (
                self.stats["anomalies_by_type"].setdefault(
                    anomaly.anomaly_type.value, 0
                )
                + 1
            )
            self.stats["anomalies_by_severity"][anomaly.severity.value] = (
                self.stats["anomalies_by_severity"].setdefault(
                    anomaly.severity.value, 0
                )
                + 1
            )

            # Emit anomaly event
            await emit_event(
                Event(
                    event_type=EventType.ANOMALY_DETECTED.value,
                    data={
                        "anomaly_type": anomaly.anomaly_type.value,
                        "severity": anomaly.severity.value,
                        "peer_id": peer_id,
                        "ip": ip,
                        "description": anomaly.description,
                        "confidence": anomaly.confidence,
                        "metadata": anomaly.metadata,
                        "timestamp": time.time(),
                    },
                ),
            )

        return anomalies

    async def _detect_statistical_anomalies(
        self,
        peer_id: str,
        ip: str,
        data: dict[str, Any],
    ) -> list[AnomalyDetection]:
        """Detect statistical anomalies."""
        anomalies = []

        # Get current metrics
        current_metrics = {
            "message_count": data.get("message_count", 0),
            "bytes_sent": data.get("bytes_sent", 0),
            "bytes_received": data.get("bytes_received", 0),
            "error_count": data.get("error_count", 0),
            "connection_time": data.get("connection_time", 0),
        }

        # Check each metric for statistical anomalies
        for metric_name, current_value in current_metrics.items():
            if metric_name not in self.statistical_baselines[peer_id]:
                # Initialize baseline
                self.statistical_baselines[peer_id][metric_name] = {
                    "mean": current_value,
                    "std": 0.0,
                    "count": 1,
                }
                continue

            baseline = self.statistical_baselines[peer_id][metric_name]

            # Calculate Z-score
            if baseline["std"] > 0:
                z_score = abs(current_value - baseline["mean"]) / baseline["std"]

                if z_score > self.thresholds["statistical_z_score"]:
                    severity = self._determine_severity(z_score)

                    anomaly = AnomalyDetection(
                        anomaly_type=AnomalyType.STATISTICAL,
                        severity=severity,
                        peer_id=peer_id,
                        ip=ip,
                        description=f"Statistical anomaly in {metric_name}: z-score={z_score:.2f}",
                        confidence=min(
                            1.0,
                            z_score / self.thresholds["statistical_z_score"],
                        ),
                        timestamp=time.time(),
                        metadata={
                            "metric": metric_name,
                            "value": current_value,
                            "z_score": z_score,
                            "baseline_mean": baseline["mean"],
                            "baseline_std": baseline["std"],
                        },
                    )
                    anomalies.append(anomaly)

            # Update baseline
            self._update_statistical_baseline(peer_id, metric_name, current_value)

        return anomalies

    async def _detect_behavioral_anomalies(
        self,
        peer_id: str,
        ip: str,
        data: dict[str, Any],
    ) -> list[AnomalyDetection]:
        """Detect behavioral anomalies."""
        anomalies = []

        if peer_id not in self.behavioral_patterns:
            return anomalies

        pattern = self.behavioral_patterns[peer_id]

        # Check message frequency anomaly
        current_frequency = data.get("message_frequency", 0)
        if pattern.message_frequency:
            avg_frequency = statistics.mean(pattern.message_frequency)
            if avg_frequency > 0:
                frequency_deviation = (
                    abs(current_frequency - avg_frequency) / avg_frequency
                )

                if frequency_deviation > self.thresholds["behavioral_deviation"]:
                    severity = self._determine_severity(frequency_deviation)

                    anomaly = AnomalyDetection(
                        anomaly_type=AnomalyType.BEHAVIORAL,
                        severity=severity,
                        peer_id=peer_id,
                        ip=ip,
                        description=f"Behavioral anomaly: message frequency deviation={frequency_deviation:.2f}",
                        confidence=min(
                            1.0,
                            frequency_deviation
                            / self.thresholds["behavioral_deviation"],
                        ),
                        timestamp=time.time(),
                        metadata={
                            "metric": "message_frequency",
                            "current_value": current_frequency,
                            "expected_value": avg_frequency,
                            "deviation": frequency_deviation,
                        },
                    )
                    anomalies.append(anomaly)

        # Check bytes per message anomaly
        current_bytes_per_message = data.get("bytes_per_message", 0)
        if pattern.bytes_per_message:
            avg_bytes_per_message = statistics.mean(pattern.bytes_per_message)
            if avg_bytes_per_message > 0:
                bytes_deviation = (
                    abs(current_bytes_per_message - avg_bytes_per_message)
                    / avg_bytes_per_message
                )

                if bytes_deviation > self.thresholds["behavioral_deviation"]:
                    severity = self._determine_severity(bytes_deviation)

                    anomaly = AnomalyDetection(
                        anomaly_type=AnomalyType.BEHAVIORAL,
                        severity=severity,
                        peer_id=peer_id,
                        ip=ip,
                        description=f"Behavioral anomaly: bytes per message deviation={bytes_deviation:.2f}",
                        confidence=min(
                            1.0,
                            bytes_deviation / self.thresholds["behavioral_deviation"],
                        ),
                        timestamp=time.time(),
                        metadata={
                            "metric": "bytes_per_message",
                            "current_value": current_bytes_per_message,
                            "expected_value": avg_bytes_per_message,
                            "deviation": bytes_deviation,
                        },
                    )
                    anomalies.append(anomaly)

        return anomalies

    async def _detect_network_anomalies(
        self,
        peer_id: str,
        ip: str,
        data: dict[str, Any],
    ) -> list[AnomalyDetection]:
        """Detect network anomalies."""
        anomalies = []

        # Check for unusual network patterns
        connection_time = data.get("connection_time", 0)
        bytes_sent = data.get("bytes_sent", 0)
        bytes_received = data.get("bytes_received", 0)

        # Check for asymmetric traffic (potential attack)
        if bytes_sent > 0 and bytes_received > 0:
            traffic_ratio = max(bytes_sent, bytes_received) / min(
                bytes_sent,
                bytes_received,
            )
            if traffic_ratio > 10:  # 10:1 ratio is suspicious
                severity = (
                    AnomalySeverity.MEDIUM
                    if traffic_ratio < 50
                    else AnomalySeverity.HIGH
                )

                anomaly = AnomalyDetection(
                    anomaly_type=AnomalyType.NETWORK,
                    severity=severity,
                    peer_id=peer_id,
                    ip=ip,
                    description=f"Network anomaly: asymmetric traffic ratio={traffic_ratio:.2f}",
                    confidence=min(1.0, traffic_ratio / 100),
                    timestamp=time.time(),
                    metadata={
                        "bytes_sent": bytes_sent,
                        "bytes_received": bytes_received,
                        "traffic_ratio": traffic_ratio,
                    },
                )
                anomalies.append(anomaly)

        # Check for unusually short connections (potential scanning)
        if connection_time > 0 and connection_time < 5:  # Less than 5 seconds
            anomaly = AnomalyDetection(
                anomaly_type=AnomalyType.NETWORK,
                severity=AnomalySeverity.LOW,
                peer_id=peer_id,
                ip=ip,
                description=f"Network anomaly: unusually short connection={connection_time:.2f}s",
                confidence=0.7,
                timestamp=time.time(),
                metadata={
                    "connection_time": connection_time,
                },
            )
            anomalies.append(anomaly)

        return anomalies

    async def _detect_protocol_anomalies(
        self,
        peer_id: str,
        ip: str,
        data: dict[str, Any],
    ) -> list[AnomalyDetection]:
        """Detect protocol anomalies."""
        anomalies = []

        # Check for protocol violations
        error_count = data.get("error_count", 0)
        message_count = data.get("message_count", 0)

        if message_count > 0:
            error_rate = error_count / message_count

            if error_rate > self.thresholds["protocol_violation_rate"]:
                severity = self._determine_severity(
                    error_rate / self.thresholds["protocol_violation_rate"],
                )

                anomaly = AnomalyDetection(
                    anomaly_type=AnomalyType.PROTOCOL,
                    severity=severity,
                    peer_id=peer_id,
                    ip=ip,
                    description=f"Protocol anomaly: high error rate={error_rate:.2f}",
                    confidence=min(
                        1.0,
                        error_rate / self.thresholds["protocol_violation_rate"],
                    ),
                    timestamp=time.time(),
                    metadata={
                        "error_count": error_count,
                        "message_count": message_count,
                        "error_rate": error_rate,
                    },
                )
                anomalies.append(anomaly)

        return anomalies

    async def _detect_performance_anomalies(
        self,
        peer_id: str,
        ip: str,
        data: dict[str, Any],
    ) -> list[AnomalyDetection]:
        """Detect performance anomalies."""
        anomalies = []

        # Check for performance degradation
        connection_quality = data.get("connection_quality", 1.0)

        if connection_quality < (1.0 - self.thresholds["performance_degradation"]):
            severity = self._determine_severity(
                (1.0 - connection_quality) / self.thresholds["performance_degradation"],
            )

            anomaly = AnomalyDetection(
                anomaly_type=AnomalyType.PERFORMANCE,
                severity=severity,
                peer_id=peer_id,
                ip=ip,
                description=f"Performance anomaly: low connection quality={connection_quality:.2f}",
                confidence=min(
                    1.0,
                    (1.0 - connection_quality)
                    / self.thresholds["performance_degradation"],
                ),
                timestamp=time.time(),
                metadata={
                    "connection_quality": connection_quality,
                },
            )
            anomalies.append(anomaly)

        return anomalies

    async def _update_behavioral_pattern(
        self,
        peer_id: str,
        ip: str,
        data: dict[str, Any],
    ) -> None:
        """Update behavioral pattern for a peer."""
        if peer_id not in self.behavioral_patterns:
            self.behavioral_patterns[peer_id] = BehavioralPattern(
                peer_id=peer_id,
                ip=ip,
                message_frequency=[],
                bytes_per_message=[],
                connection_duration=[],
                error_rate=[],
                request_patterns=[],
                last_updated=time.time(),
            )

        pattern = self.behavioral_patterns[peer_id]
        current_time = time.time()

        # Update message frequency
        if "message_frequency" in data:
            pattern.message_frequency.append(data["message_frequency"])
            # Keep only recent data
            if len(pattern.message_frequency) > 100:
                pattern.message_frequency = pattern.message_frequency[-100:]

        # Update bytes per message
        if "bytes_per_message" in data:
            pattern.bytes_per_message.append(data["bytes_per_message"])
            if len(pattern.bytes_per_message) > 100:
                pattern.bytes_per_message = pattern.bytes_per_message[-100:]

        # Update connection duration
        if "connection_duration" in data:
            pattern.connection_duration.append(data["connection_duration"])
            if len(pattern.connection_duration) > 50:
                pattern.connection_duration = pattern.connection_duration[-50:]

        # Update error rate
        if "error_rate" in data:
            pattern.error_rate.append(data["error_rate"])
            if len(pattern.error_rate) > 100:
                pattern.error_rate = pattern.error_rate[-100:]

        # Update request patterns
        if "request_type" in data:
            pattern.request_patterns.append(data["request_type"])
            if len(pattern.request_patterns) > 1000:
                pattern.request_patterns = pattern.request_patterns[-1000:]

        pattern.last_updated = current_time

    def _update_statistical_baseline(
        self,
        peer_id: str,
        metric_name: str,
        value: float,
    ) -> None:
        """Update statistical baseline for a metric."""
        if metric_name not in self.statistical_baselines[peer_id]:
            self.statistical_baselines[peer_id][metric_name] = {
                "mean": value,
                "std": 0.0,
                "count": 1,
            }
            return

        baseline = self.statistical_baselines[peer_id][metric_name]

        # Update mean using incremental formula
        new_count = baseline["count"] + 1
        new_mean = (baseline["mean"] * baseline["count"] + value) / new_count

        # Update standard deviation using Welford's algorithm
        if baseline["count"] > 0:
            delta = value - baseline["mean"]
            delta2 = value - new_mean
            new_std = math.sqrt(
                (baseline["std"] ** 2 * baseline["count"] + delta * delta2) / new_count,
            )
        else:
            new_std = 0.0

        baseline["mean"] = new_mean
        baseline["std"] = new_std
        baseline["count"] = new_count

    def _determine_severity(self, deviation: float) -> AnomalySeverity:
        """Determine anomaly severity based on deviation."""
        if deviation < 2.0:
            return AnomalySeverity.LOW
        if deviation < 5.0:
            return AnomalySeverity.MEDIUM
        if deviation < 10.0:
            return AnomalySeverity.HIGH
        return AnomalySeverity.CRITICAL

    def get_anomaly_history(self, limit: int = 100) -> list[AnomalyDetection]:
        """Get recent anomaly history."""
        return list(self.anomaly_history)[-limit:]

    def get_anomaly_statistics(self) -> dict[str, Any]:
        """Get anomaly detection statistics."""
        return {
            "total_anomalies": self.stats["total_anomalies"],
            "anomalies_by_type": dict(self.stats["anomalies_by_type"]),
            "anomalies_by_severity": dict(self.stats["anomalies_by_severity"]),
            "false_positives": self.stats["false_positives"],
            "true_positives": self.stats["true_positives"],
            "detection_rate": self.stats["true_positives"]
            / max(1, self.stats["total_anomalies"]),
            "false_positive_rate": self.stats["false_positives"]
            / max(1, self.stats["total_anomalies"]),
        }

    def get_behavioral_pattern(self, peer_id: str) -> BehavioralPattern | None:
        """Get behavioral pattern for a peer."""
        return self.behavioral_patterns.get(peer_id)

    def get_statistical_baseline(
        self,
        peer_id: str,
        metric_name: str,
    ) -> dict[str, float] | None:
        """Get statistical baseline for a peer metric."""
        return self.statistical_baselines.get(peer_id, {}).get(metric_name)

    def cleanup_old_data(self, max_age_seconds: int = 3600) -> None:
        """Clean up old anomaly detection data."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        # Clean up behavioral patterns
        to_remove = []
        for peer_id, pattern in self.behavioral_patterns.items():
            if pattern.last_updated < cutoff_time:
                to_remove.append(peer_id)

        for peer_id in to_remove:
            del self.behavioral_patterns[peer_id]

        # Clean up statistical baselines
        for peer_id in list(self.statistical_baselines.keys()):
            if peer_id not in self.behavioral_patterns:
                del self.statistical_baselines[peer_id]

        # Clean up anomaly history
        while self.anomaly_history and self.anomaly_history[0].timestamp < cutoff_time:
            self.anomaly_history.popleft()

    def report_false_positive(self, _anomaly_id: str) -> None:
        """Report a false positive for learning."""
        self.stats["false_positives"] += 1

    def report_true_positive(self, _anomaly_id: str) -> None:
        """Report a true positive for learning."""
        self.stats["true_positives"] += 1
