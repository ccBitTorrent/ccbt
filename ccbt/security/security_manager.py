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
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from ccbt.events import Event, EventType, emit_event

if TYPE_CHECKING:
    from ccbt.models import PeerInfo


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
        else:
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
        self.ip_blacklist: set[str] = set()
        self.ip_whitelist: set[str] = set()
        self.security_events: deque = deque(maxlen=10000)

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

        # Check IP blacklist
        if ip in self.ip_blacklist:
            await self._log_security_event(
                ThreatType.MALICIOUS_PEER,
                peer_id,
                ip,
                SecurityLevel.HIGH,
                f"Connection blocked: IP {ip} is blacklisted",
            )
            return False, "IP is blacklisted"

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

        # Check for auto-blacklisting
        if reputation.reputation_score < self.auto_blacklist_threshold:
            reputation.is_blacklisted = True
            self.ip_blacklist.add(ip)
            self.stats["blacklisted_peers"] += 1

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

        # Determine severity
        severity = SecurityLevel.MEDIUM
        if violation in [ThreatType.DDOS_ATTACK, ThreatType.MALICIOUS_PEER]:
            severity = SecurityLevel.CRITICAL
        elif violation == ThreatType.RATE_LIMIT_EXCEEDED:
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
            self.ip_blacklist.add(ip)
            self.stats["blacklisted_peers"] += 1

    def add_to_blacklist(self, ip: str, reason: str = "") -> None:
        """Add IP to blacklist."""
        self.ip_blacklist.add(ip)
        self.stats["blacklisted_peers"] += 1

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
        except RuntimeError:
            # No event loop running, skip event emission
            pass

    def remove_from_blacklist(self, ip: str) -> None:
        """Remove IP from blacklist."""
        self.ip_blacklist.discard(ip)

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
        except RuntimeError:
            # No event loop running, skip event emission
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
        except RuntimeError:
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
        except RuntimeError:
            # No event loop running, skip event emission
            pass

    def get_peer_reputation(self, peer_id: str, _ip: str) -> PeerReputation | None:
        """Get peer reputation."""
        return self.peer_reputations.get(peer_id)

    def get_blacklisted_ips(self) -> set[str]:
        """Get blacklisted IPs."""
        return self.ip_blacklist.copy()

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

            if not connection_rate:
                del self.connection_rates[ip]

        for ip in list(self.message_rates.keys()):
            message_rate = self.message_rates[ip]
            while message_rate and message_rate[0] < cutoff_time:
                message_rate.popleft()

            if not message_rate:
                del self.message_rates[ip]

        for ip in list(self.bytes_rates.keys()):
            bytes_rate = self.bytes_rates[ip]
            while bytes_rate and bytes_rate[0] < cutoff_time:
                bytes_rate.popleft()

            if not bytes_rate:
                del self.bytes_rates[ip]
