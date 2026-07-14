"""Quick Add torrent modal and dashboard callback tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.interface.screens.dialogs import QuickAddTorrentScreen
from ccbt.interface.terminal_dashboard import TerminalDashboard

pytestmark = [pytest.mark.unit, pytest.mark.interface]


@pytest.mark.asyncio
async def test_quick_add_action_submit_dismisses_with_path() -> None:
    """Submit should dismiss the modal with the entered path string."""
    screen = QuickAddTorrentScreen(MagicMock(), MagicMock())
    input_widget = MagicMock()
    input_widget.value = "magnet:?xt=urn:btih:ABC"
    screen.query_one = MagicMock(return_value=input_widget)
    screen.dismiss = MagicMock()
    screen.notify = MagicMock()

    await screen.action_submit()

    screen.dismiss.assert_called_once_with("magnet:?xt=urn:btih:ABC")


@pytest.mark.asyncio
async def test_quick_add_action_submit_rejects_empty_path() -> None:
    """Empty input should not dismiss the modal."""
    screen = QuickAddTorrentScreen(MagicMock(), MagicMock())
    input_widget = MagicMock()
    input_widget.value = "   "
    screen.query_one = MagicMock(return_value=input_widget)
    screen.dismiss = MagicMock()
    screen.notify = MagicMock()

    await screen.action_submit()

    screen.dismiss.assert_not_called()
    screen.notify.assert_called_once()


@pytest.mark.asyncio
async def test_quick_add_on_input_submitted_delegates_to_action_submit() -> None:
    """Enter in the torrent input should submit."""
    screen = QuickAddTorrentScreen(MagicMock(), MagicMock())
    screen.action_submit = AsyncMock()
    event = MagicMock()
    event.input.id = "torrent-input"

    await screen.on_input_submitted(event)

    screen.action_submit.assert_awaited_once()


@pytest.mark.asyncio
async def test_quick_add_on_button_submit_delegates_to_action_submit() -> None:
    """Add button should call action_submit."""
    screen = QuickAddTorrentScreen(MagicMock(), MagicMock())
    screen.action_submit = AsyncMock()
    event = MagicMock()
    event.button.id = "submit"

    await screen.on_button_pressed(event)

    screen.action_submit.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_quick_add_result_routes_to_process_add_torrent() -> None:
    """Dashboard dismiss callback should invoke _process_add_torrent."""
    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    dashboard._process_add_torrent = AsyncMock()

    await dashboard._on_quick_add_result("magnet:?xt=urn:btih:DEAD")

    dashboard._process_add_torrent.assert_awaited_once_with(
        "magnet:?xt=urn:btih:DEAD",
        {},
    )


@pytest.mark.asyncio
async def test_on_quick_add_result_ignores_empty_and_none() -> None:
    """Dashboard callback should ignore cancel/empty dismiss values."""
    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    dashboard._process_add_torrent = AsyncMock()

    await dashboard._on_quick_add_result(None)
    await dashboard._on_quick_add_result("   ")

    dashboard._process_add_torrent.assert_not_called()


@pytest.mark.asyncio
async def test_on_advanced_add_result_routes_payload() -> None:
    """Advanced add dismiss payload should reach _process_add_torrent."""
    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    dashboard._process_add_torrent = AsyncMock()
    payload: dict[str, Any] = {
        "path": "/tmp/example.torrent",
        "options": {"resume": True, "queue_priority": "high"},
    }

    await dashboard._on_advanced_add_result(payload)

    dashboard._process_add_torrent.assert_awaited_once_with(
        "/tmp/example.torrent",
        {"resume": True, "queue_priority": "high"},
    )


def test_action_quick_add_torrent_binding_exists() -> None:
    """Footer binding action_quick_add_torrent must exist for Textual 8."""
    assert hasattr(TerminalDashboard, "action_quick_add_torrent")
    assert hasattr(TerminalDashboard, "action_advanced_add_torrent")
    assert hasattr(TerminalDashboard, "action_browse_add_torrent")


def test_write_log_falls_back_when_logs_widget_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_write_log must not crash when the F2.8 layout has no RichLog widget."""
    from ccbt.interface import terminal_dashboard as td_module

    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    dashboard.logs = None
    messages: list[str] = []
    monkeypatch.setattr(
        td_module.logger,
        "info",
        lambda msg, *args, **kwargs: messages.append(msg),
    )

    dashboard._write_log("Adding torrent: magnet:…")

    assert messages == ["Adding torrent: magnet:…"]
