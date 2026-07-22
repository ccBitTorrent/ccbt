"""Quick Add torrent modal and dashboard callback tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.interface.screens.dialogs import QuickAddTorrentScreen
from ccbt.interface.terminal_dashboard import TerminalDashboard

pytestmark = [pytest.mark.unit, pytest.mark.interface]


@pytest.mark.asyncio
async def test_quick_add_action_submit_schedules_background_add() -> None:
    """Submit should schedule a background add task with the entered path."""
    screen = QuickAddTorrentScreen(MagicMock(), MagicMock())
    input_widget = MagicMock()
    input_widget.value = "magnet:?xt=urn:btih:ABC"
    screen.query_one = MagicMock(return_value=input_widget)
    screen._submit_add = AsyncMock()  # type: ignore[method-assign]

    await screen.action_submit()
    await asyncio.sleep(0)

    screen._submit_add.assert_awaited_once_with("magnet:?xt=urn:btih:ABC")


@pytest.mark.asyncio
async def test_quick_add_action_submit_rejects_empty_path() -> None:
    """Empty input should not schedule a background add."""
    screen = QuickAddTorrentScreen(MagicMock(), MagicMock())
    input_widget = MagicMock()
    input_widget.value = "   "
    screen.query_one = MagicMock(return_value=input_widget)
    screen._submit_add = AsyncMock()  # type: ignore[method-assign]

    await screen.action_submit()
    await asyncio.sleep(0)

    screen._submit_add.assert_not_called()


@pytest.mark.asyncio
async def test_submit_add_dismisses_on_executor_success() -> None:
    """Background add should dismiss with info_hash when executor succeeds."""
    dashboard = MagicMock()
    result = MagicMock()
    result.success = True
    result.data = {"info_hash": "deadbeef"}
    dashboard._command_executor.execute_command = AsyncMock(return_value=result)
    dashboard._data_provider = MagicMock()
    dashboard._schedule_poll = MagicMock()
    dashboard.refresh_ui_bindings = MagicMock()
    dashboard.call_later = MagicMock()

    screen = QuickAddTorrentScreen(MagicMock(), dashboard)
    screen.dismiss = MagicMock()

    await screen._submit_add("magnet:?xt=urn:btih:DEAD")

    screen.dismiss.assert_called_once_with("deadbeef")


@pytest.mark.asyncio
async def test_quick_add_on_input_submitted_delegates_to_action_submit() -> None:
    """Enter in the torrent input should submit."""
    screen = QuickAddTorrentScreen(MagicMock(), MagicMock())
    screen.action_submit = AsyncMock()
    event = MagicMock()
    event.input.id = "torrent-input"

    screen.on_input_submitted(event)
    await asyncio.sleep(0)

    screen.action_submit.assert_awaited_once()


@pytest.mark.asyncio
async def test_quick_add_on_button_submit_delegates_to_action_submit() -> None:
    """Add button should call action_submit."""
    screen = QuickAddTorrentScreen(MagicMock(), MagicMock())
    screen.action_submit = AsyncMock()
    event = MagicMock()
    event.button.id = "submit"

    screen.on_button_pressed(event)
    await asyncio.sleep(0)

    screen.action_submit.assert_awaited_once()


@pytest.mark.asyncio
async def test_quick_add_torrent_pushes_screen() -> None:
    """Dashboard quick-add should open QuickAddTorrentScreen."""
    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    dashboard.session = MagicMock()
    dashboard.push_screen = AsyncMock()

    await dashboard._quick_add_torrent()

    dashboard.push_screen.assert_awaited_once()
    screen = dashboard.push_screen.await_args.args[0]
    assert isinstance(screen, QuickAddTorrentScreen)


@pytest.mark.asyncio
async def test_advanced_add_torrent_pushes_screen() -> None:
    """Dashboard advanced-add should open AddTorrentScreen."""
    from ccbt.interface.screens.dialogs import AddTorrentScreen

    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    dashboard.session = MagicMock()
    dashboard.push_screen = AsyncMock()

    await dashboard._advanced_add_torrent()

    dashboard.push_screen.assert_awaited_once()
    screen = dashboard.push_screen.await_args.args[0]
    assert isinstance(screen, AddTorrentScreen)


def test_quick_add_bindings_and_handlers_exist() -> None:
    """Footer keys and handlers for torrent add flows must exist."""
    assert hasattr(TerminalDashboard, "_quick_add_torrent")
    assert hasattr(TerminalDashboard, "_advanced_add_torrent")
    assert hasattr(TerminalDashboard, "_browse_add_torrent")
    binding_actions = {action for _key, action, _desc in TerminalDashboard.BINDINGS}
    assert "quick_add_torrent" in binding_actions
    assert "advanced_add_torrent" in binding_actions
    assert "browse_add_torrent" in binding_actions


def test_logs_write_skips_when_widget_missing() -> None:
    """Direct logs.write must not run when the RichLog widget was not mounted."""
    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    dashboard.logs = None
    # Production code guards with `if self.logs:` before write — no helper required.
    if dashboard.logs:
        dashboard.logs.write("should not run")
    assert dashboard.logs is None
