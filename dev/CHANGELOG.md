# Changelog

All notable changes to ccBitTorrent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking Changes
- Remove top-level ``btbt config-extended``; former extended subcommands now live under ``btbt config`` (e.g. ``config schema``, ``config import``). The duplicate bare ``btbt config`` Rich summary command was removed—use ``btbt config show`` or ``btbt config describe``.

### Added
- DHT bootstrap: per-hostname DNS failure backoff (`discovery.dht_dns_host_backoff_*`) to avoid tight repeated resolver calls after timeouts or `gaierror`.
- Docs: [Metadata exchange diagnostics runbook](docs/en/diagnostics/metadata-exchange-runbook.md) (MkDocs Dev nav).
- ``btbt config describe``: nested option catalog with defaults and optional current values (table/JSON/YAML).
- ``btbt config apply``: merge a JSON/TOML/YAML patch into the target ``ccbt.toml`` with validation.
- ``config set`` validates via ``ConfigManager.simulate_load_from_file_dict`` before write; supports ``--value``, ``--dry-run``, and JSON/comma-list parsing via ``ccbt.config.config_cli_values``.
- ``config import --mode merge|replace`` for partial vs full-document imports.
- Recursive ``ConfigDiscovery.list_all_options_nested()`` and shared ``COMMA_SEPARATED_LIST_PATHS`` for env/CLI list fields.

### Changed
- Session: tracker immediate-path metadata fallback is deferred while `peer_manager._connection_batches_in_progress` and there are no entries in `peer_manager.connections`, reducing duplicate metadata churn before TCP settles.

### Internal
- Pre-commit: Ruff, ty, Bandit, and compatibility-linter fixes across discovery, MSE, session, SSL, and peer code (Joseph Pollack, ccBitTorrent contributors)

### Fixed 🐞
- Repair `try`/`except`/`finally` and indentation regressions in peer batch connect, piece manager requestability check, DHT setup/callbacks, session recovery, and XET metadata matching helper (Joseph Pollack, ccBitTorrent contributors)
- Harden `_retry_requested_pieces` exception recovery: document removal of unreachable duplicate cleanup, run repair + map discard + staleness reset under a single manager lock, add per-peer debug lines after retry failures, and fix inactive-peer requested-piece clear count to use the normalized map key (Joseph Pollack, ccBitTorrent contributors)
- Improve DHT bootstrap diagnostics and recovery by recording repeated empty-routing recovery attempts, adding explicit rebootstrap suppression/backoff visibility, and triggering recovery fallbacks in stalled query paths (Joseph Pollack, ccBitTorrent contributors)
- Improve tracker robustness by handling late UDP ANNOUNCE responses, improving tracker startup idempotence, and quarantining HTML tracker payloads immediately to prevent repeated failed HTTP poll loops (Joseph Pollack, ccBitTorrent contributors)

### Logging and Observability 🧭
- Metadata exchange: intermediate `METADATA_PEER_OUTCOME` after BitTorrent handshake validation is now DEBUG; INFO lines keep clearer ordering (`bt_handshake_ok=True` at extended-handshake milestones).

- Add explicit TRACE verbosity level (`-vvv`) and align `-v`/`-vv` behavior to INFO/DEBUG levels without changing startup semantics (Josephrp, ccBitTorrent contributors)
- Centralize Rich/Textual visual treatment for logs, dashboard, and splash output via shared style policy (Josephrp, ccBitTorrent contributors)
- Explicitly map observability environment variables and document precedence: `CCBT_LOG_CORRELATION_ID`, `CCBT_LOG_FORMAT`, `CCBT_METRICS_INTERVAL`, `CCBT_STRUCTURED_LOGGING`, `CCBT_TRACE_FILE` (Josephrp, ccBitTorrent contributors)
- Add regression coverage for verbosity mapping, style helpers, and observability precedence behavior (Josephrp, ccBitTorrent contributors)

### Migration and Rollout Notes 📌
- No breaking API changes: existing log level names, tracker behavior, and env variable names remain supported
- Backward compatibility guardrails:
  - `-vv` still maps to DEBUG, `-v` to INFO, and `-vvv` only to TRACE
  - Default output volume is unchanged at normal verbosity, with only high-frequency INFO paths reduced to debug/trace
  - Missing trace/observability env values continue to fall back to defaults from `ccbt.toml` and process configuration
- Existing automation that relies on legacy log noise should pin verbosity and avoid `-vvv` by default

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












