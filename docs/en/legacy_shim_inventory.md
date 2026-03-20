# Legacy Compatibility Inventory

Status: `audit_compat_inventory` signed off; `remove_dead_api_shims`, `remove_singleton_alias_paths`, `replace_aliased_decoders_and_wrappers` complete; `prune_ui_logging_compat`, `staged_schema_compat_cleanup` in progress
Generated: 2026-03-20  
Scope: Compatibility shims, aliases, fallbacks, and legacy paths in `ccbt/` and their direct mappings in `tests/`.

## Scope and exclusions

- Kept focus: code paths that exist for backward compatibility or legacy API support, deprecation markers, shim aliases, duplicate helpers, and compatibility fallbacks.
- Excluded: Python 3.8+ shims and explicit cross-platform compatibility helpers (for example, conditional import fallbacks that are purely Python-version-oriented and not dead/legacy API compatibility).
- Excluded: core protocol interoperability comments that are part of current behavior and not currently marked as compatibility-only.

## Legend

- **Severity**
  - `DEAD`: explicitly marked as legacy/dead and safe-to-remove once callers are migrated.
  - `BEHAVIOR_CRITICAL`: still used for runtime compatibility with existing external behavior or external callers; removal needs staged migration or explicit retention.
- **Type**
  - `API Shim`: module/class/function aliasing or compatibility wrappers.
  - `Lifecycle/Path fallback`: fallback logic for managers/resources.
  - `Schema compat`: legacy payload shaping or field aliasing.
  - `UI/CLI compat`: user-interface or command compatibility knobs.

## 1) Core API and package compatibility

### 1.1 `ccbt/session/async_main.py` (DEAD/API Shim)
- `sync_main()` and compatibility `run_daemon()` compatibility entrypoints.
- Purpose: Keep legacy `ccbt.session.async_main` behavior for tests/external imports.
- Compatibility flags: module docstring explicitly states shim purpose.
- Test anchors:
  - `tests/unit/session/test_async_main_coverage.py`
  - `tests/unit/session/test_async_main_missing_coverage.py`
  - `tests/unit/test_package_init.py` (indirect via module availability)

### 1.2 `ccbt/__init__.py` (BEHAVIOR_CRITICAL/API Shim)
- Explicit backward compatibility re-exports (`bencode`, `torrent`, `magnet`, etc.).
- `__getattr__("async_main")` import-time shim.
- Compatibility attachment of `async_main` legacy function attributes in import path.
- Test anchors:
  - `tests/unit/test_package_init.py`
  - `tests/unit/cli/test_main_entry.py`

### 1.3 `ccbt/session/session.py` (`SessionManager`, sync wrappers) (BEHAVIOR_CRITICAL/API Shim)
- `SessionManager = AsyncSessionManager` alias.
- sync-style compatibility methods: `status()`, `_cleanup_loop`, `_metrics_loop`, `_emit_global_metrics`, `_announce_loop`.
- Legacy status field aliasing in metrics/status assembly.
- Test anchors:
  - `tests/unit/session/test_session_sync_methods.py`
  - Multiple session and manager tests import `AsyncSessionManager` directly and include status-related assertions.
  - `tests/unit/session/test_manager_startup.py`

### 1.4 `ccbt/peer/__init__.py` and `ccbt/discovery/pex.py` (DEAD/API Shim)
- `ConnectionPool = PeerConnectionPool`
- `PEXManager = AsyncPexManager`
- Used for import compatibility.
- Test anchors:
  - `tests/unit/peer/*` session peer wiring indirectly.
  - `ccbt/session/peers.py` in-session usage is canonical; external shim usage appears in older tests.

## 2) Deprecated manager/singleton helper paths

### 2.1 `ccbt/extensions/manager.py` (`get_extension_manager`) (DEAD/Lifecycle fallback)
- `get_extension_manager()` remains for compatibility only and now returns a dedicated manager instance each call.
- Canonical path exists via session DI `session_manager.extension_manager`.
- Test anchors:
  - `tests/unit/peer/test_ssl_extension_protocol.py`
  - `tests/integration/test_xet_integration.py`

### 2.2 `ccbt/storage/disk_io_init.py` (`_GLOBAL_DISK_IO_MANAGER`, `get_disk_io_manager`, fallback to singleton) (DEAD/Lifecycle fallback)
- `_GLOBAL_DISK_IO_MANAGER` singleton has been removed.
- `get_disk_io_manager()` now creates a dedicated `DiskIOManager` for compatibility callers.
- `init_disk_io()` accepts optional session-owned manager injection; fallback now uses a compatibility-created manager.
- Test anchors:
  - `tests/conftest.py`
  - Existing session/storage fixtures and teardown helpers.
- Current pass status: `tests/conftest.py` no longer resets removed singleton globals; cleanup now only handles legacy state if present.

- `ccbt/transport/utp_socket.py` (`UTPSocketManager.get_instance`) (DEAD/Lifecycle fallback)
- Classmethod compatibility accessor now returns dedicated managers with deprecation warning.
- Async uTP socket manager now injection-friendly path exists through session managers.
- Test anchors:
  - `tests/unit/transport/test_utp_additional_coverage.py`
  - `tests/unit/transport/test_utp_additional.py`
  - `tests/unit/transport/test_utp_final_coverage.py`
  - `tests/unit/transport/test_utp_comprehensive.py`
  - `tests/unit/transport/test_utp.py` (independent compatibility instances)

## 3) Tracker/session wrappers and protocol path compatibility

### 3.1 `ccbt/discovery/tracker.py` (`TrackerClient`) (DEAD/API Shim)
- `TrackerClient` described as synchronous legacy compatibility wrapper/client path.
- Test anchors:
  - `tests/unit/cli/test_main.py` patches `ccbt.discovery.tracker.TrackerClient`
  - `tests/unit/session/test_tracker_announce.py` (legacy tracker client references in places)

### 3.2 `ccbt/__main__.py` (BEHAVIOR_CRITICAL direct legacy usage)
- Runtime imports of `tracker_mod.TrackerClient()`.
- Could be migrated with main entrypoint changes.
- Test anchors:
  - `tests/unit/entry` style CLI tests and CLI option matrix around entry initialization.

### 3.3 `ccbt/protocols/webtorrent.py` (`_start_websocket_server`) (DEAD/API Shim)
- Deprecated WebSocket server bootstrap path with canonical-session routing note.
- Test anchors:
  - websocket/session bootstrap tests likely through `tests/daemon/test_websocket.py`

## 4) Download/session bootstrap compatibility helpers

### 4.1 `ccbt/session/download_manager.py` (`download_torrent`, `download_magnet`) (DEAD/API Shim)
- Compatibility helpers for single-shot download entrypoints.
- Test anchors:
  - `tests/unit/session/test_download_manager_piece_received.py`
  - `tests/unit/session/test_async_main_coverage.py`
  - `tests/unit/cli/test_main_deep_paths.py`

### 4.2 `ccbt/cli/main.py` (`--debug` alias + `ctx.obj["verbose"]`) (BEHAVIOR_CRITICAL/CLI)
- `-d/--debug` flagged as deprecated compatibility mapping to `-vv`.
- `ctx.obj["verbose"]` retained as legacy duplicate.
- Test anchors:
  - `tests/unit/cli/test_main.py`
  - `tests/unit/cli/test_main_focus.py`

### 4.3 `ccbt/cli/monitoring_commands.py` (`--no-daemon`) (DEAD/CLI)
- Option currently emitted but deprecated / ignored.
- Test anchors:
  - `tests/integration/monitoring/test_dashboard_comprehensive.py` (dashboard command paths)
  - `tests/unit/interface/test_terminal_dashboard.py` via main path.

## 5) Peer/protocol/message compatibility

### 5.1 `ccbt/peer/peer.py` (`PeerInfo` alias, `MessageDecoder`) (DEAD/API Shim)
- `PeerInfo = PeerInfoModel`
- `MessageDecoder(AsyncMessageDecoder)` shim wrapper.
- Test anchors:
  - `tests/unit/peer/test_peer.py`
  - `tests/unit/peer/test_peer_expanded.py`
  - `tests/unit/peer/test_peer_coverage_gaps.py`

### 5.2 `ccbt/peer/async_peer_connection.py` (`shutdown()` alias, singleton fallback)
- `shutdown()` alias for `stop()` compatibility.
- Fallback to deprecated uTP singleton path when session manager unavailable.
- Test anchors:
  - `tests/unit/peer/test_async_peer_connection_expanded.py`
  - `tests/unit/peer/test_peer_connection_error_handling.py`
  - `tests/unit/transport/test_utp_additional.py`

### 5.3 `ccbt/piece/async_piece_manager.py` (`hash_queue = None`, `_hash_worker`) (DEAD/Worker shim)
- Legacy hash queue path marked deprecated and no-op/deprecated loop style.
- Test anchors:
  - `tests/unit/piece/test_async_piece_manager.py`-adjacent coverage files
  - Hash task migration coverage in piece manager tests.

### 5.4 `ccbt/piece/async_metadata_exchange.py` (`record_success`, `record_failure`) (DEAD/API Shim)
- Alias methods around new naming.
- Test anchors:
  - `tests/unit/piece/test_async_metadata_expanded.py`

## 6) Logging/diagnostics compatibility

### 6.1 `ccbt/utils/logging_config.py` (`ColoredFormatter`) (DEAD/Formatter shim)
- `ColoredFormatter` removed.
- `setup_logging` now uses `logging.Formatter` directly for plain output fallback.
- Test anchors:
  - `tests/unit/utils/test_logging_config_comprehensive.py` (updated to validate plain formatter path)

### 6.2 `ccbt/utils/rich_logging.py` (`show_icons`, `_show_icons`) (DEAD/Constructor shim)
- Deprecated constructor alias parameters with compatibility handling.
- Test anchors:
  - `tests/unit/cli/test_logging_enhancements.py`

### 6.3 `ccbt/utils/metrics.py` (`Metrics = MetricsCollector`) (DEAD/API Shim)
- Simple alias retained for historical import paths.
- Test anchors:
  - metrics coverage tests in `tests/unit/monitoring/*` and `tests/unit/peer/*` using collector entrypoints.

## 7) Storage compatibility

### 7.1 `ccbt/storage/checkpoint.py` (`convert_checkpoint_checkpoint_format`) (DEAD/API Shim)
- Duplicate typo helper method kept for compatibility.
- Test anchors:
  - `tests/unit/session/test_checkpoint_persistence.py`
  - `tests/unit/session/test_session_status_and_utils.py`

### 7.2 `ccbt/storage/disk_io.py` (`DiskIOError` alias) (DEAD/API Shim)
- Alias for new `DiskError`.
- Test anchors:
  - `tests/unit/session/test_download_manager_piece_received.py` and checkpoint/storage tests.

### 7.3 `ccbt/storage/file_assembler.py` (Compatibility session methods/properties) (BEHAVIOR_CRITICAL)
- `start`, `stop`, `get_status`, `piece_manager`, `download_complete` methods kept for compatibility with older session shape.
- Test anchors:
  - `tests/unit/session/test_session_status_and_utils.py`
  - session manager integration and storage tests.

## 8) Data schema and API payload compatibility

### 8.1 `ccbt/session/torrent_utils.py` + `ccbt/session/session.py` `_normalize_torrent_data` (BEHAVIOR_CRITICAL)
- Explicit legacy dict reconstruction logic (`pieces`, `piece_length`, `num_pieces`, etc.).
- Test anchors:
  - `tests/unit/session/test_session_normalize_coverage.py`
  - `tests/unit/session/test_session_coverage_boost.py`

### 8.2 `ccbt/models.py` (`listen_port` fallback + compatibility export methods)
- Deprecated singular `listen_port` with fallback into `listen_port_tcp/udp`.
- Canonical export methods named `export_*` keep backward-compatible dict keys.
- Test anchors:
  - `tests/unit/cli/test_interactive_expanded.py`
  - `tests/unit/cli/test_magnet_download_continuation.py`
  - `tests/unit/session/test_manager_startup.py`

### 8.3 `ccbt/interface/data_provider.py` (canonicalized status/read model keys) (BEHAVIOR_CRITICAL/API Shim)
- Alias injection was removed so normalized read models now emit canonical peer/rate keys only.
- Added canonical peer-rate normalization for `get_peer_metrics()` peers so dashboard consumers can rely on
  `download_rate`/`upload_rate` while protocol compatibility values (`total_*`) are still accepted at input.
- Test anchors:
  - `tests/unit/interface/test_data_provider.py`

### 8.4 `ccbt/executor/session_adapter.py` and `ccbt/daemon/state_manager.py` alias mapping
- `ccbt/executor/session_adapter.py` and `ccbt/daemon/state_manager.py` now use canonical peer keys when consuming internal status (`connected_peers`/`active_peers`) and no longer fallback to `num_peers`/`num_seeds`.
- Test anchors:
  - `tests/integration/test_status_scrape_integration.py` (should now verify canonical source path in integration surface)
  - `tests/unit/cli/test_status_scrape_display.py`
  - `tests/unit/executor/test_daemon_session_adapter_methods.py` (interface model expectations)

### 8.5 `ccbt/daemon/ipc_server.py` and `ccbt/daemon/ipc_protocol.py` IPC boundary translation
- Remaining legacy read-model aliases remain at IPC boundary by design while protocol consumers are still canonicalizing to `num_peers`/`num_seeds` and `total_*` for API compatibility.
- Current callers should continue to rely on canonical session/model fields and consume compatibility values at the API edge.
- `ccbt/executor/torrent_executor.py::_get_torrent_status` now normalizes command payloads to canonical peer keys (`connected_peers`/`active_peers`) before returning to callers, removing direct `num_peers` dependence from CLI consumers.

## 9) UI compatibility paths

### 9.1 `ccbt/interface/screens/tabbed_base.py` (`DEPRECATED` module + `ccbt/interface/screens/__init__.py`) (DEAD/UI module)
- Module removed from package; legacy exports removed from `ccbt/interface/screens/__init__.py`.
- Test anchors:
  - `tests/unit/interface/test_terminal_dashboard.py` (tabbed screens are no longer imported)

### 9.2 `ccbt/interface/terminal_dashboard.py` (`legacy layout`, compatibility stubs, `--no-daemon` arg parser path)
- Transitional UI compatibility comments and widgets/handlers with fallback behavior.
- Test anchors:
  - dashboard integration test modules in `tests/integration/monitoring/`
  - `tests/unit/interface/test_terminal_dashboard.py`

### 9.3 `ccbt/interface/splash/animation_adapter.py` (`update_message`, `clear_messages`) (DEAD/UI shim)
- Legacy message-progress compatibility hooks were removed; splash progress updates now use logger-level events instead.
- Test anchors:
  - Canonical splash progress coverage remains through `tests/unit/interface/test_terminal_dashboard.py` and dashboard integration suites.

### 9.4 `ccbt/interface/widgets/core_widgets.py` (`TorrentsTable`, `PeersTable`) (DEAD/UI shim)
- Explicitly marked legacy widgets; migration target is `ReusableDataTable`.
- Removed from `ccbt/interface/widgets/core_widgets.py` and exports in `ccbt/interface/widgets/__init__.py`; legacy behavior for the terminal dashboard is now supplied by local `ReusableDataTable`-based adapters in `ccbt/interface/terminal_dashboard.py`.
- Test anchors:
  - UI widget tests in interface and monitoring suites.

## 10) Misc compatibility utility paths worth reviewing before removal

- `ccbt/config/config.py` (`get_network_config`, `get_disk_config`, etc.): explicit backward-compat functions for config section getters.
- `ccbt/utils/ring_buffer` and other typed alias compatibility comments (behavior-critical in some paths).
- `ccbt/security/encryption.py` legacy `EncryptionConfig` constructor support, and stream conversion compatibility methods.
- `ccbt/security/key_manager.py` fallback parsing for legacy key bytes in decryptor flows.
- `ccbt/security/xet_allowlist.py` `_legacy_encryption_key` for older key material.
- `ccbt/storage/file_assembler.py` session-compat methods may be behavior-critical until UI/session refactors complete.
- `ccbt/peer/tcp_server.py` `listen_port` fallback comment for older config fields.
- `ccbt/discovery/dht.py` legacy info-hash alias and response handler naming compatibility.

These are likely not dead but can mask older format assumptions; classify as behavior-critical until migration plans verify their callers.

## Compatibility-to-tests mapping status

### Confirmed anchors already mapped
- T-Map-01: package + session compatibility aliasing:
  - `tests/unit/test_package_init.py`, `tests/unit/session/test_session_sync_methods.py`
- T-Map-02: extension manager singleton helper:
  - `tests/unit/peer/test_ssl_extension_protocol.py`, `tests/integration/test_xet_integration.py`
- T-Map-03: `MessageDecoder` compatibility:
  - `tests/unit/peer/test_peer.py`, `tests/unit/peer/test_peer_expanded.py`
- T-Map-05: uTP singleton:
  - `tests/unit/transport/test_utp_additional.py`, `tests/unit/transport/test_utp_comprehensive.py`, `tests/unit/transport/test_utp_additional_coverage.py`
- T-Map-06: disk IO singleton:
  - `tests/conftest.py` fixture and cleanup paths
- T-Map-07: data provider aliases:
  - `tests/unit/interface/test_data_provider.py`
    - `test_daemon_provider_get_peer_metrics_normalizes_rates`
- T-Map-08: legacy torrent status normalization:
  - `tests/unit/session/test_session_normalize_coverage.py`, `tests/unit/session/test_session_coverage_boost.py`
- T-Map-10: monitoring/UI compatibility pathways:
  - `tests/integration/monitoring/test_dashboard_comprehensive.py` and related dashboard suites
- T-Map-11: peer metric normalization in dashboard data path:
  - `tests/unit/interface/test_data_provider.py` (`test_daemon_provider_get_peer_metrics_normalizes_rates`)
  - Monitoring widgets consuming peer metrics: `tests/integration/monitoring/test_dashboard_comprehensive.py`, `tests/integration/monitoring/test_dashboard_expanded.py` (legacy field compatibility should now be handled at provider boundary)
- T-Map-12: executor status command canonicalization:
  - `tests/unit/executor/test_torrent_executor_config.py` (`test_torrent_status_returns_canonical_peer_fields`)

## Incomplete inventory candidates (to confirm on next passes)

- Additional compatibility references may be in modules with phrase-only markers (`legacy`, `compatibility`, `legacy info_hash`, etc.) where behavior could be protocol interoperability rather than dead API.  
- Remaining candidate files to verify in upcoming passes:
  - `ccbt/monitoring/metrics_collector.py`
  - `ccbt/cli/interactive.py`
  - `ccbt/discovery/dht_indexing.py`

## Pass 2 findings (additional compatibility hotspots)

### A) Additional legacy compatibility shims

- `ccbt/async_main.py` (`__all__` alias module shim for tests)
  - Re-exports canonical symbols for patching convenience:
    - `AsyncDownloadManager`, `AsyncPeerConnectionManager`, `AsyncPieceManager`, `download_torrent`, `download_magnet`.
  - Test anchors:
    - No direct imports found, but package-level `__getattr__("async_main")` relies on module existence.
    - `tests/unit/test_package_init.py` currently validates only `ccbt.async_main` module resolve path.

- `ccbt/cli/main.py` (`ctx.obj["verbose"]` legacy compatibility flag)
  - Maintained for legacy callers that read this legacy field.
  - Current compatibility status: likely behavior-critical until callers outside tests are audited.
  - Test anchors:
    - `tests/unit/cli/test_main.py`
    - `tests/unit/cli/test_main_options_matrix.py`
    - `tests/unit/cli/test_main_more.py`

- `ccbt/interface/widgets/core_widgets.py` (`TorrentsTable`, `PeersTable` legacy widgets)
  - Removed from module; migration to `ReusableDataTable` adapters was completed in the terminal dashboard for compatibility.
  - Test anchors:
    - Existing UI coverage in `tests/integration/monitoring/test_dashboard_comprehensive.py` exercises newer container-based widgets.
    - `ccbt/interface/terminal_dashboard.py` now hosts local compatibility adapters using `ReusableDataTable` for legacy layout bindings.

### B) Compatibility wrappers with protocol-level behavior (retain unless explicitly planned)

- `ccbt/peer/peer.py` (`PeerInfo = PeerInfoModel`, `MessageDecoder`) and
  `ccbt/peer/async_peer_connection.py` (`shutdown()` alias):
  - Classified as API compatibility shims, but may still be referenced by tests and external callers.
- `ccbt/storage/disk_io.py` alias `DiskIOError = DiskError`:
  - Small API alias likely safe but behavior-impacting removal requires test scan.
- `ccbt/session/session.py` many "for compatibility" internal fallback comments (e.g., legacy keys, test flags):
  - Mostly behavior-critical and should be normalized through `staged_schema_compat_cleanup` rather than one-shot deletion.

### C) Test mapping updates (for remove_dead_api_shims)

- `tests/unit/test_entry_points.py`
  - `test___main___daemon_status_quick_exit` validates `ccbt.__main__` daemon quick path.
  - `test_async_main_sync_wrapper_daemon_status` validates CLI status handling via patched executor path.
  - These are sensitive to removal of legacy sync wrappers and should be updated as APIs shift.

- `tests/unit/session/test_async_main_*`
  - These tests target `ccbt.session.async_main` coverage paths, not all necessarily still needed if shim is retired.
  - Need a decision point in `remove_dead_api_shims`:
    - either delete shim and move tests to `ccbt.cli.main`/`ccbt.session.session`.
    - or retain shim as intentional behavior-critical compatibility only.

- `tests/unit/cli/test_main.py` / `tests/unit/cli/test_main_deep_paths.py`
  - Contains assertions around `--debug` and config/port paths.

- `tests/unit/interface/test_terminal_dashboard.py`
  - Contains minimal regression coverage for dashboard class internals and should remain compatible with splash and no-daemon behavior changes.

- `tests/unit/utils/test_logging_config_comprehensive.py`
  - Exercises fallback/plain formatter behavior in `setup_logging`.
- `tests/unit/cli/test_logging_enhancements.py`
  - Exercises `create_rich_handler`; updated during logging-shim cleanup.
- `tests/unit/transport/test_utp_additional_coverage.py` / `tests/unit/transport/test_utp.py`
  - Still assert `UTPSocketManager.get_instance` behavior in tests.

## Pass 3 completion notes (implemented `remove_dead_api_shims` edits)

- Removed deprecated async_main compatibility modules:
  - Deleted `ccbt/session/async_main.py`.
  - Deleted `ccbt/async_main.py`.
  - Removed async_main compatibility attribute shim from `ccbt/__init__.py`.
  - Updated package init tests in `tests/unit/test_package_init.py` accordingly.
- Removed deprecated dashboard legacy path:
  - Removed `--no-daemon` flag support from `ccbt/cli/monitoring_commands.py` and `ccbt/interface/terminal_dashboard.py`.
- Removed proven-dead shim method:
  - Removed `convert_checkpoint_checkpoint_format` typo helper in `ccbt/storage/checkpoint.py`.
- Removed no-op compatibility adapters:
  - Removed `update_message` and `clear_messages` from `ccbt/interface/splash/animation_adapter.py`.
  - Removed legacy SplashManager progress message APIs from `ccbt/interface/splash/splash_manager.py`.
- Removed logging icon alias args:
  - Removed `show_icons` / `_show_icons` compatibility args from `ccbt/utils/rich_logging.py`.
  - Updated `tests/unit/cli/test_logging_enhancements.py` to assert canonical arg usage.

## Pass 4 completion notes (implemented `remove_singleton_alias_paths` edits so far)

- Removed singleton state from compatibility manager paths:
  - `ccbt/extensions/manager.py` now drops global `_extension_manager`.
  - `ccbt/storage/disk_io_init.py` now drops `_GLOBAL_DISK_IO_MANAGER`.
  - `ccbt/transport/utp_socket.py` now drops singleton `_instance` and lock.
- Updated compatibility accessors to return dedicated compatibility instances:
  - `get_extension_manager()` now always returns a new `ExtensionManager`.
  - `get_disk_io_manager()` now always returns a new `DiskIOManager`.
  - `UTPSocketManager.get_instance()` now creates a fresh started manager each call.
- Migrated call sites to prefer session-owned managers (DI) with compatibility fallback:
  - `ccbt/session/session.py`, `ccbt/session/peers.py`, `ccbt/peer/async_peer_connection.py`, `ccbt/peer/utp_peer.py`, `ccbt/transport/utp.py`, `ccbt/discovery/xet_cas.py`, and `ccbt/peer/ssl_peer.py`.
  - `ccbt/interface/screens/monitoring/disk_analysis.py`, `ccbt/interface/screens/monitoring/disk_io.py`, `ccbt/interface/screens/config/global_config.py`, `ccbt/monitoring/metrics_collector.py`, `ccbt/cli/interactive.py`, and `ccbt/cli/status.py` now prefer injected `disk_io_manager`.
- Updated tests/fixtures away from singleton resets:
  - `tests/unit/transport/test_utp_additional.py`, `tests/unit/transport/test_utp.py`, `tests/unit/transport/test_utp_comprehensive.py`, `tests/integration/test_refactored_session_lifecycle.py`, `tests/unit/peer/test_ssl_extension_protocol.py`, `tests/integration/test_ssl_extension.py`, and `tests/conftest.py`.

