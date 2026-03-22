"""Certificate/key binding helpers for authenticated swarm policy."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union

from ccbt.security.swarm_auth_contract import ALLOWED_TRUST_PROOF_HINTS

if TYPE_CHECKING:
    from ccbt.security.swarm_trust_store import SwarmTrustAnchor


@dataclass(frozen=True)
class CertificateBindingDecision:
    """Result of a binding check for a single connection."""

    bound: bool
    selected_anchor_type: Optional[str]
    reason_code: str


def _hash_public_key(public_key: bytes) -> str:
    """Return lowercase SHA-256 hex digest for a public key."""
    return hashlib.sha256(public_key).hexdigest()


def _normalize_anchor_value(value: str) -> str:
    """Normalize anchor value strings for matching."""
    return value.strip().lower().replace(" ", "")


def _decode_base64_maybe(value: str) -> Optional[bytes]:
    """Decode URL-safe/base64/hex values used by anchors."""
    normalized = value.strip()
    try:
        return base64.b64decode(normalized, validate=False)
    except Exception:
        try:
            return bytes.fromhex(normalized)
        except Exception:
            return None


def _anchor_value_matches(
    anchor: SwarmTrustAnchor,
    public_key: bytes,
    *,
    transport_hint: Optional[str]= None,
) -> bool:
    """Return True if a single anchor matches the presented key."""
    value = _normalize_anchor_value(anchor.value)
    if anchor.type == "ed25519_pubkey_hex":
        return value == public_key.hex()
    if anchor.type == "spki_sha256":
        return value == _hash_public_key(public_key)
    if anchor.type == "cert_sha256":
        if transport_hint == "tls":
            certificate_chain = _decode_base64_maybe(value)
            if certificate_chain is None:
                return False
            return _hash_public_key(certificate_chain) == _hash_public_key(public_key)
        return False
    return False


def evaluate_certificate_binding(
    *,
    public_key: bytes,
    trust_hint: Optional[str],
    anchors: list[SwarmTrustAnchor],
    transport_hint: str,
) -> CertificateBindingDecision:
    """Evaluate certificate/key binding for a parsed proof."""
    if trust_hint is not None and trust_hint not in ALLOWED_TRUST_PROOF_HINTS:
        return CertificateBindingDecision(
            bound=False,
            selected_anchor_type=None,
            reason_code="unsupported_trust_hint",
        )

    for anchor in anchors:
        if (
            trust_hint is not None and trust_hint not in (anchor.type, "cert_sha256")
        ):
            continue
        if trust_hint == "cert_sha256" and anchor.type not in {"cert_sha256"}:
            continue
        if _anchor_value_matches(
            anchor,
            public_key=public_key,
            transport_hint=transport_hint,
        ):
            return CertificateBindingDecision(
                bound=True,
                selected_anchor_type=anchor.type,
                reason_code="bound",
            )
    return CertificateBindingDecision(
        bound=False,
        selected_anchor_type=None,
        reason_code="no_matching_binding",
    )

