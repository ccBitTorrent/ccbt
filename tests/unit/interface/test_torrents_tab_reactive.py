"""Reactive torrents-list widget tests (F2.3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.interface.screens.torrents_tab import (
    FilteredTorrentsScreen,
    GlobalTorrentsScreen,
)
from ccbt.interface.widgets.torrent_controls import TorrentControlsWidget
from ccbt.interface.widgets.torrent_selector import TorrentSelector

pytestmark = [pytest.mark.unit, pytest.mark.interface]


def test_global_torrents_screen_declares_torrents_data_reactive() -> None:
    assert hasattr(GlobalTorrentsScreen, "torrents_data")


def test_filtered_torrents_screen_declares_torrents_data_reactive() -> None:
    assert hasattr(FilteredTorrentsScreen, "torrents_data")


def test_torrent_selector_declares_torrents_data_reactive() -> None:
    assert hasattr(TorrentSelector, "torrents_data")


def test_torrent_controls_widget_declares_torrents_data_reactive() -> None:
    assert hasattr(TorrentControlsWidget, "torrents_data")


def _patch_create_task(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch asyncio.create_task with a no-op Mock so sync watchers can be tested."""
    mock = MagicMock()
    monkeypatch.setattr("asyncio.create_task", mock)
    return mock


def test_global_torrents_screen_watch_delegates_to_refresh_with_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """watch_torrents_data schedules refresh_torrents(torrents_override=value) (F2.3.1)."""
    _patch_create_task(monkeypatch)
    screen = GlobalTorrentsScreen.__new__(GlobalTorrentsScreen)
    screen.refresh_torrents = MagicMock()  # type: ignore[assignment]
    payload = [{"info_hash": "a" * 40, "name": "x"}]
    screen.watch_torrents_data(payload)
    screen.refresh_torrents.assert_called_once_with(torrents_override=payload)


def test_filtered_torrents_screen_watch_delegates_to_refresh_with_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """watch_torrents_data schedules refresh_torrents(torrents_override=value) (F2.3.2)."""
    _patch_create_task(monkeypatch)
    screen = FilteredTorrentsScreen.__new__(FilteredTorrentsScreen)
    screen.refresh_torrents = MagicMock()  # type: ignore[assignment]
    payload = [{"info_hash": "a" * 40, "name": "x", "status": "downloading"}]
    screen.watch_torrents_data(payload)
    screen.refresh_torrents.assert_called_once_with(torrents_override=payload)


def test_torrent_selector_watch_delegates_to_refresh_with_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """watch_torrents_data schedules _refresh_torrent_list(torrents_override=value) (F2.3.3)."""
    _patch_create_task(monkeypatch)
    selector = TorrentSelector.__new__(TorrentSelector)
    selector._refresh_torrent_list = MagicMock()  # type: ignore[assignment]
    payload = [{"info_hash": "a" * 40, "name": "x"}]
    selector.watch_torrents_data(payload)
    selector._refresh_torrent_list.assert_called_once_with(torrents_override=payload)


def test_torrent_controls_widget_watch_delegates_to_refresh_with_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """watch_torrents_data schedules _refresh_torrent_list(torrents_override=value) (F2.3.4)."""
    _patch_create_task(monkeypatch)
    widget = TorrentControlsWidget.__new__(TorrentControlsWidget)
    widget._torrent_selector = MagicMock()
    widget._data_provider = MagicMock()
    widget._refresh_torrent_list = MagicMock()  # type: ignore[assignment]
    payload = [{"info_hash": "a" * 40, "name": "x"}]
    widget.watch_torrents_data(payload)
    widget._refresh_torrent_list.assert_called_once_with(torrents_override=payload)


def test_torrent_selector_sets_app_selected_torrent_info_hash_on_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """on_select_changed must set app.selected_torrent_info_hash (F2.3.3)."""
    selector = TorrentSelector.__new__(TorrentSelector)
    selector._torrent_options = [("x (downloading)", "a" * 40)]
    selector._selected_info_hash = None
    selector.post_message = MagicMock()  # type: ignore[assignment]
    app = MagicMock()
    # ``app`` is a read-only property on DOMNode; shadow it on the subclass.
    monkeypatch.setattr(TorrentSelector, "app", app)

    event = MagicMock()
    event.value = 0  # integer index
    selector.on_select_changed(event)

    assert selector._selected_info_hash == "a" * 40
    assert app.selected_torrent_info_hash == "a" * 40
    selector.post_message.assert_called_once()


@pytest.mark.asyncio
async def test_global_torrents_screen_refresh_uses_override_without_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """refresh_torrents(torrents_override=...) renders without calling list_torrents (F2.3.1)."""
    monkeypatch.setattr(GlobalTorrentsScreen, "is_attached", True)
    monkeypatch.setattr(GlobalTorrentsScreen, "display", True)
    screen = GlobalTorrentsScreen.__new__(GlobalTorrentsScreen)
    screen._data_provider = MagicMock()
    screen._data_provider.list_torrents = AsyncMock()  # should NOT be called
    screen._data_provider.get_global_stats = AsyncMock(return_value={})
    screen._data_provider.get_swarm_health_samples = AsyncMock(return_value=[])
    screen._metrics_panel = MagicMock()
    screen._filter_text = ""
    screen._torrents_table = MagicMock()
    screen._torrents_table.columns = True  # type: ignore[attr-defined]
    screen._torrents_table.display = True  # type: ignore[attr-defined]
    screen._empty_message = MagicMock()

    payload = [
        {
            "info_hash": "a" * 40,
            "name": "Example",
            "total_size": 100,
            "progress": 0.5,
            "status": "downloading",
        }
    ]
    await screen.refresh_torrents(torrents_override=payload)

    screen._data_provider.list_torrents.assert_not_called()
    screen._torrents_table.clear.assert_called_once()
    screen._torrents_table.add_row.assert_called()


@pytest.mark.asyncio
async def test_filtered_torrents_screen_refresh_filters_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """refresh_torrents(torrents_override=...) filters by filter_status (F2.3.2)."""
    monkeypatch.setattr(FilteredTorrentsScreen, "is_attached", True)
    monkeypatch.setattr(FilteredTorrentsScreen, "display", True)
    screen = FilteredTorrentsScreen.__new__(FilteredTorrentsScreen)
    screen._filter_status = "downloading"
    screen._data_provider = MagicMock()
    screen._data_provider.list_torrents = AsyncMock()  # should NOT be called
    screen._torrents_table = MagicMock()
    screen._torrents_table.columns = True  # type: ignore[attr-defined]
    screen._torrents_table.is_attached = True  # type: ignore[attr-defined]
    screen._torrents_table.display = True  # type: ignore[attr-defined]

    payload = [
        {
            "info_hash": "a" * 40,
            "name": "dl",
            "status": "downloading",
            "total_size": 1,
            "progress": 0.1,
        },
        {
            "info_hash": "b" * 40,
            "name": "sd",
            "status": "seeding",
            "total_size": 1,
            "progress": 1.0,
        },
    ]
    await screen.refresh_torrents(torrents_override=payload)

    screen._data_provider.list_torrents.assert_not_called()
    # Only the downloading torrent should be added to the table.
    assert screen._torrents_table.add_row.call_count == 1
