"""Adaptive timeout calculator for DHT queries and peer handshakes.

Health for handshake/DHT adaptive timeouts uses effective peer count:
``max(transport_live_count, active_post_handshake_count)`` when the peer manager exposes
:class:`ccbt.models.SwarmTimeoutSignals`, unless ``network.adaptive_timeout_health_peer_source``
is ``active_only`` (legacy: post-handshake active peers only). ``requestable_count`` is logged
for diagnostics only and does not drive the health band.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from ccbt.models import AdaptiveTimeoutHealthPeerSource, SwarmTimeoutSignals
from ccbt.utils.shutdown import is_shutting_down

logger = logging.getLogger(__name__)

_SHUTDOWN_DHT_QUERY_CAP_S = 1.0


class AdaptiveTimeoutCalculator:
    """Calculates adaptive timeouts based on peer health metrics."""

    def __init__(
        self,
        config: Any,
        peer_manager: Optional[Any] = None,
    ) -> None:
        """Initialize adaptive timeout calculator.

        Args:
            config: Configuration object with timeout settings
            peer_manager: Optional peer manager for health tracking

        """
        self.config = config
        self.peer_manager = peer_manager
        self.logger = logging.getLogger(__name__)
        self._last_shutdown_dht_timeout_log_monotonic = 0.0

    def _allow_shutdown_debug_log(self) -> bool:
        """Throttle high-frequency shutdown debug logs."""
        now = time.monotonic()
        if now - self._last_shutdown_dht_timeout_log_monotonic < 10.0:
            return False
        self._last_shutdown_dht_timeout_log_monotonic = now
        return True

    def _health_source_is_active_only(self) -> bool:
        src = getattr(
            self.config.network,
            "adaptive_timeout_health_peer_source",
            AdaptiveTimeoutHealthPeerSource.EFFECTIVE,
        )
        if isinstance(src, AdaptiveTimeoutHealthPeerSource):
            return src == AdaptiveTimeoutHealthPeerSource.ACTIVE_ONLY
        if isinstance(src, str):
            return (
                src.strip().lower() == AdaptiveTimeoutHealthPeerSource.ACTIVE_ONLY.value
            )
        return False

    def _get_timeout_health_signals(self) -> tuple[int, Optional[SwarmTimeoutSignals]]:
        """Return (effective_count_for_health_bands, signals_or_none)."""
        if self.peer_manager is None:
            return 0, None

        try:
            if hasattr(self.peer_manager, "get_swarm_timeout_signals"):
                raw = self.peer_manager.get_swarm_timeout_signals()
                if not isinstance(raw, SwarmTimeoutSignals):
                    return 0, None
                if self._health_source_is_active_only():
                    effective = raw.active_post_handshake_count
                else:
                    effective = max(
                        raw.transport_live_count,
                        raw.active_post_handshake_count,
                    )
                return effective, raw

            if hasattr(self.peer_manager, "get_active_peers"):
                active_peers = self.peer_manager.get_active_peers()
                if active_peers is not None:
                    return len(active_peers), None

            if hasattr(self.peer_manager, "connections"):
                connections = self.peer_manager.connections
                if hasattr(connections, "values"):
                    from ccbt.peer.async_peer_connection import ConnectionState

                    n = sum(
                        1
                        for conn in connections.values()
                        if hasattr(conn, "state")
                        and conn.state != ConnectionState.DISCONNECTED
                        and hasattr(conn, "reader")
                        and conn.reader is not None
                        and hasattr(conn, "writer")
                        and conn.writer is not None
                    )
                    return n, None
        except Exception as e:
            self.logger.debug("Failed to get peer health for adaptive timeouts: %s", e)

        return 0, None

    def _get_peer_health_mode(self, effective_peer_count: int) -> str:
        """Determine peer health mode based on effective peer count.

        Args:
            effective_peer_count: Peers after configured health source policy

        Returns:
            Mode string: "desperation", "normal", or "healthy"

        """
        desperation_max = int(
            getattr(self.config.network, "adaptive_timeout_desperation_max_peers", 5),
        )
        normal_max = int(
            getattr(self.config.network, "adaptive_timeout_normal_max_peers", 20),
        )
        if effective_peer_count < desperation_max:
            return "desperation"
        if effective_peer_count < normal_max:
            return "normal"
        return "healthy"

    def _normal_mode_peer_ratio(
        self,
        effective_peer_count: int,
    ) -> float:
        desperation_max = int(
            getattr(self.config.network, "adaptive_timeout_desperation_max_peers", 5),
        )
        normal_max = int(
            getattr(self.config.network, "adaptive_timeout_normal_max_peers", 20),
        )
        span = max(1, normal_max - desperation_max)
        ratio = (effective_peer_count - desperation_max) / float(span)
        return max(0.0, min(1.0, ratio))

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
            base = self.config.network.dht_timeout
            if is_shutting_down():
                return min(float(base), _SHUTDOWN_DHT_QUERY_CAP_S)
            return base

        effective_count, signals = self._get_timeout_health_signals()
        mode = self._get_peer_health_mode(effective_count)

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
            peer_ratio = self._normal_mode_peer_ratio(effective_count)
            timeout = min_timeout + (max_timeout - min_timeout) * peer_ratio
        else:  # healthy
            # Use longer timeout for healthy swarms
            timeout = max_timeout

        # Clamp to config bounds
        timeout = max(min_timeout, min(max_timeout, timeout))

        emit_debug = True
        if is_shutting_down():
            emit_debug = self._allow_shutdown_debug_log()

        if signals is not None and emit_debug:
            self.logger.debug(
                "DHT timeout calculated: %.1fs (mode=%s, transport_live=%d "
                "active_post_handshake=%d requestable=%d effective=%d)",
                timeout,
                mode,
                signals.transport_live_count,
                signals.active_post_handshake_count,
                signals.requestable_count,
                effective_count,
            )
        elif emit_debug:
            self.logger.debug(
                "DHT timeout calculated: %.1fs (mode=%s, effective=%d, no swarm signals)",
                timeout,
                mode,
                effective_count,
            )

        if is_shutting_down():
            return min(float(timeout), _SHUTDOWN_DHT_QUERY_CAP_S)
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

        effective_count, signals = self._get_timeout_health_signals()
        mode = self._get_peer_health_mode(effective_count)

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
            # Note: Reduced from 60s to 20s max - 60s was causing connections to hang
            # 20s is sufficient for slow peers/NAT traversal without blocking batch processing
            # BitTorrent spec recommends 10-30s for handshake timeouts
            timeout = max(
                min_timeout, max_timeout
            )  # Use configured values, ensure at least min_timeout
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
            peer_ratio = self._normal_mode_peer_ratio(effective_count)
            timeout = min_timeout + (max_timeout - min_timeout) * peer_ratio
        else:  # healthy
            # Use longer timeout for healthy swarms
            timeout = max_timeout

        # Clamp to config bounds
        timeout = max(min_timeout, min(max_timeout, timeout))

        # Note: Log at INFO level in desperation mode to help diagnose handshake issues
        if signals is not None:
            if mode == "desperation":
                self.logger.info(
                    "Handshake timeout calculated: %.1fs (mode=%s, transport_live=%d "
                    "active_post_handshake=%d requestable=%d effective=%d) - using longer "
                    "timeout for better connection success",
                    timeout,
                    mode,
                    signals.transport_live_count,
                    signals.active_post_handshake_count,
                    signals.requestable_count,
                    effective_count,
                )
            else:
                self.logger.debug(
                    "Handshake timeout calculated: %.1fs (mode=%s, transport_live=%d "
                    "active_post_handshake=%d requestable=%d effective=%d)",
                    timeout,
                    mode,
                    signals.transport_live_count,
                    signals.active_post_handshake_count,
                    signals.requestable_count,
                    effective_count,
                )
        elif mode == "desperation":
            self.logger.info(
                "Handshake timeout calculated: %.1fs (mode=%s, effective=%d, no swarm "
                "signals - using longer timeout for better connection success",
                timeout,
                mode,
                effective_count,
            )
        else:
            self.logger.debug(
                "Handshake timeout calculated: %.1fs (mode=%s, effective=%d, no swarm signals)",
                timeout,
                mode,
                effective_count,
            )

        return timeout
