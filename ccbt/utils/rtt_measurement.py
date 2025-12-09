"""RTT (Round-Trip Time) measurement for network optimization.

This module implements TCP timestamp-based RTT measurement using EWMA
(Exponentially Weighted Moving Average) for adaptive buffer sizing.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

logger = None


def _get_logger() -> Any:
    """Lazy import logger to avoid circular dependencies."""
    global logger
    if logger is None:
        from ccbt.utils.logging_config import get_logger

        logger = get_logger(__name__)
    return logger


class RTTMeasurer:
    """RTT measurement using TCP timestamps and EWMA smoothing.

    Implements Karn's algorithm to handle retransmissions correctly.
    """

    def __init__(
        self,
        alpha: float = 0.125,
        beta: float = 0.25,
        max_samples: int = 100,
    ) -> None:
        """Initialize RTT measurer.

        Args:
            alpha: EWMA smoothing factor for RTT (default 0.125, RFC 6298)
            beta: EWMA smoothing factor for RTT variance (default 0.25, RFC 6298)
            max_samples: Maximum number of samples to keep
        """
        self.alpha = alpha
        self.beta = beta
        self.max_samples = max_samples

        # RTT statistics
        self.rtt: float = 0.0  # Current RTT estimate
        self.rtt_var: float = 0.0  # RTT variance
        self.rto: float = 1.0  # Retransmission timeout

        # Sample history
        self.samples: deque[tuple[float, float]] = deque(
            maxlen=max_samples
        )  # (timestamp, rtt_value)

        # Retransmission tracking (Karn's algorithm)
        self.pending_measurements: dict[int, float] = {}  # seq -> send_time
        self.retransmitted: set[int] = set()  # seq numbers that were retransmitted

        # Statistics
        self.total_samples = 0
        self.retransmission_count = 0

    def record_send(self, sequence: int, timestamp: float | None = None) -> None:
        """Record packet send time for RTT measurement.

        Args:
            sequence: Sequence number or identifier
            timestamp: Send timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()

        self.pending_measurements[sequence] = timestamp

    def record_receive(
        self, sequence: int, timestamp: float | None = None
    ) -> float | None:
        """Record packet receive time and calculate RTT.

        Args:
            sequence: Sequence number or identifier
            timestamp: Receive timestamp (defaults to current time)

        Returns:
            Measured RTT in seconds, or None if measurement invalid
        """
        if timestamp is None:
            timestamp = time.time()

        if sequence not in self.pending_measurements:
            # No matching send record
            return None

        if sequence in self.retransmitted:
            # Karn's algorithm: ignore RTT measurements for retransmitted packets
            del self.pending_measurements[sequence]
            return None

        send_time = self.pending_measurements.pop(sequence)
        rtt_sample = timestamp - send_time

        if rtt_sample <= 0:
            # Invalid measurement
            return None

        # Update RTT estimate using EWMA (RFC 6298)
        if self.rtt == 0.0:
            # First measurement
            self.rtt = rtt_sample
            self.rtt_var = rtt_sample / 2.0
        else:
            # Update RTT estimate
            error = rtt_sample - self.rtt
            self.rtt = self.rtt + self.alpha * error
            self.rtt_var = self.rtt_var + self.beta * (abs(error) - self.rtt_var)

        # Update RTO (Retransmission Timeout)
        self.rto = self.rtt + 4.0 * self.rtt_var

        # Store sample
        self.samples.append((timestamp, rtt_sample))
        self.total_samples += 1

        return rtt_sample

    def mark_retransmission(self, sequence: int) -> None:
        """Mark a sequence as retransmitted (Karn's algorithm).

        Args:
            sequence: Sequence number that was retransmitted
        """
        self.retransmitted.add(sequence)
        self.retransmission_count += 1

        # Clean up old retransmission records (keep last 1000)
        if len(self.retransmitted) > 1000:
            # Remove oldest entries (simple FIFO)
            oldest = list(self.retransmitted)[:100]
            for seq in oldest:
                self.retransmitted.discard(seq)

    def get_rtt(self) -> float:
        """Get current RTT estimate in seconds.

        Returns:
            RTT estimate in seconds
        """
        return self.rtt

    def get_rtt_ms(self) -> float:
        """Get current RTT estimate in milliseconds.

        Returns:
            RTT estimate in milliseconds
        """
        return self.rtt * 1000.0

    def get_rto(self) -> float:
        """Get current retransmission timeout in seconds.

        Returns:
            RTO in seconds
        """
        return self.rto

    def get_stats(self) -> dict[str, Any]:
        """Get RTT measurement statistics.

        Returns:
            Dictionary with RTT statistics
        """
        if not self.samples:
            return {
                "rtt_ms": 0.0,
                "rtt_var_ms": 0.0,
                "rto_ms": 0.0,
                "total_samples": 0,
                "retransmission_count": 0,
                "min_rtt_ms": 0.0,
                "max_rtt_ms": 0.0,
                "avg_rtt_ms": 0.0,
            }

        rtt_values = [sample[1] for sample in self.samples]

        return {
            "rtt_ms": self.rtt * 1000.0,
            "rtt_var_ms": self.rtt_var * 1000.0,
            "rto_ms": self.rto * 1000.0,
            "total_samples": self.total_samples,
            "retransmission_count": self.retransmission_count,
            "min_rtt_ms": min(rtt_values) * 1000.0,
            "max_rtt_ms": max(rtt_values) * 1000.0,
            "avg_rtt_ms": sum(rtt_values) / len(rtt_values) * 1000.0,
        }

    def reset(self) -> None:
        """Reset RTT measurement state."""
        self.rtt = 0.0
        self.rtt_var = 0.0
        self.rto = 1.0
        self.samples.clear()
        self.pending_measurements.clear()
        self.retransmitted.clear()
        self.total_samples = 0
        self.retransmission_count = 0







































