"""Reactive attribute bridge tests for TerminalDashboard (F2.0).

Verifies that assigning the App-level ``reactive()`` attributes fires the
matching ``watch_*`` handlers, which fan out to the imperative widget pushes
(bridge step preserving F1 behavior). These tests construct the app normally
(``__init__`` initialises the reactive system) and mock the widget refs, so
they do not require a full ``run_test()`` mount.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
from ccbt.interface.terminal_dashboard import TerminalDashboard

pytestmark = [pytest.mark.unit, pytest.mark.interface]


def _make_mock_session() -> DaemonInterfaceAdapter:
    """Build a DaemonInterfaceAdapter backed by a mock IPC client."""
    mock_ipc_client = MagicMock()
    mock_ipc_client.is_daemon_running = AsyncMock(return_value=True)
    mock_ipc_client.connect_websocket = AsyncMock(return_value=True)
    mock_ipc_client.subscribe_events = AsyncMock()
    mock_ipc_client._websocket_task = None
    return DaemonInterfaceAdapter(mock_ipc_client)


def _make_dashboard() -> TerminalDashboard:
    """Construct a dashboard with mocked widget refs for reactive testing."""
    app = TerminalDashboard(_make_mock_session(), refresh_interval=0.5)
    app.overview = MagicMock()
    app.overview_footer = MagicMock()
    app.speeds = MagicMock()
    app.graphs_section = MagicMock()
    app.peers = MagicMock()
    app.torrents = SimpleNamespace(get_selected_info_hash=lambda: None)
    app._apply_filter_and_update = MagicMock()
    return app


def test_global_stats_reactive_triggers_watch_no_app_fanout() -> None:
    """F2.5: setting global_stats fires watch_global_stats (no App-level fan-out)."""
    app = _make_dashboard()
    app.global_stats = {}
    app.graphs_section.update_from_stats.reset_mock()

    payload = {"download_rate": 1.0, "upload_rate": 2.0, "num_torrents": 3}
    app.global_stats = payload

    app.graphs_section.update_from_stats.assert_not_called()


def test_rate_samples_reactive_triggers_watch_no_app_fanout() -> None:
    """F2.5: setting rate_samples fires watch_rate_samples (no App-level fan-out)."""
    app = _make_dashboard()
    app.rate_samples = []
    app.graphs_section.update_from_rate_samples.reset_mock()

    samples = [{"timestamp": 1, "download_rate": 5.0, "upload_rate": 1.0}]
    app.rate_samples = samples

    app.graphs_section.update_from_rate_samples.assert_not_called()


def test_selected_torrent_peers_reactive_triggers_watch() -> None:
    """Setting selected_torrent_peers fires watch_selected_torrent_peers."""
    app = _make_dashboard()
    app.selected_torrent_peers = []
    app.peers.update_from_peers.reset_mock()

    peers = [{"ip": "1.2.3.4", "port": 6881}]
    app.selected_torrent_peers = peers

    app.peers.update_from_peers.assert_called_once_with(peers)


def test_torrents_data_reactive_triggers_watch_and_last_status_invariant() -> None:
    """Setting torrents_data fires watch_torrents_data → _apply_filter_and_update + _last_status."""
    app = _make_dashboard()
    # Prime the reactive so the init-fire happens before we reset counts.
    app.torrents_data = []
    app._apply_filter_and_update.reset_mock()

    payload: list[dict[str, Any]] = [
        {"info_hash": "a" * 40, "name": "Example", "status": "downloading"},
        {"info_hash": "b" * 40, "name": "Other", "status": "seeding"},
    ]
    app.torrents_data = payload

    app._apply_filter_and_update.assert_called_once()
    # The watch handler rebuilds _last_status as {info_hash: status}.
    assert set(app._last_status.keys()) == {"a" * 40, "b" * 40}
    assert app._last_status["a" * 40]["name"] == "Example"
    assert app._last_status["b" * 40]["status"] == "seeding"


def test_set_reactive_falls_back_to_watch_when_reactive_system_unavailable() -> None:
    """_set_reactive returns False on a bare instance; caller invokes the watcher."""
    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    dashboard.graphs_section = MagicMock()
    dashboard.torrents = SimpleNamespace(get_selected_info_hash=lambda: None)
    dashboard._apply_filter_and_update = MagicMock()

    payload = {"download_rate": 9.0}
    accepted = dashboard._set_reactive("global_stats", payload)
    assert accepted is False
    # Mirrors the _poll_once_impl usage: on False, invoke the watcher directly.
    # F2.5: graph widgets self-render via data_bind; no graphs_section push.
    dashboard.watch_global_stats(payload)
    dashboard.graphs_section.update_from_stats.assert_not_called()
