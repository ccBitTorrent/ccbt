"""Unit tests for authenticated swarm trust-store parsing."""

from __future__ import annotations

import json

import pytest

from ccbt.security.swarm_trust_store import (
    SwarmTrustAnchor,
    SwarmTrustStore,
    current_swarm_anchors,
    load_swarm_trust_store,
    parse_swarm_trust_store,
)

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_parse_trust_store_supports_direct_swarm_map() -> None:
    payload = {
        "version": 1,
        "01234567-89ab-cdef-0123-456789abcdef": [
            {
                "type": "spki_sha256",
                "value": "a" * 64,
                "source": "unit-test",
            },
        ],
    }

    store = parse_swarm_trust_store(payload)

    anchors = store.anchors_for("01234567-89ab-cdef-0123-456789abcdef")
    assert len(anchors) == 1
    assert anchors[0].type == "spki_sha256"


def test_parse_trust_store_rejects_unknown_anchor_type() -> None:
    payload = {
        "version": 1,
        "01234567-89ab-cdef-0123-456789abcdef": [
            {"type": "unsupported", "value": "deadbeef"},
        ],
    }

    with pytest.raises(ValueError):
        parse_swarm_trust_store(payload)


def test_parse_trust_store_loads_from_file(tmp_path) -> None:
    payload = {
        "version": 2,
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": [
            {"type": "cert_sha256", "value": "b" * 64},
        ],
    }
    path = tmp_path / "trust-store.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    store = load_swarm_trust_store(path)

    anchors = store.anchors_for(
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    assert len(anchors) == 1
    assert anchors[0].type == "cert_sha256"


def test_current_swarm_anchors_filters_by_expiration_and_not_before() -> None:
    anchor_active = SwarmTrustAnchor(
        type="spki_sha256",
        value="11" * 32,
        not_before=900,
        expires_at=1100,
    )
    anchor_expired = SwarmTrustAnchor(
        type="spki_sha256",
        value="22" * 32,
        expires_at=50,
    )
    anchor_future = SwarmTrustAnchor(
        type="ed25519_pubkey_hex",
        value="33" * 32,
        not_before=6000,
    )

    store = SwarmTrustStore(
        version=1,
        swarm_anchors={
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": [
                anchor_active,
                anchor_expired,
                anchor_future,
            ]
        },
    )
    filtered = current_swarm_anchors(
        store,
        "aaaaaaaa" * 8,
        now=1000,
    )
    assert filtered == [anchor_active]

    inactive = current_swarm_anchors(
        store,
        "aaaaaaaa" * 8,
        now=10,
    )
    assert inactive == [anchor_expired]

    inactive = current_swarm_anchors(
        store,
        "aaaaaaaa" * 8,
        now=5000,
    )
    assert inactive == []
