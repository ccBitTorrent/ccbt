"""Authenticated swarm admission policy helpers."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional, Union, cast

from ccbt.security.swarm_auth_contract import (
    build_swarm_auth_extension,
    build_swarm_auth_message,
    evaluate_swarm_auth_verification_order,
)
from ccbt.security.swarm_identity import (
    canonical_torrent_info_hash_family,
    canonicalize_swarm_id,
    legacy_swarm_id_fallback,
)

AuthMode = Literal["off", "opportunistic", "strict"]
SWARM_AUTH_METRIC_TOTAL = "swarm_auth_gate_total"
SWARM_AUTH_METRIC_BY_MODE = "swarm_auth_gate_by_mode_total"
SWARM_AUTH_METRIC_REASONS = "swarm_auth_reject_reason_total"
SWARM_AUTH_DISCOVERY_SUPPRESSED_TOTAL = "swarm_auth_discovery_suppressed_total"
SWARM_AUTH_TRUSTSTORE_RELOAD_TOTAL = "swarm_auth_truststore_reload_total"
SWARM_AUTH_REVOCATION_HITS_TOTAL = "swarm_auth_revocation_hits_total"
SWARM_AUTH_OPPORTUNISTIC_VERIFY_FAILED_TOTAL = (
    "swarm_auth_opportunistic_verify_failed_total"
)
SWARM_AUTH_STRICT_LTEP_TIMEOUT_TOTAL = "swarm_auth_strict_ltep_timeout_total"
SWARM_AUTH_REJECTION_REASON_LABEL = "reason_code"
_LOGGER = logging.getLogger(__name__)


def _record_swarm_auth_metric(metric_name: str, labels: dict[str, str]) -> None:
    """Emit a swarm-auth metric, ignoring telemetry failures."""
    try:
        from ccbt.monitoring import get_metrics_collector
        from ccbt.monitoring.metrics_collector import MetricLabel

        get_metrics_collector().increment_counter(
            metric_name,
            labels=[
                MetricLabel(name=str(name), value=str(value))
                for name, value in labels.items()
            ],
        )
    except Exception:  # pragma: no cover - optional telemetry path
        return


@dataclass(frozen=True)
class AuthDecision:
    """Admission decision with telemetry-ready reason code."""

    allowed: bool
    mode: AuthMode
    reason_code: str


def _normalize_mode(value: Any, default: AuthMode = "off") -> AuthMode:
    """Normalize mode-like values to supported values."""
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"off", "opportunistic", "strict"}:
            return cast("AuthMode", normalized)
    return default


def _peer_socket_identity(peer_socket: Any) -> str:
    """Create a stable peer key for idempotent admission decisions."""
    if peer_socket is None:
        return "peer=unknown"
    peername = None
    if hasattr(peer_socket, "get_extra_info"):
        try:
            peername = peer_socket.get_extra_info("peername")
        except Exception:
            peername = None
    if isinstance(peername, tuple) and len(peername) >= 2:
        return f"{peername[0]}:{peername[1]}"
    if isinstance(peer_socket, tuple) and len(peer_socket) >= 2:
        return f"{peer_socket[0]}:{peer_socket[1]}"
    return f"{id(peer_socket)}"


def _extract_handshake_field(
    parsed_handshake: Any,
    names: tuple[str, ...],
) -> Any:
    """Read known handshake fields without strict coupling."""
    for name in names:
        if hasattr(parsed_handshake, name):
            return getattr(parsed_handshake, name)
    return None


def _extract_peer_id(parsed_handshake: Any) -> Optional[bytes]:
    """Extract handshake peer id bytes."""
    peer_id = _extract_handshake_field(parsed_handshake, ("peer_id",))
    if isinstance(peer_id, (bytes, bytearray)) and len(peer_id) == 20:
        return bytes(peer_id)
    return None


def _extract_info_hashes(parsed_handshake: Any) -> tuple[bytes | None, bytes | None]:
    """Extract v1/v2 info hashes from a parsed handshake."""
    info_v1 = _extract_handshake_field(parsed_handshake, ("info_hash_v1", "info_hash"))
    if not isinstance(info_v1, (bytes, bytearray)) or len(info_v1) not in {20, 32}:
        info_v1 = None
    info_v2 = _extract_handshake_field(parsed_handshake, ("info_hash_v2",))
    if not isinstance(info_v2, (bytes, bytearray)) or len(info_v2) not in {20, 32}:
        info_v2 = None
    if isinstance(info_v1, (bytes, bytearray)):
        info_v1 = bytes(info_v1)
    if isinstance(info_v2, (bytes, bytearray)):
        info_v2 = bytes(info_v2)
    return info_v1, info_v2


def _cache_key_info_hash(
    info_hash_v1: Optional[bytes],
    info_hash_v2: Optional[bytes],
) -> Optional[bytes]:
    """Build a deterministic cache key fragment for one or more hash families."""
    family: Optional[bytes]
    if info_hash_v1 is not None and info_hash_v2 is not None:
        try:
            family = canonical_torrent_info_hash_family(
                info_hash_v1=info_hash_v1,
                info_hash_v2=info_hash_v2,
            )
        except Exception:
            family = info_hash_v1
    else:
        family = info_hash_v1 if info_hash_v1 is not None else info_hash_v2
    if family is None:
        return None
    return family


def _extract_swarm_auth_payload(parsed_handshake: Any) -> Optional[dict[str, Any]]:
    """Best-effort extraction of `swarm_auth` payload from a handshake."""
    for field in ("swarm_auth", "swarm_auth_payload"):
        value = _extract_handshake_field(parsed_handshake, (field,))
        if isinstance(value, dict):
            return dict(value)

    extensions = _extract_handshake_field(parsed_handshake, ("extensions",))
    if isinstance(extensions, dict):
        maybe = extensions.get("swarm_auth")
        if isinstance(maybe, dict):
            return dict(maybe)
    return None


def _extract_session_mode(session: Any) -> AuthMode:
    """Resolve admission mode from session and config metadata."""
    if session is None:
        return "off"
    for attr in ("swarm_auth_mode", "auth_mode", "authenticated_swarms_mode"):
        value = getattr(session, attr, None)
        normalized = _normalize_mode(value, default="off")
        if normalized != "off":
            return normalized

    config = getattr(session, "config", None)
    if config is None:
        config = getattr(session, "security", None)
    security = getattr(config, "security", config)
    authenticated = getattr(security, "authenticated_swarms", None)
    for attr in ("mode",):
        value = getattr(authenticated, attr, None)
        normalized = _normalize_mode(value, default="off")
        if normalized != "off":
            return normalized
    return "off"


def _extract_session_auth_config(session: Any) -> Any:
    """Return the authenticated swarms config block if present."""
    config = getattr(session, "config", None)
    if config is None:
        config = getattr(session, "security", None)
    security = getattr(config, "security", config)
    return getattr(security, "authenticated_swarms", None)


def _session_info_hashes(session: Any) -> tuple[bytes | None, bytes | None]:
    """Extract v1/v2 info hashes from a session."""
    info = getattr(session, "info", None)
    if info is not None:
        info_v1 = getattr(info, "info_hash", None)
        if info_v1 is None:
            info_v1 = getattr(info, "info_hash_v1", None)
        info_v2 = getattr(info, "info_hash_v2", None)
        if isinstance(info_v1, (bytes, bytearray)) or isinstance(
            info_v2, (bytes, bytearray)
        ):
            return (
                bytes(info_v1) if isinstance(info_v1, (bytes, bytearray)) else None,
                bytes(info_v2) if isinstance(info_v2, (bytes, bytearray)) else None,
            )

    torrent_data = getattr(session, "torrent_data", None)
    if isinstance(torrent_data, dict):
        info_v1 = torrent_data.get("info_hash")
        info_v2 = torrent_data.get("info_hash_v2")
        if isinstance(info_v1, (bytes, bytearray)) or isinstance(
            info_v2, (bytes, bytearray)
        ):
            return (
                bytes(info_v1) if isinstance(info_v1, (bytes, bytearray)) else None,
                bytes(info_v2) if isinstance(info_v2, (bytes, bytearray)) else None,
            )
    return None, None


def _session_swarm_id(session: Any) -> Optional[str]:
    """Resolve explicit swarm id from session attributes."""
    for value in (
        getattr(getattr(session, "info", None), "swarm_id", None),
        getattr(session, "swarm_id", None),
    ):
        if not isinstance(value, str):
            continue
        try:
            return canonicalize_swarm_id(value)
        except Exception as err:
            _LOGGER.debug(
                "Failed to canonicalize swarm_id %r from session: %s", value, err
            )
            continue

    torrent_data = getattr(session, "torrent_data", None)
    if isinstance(torrent_data, dict):
        value = torrent_data.get("swarm_id")
        if isinstance(value, str):
            try:
                return canonicalize_swarm_id(value)
            except Exception as err:
                _LOGGER.debug(
                    "Failed to canonicalize torrent_data swarm_id %r: %s",
                    value,
                    err,
                )

    info_v1, info_v2 = _session_info_hashes(session)
    if isinstance(info_v1, (bytes, bytearray)):
        try:
            return legacy_swarm_id_fallback(
                canonical_torrent_info_hash_family(
                    info_hash_v1=bytes(info_v1),
                    info_hash_v2=bytes(info_v2) if info_v2 is not None else None,
                )
            )
        except Exception as err:
            _LOGGER.debug("Failed to resolve legacy swarm id fallback: %s", err)
            return None
    return None


def _session_trusted_swarm_ids(session: Any) -> list[str]:
    """Collect trust anchors from session objects."""
    raw: list[str] = []
    for attr in ("trusted_swarm_ids", "trusted_swarm_id", "swarm_trust_ids"):
        value = getattr(session, attr, None)
        if isinstance(value, str):
            raw.append(value)
        elif isinstance(value, (list, tuple, set)):
            raw.extend([item for item in value if isinstance(item, str)])
    config = getattr(session, "config", None)
    if config is None:
        config = getattr(session, "security", None)
    security = getattr(config, "security", config)
    authenticated = getattr(security, "authenticated_swarms", None)
    trusted = getattr(authenticated, "trusted_swarm_ids", None)
    if isinstance(trusted, (list, tuple, set)):
        raw.extend([value for value in trusted if isinstance(value, str)])

    fallback = _session_swarm_id(session)
    if fallback is not None:
        raw.append(fallback)

    canonical: list[str] = []
    for raw_value in raw:
        try:
            canonical.append(canonicalize_swarm_id(raw_value))
        except Exception as err:
            _LOGGER.debug(
                "Failed to canonicalize trusted swarm id %r: %s", raw_value, err
            )
            continue
    return canonical


def _resolve_signer_verify(
    session: Any,
) -> Callable[[bytes, bytes, bytes], bool] | None:
    """Resolve Ed25519 verifier function from session or config."""
    for attr in ("key_manager", "swarm_key_manager", "auth_key_manager"):
        value = getattr(session, attr, None)
        if value is None:
            continue
        verify = getattr(value, "verify_signature", None)
        if callable(verify):
            return cast("Callable[[bytes, bytes, bytes], bool]", verify)
    return None


def _resolve_signer_for_session(session: Any) -> Optional[Any]:
    """Resolve the signer manager used for auth material creation."""
    for attr in ("key_manager", "swarm_key_manager", "auth_key_manager"):
        value = getattr(session, attr, None)
        if value is not None:
            return value
    return None


def _session_auth_material_state(session: Any) -> tuple[Any, Any, bool, bool]:
    """Return cached material and parse-error state for a session.

    Returns:
      (trust_store, revocation_cache, trust_store_parse_error, revocation_parse_error)
    """
    return (
        getattr(session, "_swarm_auth_trust_store", None),
        getattr(session, "_swarm_auth_revocation_cache", None),
        bool(getattr(session, "_swarm_auth_trust_store_parse_error", False)),
        bool(getattr(session, "_swarm_auth_revocation_parse_error", False)),
    )


def _allow_after_parse_errors(
    *,
    mode: AuthMode,
    trust_store_parse_error: bool,
    revocation_parse_error: bool,
    has_any_cached_material: bool,
    fail_closed_on_parse_errors: bool,
) -> bool:
    """Return whether admission may continue after parse/reload failures."""
    if not trust_store_parse_error and not revocation_parse_error:
        return True
    if mode == "strict":
        return False
    if fail_closed_on_parse_errors:
        return False
    return bool(has_any_cached_material)


def _parse_error_reason(
    mode: AuthMode,
    trust_store_parse_error: bool,
    revocation_parse_error: bool,
    has_any_cached_material: bool,
    fail_closed_on_parse_errors: bool,
) -> Optional[str]:
    """Map parse-reload failures to admission reason if deny is required."""
    if _allow_after_parse_errors(
        mode=mode,
        trust_store_parse_error=trust_store_parse_error,
        revocation_parse_error=revocation_parse_error,
        has_any_cached_material=has_any_cached_material,
        fail_closed_on_parse_errors=fail_closed_on_parse_errors,
    ):
        return None
    if trust_store_parse_error:
        return "trust_store_parse_error"
    if revocation_parse_error:
        return "revocation_profile_parse_error"
    return "trust_material_parse_error"


def _extract_session_fail_closed_on_parse_errors(session: Any) -> bool:
    """Return whether authenticated-swarms parse failures should be denied."""
    auth_cfg = _extract_session_auth_config(session)
    if isinstance(auth_cfg, dict):
        return bool(auth_cfg.get("fail_closed_on_parse_errors", False))
    return bool(getattr(auth_cfg, "fail_closed_on_parse_errors", False))


def _resolve_swarm_auth_materials(session: Any, mode: AuthMode) -> list[str]:
    """Resolve trust-store/revocation based failures and return failure reason."""
    trust_store, revocation_cache, trust_err, revocation_err = (
        _session_auth_material_state(session)
    )
    if mode == "off":
        return []
    strict_mode = mode == "strict"
    fail_closed_on_parse_errors = _extract_session_fail_closed_on_parse_errors(session)
    has_cached = bool(trust_store) or bool(revocation_cache)
    reason = _parse_error_reason(
        mode="strict" if strict_mode else mode,
        trust_store_parse_error=trust_err,
        revocation_parse_error=revocation_err,
        has_any_cached_material=has_cached,
        fail_closed_on_parse_errors=fail_closed_on_parse_errors,
    )
    if reason:
        return [reason]
    # No failures blocking admission here; trust checks happen in evaluation path.
    # Keep this helper returning an explicit empty marker for clarity.
    return []


def _validate_trust_store_and_revocation_constraints(
    session: Any,
    raw_swarm_auth: Any,
    peer_tls_public_key_from_cert: Optional[bytes] = None,
    transport_hint: str = "plain",
) -> Optional[str]:
    """Validate trust-store and revocation gates against a parsed proof."""
    try:
        from ccbt.security.swarm_auth_contract import parse_swarm_auth_dict

        proof = parse_swarm_auth_dict(raw_swarm_auth)
    except Exception:
        return None

    trust_store, revocation_cache, _, _ = _session_auth_material_state(session)
    if trust_store is not None:
        try:
            from ccbt.security.swarm_trust_store import current_swarm_anchors

            anchors = current_swarm_anchors(
                trust_store,
                proof.swarm_id,
                now=int(time.time()),
            )
        except Exception:
            anchors = []
        if not anchors:
            return "trust_lookup_failed"
        if proof.trust_proof_hint is None and any(
            anchor.type == "ed25519_pubkey_hex" for anchor in anchors
        ):
            current_key = proof.public_key.hex()
            if not any(
                anchor.value.strip().lower() == current_key for anchor in anchors
            ):
                return "trusted_peer_key_mismatch"
        if proof.trust_proof_hint is not None:
            if peer_tls_public_key_from_cert is None:
                return "trusted_peer_key_mismatch"
            try:
                from ccbt.security.swarm_certificate_binding import (
                    evaluate_certificate_binding,
                )

                binding_decision = evaluate_certificate_binding(
                    public_key=peer_tls_public_key_from_cert,
                    trust_hint=proof.trust_proof_hint,
                    anchors=anchors,
                    transport_hint=transport_hint,
                )
            except Exception:
                return "trusted_peer_key_mismatch"
            if not binding_decision.bound:
                return "trusted_peer_key_mismatch"
    if revocation_cache is not None:
        profile = getattr(
            revocation_cache, "profile", revocation_cache
        )  # SwarmRevocationCache or raw profile
        is_revoked_swarm = getattr(
            profile,
            "is_revoked_swarm_id",
            lambda *_args, **_kwargs: False,
        )
        is_revoked_fingerprint = getattr(
            profile,
            "is_revoked_fingerprint",
            lambda *_args, **_kwargs: False,
        )
        if callable(is_revoked_swarm) and is_revoked_swarm(proof.swarm_id):
            return "revoked_swarm_id"
        if callable(is_revoked_fingerprint) and is_revoked_fingerprint(
            proof.public_key.hex()
        ):
            return "revoked_peer_key"
    return None


def build_outbound_swarm_auth_payload(
    *,
    session: Any,
    peer_id: bytes,
    info_hash: Union[bytes, tuple[bytes | None, bytes | None]],
    transport_hint: str,
    timestamp: Optional[int] = None,
    trust_proof_hint: Optional[str] = None,
) -> dict[str, Any]:
    """Build a swarm-auth extension payload from local session data."""
    if not isinstance(peer_id, (bytes, bytearray)):
        msg = "peer_id must be bytes"
        raise TypeError(msg)
    if len(peer_id) != 20:
        msg = "peer_id must be 20 bytes"
        raise ValueError(msg)
    peer_id_bytes = bytes(peer_id)

    if not isinstance(info_hash, tuple):
        if not isinstance(info_hash, (bytes, bytearray)) or len(info_hash) not in {
            20,
            32,
        }:
            msg = "info_hash must be 20 or 32 bytes, or a v1/v2 tuple"
            raise ValueError(msg)
        info_hash_bytes = bytes(info_hash)
    else:
        if len(info_hash) != 2:
            msg = "info_hash tuple must contain two values"
            raise ValueError(msg)
        info_hash_bytes = None
        v1 = info_hash[0]
        v2 = info_hash[1] if len(info_hash) > 1 else None
        info_hash_bytes = (bytes(v1) if isinstance(v1, (bytes, bytearray)) else b"") + (
            bytes(v2) if isinstance(v2, (bytes, bytearray)) else b""
        )

    signer = _resolve_signer_for_session(session)
    if signer is None:
        msg = "missing_key_manager"
        raise ValueError(msg)

    sign_message = getattr(signer, "sign_message", None)
    get_public_key_bytes = getattr(signer, "get_public_key_bytes", None)
    if not callable(sign_message) or not callable(get_public_key_bytes):
        msg = "invalid_key_manager"
        raise TypeError(msg)

    swarm_id = _session_swarm_id(session)
    if not swarm_id:
        msg = "missing_swarm_id"
        raise ValueError(msg)

    raw_timestamp = int(time.time()) if timestamp is None else int(timestamp)
    if raw_timestamp < 0:
        msg = "timestamp must be non-negative"
        raise ValueError(msg)

    message = build_swarm_auth_message(
        swarm_id=swarm_id,
        peer_id=peer_id_bytes,
        info_hash=info_hash_bytes,
        timestamp=raw_timestamp,
        transport_hint=transport_hint,
    )
    signature = sign_message(message)
    if not isinstance(signature, (bytes, bytearray)) or len(signature) != 64:
        msg = "signature must be 64 bytes"
        raise ValueError(msg)

    public_key = get_public_key_bytes()
    if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != 32:
        msg = "public_key must be 32 bytes"
        raise ValueError(msg)

    return build_swarm_auth_extension(
        swarm_id=swarm_id,
        public_key=bytes(public_key),
        signature=bytes(signature),
        timestamp=raw_timestamp,
        trust_proof_hint=trust_proof_hint,
    )


class SwarmAuthPolicy:
    """Shared policy engine for authenticated swarm admission."""

    def __init__(self, *, cache_ttl_s: float = 60.0) -> None:
        """Create a policy object with a configurable admission cache TTL."""
        self._cache_ttl_s = float(cache_ttl_s)
        self._decision_cache: dict[str, tuple[float, AuthDecision]] = {}
        self._outbound_decision_cache: dict[str, tuple[float, AuthDecision]] = {}

    def _cache_key(
        self,
        *,
        peer_socket: Any,
        parsed_handshake: Any,
        session: Any,
        transport_hint: str,
        tls_hint: Optional[str],
    ) -> str:
        peer_id = _extract_peer_id(parsed_handshake)
        info_hash_v1, info_hash_v2 = _extract_info_hashes(parsed_handshake)
        info_hash = _cache_key_info_hash(info_hash_v1, info_hash_v2)
        return "|".join(
            (
                str(id(session)),
                f"mode={_extract_session_mode(session)}",
                f"peer={peer_id.hex() if peer_id else 'none'}",
                f"info={info_hash.hex() if info_hash else 'none'}",
                f"transport={transport_hint}",
                f"tls={tls_hint or ''}",
                f"socket={_peer_socket_identity(peer_socket)}",
            )
        )

    def _get_cached(self, key: str) -> Optional[AuthDecision]:
        entry = self._decision_cache.get(key)
        if entry is None:
            return None
        seen_at, decision = entry
        if time.time() - seen_at > self._cache_ttl_s:
            self._decision_cache.pop(key, None)
            return None
        return decision

    def _set_cached(self, key: str, decision: AuthDecision) -> None:
        self._decision_cache[key] = (time.time(), decision)

    def _cache_key_outbound(
        self,
        *,
        peer_socket: Any,
        peer_id: bytes,
        torrent_data: Any,
        transport_hint: str,
        tls_hint: Optional[str],
    ) -> str:
        info_hash_v1, info_hash_v2 = _session_info_hashes(torrent_data)
        info_hash = _cache_key_info_hash(info_hash_v1, info_hash_v2)
        return "|".join(
            (
                str(id(torrent_data)),
                f"mode={_extract_session_mode(torrent_data)}",
                f"peer={bytes(peer_id).hex() if isinstance(peer_id, (bytes, bytearray)) else 'none'}",
                f"info={info_hash.hex() if isinstance(info_hash, (bytes, bytearray)) else 'none'}",
                f"transport={transport_hint}",
                f"tls={tls_hint or ''}",
                f"socket={_peer_socket_identity(peer_socket)}",
            )
        )

    def _get_cached_outbound(self, key: str) -> Optional[AuthDecision]:
        entry = self._outbound_decision_cache.get(key)
        if entry is None:
            return None
        seen_at, decision = entry
        if time.time() - seen_at > self._cache_ttl_s:
            self._outbound_decision_cache.pop(key, None)
            return None
        return decision

    def _set_cached_outbound(self, key: str, decision: AuthDecision) -> None:
        self._outbound_decision_cache[key] = (time.time(), decision)

    def _emit_decision_metrics(
        self,
        *,
        direction: str,
        decision: AuthDecision,
        transport_hint: str,
        tls_hint: Optional[str],
    ) -> None:
        labels = {
            "direction": direction,
            "mode": decision.mode,
            "transport_hint": transport_hint,
            "tls_hint": tls_hint or "none",
            "decision": "allow" if decision.allowed else "deny",
            "reason_code": decision.reason_code,
        }
        _record_swarm_auth_metric(SWARM_AUTH_METRIC_TOTAL, labels)
        _record_swarm_auth_metric(SWARM_AUTH_METRIC_BY_MODE, labels)
        if not decision.allowed:
            _record_swarm_auth_metric(
                SWARM_AUTH_METRIC_REASONS,
                {
                    "mode": decision.mode,
                    "reason_code": decision.reason_code,
                    "direction": direction,
                    "transport": transport_hint,
                },
            )
        if decision.mode == "opportunistic" and decision.reason_code not in {
            "allow",
            "swarm_auth_mode_off",
            "no_trust_material",
        }:
            _record_swarm_auth_metric(
                SWARM_AUTH_OPPORTUNISTIC_VERIFY_FAILED_TOTAL,
                {
                    "mode": decision.mode,
                    "direction": direction,
                    "transport_hint": transport_hint,
                    "tls_hint": tls_hint or "none",
                    "reason_code": decision.reason_code,
                },
            )

    def _evaluate_inbound(
        self,
        *,
        parsed_handshake: Any,
        session: Any,
        transport_hint: str,
        tls_hint: Optional[str],
        peer_tls_public_key_from_cert: Optional[bytes] = None,
    ) -> AuthDecision:
        mode = _extract_session_mode(session)
        if mode == "off":
            return AuthDecision(True, "off", "swarm_auth_mode_off")

        peer_id = _extract_peer_id(parsed_handshake)
        info_hash_v1, info_hash_v2 = _extract_info_hashes(parsed_handshake)
        if peer_id is None and info_hash_v1 is None and info_hash_v2 is None:
            return AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code="missing_peer_id_and_info_hash",
            )
        if peer_id is None:
            return AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code="missing_peer_id",
            )
        if info_hash_v1 is None and info_hash_v2 is None:
            return AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code="missing_info_hash",
            )

        trusted = _session_trusted_swarm_ids(session)
        if not trusted:
            if mode == "strict":
                return AuthDecision(False, "strict", "missing_trust_material")
            return AuthDecision(True, "opportunistic", "no_trust_material")

        parse_fail_reasons = _resolve_swarm_auth_materials(session, mode)
        if parse_fail_reasons:
            return AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code=parse_fail_reasons[0],
            )

        raw_swarm_auth = _extract_swarm_auth_payload(parsed_handshake)
        raw_schema_candidate = _extract_handshake_field(
            parsed_handshake, ("swarm_auth", "swarm_auth_payload")
        )
        if raw_schema_candidate is None:
            extensions = _extract_handshake_field(parsed_handshake, ("extensions",))
            if isinstance(extensions, dict) and "swarm_auth" in extensions:
                raw_schema_candidate = extensions.get("swarm_auth")
        signer_verify = _resolve_signer_verify(session)
        if raw_swarm_auth is None:
            reason = (
                "swarm_auth_parse_mismatch"
                if raw_schema_candidate is not None
                else "missing_schema"
            )
            return AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code=reason,
            )
        if signer_verify is None:
            reason = "missing_signature_verifier"
            return AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code=reason,
            )

        material_failure = _validate_trust_store_and_revocation_constraints(
            session=session,
            raw_swarm_auth=raw_swarm_auth,
            peer_tls_public_key_from_cert=peer_tls_public_key_from_cert,
            transport_hint="tls" if tls_hint == "tls" else transport_hint,
        )
        if material_failure is not None:
            return AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code=material_failure,
            )

        allowed, reason = evaluate_swarm_auth_verification_order(
            raw_swarm_auth=raw_swarm_auth,
            peer_id=peer_id,
            info_hash=(info_hash_v1, info_hash_v2),
            transport_hint=transport_hint,
            signer_verify=signer_verify,
            trusted_swarm_ids=trusted,
            now=None,
        )
        if mode == "strict":
            return AuthDecision(
                allowed=allowed,
                mode=mode,
                reason_code=reason,
            )
        # Opportunistic mode is intentionally non-blocking on verification failures.
        # Keep the peer admitted but preserve failure reason for telemetry.
        return AuthDecision(allowed=True, mode="opportunistic", reason_code=reason)

    def evaluate_inbound_admission(
        self,
        peer_socket: Any,
        parsed_handshake: Any,
        session: Any,
        transport_hint: str,
        tls_hint: Optional[str] = None,
        peer_tls_public_key_from_cert: Optional[bytes] = None,
    ) -> AuthDecision:
        """Evaluate whether an inbound connection should be admitted."""
        key = self._cache_key(
            peer_socket=peer_socket,
            parsed_handshake=parsed_handshake,
            session=session,
            transport_hint=transport_hint,
            tls_hint=tls_hint,
        )
        cached = self._get_cached(key)
        if cached is not None:
            self._emit_decision_metrics(
                direction="inbound",
                decision=cached,
                transport_hint=transport_hint,
                tls_hint=tls_hint,
            )
            return cached

        decision = self._evaluate_inbound(
            parsed_handshake=parsed_handshake,
            session=session,
            transport_hint=transport_hint,
            tls_hint=tls_hint,
            peer_tls_public_key_from_cert=peer_tls_public_key_from_cert,
        )
        self._set_cached(key, decision)
        self._emit_decision_metrics(
            direction="inbound",
            decision=decision,
            transport_hint=transport_hint,
            tls_hint=tls_hint,
        )
        return decision

    def evaluate_outbound_admission(
        self,
        peer_socket: Any,
        peer_id: bytes,
        torrent_data: Any,
        transport_hint: str,
        tls_hint: Optional[str] = None,
    ) -> AuthDecision:
        """Evaluate whether an outbound connection should proceed."""
        key = self._cache_key_outbound(
            peer_socket=peer_socket,
            peer_id=peer_id,
            torrent_data=torrent_data,
            transport_hint=transport_hint,
            tls_hint=tls_hint,
        )
        cached = self._get_cached_outbound(key)
        if cached is not None:
            self._emit_decision_metrics(
                direction="outbound",
                decision=cached,
                transport_hint=transport_hint,
                tls_hint=tls_hint,
            )
            return cached

        if not isinstance(peer_id, (bytes, bytearray)) or len(peer_id) != 20:
            decision = AuthDecision(False, "strict", "invalid_peer_id")
            self._set_cached_outbound(key, decision)
            self._emit_decision_metrics(
                direction="outbound",
                decision=decision,
                transport_hint=transport_hint,
                tls_hint=tls_hint,
            )
            return decision

        mode = _extract_session_mode(torrent_data)
        if mode == "off":
            decision = AuthDecision(True, "off", "swarm_auth_mode_off")
            self._set_cached_outbound(key, decision)
            self._emit_decision_metrics(
                direction="outbound",
                decision=decision,
                transport_hint=transport_hint,
                tls_hint=tls_hint,
            )
            return decision

        info_hash_v1, info_hash_v2 = _session_info_hashes(torrent_data)
        if not isinstance(info_hash_v1, (bytes, bytearray)) and not isinstance(
            info_hash_v2, (bytes, bytearray)
        ):
            decision = AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code="missing_torrent_info_hash",
            )
            self._set_cached_outbound(key, decision)
            self._emit_decision_metrics(
                direction="outbound",
                decision=decision,
                transport_hint=transport_hint,
                tls_hint=tls_hint,
            )
            return decision

        trusted = _session_trusted_swarm_ids(torrent_data)
        if not trusted:
            reason = "missing_trust_material"
            decision = AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code=reason,
            )
            self._set_cached_outbound(key, decision)
            self._emit_decision_metrics(
                direction="outbound",
                decision=decision,
                transport_hint=transport_hint,
                tls_hint=tls_hint,
            )
            return decision

        signer_verify = _resolve_signer_verify(torrent_data)
        if signer_verify is None:
            reason = "missing_signature_verifier"
            decision = AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code=reason,
            )
            self._set_cached_outbound(key, decision)
            self._emit_decision_metrics(
                direction="outbound",
                decision=decision,
                transport_hint=transport_hint,
                tls_hint=tls_hint,
            )
            return decision

        try:
            parse_fail_reasons = _resolve_swarm_auth_materials(torrent_data, mode)
            if parse_fail_reasons:
                decision = AuthDecision(
                    allowed=mode != "strict",
                    mode=mode,
                    reason_code=parse_fail_reasons[0],
                )
                self._set_cached_outbound(key, decision)
                self._emit_decision_metrics(
                    direction="outbound",
                    decision=decision,
                    transport_hint=transport_hint,
                    tls_hint=tls_hint,
                )
                return decision

            raw_swarm_auth = build_outbound_swarm_auth_payload(
                session=torrent_data,
                peer_id=bytes(peer_id),
                info_hash=(info_hash_v1, info_hash_v2),
                transport_hint=transport_hint,
            )
        except ValueError:
            reason = "outbound_payload_error"
            decision = AuthDecision(
                allowed=mode != "strict",
                mode=mode,
                reason_code=reason,
            )
            self._set_cached_outbound(key, decision)
            self._emit_decision_metrics(
                direction="outbound",
                decision=decision,
                transport_hint=transport_hint,
                tls_hint=tls_hint,
            )
            return decision

        allowed, reason = evaluate_swarm_auth_verification_order(
            raw_swarm_auth=raw_swarm_auth,
            peer_id=bytes(peer_id),
            info_hash=(info_hash_v1, info_hash_v2),
            transport_hint=transport_hint,
            signer_verify=signer_verify,
            trusted_swarm_ids=trusted,
            now=None,
        )
        material_failure = _validate_trust_store_and_revocation_constraints(
            session=torrent_data,
            raw_swarm_auth=raw_swarm_auth,
        )
        if material_failure is not None:
            if mode == "strict":
                allowed = False
            reason = material_failure
        if mode == "strict":
            decision = AuthDecision(
                allowed=allowed,
                mode="strict",
                reason_code=reason,
            )
        else:
            # Opportunistic mode always allows the outbound peer while surfacing failures
            # via telemetry for operator visibility.
            decision = AuthDecision(
                allowed=True,
                mode="opportunistic",
                reason_code=reason,
            )

        self._set_cached_outbound(key, decision)
        self._emit_decision_metrics(
            direction="outbound",
            decision=decision,
            transport_hint=transport_hint,
            tls_hint=tls_hint,
        )
        return decision

    @staticmethod
    def build_telemetry_tags(
        *,
        mode: AuthMode,
        transport_hint: str,
        reason_code: str,
        allowed: bool,
    ) -> dict[str, str]:
        """Build telemetry labels for a single admission decision."""
        return {
            "mode": mode,
            "transport_hint": transport_hint,
            "decision": "allow" if allowed else "deny",
            "reason_code": reason_code,
        }


_DEFAULT_POLICY = SwarmAuthPolicy()


def evaluate_inbound_admission(
    peer_socket: Any,
    parsed_handshake: Any,
    session: Any,
    transport_hint: str,
    tls_hint: Optional[str] = None,
    peer_tls_public_key_from_cert: Optional[bytes] = None,
) -> AuthDecision:
    """Convenience wrapper for inbound admission decision."""
    return _DEFAULT_POLICY.evaluate_inbound_admission(
        peer_socket=peer_socket,
        parsed_handshake=parsed_handshake,
        session=session,
        transport_hint=transport_hint,
        tls_hint=tls_hint,
        peer_tls_public_key_from_cert=peer_tls_public_key_from_cert,
    )


def evaluate_outbound_admission(
    peer_socket: Any,
    peer_id: bytes,
    torrent_data: Any,
    transport_hint: str,
    tls_hint: Optional[str] = None,
) -> AuthDecision:
    """Convenience wrapper for outbound admission decision."""
    return _DEFAULT_POLICY.evaluate_outbound_admission(
        peer_socket=peer_socket,
        peer_id=peer_id,
        torrent_data=torrent_data,
        transport_hint=transport_hint,
        tls_hint=tls_hint,
    )
