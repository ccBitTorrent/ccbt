# XET big-bang release checklist

Generated from `dev\xet-claim-registry.yaml`.
Every claim must be `supported` with passing `test_ids` before release.

| ID | Gate | Status | Claim | Tests |
|----|------|--------|-------|-------|
| C1 | G9 | experimental | XET is fully implemented | `test_xet_golden_chunking`, `test_interop_cas_client_openxet`, `test_e2e_chunk_exchange` |
| C2 | G1 | experimental | Gearhash CDC 8KiB-128KiB, 64KiB target, upstream-compatible boundaries | `test_xet_golden_chunking`, `test_xet_golden_streaming_equivalence` |
| C3 | G2 | experimental | Cross-torrent chunk-level deduplication | `test_xet_store_cross_torrent_dedup`, `test_xet_store_verify_on_read` |
| C4 | G7 | experimental | Peer-to-peer CAS over DHT and trackers | `test_e2e_discovery_dht_only`, `test_e2e_discovery_tracker_only` |
| C5 | G8 | experimental | Only changed chunks redistribute on update | `test_e2e_folder_sync_changed_chunks_only` |
| C6 | G1 | experimental | BLAKE3 keyed hashing and Merkle verification (single suite) | `test_xet_golden_hashing`, `test_xet_golden_merkle` |
| C7 | G1 | experimental | Upstream xorb and MDB shard formats | `test_xet_golden_xorb_roundtrip`, `test_xet_golden_shard_roundtrip` |
| C8 | G6 | experimental | BEP 10 XET extension with request-correlated chunk messages | `test_e2e_chunk_exchange`, `test_xet_extension_v2_wire` |
| C9 | G7 | experimental | 10 discovery mechanisms, each individually proven | `test_e2e_discovery_dht_only`, `test_e2e_discovery_gossip_only` |
| C10 | G8 | experimental | Four folder sync modes (designated, best_effort, broadcast, consensus) | `test_e2e_sync_designated_failover`, `test_e2e_sync_broadcast_converges` |
| C11 | G8 | experimental | Raft and Byzantine consensus over the wire | `test_consensus_raft_partition`, `test_consensus_byzantine_liars` |
| C12 | G8 | experimental | Conflict resolution (last-write-wins, version-vector, 3-way-merge, timestamp) with preserved conflicts | `test_e2e_sync_conflict_preserved` |
| C13 | G8 | experimental | Git version references tracked; auto-commit opt-in | `test_xet_git_versioning_real_repo` |
| C14 | G6 | experimental | Encrypted allowlist (AES-256-GCM) with Ed25519 handshake proof | `test_xet_allowlist_encrypted_roundtrip`, `test_e2e_chunk_exchange` |
| C15 | G8 | experimental | .tonic v2, tonic links, cold-link join, remote URL, daemon persistence, IPC/UI status | `test_xet_tonic_v2_roundtrip`, `test_e2e_cold_link_join` |
| C16 | G9 | experimental | Configuration for XET, xet_sync, CAS/Hub, and NAT ports | `test_xet_config_target_enforced` |
| C17 | G9 | experimental | CLI: ccbt xet, btbt tonic, ccbt cas serve, ccbt hub serve, git-xet | `test_interop_git_xet_roundtrip`, `test_xet_cli_migrate_legacy` |
| C18 | G3 | experimental | CAS client compatible with HF CAS contract and OpenXet | `test_interop_cas_client_openxet`, `test_interop_cas_contract_fixtures` |
| C19 | G5 | experimental | CAS server compatible with stock hf_xet; Hub API with huggingface_hub; Git LFS | `test_interop_hf_xet_against_ccbt_cas`, `test_interop_hub_huggingface_hub` |
| C20 | G2 | experimental | No placeholder XET modules remain reachable from docs | `test_xet_no_placeholder_modules` |

## Gate commands

```bash
python dev/scripts/check_xet_claims.py
python dev/scripts/check_xet_claims.py --release
pytest -c dev/pytest.ini tests/unit/storage/test_xet_golden_codec.py tests/integration/xet_e2e tests/unit/session/test_xet_transport.py tests/unit/consensus/test_consensus_raft_byzantine.py
```
