"""Local Metric-Based Blacklist Source for ccBitTorrent.

from __future__ import annotations

Provides automatic blacklisting based on locally observed peer metrics.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from ccbt.security.security_manager import SecurityManager

logger = logging.getLogger(__name__)


@dataclass
class PeerMetricEntry:
    """Single metric entry for a peer."""

    ip: str
    metric_type: str  # "handshake_failure", "spam", "violation", "connection_attempt"
    value: float
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PeerMetricsSummary:
    """Aggregated metrics for a peer over time window."""

    ip: str
    failed_handshakes: int = 0
    total_connection_attempts: int = 0
    connection_success_rate: float = 0.0
    spam_score: float = 0.0
    violation_count: int = 0
    reputation_score: float = 1.0
    last_seen: float = 0.0
    first_seen: float = 0.0


class LocalBlacklistSource:
    """Local metric-based blacklist source.

    Tracks peer behavior metrics and automatically blacklists
    IPs that exceed configured thresholds.
    """

    def __init__(
        self,
        security_manager: SecurityManager,
        evaluation_interval: float = 300.0,  # 5 minutes
        metric_window: float = 3600.0,  # 1 hour
        thresholds: dict[str, Any] | None = None,
        expiration_hours: float | None = 24.0,
        min_observations: int = 3,
    ):
        """Initialize local blacklist source.

        Args:
            security_manager: SecurityManager instance
            evaluation_interval: How often to evaluate metrics (seconds)
            metric_window: Time window for metric aggregation (seconds)
            thresholds: Threshold configuration dict
            expiration_hours: Expiration time for auto-blacklisted IPs (hours, None = permanent)
            min_observations: Minimum observations before blacklisting

        """
        self.security_manager = security_manager
        self.evaluation_interval = evaluation_interval
        self.metric_window = metric_window
        self.expiration_hours = expiration_hours
        self.min_observations = min_observations

        # Default thresholds
        self.thresholds = {
            "failed_handshakes": 5,  # Blacklist after 5 failed handshakes
            "handshake_failure_rate": 0.8,  # 80% failure rate
            "spam_score": 10.0,  # Spam score threshold
            "violation_count": 3,  # 3 protocol violations
            "reputation_threshold": 0.2,  # Reputation below 0.2
            "connection_attempt_rate": 20,  # 20 attempts per minute
        }
        if thresholds:
            self.thresholds.update(thresholds)

        # Metric storage (bounded deque to prevent memory issues)
        self.metric_entries: deque[PeerMetricEntry] = deque(maxlen=100000)

        # Background task
        self._evaluation_task: asyncio.Task | None = None
        self._running = False

    async def start_evaluation(self) -> None:
        """Start periodic evaluation task."""
        if self._evaluation_task and not self._evaluation_task.done():
            logger.warning("Local blacklist evaluation task already running")
            return

        self._running = True

        async def evaluation_loop():
            while self._running:
                try:
                    await asyncio.sleep(self.evaluation_interval)
                    logger.debug("Starting local blacklist evaluation...")
                    blacklisted_count = await self.evaluate_metrics()
                    if blacklisted_count > 0:
                        logger.info(
                            "Local blacklist evaluation: %d IPs blacklisted",
                            blacklisted_count,
                        )
                        # Save blacklist after evaluation
                        try:
                            await self.security_manager.save_blacklist()
                        except Exception as e:
                            logger.warning(
                                "Failed to save blacklist after local evaluation: %s", e
                            )
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Error in local blacklist evaluation")
                    await asyncio.sleep(60)  # Retry after 1 minute

        self._evaluation_task = asyncio.create_task(evaluation_loop())
        logger.info(
            "Started local blacklist evaluation (interval: %ss, window: %ss)",
            self.evaluation_interval,
            self.metric_window,
        )

    def stop_evaluation(self) -> None:
        """Stop evaluation background task."""
        self._running = False
        if self._evaluation_task and not self._evaluation_task.done():
            self._evaluation_task.cancel()
            logger.info("Stopped local blacklist evaluation task")

    async def record_metric(
        self,
        ip: str,
        metric_type: str,
        value: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a metric for an IP.

        Args:
            ip: IP address
            metric_type: Type of metric ("handshake_failure", "spam", "violation", "connection_attempt")
            value: Metric value
            metadata: Additional metadata

        """
        # Validate IP
        if not self._is_valid_ip(ip):
            logger.warning("Invalid IP address in metric record: %s", ip)
            return

        entry = PeerMetricEntry(
            ip=ip,
            metric_type=metric_type,
            value=value,
            timestamp=time.time(),
            metadata=metadata or {},
        )

        self.metric_entries.append(entry)

    async def evaluate_metrics(self) -> int:
        """Evaluate metrics and blacklist IPs that exceed thresholds.

        Returns:
            Number of IPs blacklisted

        """
        current_time = time.time()
        cutoff_time = current_time - self.metric_window

        # Aggregate metrics per IP
        ip_metrics: dict[str, PeerMetricsSummary] = {}

        # Process all metric entries in window
        for entry in self.metric_entries:
            if entry.timestamp < cutoff_time:
                continue  # Outside window

            if entry.ip not in ip_metrics:
                ip_metrics[entry.ip] = PeerMetricsSummary(
                    ip=entry.ip,
                    first_seen=entry.timestamp,
                    last_seen=entry.timestamp,
                )

            summary = ip_metrics[entry.ip]
            summary.last_seen = max(summary.last_seen, entry.timestamp)
            summary.first_seen = min(summary.first_seen, entry.timestamp)

            # Aggregate by metric type
            if entry.metric_type == "handshake_failure":
                summary.failed_handshakes += int(entry.value)
            elif entry.metric_type == "connection_attempt":
                summary.total_connection_attempts += int(entry.value)
            elif entry.metric_type == "connection_success":
                summary.total_connection_attempts += int(entry.value)
            elif entry.metric_type == "spam":
                summary.spam_score += entry.value
            elif entry.metric_type == "violation":
                summary.violation_count += int(entry.value)

        # Get reputation scores from SecurityManager
        for ip, summary in ip_metrics.items():
            # Find peer reputation by IP
            for peer_id, reputation in self.security_manager.peer_reputations.items():
                if reputation.ip == ip:
                    summary.reputation_score = reputation.reputation_score
                    break

            # Calculate connection success rate
            if summary.total_connection_attempts > 0:
                successful = summary.total_connection_attempts - summary.failed_handshakes
                summary.connection_success_rate = (
                    successful / summary.total_connection_attempts
                )

        # Evaluate against thresholds
        blacklisted_count = 0
        for ip, summary in ip_metrics.items():
            if self._should_blacklist(summary):
                expires_in = None
                if self.expiration_hours:
                    expires_in = self.expiration_hours * 3600.0

                reason = self._generate_blacklist_reason(summary)
                self.security_manager.add_to_blacklist(
                    ip,
                    reason,
                    expires_in=expires_in,
                    source="local_metrics",
                )
                blacklisted_count += 1
                logger.info(
                    "Auto-blacklisted IP %s: %s", ip, reason
                )

        # Cleanup old metrics
        self._cleanup_old_metrics(cutoff_time)

        return blacklisted_count

    def _should_blacklist(self, summary: PeerMetricsSummary) -> bool:
        """Check if peer should be blacklisted based on metrics.

        Args:
            summary: Aggregated peer metrics

        Returns:
            True if peer should be blacklisted

        """
        # Skip if already blacklisted
        if self.security_manager.is_ip_blacklisted(summary.ip):
            return False

        # Skip if whitelisted
        if self.security_manager.is_ip_whitelisted(summary.ip):
            return False

        # Check minimum observations
        if summary.total_connection_attempts < self.min_observations:
            return False

        thresholds = self.thresholds

        # Check failed handshakes count
        if summary.failed_handshakes >= thresholds.get("failed_handshakes", 5):
            return True

        # Check handshake failure rate
        if summary.total_connection_attempts > 0:
            failure_rate = summary.failed_handshakes / summary.total_connection_attempts
            if failure_rate >= thresholds.get("handshake_failure_rate", 0.8):
                return True

        # Check spam score
        if summary.spam_score >= thresholds.get("spam_score", 10.0):
            return True

        # Check violation count
        if summary.violation_count >= thresholds.get("violation_count", 3):
            return True

        # Check reputation
        if summary.reputation_score < thresholds.get("reputation_threshold", 0.2):
            return True

        # Check connection attempt rate (spam)
        time_span = summary.last_seen - summary.first_seen
        if time_span > 0:
            attempts_per_minute = (summary.total_connection_attempts / time_span) * 60
            if attempts_per_minute >= thresholds.get("connection_attempt_rate", 20):
                return True

        return False

    def _generate_blacklist_reason(self, summary: PeerMetricsSummary) -> str:
        """Generate human-readable reason for blacklisting.

        Args:
            summary: Aggregated peer metrics

        Returns:
            Reason string

        """
        reasons = []

        if summary.failed_handshakes >= self.thresholds.get("failed_handshakes", 5):
            reasons.append(
                f"{summary.failed_handshakes} failed handshakes"
            )

        if summary.total_connection_attempts > 0:
            failure_rate = summary.failed_handshakes / summary.total_connection_attempts
            if failure_rate >= self.thresholds.get("handshake_failure_rate", 0.8):
                reasons.append(
                    f"{failure_rate:.0%} handshake failure rate"
                )

        if summary.spam_score >= self.thresholds.get("spam_score", 10.0):
            reasons.append(f"spam score {summary.spam_score:.1f}")

        if summary.violation_count >= self.thresholds.get("violation_count", 3):
            reasons.append(f"{summary.violation_count} protocol violations")

        if summary.reputation_score < self.thresholds.get("reputation_threshold", 0.2):
            reasons.append(f"low reputation {summary.reputation_score:.2f}")

        time_span = summary.last_seen - summary.first_seen
        if time_span > 0:
            attempts_per_minute = (summary.total_connection_attempts / time_span) * 60
            if attempts_per_minute >= self.thresholds.get("connection_attempt_rate", 20):
                reasons.append(
                    f"{attempts_per_minute:.1f} connection attempts/min"
                )

        if not reasons:
            return "Multiple threshold violations"

        return "Local metrics: " + ", ".join(reasons)

    def _cleanup_old_metrics(self, cutoff_time: float) -> None:
        """Remove metrics older than cutoff time.

        Args:
            cutoff_time: Timestamp cutoff

        """
        # Since we use a bounded deque, old entries are automatically removed
        # But we can still clean up if needed
        initial_count = len(self.metric_entries)
        # The deque will automatically maintain maxlen, so we just need to
        # ensure we're not keeping too many old entries
        # For efficiency, we'll let the deque handle it naturally

        # Log cleanup if significant
        if initial_count > 10000:
            logger.debug(
                "Metric entries: %d (window: %ds)",
                len(self.metric_entries),
                self.metric_window,
            )

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format.

        Args:
            ip: IP address string to validate

        Returns:
            True if valid IP address

        """
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of current metrics.

        Returns:
            Dictionary with metrics summary

        """
        current_time = time.time()
        cutoff_time = current_time - self.metric_window

        active_entries = [
            entry for entry in self.metric_entries if entry.timestamp >= cutoff_time
        ]

        ip_counts: dict[str, int] = {}
        metric_type_counts: dict[str, int] = {}

        for entry in active_entries:
            ip_counts[entry.ip] = ip_counts.get(entry.ip, 0) + 1
            metric_type_counts[entry.metric_type] = (
                metric_type_counts.get(entry.metric_type, 0) + 1
            )

        return {
            "total_entries": len(active_entries),
            "unique_ips": len(ip_counts),
            "metric_types": metric_type_counts,
            "window_seconds": self.metric_window,
        }








