"""Adaptive timeout calculator for DHT queries and peer handshakes.

This module provides adaptive timeout calculation based on peer health metrics,
allowing longer timeouts in desperation mode (few peers) and adjusting timeouts
based on swarm health.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AdaptiveTimeoutCalculator:
    """Calculates adaptive timeouts based on peer health metrics."""

    def __init__(
        self,
        config: Any,
        peer_manager: Any | None = None,
    ) -> None:
        """Initialize adaptive timeout calculator.

        Args:
            config: Configuration object with timeout settings
            peer_manager: Optional peer manager for health tracking
        """
        self.config = config
        self.peer_manager = peer_manager
        self.logger = logging.getLogger(__name__)

    def _get_active_peer_count(self) -> int:
        """Get current active peer count.

        Returns:
            Number of active peers, or 0 if unavailable
        """
        if self.peer_manager is None:
            return 0

        try:
            if hasattr(self.peer_manager, "get_active_peers"):
                active_peers = self.peer_manager.get_active_peers()
                if active_peers is not None:
                    return len(active_peers)
            elif hasattr(self.peer_manager, "connections"):
                # Fallback: count connections that are not disconnected
                connections = self.peer_manager.connections
                if hasattr(connections, "values"):
                    from ccbt.peer.async_peer_connection import ConnectionState

                    return sum(
                        1
                        for conn in connections.values()
                        if hasattr(conn, "state")
                        and conn.state != ConnectionState.DISCONNECTED
                        and hasattr(conn, "reader")
                        and conn.reader is not None
                        and hasattr(conn, "writer")
                        and conn.writer is not None
                    )
        except Exception as e:
            self.logger.debug("Failed to get active peer count: %s", e)

        return 0

    def _get_peer_health_mode(self, active_peer_count: int) -> str:
        """Determine peer health mode based on active peer count.

        Args:
            active_peer_count: Number of active peers

        Returns:
            Mode string: "desperation", "normal", or "healthy"
        """
        if active_peer_count < 5:
            return "desperation"
        elif active_peer_count < 20:
            return "normal"
        else:
            return "healthy"

    def calculate_dht_timeout(self) -> float:
        """Calculate adaptive DHT query timeout based on peer health.

        Returns:
            Timeout in seconds
        """
        # Check if adaptive timeouts are enabled
        if not getattr(
            self.config.discovery,
            "dht_adaptive_timeout_enabled",
            False,
        ):
            # Use base timeout from config
            return self.config.network.dht_timeout

        active_peer_count = self._get_active_peer_count()
        mode = self._get_peer_health_mode(active_peer_count)

        # Get timeout range for current mode
        if mode == "desperation":
            min_timeout = getattr(
                self.config.discovery,
                "dht_timeout_desperation_min",
                30.0,
            )
            max_timeout = getattr(
                self.config.discovery,
                "dht_timeout_desperation_max",
                60.0,
            )
        elif mode == "normal":
            min_timeout = getattr(
                self.config.discovery,
                "dht_timeout_normal_min",
                5.0,
            )
            max_timeout = getattr(
                self.config.discovery,
                "dht_timeout_normal_max",
                15.0,
            )
        else:  # healthy
            min_timeout = getattr(
                self.config.discovery,
                "dht_timeout_healthy_min",
                10.0,
            )
            max_timeout = getattr(
                self.config.discovery,
                "dht_timeout_healthy_max",
                30.0,
            )

        # Use max timeout in desperation mode, scale for others
        if mode == "desperation":
            timeout = max_timeout
        elif mode == "normal":
            # Scale based on peer count (more peers = slightly longer timeout)
            # Linear interpolation between min and max based on peer count (5-20 range)
            peer_ratio = (active_peer_count - 5) / 15.0  # 0.0 at 5 peers, 1.0 at 20 peers
            timeout = min_timeout + (max_timeout - min_timeout) * peer_ratio
        else:  # healthy
            # Use longer timeout for healthy swarms
            timeout = max_timeout

        # Clamp to config bounds
        timeout = max(min_timeout, min(max_timeout, timeout))

        self.logger.debug(
            "DHT timeout calculated: %.1fs (mode=%s, active_peers=%d)",
            timeout,
            mode,
            active_peer_count,
        )

        return timeout

    def calculate_handshake_timeout(self) -> float:
        """Calculate adaptive handshake timeout based on peer health.

        Returns:
            Timeout in seconds
        """
        # Check if adaptive timeouts are enabled
        if not getattr(
            self.config.network,
            "handshake_adaptive_timeout_enabled",
            False,
        ):
            # Use base timeout from config, but ensure minimum 15.0s for better peer acceptance
            return max(15.0, self.config.network.handshake_timeout)

        active_peer_count = self._get_active_peer_count()
        mode = self._get_peer_health_mode(active_peer_count)

        # Get timeout range for current mode
        if mode == "desperation":
            min_timeout = getattr(
                self.config.network,
                "handshake_timeout_desperation_min",
                10.0,
            )
            max_timeout = getattr(
                self.config.network,
                "handshake_timeout_desperation_max",
                20.0,  # CRITICAL: Default to 20.0, not 60.0 - config should override if needed
            )
            # CRITICAL FIX: Reduced from 60s to 20s max - 60s was causing connections to hang
            # 20s is sufficient for slow peers/NAT traversal without blocking batch processing
            # BitTorrent spec recommends 10-30s for handshake timeouts
            timeout = max(min_timeout, max_timeout)  # Use configured values, ensure at least min_timeout
        elif mode == "normal":
            min_timeout = getattr(
                self.config.network,
                "handshake_timeout_normal_min",
                15.0,
            )
            max_timeout = getattr(
                self.config.network,
                "handshake_timeout_normal_max",
                30.0,
            )
        else:  # healthy
            min_timeout = getattr(
                self.config.network,
                "handshake_timeout_healthy_min",
                20.0,
            )
            max_timeout = getattr(
                self.config.network,
                "handshake_timeout_healthy_max",
                40.0,
            )

        # Use max timeout in desperation mode, scale for others
        if mode == "desperation":
            timeout = max_timeout
        elif mode == "normal":
            # Scale based on peer count (more peers = slightly longer timeout)
            # Linear interpolation between min and max based on peer count (5-20 range)
            peer_ratio = (active_peer_count - 5) / 15.0  # 0.0 at 5 peers, 1.0 at 20 peers
            timeout = min_timeout + (max_timeout - min_timeout) * peer_ratio
        else:  # healthy
            # Use longer timeout for healthy swarms
            timeout = max_timeout

        # Clamp to config bounds
        timeout = max(min_timeout, min(max_timeout, timeout))

        # CRITICAL FIX: Log at INFO level in desperation mode to help diagnose handshake issues
        if mode == "desperation":
            self.logger.info(
                "Handshake timeout calculated: %.1fs (mode=%s, active_peers=%d) - using longer timeout for better connection success",
                timeout,
                mode,
                active_peer_count,
            )
        else:
            self.logger.debug(
                "Handshake timeout calculated: %.1fs (mode=%s, active_peers=%d)",
                timeout,
                mode,
                active_peer_count,
            )

        return timeout


