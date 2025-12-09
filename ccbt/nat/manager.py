"""Unified NAT traversal manager."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from ccbt.nat.exceptions import NATPMPError, UPnPError
from ccbt.nat.natpmp import NATPMPClient
from ccbt.nat.port_mapping import PortMapping, PortMappingManager
from ccbt.nat.upnp import UPnPClient

if TYPE_CHECKING:  # pragma: no cover
    import ipaddress  # TYPE_CHECKING imports never execute at runtime

logger = logging.getLogger(__name__)


class NATManager:
    """Unified NAT traversal manager supporting NAT-PMP and UPnP."""

    def __init__(self, config) -> None:
        """Initialize NAT manager.

        Args:
            config: Configuration object with nat settings

        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        self.natpmp_client: NATPMPClient | None = None
        self.upnp_client: UPnPClient | None = None
        # Pass renewal callback to port mapping manager
        self.port_mapping_manager = PortMappingManager(
            renewal_callback=self._renew_mapping_callback
        )

        self.active_protocol: str | None = None  # "natpmp" or "upnp"
        self.external_ip: ipaddress.IPv4Address | None = None
        self._discovery_task: asyncio.Task | None = None
        self._discovery_attempted: bool = False  # Track if discovery has been attempted

    async def discover(self, force: bool = False) -> bool:
        """Discover available NAT traversal protocol.

        Tries NAT-PMP first, then UPnP, with retry logic and exponential backoff.

        Args:
            force: If True, force discovery even if already attempted and failed

        Returns:
            True if a protocol was discovered, False otherwise

        """
        # CRITICAL FIX: Don't retry discovery if it already failed and we're not forcing
        # This prevents infinite discovery loops when discovery fails
        if self._discovery_attempted and not force and not self.active_protocol:
            self.logger.debug(
                "NAT discovery already attempted and failed, skipping (use force=True to retry)"
            )
            return False

        # CRITICAL FIX: Add retry logic with exponential backoff for NAT discovery
        # Retry delays: 2s, 4s (2 attempts total) - optimized for faster startup
        max_attempts = 2
        retry_delays = [2.0, 4.0]

        # Mark discovery as attempted
        self._discovery_attempted = True

        for attempt in range(max_attempts):
            if attempt > 0:
                delay = retry_delays[attempt - 1]
                self.logger.info(
                    "NAT discovery attempt %d/%d (retrying after %.1fs delay)",
                    attempt + 1,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)

            # Try NAT-PMP first
            if self.config.nat.enable_nat_pmp:
                try:
                    self.natpmp_client = NATPMPClient()
                    await self.natpmp_client.get_external_ip()
                    self.active_protocol = "natpmp"
                    self.external_ip = self.natpmp_client._external_ip  # noqa: SLF001
                    self.logger.info(
                        "NAT-PMP discovered and active (attempt %d/%d)",
                        attempt + 1,
                        max_attempts,
                    )
                    # Reset discovery attempted flag on success
                    self._discovery_attempted = False
                    return True
                except NATPMPError as e:
                    self.logger.debug(
                        "NAT-PMP discovery failed (attempt %d/%d): %s",
                        attempt + 1,
                        max_attempts,
                        e,
                    )

            # Fallback to UPnP
            if self.config.nat.enable_upnp:
                try:
                    self.upnp_client = UPnPClient()
                    if await self.upnp_client.discover():
                        self.external_ip = await self.upnp_client.get_external_ip()
                        self.active_protocol = "upnp"
                        self.logger.info(
                            "UPnP discovered and active (attempt %d/%d)",
                            attempt + 1,
                            max_attempts,
                        )
                        # Reset discovery attempted flag on success
                        self._discovery_attempted = False
                        return True
                    # UPnP discovery returned False - no device found
                    self.logger.debug(
                        "UPnP discovery returned False (attempt %d/%d) - no device found",
                        attempt + 1,
                        max_attempts,
                    )
                except UPnPError as e:
                    # Enhanced UPnP discovery error logging
                    error_msg = str(e)
                    if "HTTP 500" in error_msg or "500" in error_msg:
                        self.logger.warning(
                            "UPnP discovery failed (attempt %d/%d): Router returned HTTP 500 error. "
                            "The router's UPnP service may be malfunctioning. "
                            "Consider manually configuring port forwarding.",
                            attempt + 1,
                            max_attempts,
                        )
                    elif (
                        "timeout" in error_msg.lower()
                        or "connection" in error_msg.lower()
                    ):
                        self.logger.debug(
                            "UPnP discovery failed (attempt %d/%d): Could not connect to router (%s). "
                            "UPnP may be disabled or the router may not support it.",
                            attempt + 1,
                            max_attempts,
                            error_msg,
                        )
                    else:
                        self.logger.debug(
                            "UPnP discovery failed (attempt %d/%d): %s",
                            attempt + 1,
                            max_attempts,
                            e,
                        )

        # NAT traversal is optional - only log as debug to reduce noise
        # Downloads work fine without NAT traversal (most users don't need it)
        self.logger.info(
            "No NAT traversal protocol available after %d attempts (this is normal and doesn't affect downloads)",
            max_attempts,
        )
        return False

    async def start(self) -> None:
        """Start NAT manager and discover protocol."""
        if not self.config.nat.auto_map_ports:
            return

        # CRITICAL FIX: Clear discovery cache on startup to force fresh discovery
        # This helps when router UPnP service has changed or stale URLs exist
        if self.upnp_client:
            self.upnp_client.clear_cache()
        self._discovery_attempted = False  # Reset discovery state

        await self.discover()

        # CRITICAL FIX: Clear existing port mappings before creating new ones
        # This prevents conflicts from stale mappings left by previous sessions
        if self.active_protocol == "upnp" and self.upnp_client:
            try:
                deleted_count = await self.upnp_client.clear_all_mappings("ccBitTorrent")
                if deleted_count > 0:
                    self.logger.info(
                        "Cleared %d existing UPnP port mapping(s) before creating new ones",
                        deleted_count,
                    )
            except Exception as e:
                # Some routers don't support GetGenericPortMappingEntry
                # This is OK - we'll rely on delete before add strategy
                self.logger.debug(
                    "Could not clear existing mappings (may not be supported): %s. "
                    "Will rely on delete before add strategy.",
                    e,
                )

        # Start periodic discovery
        if self.config.nat.nat_discovery_interval > 0:
            self._discovery_task = asyncio.create_task(self._discovery_loop())

    async def _discovery_loop(self) -> None:
        """Periodically re-discover NAT devices."""
        while True:
            try:
                await asyncio.sleep(self.config.nat.nat_discovery_interval)

                # Re-discover if protocol not active (but only periodically, not on every loop)
                # Use force=True to allow periodic retries
                if not self.active_protocol:
                    await self.discover(force=True)
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in discovery loop")

    async def map_port(
        self,
        internal_port: int,
        external_port: int = 0,
        protocol: str = "tcp",
    ) -> PortMapping | None:
        """Map a port using the active protocol with retry logic.

        Args:
            internal_port: Internal port to map
            external_port: Desired external port (0 for automatic)
            protocol: "tcp" or "udp"

        Returns:
            PortMapping if successful, None otherwise

        """
        if not self.active_protocol:
            # CRITICAL FIX: Only try discovery once if not already attempted
            # This prevents multiple discovery attempts when mapping multiple ports
            if not self._discovery_attempted:
                discovered = await self.discover()
                if not discovered:
                    self.logger.warning(
                        "Cannot map port %s:%d - no active protocol (discovery failed)",
                        protocol,
                        internal_port,
                    )
                    return None
            else:
                # Discovery already attempted and failed, don't retry
                self.logger.debug(
                    "Cannot map port %s:%d - no active protocol (discovery already attempted)",
                    protocol,
                    internal_port,
                )
                return None

        # CRITICAL FIX: Add retry logic with exponential backoff for failed port mappings
        # Retry delays: 5s, 10s, 20s (3 attempts total)
        max_attempts = 3
        retry_delays = [5.0, 10.0, 20.0]

        for attempt in range(max_attempts):
            if attempt > 0:
                delay = retry_delays[attempt - 1]
                self.logger.info(
                    "Port mapping retry attempt %d/%d for %s:%d (retrying after %.1fs delay)",
                    attempt + 1,
                    max_attempts,
                    protocol.upper(),
                    internal_port,
                    delay,
                )
                await asyncio.sleep(delay)

            try:
                if self.active_protocol == "natpmp":
                    if not self.natpmp_client:
                        self.logger.warning(
                            "NAT-PMP client not available for port mapping"
                        )
                        if attempt < max_attempts - 1:
                            continue
                        return None

                    self.logger.info(
                        "Mapping port via NAT-PMP: %s %d->%d (attempt %d/%d)",
                        protocol.upper(),
                        internal_port,
                        external_port or internal_port,
                        attempt + 1,
                        max_attempts,
                    )
                    mapping_result = await self.natpmp_client.add_port_mapping(
                        internal_port,
                        external_port,
                        lifetime=self.config.nat.port_mapping_lease_time,
                        protocol=protocol,
                    )

                    mapping = await self.port_mapping_manager.add_mapping(
                        mapping_result.internal_port,
                        mapping_result.external_port,
                        mapping_result.protocol,
                        "natpmp",
                        mapping_result.lifetime,
                    )
                    self.logger.info(
                        "NAT-PMP port mapping successful: %s %d->%d (lifetime: %ds)",
                        protocol.upper(),
                        mapping_result.internal_port,
                        mapping_result.external_port,
                        mapping_result.lifetime,
                    )
                    return mapping

                if self.active_protocol == "upnp":
                    if not self.upnp_client:
                        self.logger.warning(
                            "UPnP client not available for port mapping"
                        )
                        if attempt < max_attempts - 1:
                            continue
                        return None

                    actual_external = external_port or internal_port
                    self.logger.info(
                        "Mapping port via UPnP: %s %d->%d (attempt %d/%d)",
                        protocol.upper(),
                        internal_port,
                        actual_external,
                        attempt + 1,
                        max_attempts,
                    )
                    await self.upnp_client.add_port_mapping(
                        internal_port,
                        actual_external,
                        protocol.upper(),
                        description="ccBitTorrent",
                        duration=self.config.nat.port_mapping_lease_time,
                    )

                    mapping = await self.port_mapping_manager.add_mapping(
                        internal_port,
                        actual_external,
                        protocol,
                        "upnp",
                        self.config.nat.port_mapping_lease_time,
                    )
                    self.logger.info(
                        "UPnP port mapping successful: %s %d->%d (lifetime: %ds)",
                        protocol.upper(),
                        internal_port,
                        actual_external,
                        self.config.nat.port_mapping_lease_time,
                    )
                    return mapping

                # If we get here, active_protocol is set but not natpmp or upnp
                self.logger.warning(
                    "Unknown NAT protocol: %s (attempt %d/%d)",
                    self.active_protocol,
                    attempt + 1,
                    max_attempts,
                )
                if attempt < max_attempts - 1:
                    continue
                return None

            except (NATPMPError, UPnPError) as e:
                error_type = type(e).__name__
                error_msg = str(e)

                # Check if this is a retryable error (not authorization/permission errors)
                is_retryable = True
                if (
                    "606" in error_msg
                    or "Action not authorized" in error_msg
                    or "permission" in error_msg.lower()
                    or "denied" in error_msg.lower()
                ):
                    # UPnP error 606 (Action not authorized) is not retryable
                    is_retryable = False
                    if attempt < max_attempts - 1:
                        # Still retry once more in case it's a transient router issue
                        self.logger.warning(
                            "Port mapping failed with authorization error (attempt %d/%d): %s. "
                            "Will retry once more in case it's transient.",
                            attempt + 1,
                            max_attempts,
                            error_msg,
                        )
                        continue

                # If last attempt or non-retryable error, provide user-friendly message
                if attempt == max_attempts - 1 or not is_retryable:
                    # Provide user-friendly error messages
                    if "606" in error_msg or "Action not authorized" in error_msg:
                        user_msg = (
                            f"UPnP port mapping failed: Router denied the port mapping request (error 606: Action not authorized). "
                            f"This usually means UPnP is enabled but the router requires manual port forwarding. "
                            f"Please manually forward port {internal_port} ({protocol.upper()}) in your router settings. "
                            f"Instructions: https://portforward.com/router.htm"
                        )
                    elif "HTTP 500" in error_msg or "500" in error_msg:
                        user_msg = (
                            f"UPnP port mapping failed: Router returned internal server error (HTTP 500). "
                            f"This usually means the router's UPnP service is malfunctioning or the port is already in use. "
                            f"Try manually forwarding port {internal_port} ({protocol.upper()}) in your router settings."
                        )
                    elif (
                        "connection" in error_msg.lower()
                        or "timeout" in error_msg.lower()
                    ):
                        user_msg = (
                            f"UPnP port mapping failed: Could not connect to router's UPnP service. "
                            f"Ensure UPnP is enabled in your router settings. "
                            f"Port {internal_port} ({protocol.upper()}) may need manual forwarding."
                        )
                    elif (
                        "permission" in error_msg.lower()
                        or "denied" in error_msg.lower()
                    ):
                        user_msg = (
                            f"UPnP port mapping failed: Router denied the port mapping request. "
                            f"This may indicate insufficient permissions or router security restrictions. "
                            f"Try manually forwarding port {internal_port} ({protocol.upper()}) in your router settings."
                        )
                    else:
                        user_msg = (
                            f"UPnP port mapping failed for port {internal_port} ({protocol.upper()}): {error_msg}. "
                            f"Consider manually forwarding this port in your router settings."
                        )

                    self.logger.exception(
                        "Port mapping failed via %s (attempt %d/%d)",
                        self.active_protocol or "unknown",
                        attempt + 1,
                        max_attempts,
                    )
                    self.logger.warning(
                        "Failed to map port %s:%s via %s - %s",
                        protocol,
                        external_port or internal_port,
                        self.active_protocol or "unknown",
                        user_msg,
                    )
                    self.logger.debug(
                        "Port mapping error details: type=%s, error=%s",
                        error_type,
                        error_msg,
                    )

                    # If not retryable and last attempt, return None
                    if not is_retryable or attempt == max_attempts - 1:
                        return None

                # Retry on next iteration if retryable and not last attempt
                if is_retryable and attempt < max_attempts - 1:
                    continue
            except Exception as e:
                # Unexpected errors - log with full details for debugging
                error_type = type(e).__name__
                self.logger.exception(
                    "Unexpected error mapping port %s:%s via %s (attempt %d/%d): %s (%s)",
                    protocol,
                    external_port or internal_port,
                    self.active_protocol or "unknown",
                    attempt + 1,
                    max_attempts,
                    e,
                    error_type,
                )
                # Retry on next iteration if not last attempt
                if attempt < max_attempts - 1:
                    continue
                return None

        # All attempts failed
        self.logger.error(
            "Port mapping failed after %d attempts for %s:%d",
            max_attempts,
            protocol.upper(),
            internal_port,
        )
        return None

    async def renew_mapping(self, mapping: PortMapping) -> tuple[bool, int | None]:
        """Renew a port mapping.

        Renewal requests are identical to initial mapping requests per RFC 6886.
        For NAT-PMP, we send the same add_port_mapping request.
        For UPnP, we call add_port_mapping again with the same parameters.

        Args:
            mapping: Port mapping to renew

        Returns:
            Tuple of (success: bool, new_lifetime: int | None)
            new_lifetime is None if renewal failed or if mapping is permanent

        """
        if not self.active_protocol:
            # Try to discover protocol if not active (but only if not already attempted)
            # This prevents infinite discovery loops
            if not self._discovery_attempted:
                discovered = await self.discover()
                if not discovered:
                    self.logger.warning(
                        "Cannot renew mapping %s:%s - no active protocol (discovery failed)",
                        mapping.protocol,
                        mapping.external_port,
                    )
                    return False, None
            else:
                # Discovery already attempted and failed, don't retry
                self.logger.debug(
                    "Cannot renew mapping %s:%s - no active protocol (discovery already attempted)",
                    mapping.protocol,
                    mapping.external_port,
                )
                return False, None

        try:
            if mapping.protocol_source == "natpmp":
                if not self.natpmp_client:
                    self.logger.warning(
                        "Cannot renew NAT-PMP mapping %s:%s - client not available",
                        mapping.protocol,
                        mapping.external_port,
                    )
                    return False, None

                # Renew by sending same mapping request (RFC 6886 section 3.6)
                mapping_result = await self.natpmp_client.add_port_mapping(
                    mapping.internal_port,
                    mapping.external_port,
                    lifetime=self.config.nat.port_mapping_lease_time,
                    protocol=mapping.protocol,
                )

                self.logger.info(
                    "Renewed NAT-PMP mapping %s:%s -> %s (new lifetime: %s s)",
                    mapping.protocol,
                    mapping.internal_port,
                    mapping_result.external_port,
                    mapping_result.lifetime,
                )

                return True, mapping_result.lifetime

            if mapping.protocol_source == "upnp":
                if not self.upnp_client:
                    self.logger.warning(
                        "Cannot renew UPnP mapping %s:%s - client not available",
                        mapping.protocol,
                        mapping.external_port,
                    )
                    return False, None

                # Renew by calling add_port_mapping again
                await self.upnp_client.add_port_mapping(
                    mapping.internal_port,
                    mapping.external_port,
                    protocol=mapping.protocol.upper(),
                    description="ccBitTorrent",
                    duration=self.config.nat.port_mapping_lease_time,
                )

                self.logger.info(
                    "Renewed UPnP mapping %s:%s -> %s (duration: %s s)",
                    mapping.protocol,
                    mapping.internal_port,
                    mapping.external_port,
                    self.config.nat.port_mapping_lease_time,
                )

                return True, self.config.nat.port_mapping_lease_time

            self.logger.warning(
                "Unknown protocol source for mapping %s:%s: %s",
                mapping.protocol,
                mapping.external_port,
                mapping.protocol_source,
            )
            return False, None

        except (NATPMPError, UPnPError) as e:
            self.logger.warning(
                "Failed to renew mapping %s:%s: %s",
                mapping.protocol,
                mapping.external_port,
                e,
            )
            return False, None
        except Exception:
            self.logger.exception(
                "Unexpected error renewing mapping %s:%s",
                mapping.protocol,
                mapping.external_port,
            )
            return False, None

    async def _renew_mapping_callback(
        self, mapping: PortMapping
    ) -> tuple[bool, int | None]:
        """Callback for port mapping renewal.

        This is passed to PortMappingManager to enable renewal.

        Args:
            mapping: Port mapping to renew

        Returns:
            Tuple of (success: bool, new_lifetime: int | None)

        """
        return await self.renew_mapping(mapping)

    async def unmap_port(self, external_port: int, protocol: str = "tcp") -> bool:
        """Remove port mapping.

        Args:
            external_port: External port to remove
            protocol: "tcp" or "udp"

        Returns:
            True if successful, False otherwise

        """
        if not self.active_protocol:
            return False

        try:
            if self.active_protocol == "natpmp":
                if self.natpmp_client:
                    await self.natpmp_client.delete_port_mapping(
                        external_port, protocol
                    )
            elif self.active_protocol == "upnp" and self.upnp_client:
                await self.upnp_client.delete_port_mapping(
                    external_port, protocol.upper()
                )

            await self.port_mapping_manager.remove_mapping(protocol, external_port)
            return True

        except (NATPMPError, UPnPError):
            self.logger.exception("Failed to unmap port %s:%s", protocol, external_port)
            return False
        except Exception:
            self.logger.exception("Unexpected error unmapping port")
            return False

    async def map_listen_ports(self) -> None:
        """Map all required ports (TCP listen, UDP peer, UDP tracker, DHT, XET).

        CRITICAL FIX: Maps both TCP and UDP for all applicable ports to ensure
        proper NAT traversal. For listen_port, both TCP and UDP are mapped.
        For tracker_udp_port, both TCP and UDP are mapped if different from listen_port.
        DHT port is UDP only.
        XET protocol port is UDP only.
        XET multicast port is UDP only (usually not needed for multicast).
        """
        # CRITICAL FIX: Track mapping results for diagnostics
        mapping_results = []
        # Use new port configuration with backward compatibility
        configured_tcp_port = (
            self.config.network.listen_port_tcp or self.config.network.listen_port
        )
        configured_udp_port = (
            self.config.network.listen_port_udp or self.config.network.listen_port
        )
        configured_tracker_udp_port = (
            self.config.network.tracker_udp_port
            or self.config.network.listen_port
        )
        # XET protocol port (uses listen_port_udp if not set)
        configured_xet_port = (
            self.config.network.xet_port
            or self.config.network.listen_port_udp
            or self.config.network.listen_port
        )
        # XET multicast port
        configured_xet_multicast_port = getattr(
            self.config.network, "xet_multicast_port", None
        )

        # CRITICAL FIX: Map both TCP and UDP for listen ports
        # Use listen_port_tcp and listen_port_udp from config (with fallback to listen_port)
        # If they're the same port, map both TCP and UDP for that port
        # If they're different, map TCP for TCP port and UDP for UDP port
        if self.config.nat.map_tcp_port:
            # Map TCP for listen_port_tcp (or listen_port if not set)
            if configured_tcp_port <= 0 or configured_tcp_port > 65535:
                self.logger.error(
                    "NAT: Invalid configured TCP port %d (must be 1-65535), skipping TCP port mapping",
                    configured_tcp_port,
                )
            else:
                result = await self.map_port(
                    configured_tcp_port,
                    configured_tcp_port,
                    "tcp",
                )
                # CRITICAL FIX: Verify mapping was actually created and uses correct ports
                verified = False
                internal_port_match = False
                external_port_match = False
                if result:
                    # Check if mapping exists in port_mapping_manager
                    mappings = await self.port_mapping_manager.get_all_mappings()
                    for m in mappings:
                        if (
                            m.protocol == "tcp"
                            and m.external_port == configured_tcp_port
                        ):
                            verified = True
                            external_port_match = True
                            if m.internal_port == configured_tcp_port:
                                internal_port_match = True
                            else:
                                self.logger.warning(
                                    "NAT: TCP port mapping internal port mismatch: configured=%d, mapped=%d",
                                    configured_tcp_port,
                                    m.internal_port,
                                )
                            break

                mapping_results.append(
                    ("TCP", configured_tcp_port, result and verified)
                )
                if result and verified and internal_port_match:
                    self.logger.info(
                        "NAT: Successfully mapped and verified TCP port %d (internal=%d, external=%d)",
                        configured_tcp_port,
                        configured_tcp_port,
                        configured_tcp_port,
                    )
                elif result and verified and not internal_port_match:
                    self.logger.warning(
                        "NAT: TCP port %d mapped but internal port mismatch detected",
                        configured_tcp_port,
                    )
                elif result and not verified:
                    self.logger.warning(
                        "NAT: TCP port %d mapping reported success but verification failed (configured port: %d)",
                        configured_tcp_port,
                        configured_tcp_port,
                    )
                else:
                    self.logger.warning(
                        "NAT: Failed to map TCP port %d (configured port: %d) - incoming TCP connections may fail",
                        configured_tcp_port,
                        configured_tcp_port,
                    )

        # CRITICAL FIX: Map UDP for listen_port_udp (or listen_port if not set)
        # If listen_port_tcp == listen_port_udp, we'll have both TCP and UDP for the same port
        if self.config.nat.map_udp_port:
            # Map UDP for listen_port_udp
            if configured_udp_port <= 0 or configured_udp_port > 65535:
                self.logger.error(
                    "NAT: Invalid configured UDP port %d (must be 1-65535), skipping UDP port mapping",
                    configured_udp_port,
                )
            else:
                result = await self.map_port(
                    configured_udp_port,
                    configured_udp_port,
                    "udp",
                )
                # CRITICAL FIX: Verify mapping was actually created and uses correct ports
                verified = False
                internal_port_match = False
                # external_port_match = False  # Reserved for future use
                if result:
                    mappings = await self.port_mapping_manager.get_all_mappings()
                    for m in mappings:
                        if (
                            m.protocol == "udp"
                            and m.external_port == configured_udp_port
                        ):
                            verified = True
                            # external_port_match = True  # Reserved for future use
                            if m.internal_port == configured_udp_port:
                                internal_port_match = True
                            else:
                                self.logger.warning(
                                    "NAT: UDP port mapping internal port mismatch: configured=%d, mapped=%d",
                                    configured_udp_port,
                                    m.internal_port,
                                )
                            break

                mapping_results.append(
                    ("UDP", configured_udp_port, result and verified)
                )
                if result and verified and internal_port_match:
                    self.logger.info(
                        "NAT: Successfully mapped and verified UDP port %d (internal=%d, external=%d)",
                        configured_udp_port,
                        configured_udp_port,
                        configured_udp_port,
                    )
                elif result and verified and not internal_port_match:
                    self.logger.warning(
                        "NAT: UDP port %d mapped but internal port mismatch detected",
                        configured_udp_port,
                    )
                elif result and not verified:
                    self.logger.warning(
                        "NAT: UDP port %d mapping reported success but verification failed (configured port: %d)",
                        configured_udp_port,
                        configured_udp_port,
                    )
                else:
                    self.logger.warning(
                        "NAT: Failed to map UDP port %d (configured port: %d) - UDP peer connections and tracker responses may not reach client",
                        configured_udp_port,
                        configured_udp_port,
                    )

        # CRITICAL FIX: Map both TCP and UDP for tracker_udp_port if different from listen ports
        # Check if tracker port is different from both TCP and UDP listen ports
        tracker_port_different = (
            configured_tracker_udp_port != configured_tcp_port
            and configured_tracker_udp_port != configured_udp_port
        )
        if (
            self.config.nat.map_udp_port
            and tracker_port_different
        ):
            # Map UDP for tracker port
            if configured_tracker_udp_port <= 0 or configured_tracker_udp_port > 65535:
                self.logger.error(
                    "NAT: Invalid configured UDP tracker port %d (must be 1-65535), skipping UDP tracker port mapping",
                    configured_tracker_udp_port,
                )
            else:
                result = await self.map_port(
                    configured_tracker_udp_port,
                    configured_tracker_udp_port,
                    "udp",
                )
                # CRITICAL FIX: Verify mapping was actually created
                verified = False
                internal_port_match = False
                if result:
                    mappings = await self.port_mapping_manager.get_all_mappings()
                    for m in mappings:
                        if (
                            m.protocol == "udp"
                            and m.external_port == configured_tracker_udp_port
                        ):
                            verified = True
                            if m.internal_port == configured_tracker_udp_port:
                                internal_port_match = True
                            break

                mapping_results.append(
                    ("UDP (Tracker)", configured_tracker_udp_port, result and verified)
                )
                if result and verified and internal_port_match:
                    self.logger.info(
                        "NAT: Successfully mapped and verified UDP tracker port %d",
                        configured_tracker_udp_port,
                    )
                elif result and verified and not internal_port_match:
                    self.logger.warning(
                        "NAT: UDP tracker port %d mapped but internal port mismatch detected",
                        configured_tracker_udp_port,
                    )
                elif result and not verified:
                    self.logger.warning(
                        "NAT: UDP tracker port %d mapping reported success but verification failed",
                        configured_tracker_udp_port,
                    )
                else:
                    self.logger.warning(
                        "NAT: Failed to map UDP tracker port %d - tracker communication may fail",
                        configured_tracker_udp_port,
                    )

            # CRITICAL FIX: Also map TCP for tracker port (both protocols needed)
            if self.config.nat.map_tcp_port:
                if configured_tracker_udp_port <= 0 or configured_tracker_udp_port > 65535:
                    self.logger.error(
                        "NAT: Invalid configured UDP tracker port %d (must be 1-65535), skipping TCP tracker port mapping",
                        configured_tracker_udp_port,
                    )
                else:
                    result = await self.map_port(
                        configured_tracker_udp_port,
                        configured_tracker_udp_port,
                        "tcp",
                    )
                    verified = False
                    internal_port_match = False
                    if result:
                        mappings = await self.port_mapping_manager.get_all_mappings()
                        for m in mappings:
                            if (
                                m.protocol == "tcp"
                                and m.external_port == configured_tracker_udp_port
                            ):
                                verified = True
                                if m.internal_port == configured_tracker_udp_port:
                                    internal_port_match = True
                                break

                    mapping_results.append(
                        ("TCP (Tracker)", configured_tracker_udp_port, result and verified)
                    )
                    if result and verified and internal_port_match:
                        self.logger.info(
                            "NAT: Successfully mapped and verified TCP tracker port %d",
                            configured_tracker_udp_port,
                        )
                    elif result and verified and not internal_port_match:
                        self.logger.warning(
                            "NAT: TCP tracker port %d mapped but internal port mismatch detected",
                            configured_tracker_udp_port,
                        )
                    elif result and not verified:
                        self.logger.warning(
                            "NAT: TCP tracker port %d mapping reported success but verification failed",
                            configured_tracker_udp_port,
                        )
                    else:
                        self.logger.warning(
                            "NAT: Failed to map TCP tracker port %d - tracker communication may fail",
                            configured_tracker_udp_port,
                        )

        # Map DHT port if available
        if self.config.nat.map_dht_port:
            dht_port = getattr(self.config.discovery, "dht_port", None)
            if dht_port:
                result = await self.map_port(
                    dht_port,
                    dht_port,
                    "udp",
                )
                # CRITICAL FIX: Verify mapping was actually created
                verified = False
                if result:
                    mappings = await self.port_mapping_manager.get_all_mappings()
                    for m in mappings:
                        if m.protocol == "udp" and m.external_port == dht_port:
                            verified = True
                            break

                mapping_results.append(("UDP (DHT)", dht_port, result and verified))
                if result and verified:
                    self.logger.info(
                        "NAT: Successfully mapped and verified DHT UDP port %d",
                        dht_port,
                    )
                elif result and not verified:
                    self.logger.warning(
                        "NAT: DHT UDP port %d mapping reported success but verification failed",
                        dht_port,
                    )
                else:
                    self.logger.warning(
                        "NAT: Failed to map DHT UDP port %d - DHT queries may fail",
                        dht_port,
                    )

        # Map XET protocol port if enabled and XET is enabled
        if (
            self.config.nat.map_xet_port
            and hasattr(self.config, "xet_sync")
            and self.config.xet_sync
            and self.config.xet_sync.enable_xet
        ):
            # Check if XET port is different from already mapped ports
            xet_port_different = (
                configured_xet_port != configured_tcp_port
                and configured_xet_port != configured_udp_port
                and configured_xet_port != configured_tracker_udp_port
            )
            # Also check if different from DHT port
            dht_port = getattr(self.config.discovery, "dht_port", None)
            if dht_port:
                xet_port_different = xet_port_different and configured_xet_port != dht_port

            if xet_port_different:
                # Map UDP for XET protocol port (only if different from other ports)
                if configured_xet_port <= 0 or configured_xet_port > 65535:
                    self.logger.error(
                        "NAT: Invalid configured XET port %d (must be 1-65535), skipping XET port mapping",
                        configured_xet_port,
                    )
                else:
                    result = await self.map_port(
                        configured_xet_port,
                        configured_xet_port,
                        "udp",
                    )
                    # Verify mapping was actually created
                    verified = False
                    internal_port_match = False
                    if result:
                        mappings = await self.port_mapping_manager.get_all_mappings()
                        for m in mappings:
                            if (
                                m.protocol == "udp"
                                and m.external_port == configured_xet_port
                            ):
                                verified = True
                                if m.internal_port == configured_xet_port:
                                    internal_port_match = True
                                break

                    mapping_results.append(
                        ("UDP (XET)", configured_xet_port, result and verified)
                    )
                    if result and verified and internal_port_match:
                        self.logger.info(
                            "NAT: Successfully mapped and verified XET UDP port %d",
                            configured_xet_port,
                        )
                    elif result and verified and not internal_port_match:
                        self.logger.warning(
                            "NAT: XET UDP port %d mapped but internal port mismatch detected",
                            configured_xet_port,
                        )
                    elif result and not verified:
                        self.logger.warning(
                            "NAT: XET UDP port %d mapping reported success but verification failed",
                            configured_xet_port,
                        )
                    else:
                        self.logger.warning(
                            "NAT: Failed to map XET UDP port %d - XET protocol communication may fail",
                            configured_xet_port,
                        )
            else:
                self.logger.debug(
                    "NAT: XET port %d is same as another mapped port, skipping duplicate mapping",
                    configured_xet_port,
                )

        # Map XET multicast port if enabled (usually not needed for multicast)
        if (
            self.config.nat.map_xet_multicast_port
            and configured_xet_multicast_port
            and hasattr(self.config, "xet_sync")
            and self.config.xet_sync
            and self.config.xet_sync.enable_xet
        ):
            # Check if multicast port is different from already mapped ports
            multicast_port_different = (
                configured_xet_multicast_port != configured_tcp_port
                and configured_xet_multicast_port != configured_udp_port
                and configured_xet_multicast_port != configured_tracker_udp_port
                and configured_xet_multicast_port != configured_xet_port
            )
            dht_port = getattr(self.config.discovery, "dht_port", None)
            if dht_port:
                multicast_port_different = (
                    multicast_port_different
                    and configured_xet_multicast_port != dht_port
                )

            if multicast_port_different:
                # Map UDP for XET multicast port
                if (
                    configured_xet_multicast_port <= 0
                    or configured_xet_multicast_port > 65535
                ):
                    self.logger.error(
                        "NAT: Invalid configured XET multicast port %d (must be 1-65535), skipping XET multicast port mapping",
                        configured_xet_multicast_port,
                    )
                else:
                    result = await self.map_port(
                        configured_xet_multicast_port,
                        configured_xet_multicast_port,
                        "udp",
                    )
                    # Verify mapping was actually created
                    verified = False
                    internal_port_match = False
                    if result:
                        mappings = await self.port_mapping_manager.get_all_mappings()
                        for m in mappings:
                            if (
                                m.protocol == "udp"
                                and m.external_port == configured_xet_multicast_port
                            ):
                                verified = True
                                if m.internal_port == configured_xet_multicast_port:
                                    internal_port_match = True
                                break

                    mapping_results.append(
                        (
                            "UDP (XET Multicast)",
                            configured_xet_multicast_port,
                            result and verified,
                        )
                    )
                    if result and verified and internal_port_match:
                        self.logger.info(
                            "NAT: Successfully mapped and verified XET multicast UDP port %d",
                            configured_xet_multicast_port,
                        )
                    elif result and verified and not internal_port_match:
                        self.logger.warning(
                            "NAT: XET multicast UDP port %d mapped but internal port mismatch detected",
                            configured_xet_multicast_port,
                        )
                    elif result and not verified:
                        self.logger.warning(
                            "NAT: XET multicast UDP port %d mapping reported success but verification failed",
                            configured_xet_multicast_port,
                        )
                    else:
                        self.logger.warning(
                            "NAT: Failed to map XET multicast UDP port %d - XET multicast may not work across NAT",
                            configured_xet_multicast_port,
                        )
            else:
                self.logger.debug(
                    "NAT: XET multicast port %d is same as another mapped port, skipping duplicate mapping",
                    configured_xet_multicast_port,
                )

        # CRITICAL FIX: Log summary of all port mappings for diagnostics
        successful_mappings = [r for r in mapping_results if r[2]]
        failed_mappings = [r for r in mapping_results if not r[2]]

        if successful_mappings:
            self.logger.info(
                "NAT: Successfully mapped %d port(s): %s",
                len(successful_mappings),
                ", ".join(
                    [f"{proto}:{port}" for proto, port, _ in successful_mappings]
                ),
            )
        if failed_mappings:
            self.logger.warning(
                "NAT: Failed to map %d port(s): %s. This may prevent peer connections and tracker responses.",
                len(failed_mappings),
                ", ".join([f"{proto}:{port}" for proto, port, _ in failed_mappings]),
            )

    async def wait_for_mapping(self, timeout: float = 60.0) -> bool:
        """Wait for at least one port mapping to be active.

        This method waits until at least one port mapping has been successfully
        created, or until the timeout expires. This is useful to ensure NAT
        port mapping is complete before starting services that depend on it
        (e.g., TCP server for incoming peer connections).

        Args:
            timeout: Maximum time to wait in seconds (default: 60.0, increased for slow routers)

        Returns:
            True if at least one mapping is active, False if timeout expires

        """
        start_time = asyncio.get_event_loop().time()
        check_interval = 0.2  # Check every 200ms (optimized for faster detection)

        # First check immediately (no delay) - mappings may already be complete
        mappings = await self.port_mapping_manager.get_all_mappings()
        if mappings:
            # At least one mapping exists
            self.logger.info(
                "NAT: Port mapping confirmed immediately (%d mapping(s) active)",
                len(mappings),
            )
            return True

        # Then check with intervals
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            await asyncio.sleep(check_interval)
            mappings = await self.port_mapping_manager.get_all_mappings()
            if mappings:
                # At least one mapping exists
                self.logger.info(
                    "NAT: Port mapping confirmed (%d mapping(s) active)",
                    len(mappings),
                )
                return True

        # Timeout expired
        mappings = await self.port_mapping_manager.get_all_mappings()
        if mappings:
            # Mappings exist but we hit timeout (shouldn't happen, but handle gracefully)
            self.logger.info(
                "NAT: Port mapping confirmed after timeout check (%d mapping(s) active)",
                len(mappings),
            )
            return True

        self.logger.warning(
            "NAT: Port mapping timeout after %.1fs - no mappings active. "
            "TCP server will start anyway, but incoming connections may fail.",
            timeout,
        )
        return False

    async def stop(self) -> None:
        """Stop NAT manager and cleanup."""
        if self._discovery_task:
            self._discovery_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._discovery_task

        # Unmap all ports
        mappings = await self.port_mapping_manager.get_all_mappings()
        for mapping in mappings:
            await self.unmap_port(mapping.external_port, mapping.protocol)

        if self.natpmp_client:
            await self.natpmp_client.close()

        self.logger.info("NAT manager stopped")

    async def get_external_ip(self) -> ipaddress.IPv4Address | None:
        """Get external IP address.

        Returns:
            External IP address if available, None otherwise

        """
        if self.external_ip:
            return self.external_ip

        if not self.active_protocol:
            # CRITICAL FIX: Only try discovery once if not already attempted
            # This prevents multiple discovery attempts
            if not self._discovery_attempted:
                await self.discover()

        if self.active_protocol == "natpmp" and self.natpmp_client:
            try:
                self.external_ip = await self.natpmp_client.get_external_ip()
                return self.external_ip
            except NATPMPError:
                pass
        elif self.active_protocol == "upnp" and self.upnp_client:
            try:
                self.external_ip = await self.upnp_client.get_external_ip()
                return self.external_ip
            except UPnPError:
                pass

        return None

    async def get_external_port(
        self, internal_port: int, protocol: str = "tcp"
    ) -> int | None:
        """Get external port for a given internal port and protocol.

        This method queries the port mapping manager to find the external port
        that corresponds to the given internal port. This is critical for
        tracker announces when behind NAT, as trackers need the external port
        to route incoming connections correctly.

        Args:
            internal_port: Internal port to look up
            protocol: Protocol type ("tcp" or "udp")

        Returns:
            External port if mapping exists, None otherwise

        """
        mappings = await self.port_mapping_manager.get_all_mappings()
        for mapping in mappings:
            if mapping.internal_port == internal_port and mapping.protocol == protocol:
                return mapping.external_port
        return None

    async def get_status(self) -> dict:
        """Get NAT manager status.

        Returns:
            Dictionary with status information

        """
        mappings = [
            {
                "protocol": mapping.protocol,
                "internal_port": mapping.internal_port,
                "external_port": mapping.external_port,
                "source": mapping.protocol_source,
                "expires_at": mapping.expires_at,
            }
            for mapping in await self.port_mapping_manager.get_all_mappings()
        ]

        return {
            "active_protocol": self.active_protocol,
            "external_ip": str(self.external_ip) if self.external_ip else None,
            "mappings": mappings,
        }
