"""Deterministic virtual-swarm simulation for A/B verification.

Models the mechanisms in the acceleration plan, not the wire protocol:
dial parallelism determines when peers become requestable; each block is
served by a peer with (latency + size/bandwidth) service time; the
accelerated strategy duplicates straggler blocks (first arrival wins,
losers are wasted bytes) and uses adaptive timeouts. Seeded and fully
deterministic so baseline vs treatment is reproducible in CI.
"""

from __future__ import annotations

import heapq
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class SimPeer:
    """One scripted virtual peer."""

    peer_id: int
    latency_s: float
    bandwidth_bps: float
    unchoke_delay_s: float
    reliability: float = 1.0  # fraction of requests that ever complete


@dataclass
class SimResult:
    """Outcome of one simulated download."""

    completion_s: float
    time_to_first_requestable_s: float
    time_to_first_piece_s: float
    time_to_50pct_s: float
    wasted_bytes: int
    useful_bytes: int
    duplicate_requests: int
    cancelled_requests: int = 0

    @property
    def wasted_fraction(self) -> float:
        """Fraction of total bytes that were redundant."""
        total = self.useful_bytes + self.wasted_bytes
        return (self.wasted_bytes / total) if total else 0.0

    def as_dict(self) -> dict[str, float]:
        """Return rounded metrics as a plain dict."""
        return {
            "completion_s": round(self.completion_s, 3),
            "time_to_first_requestable_s": round(self.time_to_first_requestable_s, 3),
            "time_to_first_piece_s": round(self.time_to_first_piece_s, 3),
            "time_to_50pct_s": round(self.time_to_50pct_s, 3),
            "wasted_fraction": round(self.wasted_fraction, 4),
            "duplicate_requests": float(self.duplicate_requests),
            "cancelled_requests": float(self.cancelled_requests),
        }


def make_peers(count: int, seed: int = 1234) -> list[SimPeer]:
    """Generate a deterministic public-swarm-like peer mix."""
    rng = random.Random(seed)
    peers: list[SimPeer] = []
    for i in range(count):
        # Public-swarm-like mix: a few fast seeders, many slow leechers.
        kind = rng.random()
        if kind < 0.2:
            bw, lat = rng.uniform(5e6, 20e6), rng.uniform(0.02, 0.08)
        elif kind < 0.7:
            bw, lat = rng.uniform(5e5, 5e6), rng.uniform(0.05, 0.2)
        else:
            bw, lat = rng.uniform(5e4, 5e5), rng.uniform(0.15, 0.3)
        peers.append(
            SimPeer(
                peer_id=i,
                latency_s=lat,
                bandwidth_bps=bw,
                unchoke_delay_s=rng.uniform(0.5, 10.0),
                reliability=0.7 if rng.random() < 0.15 else 1.0,
            )
        )
    return peers


def simulate(
    *,
    peers: list[SimPeer],
    num_blocks: int = 400,
    block_bytes: int = 16384,
    blocks_per_piece: int = 16,
    dial_parallelism: int = 8,
    connect_batch_s: float = 1.0,
    duplicate_stragglers: bool = False,
    straggler_after_s: float = 2.0,
    max_copies: int = 3,
    pipeline_per_peer: int = 16,
    request_timeout_s: float = 60.0,
) -> SimResult:
    """Event-driven block download simulation (single torrent)."""
    # When each peer becomes requestable: dial batch + unchoke delay.
    ready_at = {
        p.peer_id: (p.peer_id // max(1, dial_parallelism)) * connect_batch_s
        + p.unchoke_delay_s
        for p in peers
    }
    # Time until a useful cohort (8th, or all if fewer) is requestable;
    # this is what dial parallelism actually accelerates.
    _sorted_ready = sorted(ready_at.values())
    first_requestable = (
        _sorted_ready[min(7, len(_sorted_ready) - 1)] if _sorted_ready else 0.0
    )

    # Events: (time, seq, kind, block, peer_id)
    events: list[tuple[float, int, str, int, int]] = []
    seq = 0

    def push(t: float, kind: str, block: int, pid: int) -> None:
        nonlocal seq
        heapq.heappush(events, (t, seq, kind, block, pid))
        seq += 1

    in_flight: dict[int, dict[int, float]] = {}  # block -> {peer: started}
    completed: set[int] = set()
    busy: dict[int, int] = {p.peer_id: 0 for p in peers}
    now = 0.0
    next_block = 0
    wasted = 0
    dup_requests = 0
    cancelled = 0
    first_piece_at = 0.0
    half_at = 0.0
    completed_pieces: set[int] = set()

    def service_time(p: SimPeer) -> float:
        return p.latency_s + block_bytes / max(1.0, p.bandwidth_bps)

    def try_assign(now_t: float) -> None:
        nonlocal next_block, dup_requests
        # Assign fresh blocks to idle-ish ready peers (fastest first).
        ready_peers = sorted(
            (
                p
                for p in peers
                if ready_at[p.peer_id] <= now_t and busy[p.peer_id] < pipeline_per_peer
            ),
            key=lambda p: service_time(p),
        )
        for p in ready_peers:
            while busy[p.peer_id] < pipeline_per_peer and next_block < num_blocks:
                b = next_block
                next_block += 1
                if p.reliability < 1.0 and (b * 31 + p.peer_id) % 10 >= int(
                    p.reliability * 10
                ):
                    # Unreliable peer: request hangs (only duplication/timeout saves it)
                    in_flight.setdefault(b, {})[p.peer_id] = now_t
                    busy[p.peer_id] += 1
                    continue
                in_flight.setdefault(b, {})[p.peer_id] = now_t
                busy[p.peer_id] += 1
                push(now_t + service_time(p), "done", b, p.peer_id)
        # Duplicate stragglers onto fastest idle ready peer.
        if duplicate_stragglers:
            for b, holders in list(in_flight.items()):
                if b in completed or len(holders) >= max_copies:
                    continue
                age = now_t - min(holders.values())
                if age < straggler_after_s:
                    continue
                for p in ready_peers:
                    if p.peer_id in holders or busy[p.peer_id] >= pipeline_per_peer:
                        continue
                    holders[p.peer_id] = now_t
                    busy[p.peer_id] += 1
                    dup_requests += 1
                    if not (
                        p.reliability < 1.0
                        and (b * 31 + p.peer_id) % 10 >= int(p.reliability * 10)
                    ):
                        push(now_t + service_time(p), "done", b, p.peer_id)
                    break

    for p in peers:
        push(ready_at[p.peer_id], "ready", -1, p.peer_id)
    # Periodic straggler scan.
    t_scan = 0.5
    while t_scan < 3600:
        push(t_scan, "scan", -1, -1)
        t_scan += 0.5

    guard = 0
    while events and len(completed) < num_blocks:
        guard += 1
        if guard > 2_000_000:
            break
        now, _, kind, block, pid = heapq.heappop(events)
        if kind == "scan":
            # Timeout rescue: blocks held (hung) beyond request_timeout are
            # freed and re-issued to the fastest reliable ready peer.
            for b, holders in list(in_flight.items()):
                if b in completed or not holders:
                    continue
                if now - min(holders.values()) < request_timeout_s:
                    continue
                cancelled += len(holders)
                for old_pid in holders:
                    busy[old_pid] = max(0, busy[old_pid] - 1)
                del in_flight[b]
                rescuers = sorted(
                    (
                        p
                        for p in peers
                        if p.reliability >= 1.0 and ready_at[p.peer_id] <= now
                    ),
                    key=lambda p: service_time(p),
                )
                if rescuers:
                    rp = rescuers[0]
                    in_flight[b] = {rp.peer_id: now}
                    busy[rp.peer_id] += 1
                    push(now + service_time(rp), "done", b, rp.peer_id)
        if kind == "done":
            if pid in busy:
                busy[pid] = max(0, busy[pid] - 1)
            if block in completed:
                wasted += block_bytes
                continue
            completed.add(block)
            # Other copies of this block are wasted work in flight.
            for other_pid in in_flight.pop(block, {}):
                if other_pid != pid:
                    wasted += 0  # counted if/when they complete above
            piece = block // blocks_per_piece
            if piece not in completed_pieces:
                piece_blocks = range(
                    piece * blocks_per_piece,
                    min(num_blocks, (piece + 1) * blocks_per_piece),
                )
                if all(b in completed for b in piece_blocks):
                    completed_pieces.add(piece)
                    if not first_piece_at:
                        first_piece_at = now
            if not half_at and len(completed) >= num_blocks // 2:
                half_at = now
        try_assign(now)

    useful = len(completed) * block_bytes
    return SimResult(
        completion_s=now,
        time_to_first_requestable_s=first_requestable,
        time_to_first_piece_s=first_piece_at,
        time_to_50pct_s=half_at,
        wasted_bytes=wasted,
        useful_bytes=useful,
        duplicate_requests=dup_requests,
        cancelled_requests=cancelled,
    )


def make_stall_peers() -> list[SimPeer]:
    """Build the peer set reproducing the measured live stall.

    1 slow unreliable supplier, 1 peer that never unchokes, and a
    handful of normal peers behind them.
    """
    peers = [
        # Slow supplier that hangs ~30% of requests (the 48/48 pipeline peer)
        SimPeer(
            peer_id=0,
            latency_s=0.6,
            bandwidth_bps=50_000,
            unchoke_delay_s=0.5,
            reliability=0.7,
        ),
        # Permanently choked peer (never becomes requestable)
        SimPeer(
            peer_id=1,
            latency_s=0.1,
            bandwidth_bps=5_000_000,
            unchoke_delay_s=1e9,
            reliability=1.0,
        ),
    ]
    peers.extend(
        SimPeer(
            peer_id=i,
            latency_s=0.08,
            bandwidth_bps=2_000_000,
            unchoke_delay_s=3.0 + i,
            reliability=1.0,
        )
        for i in range(2, 8)
    )
    return peers


def run_stall_scenario(num_blocks: int = 400) -> dict[str, dict[str, float]]:
    """Run baseline vs treatment configurations on the stall peer set.

    Baseline: deep pipeline, long timeout, no duplication. Treatment:
    capped pipeline, short timeout, straggler duplication.
    """
    peers = make_stall_peers()
    baseline = simulate(
        peers=peers,
        num_blocks=num_blocks,
        dial_parallelism=2,
        duplicate_stragglers=False,
        pipeline_per_peer=48,
        request_timeout_s=22.5,
    )
    treatment = simulate(
        peers=peers,
        num_blocks=num_blocks,
        dial_parallelism=8,
        duplicate_stragglers=True,
        straggler_after_s=1.0,
        max_copies=3,
        pipeline_per_peer=16,
        request_timeout_s=15.0,
    )
    return {"baseline": baseline.as_dict(), "treatment": treatment.as_dict()}


def run_scenario(
    peer_count: int, seed: int = 1234, num_blocks: int = 400
) -> dict[str, dict[str, float]]:
    """Run baseline vs treatment for one peer-count scenario."""
    peers = make_peers(peer_count, seed=seed)
    baseline = simulate(
        peers=peers,
        num_blocks=num_blocks,
        dial_parallelism=8,
        duplicate_stragglers=False,
    )
    treatment = simulate(
        peers=peers,
        num_blocks=num_blocks,
        dial_parallelism=24,
        duplicate_stragglers=True,
        straggler_after_s=1.0,
        max_copies=3,
    )
    return {"baseline": baseline.as_dict(), "treatment": treatment.as_dict()}
