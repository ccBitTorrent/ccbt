"""Unit tests for certificate/key binding."""

from __future__ import annotations

from ccbt.security.swarm_certificate_binding import (
    CertificateBindingDecision,
    evaluate_certificate_binding,
)
from ccbt.security.swarm_trust_store import SwarmTrustAnchor

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_certificate_binding_accepts_matching_ed25519_anchor() -> None:
    public_key = bytes.fromhex("11" * 32)
    anchors = [
        SwarmTrustAnchor(type="ed25519_pubkey_hex", value=public_key.hex()),
    ]

    decision = evaluate_certificate_binding(
        public_key=public_key,
        trust_hint="spki_sha256",
        anchors=anchors,
        transport_hint="plain",
    )

    assert isinstance(decision, CertificateBindingDecision)
    assert decision.bound is False
    assert decision.reason_code == "no_matching_binding"


def test_certificate_binding_accepts_matching_spki_anchor() -> None:
    public_key = bytes.fromhex("22" * 32)
    import hashlib

    anchors = [
        SwarmTrustAnchor(
            type="spki_sha256",
            value=hashlib.sha256(public_key).hexdigest(),
        ),
    ]

    decision = evaluate_certificate_binding(
        public_key=public_key,
        trust_hint="spki_sha256",
        anchors=anchors,
        transport_hint="mse",
    )

    assert decision.bound
    assert decision.reason_code == "bound"
    assert decision.selected_anchor_type == "spki_sha256"
