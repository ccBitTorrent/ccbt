"""Unit tests for peer discovery telemetry helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ccbt.session.peer_discovery_telemetry import (
    attach_peer_discovery_metrics_ref,
    observe_pending_peer_queue,
    record_batch_and_deferral_transition,
    record_connect_submit_peer_manager,
    record_connect_submit_session,
)

pytestmark = [pytest.mark.unit, pytest.mark.session]


def test_record_connect_submit_session_updates_dict() -> None:
    """Session-level connect_submit counters increment without a peer manager."""
    metrics = {
        "connect_submit_total_by_status": {},
        "connect_reentrant_queued_total": 0,
    }
    session = SimpleNamespace(_peer_discovery_metrics=metrics)
    record_connect_submit_session(session, "noop_empty")
    assert metrics["connect_submit_total_by_status"]["noop_empty"] == 1


def test_record_connect_submit_peer_manager_with_ref() -> None:
    """Peer manager ref wires metrics dict for connect_to_peers outcomes."""
    metrics: dict = {
        "connect_submit_total_by_status": {},
        "connect_reentrant_queued_total": 0,
    }
    pm = SimpleNamespace()
    attach_peer_discovery_metrics_ref(pm, metrics)
    record_connect_submit_peer_manager(pm, "queued_reentrant")
    assert metrics["connect_submit_total_by_status"]["queued_reentrant"] == 1
    assert metrics["connect_reentrant_queued_total"] == 1


def test_batch_and_deferral_transitions_increment() -> None:
    """Owner/deferral on+off transitions append to nested counter dicts."""
    metrics: dict = {}
    pm = SimpleNamespace()
    attach_peer_discovery_metrics_ref(pm, metrics)
    record_batch_and_deferral_transition(
        pm, batch_owner_active=True, deferral_active=True
    )
    record_batch_and_deferral_transition(
        pm, batch_owner_active=False, deferral_active=False
    )
    assert metrics["batch_owner_state_transition_total"]["to_active"] == 1
    assert metrics["batch_owner_state_transition_total"]["to_idle"] == 1
    assert metrics["dht_deferral_state_transition_total"]["to_active"] == 1
    assert metrics["dht_deferral_state_transition_total"]["to_idle"] == 1


def test_observe_pending_peer_queue_emits_slo_primitives() -> None:
    """Pending queue observer should populate p95 age and 10s drain-rate gauges."""
    metrics: dict = {}
    pm = SimpleNamespace(
        _pending_peer_queue=[object(), object(), object()],
        _pending_peer_enqueued_at={"a": 1.0, "b": 2.0, "c": 3.0},
    )
    attach_peer_discovery_metrics_ref(pm, metrics)
    observe_pending_peer_queue(pm)
    assert "pending_connect_queue_depth_gauge" in metrics
    assert "pending_age_p95_s" in metrics
    assert "pending_drain_rate_per_10s" in metrics
