"""Reactive per-torrent screen tests (F2.4)."""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
from ccbt.interface.screens.per_torrent_files import TorrentFilesScreen
from ccbt.interface.screens.per_torrent_info import TorrentInfoScreen
from ccbt.interface.screens.per_torrent_peers import TorrentPeersScreen
from ccbt.interface.screens.per_torrent_trackers import TorrentTrackersScreen
from ccbt.interface.terminal_dashboard import TerminalDashboard

pytestmark = [pytest.mark.unit, pytest.mark.interface]


def _make_app() -> TerminalDashboard:
    mock_ipc_client = MagicMock()
    mock_ipc_client.is_daemon_running = AsyncMock(return_value=True)
    mock_ipc_client.connect_websocket = AsyncMock(return_value=True)
    mock_ipc_client.subscribe_events = AsyncMock()
    mock_ipc_client._websocket_task = None
    session = DaemonInterfaceAdapter(mock_ipc_client)
    app = TerminalDashboard(session, refresh_interval=0.5)
    return app


def _wire_data_provider(app: TerminalDashboard, info_hash: str) -> MagicMock:
    dp = MagicMock()
    dp.get_torrent_status = AsyncMock(
        return_value={"info_hash": info_hash, "name": "x", "progress": 0.5}
    )
    dp.get_torrent_peers = AsyncMock(return_value=[{"ip": "1.2.3.4", "port": 6881}])
    dp.get_torrent_files = AsyncMock(
        return_value=[{"index": 0, "path": "a", "size": 10}]
    )
    dp.get_torrent_trackers = AsyncMock(
        return_value=[{"url": "http://t", "status": "ok"}]
    )
    dp.get_piece_health = AsyncMock(return_value={"availability": [1, 2]})
    dp.get_aggressive_discovery_status = AsyncMock(return_value={"enabled": True})
    dp.get_media_candidates = AsyncMock(return_value=[{"index": 0, "name": "video.mkv", "size": 100}])
    dp.get_media_stream_status = AsyncMock(return_value={"active": False})
    app._data_provider = dp
    return dp


def test_app_declares_aggressive_discovery_status_reactive() -> None:
    assert hasattr(TerminalDashboard, "aggressive_discovery_status")


def test_app_has_refresh_selected_torrent_worker() -> None:
    """_refresh_selected_torrent must be @work(exclusive=True, group='selected_torrent') (F2.4.1)."""
    assert inspect.iscoroutinefunction(TerminalDashboard._refresh_selected_torrent_impl)
    assert (
        TerminalDashboard._refresh_selected_torrent
        is not TerminalDashboard._refresh_selected_torrent_impl
    )

    app = TerminalDashboard.__new__(TerminalDashboard)
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

    app.run_worker = fake_run_worker  # type: ignore[assignment]
    app._refresh_selected_torrent()  # type: ignore[func-returns-value]

    assert captured["group"] == "selected_torrent"
    assert captured["exclusive"] is True
    assert captured["exit_on_error"] is False
    assert captured["name"] == "_refresh_selected_torrent"


def test_info_screen_declares_reactives() -> None:
    assert hasattr(TorrentInfoScreen, "selected_torrent_status")
    assert hasattr(TorrentInfoScreen, "aggressive_discovery_status")


def test_files_screen_declares_reactive() -> None:
    assert hasattr(TorrentFilesScreen, "selected_torrent_files")


def test_peers_screen_declares_reactive() -> None:
    assert hasattr(TorrentPeersScreen, "selected_torrent_peers")


def test_trackers_screen_declares_reactive() -> None:
    assert hasattr(TorrentTrackersScreen, "selected_torrent_trackers")


def test_watch_selected_torrent_info_hash_triggers_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """watch_selected_torrent_info_hash must call _refresh_selected_torrent (F2.4.1)."""
    app = TerminalDashboard.__new__(TerminalDashboard)
    called: dict[str, bool] = {}

    def fake_refresh() -> None:
        called["refresh"] = True

    app._refresh_selected_torrent = fake_refresh  # type: ignore[assignment]
    app.watch_selected_torrent_info_hash("abc123")
    assert called.get("refresh") is True

    # Falsy value should NOT trigger the worker.
    called.clear()
    app.watch_selected_torrent_info_hash(None)
    assert "refresh" not in called


def test_info_screen_watch_selected_torrent_status_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TorrentInfoScreen.watch_selected_torrent_status schedules refresh_info(status_override=value) (F2.4.2)."""
    monkeypatch.setattr("asyncio.create_task", MagicMock())
    screen = TorrentInfoScreen.__new__(TorrentInfoScreen)
    screen.refresh_info = MagicMock()  # type: ignore[assignment]
    payload = {"info_hash": "a" * 40, "name": "x"}
    screen.watch_selected_torrent_status(payload)
    screen.refresh_info.assert_called_once()
    assert screen.refresh_info.call_args.kwargs.get("status_override") is payload


def test_info_screen_watch_aggressive_discovery_status_syncs_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TorrentInfoScreen.watch_aggressive_discovery_status updates the switch (F2.4.2)."""
    screen = TorrentInfoScreen.__new__(TorrentInfoScreen)
    switch = MagicMock()
    screen._dht_aggressive_switch = switch
    screen.watch_aggressive_discovery_status({"enabled": True})
    assert switch.value is True


def test_files_screen_watch_delegates_to_refresh_with_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TorrentFilesScreen.watch_selected_torrent_files schedules refresh_files(files_override=value) (F2.4.3)."""
    monkeypatch.setattr("asyncio.create_task", MagicMock())
    screen = TorrentFilesScreen.__new__(TorrentFilesScreen)
    screen.refresh_files = MagicMock()  # type: ignore[assignment]
    payload = [{"index": 0, "path": "a"}]
    screen.watch_selected_torrent_files(payload)
    screen.refresh_files.assert_called_once()
    assert screen.refresh_files.call_args.kwargs.get("files_override") is payload


def test_peers_screen_watch_delegates_to_refresh_with_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TorrentPeersScreen.watch_selected_torrent_peers schedules refresh_peers(peers_override=value) (F2.4.4)."""
    monkeypatch.setattr("asyncio.create_task", MagicMock())
    screen = TorrentPeersScreen.__new__(TorrentPeersScreen)
    screen.refresh_peers = MagicMock()  # type: ignore[assignment]
    payload = [{"ip": "1.2.3.4"}]
    screen.watch_selected_torrent_peers(payload)
    screen.refresh_peers.assert_called_once()
    assert screen.refresh_peers.call_args.kwargs.get("peers_override") is payload


def test_trackers_screen_watch_delegates_to_refresh_with_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TorrentTrackersScreen.watch_selected_torrent_trackers schedules refresh_trackers(trackers_override=value) (F2.4.5)."""
    monkeypatch.setattr("asyncio.create_task", MagicMock())
    screen = TorrentTrackersScreen.__new__(TorrentTrackersScreen)
    screen.refresh_trackers = MagicMock()  # type: ignore[assignment]
    payload = [{"url": "http://t"}]
    screen.watch_selected_torrent_trackers(payload)
    screen.refresh_trackers.assert_called_once()
    assert screen.refresh_trackers.call_args.kwargs.get("trackers_override") is payload


@pytest.mark.asyncio
async def test_refresh_selected_torrent_impl_sets_all_reactives() -> None:
    """_refresh_selected_torrent_impl gathers 8 calls and sets all 8 reactives (F2.4.1 + F2.6)."""
    app = _make_app()
    info_hash = "a" * 40
    dp = _wire_data_provider(app, info_hash)
    # Neutralize the watcher's worker dispatch so setting the reactive does not
    # double-run the impl; we exercise the impl directly below.
    app._refresh_selected_torrent = lambda: None  # type: ignore[assignment, return-value]
    app.selected_torrent_info_hash = info_hash  # type: ignore[attr-defined]

    await app._refresh_selected_torrent_impl()

    dp.get_torrent_status.assert_awaited_once_with(info_hash)
    dp.get_torrent_peers.assert_awaited_once_with(info_hash)
    dp.get_torrent_files.assert_awaited_once_with(info_hash)
    dp.get_torrent_trackers.assert_awaited_once_with(info_hash)
    dp.get_piece_health.assert_awaited_once_with(info_hash)
    dp.get_aggressive_discovery_status.assert_awaited_once_with(info_hash)
    dp.get_media_candidates.assert_awaited_once_with(info_hash)
    dp.get_media_stream_status.assert_awaited_once_with(info_hash)

    assert app.selected_torrent_status == {
        "info_hash": info_hash,
        "name": "x",
        "progress": 0.5,
    }
    assert app.selected_torrent_peers == [{"ip": "1.2.3.4", "port": 6881}]
    assert app.selected_torrent_files == [{"index": 0, "path": "a", "size": 10}]
    assert app.selected_torrent_trackers == [{"url": "http://t", "status": "ok"}]
    assert app.selected_torrent_piece_health == {"availability": [1, 2]}
    assert app.aggressive_discovery_status == {"enabled": True}
    assert app.media_candidates == [{"index": 0, "name": "video.mkv", "size": 100}]
    assert app.media_stream_status == {"active": False}


@pytest.mark.asyncio
async def test_refresh_selected_torrent_impl_noop_without_info_hash() -> None:
    """_refresh_selected_torrent_impl returns early when no torrent is selected (F2.4.1)."""
    app = _make_app()
    dp = _wire_data_provider(app, "deadbeef")
    app.selected_torrent_info_hash = None  # type: ignore[attr-defined]

    await app._refresh_selected_torrent_impl()

    dp.get_torrent_status.assert_not_awaited()
