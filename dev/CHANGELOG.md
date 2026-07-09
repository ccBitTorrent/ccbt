# Changelog

All notable changes to ccBitTorrent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Changed

- Defer session tracker metadata fallback while peer connection batches are active to reduce duplicate metadata churn before TCP settles (Joseph Pollack, ccBitTorrent contributors)

### Internal

- Pre-commit: Ruff, ty, Bandit, and compatibility-linter fixes across discovery, MSE, session, SSL, and peer code (Joseph Pollack, ccBitTorrent contributors)

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

[0.0.1]: https://github.com/ccBittorrent/ccbt/releases/tag/v0.0.1
