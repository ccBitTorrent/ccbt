"""Unit tests for peer-choked solo grace timeout helper."""

from __future__ import annotations

import pytest

from ccbt.peer.async_peer_connection import (
    _apply_peer_choked_solo_grace,
    _is_sparse_swarm_for_recycle,
)

pytestmark = pytest.mark.unit

_BASE = 30.0
_SOLO = 180.0
_CAP = 90.0


def test_solo_grace_extends_base_timeout() -> None:
    """Solo grace floor should lift the effective deadline above the base timeout."""
    assert (
        _apply_peer_choked_solo_grace(
            _BASE,
            solo_grace=_SOLO,
            zero_bytes_cap=0.0,
            bytes_downloaded=0,
        )
        == _SOLO
    )


def test_zero_bytes_cap_shortens_grace_when_no_progress() -> None:
    """Zero-bytes cap applies only when no bytes and no outstanding requests."""
    assert (
        _apply_peer_choked_solo_grace(
            _BASE,
            solo_grace=_SOLO,
            zero_bytes_cap=_CAP,
            bytes_downloaded=0,
        )
        == _CAP
    )


def test_zero_bytes_cap_ignored_when_downloading() -> None:
    """Any downloaded bytes disable the zero-progress cap."""
    assert (
        _apply_peer_choked_solo_grace(
            _BASE,
            solo_grace=_SOLO,
            zero_bytes_cap=_CAP,
            bytes_downloaded=1,
        )
        == _SOLO
    )


def test_zero_bytes_cap_applies_even_with_outstanding_requests() -> None:
    """Zero delivered bytes caps grace even with stale outstanding entries.

    A choked peer's outstanding requests will time out on their own; they
    are not evidence the peer is a supplier. (Plan WS2: previously the
    cap was ignored here, holding dead peers for the full 180s grace.)
    """
    assert (
        _apply_peer_choked_solo_grace(
            _BASE,
            solo_grace=_SOLO,
            zero_bytes_cap=_CAP,
            bytes_downloaded=0,
        )
        == _CAP
    )


def test_sparse_swarm_classification_when_no_requestable_peers() -> None:
    """No requestable peers should be treated as sparse for recycle decisions."""
    assert _is_sparse_swarm_for_recycle(
        active_peer_count=6,
        requestable_peer_count=0,
        max_peer_capacity=20,
    )


def test_sparse_swarm_classification_false_for_healthy_swarm() -> None:
    """Healthy active+requestable swarms should not use sparse recycle policy."""
    assert (
        _is_sparse_swarm_for_recycle(
            active_peer_count=6,
            requestable_peer_count=3,
            max_peer_capacity=20,
        )
        is False
    )


def test_sparse_swarm_classification_false_under_high_pressure() -> None:
    """Near-capacity swarms should keep recycle pressure active."""
    assert (
        _is_sparse_swarm_for_recycle(
            active_peer_count=8,
            requestable_peer_count=0,
            max_peer_capacity=10,
            recycle_pressure_threshold=0.8,
        )
        is False
    )
