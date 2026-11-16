"""Pilot compose coverage: every screen/widget/tab must compose without
exceptions on the supported Textual version, at small and large sizes.

Regression net for the Preferences crash (`display=` constructor kwarg
in ConfigScreenWrapper) which shipped while the suite was green because
nothing ever composed that widget.
"""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from textual.app import App

from ccbt.interface.widgets.config_wrapper import ConfigScreenWrapper
from tests.unit.interface.fakes import FakeDataProvider, FakeExecutor

pytestmark = [pytest.mark.unit, pytest.mark.interface]

SIZES = [(80, 24), (120, 40)]


class _Host(App):
    """Minimal app hosting one widget; exposes fake provider/executor."""

    def __init__(self, widget):
        super().__init__()
        self._widget = widget
        self._data_provider = FakeDataProvider()
        self._command_executor = FakeExecutor()

    def compose(self):
        yield self._widget


def _host(widget):
    return _Host(widget)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("config_type", ["global", "torrent", "network", "security"])
def test_config_wrapper_composes(size, config_type):
    import asyncio

    async def _run():
        info = "a" * 40 if config_type == "torrent" else None
        widget = ConfigScreenWrapper(
            config_type,
            FakeDataProvider(),
            FakeExecutor(),
            info_hash=info,
            id=f"{config_type}-config-wrapper",
        )
        app = _host(widget)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            if config_type in ("global", "torrent"):
                mounted = app.query_one("#config-editors")
                if config_type == "global":
                    assert mounted.display is False
                else:
                    assert mounted.display is True
            else:
                # network/bandwidth/... wrappers compose a placeholder pane
                assert app.query_one("#config-placeholder") is not None
            assert app.query_one("#cancel-button").display is False

    asyncio.run(_run())


@pytest.mark.parametrize("size", SIZES)
def test_preferences_tab_composes(size):
    """The exact path that crashed in production: Preferences -> General."""
    import asyncio

    from ccbt.interface.screens.preferences_tab import PreferencesTabContent

    async def _run():
        app = _host(PreferencesTabContent(FakeExecutor(), id="preferences-content"))
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            # General sub-tab auto-loads and mounts the global config wrapper
            assert app.query_one("#global-config-wrapper") is not None
            assert app.query_one("#config-editors").display is False

    asyncio.run(_run())


@pytest.mark.parametrize("size", SIZES)
def test_upload_download_graph_compact_no_scroll(size):
    import asyncio

    from ccbt.interface.widgets.graph_widget import UploadDownloadGraphWidget

    async def _run():
        widget = UploadDownloadGraphWidget(FakeDataProvider(), id="network-graph")
        app = _host(widget)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            # Compact strip: fits in <=9 rows, no scrollable overflow
            assert widget.region.height <= 9, widget.region
            assert widget.styles.overflow_y[0] != "scroll"
            assert app.query_one("#download-sparkline").region.height <= 3
            assert app.query_one("#upload-sparkline").region.height <= 3
            # No self-poll timer method anymore (reactive data_bind only)
            assert not hasattr(widget, "_start_updates")
            # Reactive path updates labels without polling
            widget.watch_rate_samples(
                [
                    {"timestamp": 1, "download_rate": 4096.0, "upload_rate": 1024.0},
                    {"timestamp": 2, "download_rate": 8192.0, "upload_rate": 2048.0},
                ]
            )
            await pilot.pause()
            assert "peak" in str(app.query_one("#rate-summary").render())

    asyncio.run(_run())


def _mock_session():
    from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter

    mock_ipc_client = MagicMock()
    mock_ipc_client.is_daemon_running = AsyncMock(return_value=True)
    mock_ipc_client.connect_websocket = AsyncMock(return_value=True)
    mock_ipc_client.subscribe_events = AsyncMock()
    mock_ipc_client._websocket_task = None
    return DaemonInterfaceAdapter(mock_ipc_client)


@pytest.mark.parametrize("size", SIZES)
def test_domain_screens_compose(size):
    import asyncio

    from ccbt.interface.screens.monitoring.domains import (
        CasHubManagementScreen,
        CheckpointsManagementScreen,
        PeerDiagnosticsScreen,
        QueueManagementScreen,
        SecurityManagementScreen,
        SessionManagementScreen,
        TorrentAdvancedScreen,
    )
    from ccbt.interface.screens.monitoring.xet_share import XetShareScreen

    screens = [
        QueueManagementScreen,
        SecurityManagementScreen,
        CheckpointsManagementScreen,
        SessionManagementScreen,
        TorrentAdvancedScreen,
        CasHubManagementScreen,
        PeerDiagnosticsScreen,
        XetShareScreen,
    ]

    async def _run():
        for screen_cls in screens:
            app = App()
            async with app.run_test(size=size) as pilot:
                await app.push_screen(screen_cls(_mock_session()))
                await pilot.pause()
                assert app.screen is not None

    asyncio.run(_run())


@pytest.mark.parametrize("size", SIZES)
def test_dashboard_composes_and_preferences_reachable(size):
    """Full dashboard first paint + Preferences tab must not crash."""
    import asyncio

    from ccbt.interface.terminal_dashboard import TerminalDashboard

    async def _run():
        app = TerminalDashboard(_mock_session(), refresh_interval=0.5)
        started = time.monotonic()
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            first_paint = time.monotonic() - started
            # Startup budget: first paint well under the reported ~99s gap
            assert first_paint < 30, first_paint
            assert app.query_one("#graphs-section") is not None
            # Open Preferences (the production crash path)
            tabs = app.query_one("MainTabsContainer")
            tabs._load_insight_tab_content("tab-preferences")
            await pilot.pause()
            assert app.query_one("#global-config-wrapper") is not None

    asyncio.run(_run())
