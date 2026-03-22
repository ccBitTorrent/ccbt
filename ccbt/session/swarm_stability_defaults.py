"""Centralized defaults for swarm-stability and recovery tuning."""

from __future__ import annotations

from typing import Final

# Safe defaults are conservative and intentionally reversible.
# Values are chosen to reduce churn in low-peer states first, then restore
# aggressive behavior only when recovery metrics prove benefit.

PEER_DISCOVERY_DEFAULTS: Final[dict[str, int | float | bool]] = {
    "low_peer_threshold": 1,
    "low_peer_suppression_window_s": 20.0,
    "low_peer_cleanup_suppression_factor": 1.0,
    "bootstrap_seed_replay_limit": 6,
    "bootstrap_retry_memo_ttl_s": 30.0,
    "dht_zero_state_reprobe_wait_s": 45.0,
    "dht_rebootstrap_timeout_s": 45.0,
    "dht_bootstrap_timeout_s": 45.0,
    "dht_bootstrap_retries_max": 3,
    "dht_bootstrap_memo_ttl_s": 120.0,
    "dht_empty_state_backoff_factor": 1.5,
}

HANDSHAKE_CHOKE_DEFAULTS: Final[dict[str, int | float | bool]] = {
    "handshake_timeout_floor_s": 2.0,
    "handshake_timeout_ceiling_s": 10.0,
    "connection_timeout_floor_s": 4.0,
    "connection_timeout_ceiling_s": 18.0,
    "no_active_torrent_grace_s": 2.5,
    "choke_penalty_decay_half_life_s": 90.0,
    "choke_only_penalty_base": 1.0,
    "choke_only_penalty_cap": 3.0,
}

PIECE_SELECTION_DEFAULTS: Final[dict[str, int | float | bool]] = {
    "seeder_preference_boost": 12,
    "throughput_bonus_divisor": 20,
    "min_confidence_window_s": 15.0,
    "no_progress_streak_threshold": 10,
    "no_progress_pause_s": 2.5,
    "availability_deadband_threshold": 3,
    "availability_deadband_s": 1.5,
    "recent_unchoke_window_s": 45.0,
    "alternate_pool_size": 12,
    "alternate_pool_retry_delay_s": 0.5,
    "requeue_debounce_s": 1.25,
    "retry_from_active_delay_s": 2.0,
    "retry_from_active_max_attempts": 2,
}

TRACKER_DHT_DEFAULTS: Final[dict[str, int | float | bool]] = {
    "tracker_first_batch_size": 25,
    "tracker_timeout_s": 12.0,
    "tracker_source_tier_timeout_s": 6.0,
    "dht_recovery_request_budget": 24,
    "dht_recovery_batch_budget": 3,
    "tracker_udp_transaction_budget": 25,
    "tracker_udp_stale_cleanup_window_s": 12.0,
    "tracker_fail_fast_budget_window_s": 30.0,
}

CLEANUP_DEFAULTS: Final[dict[str, int | float | bool]] = {
    "complete_peer_cleanup_protection_s": 12.0,
    "inflight_protection_grace_s": 10.0,
    "stale_health_scale_low_peer": 3.0,
    "stale_health_scale_default": 1.0,
    "stale_cleanup_two_phase_window_s": 2.5,
    "cleanup_grace_after_error_s": 2.0,
}

DEFAULT_ROLLBACK: Final[dict[str, int | float | bool]] = {
    "low_peer_suppression_window_s": 0.0,
    "low_peer_threshold": 1,
    "dht_zero_state_reprobe_wait_s": 15.0,
    "dht_bootstrap_retries_max": 1,
    "dht_bootstrap_memo_ttl_s": 0.0,
    "choke_only_penalty_base": 0.0,
    "choke_only_penalty_cap": 0.0,
    "choke_penalty_decay_half_life_s": 0.0,
    "seeder_preference_boost": 0,
    "throughput_bonus_divisor": 1_000_000,
    "availability_deadband_threshold": 0,
    "availability_deadband_s": 0.0,
    "alternate_pool_size": 0,
    "alternate_pool_retry_delay_s": 0.0,
    "requeue_debounce_s": 0.0,
    "retry_from_active_delay_s": 0.0,
    "retry_from_active_max_attempts": 0,
    "tracker_first_batch_size": 0,
    "tracker_timeout_s": 8.0,
    "tracker_udp_transaction_budget": 8,
    "complete_peer_cleanup_protection_s": 0.0,
    "cleanup_grace_after_error_s": 0.0,
}

SWARM_SAFETY_DEFAULTS: Final[dict[str, dict[str, int | float | bool]]] = {
    "peer_discovery": PEER_DISCOVERY_DEFAULTS,
    "handshake_choke": HANDSHAKE_CHOKE_DEFAULTS,
    "piece_selection": PIECE_SELECTION_DEFAULTS,
    "tracker_dht": TRACKER_DHT_DEFAULTS,
    "cleanup": CLEANUP_DEFAULTS,
}
