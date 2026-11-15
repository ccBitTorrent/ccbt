# Changelog

All notable changes to ccBitTorrent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Exciting New Features 🎉

- XET is now **supported**: all 20 claims (C1–C20) in `dev/xet-claim-registry.yaml` flipped from experimental to supported after the G9 big-bang gate passed on local live evidence (real `hf_xet`/`huggingface_hub`/git-lfs against ccbt CAS/Hub on loopback, plus a cross-test against a real external OpenXet CAS server and the HF production CAS; harness: `dev/scripts/run_xet_live_gate.py`, never run in CI). Suite: `xet-blake3-gearhash-lz4:v2`; Byzantine consensus requires `n >= 3f + 1`

### Fixed 🐞

- Fix CAS shard-upload v2 stream to emit upstream `ShardUploadEvent` frames (`validating`/`committing`/`result` with `type` tags) so stock `hf_xet` accepts uploads against `ccbt cas serve`
- Fix Hub API compatibility with modern `huggingface_hub` (repo URL shape, `preupload`, `commitOid`, repo deletion)

## [0.2.0] - 2026-11-15

### Exciting New Features 🎉

- Ship the XET native suite `xet-blake3-gearhash-lz4:v2` with Gearhash CDC, BLAKE3 hashing, LZ4 xorbs/shards, Hub git-xet CAS, peer handshake negotiation, and legacy-store migration (`ccbt xet migrate-legacy`) (Joseph Pollack, ccBitTorrent contributors)
- Add swarm and download acceleration for cold-start connection scheduling, pipeline depth, and sparse-swarm piece progress (Joseph Pollack, ccBitTorrent contributors)

### Documentation 📚

- Add the XET native specification and experimental claim registry / release checklist for the big-bang gate (Joseph Pollack, ccBitTorrent contributors)

### Fixed 🐞

- Fix Python 3.9/3.10 compatibility for XET CAS `Self` typing, migrate-legacy `zip` usage, and CI py3.9 runners on ubuntu-24.04 (Joseph Pollack, ccBitTorrent contributors)
- Fix git-xet Hub clone empty-tree failures on CI by forcing `main` as the default branch (Joseph Pollack, ccBitTorrent contributors)
- Normalize test working directories and harden DHT/local-store discovery mocks used by XET e2e coverage (Joseph Pollack, ccBitTorrent contributors)

### Internal 🔧

- Expand XET unit/integration/e2e coverage (handshake, CAS HTTP, Hub git-xet, golden codec, chunk exchange, sync) (Joseph Pollack, ccBitTorrent contributors)
- Align pre-commit selective pytest discovery and compatibility-linter rules with the 3.9+ support floor (Joseph Pollack, ccBitTorrent contributors)

### Migration and Rollout Notes 📌

- XET remains experimental until the G9 big-bang gate in `dev/xet-claim-registry.yaml` passes; docs must not claim full support yet
- Legacy `.tonic` / pre-suite stores are read-only import via `ccbt xet migrate-legacy` and must not mix with v2 chunks for the same file

## [0.1.0] - 2026-07-23

### Breaking Changes

- Remove top-level ``btbt config-extended``; extended subcommands now live under ``btbt config`` such as ``config schema`` and ``config import`` (Joseph Pollack, ccBitTorrent contributors)

### Added

- Add DHT bootstrap per-hostname DNS failure backoff to avoid tight resolver retry loops after timeouts or `gaierror` (Joseph Pollack, ccBitTorrent contributors)
- Add the metadata exchange diagnostics runbook to MkDocs Dev nav (Joseph Pollack, ccBitTorrent contributors)
- Add ``btbt config describe`` nested option catalog output with defaults and optional current values (Joseph Pollack, ccBitTorrent contributors)
- Add ``btbt config apply`` JSON/TOML/YAML merge patch support with validation (Joseph Pollack, ccBitTorrent contributors)
- Validate ``config set`` with config simulation and JSON/comma-list value parsing before writes (Joseph Pollack, ccBitTorrent contributors)
- Add ``config import --mode merge|replace`` for partial and full-document imports (Joseph Pollack, ccBitTorrent contributors)
- Add recursive config option discovery and shared env/CLI list-field parsing constants (Joseph Pollack, ccBitTorrent contributors)
- Add swarm-health / cold-start connection and pipeline scheduling improvements for sparse swarms (Joseph Pollack, ccBitTorrent contributors)

### Changed

- Defer session tracker metadata fallback while peer connection batches are active to reduce duplicate metadata churn before TCP settles (Joseph Pollack, ccBitTorrent contributors)
- Treat BitTorrent peer streams as non-reusable live sockets with exact lease ownership in the connection pool (Joseph Pollack, ccBitTorrent contributors)

### Internal

- Pre-commit: Ruff, ty, Bandit, and compatibility-linter fixes across discovery, MSE, session, SSL, and peer code (Joseph Pollack, ccBitTorrent contributors)
- Align CI tests and fixtures with current peer, scrape, magnet, and config surfaces (Joseph Pollack, ccBitTorrent contributors)

### Fixed 🐞

- Migrate Textual dashboard live data to App reactives, daemon IPC bindings, and startup-interrupt retry behavior so the TUI stays open after connecting (Joseph Pollack, ccBitTorrent contributors)
- Repair peer batch, piece manager, DHT setup, session recovery, and XET metadata matching regressions (Joseph Pollack, ccBitTorrent contributors)
- Harden `_retry_requested_pieces` cleanup and requested-piece map recovery under one manager lock (Joseph Pollack, ccBitTorrent contributors)
- Improve DHT bootstrap diagnostics, recovery backoff visibility, and stalled-query recovery fallbacks (Joseph Pollack, ccBitTorrent contributors)
- Improve tracker robustness for late UDP responses, startup idempotence, and HTML payload quarantine (Joseph Pollack, ccBitTorrent contributors)

### Logging and Observability 🧭

- Move intermediate metadata exchange peer outcome logs to DEBUG while keeping INFO milestone ordering clearer (Joseph Pollack, ccBitTorrent contributors)
- Add explicit TRACE verbosity level (`-vvv`) and align `-v`/`-vv` behavior to INFO/DEBUG levels without changing startup semantics (Josephrp, ccBitTorrent contributors)
- Centralize Rich/Textual visual treatment for logs, dashboard, and splash output via shared style policy (Josephrp, ccBitTorrent contributors)
- Map observability environment variables and document their precedence behavior (Josephrp, ccBitTorrent contributors)
- Add regression coverage for verbosity mapping, style helpers, and observability precedence behavior (Josephrp, ccBitTorrent contributors)

### Migration and Rollout Notes 📌

- Preserve existing log level names, tracker behavior, and observability environment variable names (Josephrp, ccBitTorrent contributors)
- Preserve `-v`, `-vv`, and `-vvv` semantics while keeping default output volume unchanged (Josephrp, ccBitTorrent contributors)
- Preserve fallback behavior for missing trace and observability values from `ccbt.toml` and process configuration (Josephrp, ccBitTorrent contributors)
- Recommend automation that depends on legacy log noise pins verbosity and avoids `-vvv` by default (Josephrp, ccBitTorrent contributors)

## [0.0.1] - 2024-12-XX

### Exciting New Features 🎉

- Initial release of ccBitTorrent high-performance BitTorrent client (Josephrp, ccBitTorrent contributors)

### Performance ⚡

- Optimized disk I/O with file preallocation, write batching, and memory-mapped I/O (Josephrp, ccBitTorrent contributors)

### Documentation 📚

- Getting started guides and examples (Josephrp, ccBitTorrent contributors)

### Internal 🔧

- Contributing (Josephrp, ccBitTorrent contributors)
- Session refactoring with controller-based architecture and dependency injection (Joseph Pollack, ccBitTorrent contributors)
- Improved tracker, peer, and piece stability checks and async typing/type cleanup for pre-commit readiness (Joseph Pollack, ccBitTorrent contributors)

[0.2.0]: https://github.com/ccBitTorrent/ccbt/releases/tag/v0.2.0
[0.1.0]: https://github.com/ccBitTorrent/ccbt/releases/tag/v0.1.0
[0.0.1]: https://github.com/ccBitTorrent/ccbt/releases/tag/v0.0.1
