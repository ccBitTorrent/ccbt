"""Authenticated swarm proof contract helpers.

This module provides a minimal implementation of the proof payload
contract for swarm admission work:

- schema-aware marshal/unmarshal for the `e.swarm_auth` dictionary fields
- canonical signed-payload construction
- signature verification against a provided verifier
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Sequence, Union

from ccbt.security.swarm_identity import canonicalize_swarm_id

SWARM_AUTH_VERSION = 1
SWARM_AUTH_PREFIX = b"CCBT-SWARM-AUTH-v1"

ALLOWED_TRANSPORT_HINTS = frozenset({"plain", "mse", "mse_pe", "ssl", "tls", "other"})
ALLOWED_TRUST_PROOF_HINTS = frozenset({"spki_sha256", "cert_sha256"})


def _encode_base64url(data: bytes) -> str:
    """Encode bytes using URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode_base64url(value: str) -> bytes:
    """Decode URL-safe base64 and tolerate omitted padding."""
    if not isinstance(value, str):
        msg = "base64url value must be a string"
        raise TypeError(msg)
    value_str = value.strip()
    padding = "=" * ((4 - (len(value_str) % 4)) % 4)
    return base64.urlsafe_b64decode((value_str + padding).encode("ascii"))


def _normalize_transport_hint(transport_hint: str) -> str:
    """Normalize transport hint into a deterministic value."""
    hint = transport_hint.strip().lower().replace("-", "_")
    if not hint:
        return "other"
    if hint in ALLOWED_TRANSPORT_HINTS:
        return hint
    return "other"


def _resolve_info_hash_family(
    info_hash: Union[bytes, Sequence[bytes | None], tuple[bytes | None, bytes | None]],
) -> bytes:
    """Resolve the protocol-specific info-hash family bytes for signing."""
    if isinstance(info_hash, (bytes, bytearray)):
        info_hash_bytes = bytes(info_hash)
        if len(info_hash_bytes) not in {20, 32}:
            msg = f"info_hash must be 20 or 32 bytes, got {len(info_hash_bytes)}"
            raise ValueError(msg)
        return info_hash_bytes

    if not isinstance(info_hash, (tuple, list)):
        msg = "info_hash must be bytes or a family tuple"
        raise TypeError(msg)

    normalized: list[bytes] = []
    for value in info_hash:
        if value is None:
            continue
        if not isinstance(value, (bytes, bytearray)):
            msg = "info_hash family elements must be bytes"
            raise TypeError(msg)
        candidate = bytes(value)
        if len(candidate) not in {20, 32}:
            msg = f"info_hash must be 20 or 32 bytes, got {len(candidate)}"
            raise ValueError(msg)
        normalized.append(candidate)

    if not normalized:
        msg = "info_hash family is empty"
        raise ValueError(msg)
    if len(normalized) == 1:
        return normalized[0]
    if len(normalized) != 2:
        msg = "info_hash family must contain at most two hashes"
        raise ValueError(msg)

    # Canonical v1/v2 family ordering is v1 20 bytes first, then v2 32 bytes.
    if {len(normalized[0]), len(normalized[1])} != {20, 32}:
        msg = "info_hash family must be one v1 and one v2 hash"
        raise ValueError(msg)
    if len(normalized[0]) == 20:
        v1, v2 = normalized
    else:
        v2, v1 = normalized
    return v1 + v2


@dataclass(frozen=True)
class SwarmAuthProof:
    """Parsed, validated swarm auth proof tuple."""

    version: int
    swarm_id: str
    public_key: bytes
    signature: bytes
    timestamp: int
    trust_proof_hint: Optional[str] = None

    def to_extension_dict(self) -> dict[str, Any]:
        """Return proof values in extension handshake shape."""
        payload: dict[str, Any] = {
            "v": self.version,
            "sid": self.swarm_id,
            "pk": _encode_base64url(self.public_key),
            "sig": _encode_base64url(self.signature),
            "ts": self.timestamp,
        }
        if self.trust_proof_hint is not None:
            payload["tp"] = self.trust_proof_hint
        return payload


def build_swarm_auth_message(
    swarm_id: str,
    peer_id: bytes,
    info_hash: Union[bytes, Sequence[bytes | None], tuple[bytes | None, bytes | None]],
    timestamp: int,
    transport_hint: str,
) -> bytes:
    """Build canonical signed payload for `swarm_auth`.

    Payload format:
    b"CCBT-SWARM-AUTH-v1" || sid_bytes || peer_id || info_hash || ts_le_u64 ||
    transport_hint
    """
    normalized_sid = canonicalize_swarm_id(swarm_id)
    if not isinstance(peer_id, (bytes, bytearray)):
        msg = "peer_id must be bytes"
        raise TypeError(msg)
    if len(peer_id) != 20:
        msg = f"peer_id must be 20 bytes, got {len(peer_id)}"
        raise ValueError(msg)
    info_hash_bytes = _resolve_info_hash_family(info_hash)
    if not isinstance(timestamp, int) or timestamp < 0:
        msg = f"timestamp must be a non-negative integer, got {timestamp!r}"
        raise ValueError(msg)

    normalized_hint = _normalize_transport_hint(transport_hint)
    sid_bytes = bytes.fromhex(normalized_sid)
    if len(sid_bytes) == 0:
        msg = "swarm_id must resolve to bytes"
        raise ValueError(msg)
    ts_bytes = int(timestamp).to_bytes(8, "little", signed=False)
    return (
        SWARM_AUTH_PREFIX
        + sid_bytes
        + peer_id
        + info_hash_bytes
        + ts_bytes
        + normalized_hint.encode("ascii")
    )


def parse_swarm_auth_dict(data: dict[str, Any]) -> SwarmAuthProof:
    """Parse and validate an e.swarm_auth dictionary."""
    try:
        version = int(data.get("v", 0))
    except (TypeError, ValueError) as exc:
        msg = "invalid swarm_auth version"
        raise ValueError(msg) from exc
    if version != SWARM_AUTH_VERSION:
        msg = f"unsupported swarm_auth version: {version}"
        raise ValueError(msg)

    swarm_id = data.get("sid")
    if not isinstance(swarm_id, str):
        msg = "swarm_auth sid must be a string"
        raise TypeError(msg)
    swarm_id = canonicalize_swarm_id(swarm_id)

    try:
        public_key = _decode_base64url(str(data["pk"]))
    except (KeyError, TypeError, ValueError) as exc:
        msg = "invalid swarm_auth pk"
        raise ValueError(msg) from exc
    if len(public_key) != 32:
        msg = "swarm_auth pk must be 32 bytes"
        raise ValueError(msg)

    try:
        signature = _decode_base64url(str(data["sig"]))
    except (KeyError, TypeError, ValueError) as exc:
        msg = "invalid swarm_auth sig"
        raise ValueError(msg) from exc
    if len(signature) != 64:
        msg = "swarm_auth sig must be 64 bytes"
        raise ValueError(msg)

    try:
        timestamp = int(data["ts"])
    except (KeyError, TypeError, ValueError) as exc:
        msg = "invalid swarm_auth ts"
        raise ValueError(msg) from exc
    if timestamp < 0:
        msg = "swarm_auth ts must be non-negative"
        raise ValueError(msg)

    trust_hint = data.get("tp")
    if trust_hint is None:
        trust_hint = None
    elif isinstance(trust_hint, str):
        if trust_hint not in ALLOWED_TRUST_PROOF_HINTS:
            msg = f"unsupported swarm_auth trust hint: {trust_hint}"
            raise ValueError(msg)
    else:
        msg = "swarm_auth tp must be a string"
        raise ValueError(msg)

    return SwarmAuthProof(
        version=version,
        swarm_id=swarm_id,
        public_key=public_key,
        signature=signature,
        timestamp=timestamp,
        trust_proof_hint=trust_hint,
    )


def build_swarm_auth_extension(
    *,
    swarm_id: str,
    public_key: bytes,
    signature: bytes,
    timestamp: int,
    trust_proof_hint: Optional[str] = None,
) -> dict[str, Any]:
    """Build BEP-10 extension payload value for key `e.swarm_auth`."""
    proof = SwarmAuthProof(
        version=SWARM_AUTH_VERSION,
        swarm_id=canonicalize_swarm_id(swarm_id),
        public_key=public_key,
        signature=signature,
        timestamp=timestamp,
        trust_proof_hint=trust_proof_hint,
    )
    if proof.version != SWARM_AUTH_VERSION:
        msg = "unsupported swarm_auth version"
        raise ValueError(msg)
    if len(proof.public_key) != 32:
        msg = "public_key must be 32 bytes"
        raise ValueError(msg)
    if len(proof.signature) != 64:
        msg = "signature must be 64 bytes"
        raise ValueError(msg)
    if (
        proof.trust_proof_hint is not None
        and proof.trust_proof_hint not in ALLOWED_TRUST_PROOF_HINTS
    ):
        msg = f"unsupported trust_proof_hint: {proof.trust_proof_hint}"
        raise ValueError(msg)
    return proof.to_extension_dict()


def verify_swarm_auth_signature(
    proof: SwarmAuthProof,
    peer_id: bytes,
    info_hash: Union[bytes, Sequence[bytes | None], tuple[bytes | None, bytes | None]],
    transport_hint: str,
    signer_verify: Callable[[bytes, bytes, bytes], bool],
) -> bool:
    """Verify `sig` over the canonical payload."""
    payload = build_swarm_auth_message(
        proof.swarm_id,
        peer_id=peer_id,
        info_hash=info_hash,
        timestamp=proof.timestamp,
        transport_hint=transport_hint,
    )
    return signer_verify(payload, proof.signature, proof.public_key)


def evaluate_swarm_auth_verification_order(
    *,
    raw_swarm_auth: Optional[dict[str, Any]],
    peer_id: bytes,
    info_hash: Union[bytes, Sequence[bytes | None], tuple[bytes | None, bytes | None]],
    transport_hint: str,
    signer_verify: Callable[[bytes, bytes, bytes], bool],
    trusted_swarm_ids: Iterable[str],
    now: Optional[float] = None,
    freshness_window_seconds: int = 300,
) -> tuple[bool, str]:
    """Evaluate proof with canonical verification steps.

    Returns `(allowed, reason_code)`.
    """
    if raw_swarm_auth is None:
        return False, "missing_schema"
    try:
        proof = parse_swarm_auth_dict(raw_swarm_auth)
    except ValueError:
        return False, "invalid_schema"

    # Trust lookup (step 2): strict allow by explicit allow-list.
    canonical_allowed = {canonicalize_swarm_id(item) for item in trusted_swarm_ids}
    if proof.swarm_id not in canonical_allowed:
        return False, "trust_lookup_failed"

    # Timestamp freshness (step 3)
    current = int(now if now is not None else time.time())
    age = abs(current - proof.timestamp)
    if age > freshness_window_seconds:
        return False, "timestamp_stale"

    # Certificate/key-chain binding is currently policy-level:
    # defer to caller-supplied trust set and verifier. Keep as a distinct step.
    if not verify_swarm_auth_signature(
        proof,
        peer_id=peer_id,
        info_hash=info_hash,
        transport_hint=transport_hint,
        signer_verify=signer_verify,
    ):
        return False, "invalid_signature"

    # Signature validation passed
    return True, "allow"
