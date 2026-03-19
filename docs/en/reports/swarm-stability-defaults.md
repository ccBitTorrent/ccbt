# Swarm Stability Safe Defaults Register

## Purpose

This document defines conservative defaults and rollback targets for newly introduced
retry/backoff/selection behaviors before any behavior-changing edits are merged.

All defaults are centralized in `ccbt/session/swarm_stability_defaults.py`.

## Default sets by control surface

### Peer discovery and bootstrap control

| Parameter | Default | Rollback |
| - | -: | - |
| `peer_discovery.low_peer_threshold` | `1` | `1` |
| `peer_discovery.low_peer_suppression_window_s` | `20.0` | `0.0` |
| `peer_discovery.low_peer_cleanup_suppression_factor` | `1.0` | `1.0` |
| `peer_discovery.bootstrap_retry_memo_ttl_s` | `30.0` | `0.0` |
| `peer_discovery.dht_zero_state_reprobe_wait_s` | `45.0` | `15.0` |
| `peer_discovery.dht_bootstrap_memo_ttl_s` | `120.0` | `0.0` |
| `peer_discovery.dht_bootstrap_retries_max` | `3` | `1` |
| `peer_discovery.dht_empty_state_backoff_factor` | `1.5` | `1.0` |

### Handshake/choke handling

| Parameter | Default | Rollback |
| - | -: | - |
| `handshake_choke.handshake_timeout_floor_s` | `2.0` | `1.0` |
| `handshake_choke.handshake_timeout_ceiling_s` | `10.0` | `10.0` |
| `handshake_choke.connection_timeout_floor_s` | `4.0` | `2.0` |
| `handshake_choke.connection_timeout_ceiling_s` | `18.0` | `18.0` |
| `handshake_choke.no_active_torrent_grace_s` | `2.5` | `0.0` |
| `handshake_choke.choke_penalty_decay_half_life_s` | `90.0` | `0.0` |
| `handshake_choke.choke_only_penalty_base` | `1.0` | `0.0` |
| `handshake_choke.choke_only_penalty_cap` | `3.0` | `0.0` |

### Piece selection and request productivity

| Parameter | Default | Rollback |
| - | -: | - |
| `piece_selection.seeder_preference_boost` | `12` | `0` |
| `piece_selection.throughput_bonus_divisor` | `20` | `1000000` |
| `piece_selection.min_confidence_window_s` | `15.0` | `0.0` |
| `piece_selection.no_progress_streak_threshold` | `10` | `9999` |
| `piece_selection.no_progress_pause_s` | `2.5` | `0.0` |
| `piece_selection.alternate_pool_size` | `12` | `0` |
| `piece_selection.alternate_pool_retry_delay_s` | `0.5` | `0.0` |
| `piece_selection.requeue_debounce_s` | `1.25` | `0.0` |

### Tracker/DHT recovery controls

| Parameter | Default | Rollback |
| - | -: | - |
| `tracker_dht.tracker_first_batch_size` | `25` | `0` |
| `tracker_dht.tracker_timeout_s` | `12.0` | `8.0` |
| `tracker_dht.tracker_source_tier_timeout_s` | `6.0` | `6.0` |
| `tracker_dht.dht_recovery_request_budget` | `24` | `0` |
| `tracker_dht.dht_recovery_batch_budget` | `3` | `1` |
| `tracker_dht.tracker_udp_transaction_budget` | `25` | `8` |
| `tracker_dht.tracker_udp_stale_cleanup_window_s` | `12.0` | `0.0` |
| `tracker_dht.tracker_fail_fast_budget_window_s` | `30.0` | `0.0` |

### Cleanup stability controls

| Parameter | Default | Rollback |
| - | -: | - |
| `cleanup.complete_peer_cleanup_protection_s` | `12.0` | `0.0` |
| `cleanup.inflight_protection_grace_s` | `10.0` | `0.0` |
| `cleanup.stale_health_scale_low_peer` | `3.0` | `1.0` |
| `cleanup.stale_health_scale_default` | `1.0` | `1.0` |
| `cleanup.stale_cleanup_two_phase_window_s` | `2.5` | `0.0` |
| `cleanup.cleanup_grace_after_error_s` | `2.0` | `0.0` |

## Integration note

- If rollout introduces unexpected regressions, set a specific parameter family
  to its rollback value in the runtime configuration path, then re-run milestone
  gates before attempting the next adjustment.
- No behavior-changing code edit should be merged without first referencing one
  of the default dictionaries in this registry.
