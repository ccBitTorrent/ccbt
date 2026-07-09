"""PieceAvailabilityHealthBar reactive tests (F2.1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from ccbt.interface.widgets.piece_availability_bar import PieceAvailabilityHealthBar

pytestmark = [pytest.mark.unit, pytest.mark.interface]


def _bare_bar() -> PieceAvailabilityHealthBar:
    """Build a minimally-initialized bar for unit testing (no mount required)."""
    bar = PieceAvailabilityHealthBar.__new__(PieceAvailabilityHealthBar)
    bar._availability = []
    bar._max_peers = 0
    bar._piece_health_data = None
    bar._grid_rows = 8
    bar._grid_cols = 0
    bar.update = MagicMock()  # type: ignore[assignment]
    return bar


def test_piece_health_reactive_is_declared() -> None:
    """The widget must declare a piece_health reactive attribute (F2.1.1)."""
    assert hasattr(PieceAvailabilityHealthBar, "piece_health")


def test_watch_piece_health_calls_update_from_piece_health() -> None:
    """watch_piece_health renders the bar from the bound dict (F2.1.1)."""
    bar = _bare_bar()
    payload = {"availability": [1, 2, 3], "max_peers": 3}
    bar.watch_piece_health(payload)
    assert bar._availability == [1, 2, 3]
    assert bar._max_peers == 3
    assert bar._piece_health_data == payload
    bar.update.assert_called_once()


def test_watch_piece_health_ignores_non_dict() -> None:
    """watch_piece_health must not crash on non-dict payloads."""
    bar = _bare_bar()
    bar.watch_piece_health(None)  # type: ignore[arg-type]
    bar.update.assert_not_called()


def test_update_from_piece_health_backward_compat() -> None:
    """update_from_piece_health remains a working wrapper (F2.1.2 backward compat)."""
    bar = _bare_bar()
    payload = {"availability": [0, 1, 2], "max_peers": 2}
    bar.update_from_piece_health(payload)
    assert bar._piece_health_data == payload
    assert bar._availability == [0, 1, 2]
    bar.update.assert_called_once()


def test_on_mount_binds_to_app_selected_torrent_piece_health() -> None:
    """on_mount must data_bind piece_health to the App reactive (F2.1.2)."""
    bar = PieceAvailabilityHealthBar.__new__(PieceAvailabilityHealthBar)
    bar.data_bind = MagicMock()  # type: ignore[assignment]
    bar.on_mount()
    bar.data_bind.assert_called_once()
    _args, kwargs = bar.data_bind.call_args
    assert "piece_health" in kwargs
    bound = kwargs["piece_health"]
    # The bound value is TerminalDashboard.selected_torrent_piece_health
    from ccbt.interface.terminal_dashboard import TerminalDashboard

    assert bound is TerminalDashboard.selected_torrent_piece_health
