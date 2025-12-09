"""Security Manager for ccBitTorrent.

from __future__ import annotations

Provides centralized security management including:
- Peer validation and reputation tracking
- Rate limiting and DDoS protection
- Malicious behavior detection
- IP blacklist/whitelist management
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles

from ccbt.utils.events import Event, EventType, emit_event

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from ccbt.models import PeerInfo
    from ccbt.security.ip_filter import IPFilter


class SecurityLevel(Enum):
    """Security levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(Enum):
    """Types of security threats."""

    DDOS_ATTACK = "ddos_attack"
    MALICIOUS_PEER = "malicious_peer"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    INVALID_HANDSHAKE = "invalid_handshake"
    PROTOCOL_VIOLATION = "protocol_violation"


@dataclass
class PeerReputation:
    """Peer reputation information."""

    peer_id: str
    ip: str
    reputation_score: float = 0.5  # 0.0 (bad) to 1.0 (good)
    connection_count: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_seen: float = 0.0
    first_seen: float = 0.0
    violations: list[ThreatType] = field(default_factory=list)
    is_blacklisted: bool = False
    is_whitelisted: bool = False

    def update_reputation(
        self,
        success: bool,
        bytes_sent: int = 0,
        bytes_received: int = 0,
    ) -> None:
        """Update peer reputation based on activity."""
        self.connection_count += 1
        if success:
            self.successful_connections += 1
            # Increase reputation for successful connections
            self.reputation_score = min(1.0, self.reputation_score + 0.01)
        else:  # Tested in test_security_manager_coverage.py::TestPeerReputation::test_update_reputation_failed_connection
            self.failed_connections += 1
            # Decrease reputation for failed connections
            self.reputation_score = max(0.0, self.reputation_score - 0.05)

        self.bytes_sent += bytes_sent
        self.bytes_received += bytes_received
        self.last_seen = time.time()

    def add_violation(self, violation: ThreatType) -> None:
        """Add a security violation."""
        self.violations.append(violation)
        # Significantly decrease reputation for violations
        self.reputation_score = max(0.0, self.reputation_score - 0.2)

        # Auto-blacklist for critical violations
        if violation in [ThreatType.DDOS_ATTACK, ThreatType.MALICIOUS_PEER]:
            self.is_blacklisted = True


@dataclass
class BlacklistEntry:
    """Blacklist entry with metadata."""

    ip: str
    reason: str
    added_at: float
    expires_at: float | None = None  # None = permanent
    source: str = "manual"  # "manual", "auto", "reputation", "violation"

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


@dataclass
class SecurityEvent:
    """Security event information."""

    event_type: ThreatType
    peer_id: str
    ip: str
    severity: SecurityLevel
    description: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


class SecurityManager:
    """Centralized security management."""

    def __init__(self):
        """Initialize security manager."""
        self.peer_reputations: dict[str, PeerReputation] = {}
        self.blacklist_entries: dict[str, BlacklistEntry] = {}
        self.ip_whitelist: set[str] = set()
        self.ip_filter: IPFilter | None = None
        self.security_events: deque = deque(maxlen=10000)
        self.blacklist_file: Path | None = None
        self.blacklist_updater: Any | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._default_expiration_hours: float | None = None

        # Rate limiting
        self.connection_rates: dict[str, deque] = defaultdict(lambda: deque())
        self.message_rates: dict[str, deque] = defaultdict(lambda: deque())
        self.bytes_rates: dict[str, deque] = defaultdict(lambda: deque())

        # Configuration
        self.max_connections_per_minute = 10
        self.max_messages_per_minute = 100
        self.max_bytes_per_minute = 1024 * 1024  # 1MB
        self.reputation_threshold = 0.3
        self.auto_blacklist_threshold = 0.1

        # Statistics
        self.stats = {
            "total_connections": 0,
            "blocked_connections": 0,
            "security_events": 0,
            "blacklisted_peers": 0,
            "whitelisted_peers": 0,
        }

    async def validate_peer(self, peer_info: PeerInfo) -> tuple[bool, str]:
        """Validate a peer connection.

        Returns:
            Tuple of (is_valid, reason)

        """
        peer_id = peer_info.peer_id.hex() if peer_info.peer_id else ""
        ip = peer_info.ip

        # Check IP blacklist (including expiration check)
        entry = self.blacklist_entries.get(ip)
        if entry:
            if entry.is_expired():
                # Remove expired entry
                self.blacklist_entries.pop(ip, None)
                self.stats["blacklisted_peers"] = len(self.blacklist_entries)
            else:
                await self._log_security_event(
                    ThreatType.MALICIOUS_PEER,
                    peer_id,
                    ip,
                    SecurityLevel.HIGH,
                    f"Connection blocked: IP {ip} is blacklisted",
                )
                return False, "IP is blacklisted"

        # Check IP filter if enabled
        if self.ip_filter and self.ip_filter.enabled and self.ip_filter.is_blocked(ip):
            await self._log_security_event(
                ThreatType.MALICIOUS_PEER,
                peer_id,
                ip,
                SecurityLevel.HIGH,
                f"Connection blocked: IP {ip} is blocked by filter",
            )
            return False, "IP is blocked by filter"

        # Check rate limits
        if not await self._check_rate_limits(ip):
            await self._log_security_event(
                ThreatType.RATE_LIMIT_EXCEEDED,
                peer_id,
                ip,
                SecurityLevel.MEDIUM,
                f"Connection blocked: Rate limit exceeded for IP {ip}",
            )
            return False, "Rate limit exceeded"

        # Check peer reputation
        reputation = self._get_peer_reputation(peer_id, ip)
        if reputation.reputation_score < self.reputation_threshold:
            await self._log_security_event(
                ThreatType.MALICIOUS_PEER,
                peer_id,
                ip,
                SecurityLevel.MEDIUM,
                f"Connection blocked: Low reputation score {reputation.reputation_score:.2f}",
            )
            return False, "Low reputation score"

        # Update connection rate
        self._update_connection_rate(ip)

        # Update statistics
        self.stats["total_connections"] += 1

        return True, "Valid peer"

    async def record_peer_activity(
        self,
        peer_id: str,
        ip: str,
        success: bool,
        bytes_sent: int = 0,
        bytes_received: int = 0,
    ) -> None:
        """Record peer activity for reputation tracking."""
        reputation = self._get_peer_reputation(peer_id, ip)
        reputation.update_reputation(success, bytes_sent, bytes_received)

        # Update rate tracking
        self._update_message_rate(ip)
        self._update_bytes_rate(ip, bytes_sent + bytes_received)

        # Record metric for local blacklist source
        await self._record_activity_for_local_blacklist(peer_id, ip, success)

        # Check for auto-blacklisting
        if reputation.reputation_score < self.auto_blacklist_threshold:
            reputation.is_blacklisted = True
            # Use add_to_blacklist with reputation source and optional expiration
            expires_in = None
            if self._default_expiration_hours:
                expires_in = self._default_expiration_hours * 3600.0
            self.add_to_blacklist(
                ip,
                f"Auto-blacklisted due to low reputation: {reputation.reputation_score:.2f}",
                expires_in=expires_in,
                source="reputation",
            )

            await self._log_security_event(
                ThreatType.MALICIOUS_PEER,
                peer_id,
                ip,
                SecurityLevel.CRITICAL,
                f"Peer auto-blacklisted due to low reputation: {reputation.reputation_score:.2f}",
            )

    async def report_violation(
        self,
        peer_id: str,
        ip: str,
        violation: ThreatType,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Report a security violation."""
        reputation = self._get_peer_reputation(peer_id, ip)
        reputation.add_violation(violation)

        # Record violation for local blacklist source
        await self._record_violation_for_local_blacklist(peer_id, ip, violation)

        # Determine severity
        severity = SecurityLevel.MEDIUM
        if violation in [ThreatType.DDOS_ATTACK, ThreatType.MALICIOUS_PEER]:
            severity = SecurityLevel.CRITICAL
        elif (
            violation == ThreatType.RATE_LIMIT_EXCEEDED
        ):  # Tested in test_security_manager_additional_coverage.py::TestSecurityManagerAdditionalCoverage::test_report_violation_rate_limit_severity
            severity = SecurityLevel.LOW

        await self._log_security_event(
            violation,
            peer_id,
            ip,
            severity,
            description,
            metadata or {},
        )

        # Auto-blacklist for critical violations
        if violation in [ThreatType.DDOS_ATTACK, ThreatType.MALICIOUS_PEER]:
            reputation.is_blacklisted = True
            # Use add_to_blacklist with violation source and optional expiration
            expires_in = None
            if self._default_expiration_hours:
                expires_in = self._default_expiration_hours * 3600.0
            self.add_to_blacklist(ip, description, expires_in=expires_in, source="violation")

    def add_to_blacklist(
        self,
        ip: str,
        reason: str = "",
        expires_in: float | None = None,
        source: str = "manual",
    ) -> None:
        """Add IP to blacklist.

        Args:
            ip: IP address to blacklist
            reason: Reason for blacklisting
            expires_in: Seconds until expiration (None = permanent)
            source: Source of blacklist entry ("manual", "auto", "reputation", "violation")

        """
        expires_at = None
        if expires_in:
            expires_at = time.time() + expires_in

        entry = BlacklistEntry(
            ip=ip,
            reason=reason,
            added_at=time.time(),
            expires_at=expires_at,
            source=source,
        )

        self.blacklist_entries[ip] = entry
        self.stats["blacklisted_peers"] = len(self.blacklist_entries)

        # Also add to IP filter if enabled
        if self.ip_filter and self.ip_filter.enabled:
            from ccbt.security.ip_filter import FilterMode

            self.ip_filter.add_rule(
                f"{ip}/32", mode=FilterMode.BLOCK, source="blacklist"
            )

        # Emit blacklist event
        try:
            loop = asyncio.get_running_loop()
            _ = loop.create_task(  # noqa: RUF006
                emit_event(
                    Event(
                        event_type=EventType.SECURITY_BLACKLIST_ADDED.value,
                        data={
                            "ip": ip,
                            "reason": reason,
                            "timestamp": time.time(),
                        },
                    ),
                )
            )
        except RuntimeError:  # Tested in test_security_manager_additional_coverage.py::TestSecurityManagerAdditionalCoverage::test_add_to_blacklist_no_event_loop
            # No event loop running, skip event emission
            pass

        # Auto-save blacklist (fire-and-forget)
        try:
            loop = asyncio.get_running_loop()
            _ = loop.create_task(self.save_blacklist())  # noqa: RUF006
        except RuntimeError:
            # No event loop running, skip auto-save
            pass

    def remove_from_blacklist(self, ip: str) -> None:
        """Remove IP from blacklist."""
        self.blacklist_entries.pop(ip, None)
        self.stats["blacklisted_peers"] = len(self.blacklist_entries)

        # Emit blacklist removal event
        try:
            loop = asyncio.get_running_loop()
            _ = loop.create_task(  # noqa: RUF006
                emit_event(
                    Event(
                        event_type=EventType.SECURITY_BLACKLIST_REMOVED.value,
                        data={
                            "ip": ip,
                            "timestamp": time.time(),
                        },
                    ),
                )
            )
        except RuntimeError:  # Tested in test_security_manager_additional_coverage.py::TestSecurityManagerAdditionalCoverage::test_remove_from_blacklist_no_event_loop
            # No event loop running, skip event emission
            pass

        # Auto-save blacklist (fire-and-forget)
        try:
            loop = asyncio.get_running_loop()
            _ = loop.create_task(self.save_blacklist())  # noqa: RUF006
        except RuntimeError:
            # No event loop running, skip auto-save
            pass

    def add_to_whitelist(self, ip: str, reason: str = "") -> None:
        """Add IP to whitelist."""
        self.ip_whitelist.add(ip)
        self.stats["whitelisted_peers"] += 1

        # Emit whitelist event
        try:
            loop = asyncio.get_running_loop()
            _ = loop.create_task(  # noqa: RUF006
                emit_event(
                    Event(
                        event_type=EventType.SECURITY_WHITELIST_ADDED.value,
                        data={
                            "ip": ip,
                            "reason": reason,
                            "timestamp": time.time(),
                        },
                    ),
                )
            )
        except RuntimeError:  # Tested in test_security_manager_additional_coverage.py::TestSecurityManagerAdditionalCoverage::test_add_to_whitelist_no_event_loop
            # No event loop running, skip event emission
            pass

    def remove_from_whitelist(self, ip: str) -> None:
        """Remove IP from whitelist."""
        self.ip_whitelist.discard(ip)

        # Emit whitelist removal event
        try:
            loop = asyncio.get_running_loop()
            _ = loop.create_task(  # noqa: RUF006
                emit_event(
                    Event(
                        event_type=EventType.SECURITY_WHITELIST_REMOVED.value,
                        data={
                            "ip": ip,
                            "timestamp": time.time(),
                        },
                    ),
                )
            )
        except RuntimeError:  # Tested in test_security_manager_additional_coverage.py::TestSecurityManagerAdditionalCoverage::test_remove_from_whitelist_no_event_loop
            # No event loop running, skip event emission
            pass

    @property
    def ip_blacklist(self) -> set[str]:
        """Get blacklisted IPs as a set (backward compatibility).

        Returns:
            Set of blacklisted IP addresses (excluding expired entries)
        """
        current_time = time.time()
        return {
            ip
            for ip, entry in self.blacklist_entries.items()
            if entry.expires_at is None or entry.expires_at > current_time
        }

    async def save_blacklist(self, blacklist_file: Path | None = None) -> None:
        """Save blacklist to persistent storage.

        Args:
            blacklist_file: Path to blacklist file (uses default if None)

        """
        if blacklist_file is None:
            from ccbt.daemon.daemon_manager import _get_daemon_home_dir

            home_dir = _get_daemon_home_dir()
            blacklist_file = home_dir / ".ccbt" / "security" / "blacklist.json"
            self.blacklist_file = blacklist_file
        else:
            self.blacklist_file = blacklist_file

        blacklist_file = Path(blacklist_file).expanduser()
        blacklist_file.parent.mkdir(parents=True, exist_ok=True)

        # Filter out expired entries before saving
        current_time = time.time()
        active_entries = {
            ip: entry
            for ip, entry in self.blacklist_entries.items()
            if entry.expires_at is None or entry.expires_at > current_time
        }

        data = {
            "version": 1,
            "entries": [
                {
                    "ip": entry.ip,
                    "reason": entry.reason,
                    "added_at": entry.added_at,
                    "expires_at": entry.expires_at,
                    "source": entry.source,
                }
                for entry in active_entries.values()
            ],
            "metadata": {
                "last_updated": time.time(),
                "count": len(active_entries),
            },
        }

        try:
            # Atomic write: write to temp file, then rename
            temp_file = blacklist_file.with_suffix(".tmp")
            async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, indent=2))
            temp_file.replace(blacklist_file)
            logger.info(
                "Saved blacklist with %d IPs to %s", len(active_entries), blacklist_file
            )
        except Exception as e:
            logger.warning("Failed to save blacklist to %s: %s", blacklist_file, e)
            # Clean up temp file if it exists
            temp_file = blacklist_file.with_suffix(".tmp")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    async def load_blacklist(self, blacklist_file: Path | None = None) -> None:
        """Load blacklist from persistent storage.

        Args:
            blacklist_file: Path to blacklist file (uses default if None)

        """
        if blacklist_file is None:
            from ccbt.daemon.daemon_manager import _get_daemon_home_dir

            home_dir = _get_daemon_home_dir()
            blacklist_file = home_dir / ".ccbt" / "security" / "blacklist.json"
            self.blacklist_file = blacklist_file
        else:
            self.blacklist_file = blacklist_file

        blacklist_file = Path(blacklist_file).expanduser()

        if not blacklist_file.exists():
            logger.debug("Blacklist file not found, starting with empty blacklist")
            return

        try:
            import ipaddress

            async with aiofiles.open(blacklist_file, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            # Handle version 1 format
            if "version" in data and data["version"] == 1:
                entries_data = data.get("entries", [])
            else:
                # Legacy format: just list of IPs
                entries_data = [{"ip": ip} for ip in data.get("ips", [])]

            loaded_count = 0
            for entry_data in entries_data:
                ip = entry_data.get("ip", "")
                if not ip:
                    continue

                # Validate IP address
                try:
                    ipaddress.ip_address(ip)
                except ValueError:
                    logger.warning("Invalid IP address in blacklist: %s", ip)
                    continue

                # Create BlacklistEntry
                entry = BlacklistEntry(
                    ip=ip,
                    reason=entry_data.get("reason", ""),
                    added_at=entry_data.get("added_at", time.time()),
                    expires_at=entry_data.get("expires_at"),
                    source=entry_data.get("source", "persisted"),
                )

                # Only add if not expired
                if not entry.is_expired():
                    self.blacklist_entries[ip] = entry
                    loaded_count += 1

            self.stats["blacklisted_peers"] = len(self.blacklist_entries)
            logger.info("Loaded %d IPs from blacklist file", loaded_count)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse blacklist file %s: %s", blacklist_file, e)
        except Exception as e:
            logger.warning("Failed to load blacklist from %s: %s", blacklist_file, e)

    def get_peer_reputation(self, peer_id: str, _ip: str) -> PeerReputation | None:
        """Get peer reputation."""
        return self.peer_reputations.get(peer_id)

    def get_blacklisted_ips(self) -> set[str]:
        """Get blacklisted IPs."""
        return self.ip_blacklist.copy()  # Uses computed property

    def get_whitelisted_ips(self) -> set[str]:
        """Get whitelisted IPs."""
        return self.ip_whitelist.copy()

    def is_ip_blacklisted(self, ip: str) -> bool:
        """Check if IP is blacklisted."""
        return ip in self.ip_blacklist

    def is_ip_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted."""
        return ip in self.ip_whitelist

    def get_security_events(self, limit: int = 100) -> list[SecurityEvent]:
        """Get recent security events."""
        return list(self.security_events)[-limit:]

    def get_security_statistics(self) -> dict[str, Any]:
        """Get security statistics."""
        return {
            "total_connections": self.stats["total_connections"],
            "blocked_connections": self.stats["blocked_connections"],
            "security_events": self.stats["security_events"],
            "blacklisted_peers": self.stats["blacklisted_peers"],
            "whitelisted_peers": self.stats["whitelisted_peers"],
            "blacklist_size": len(self.ip_blacklist),
            "whitelist_size": len(self.ip_whitelist),
            "reputation_tracking": len(self.peer_reputations),
        }

    def _get_peer_reputation(self, peer_id: str, ip: str) -> PeerReputation:
        """Get or create peer reputation."""
        if peer_id not in self.peer_reputations:
            self.peer_reputations[peer_id] = PeerReputation(
                peer_id=peer_id,
                ip=ip,
                first_seen=time.time(),
                last_seen=time.time(),
            )
        return self.peer_reputations[peer_id]

    async def _check_rate_limits(self, ip: str) -> bool:
        """Check if IP is within rate limits."""
        current_time = time.time()

        # Check connection rate
        connection_rate = self.connection_rates[ip]
        while connection_rate and connection_rate[0] < current_time - 60:
            connection_rate.popleft()

        if len(connection_rate) >= self.max_connections_per_minute:
            return False

        # Check message rate
        message_rate = self.message_rates[ip]
        while message_rate and message_rate[0] < current_time - 60:
            message_rate.popleft()

        if len(message_rate) >= self.max_messages_per_minute:
            return False

        # Check bytes rate
        bytes_rate = self.bytes_rates[ip]
        while bytes_rate and bytes_rate[0] < current_time - 60:
            bytes_rate.popleft()

        total_bytes = sum(bytes_rate)
        return not total_bytes >= self.max_bytes_per_minute

    def _update_connection_rate(self, ip: str) -> None:
        """Update connection rate tracking."""
        self.connection_rates[ip].append(time.time())

    def _update_message_rate(self, ip: str) -> None:
        """Update message rate tracking."""
        self.message_rates[ip].append(time.time())

    def _update_bytes_rate(self, ip: str, bytes_count: int) -> None:
        """Update bytes rate tracking."""
        self.bytes_rates[ip].append(bytes_count)

    async def _log_security_event(
        self,
        event_type: ThreatType,
        peer_id: str,
        ip: str,
        severity: SecurityLevel,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a security event."""
        event = SecurityEvent(
            event_type=event_type,
            peer_id=peer_id,
            ip=ip,
            severity=severity,
            description=description,
            timestamp=time.time(),
            metadata=metadata or {},
        )

        self.security_events.append(event)
        self.stats["security_events"] += 1

        # Emit security event
        await emit_event(
            Event(
                event_type=EventType.SECURITY_EVENT.value,
                data={
                    "threat_type": event_type.value,
                    "peer_id": peer_id,
                    "ip": ip,
                    "severity": severity.value,
                    "description": description,
                    "metadata": metadata or {},
                    "timestamp": time.time(),
                },
            ),
        )

    def cleanup_old_data(self, max_age_seconds: int = 3600) -> None:
        """Clean up old reputation and rate data."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        # Clean up old peer reputations
        to_remove = []
        for peer_id, reputation in self.peer_reputations.items():
            if reputation.last_seen < cutoff_time:
                to_remove.append(peer_id)

        for peer_id in to_remove:
            del self.peer_reputations[peer_id]

        # Clean up old rate data
        for ip in list(self.connection_rates.keys()):
            connection_rate = self.connection_rates[ip]
            while connection_rate and connection_rate[0] < cutoff_time:
                connection_rate.popleft()

            if not connection_rate:  # pragma: no cover - Empty connection rate cleanup, tested via non-empty rates
                del self.connection_rates[ip]

        for ip in list(self.message_rates.keys()):
            message_rate = self.message_rates[ip]
            while message_rate and message_rate[0] < cutoff_time:
                message_rate.popleft()

            if not message_rate:  # pragma: no cover - Empty message rate cleanup, tested via non-empty rates
                del self.message_rates[ip]

        for ip in list(self.bytes_rates.keys()):
            bytes_rate = self.bytes_rates[ip]
            while bytes_rate and bytes_rate[0] < cutoff_time:
                bytes_rate.popleft()

            if not bytes_rate:  # pragma: no cover - Empty bytes rate cleanup, tested via non-empty rates
                del self.bytes_rates[ip]

    async def cleanup_expired_entries(self) -> int:
        """Remove expired blacklist entries.

        Returns:
            Number of expired entries removed

        """
        expired = [
            ip for ip, entry in self.blacklist_entries.items() if entry.is_expired()
        ]

        for ip in expired:
            self.blacklist_entries.pop(ip, None)

        if expired:
            self.stats["blacklisted_peers"] = len(self.blacklist_entries)
            logger.info("Cleaned up %d expired blacklist entries", len(expired))
            # Save after cleanup
            try:
                await self.save_blacklist()
            except Exception as e:
                logger.warning("Failed to save blacklist after cleanup: %s", e)

        return len(expired)

    async def load_ip_filter(self, config: Any) -> None:
        """Load and initialize IP filter from configuration.

        Args:
            config: Configuration object with ip_filter settings

        """
        from ccbt.security.ip_filter import FilterMode, IPFilter

        # Get IP filter config
        ip_filter_config = getattr(getattr(config, "security", None), "ip_filter", None)
        if not ip_filter_config:
            logger.debug("IP filter config not found, skipping initialization")
            return

        # Create IP filter instance
        filter_mode = FilterMode.BLOCK
        if hasattr(ip_filter_config, "filter_mode"):
            mode_str = ip_filter_config.filter_mode.lower()
            if mode_str == "allow":
                filter_mode = FilterMode.ALLOW

        self.ip_filter = IPFilter(
            enabled=getattr(ip_filter_config, "enable_ip_filter", False),
            mode=filter_mode,
        )

        if not self.ip_filter.enabled:
            logger.debug("IP filter is disabled")
            return

        logger.info("Loading IP filter...")

        # Load filter files
        filter_files = getattr(ip_filter_config, "filter_files", [])
        for file_path in filter_files:
            if file_path:
                loaded, errors = await self.ip_filter.load_from_file(file_path)
                logger.info(
                    "Loaded %d rules from %s (%d errors)", loaded, file_path, errors
                )

        # Load filter URLs
        filter_urls = getattr(ip_filter_config, "filter_urls", [])
        cache_dir = getattr(ip_filter_config, "filter_cache_dir", "~/.ccbt/filters")
        update_interval = getattr(ip_filter_config, "filter_update_interval", 86400.0)

        if filter_urls:
            # Initial load
            await self.ip_filter.update_filter_lists(
                filter_urls, cache_dir, update_interval
            )

            # Start auto-update if configured
            await self.ip_filter.start_auto_update(
                filter_urls, cache_dir, update_interval
            )

        logger.info("IP filter loaded: %d rules", len(self.ip_filter.rules))

        # Load and initialize blacklist
        await self._initialize_blacklist(config)

    async def _initialize_blacklist(self, config: Any) -> None:
        """Initialize blacklist from configuration.

        Args:
            config: Configuration object with blacklist settings

        """
        # Get blacklist config
        blacklist_config = getattr(getattr(config, "security", None), "blacklist", None)
        if not blacklist_config:
            logger.debug("Blacklist config not found, skipping initialization")
            return

        # Store default expiration for auto-blacklisting
        self._default_expiration_hours = getattr(
            blacklist_config, "default_expiration_hours", None
        )

        # Load blacklist from file if persistence enabled
        if getattr(blacklist_config, "enable_persistence", True):
            blacklist_file = getattr(blacklist_config, "blacklist_file", None)
            if blacklist_file:
                blacklist_file = Path(blacklist_file).expanduser()
            await self.load_blacklist(blacklist_file)

        # Initialize auto-update if enabled OR if local source is enabled
        local_source_config = getattr(blacklist_config, "local_source", None)
        local_source_enabled = (
            local_source_config and getattr(local_source_config, "enabled", False)
        )
        if getattr(blacklist_config, "auto_update_enabled", False) or local_source_enabled:
            await self.initialize_blacklist_updater(blacklist_config)

    async def initialize_blacklist_updater(self, blacklist_config: Any) -> None:
        """Initialize blacklist updater from configuration.

        Args:
            blacklist_config: BlacklistConfig instance

        """
        from ccbt.security.blacklist_updater import BlacklistUpdater

        update_interval = getattr(blacklist_config, "auto_update_interval", 3600.0)
        sources = getattr(blacklist_config, "auto_update_sources", [])
        local_source_config = getattr(blacklist_config, "local_source", None)

        # Initialize even if no external sources (for local source support)
        if not sources and not (local_source_config and getattr(local_source_config, "enabled", False)):
            logger.debug("No blacklist update sources configured")
            return

        self.blacklist_updater = BlacklistUpdater(
            self,
            update_interval=update_interval,
            sources=sources,
            local_source_config=local_source_config,
        )

        await self.blacklist_updater.start_auto_update()

        # Start periodic cleanup task
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(3600)  # Check every hour
                    await self.cleanup_expired_entries()
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Error in blacklist cleanup task")
                    await asyncio.sleep(60)  # Retry after 1 minute

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Started blacklist cleanup task")

    async def _record_violation_for_local_blacklist(
        self, peer_id: str, ip: str, violation: ThreatType
    ) -> None:
        """Record violation for local blacklist source.

        Args:
            peer_id: Peer identifier
            ip: IP address
            violation: Violation type

        """
        if self.blacklist_updater:
            local_source = getattr(self.blacklist_updater, "_local_source", None)
            if local_source:
                await local_source.record_metric(
                    ip,
                    "violation",
                    1.0,
                    metadata={"violation_type": violation.value, "peer_id": peer_id},
                )

    async def _record_activity_for_local_blacklist(
        self, peer_id: str, ip: str, success: bool
    ) -> None:
        """Record peer activity for local blacklist source.

        Args:
            peer_id: Peer identifier
            ip: IP address
            success: Whether connection was successful

        """
        if self.blacklist_updater:
            local_source = getattr(self.blacklist_updater, "_local_source", None)
            if local_source:
                metric_type = "connection_success" if success else "connection_attempt"
                await local_source.record_metric(
                    ip,
                    metric_type,
                    1.0,
                    metadata={"peer_id": peer_id, "success": success},
                )
