"""Typed model and parser for authenticated swarm trust-material manifests."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from ccbt.security.swarm_auth_policy import SWARM_AUTH_TRUSTSTORE_RELOAD_TOTAL
from ccbt.security.swarm_identity import canonicalize_swarm_id

SUPPORTED_ANCHOR_TYPES = {
    "spki_sha256",
    "cert_sha256",
    "ed25519_pubkey_hex",
}


def _record_truststore_reload_metric(source: Union[str, Path], status: str) -> None:
    """Record trust-store reload activity for optional telemetry."""
    try:
        from ccbt.monitoring import get_metrics_collector
        from ccbt.monitoring.metrics_collector import MetricLabel

        get_metrics_collector().increment_counter(
            SWARM_AUTH_TRUSTSTORE_RELOAD_TOTAL,
            labels=[
                MetricLabel(name="source", value=str(source)),
                MetricLabel(name="status", value=str(status)),
            ],
        )
    except Exception:  # pragma: no cover
        return


@dataclass(frozen=True)
class SwarmTrustAnchor:
    """Single trust anchor entry for a swarm id."""

    type: str
    value: str
    expires_at: Optional[int] = None
    not_before: Optional[int] = None
    source: Optional[str] = None

    def is_current(self, now: Optional[int] = None) -> bool:
        """Return True if the anchor is within optional validity bounds."""
        current = int(now if now is not None else time.time())
        if self.not_before is not None and current < self.not_before:
            return False
        return not (self.expires_at is not None and current > self.expires_at)


@dataclass(frozen=True)
class SwarmTrustStore:
    """Parsed trust store payload."""

    version: int
    swarm_anchors: dict[str, list[SwarmTrustAnchor]] = field(default_factory=dict)

    def anchors_for(self, swarm_id: str) -> list[SwarmTrustAnchor]:
        """Return anchors for a swarm id (canonicalized input)."""
        canonical = canonicalize_swarm_id(swarm_id)
        return self.swarm_anchors.get(canonical, [])


def _coerce_anchor(entry: Mapping[str, Any]) -> SwarmTrustAnchor:
    anchor_type = entry.get("type")
    if not isinstance(anchor_type, str):
        msg = "trust anchor missing string 'type'"
        raise TypeError(msg)
    if anchor_type not in SUPPORTED_ANCHOR_TYPES:
        msg = f"unsupported trust anchor type: {anchor_type}"
        raise ValueError(msg)

    value = entry.get("value")
    if not isinstance(value, str) or not value:
        msg = "trust anchor missing non-empty string 'value'"
        raise TypeError(msg)

    expires_at = entry.get("expires_at")
    if expires_at is not None and not isinstance(expires_at, int):
        msg = "'expires_at' must be integer if provided"
        raise ValueError(msg)

    not_before = entry.get("not_before")
    if not_before is not None and not isinstance(not_before, int):
        msg = "'not_before' must be integer if provided"
        raise ValueError(msg)

    source = entry.get("source")
    if source is not None and not isinstance(source, str):
        msg = "'source' must be string if provided"
        raise ValueError(msg)

    return SwarmTrustAnchor(
        type=anchor_type,
        value=value,
        expires_at=expires_at,
        not_before=not_before,
        source=source,
    )


def parse_swarm_trust_store(payload: Mapping[str, Any]) -> SwarmTrustStore:
    """Parse and validate trust material payload."""
    if not isinstance(payload, Mapping):
        msg = "trust store payload must be a mapping"
        raise TypeError(msg)

    raw_version = payload.get("version", 1)
    try:
        version = int(raw_version)
    except (TypeError, ValueError) as exc:
        msg = "trust store 'version' must be an integer"
        raise ValueError(msg) from exc
    if version <= 0:
        msg = "trust store version must be positive"
        raise ValueError(msg)

    raw_swarm_map: Mapping[str, Any]
    if "swarm_anchors" in payload:
        raw_swarm_map = payload["swarm_anchors"]
        if not isinstance(raw_swarm_map, Mapping):
            msg = "'swarm_anchors' must be a mapping"
            raise TypeError(msg)
    else:
        raw_swarm_map = {
            key: value for key, value in payload.items() if key not in {"version"}
        }

    anchors_by_swarm: dict[str, list[SwarmTrustAnchor]] = {}
    for swarm_id, raw_anchors in raw_swarm_map.items():
        if not isinstance(swarm_id, str):
            msg = "swarm id keys must be strings"
            raise TypeError(msg)
        canonical = canonicalize_swarm_id(swarm_id)
        if not isinstance(raw_anchors, list):
            msg = f"anchors for swarm {swarm_id} must be a list"
            raise TypeError(msg)

        anchors: list[SwarmTrustAnchor] = []
        for anchor_entry in raw_anchors:
            if not isinstance(anchor_entry, Mapping):
                msg = f"anchor entry for swarm {swarm_id} must be an object"
                raise TypeError(msg)
            anchors.append(_coerce_anchor(anchor_entry))
        anchors_by_swarm[canonical] = anchors

    return SwarmTrustStore(version=version, swarm_anchors=anchors_by_swarm)


def load_swarm_trust_store(source: Union[str, Path]) -> SwarmTrustStore:
    """Load a trust store JSON file from disk."""
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            msg = "trust store file must contain a JSON object"
            raise TypeError(msg)
        store = parse_swarm_trust_store(raw)
        _record_truststore_reload_metric(path, "success")
        return store
    except Exception:
        _record_truststore_reload_metric(path, "failure")
        raise


def merge_swarm_anchor_maps(
    base: Mapping[str, list[SwarmTrustAnchor]],
    updates: Mapping[str, list[SwarmTrustAnchor]],
) -> dict[str, list[SwarmTrustAnchor]]:
    """Merge anchor maps with updates taking precedence by swarm id."""
    merged: dict[str, list[SwarmTrustAnchor]] = {}
    merged.update({key: list(value) for key, value in base.items()})
    for key, value in updates.items():
        merged[key] = list(value)
    return merged


def current_swarm_anchors(
    store: SwarmTrustStore,
    swarm_id: str,
    *,
    now: Optional[int] = None,
) -> list[SwarmTrustAnchor]:
    """Return currently valid anchors for a swarm id."""
    return [
        anchor for anchor in store.anchors_for(swarm_id) if anchor.is_current(now=now)
    ]
