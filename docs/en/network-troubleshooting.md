# Network troubleshooting

This page is a **placeholder** for detailed network diagnostics (NAT, firewalls, trackers, DHT, and listen ports). Until it is expanded, use:

- [Configuration](configuration.md) — ports, bind addresses, and protocol toggles
- [Performance tuning](performance.md) — throughput and connection limits
- [BEP XET](bep_xet.md) — Xet-specific setup when that protocol is enabled

If you hit a reproducible bug, open an issue with logs, OS, and `ccbt.toml` (redacted) on the project repository.

## Windows caps and discovery pressure

- On Windows, `max_global_peers` and per-torrent caps may be clamped for compatibility; check logs for the effective values after startup.
- **Active vs requestable peers:** TCP connections may be “active” while the remote is choking you. Requestable-driven discovery (`CCBT_TARGET_REQUESTABLE_PEERS`, `CCBT_REQUESTABLE_TICK_INTERVAL_S`) tightens DHT timing and resumes pending connects when `can_request()` peers lag the target.
- **Inbound registration:** Tune `CCBT_INBOUND_*` wait caps and probation when multi-torrent daemons drop magnet handshakes; `CCBT_INBOUND_REGISTRATION_WAIT_CAP_METADATA_PENDING_S` lengthens the initial poll when metadata is still fetching.
- **Connection pool:** Very low `CCBT_CONNECTION_POOL_MIN_DOWNLOAD_BANDWIDTH` marks peers “starved” after unchoke; see `env.example`. Performance recycling is skipped during the pool grace window until bytes are received.
- **PeerSelector (`ccbt/ml/peer_selector.py`):** Optional blend into outbound ranking via `CCBT_PEER_SELECTOR_ML_RANKING_WEIGHT` (default `0` = disabled). Values up to `0.5` mix heuristic scores with `PeerSelector.rank_peers` outputs; treat as experimental.
- **Choke-only slot replacement:** `CCBT_CHOKE_ONLY_SLOT_REPLACEMENT_ENABLED` (default off) can disconnect oldest persistently choked peers when no connection is requestable and the swarm is near `max_peers_per_torrent`; see `env.example`.
