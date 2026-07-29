"""Tests for App-level reactive binding wiring (Textual 8)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ccbt.interface.reactive_bridge import ReactiveBindRequest
from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
from ccbt.interface.terminal_dashboard import TerminalDashboard

pytestmark = [pytest.mark.unit, pytest.mark.interface]


def _make_dashboard() -> TerminalDashboard:
    mock_ipc_client = MagicMock()
    session = DaemonInterfaceAdapter(mock_ipc_client)
    app = TerminalDashboard(session, refresh_interval=0.5)
    app.query = MagicMock(return_value=[])  # type: ignore[method-assign]
    app.call_later = MagicMock()  # type: ignore[method-assign]
    return app


def test_wire_reactive_bindings_queries_widget_types() -> None:
    """_wire_reactive_bindings should query each bindable widget class."""
    app = _make_dashboard()
    app._wire_reactive_bindings()
    assert app.query.call_count >= 20


def test_schedule_reactive_bind_defers_to_call_later() -> None:
    """Lazy widgets must bind via App call_later (Textual 8 message pump)."""
    app = _make_dashboard()
    widget = MagicMock()
    app.schedule_reactive_bind(widget)
    app.call_later.assert_called_once()


def test_request_reactive_bind_delegates_to_lazy_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    """Static helper delegates to reactive_bridge.request_lazy_bind."""
    widget = MagicMock()
    called: list[Any] = []

    def _capture(w: Any) -> None:
        called.append(w)

    monkeypatch.setattr(
        "ccbt.interface.terminal_dashboard.request_lazy_bind",
        _capture,
    )
    TerminalDashboard.request_reactive_bind(widget)
    assert called == [widget]


def test_reactive_bind_request_message_carries_widget() -> None:
    """ReactiveBindRequest must retain the widget reference."""
    widget = MagicMock()
    event = ReactiveBindRequest(widget)
    assert event.widget is widget


def test_watch_global_stats_updates_overview_footer() -> None:
    """Footer overview must update when global_stats reactive changes."""
    app = _make_dashboard()
    app.overview_footer = MagicMock()
    payload = {"num_torrents": 2, "download_rate": 100.0, "upload_rate": 50.0}
    app.watch_global_stats(payload)
    app.overview_footer.update_from_stats.assert_called_once_with(payload)


def test_hydrate_reactive_widgets_pushes_empty_stats() -> None:
    """Empty stats dict must still hydrate the footer (zero state)."""
    app = _make_dashboard()
    app.global_stats = {}
    app.overview_footer = MagicMock()
    app._hydrate_reactive_widgets()
    app.overview_footer.update_from_stats.assert_called_once_with({})
