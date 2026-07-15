"""Peer discovery telemetry: per-torrent metrics dict + global collector counters.

Grep-stable log prefixes used elsewhere: ``pd_connect_submit``, ``pd_pending_resume``,
``pd_deprecate_private_resume``.
"""

from __future__ import annotations

import contextlib
import time
from typing import Any, Mapping, Optional


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(max(0, min(len(ordered) - 1, round((len(ordered) - 1) * q))))
    return float(ordered[idx])


def _bump_connect_submit_counts(metrics: dict[str, Any], status: str) -> None:
    by_status = metrics.setdefault("connect_submit_total_by_status", {})
    by_status[status] = int(by_status.get(status, 0) or 0) + 1
    if status == "queued_reentrant":
        metrics["connect_reentrant_queued_total"] = (
            int(metrics.get("connect_reentrant_queued_total", 0) or 0) + 1
        )


def _global_connect_submit_counter(status: str) -> None:
    with contextlib.suppress(Exception):
        from ccbt.monitoring import get_metrics_collector

        coll = get_metrics_collector()
        coll.increment_counter(
            "peer_discovery_connect_submit_total",
            1,
            {"status": str(status)},
        )


def record_connect_submit_session(session: Any, status: str) -> None:
    """Record a connect submit outcome when no peer manager ref is available."""
    metrics = getattr(session, "_peer_discovery_metrics", None)
    if isinstance(metrics, dict):
        _bump_connect_submit_counts(metrics, status)
    _global_connect_submit_counter(status)


def _peer_metrics_dict(peer_manager: Any) -> Optional[dict[str, Any]]:
    ref = getattr(peer_manager, "_peer_discovery_metrics_ref", None)
    return ref if isinstance(ref, dict) else None


def record_connect_submit_peer_manager(peer_manager: Any, status: str) -> None:
    """Record connect_to_peers / ConnectSubmitResult status for this torrent."""
    d = _peer_metrics_dict(peer_manager)
    if d is not None:
        _bump_connect_submit_counts(d, status)
    _global_connect_submit_counter(status)


def record_batch_and_deferral_transition(
    peer_manager: Any,
    *,
    batch_owner_active: Optional[bool] = None,
    deferral_active: Optional[bool] = None,
) -> None:
    """Increment batch-owner / DHT-deferral transition tallies for split-state telemetry."""
    d = _peer_metrics_dict(peer_manager)
    if d is None:
        return
    if batch_owner_active is not None:
        bucket = d.setdefault("batch_owner_state_transition_total", {})
        key = "to_active" if batch_owner_active else "to_idle"
        bucket[key] = int(bucket.get(key, 0) or 0) + 1
    if deferral_active is not None:
        dbucket = d.setdefault("dht_deferral_state_transition_total", {})
        dkey = "to_active" if deferral_active else "to_idle"
        dbucket[dkey] = int(dbucket.get(dkey, 0) or 0) + 1
    with contextlib.suppress(Exception):
        from ccbt.monitoring import get_metrics_collector

        coll = get_metrics_collector()
        if batch_owner_active is not None:
            coll.increment_counter(
                "peer_discovery_batch_owner_transition_total",
                1,
                {"state": "active" if batch_owner_active else "idle"},
            )
        if deferral_active is not None:
            coll.increment_counter(
                "peer_discovery_dht_deferral_transition_total",
                1,
                {"state": "active" if deferral_active else "idle"},
            )


def record_pending_resume_edge(peer_manager: Any, reason: str) -> None:
    """Count pending-queue resume scheduling by normalized edge (prefix before ':')."""
    edge = (reason or "unknown").split(":", 1)[0]
    d = _peer_metrics_dict(peer_manager)
    if d is not None:
        t = d.setdefault("pending_resume_edge_trigger_total", {})
        t[edge] = int(t.get(edge, 0) or 0) + 1
    with contextlib.suppress(Exception):
        from ccbt.monitoring import get_metrics_collector

        get_metrics_collector().increment_counter(
            "peer_discovery_pending_resume_edge_total",
            1,
            {"edge": edge},
        )


def record_pending_resume_suppressed_inflight(peer_manager: Any) -> None:
    """Increment counter when resume is deferred (owner active or coalesced worker)."""
    d = _peer_metrics_dict(peer_manager)
    if d is not None:
        d["pending_resume_suppressed_inflight_only_total"] = (
            int(d.get("pending_resume_suppressed_inflight_only_total", 0) or 0) + 1
        )
    with contextlib.suppress(Exception):
        from ccbt.monitoring import get_metrics_collector

        get_metrics_collector().increment_counter(
            "peer_discovery_pending_resume_suppressed_inflight_total", 1
        )


def observe_pending_peer_queue(peer_manager: Any) -> None:
    """Sample pending connect queue depth + oldest enqueue age into session metrics / collector."""
    d = _peer_metrics_dict(peer_manager)
    if d is None:
        return
    try:
        depth = len(getattr(peer_manager, "_pending_peer_queue", []) or [])
    except Exception:
        depth = 0
    d["pending_connect_queue_depth_gauge"] = depth
    now = time.monotonic()
    oldest_age = 0.0
    enq = getattr(peer_manager, "_pending_peer_enqueued_at", None)
    if isinstance(enq, dict) and enq:
        with contextlib.suppress(Exception):
            oldest_age = max(0.0, now - min(float(t) for t in enq.values()))
    d["pending_connect_queue_oldest_age_s_gauge"] = oldest_age
    samples = d.setdefault("pending_connect_queue_depth_observations", [])
    if isinstance(samples, list) and len(samples) < 2000:
        samples.append(float(depth))
    ages = d.setdefault("pending_connect_queue_age_observations_s", [])
    if isinstance(ages, list) and len(ages) < 2000:
        ages.append(float(oldest_age))
    d["pending_age_p95_s"] = _percentile(
        [float(v) for v in ages if isinstance(v, (int, float))], 0.95
    )
    samples_ts = d.setdefault("pending_connect_queue_depth_observations_ts", [])
    if isinstance(samples_ts, list) and len(samples_ts) < 2000:
        samples_ts.append((float(now), float(depth)))
    # Rolling 10s drain-rate: positive means queue draining.
    drain_rate = 0.0
    if isinstance(samples_ts, list) and len(samples_ts) >= 2:
        window_start = float(now) - 10.0
        points = [
            (float(ts), float(dp))
            for ts, dp in samples_ts
            if isinstance(ts, (int, float))
            and isinstance(dp, (int, float))
            and float(ts) >= window_start
        ]
        if len(points) >= 2:
            first_ts, first_depth = points[0]
            last_ts, last_depth = points[-1]
            elapsed = max(0.001, last_ts - first_ts)
            drain_rate = max(0.0, (first_depth - last_depth) / elapsed)
    d["pending_drain_rate_per_10s"] = float(drain_rate * 10.0)
    deferred_total = float(d.get("deferred_peer_candidates_total", 0) or 0)
    ingress_drop_total = float(d.get("ingress_budget_drop_total", 0) or 0)
    if deferred_total > 0:
        d["pending_ingress_drop_ratio"] = min(1.0, ingress_drop_total / deferred_total)
    else:
        d["pending_ingress_drop_ratio"] = 0.0
    with contextlib.suppress(Exception):
        from ccbt.monitoring import get_metrics_collector

        coll = get_metrics_collector()
        coll.set_gauge("peer_discovery_pending_queue_depth", float(depth))
        coll.set_gauge("peer_discovery_pending_queue_age_p95_s", d["pending_age_p95_s"])
        coll.set_gauge(
            "peer_discovery_pending_queue_drain_rate_per_10s",
            d["pending_drain_rate_per_10s"],
        )
        coll.set_gauge(
            "peer_discovery_pending_ingress_drop_ratio",
            float(d.get("pending_ingress_drop_ratio", 0.0) or 0.0),
        )
        coll.record_histogram(
            "peer_discovery_pending_queue_age_s",
            float(oldest_age),
        )


def record_deprecated_private_resume_reason(
    peer_manager: Any, reason: str, *, caller: str
) -> None:
    """Track non-canonical _schedule_pending_resume reasons for compatibility diagnostics.

    Deprecated / legacy: counts private resume reason strings that bypass the canonical
    reason vocabulary; kept for migration telemetry only (see ``_ALLOWED_RESUME_REASONS``).
    """
    d = _peer_metrics_dict(peer_manager)
    if d is not None:
        bucket = d.setdefault("deprecated_private_pending_resume_reason_total", {})
        key = f"{caller}:{reason}"
        bucket[key] = int(bucket.get(key, 0) or 0) + 1


_ALLOWED_RESUME_REASONS: frozenset[str] = frozenset(
    {
        "capacity_change",
        "requestable_peer_deficit",
        "peer_disconnected",
        "post_batch_completion",
        "hard_unchoke_recovery",
        "pipeline_timeout_stall",
        "pipeline_timeout_stall_disconnect",
        "waiting_for_slot_release",
        "inflight_dedup",
        "inflight_drained",
        "status_loop_stall",
        "piece_selector_no_piece_info",
        "zero_active_reentrant_drain",
        "stale_batch_owner_reset",
    }
)


def maybe_log_deprecated_pending_resume_reason(peer_manager: Any, reason: str) -> None:
    """If reason is not in the canonical set, count + DEBUG deprecation (grep: pd_deprecate_private_resume)."""
    base = (reason or "unknown").split(":", 1)[0]
    if base in _ALLOWED_RESUME_REASONS:
        return
    record_deprecated_private_resume_reason(
        peer_manager, reason, caller="schedule_pending_resume"
    )
    log = getattr(peer_manager, "logger", None)
    if log is not None:
        with contextlib.suppress(Exception):
            log.debug(
                "pd_deprecate_private_resume reason=%s full_reason=%s",
                base,
                reason,
            )


def attach_peer_discovery_metrics_ref(
    peer_manager: Any, metrics: Mapping[str, Any]
) -> None:
    """Bind session peer discovery metrics dict onto the peer manager (weak ownership)."""
    if isinstance(metrics, dict):
        peer_manager._peer_discovery_metrics_ref = metrics  # noqa: SLF001


def observe_udp_tracker_pending_window(pending_count: int) -> None:
    """Publish process-wide UDP tracker in-flight wait count (singleton client).

    Emits a gauge (current depth) and a histogram sample (distribution of depth
    when sampled, throttled by the UDP client to ~4 Hz).
    """
    with contextlib.suppress(Exception):
        from ccbt.monitoring import get_metrics_collector

        coll = get_metrics_collector()
        v = float(pending_count)
        coll.set_gauge("discovery_udp_tracker_pending_requests", v)
        coll.record_histogram("discovery_udp_tracker_pending_requests_sample", v)
        coll.increment_counter("discovery_udp_tracker_pending_gauge_updates_total", 1)
