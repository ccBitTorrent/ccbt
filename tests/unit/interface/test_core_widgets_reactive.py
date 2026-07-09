"""Reactive core-widget tests for Overview and SpeedSparklines (F2.2)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from ccbt.interface.widgets.core_widgets import Overview, SpeedSparklines

pytestmark = [pytest.mark.unit, pytest.mark.interface]


def test_overview_declares_global_stats_reactive() -> None:
    """Overview must declare a global_stats reactive (F2.2.1)."""
    assert hasattr(Overview, "global_stats")


def test_overview_watch_global_stats_renders() -> None:
    """watch_global_stats calls update_from_stats which renders (F2.2.1)."""
    overview = Overview.__new__(Overview)
    overview.update = MagicMock()  # type: ignore[assignment]
    payload = {"num_torrents": 5, "download_rate": 2048.0, "upload_rate": 512.0}
    overview.watch_global_stats(payload)
    overview.update.assert_called_once()


def test_overview_watch_global_stats_ignores_non_dict() -> None:
    """watch_global_stats must not crash on non-dict payloads."""
    overview = Overview.__new__(Overview)
    overview.update = MagicMock()  # type: ignore[assignment]
    overview.watch_global_stats(None)  # type: ignore[arg-type]
    overview.update.assert_not_called()


def test_overview_on_mount_binds_to_app_global_stats() -> None:
    """on_mount must data_bind global_stats to the App reactive (F2.2.1)."""
    overview = Overview.__new__(Overview)
    overview.data_bind = MagicMock()  # type: ignore[assignment]
    overview.on_mount()
    overview.data_bind.assert_called_once()
    _args, kwargs = overview.data_bind.call_args
    assert "global_stats" in kwargs
    from ccbt.interface.terminal_dashboard import TerminalDashboard

    assert kwargs["global_stats"] is TerminalDashboard.global_stats


def test_speed_sparklines_declares_global_stats_reactive() -> None:
    """SpeedSparklines must declare a global_stats reactive (F2.2.2)."""
    assert hasattr(SpeedSparklines, "global_stats")


def _bare_speeds() -> SpeedSparklines:
    """Build a minimally-initialized SpeedSparklines for unit testing."""
    speeds = SpeedSparklines.__new__(SpeedSparklines)
    speeds._down = MagicMock()
    speeds._up = MagicMock()
    speeds._down_history = []
    speeds._up_history = []
    return speeds


def test_speed_sparklines_watch_global_stats_appends_history() -> None:
    """watch_global_stats appends rates to the 120-sample history (F2.2.2)."""
    speeds = _bare_speeds()
    speeds.watch_global_stats({"download_rate": 10.0, "upload_rate": 5.0})
    assert speeds._down_history == [10.0]
    assert speeds._up_history == [5.0]
    # update_from_stats assigns the history to the sparkline ``data`` attr.
    assert speeds._down.data == [10.0]
    assert speeds._up.data == [5.0]


def test_speed_sparklines_watch_truncates_to_120_samples() -> None:
    """History must be capped at 120 samples (F2.2.2)."""
    speeds = _bare_speeds()
    # Pre-fill 120 samples.
    speeds._down_history = [float(i) for i in range(120)]
    speeds._up_history = [float(i) for i in range(120)]
    speeds.watch_global_stats({"download_rate": 999.0, "upload_rate": 888.0})
    assert len(speeds._down_history) == 120
    assert speeds._down_history[-1] == 999.0
    assert len(speeds._up_history) == 120
    assert speeds._up_history[-1] == 888.0


def test_speed_sparklines_watch_ignores_non_dict() -> None:
    """watch_global_stats must not crash on non-dict payloads."""
    speeds = _bare_speeds()
    speeds.watch_global_stats(None)  # type: ignore[arg-type]
    assert speeds._down_history == []
    assert speeds._up_history == []
