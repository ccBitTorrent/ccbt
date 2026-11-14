"""Download-acceleration primitives (pure, testable helpers)."""

from ccbt.performance.acceleration import (
    BlockLatencyTracker,
    DuplicateBudget,
    RampMetrics,
    accel_enabled,
    adaptive_request_timeout,
    adaptive_upload_slots,
    is_dynamic_endgame,
    is_snubbed,
    peer_usefulness_score,
    race_first_success,
    ramp_choking_intervals,
    should_duplicate_block,
    strategy_flag,
    warm_pipeline_depth,
)

__all__ = [
    "BlockLatencyTracker",
    "DuplicateBudget",
    "RampMetrics",
    "accel_enabled",
    "adaptive_request_timeout",
    "adaptive_upload_slots",
    "is_dynamic_endgame",
    "is_snubbed",
    "peer_usefulness_score",
    "race_first_success",
    "ramp_choking_intervals",
    "should_duplicate_block",
    "strategy_flag",
    "warm_pipeline_depth",
]
