# ADR-0006: Authenticated Swarm Admission and Timeout Semantics

## Status

Accepted

## Context

ccBitTorrent supports authenticated swarm admission to reduce spoofing and accidental peer poisoning in private or restricted ecosystems.
Recent implementation work added:

- Authenticated-swarms policy modes (`off`, `opportunistic`, `strict`)
- Trust anchors and revocation checks
- BEP 10 LTEP timeout enforcement in strict mode
- Certificate-bound trust proofs for TLS-capable peers
- v1/v2/hybrid swarm identifiers in signed proof payloads

This document captures the operational contract so deployments can tune behavior safely.

## Decision

The client will evaluate swarm admission in two stages:

1. Structural and cryptographic validation of `e.swarm_auth` via `ccbt.security.swarm_auth_contract`.
2. Policy and environment enforcement in `ccbt.security.swarm_auth_policy`.

### Admission modes

- `off` disables authenticated filtering; peers are admitted by existing protocol and transport rules.
- `opportunistic` runs the same checks but allows trusted policy exceptions, with mismatches recorded for observability.
- `strict` requires all required checks to pass before peer messaging continues.

### Discovery behavior

- Authenticated swarms can be scoped by `discovery_mode`.
- When `strict` mode is active and `discovery_strict_for_strict_mode = true`, discovery sources are limited to the configured mode so unauthenticated peers are not newly learned through alternate channels.

### LTEP timeout

- In strict mode, inbound peers that advertise BEP 10 support are expected to complete extension negotiation within
  `security.authenticated_swarms.strict_ltep_handshake_timeout_s`.
- If the peer does not complete negotiation in time, the session records `SWARM_AUTH_STRICT_LTEP_TIMEOUT_TOTAL` and closes the connection.
- Timeout behavior is a health gate to avoid waiting indefinitely on peers that can stall authenticated setup.

### Trust material evaluation

- If `e.swarm_auth.tp` is present in the peer payload, the policy performs transport-aware certificate binding against configured anchors:
  - `spki_sha256` validates the peer TLS public key hash.
  - `cert_sha256` validates the peer TLS certificate hash.
- If TLS material is missing or does not match, admission fails with `trusted_peer_key_mismatch`.
- When no `tp` hint is present, legacy Ed25519 key anchoring rules are used.

### Revocation and trust sources

- Trust and revocation inputs are loaded from configurable files and periodically refreshed.
- Trust misses and parse failures are surfaced as explicit reject reasons and metrics, then fail-closed behavior is controlled by `fail_closed_on_parse_errors`.

## Consequences

### Deployment implications

- Operators can choose strict identity enforcement (`strict`) or staged rollout (`opportunistic`) based on tracker/peer mix.
- The LTEP timeout should be tuned with expected network latency in mind; values that are too low can reject slow peers during startup bursts.
- Enable both trust stores and revocation profiles to reduce drift risk for rotated credentials.

### Required implementation touch points

- `ccbt/security/swarm_auth_policy.py`
- `ccbt/security/swarm_auth_contract.py`
- `ccbt/security/swarm_certificate_binding.py`
- `ccbt/peer/async_peer_connection.py`
- `ccbt/peer/ssl_peer.py`
- `docs/en/configuration.md`

## Related metrics

- `swarm_auth_gate_total`
- `swarm_auth_gate_by_mode_total`
- `swarm_auth_reject_reason_total`
- `swarm_auth_discovery_suppressed_total`
- `swarm_auth_opportunistic_verify_failed_total`
- `swarm_auth_strict_ltep_timeout_total`
- `swarm_auth_truststore_reload_total`
- `swarm_auth_revocation_hits_total`

