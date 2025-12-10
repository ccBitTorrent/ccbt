"""Widget for visualizing DHT discovery health."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.widgets import Static
else:
    try:
        from textual.app import ComposeResult  # type: ignore
        from textual.widgets import Static  # type: ignore
    except ImportError:  # pragma: no cover
        ComposeResult = Any  # type: ignore[assignment,misc]

        class Static:  # type: ignore[no-redef]
            """Fallback Static widget when Textual is unavailable."""

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ccbt.i18n import _

logger = logging.getLogger(__name__)

HEALTH_LABEL_COLORS = {
    "excellent": "green",
    "healthy": "yellow",
    "degraded": "orange1",
    "critical": "red",
}

__all__ = ["DHTHealthWidget"]


class DHTHealthWidget(Static):  # type: ignore[misc]
    """Widget that renders aggregate DHT health information."""

    DEFAULT_CSS = """
    DHTHealthWidget {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(
        self,
        data_provider: Any | None,
        refresh_interval: float = 2.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._data_provider = data_provider
        self._refresh_interval = refresh_interval
        self._update_task: Any | None = None

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose widget layout."""
        yield Static(id="dht-health-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Start periodic updates when the widget is mounted."""
        self._start_updates()

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Stop periodic updates when the widget is removed."""
        if self._update_task:
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:  # pragma: no cover
        """Initialize refresh timer."""

        def schedule_update() -> None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            loop.create_task(self._update_from_provider())

        try:
            self._update_task = self.set_interval(self._refresh_interval, schedule_update)  # type: ignore[attr-defined]
            self.call_after_refresh(schedule_update)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.error("DHTHealthWidget: Failed to start update loop: %s", exc, exc_info=True)

    async def _update_from_provider(self) -> None:
        """Fetch DHT summary data and update widget output."""
        if not self._data_provider:
            self.update(
                Panel(
                    _("DHT data is unavailable in the current mode."),
                    border_style="yellow",
                )
            )
            return

        try:
            summary = await self._data_provider.get_dht_health_summary()
        except Exception as exc:
            logger.error("DHTHealthWidget: Error loading data: %s", exc, exc_info=True)
            self.update(
                Panel(
                    _("Failed to load DHT health data: {error}").format(error=str(exc)),
                    border_style="red",
                )
            )
            return

        self.update(self._render_summary(summary))

    def _render_summary(self, summary: dict[str, Any]) -> Panel:
        """Render summary view."""
        items = summary.get("items") or []
        overall_health = float(summary.get("overall_health", 0.0))
        torrents_with_dht = int(summary.get("torrents_with_dht", 0))
        aggressive = int(summary.get("aggressive_enabled", 0))
        total_queries = int(summary.get("total_queries", 0))

        stats_text = Text()
        stats_text.append(f"{_('Overall Health')}: ", style="bold cyan")
        stats_text.append(f"{overall_health * 100:.0f}%", style=self._health_color(overall_health))
        stats_text.append("   ")
        stats_text.append(f"{_('Active Torrents')}: ", style="bold cyan")
        stats_text.append(str(torrents_with_dht), style="white")
        stats_text.append("   ")
        stats_text.append(f"{_('Aggressive Mode')}: ", style="bold cyan")
        stats_text.append(str(aggressive), style="white")
        stats_text.append("   ")
        stats_text.append(f"{_('Total Queries')}: ", style="bold cyan")
        stats_text.append(str(total_queries), style="white")

        table = Table(expand=True, box=None, pad_edge=False)
        table.add_column(_("Torrent"), ratio=2, overflow="fold")
        table.add_column(_("Health"), justify="center", ratio=1)
        table.add_column(_("Peers/Q"), justify="right")
        table.add_column(_("Depth"), justify="right")
        table.add_column(_("Nodes/Q"), justify="right")
        table.add_column(_("Queries"), justify="right")
        table.add_column(_("Mode"), justify="center")

        if not items:
            table.add_row(_("No torrents with DHT activity yet."), "", "", "", "", "", "")
        else:
            for item in items:
                health_score = float(item.get("health_score", 0.0))
                health_label = item.get("health_label", "critical")
                table.add_row(
                    item.get("name", item.get("info_hash", "unknown")) or "unknown",
                    self._format_health_badge(health_score, health_label),
                    f"{float(item.get('peers_found_per_query', 0.0)):.2f}",
                    f"{float(item.get('query_depth_achieved', 0.0)):.1f}",
                    f"{float(item.get('nodes_queried_per_query', 0.0)):.1f}",
                    str(int(item.get("total_queries", 0) or 0)),
                    _("Aggressive") if item.get("aggressive_mode_enabled") else _("Normal"),
                )

        content = Group(stats_text, Panel(table, title=_("DHT Health Hotspots"), border_style="blue"))
        return Panel(content, title=_("DHT Health"), border_style="cyan")

    @staticmethod
    def _health_color(score: float) -> str:
        if score >= 0.75:
            return "green"
        if score >= 0.55:
            return "yellow"
        if score >= 0.35:
            return "orange1"
        return "red"

    def _format_health_badge(self, score: float, label: str) -> str:
        color = HEALTH_LABEL_COLORS.get(label, self._health_color(score))
        return f"[{color}]{int(score * 100):d}%[/]"

