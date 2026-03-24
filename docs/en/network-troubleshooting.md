# Network troubleshooting

This page is a **placeholder** for detailed network diagnostics (NAT, firewalls, trackers, DHT, and listen ports). Until it is expanded, use:

- [Configuration](configuration.md) — ports, bind addresses, and protocol toggles
- [Performance tuning](performance.md) — throughput and connection limits
- [BEP XET](bep_xet.md) — Xet-specific setup when that protocol is enabled

If you hit a reproducible bug, open an issue with logs, OS, and `ccbt.toml` (redacted) on the project repository.

## Windows caps and discovery pressure

- **Layered limits:** Effective peer counts come from several layers: (1) `CCBT_*` / `ccbt.toml` values, (2) `CCBT_WINDOWS_NETWORK_COMPAT_STRICT=true` (default on Windows) clamping `max_global_peers` to 200, `connection_pool_max_connections` to 150, and `max_peers_per_torrent` to 100 when set higher, (3) `config_conditional` adjustments after startup (e.g. single NIC may cap `max_global_peers` at 200; multiple interfaces may raise toward 300). Check logs for `Clamped network.*` and `Peer connection limits (effective config)`.
- **Authoritative runtime precedence:** Runtime tuning resolves as `file (TOML) -> optimization profile -> env -> Windows clamp`. Use `btbt config show -S network -f json` and `btbt config describe --include-current --path-prefix network.` to verify the effective value that wins.
- **Daemon metadata path is separate:** Daemon IPC fallback reads `~/.ccbt/daemon/config.json` (`ipc_port`, `api_key`) only when resolving daemon URL/port; this file is not the runtime tuning source for network/discovery policy.
- On Windows, `max_global_peers` and per-torrent caps may be clamped for compatibility; check logs for the effective values after startup.
- **Tracker paths:** The announce loop (`ccbt/session/announce.py`) can hand the full deduplicated peer list to `connect_peers_to_download`. UDP/HTTP **immediate** callbacks (`ccbt/session/session.py`) first take a bounded batch (`CCBT_TRACKER_IMMEDIATE_CONNECT_BURST_TOTAL` / `CCBT_TRACKER_IMMEDIATE_CONNECT_BURST_PER_SOURCE`, with per-source cap mode `CCBT_TRACKER_IMMEDIATE_PER_SOURCE_CAP_MODE`); additional peers are enqueued on the peer manager **pending queue** and drained after batches complete. If the immediate-connect **circuit breaker** fires (`CCBT_TRACKER_IMMEDIATE_CONNECT_WINDOW_S` / `CCBT_TRACKER_IMMEDIATE_CONNECT_WINDOW_CAP`), peers are also enqueued to the pending queue rather than dropped. `CCBT_MAX_CONNECT_BURST_PER_TICK` applies to DHT / requestable-driven pressure, not that immediate tracker path.
- **Inbound vs global cap:** `AsyncPeerConnectionManager` enforces `max_peers_per_torrent` on inbound TCP for that torrent. `max_global_peers` is intended as a process-wide budget; multi-torrent enforcement is coordinated via `PeerService` / session manager—do not assume a per-torrent manager alone enforces global totals on inbound accepts.
- **MSE:** With encryption **preferred**, `CCBT_MSE_INITIATOR_TIMEOUT_SCALE_ZERO_ACTIVE` (default `1.0`) can be lowered (e.g. `0.65`) to shorten the MSE initiator timeout when the torrent has zero active peers, so plain fallback happens sooner under connection pressure.
- **Logs:** At peer manager start, look for `Peer connection limits (effective config): connection_pool_max_connections=...` to confirm the post-clamp pool size vs `CCBT_CONNECTION_POOL_MAX_CONNECTIONS`.
- **Active vs requestable peers:** TCP connections may be “active” while the remote is choking you. Requestable-driven discovery (`CCBT_TARGET_REQUESTABLE_PEERS`, `CCBT_REQUESTABLE_TICK_INTERVAL_S`) tightens DHT timing and resumes pending connects when `can_request()` peers lag the target. On Windows with `CCBT_WINDOWS_NETWORK_COMPAT_STRICT=true`, global peers are capped at 200—keep `CCBT_TARGET_REQUESTABLE_PEERS` within what your total swarm budget allows.
- **DHT cadence expectations:** Discovery uses a 30s retry seed, but normal-mode loop cadence is clamped to at least ~60s before failure backoff expands. Emergency/requestable-zero paths can temporarily compress cadence. Check debug startup logs for effective DHT retry/min-interval values.
- **Inbound registration:** Tune `CCBT_INBOUND_*` wait caps and probation when multi-torrent daemons drop magnet handshakes; `CCBT_INBOUND_REGISTRATION_WAIT_CAP_METADATA_PENDING_S` lengthens the initial poll when metadata is still fetching.
- **Inbound probation queue bounds:** `CCBT_INBOUND_PROBATION_WAIT_QUEUE_MAX_TOTAL` bounds queued waiters globally and `CCBT_INBOUND_PROBATION_QUEUED_MAX_WAIT_S` bounds per-peer queued wait duration before expiry.
- **Sparse-swarm probation/recycle knobs:** `CCBT_PEER_QUALITY_PROBATION_SPARSE_CHOKE_GRACE_SECONDS`, `CCBT_PEER_RECYCLE_SPARSE_BACKOFF_CAP_SECONDS`, and `CCBT_RECYCLE_PRESSURE_THRESHOLD` control how aggressively the client rotates non-requestable peers in sparse swarms.
- **Connection pool:** Very low `CCBT_CONNECTION_POOL_MIN_DOWNLOAD_BANDWIDTH` marks peers “starved” after unchoke; see `env.example`. Performance recycling is skipped during the pool grace window until bytes are received.
- **PeerSelector (`ccbt/ml/peer_selector.py`):** Optional blend into outbound ranking via `CCBT_PEER_SELECTOR_ML_RANKING_WEIGHT` (default `0` = disabled). Values up to `0.5` mix heuristic scores with `PeerSelector.rank_peers` outputs; treat as experimental.
- **Choke-only slot replacement:** `CCBT_CHOKE_ONLY_SLOT_REPLACEMENT_ENABLED` (default off) can disconnect oldest persistently choked peers when no connection is requestable and the swarm is near `max_peers_per_torrent`; see `env.example`.

## Connect batch split-state and submit statuses

- **Batch owner:** At most one `connect_to_peers` “owner” run per `AsyncPeerConnectionManager` at a time. While the owner is active, `_batch_owner_active` and `_dht_connect_deferral_active` are true so DHT/session recovery can defer to the batch without treating “peers in flight” as a finished handoff.
- **Reentrant submit:** A second `connect_to_peers` while the owner is active **queues** peers on the pending deque and returns `ConnectSubmitResult(status="queued_reentrant")`. This is a successful queue merge, **not** “batch complete” and **not** equivalent to `owner_started`. Session recovery must not skip DHT or treat tracker handoff as done solely because of `queued_reentrant`.
- **Owner started:** `owner_started` means the owner took the lock and scheduled work for this submit; it does not mean all peers are connected yet.
- **Grep-stable diagnostics:** Logs and metrics use stable tokens — `pd_connect_submit status=…`, `pd_pending_resume schedule reason=…`, `pd_deprecate_private_resume` when a non-canonical pending-resume reason is scheduled (prefer `request_pending_resume()` on the peer manager instead of `_schedule_pending_resume`).
- **Per-torrent metrics:** `AsyncTorrentSession._peer_discovery_metrics` includes counters such as `connect_submit_total_by_status`, `connect_reentrant_queued_total`, `batch_owner_state_transition_total`, `dht_deferral_state_transition_total`, `pending_resume_edge_trigger_total`, `pending_connect_queue_depth_gauge`, `time_to_first_requestable_s`, `dht_candidate_promotion_selected_total`, etc. Global `MetricsCollector` names are prefixed with `peer_discovery_*`.

## MSE / protocol encryption bounds (operator summary)

- **What changed in recent discovery hardening:** MSE initiator timeouts can scale when the swarm has **zero active peers** (`CCBT_MSE_INITIATOR_TIMEOUT_SCALE_ZERO_ACTIVE`) so preferred encryption can fall back to plaintext handshake sooner under pressure. Retry serialization and backoff are bounded per endpoint/profile so overlapping transports do not stampede.
- **What stayed BEP-aligned:** Handshake ordering, info-hash validation, and peer wire message handling after encryption negotiation are unchanged; obfuscation remains optional traffic shaping, not a replacement for the standard BitTorrent handshake + stream.

## Recovery gating (tracker → DHT)

- **Requestable deficit window:** When the swarm is at or above `min_peers_before_dht` but has no requestable **and** no productive peers, immediate DHT `get_peers` escalation can wait for a short persistence window (session defaults: `recovery_requestable_deficit_window_s` ≈ 12s, `recovery_dht_escalation_cooldown_s` ≈ 10s unless fail-fast bypass applies). Tune via `ccbt.toml` / env and verify via effective config output.

## Daemon shutdown contract and noisy drain windows

- **IPC shutdown contract:** `POST /api/v1/shutdown` now returns a truthful payload with `accepted` and `status`. Treat graceful shutdown as accepted only when `accepted=true`.
- **Idempotency:** Duplicate shutdown requests can return `status=already_shutting_down` while still `accepted=true`.
- **Fallback behavior:** If the shutdown bridge is unavailable, the endpoint can return non-success (`accepted=false`) with a fallback hint. CLI may then use signal-based fallback.
- **Expected logs during shutdown:** Short-lived cleanup logs are normal, but sustained zero-peer DHT timeout spam should be reduced due to shutdown-time throttling and early quiesce.
- **Operator check:** If shutdown appears stalled, compare time between `Daemon shutdown sequence started` and `Daemon stopped` and inspect whether repeated `DHT timeout calculated` / `Connection state distribution` lines are throttled.
