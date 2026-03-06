# Peer Connection Reliability Issue Pack (2026-03-06)

This directory contains ready-to-publish issue drafts for peer discovery/connection stall behavior where downloads can stop progressing after initial peer connections.

## Drafts

1. `01_announce_loop_exits_when_peer_manager_not_ready.md`
2. `02_dht_blocked_until_50_peers.md`
3. `03_peer_count_low_handler_blocks_nonzero_low_peers.md`
4. `04_dht_opt_in_for_non_magnet_torrents.md`
5. `05_dht_queued_pending_peers_not_drained.md`
6. `06_async_peer_connection_result_variable_bug.md`
7. `07_dht_dedup_no_ttl.md`

## Suggested labels

- `bug`
- `p0` / `p1` / `p2` (severity-specific)
- `peer-discovery`
- `session`
- `dht`
- `tracker`
- `regression-risk`

## Notes

- Each file is formatted as a GitHub issue draft with reproducible steps, impact, root-cause evidence, and acceptance criteria.
- Priority order reflects user impact and likelihood to cause "initial peers connect but download later stalls."
