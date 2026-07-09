"""Focused terminal dashboard regression tests."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.interface import terminal_dashboard as dashboard_module
from ccbt.interface.terminal_dashboard import TerminalDashboard

pytestmark = [pytest.mark.unit, pytest.mark.interface]


@pytest.mark.asyncio
async def test_poll_once_marks_cached_rows_stale_when_list_torrents_fails() -> None:
    """Polling should retain the last rows but mark them stale on list failure."""
    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    dashboard._data_provider = SimpleNamespace(
        get_ui_snapshot=AsyncMock(side_effect=RuntimeError("snapshot unavailable")),
        get_global_stats=AsyncMock(
            return_value={"download_rate": 0.0, "upload_rate": 0.0}
        ),
        list_torrents=AsyncMock(side_effect=RuntimeError("list failed")),
    )
    dashboard._last_status = {
        "a" * 40: {
            "info_hash": "a" * 40,
            "name": "Example",
            "status": "downloading",
        }
    }
    dashboard._splash_manager = None
    dashboard._splash_ended = True
    dashboard._poll_timer = None
    dashboard._last_poll_started_at = None
    dashboard._last_poll_completed_at = None
    dashboard.statusbar = None
    dashboard.overview = None
    dashboard.overview_footer = None
    dashboard.speeds = None
    dashboard.graphs_section = None
    dashboard.peers = None
    dashboard.details = None
    dashboard.torrents = SimpleNamespace(get_selected_info_hash=lambda: None)
    dashboard.session = SimpleNamespace(_websocket_connected=False)
    dashboard.alert_manager = SimpleNamespace(alert_rules={})
    dashboard.metrics_collector = None
    dashboard._command_executor = MagicMock()
    dashboard._apply_filter_and_update = MagicMock()
    dashboard.query_one = MagicMock(side_effect=Exception("no widget"))

    await dashboard._poll_once_impl()

    assert dashboard._last_status["a" * 40]["_stale"] is True
    assert dashboard._apply_filter_and_update.call_count >= 1


def test_poll_once_worker_is_exclusive_in_poll_group() -> None:
    """_poll_once must be a @work(exclusive=True, group='poll') wrapper (F1)."""
    assert inspect.iscoroutinefunction(TerminalDashboard._poll_once_impl)
    assert TerminalDashboard._poll_once is not TerminalDashboard._poll_once_impl

    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    captured: dict[str, Any] = {}

    def fake_run_worker(
        _func: Any,
        *,
        name: str,
        group: str,
        description: str,
        exclusive: bool,
        exit_on_error: bool,
        thread: bool,
    ) -> Any:
        captured["name"] = name
        captured["group"] = group
        captured["exclusive"] = exclusive
        captured["exit_on_error"] = exit_on_error
        captured["thread"] = thread
        return MagicMock()

    dashboard.run_worker = fake_run_worker  # type: ignore[assignment]

    dashboard._poll_once()

    assert captured["group"] == "poll"
    assert captured["exclusive"] is True
    assert captured["exit_on_error"] is False
    assert captured["name"] == "_poll_once"


def test_run_dashboard_retries_once_on_early_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_dashboard should retry once on an immediate startup interrupt."""

    run_calls: list[str] = []
    monotonic_values = iter([10.0, 11.2])
    original_monotonic = dashboard_module.time.monotonic

    class FakeDashboard:
        def __init__(
            self,
            _session: Any,
            refresh_interval: float,
            splash_manager: Any,
        ) -> None:
            self.refresh_interval = refresh_interval
            self.splash_manager = splash_manager
            self._received_input_event = False

        def run(self) -> None:
            run_calls.append("run")
            if len(run_calls) == 1:
                raise KeyboardInterrupt()

    monkeypatch.setattr(dashboard_module, "TerminalDashboard", FakeDashboard)
    def fake_monotonic() -> float:
        return next(monotonic_values, original_monotonic())

    monkeypatch.setattr(dashboard_module.time, "monotonic", fake_monotonic)

    dashboard_module.run_dashboard(
        session=object(),
        refresh=1.0,
        dev_mode=False,
        splash_manager=None,
    )

    assert run_calls == ["run", "run"]
