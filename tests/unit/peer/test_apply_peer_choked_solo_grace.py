"""Unit tests for peer-choked solo grace timeout helper."""

from __future__ import annotations

import pytest

from ccbt.peer.async_peer_connection import _apply_peer_choked_solo_grace

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
            outstanding_count=0,
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
            outstanding_count=0,
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
            outstanding_count=0,
        )
        == _SOLO
    )


def test_zero_bytes_cap_ignored_when_outstanding_requests() -> None:
    """Outstanding requests disable the zero-progress cap."""
    assert (
        _apply_peer_choked_solo_grace(
            _BASE,
            solo_grace=_SOLO,
            zero_bytes_cap=_CAP,
            bytes_downloaded=0,
            outstanding_count=3,
        )
        == _SOLO
    )
