# Publishing these drafts to GitHub Issues

This environment cannot perform GitHub write operations, so use these commands locally (or in a write-enabled automation context) to publish all drafts:

1. `gh issue create --title "[P0] Announce loop exits permanently when peer manager is not ready" --body-file docs/reports/issues/01_announce_loop_exits_when_peer_manager_not_ready.md --label bug --label p0 --label tracker --label session`
2. `gh issue create --title "[P0] DHT discovery hard-gated until 50 active peers" --body-file docs/reports/issues/02_dht_blocked_until_50_peers.md --label bug --label p0 --label dht --label peer-discovery`
3. `gh issue create --title "[P1] peer_count_low handler suppresses DHT when peers are low but non-zero" --body-file docs/reports/issues/03_peer_count_low_handler_blocks_nonzero_low_peers.md --label bug --label p1 --label dht --label session`
4. `gh issue create --title "[P1] DHT fallback disabled for non-magnet torrents unless explicitly requested" --body-file docs/reports/issues/04_dht_opt_in_for_non_magnet_torrents.md --label bug --label p1 --label dht --label configuration`
5. `gh issue create --title "[P1] DHT queued/pending peer buffers appear undrained" --body-file docs/reports/issues/05_dht_queued_pending_peers_not_drained.md --label bug --label p1 --label dht --label peer-discovery`
6. `gh issue create --title "[P1] Async peer connection batch result handling uses wrong variable" --body-file docs/reports/issues/06_async_peer_connection_result_variable_bug.md --label bug --label p1 --label peer-connection`
7. `gh issue create --title "[P2] DHT dedup cache lacks TTL and can suppress useful rediscovery" --body-file docs/reports/issues/07_dht_dedup_no_ttl.md --label bug --label p2 --label dht --label reliability`

Optional: adjust label names to match repository conventions.
