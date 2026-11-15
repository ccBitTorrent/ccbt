# XET support matrix

Generated from `dev/xet-claim-registry.yaml`. Do not edit by hand.
Every row is **supported** (big-bang gate G9 passed).

| Claim | Gate | Status | Owner | Tests |
|-------|------|--------|-------|-------|
| C1: XET is fully implemented | G9 | **supported** | `ccbt` | `test_xet_golden_chunking`, `test_interop_cas_client_openxet`, `test_e2e_chunk_exchange` |
| C2: Gearhash CDC 8KiB-128KiB, 64KiB target, upstream-compatible boundaries | G1 | **supported** | `ccbt/storage/xet_chunking.py` | `test_xet_golden_chunking`, `test_xet_golden_streaming_equivalence` |
| C3: Cross-torrent chunk-level deduplication | G2 | **supported** | `ccbt/storage/xet_deduplication.py` | `test_xet_store_cross_torrent_dedup`, `test_xet_store_verify_on_read` |
| C4: Peer-to-peer CAS over DHT and trackers | G7 | **supported** | `ccbt/discovery/xet_cas.py` | `test_e2e_discovery_dht_only`, `test_e2e_discovery_tracker_only` |
| C5: Only changed chunks redistribute on update | G8 | **supported** | `ccbt/storage/xet_folder_manager.py` | `test_e2e_folder_sync_changed_chunks_only` |
| C6: BLAKE3 keyed hashing and Merkle verification (single suite) | G1 | **supported** | `ccbt/storage/xet_hashing.py` | `test_xet_golden_hashing`, `test_xet_golden_merkle` |
| C7: Upstream xorb and MDB shard formats | G1 | **supported** | `ccbt/storage/xet_xorb.py` | `test_xet_golden_xorb_roundtrip`, `test_xet_golden_shard_roundtrip` |
| C8: BEP 10 XET extension with request-correlated chunk messages | G6 | **supported** | `ccbt/extensions/xet.py` | `test_e2e_chunk_exchange`, `test_xet_extension_v2_wire` |
| C9: 10 discovery mechanisms, each individually proven | G7 | **supported** | `ccbt/protocols/xet.py` | `test_e2e_discovery_dht_only`, `test_e2e_discovery_gossip_only` |
| C10: Four folder sync modes (designated, best_effort, broadcast, consensus) | G8 | **supported** | `ccbt/session/xet_sync_manager.py` | `test_e2e_sync_designated_failover`, `test_e2e_sync_broadcast_converges` |
| C11: Raft and Byzantine consensus over the wire | G8 | **supported** | `ccbt/consensus/raft.py` | `test_consensus_raft_partition`, `test_consensus_byzantine_liars` |
| C12: Conflict resolution (last-write-wins, version-vector, 3-way-merge, timestamp) with preserved conflicts | G8 | **supported** | `ccbt/session/xet_conflict.py` | `test_e2e_sync_conflict_preserved` |
| C13: Git version references tracked; auto-commit opt-in | G8 | **supported** | `ccbt/storage/git_versioning.py` | `test_xet_git_versioning_real_repo` |
| C14: Encrypted allowlist (AES-256-GCM) with Ed25519 handshake proof | G6 | **supported** | `ccbt/security/xet_allowlist.py` | `test_xet_allowlist_encrypted_roundtrip`, `test_e2e_chunk_exchange` |
| C15: .tonic v2, tonic links, cold-link join, remote URL, daemon persistence, IPC/UI status | G8 | **supported** | `ccbt/core/tonic.py` | `test_xet_tonic_v2_roundtrip`, `test_e2e_cold_link_join` |
| C16: Configuration for XET, xet_sync, CAS/Hub, and NAT ports | G9 | **supported** | `ccbt/models.py` | `test_xet_config_target_enforced` |
| C17: CLI: ccbt xet, btbt tonic, ccbt cas serve, ccbt hub serve, git-xet | G9 | **supported** | `ccbt/cli/xet_commands.py` | `test_interop_git_xet_roundtrip`, `test_xet_cli_migrate_legacy` |
| C18: CAS client compatible with HF CAS contract and OpenXet | G3 | **supported** | `ccbt/discovery/xet_cas_http.py` | `test_interop_cas_client_openxet`, `test_interop_cas_contract_fixtures` |
| C19: CAS server compatible with stock hf_xet; Hub API with huggingface_hub; Git LFS | G5 | **supported** | `ccbt/cas_server/app.py` | `test_interop_hf_xet_against_ccbt_cas`, `test_interop_hub_huggingface_hub` |
| C20: No placeholder XET modules remain reachable from docs | G2 | **supported** | `ccbt/storage` | `test_xet_no_placeholder_modules` |
