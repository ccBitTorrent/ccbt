"""Revoked swarm identity and trust-material tracking."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from ccbt.security.swarm_auth_policy import SWARM_AUTH_REVOCATION_HITS_TOTAL


@dataclass(frozen=True)
class SwarmRevocationProfile:
    """Parsed revocation policy content."""

    revoked_fingerprints: frozenset[str] = field(default_factory=frozenset)
    revoked_swarm_ids: frozenset[str] = field(default_factory=frozenset)
    reason_code: Optional[str] = None

    def is_revoked_swarm_id(self, swarm_id: str) -> bool:
        """Return True when the canonicalized swarm id is revoked."""
        if not isinstance(swarm_id, str):
            return False
        normalized = swarm_id.lower().strip()
        if normalized in self.revoked_swarm_ids:
            _record_revocation_hit("swarm_id")
            return True
        return False

    def is_revoked_fingerprint(self, fingerprint: str) -> bool:
        """Return True when fingerprint matches revocation list."""
        if not isinstance(fingerprint, str):
            return False
        normalized = fingerprint.lower().strip()
        if normalized in self.revoked_fingerprints:
            _record_revocation_hit("fingerprint")
            return True
        return False


def _record_revocation_hit(reason_type: str) -> None:
    """Record a revocation hit for optional telemetry."""
    try:
        from ccbt.monitoring import get_metrics_collector
        from ccbt.monitoring.metrics_collector import MetricLabel

        get_metrics_collector().increment_counter(
            SWARM_AUTH_REVOCATION_HITS_TOTAL,
            labels=[MetricLabel(name="type", value=str(reason_type))],
        )
    except Exception:  # pragma: no cover
        return


@dataclass(frozen=True)
class SwarmRevocationCache:
    """In-memory revocation cache with reload timestamp."""

    profile: SwarmRevocationProfile
    loaded_at: float
    source: Optional[str] = None

    def is_stale(self, now: Optional[float] = None, ttl_s: float = 60.0) -> bool:
        """Return True when cache has exceeded TTL."""
        current = time.time() if now is None else now
        return current - self.loaded_at > ttl_s


def parse_swarm_revocation_payload(
    payload: Mapping[str, Any],
) -> SwarmRevocationProfile:
    """Parse a revocation payload according to p0-8 schema."""
    if not isinstance(payload, Mapping):
        msg = "revocation payload must be a mapping"
        raise TypeError(msg)

    revoked_fingerprints = payload.get("revoked_fingerprints", [])
    if revoked_fingerprints is None:
        revoked_fingerprints = []
    revoked_swarm_ids = payload.get("revoked_swarm_ids", [])
    if revoked_swarm_ids is None:
        revoked_swarm_ids = []

    if not isinstance(revoked_fingerprints, list):
        msg = "'revoked_fingerprints' must be a list"
        raise TypeError(msg)
    if not isinstance(revoked_swarm_ids, list):
        msg = "'revoked_swarm_ids' must be a list"
        raise TypeError(msg)

    cleaned_fingerprints = [
        str(item).strip().lower() for item in revoked_fingerprints if str(item).strip()
    ]
    cleaned_swarm_ids = [
        str(item).strip().lower() for item in revoked_swarm_ids if str(item).strip()
    ]
    reason = payload.get("reason_code")
    if reason is not None:
        reason = str(reason)

    return SwarmRevocationProfile(
        revoked_fingerprints=frozenset(cleaned_fingerprints),
        revoked_swarm_ids=frozenset(cleaned_swarm_ids),
        reason_code=reason,
    )


def load_swarm_revocation_profile(source: Union[str, Path]) -> SwarmRevocationProfile:
    """Load revocation payload from JSON file."""
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        msg = "revocation payload must be a mapping"
        raise TypeError(msg)
    return parse_swarm_revocation_payload(raw)


def load_swarm_revocation_cache(
    source: Union[str, Path], *, stale_tolerant: bool = True
) -> tuple[SwarmRevocationCache | None, bool]:
    """Load revocation cache from source.

    Returns (cache, had_parse_error) so callers can apply fail-closed policy.
    """
    try:
        profile = load_swarm_revocation_profile(source)
        return SwarmRevocationCache(
            profile=profile, loaded_at=time.time(), source=str(source)
        ), False
    except Exception:
        if stale_tolerant:
            return None, True
        raise


def allow_after_parse_failure(
    *,
    strict_mode: bool,
    stale_cache_present: bool,
    parse_error: bool,
    fail_closed_on_parse_errors: bool = False,
) -> bool:
    """Return whether admission should continue after a parse/reload error."""
    if not parse_error:
        return True
    if strict_mode:
        return False
    if fail_closed_on_parse_errors:
        return False
    return stale_cache_present
