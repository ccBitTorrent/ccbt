"""Pure helpers for download acceleration.

These functions encode the decisions described in the acceleration plan
(straggler duplication, adaptive timeouts, snub detection, BEP 6 aware
ranking, ramp-aware choking) without any I/O, so they can be unit tested
deterministically and reused by the peer/piece managers and by the
virtual-swarm benchmark.

References: BEP 3 (choking / optimistic unchoke), BEP 6 (fast extension /
allow-fast), BEP 11 (PEX), libtorrent concepts of snubbing and endgame
duplicate requests.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Optional, TypeVar

T = TypeVar("T")


def accel_enabled(config: Any) -> bool:
    """Swarm acceleration is ON by default.

    Only an explicit ``False`` on ``config.network.swarm_acceleration_enabled``
    disables it; a missing/``None`` attribute (legacy or partial configs)
    means enabled.
    """
    network = getattr(config, "network", None)
    value = getattr(network, "swarm_acceleration_enabled", None)
    return True if value is None else bool(value)


def strategy_flag(config: Any, name: str) -> bool:
    """Strategy acceleration flags are likewise on unless explicitly off."""
    strategy = getattr(config, "strategy", None)
    value = getattr(strategy, name, None)
    return True if value is None else bool(value)


async def race_first_success(
    candidates: dict[str, Awaitable[T]],
) -> tuple[str, T]:
    """Race awaitables; return the first success, cancelling the losers.

    Failures are tolerated until every candidate has failed, in which case
    the first failure is raised. Loser results that arrive anyway are
    consumed so no task exception goes unretrieved.
    """
    tasks = {name: asyncio.ensure_future(coro) for name, coro in candidates.items()}
    if not tasks:
        msg = "race_first_success requires at least one candidate"
        raise ValueError(msg)
    first_error: Optional[BaseException] = None
    try:
        pending = set(tasks.values())
        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for name, task in list(tasks.items()):
                if task not in done:
                    continue
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc is None:
                    for other in pending:
                        other.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    return name, task.result()
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error
        msg = "All raced candidates were cancelled"
        raise ConnectionError(msg)
    finally:
        for task in tasks.values():
            if not task.done():
                task.cancel()


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(sorted_values[int(rank)])
    frac = rank - lo
    return float(sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac)


class BlockLatencyTracker:
    """Rolling per-swarm / per-peer block latency samples."""

    def __init__(self, max_samples: int = 512) -> None:
        """Keep at most max_samples recent latency samples."""
        self._samples: deque[float] = deque(maxlen=max_samples)

    def record(self, latency_s: float) -> None:
        """Record one block latency sample in seconds."""
        if latency_s > 0:
            self._samples.append(float(latency_s))

    def __len__(self) -> int:
        """Return the number of retained samples."""
        return len(self._samples)

    def percentile(self, pct: float, default: float = 0.0) -> float:
        """Return the given percentile, or default when empty."""
        if not self._samples:
            return default
        return _percentile(sorted(self._samples), pct)

    @property
    def p50(self) -> float:
        """Median block latency."""
        return self.percentile(50)

    @property
    def p90(self) -> float:
        """90th-percentile block latency."""
        return self.percentile(90)

    @property
    def p95(self) -> float:
        """95th-percentile block latency."""
        return self.percentile(95)


class DuplicateBudget:
    """Rolling budget for redundant (duplicate) block bytes.

    Duplication is only allowed while redundant bytes stay at or below
    ``max_fraction`` of useful downloaded bytes over the observed window.
    """

    def __init__(self, max_fraction: float = 0.10) -> None:
        """Cap redundant bytes at max_fraction of total bytes."""
        self.max_fraction = max(0.0, min(1.0, float(max_fraction)))
        self.useful_bytes = 0
        self.duplicate_bytes = 0

    def record_useful(self, nbytes: int) -> None:
        """Record useful first-arrival bytes."""
        if nbytes > 0:
            self.useful_bytes += int(nbytes)

    def record_duplicate(self, nbytes: int) -> None:
        """Record redundant duplicate bytes."""
        if nbytes > 0:
            self.duplicate_bytes += int(nbytes)

    @property
    def wasted_fraction(self) -> float:
        """Fraction of total bytes that were redundant."""
        total = self.useful_bytes + self.duplicate_bytes
        return (self.duplicate_bytes / total) if total > 0 else 0.0

    def allows(self, next_bytes: int = 0) -> bool:
        """True if sending another duplicate keeps us within budget."""
        if self.max_fraction <= 0:
            return False
        total = self.useful_bytes + self.duplicate_bytes + max(0, int(next_bytes))
        if total <= 0:
            return True
        return (
            self.duplicate_bytes + max(0, int(next_bytes))
        ) / total <= self.max_fraction + 1e-9


def adaptive_request_timeout(
    p95_latency_s: float,
    *,
    multiplier: float = 4.0,
    minimum_s: float = 5.0,
    maximum_s: float = 30.0,
    fallback_s: float = 30.0,
) -> float:
    """Timeout = clamp(multiplier * p95 latency, min, max)."""
    if p95_latency_s <= 0:
        return max(minimum_s, min(maximum_s, fallback_s))
    return max(minimum_s, min(maximum_s, multiplier * float(p95_latency_s)))


def should_duplicate_block(
    *,
    block_age_s: float,
    swarm_p90_latency_s: float,
    blocks_remaining_in_piece: int,
    existing_copies: int,
    max_copies: int = 3,
    budget_allows: bool = True,
    enabled: bool = True,
) -> bool:
    """Decide whether to speculatively duplicate an in-flight block.

    Fires when the block is a straggler (age beyond swarm p90, with a
    small-sample floor) or when its piece is nearly complete (<=2 blocks
    left) at any overall download progress.
    """
    if not enabled or not budget_allows:
        return False
    if existing_copies <= 0 or existing_copies >= max(1, max_copies):
        return False
    is_last_blocks = 0 < blocks_remaining_in_piece <= 2
    # Require at least ~1s of age so we never duplicate instantly, and
    # beyond p90 when we have a meaningful latency estimate.
    threshold = max(1.0, swarm_p90_latency_s) if swarm_p90_latency_s > 0 else 1.0
    is_straggler = block_age_s >= threshold
    return bool((is_last_blocks and block_age_s >= 1.0) or is_straggler)


def is_dynamic_endgame(
    *,
    remaining_pieces: int,
    total_pieces: int,
    threshold: float = 0.95,
    last_pieces: int = 20,
    all_remaining_stalled: bool = False,
) -> bool:
    """Endgame by progress, by absolute tail size, or by stall."""
    if total_pieces <= 0 or remaining_pieces <= 0:
        return False
    if remaining_pieces <= total_pieces * (1.0 - threshold):
        return True
    # Absolute-tail rule only for torrents larger than the tail window;
    # otherwise every small torrent would start in endgame.
    if total_pieces > last_pieces and remaining_pieces <= max(1, last_pieces):
        return True
    return bool(all_remaining_stalled)


def is_snubbed(
    *,
    seconds_since_payload: float,
    seconds_unchoked: float,
    others_delivering: bool,
    threshold_s: float = 10.0,
) -> bool:
    """Peer is unchoked but delivers nothing while others deliver (libtorrent snub)."""
    return bool(
        others_delivering
        and seconds_unchoked >= threshold_s
        and seconds_since_payload >= threshold_s
    )


def peer_usefulness_score(
    *,
    has_needed_piece: bool = False,
    rarity_overlap: float = 0.0,
    historic_unchoke_rate: float = 0.0,
    download_rate_bps: float = 0.0,
    connect_latency_s: float = 0.0,
    seconds_since_failure: float = 1e9,
    is_snubbed_peer: bool = False,
) -> float:
    """Higher is dialled / chosen first."""
    score = 0.0
    if has_needed_piece:
        score += 100.0
    score += 50.0 * max(0.0, min(1.0, rarity_overlap))
    score += 40.0 * max(0.0, min(1.0, historic_unchoke_rate))
    # log-scaled throughput contribution, ~0..30
    if download_rate_bps > 0:
        score += min(30.0, 10.0 * math.log10(1.0 + download_rate_bps / 1024.0))
    if connect_latency_s > 0:
        score -= min(20.0, connect_latency_s * 10.0)
    if seconds_since_failure < 60.0:
        score -= 30.0 * (1.0 - max(0.0, seconds_since_failure) / 60.0)
    if is_snubbed_peer:
        score -= 80.0
    return score


def warm_pipeline_depth(
    *,
    current_depth: int,
    initial_depth: int = 32,
    min_depth: int = 4,
    max_depth: int = 128,
    bdp_blocks: int = 0,
) -> int:
    """Pipeline depth at connect / warm-up: never below warm start or BDP need."""
    target = max(int(current_depth), int(initial_depth))
    if bdp_blocks > 0:
        target = max(target, int(bdp_blocks))
    return max(min_depth, min(max_depth, target))


def adaptive_upload_slots(
    *,
    base_slots: int = 8,
    max_slots: int = 16,
    upload_rate_bps: float = 0.0,
    requestable_peers: int = 0,
    requestable_target: int = 0,
) -> int:
    """Scale upload slots with measured upload capacity during a deficit."""
    slots = int(base_slots)
    if requestable_target > 0 and requestable_peers < requestable_target:
        # Roughly one extra slot per 512 KiB/s of upload headroom.
        extra = int(upload_rate_bps // (512 * 1024))
        slots = max(slots, min(int(max_slots), int(base_slots) + extra))
    return max(1, min(int(max_slots), slots))


def ramp_choking_intervals(
    *,
    requestable_peers: int,
    requestable_target: int,
    unchoke_interval_s: float = 10.0,
    optimistic_interval_s: float = 30.0,
) -> tuple[float, float]:
    """Faster choking cadence while we still lack requestable peers."""
    if requestable_target > 0 and requestable_peers < requestable_target:
        return (min(unchoke_interval_s, 5.0), min(optimistic_interval_s, 20.0))
    return (float(unchoke_interval_s), float(optimistic_interval_s))


@dataclass
class RampMetrics:
    """Once-only ramp-up milestones plus duplicate/cancel counters."""

    started_monotonic: float = field(default_factory=time.monotonic)
    time_to_first_requestable_s: Optional[float] = None
    time_to_first_productive_s: Optional[float] = None
    time_to_first_piece_s: Optional[float] = None
    time_to_pct_s: dict[int, Optional[float]] = field(
        default_factory=lambda: {10: None, 50: None, 90: None}
    )
    duplicate_bytes: int = 0
    duplicate_requests: int = 0
    cancels_sent: int = 0
    useful_bytes: int = 0
    requestable_series: list[tuple[float, int]] = field(default_factory=list)

    def _elapsed(self, now: Optional[float] = None) -> float:
        """Seconds since the ramp clock started."""
        return (now if now is not None else time.monotonic()) - self.started_monotonic

    def touch_requestable(self, count: int, now: Optional[float] = None) -> None:
        """Record the current requestable-peer count."""
        elapsed = self._elapsed(now)
        self.requestable_series.append((elapsed, int(count)))
        if count > 0 and self.time_to_first_requestable_s is None:
            self.time_to_first_requestable_s = elapsed

    def touch_productive(self, count: int, now: Optional[float] = None) -> None:
        """Record first productive (data-delivering) peer sighting."""
        if count > 0 and self.time_to_first_productive_s is None:
            self.time_to_first_productive_s = self._elapsed(now)

    def touch_first_piece(self, now: Optional[float] = None) -> None:
        """Record completion of the first verified piece."""
        if self.time_to_first_piece_s is None:
            self.time_to_first_piece_s = self._elapsed(now)

    def touch_progress(self, fraction: float, now: Optional[float] = None) -> None:
        """Record percent-complete milestones from a 0..1 fraction."""
        elapsed = self._elapsed(now)
        for pct in (10, 50, 90):
            if fraction * 100.0 >= pct and self.time_to_pct_s[pct] is None:
                self.time_to_pct_s[pct] = elapsed

    def snapshot(self) -> dict[str, object]:
        """Return all ramp metrics as a plain dict."""
        total = self.useful_bytes + self.duplicate_bytes
        return {
            "time_to_first_requestable_s": self.time_to_first_requestable_s,
            "time_to_first_productive_s": self.time_to_first_productive_s,
            "time_to_first_piece_s": self.time_to_first_piece_s,
            "time_to_10pct_s": self.time_to_pct_s[10],
            "time_to_50pct_s": self.time_to_pct_s[50],
            "time_to_90pct_s": self.time_to_pct_s[90],
            "duplicate_bytes": self.duplicate_bytes,
            "duplicate_requests": self.duplicate_requests,
            "cancels_sent": self.cancels_sent,
            "duplicate_wasted_fraction": (self.duplicate_bytes / total)
            if total
            else 0.0,
            "requestable_series": list(self.requestable_series),
        }
