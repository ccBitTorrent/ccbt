"""Textual 8 reactive data-binding helpers for the dashboard.

Textual requires ``data_bind`` to run with the App as the active message pump
(see ``textual.dom.DOMNode.data_bind``). Bindings from a child ``on_mount``
raise ``ReactiveError`` because the pump is the child widget, not the App.

Patterns supported here:
- **Compose-time binding** — ``yield Widget().data_bind(App.reactive)`` in
  ``TerminalDashboard.compose()`` (canonical Textual 8 pattern).
- **Lazy binding** — post ``ReactiveBindRequest`` after dynamic ``mount()``;
  the App handles it on its own message pump.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ccbt.interface.terminal_dashboard import TerminalDashboard

logger = logging.getLogger(__name__)

try:
    from textual.message import Message
except ImportError:  # pragma: no cover - textual unavailable in minimal envs

    class Message:  # type: ignore[no-redef]
        """Fallback Message when textual is unavailable."""


class ReactiveBindRequest(Message):
    """Ask the App to ``data_bind`` a lazily mounted widget."""

    def __init__(self, widget: Any) -> None:
        self.widget = widget
        super().__init__()


def request_lazy_bind(widget: Any) -> None:
    """Post a bind request so the App wires reactives on its message pump."""
    if widget is None:
        return
    try:
        widget.post_message(ReactiveBindRequest(widget))
    except Exception:
        app = getattr(widget, "app", None)
        if app is not None and hasattr(app, "schedule_reactive_bind"):
            app.schedule_reactive_bind(widget)


def binding_specs(app_cls: type[Any]) -> list[tuple[type[Any], dict[str, Any]]]:
    """Return widget-class → App-reactive binding specs for the dashboard."""
    from ccbt.interface.screens.per_torrent_files import TorrentFilesScreen
    from ccbt.interface.screens.per_torrent_info import TorrentInfoScreen
    from ccbt.interface.screens.per_torrent_peers import TorrentPeersScreen
    from ccbt.interface.screens.per_torrent_trackers import TorrentTrackersScreen
    from ccbt.interface.screens.torrents_tab import (
        FilteredTorrentsScreen,
        GlobalTorrentsScreen,
    )
    from ccbt.interface.widgets.core_widgets import Overview, SpeedSparklines
    from ccbt.interface.widgets.dht_health_widget import DHTHealthWidget
    from ccbt.interface.widgets.global_kpis_panel import GlobalKPIsPanel
    from ccbt.interface.widgets.graph_widget import (
        DiskGraphWidget,
        DownloadGraphWidget,
        NetworkGraphWidget,
        PeerQualitySummaryWidget,
        PerTorrentGraphWidget,
        SwarmHealthDotPlot,
        SystemResourcesGraphWidget,
        UploadDownloadGraphWidget,
        UploadGraphWidget,
    )
    from ccbt.interface.widgets.media_playback_widget import MediaPlaybackWidget
    from ccbt.interface.widgets.peer_quality_distribution_widget import (
        PeerQualityDistributionWidget,
    )
    from ccbt.interface.widgets.swarm_timeline_widget import SwarmTimelineWidget
    from ccbt.interface.widgets.torrent_controls import TorrentControlsWidget
    from ccbt.interface.widgets.torrent_file_explorer import TorrentFileExplorerWidget
    from ccbt.interface.widgets.torrent_selector import TorrentSelector

    return [
        (Overview, {"global_stats": app_cls.global_stats}),
        (SpeedSparklines, {"global_stats": app_cls.global_stats}),
        (
            UploadDownloadGraphWidget,
            {
                "global_stats": app_cls.global_stats,
                "rate_samples": app_cls.rate_samples,
            },
        ),
        (DownloadGraphWidget, {"global_stats": app_cls.global_stats}),
        (UploadGraphWidget, {"global_stats": app_cls.global_stats}),
        (DiskGraphWidget, {"disk_io_metrics": app_cls.disk_io_metrics}),
        (NetworkGraphWidget, {"network_quality": app_cls.network_quality}),
        (SystemResourcesGraphWidget, {"system_metrics": app_cls.system_metrics}),
        (SwarmHealthDotPlot, {"swarm_health_samples": app_cls.swarm_health_samples}),
        (
            PeerQualitySummaryWidget,
            {"peer_quality_distribution": app_cls.peer_quality_distribution},
        ),
        (GlobalKPIsPanel, {"global_kpis": app_cls.global_kpis}),
        (DHTHealthWidget, {"dht_health_summary": app_cls.dht_health_summary}),
        (
            PeerQualityDistributionWidget,
            {"peer_quality_distribution": app_cls.peer_quality_distribution},
        ),
        (SwarmTimelineWidget, {"swarm_health_samples": app_cls.swarm_health_samples}),
        (GlobalTorrentsScreen, {"torrents_data": app_cls.torrents_data}),
        (FilteredTorrentsScreen, {"torrents_data": app_cls.torrents_data}),
        (TorrentSelector, {"torrents_data": app_cls.torrents_data}),
        (TorrentControlsWidget, {"torrents_data": app_cls.torrents_data}),
        (TorrentFilesScreen, {"selected_torrent_files": app_cls.selected_torrent_files}),
        (TorrentPeersScreen, {"selected_torrent_peers": app_cls.selected_torrent_peers}),
        (TorrentInfoScreen, {"selected_torrent_status": app_cls.selected_torrent_status}),
        (
            TorrentTrackersScreen,
            {"selected_torrent_trackers": app_cls.selected_torrent_trackers},
        ),
        (
            TorrentFileExplorerWidget,
            {
                "selected_torrent_files": app_cls.selected_torrent_files,
                "selected_torrent_status": app_cls.selected_torrent_status,
            },
        ),
        (
            MediaPlaybackWidget,
            {
                "media_candidates": app_cls.media_candidates,
                "media_stream_status": app_cls.media_stream_status,
            },
        ),
        (
            PerTorrentGraphWidget,
            {
                "selected_torrent_status": app_cls.selected_torrent_status,
                "selected_torrent_piece_health": app_cls.selected_torrent_piece_health,
            },
        ),
    ]


def bind_widget_from_app(app: TerminalDashboard, widget: Any) -> bool:
    """Bind one widget instance to App reactives; return True on success."""
    for widget_cls, bindings in binding_specs(type(app)):
        if not isinstance(widget, widget_cls):
            continue
        try:
            widget.data_bind(**bindings)  # type: ignore[attr-defined]
            hydrate_bound_widget(app, widget, bindings)
            logger.debug(
                "Reactive bridge: bound %s",
                widget_cls.__name__,
            )
            return True
        except Exception as exc:
            logger.debug(
                "Reactive bridge: bind skipped for %s: %s",
                widget_cls.__name__,
                exc,
            )
            return False
    return False


def hydrate_bound_widget(
    app: Any, widget: Any, bindings: dict[str, Any]
) -> None:
    """Push current App reactive values into a newly bound widget."""
    for reactive_name in bindings:
        if not hasattr(app, reactive_name):
            continue
        value = getattr(app, reactive_name)
        watcher = getattr(widget, f"watch_{reactive_name}", None)
        if callable(watcher):
            with contextlib.suppress(Exception):
                watcher(value)


def wire_all_bindings(app: TerminalDashboard) -> int:
    """Query and bind every bindable widget currently in the tree."""
    wired = 0
    for widget_cls, bindings in binding_specs(type(app)):
        for widget in app.query(widget_cls):  # type: ignore[attr-defined]
            try:
                widget.data_bind(**bindings)  # type: ignore[attr-defined]
                hydrate_bound_widget(app, widget, bindings)
                wired += 1
            except Exception as exc:
                logger.debug(
                    "Reactive bridge: bind skipped for %s: %s",
                    widget_cls.__name__,
                    exc,
                )
    logger.debug("Reactive bridge: wired %d binding(s)", wired)
    return wired


def fan_out_app_reactives(app: Any) -> int:
    """Push current App reactive snapshots into every bound widget.

    Textual may skip ``watch_*`` when a reactive value is unchanged (equality).
    Poll/hydrate paths call this after assigning App reactives so lazily mounted
    widgets always receive a direct ``watch_*`` push.
    """
    pushed = 0
    for widget_cls, bindings in binding_specs(type(app)):
        try:
            widgets = list(app.query(widget_cls))  # type: ignore[attr-defined]
        except Exception:
            widgets = []
        for widget in widgets:
            for reactive_name in bindings:
                if not hasattr(app, reactive_name):
                    continue
                value = getattr(app, reactive_name)
                watcher = getattr(widget, f"watch_{reactive_name}", None)
                if callable(watcher):
                    with contextlib.suppress(Exception):
                        watcher(value)
                        pushed += 1
    logger.debug("Reactive bridge: fan-out pushed %d watcher(s)", pushed)
    return pushed
