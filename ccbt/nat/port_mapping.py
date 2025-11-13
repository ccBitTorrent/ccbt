"""Port mapping state management."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Type alias for renewal callback (using string for forward reference)
RenewalCallback = Callable[["PortMapping"], Awaitable[tuple[bool, int | None]]]


@dataclass
class PortMapping:
    """Represents an active port mapping."""

    internal_port: int
    external_port: int
    protocol: str  # "tcp" or "udp"
    protocol_source: str  # "natpmp" or "upnp"
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    renewal_task: asyncio.Task | None = None


class PortMappingManager:
    """Manages active port mappings and renewal."""

    def __init__(self, renewal_callback: RenewalCallback | None = None) -> None:
        """Initialize port mapping manager.

        Args:
            renewal_callback: Optional async callback for renewing mappings.
                Signature: async (mapping: PortMapping) -> tuple[bool, int | None]
                Returns (success, new_lifetime)

        """
        self.mappings: dict[str, PortMapping] = {}  # key: "tcp:1234"
        self.lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)
        self.renewal_callback = renewal_callback

    def _make_key(self, protocol: str, external_port: int) -> str:
        """Create mapping key."""
        return f"{protocol}:{external_port}"

    async def add_mapping(
        self,
        internal_port: int,
        external_port: int,
        protocol: str,
        protocol_source: str,
        lifetime: int | None = None,
    ) -> PortMapping:
        """Add port mapping and schedule renewal.

        Args:
            internal_port: Internal port
            external_port: External port
            protocol: "tcp" or "udp"
            protocol_source: "natpmp" or "upnp"
            lifetime: Mapping lifetime in seconds (None for permanent)

        Returns:
            PortMapping object

        """
        key = self._make_key(protocol, external_port)

        async with self.lock:
            mapping = PortMapping(
                internal_port=internal_port,
                external_port=external_port,
                protocol=protocol,
                protocol_source=protocol_source,
                expires_at=time.time() + lifetime
                if lifetime and lifetime > 0
                else None,
            )
            self.mappings[key] = mapping

            # Schedule renewal if lifetime specified
            if lifetime and lifetime > 0:
                mapping.renewal_task = asyncio.create_task(
                    self._renew_mapping(mapping, lifetime)
                )

        self.logger.debug("Added port mapping: %s", key)
        return mapping

    async def remove_mapping(self, protocol: str, external_port: int) -> bool:
        """Remove port mapping.

        Args:
            protocol: "tcp" or "udp"
            external_port: External port

        Returns:
            True if mapping was removed, False if not found

        """
        key = self._make_key(protocol, external_port)

        async with self.lock:
            if key in self.mappings:
                mapping = self.mappings[key]
                if mapping.renewal_task is not None:
                    mapping.renewal_task.cancel()
                del self.mappings[key]
                self.logger.debug("Removed port mapping: %s", key)
                return True
        return False

    async def _renew_mapping(self, mapping: PortMapping, lifetime: int) -> None:
        """Renew port mapping before expiration.

        Per RFC 6886, renewal should begin at 50% of lifetime, but we use 80%
        to be more conservative and ensure we have time for retries.

        This method will:
        1. Wait until renewal time (80% of lifetime)
        2. Attempt renewal via callback
        3. Update mapping expiration on success
        4. Schedule next renewal if successful
        5. Handle errors with retry logic

        Args:
            mapping: Port mapping to renew
            lifetime: Original lifetime in seconds

        """
        # Renew at 80% of lifetime (conservative approach)
        # This gives us 20% of lifetime for retries and error handling
        renewal_delay = lifetime * 0.8
        max_retries = 3
        retry_delay = 60  # Wait 1 minute between retries

        try:
            # Wait until renewal time
            await asyncio.sleep(renewal_delay)

            # Check if mapping still exists (might have been removed)
            key = self._make_key(mapping.protocol, mapping.external_port)
            async with self.lock:
                if key not in self.mappings:
                    self.logger.debug(
                        "Mapping %s:%s no longer exists, skipping renewal",
                        mapping.protocol,
                        mapping.external_port,
                    )
                    return
                # Get current mapping (in case it was updated)
                current_mapping = self.mappings[key]

            # Attempt renewal with retries
            if not self.renewal_callback:
                self.logger.warning(
                    "Cannot renew mapping %s:%s - no renewal callback set",
                    mapping.protocol,
                    mapping.external_port,
                )
                return

            success = False
            new_lifetime: int | None = None

            for attempt in range(max_retries):
                try:
                    self.logger.info(
                        "Renewing port mapping %s:%s (attempt %d/%d)",
                        mapping.protocol,
                        mapping.external_port,
                        attempt + 1,
                        max_retries,
                    )

                    success, new_lifetime = await self.renewal_callback(current_mapping)

                    if success and new_lifetime is not None:
                        # Update mapping expiration time
                        # new_lifetime can be 0 (permanent) or positive
                        async with self.lock:
                            if key in self.mappings:
                                updated_mapping = self.mappings[key]
                                updated_mapping.expires_at = (
                                    time.time() + new_lifetime
                                    if new_lifetime > 0
                                    else None
                                )
                                self.logger.info(
                                    "Successfully renewed mapping %s:%s "
                                    "(new lifetime: %s s, expires at: %.0f)",
                                    mapping.protocol,
                                    mapping.external_port,
                                    new_lifetime,
                                    updated_mapping.expires_at or 0,
                                )

                                # Cancel old renewal task and schedule next one
                                if updated_mapping.renewal_task:
                                    updated_mapping.renewal_task.cancel()

                                # Schedule next renewal if lifetime is finite
                                if new_lifetime > 0:
                                    updated_mapping.renewal_task = asyncio.create_task(
                                        self._renew_mapping(
                                            updated_mapping, new_lifetime
                                        )
                                    )
                                else:
                                    # Permanent mapping, no need to renew
                                    updated_mapping.renewal_task = None

                        break  # Success, exit retry loop

                    if success and new_lifetime is None:
                        # Renewal succeeded but no lifetime returned
                        # This shouldn't happen, but handle gracefully
                        self.logger.warning(
                            "Renewal succeeded but no lifetime returned for %s:%s",
                            mapping.protocol,
                            mapping.external_port,
                        )
                        # Don't schedule next renewal
                        break

                    # Renewal failed
                    if attempt < max_retries - 1:
                        self.logger.warning(
                            "Renewal attempt %d/%d failed for %s:%s, "
                            "retrying in %d seconds",
                            attempt + 1,
                            max_retries,
                            mapping.protocol,
                            mapping.external_port,
                            retry_delay,
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        self.logger.error(
                            "Failed to renew mapping %s:%s after %d attempts",
                            mapping.protocol,
                            mapping.external_port,
                            max_retries,
                        )

                except Exception:
                    self.logger.exception(
                        "Error during renewal attempt %d/%d for %s:%s",
                        attempt + 1,
                        max_retries,
                        mapping.protocol,
                        mapping.external_port,
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)

            if not success:
                self.logger.error(
                    "Port mapping %s:%s will expire - renewal failed",
                    mapping.protocol,
                    mapping.external_port,
                )

        except asyncio.CancelledError:
            # Task was cancelled (mapping removed or manager stopped)
            self.logger.debug(
                "Renewal task cancelled for mapping %s:%s",
                mapping.protocol,
                mapping.external_port,
            )
        except Exception:
            self.logger.exception(
                "Unexpected error in renewal task for mapping %s:%s",
                mapping.protocol,
                mapping.external_port,
            )

    async def get_all_mappings(self) -> list[PortMapping]:
        """Get all active mappings.

        Returns:
            List of PortMapping objects

        """
        async with self.lock:
            return list(self.mappings.values())

    async def get_mapping(
        self, protocol: str, external_port: int
    ) -> PortMapping | None:
        """Get a specific mapping.

        Args:
            protocol: "tcp" or "udp"
            external_port: External port

        Returns:
            PortMapping if found, None otherwise

        """
        key = self._make_key(protocol, external_port)
        async with self.lock:
            return self.mappings.get(key)

    async def cleanup_expired(self) -> None:
        """Clean up expired mappings."""
        now = time.time()
        async with self.lock:
            expired = [
                key
                for key, mapping in self.mappings.items()
                if mapping.expires_at and mapping.expires_at < now
            ]
            for key in expired:
                mapping = self.mappings[key]
                if mapping.renewal_task is not None:
                    mapping.renewal_task.cancel()
                self.logger.info("Cleaned up expired mapping: %s", key)
                del self.mappings[key]
