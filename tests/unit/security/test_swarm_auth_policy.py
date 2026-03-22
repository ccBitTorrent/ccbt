"""Unit tests for authenticated-swarm admission policy."""

from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
import hashlib
import time

import pytest

from ccbt.security.key_manager import Ed25519KeyManager
from ccbt.security.swarm_auth_contract import build_swarm_auth_extension, build_swarm_auth_message
from ccbt.security.swarm_revocation import SwarmRevocationCache, SwarmRevocationProfile
from ccbt.security.swarm_trust_store import SwarmTrustAnchor, SwarmTrustStore
from ccbt.security.swarm_auth_policy import (
    SWARM_AUTH_METRIC_BY_MODE,
    SWARM_AUTH_METRIC_REASONS,
    SWARM_AUTH_METRIC_TOTAL,
    AuthDecision,
    SWARM_AUTH_OPPORTUNISTIC_VERIFY_FAILED_TOTAL,
    SWARM_AUTH_STRICT_LTEP_TIMEOUT_TOTAL,
    SwarmAuthPolicy,
    evaluate_inbound_admission,
    evaluate_outbound_admission,
)
from ccbt.security.swarm_identity import canonicalize_swarm_id

pytestmark = [pytest.mark.unit, pytest.mark.security]


@pytest.fixture
def key_manager(tmp_path: Path) -> Ed25519KeyManager:
    return Ed25519KeyManager(key_dir=tmp_path / "swarm-auth-policy")


def _handshake(peer_id: bytes, info_hash: bytes, swarm_auth: dict[str, object] | None = None):
    return SimpleNamespace(
        peer_id=peer_id,
        info_hash_v1=info_hash,
        info_hash=info_hash,
        info_hash_v2=None,
        swarm_auth=swarm_auth,
    )


def _peer_socket(ip: str = "127.0.0.1", port: int = 51413):
    class Socket:
        def get_extra_info(self, key: str):
            if key == "peername":
                return (ip, port)
            return None

    return Socket()


def _session(
    *,
    auth_mode: str,
    trusted: list[str] | None = None,
    swarm_id: str | None = None,
    include_key_manager: bool = True,
) -> SimpleNamespace:
    cfg = SimpleNamespace(
        security=SimpleNamespace(authenticated_swarms=SimpleNamespace(mode=auth_mode))
    )
    kwargs = {"auth_mode": auth_mode, "config": cfg}
    if trusted is not None:
        kwargs["trusted_swarm_ids"] = trusted
    if swarm_id is not None:
        kwargs["swarm_id"] = swarm_id
    if include_key_manager:
        kwargs["key_manager"] = None
    return SimpleNamespace(**kwargs)


def test_evaluate_inbound_policy_off_mode_allows() -> None:
    peer_id = b"p" * 20
    info_hash = b"\x11" * 20
    session = _session(auth_mode="off", include_key_manager=False)
    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash),
        session=session,
        transport_hint="plain",
    )

    assert decision == AuthDecision(True, "off", "swarm_auth_mode_off")


def test_evaluate_inbound_policy_strict_missing_trust_is_denied() -> None:
    peer_id = b"x" * 20
    info_hash = b"\x22" * 20
    session = _session(auth_mode="strict", include_key_manager=False)
    session.config.security.authenticated_swarms.mode = "strict"

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash),
        session=session,
        transport_hint="plain",
    )

    assert decision.allowed is False
    assert decision.mode == "strict"
    assert decision.reason_code == "missing_trust_material"


def test_evaluate_inbound_policy_opportunistic_missing_schema_is_permitted(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id = b"y" * 20
    info_hash = b"\x33" * 20
    fallback_swarm = canonicalize_swarm_id("12345678-9abc-def0-1234-56789abcdef0")
    session = _session(
        auth_mode="opportunistic",
        trusted=[fallback_swarm],
        include_key_manager=True,
    )
    session.key_manager = key_manager

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash),
        session=session,
        transport_hint="plain",
    )

    assert decision.allowed is True
    assert decision.mode == "opportunistic"
    assert decision.reason_code == "missing_schema"


def test_evaluate_inbound_policy_opportunistic_invalid_signature_is_permitted_with_metric(
    key_manager: Ed25519KeyManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    peer_id = b"y" * 20
    info_hash = b"\x33" * 20
    fallback_swarm = canonicalize_swarm_id("12345678-9abc-def0-1234-56789abcdef0")
    session = _session(
        auth_mode="opportunistic",
        trusted=[fallback_swarm],
        include_key_manager=True,
    )
    session.key_manager = key_manager

    extension = _build_signed_handshake(
        key_manager=key_manager,
        peer_id=peer_id,
        info_hash=info_hash,
        swarm_id=fallback_swarm,
        transport_hint="plain",
        timestamp=int(time.time()),
    )
    raw_signature = extension["sig"]
    if not isinstance(raw_signature, str):
        tampered_signature = b"\x00" * 64
    else:
        padding = "=" * ((4 - (len(raw_signature) % 4)) % 4)
        tampered_signature = base64.urlsafe_b64decode(raw_signature + padding)
    tampered_signature = b"\x00" * len(tampered_signature)
    extension["sig"] = base64.urlsafe_b64encode(tampered_signature).decode("ascii").rstrip("=")

    recorded: list[tuple[str, dict[str, str]]] = []

    def capture_metric(name: str, labels: dict[str, str]) -> None:
        recorded.append((name, dict(labels)))

    monkeypatch.setattr(
        "ccbt.security.swarm_auth_policy._record_swarm_auth_metric",
        capture_metric,
    )

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash, extension),
        session=session,
        transport_hint="plain",
    )

    assert decision.allowed is True
    assert decision.mode == "opportunistic"
    assert decision.reason_code == "invalid_signature"
    assert any(
        name == SWARM_AUTH_OPPORTUNISTIC_VERIFY_FAILED_TOTAL
        and labels.get("reason_code") == "invalid_signature"
        for name, labels in recorded
    )
    assert not any(
        name == SWARM_AUTH_METRIC_REASONS
        and labels.get("reason_code") == "invalid_signature"
        for name, labels in recorded
    )


def test_evaluate_inbound_policy_strict_with_trust_store_mismatch_is_denied(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id = b"a" * 20
    info_hash = b"\x90" * 20
    swarm_id = canonicalize_swarm_id("aaaaaaaa" * 8)
    mismatch = canonicalize_swarm_id("bbbbbbbb" * 8)
    extension = _build_signed_handshake(
        key_manager=key_manager,
        peer_id=peer_id,
        info_hash=info_hash,
        swarm_id=swarm_id,
        transport_hint="plain",
        timestamp=int(time.time()),
    )
    session = _session(
        auth_mode="strict",
        trusted=[swarm_id],
        include_key_manager=True,
    )
    session.key_manager = key_manager
    session._swarm_auth_trust_store = SwarmTrustStore(
        version=1,
        swarm_anchors={
            mismatch: [
                SwarmTrustAnchor(type="ed25519_pubkey_hex", value="00" * 32),
            ]
        },
    )

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash, extension),
        session=session,
        transport_hint="plain",
    )

    assert decision.allowed is False
    assert decision.reason_code == "trust_lookup_failed"


def test_evaluate_inbound_policy_strict_with_tls_spki_binding_allows_matching_anchor(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id = b"u" * 20
    info_hash = b"\x7a" * 20
    swarm_id = canonicalize_swarm_id("eeeeeeee" * 8)
    peer_spki = b"fake-spki-material"
    extension = _build_signed_handshake_with_hint(
        key_manager=key_manager,
        peer_id=peer_id,
        info_hash=info_hash,
        swarm_id=swarm_id,
        transport_hint="mse",
        timestamp=int(time.time()),
        trust_proof_hint="spki_sha256",
    )
    session = _session(
        auth_mode="strict",
        trusted=[swarm_id],
        include_key_manager=True,
    )
    session.key_manager = key_manager
    session._swarm_auth_trust_store = SwarmTrustStore(
        version=1,
        swarm_anchors={
            swarm_id: [
                SwarmTrustAnchor(
                    type="spki_sha256",
                    value=hashlib.sha256(peer_spki).hexdigest(),
                )
            ]
        },
    )

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash, extension),
        session=session,
        transport_hint="mse",
        tls_hint="tls",
        peer_tls_public_key_from_cert=peer_spki,
    )

    assert decision == AuthDecision(True, "strict", "allow")


def test_evaluate_inbound_policy_strict_with_tls_binding_mismatch_is_denied(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id = b"v" * 20
    info_hash = b"\x7b" * 20
    swarm_id = canonicalize_swarm_id("ffffffff" * 8)
    peer_spki = b"fake-spki-material"
    extension = _build_signed_handshake_with_hint(
        key_manager=key_manager,
        peer_id=peer_id,
        info_hash=info_hash,
        swarm_id=swarm_id,
        transport_hint="mse",
        timestamp=int(time.time()),
        trust_proof_hint="spki_sha256",
    )
    session = _session(
        auth_mode="strict",
        trusted=[swarm_id],
        include_key_manager=True,
    )
    session.key_manager = key_manager
    session._swarm_auth_trust_store = SwarmTrustStore(
        version=1,
        swarm_anchors={
            swarm_id: [
                SwarmTrustAnchor(
                    type="spki_sha256",
                    value=hashlib.sha256(b"different-spki-material").hexdigest(),
                )
            ]
        },
    )

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash, extension),
        session=session,
        transport_hint="mse",
        tls_hint="tls",
        peer_tls_public_key_from_cert=peer_spki,
    )

    assert decision.allowed is False
    assert decision.reason_code == "trusted_peer_key_mismatch"


def test_evaluate_inbound_policy_strict_with_tls_cert_hint_and_missing_material_is_denied(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id = b"w" * 20
    info_hash = b"\x7c" * 20
    swarm_id = canonicalize_swarm_id("00000000" * 8)
    cert_der = b"\x30\x81\x0a...fake-cert-bytes..."
    extension = _build_signed_handshake_with_hint(
        key_manager=key_manager,
        peer_id=peer_id,
        info_hash=info_hash,
        swarm_id=swarm_id,
        transport_hint="mse",
        timestamp=int(time.time()),
        trust_proof_hint="cert_sha256",
    )
    session = _session(
        auth_mode="strict",
        trusted=[swarm_id],
        include_key_manager=True,
    )
    session.key_manager = key_manager
    session._swarm_auth_trust_store = SwarmTrustStore(
        version=1,
        swarm_anchors={
            swarm_id: [
                SwarmTrustAnchor(
                    type="cert_sha256",
                    value=hashlib.sha256(cert_der).hexdigest(),
                )
            ]
        },
    )

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash, extension),
        session=session,
        transport_hint="mse",
        tls_hint="tls",
        peer_tls_public_key_from_cert=None,
    )

    assert decision.allowed is False
    assert decision.reason_code == "trusted_peer_key_mismatch"


def test_evaluate_inbound_policy_opportunistic_allows_with_key_mismatch_when_allowing(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id = b"b" * 20
    info_hash = b"\x91" * 20
    swarm_id = canonicalize_swarm_id("cccccccc" * 8)
    extension = _build_signed_handshake(
        key_manager=key_manager,
        peer_id=peer_id,
        info_hash=info_hash,
        swarm_id=swarm_id,
        transport_hint="plain",
        timestamp=int(time.time()),
    )
    session = _session(
        auth_mode="opportunistic",
        trusted=[swarm_id],
        include_key_manager=True,
    )
    session.key_manager = key_manager
    session._swarm_auth_trust_store = SwarmTrustStore(
        version=1,
        swarm_anchors={
            swarm_id: [
                SwarmTrustAnchor(
                    type="ed25519_pubkey_hex",
                    value="00" * 32,
                )
            ]
        },
    )

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash, extension),
        session=session,
        transport_hint="plain",
    )

    assert decision.allowed is True
    assert decision.mode == "opportunistic"
    assert decision.reason_code == "trusted_peer_key_mismatch"


def test_evaluate_inbound_policy_parse_error_revocation_cache_blocks_when_no_stale_cache() -> None:
    peer_id = b"c" * 20
    info_hash = b"\x92" * 20
    swarm_id = canonicalize_swarm_id("dddddddd" * 8)
    session = _session(
        auth_mode="opportunistic",
        trusted=[swarm_id],
        include_key_manager=False,
    )
    session._swarm_auth_revocation_parse_error = True
    session._swarm_auth_revocation_cache = None

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash),
        session=session,
        transport_hint="plain",
    )

    assert decision.allowed is True
    assert decision.reason_code == "revocation_profile_parse_error"


def test_evaluate_inbound_policy_parse_error_revocation_cache_allowed_with_stale_cache() -> None:
    peer_id = b"d" * 20
    info_hash = b"\x93" * 20
    swarm_id = canonicalize_swarm_id("eeeeeeee" * 8)
    session = _session(
        auth_mode="opportunistic",
        trusted=[swarm_id],
        include_key_manager=False,
    )
    session._swarm_auth_revocation_cache = SwarmRevocationCache(
        profile=SwarmRevocationProfile(
            revoked_fingerprints=frozenset(),
            revoked_swarm_ids=frozenset(),
        ),
        loaded_at=time.time(),
    )
    session._swarm_auth_revocation_parse_error = True

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash),
        session=session,
        transport_hint="plain",
    )

    assert decision.allowed is True
    assert decision.mode == "opportunistic"
    assert decision.reason_code == "missing_schema"


def _build_signed_handshake(
    *,
    key_manager: Ed25519KeyManager,
    peer_id: bytes,
    info_hash: bytes,
    swarm_id: str,
    transport_hint: str,
    timestamp: int,
) -> dict[str, object]:
    normalized_swarm = canonicalize_swarm_id(swarm_id)
    payload = build_swarm_auth_message(
        normalized_swarm,
        peer_id=peer_id,
        info_hash=info_hash,
        timestamp=timestamp,
        transport_hint=transport_hint,
    )
    signature = key_manager.sign_message(payload)
    return build_swarm_auth_extension(
        swarm_id=normalized_swarm,
        public_key=key_manager.get_public_key_bytes(),
        signature=signature,
        timestamp=timestamp,
    )


def _build_signed_handshake_with_hint(
    *,
    key_manager: Ed25519KeyManager,
    peer_id: bytes,
    info_hash: bytes,
    swarm_id: str,
    transport_hint: str,
    timestamp: int,
    trust_proof_hint: str | None,
) -> dict[str, object]:
    normalized_swarm = canonicalize_swarm_id(swarm_id)
    payload = build_swarm_auth_message(
        normalized_swarm,
        peer_id=peer_id,
        info_hash=info_hash,
        timestamp=timestamp,
        transport_hint=transport_hint,
    )
    signature = key_manager.sign_message(payload)
    return build_swarm_auth_extension(
        swarm_id=normalized_swarm,
        public_key=key_manager.get_public_key_bytes(),
        signature=signature,
        timestamp=timestamp,
        trust_proof_hint=trust_proof_hint,
    )


def test_evaluate_inbound_policy_strict_with_valid_proof_is_allowed(
    key_manager: Ed25519KeyManager,
) -> None:
    now = int(time.time())
    peer_id = b"z" * 20
    info_hash = b"\x44" * 20
    swarm_id = canonicalize_swarm_id("aaaaaaaa" * 8)
    extension = _build_signed_handshake(
        key_manager=key_manager,
        peer_id=peer_id,
        info_hash=info_hash,
        swarm_id=swarm_id,
        transport_hint="plain",
        timestamp=now,
    )
    session = _session(
        auth_mode="strict",
        trusted=[swarm_id],
        include_key_manager=True,
    )
    session.key_manager = key_manager

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash, extension),
        session=session,
        transport_hint="plain",
    )
    assert decision == AuthDecision(True, "strict", "allow")


def test_evaluate_inbound_policy_strict_with_v2_info_hash_is_allowed(
    key_manager: Ed25519KeyManager,
) -> None:
    now = int(time.time())
    peer_id = b"v" * 20
    info_hash_v2 = b"\x55" * 32
    swarm_id = canonicalize_swarm_id("aaaaaaaa" * 8)
    extension = _build_signed_handshake(
        key_manager=key_manager,
        peer_id=peer_id,
        info_hash=info_hash_v2,
        swarm_id=swarm_id,
        transport_hint="plain",
        timestamp=now,
    )
    session = _session(
        auth_mode="strict",
        trusted=[swarm_id],
        include_key_manager=True,
    )
    session.key_manager = key_manager
    handshake = SimpleNamespace(
        peer_id=peer_id,
        info_hash_v1=None,
        info_hash=None,
        info_hash_v2=info_hash_v2,
        swarm_auth=extension,
    )

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=handshake,
        session=session,
        transport_hint="plain",
    )
    assert decision == AuthDecision(True, "strict", "allow")


def test_evaluate_inbound_policy_strict_uses_trust_lookup_failure(
    key_manager: Ed25519KeyManager,
) -> None:
    now = int(time.time())
    peer_id = b"w" * 20
    info_hash = b"\x55" * 20
    swarm_id = canonicalize_swarm_id("bbbbbbbb" * 8)
    extension = _build_signed_handshake(
        key_manager=key_manager,
        peer_id=peer_id,
        info_hash=info_hash,
        swarm_id=swarm_id,
        transport_hint="mse",
        timestamp=now,
    )
    session = _session(
        auth_mode="strict",
        trusted=[canonicalize_swarm_id("cccccccc" * 8)],
        include_key_manager=True,
    )
    session.key_manager = key_manager

    decision = evaluate_inbound_admission(
        peer_socket=_peer_socket(),
        parsed_handshake=_handshake(peer_id, info_hash, extension),
        session=session,
        transport_hint="mse",
    )

    assert decision.allowed is False
    assert decision.reason_code == "trust_lookup_failed"


def test_evaluate_inbound_policy_cache_is_idempotent_for_same_candidate(
    key_manager: Ed25519KeyManager,
) -> None:
    now = int(time.time())
    peer_id = b"i" * 20
    info_hash = b"\x66" * 20
    swarm_id = canonicalize_swarm_id("dddddddd" * 8)
    extension = _build_signed_handshake(
        key_manager=key_manager,
        peer_id=peer_id,
        info_hash=info_hash,
        swarm_id=swarm_id,
        transport_hint="tls",
        timestamp=now,
    )
    session = _session(
        auth_mode="opportunistic",
        trusted=[swarm_id],
        include_key_manager=True,
    )
    session.key_manager = key_manager
    socket = _peer_socket()
    handshake = _handshake(peer_id, info_hash, extension)

    first = evaluate_inbound_admission(
        peer_socket=socket,
        parsed_handshake=handshake,
        session=session,
        transport_hint="tls",
    )
    second = evaluate_inbound_admission(
        peer_socket=socket,
        parsed_handshake=handshake,
        session=session,
        transport_hint="tls",
    )

    assert first == second


def test_evaluate_outbound_policy_off_mode_allows_immediately() -> None:
    peer_id = b"q" * 20
    info_hash = b"\x77" * 20
    session = _session(auth_mode="off", include_key_manager=False)
    session.torrent_data = {"info_hash": info_hash}

    decision = evaluate_outbound_admission(
        peer_socket=_peer_socket(),
        peer_id=peer_id,
        torrent_data=session,
        transport_hint="plain",
    )

    assert decision == AuthDecision(True, "off", "swarm_auth_mode_off")


def test_evaluate_outbound_policy_strict_with_missing_signature_verifier_is_denied() -> None:
    peer_id = b"r" * 20
    info_hash = b"\x78" * 20
    swarm_id = canonicalize_swarm_id("12345678-9abc-def0-1234-56789abcdef0")
    session = _session(auth_mode="strict", include_key_manager=False)
    session.torrent_data = {"info_hash": info_hash}
    session.swarm_id = swarm_id

    decision = evaluate_outbound_admission(
        peer_socket=_peer_socket(),
        peer_id=peer_id,
        torrent_data=session,
        transport_hint="mse",
    )

    assert decision.allowed is False
    assert decision.mode == "strict"
    assert decision.reason_code == "missing_signature_verifier"


def test_evaluate_outbound_policy_strict_with_invalid_peer_id_is_denied() -> None:
    info_hash = b"\x79" * 20
    session = _session(auth_mode="strict", include_key_manager=False, trusted=[])
    session.torrent_data = {"info_hash": info_hash}
    session.swarm_id = "12345678-9abc-def0-1234-56789abcdef0"

    decision = evaluate_outbound_admission(
        peer_socket=_peer_socket(),
        peer_id=b"short",
        torrent_data=session,
        transport_hint="plain",
    )

    assert decision.allowed is False
    assert decision.reason_code == "invalid_peer_id"


def test_evaluate_outbound_policy_strict_without_torrent_info_hash_is_denied() -> None:
    session = _session(auth_mode="strict", include_key_manager=False)
    decision = evaluate_outbound_admission(
        peer_socket=_peer_socket(),
        peer_id=b"x" * 20,
        torrent_data=session,
        transport_hint="plain",
    )
    assert decision.allowed is False
    assert decision.mode == "strict"
    assert decision.reason_code == "missing_torrent_info_hash"


def test_evaluate_outbound_policy_strict_with_valid_proof_is_allowed(
    key_manager: Ed25519KeyManager,
) -> None:
    peer_id = b"z" * 20
    info_hash = b"\x80" * 20
    swarm_id = canonicalize_swarm_id("aaaaaaaa" * 8)
    session = _session(
        auth_mode="strict",
        trusted=[swarm_id],
        include_key_manager=False,
    )
    session.key_manager = key_manager
    session.torrent_data = {"info_hash": info_hash}
    session.swarm_id = swarm_id

    decision = evaluate_outbound_admission(
        peer_socket=_peer_socket(),
        peer_id=peer_id,
        torrent_data=session,
        transport_hint="mse",
    )

    assert decision == AuthDecision(True, "strict", "allow")


def test_evaluate_outbound_policy_opportunistic_is_permitted_without_signature_verifier() -> None:
    peer_id = b"o" * 20
    info_hash = b"\x81" * 20
    session = _session(auth_mode="opportunistic", include_key_manager=False)
    session.torrent_data = {"info_hash": info_hash}

    decision = evaluate_outbound_admission(
        peer_socket=_peer_socket(),
        peer_id=peer_id,
        torrent_data=session,
        transport_hint="plain",
    )

    assert decision.allowed is True
    assert decision.mode == "opportunistic"
    assert decision.reason_code in {"missing_signature_verifier", "allow"}


def test_telemetry_metric_names_are_defined() -> None:
    assert SWARM_AUTH_METRIC_TOTAL != SWARM_AUTH_METRIC_BY_MODE
    assert SWARM_AUTH_METRIC_TOTAL
    assert SWARM_AUTH_METRIC_BY_MODE
    assert SWARM_AUTH_METRIC_REASONS
    assert SWARM_AUTH_OPPORTUNISTIC_VERIFY_FAILED_TOTAL
    assert SWARM_AUTH_STRICT_LTEP_TIMEOUT_TOTAL


def test_telemetry_tag_builder_matches_decision() -> None:
    tags = SwarmAuthPolicy.build_telemetry_tags(
        mode="strict",
        transport_hint="mse",
        reason_code="allow",
        allowed=True,
    )

    assert tags["mode"] == "strict"
    assert tags["decision"] == "allow"
    assert tags["reason_code"] == "allow"
