"""Utilities for swarm identifier normalization and legacy fallback IDs."""

from __future__ import annotations

import base64
import re
import uuid
from hashlib import sha256
from typing import Optional

_HEX_PATTERN = re.compile(r"^[0-9a-f]+$")
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def canonicalize_swarm_id(raw_swarm_id: str) -> str:
    """Return a canonical lowercase-hex swarm identifier.

    Supported forms:
    - Hex strings (`...`) with optional `0x` prefix.
    - UUID-like identifiers (hyphens removed).
    - URL-safe base32 (`-`/`_`) with explicit migration decoding.
    """
    if not isinstance(raw_swarm_id, str):
        msg = "swarm_id must be a string"
        raise TypeError(msg)

    text = raw_swarm_id.strip()
    if not text:
        msg = "swarm_id must not be empty"
        raise ValueError(msg)

    candidate = text.strip().lower()
    if candidate.startswith("0x"):
        candidate = candidate[2:]
    if candidate == "":
        msg = "swarm_id must not be empty"
        raise ValueError(msg)

    if _UUID_PATTERN.fullmatch(candidate):
        return candidate.replace("-", "")

    if _HEX_PATTERN.fullmatch(candidate):
        return candidate

    if "-" in candidate or "_" in candidate:
        try:
            normalized = candidate.replace("-", "").replace("_", "").upper()
            return base64.b32decode(normalized, casefold=True).hex()
        except Exception as exc:  # pragma: no cover - fallback path
            msg = f"invalid base32/swarm_id payload: {raw_swarm_id}"
            raise ValueError(msg) from exc

    try:
        return uuid.UUID(candidate).hex
    except ValueError as err:
        msg = f"swarm_id must be hex, uuid, or base32-like; got {raw_swarm_id!r}"
        raise ValueError(msg) from err


def legacy_swarm_id_fallback(info_hash_family_bytes: bytes) -> str:
    """Generate deterministic legacy fallback swarm-id from canonical info-hash family bytes."""
    if not isinstance(info_hash_family_bytes, (bytes, bytearray)):
        msg = "info_hash_family_bytes must be raw bytes"
        raise TypeError(msg)
    if not info_hash_family_bytes:
        msg = "info_hash_family_bytes must not be empty"
        raise ValueError(msg)
    return sha256(b"ccbt-swarm:" + bytes(info_hash_family_bytes)).hexdigest()


def canonical_torrent_info_hash_family(
    *, info_hash_v1: Optional[bytes] = None, info_hash_v2: Optional[bytes] = None
) -> bytes:
    """Return canonical v1/v2 info-hash family bytes for deterministic fallback IDs."""
    if info_hash_v1 is None and info_hash_v2 is None:
        msg = "at least one info hash family member is required"
        raise ValueError(msg)

    if info_hash_v1 is not None and info_hash_v2 is not None:
        return bytes(info_hash_v1) + bytes(info_hash_v2)
    return bytes(info_hash_v1 or info_hash_v2)
