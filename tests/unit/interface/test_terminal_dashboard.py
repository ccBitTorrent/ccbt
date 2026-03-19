"""Focused terminal dashboard regression tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.interface.terminal_dashboard import TerminalDashboard


pytestmark = [pytest.mark.unit, pytest.mark.interface]


@pytest.mark.asyncio
async def test_poll_once_marks_cached_rows_stale_when_list_torrents_fails() -> None:
    """Polling should retain the last rows but mark them stale on list failure."""
    dashboard = TerminalDashboard.__new__(TerminalDashboard)
    dashboard._data_provider = SimpleNamespace(
        get_ui_snapshot=AsyncMock(side_effect=RuntimeError("snapshot unavailable")),
        get_global_stats=AsyncMock(return_value={"download_rate": 0.0, "upload_rate": 0.0}),
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

    await dashboard._poll_once()

    assert dashboard._last_status["a" * 40]["_stale"] is True
    assert dashboard._apply_filter_and_update.call_count >= 1
