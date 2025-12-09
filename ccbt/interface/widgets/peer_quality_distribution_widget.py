"""Widget for visualizing peer quality distribution across all torrents."""

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
        from textual.widgets import Static, DataTable  # type: ignore
    except ImportError:  # pragma: no cover
        ComposeResult = Any  # type: ignore[assignment,misc]

        class Static:  # type: ignore[no-redef]
            """Fallback Static widget when Textual is unavailable."""

        class DataTable:  # type: ignore[no-redef]
            """Fallback DataTable widget when Textual is unavailable."""

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ccbt.i18n import _

logger = logging.getLogger(__name__)

QUALITY_TIER_COLORS = {
    "excellent": "green",
    "good": "yellow",
    "fair": "orange1",
    "poor": "red",
}

__all__ = ["PeerQualityDistributionWidget"]


class PeerQualityDistributionWidget(Static):  # type: ignore[misc]
    """Widget that renders peer quality distribution across all torrents."""

    DEFAULT_CSS = """
    PeerQualityDistributionWidget {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(
        self,
        data_provider: Any | None,
        refresh_interval: float = 3.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._data_provider = data_provider
        self._refresh_interval = refresh_interval
        self._update_task: Any | None = None

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose widget layout."""
        yield Static(id="peer-quality-placeholder")

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
            logger.error("PeerQualityDistributionWidget: Failed to start update loop: %s", exc, exc_info=True)

    async def _update_from_provider(self) -> None:
        """Fetch peer quality distribution data and update widget output."""
        if not self._data_provider:
            self.update(
                Panel(
                    _("Peer quality data is unavailable in the current mode."),
                    border_style="yellow",
                )
            )
            return

        try:
            distribution = await self._data_provider.get_peer_quality_distribution()
        except Exception as exc:
            logger.error("PeerQualityDistributionWidget: Error loading data: %s", exc, exc_info=True)
            self.update(
                Panel(
                    _("Failed to load peer quality distribution: {error}").format(error=str(exc)),
                    border_style="red",
                )
            )
            return

        self.update(self._render_distribution(distribution))

    def _render_distribution(self, distribution: dict[str, Any]) -> Panel:
        """Render peer quality distribution view."""
        total_peers = int(distribution.get("total_peers", 0))
        quality_tiers = distribution.get("quality_tiers", {})
        average_quality = float(distribution.get("average_quality", 0.0))
        top_peers = distribution.get("top_peers", [])
        per_torrent = distribution.get("per_torrent", [])

        # Summary stats
        stats_text = Text()
        stats_text.append(f"{_('Total Peers')}: ", style="bold cyan")
        stats_text.append(str(total_peers), style="white")
        stats_text.append("   ")
        stats_text.append(f"{_('Average Quality')}: ", style="bold cyan")
        stats_text.append(f"{average_quality * 100:.0f}%", style=self._quality_color(average_quality))
        stats_text.append("   ")
        stats_text.append(f"{_('Excellent')}: ", style="bold cyan")
        stats_text.append(str(quality_tiers.get("excellent", 0)), style="green")
        stats_text.append("   ")
        stats_text.append(f"{_('Good')}: ", style="bold cyan")
        stats_text.append(str(quality_tiers.get("good", 0)), style="yellow")
        stats_text.append("   ")
        stats_text.append(f"{_('Fair')}: ", style="bold cyan")
        stats_text.append(str(quality_tiers.get("fair", 0)), style="orange1")
        stats_text.append("   ")
        stats_text.append(f"{_('Poor')}: ", style="bold cyan")
        stats_text.append(str(quality_tiers.get("poor", 0)), style="red")

        # Quality distribution table
        dist_table = Table(expand=True, box=None, pad_edge=False, title=_("Quality Distribution"))
        dist_table.add_column(_("Tier"), ratio=1)
        dist_table.add_column(_("Count"), justify="right", ratio=1)
        dist_table.add_column(_("Percentage"), justify="right", ratio=1)
        dist_table.add_column(_("Visual"), ratio=2)

        if total_peers > 0:
            for tier in ["excellent", "good", "fair", "poor"]:
                count = quality_tiers.get(tier, 0)
                percentage = (count / total_peers * 100) if total_peers > 0 else 0.0
                color = QUALITY_TIER_COLORS.get(tier, "white")
                # Visual bar (simple text representation)
                bar_length = int(percentage / 2)  # Scale to fit
                visual_bar = "█" * bar_length
                dist_table.add_row(
                    f"[{color}]{tier.capitalize()}[/{color}]",
                    str(count),
                    f"{percentage:.1f}%",
                    f"[{color}]{visual_bar}[/{color}]",
                )
        else:
            dist_table.add_row(_("No peers available"), "", "", "")

        # Top peers table
        top_peers_table = Table(expand=True, box=None, pad_edge=False, title=_("Top 10 Peers by Quality"))
        top_peers_table.add_column(_("Peer"), ratio=2, overflow="fold")
        top_peers_table.add_column(_("Quality"), justify="center", ratio=1)
        top_peers_table.add_column(_("↓ Rate"), justify="right", ratio=1)
        top_peers_table.add_column(_("↑ Rate"), justify="right", ratio=1)
        top_peers_table.add_column(_("Torrents"), justify="right", ratio=1)

        if top_peers:
            for peer in top_peers[:10]:
                peer_key = peer.get("peer_key", "unknown")
                quality_score = float(peer.get("quality_score", 0.0))
                download_rate = float(peer.get("download_rate", 0.0))
                upload_rate = float(peer.get("upload_rate", 0.0))
                torrents = peer.get("torrents", [])
                
                # Format rates
                def _format_rate(rate: float) -> str:
                    if rate >= 1024 * 1024:
                        return f"{rate / (1024 * 1024):.1f} MiB/s"
                    if rate >= 1024:
                        return f"{rate / 1024:.1f} KiB/s"
                    return f"{rate:.0f} B/s"
                
                top_peers_table.add_row(
                    peer_key[:40],  # Truncate long keys
                    self._format_quality_badge(quality_score),
                    _format_rate(download_rate),
                    _format_rate(upload_rate),
                    str(len(torrents)),
                )
        else:
            top_peers_table.add_row(_("No peer quality data available"), "", "", "", "")

        # Per-torrent summary table (top 5)
        per_torrent_table = Table(expand=True, box=None, pad_edge=False, title=_("Per-Torrent Quality Summary"))
        per_torrent_table.add_column(_("Torrent"), ratio=2, overflow="fold")
        per_torrent_table.add_column(_("Peers"), justify="right", ratio=1)
        per_torrent_table.add_column(_("Avg Quality"), justify="center", ratio=1)
        per_torrent_table.add_column(_("High"), justify="right", ratio=1)
        per_torrent_table.add_column(_("Medium"), justify="right", ratio=1)
        per_torrent_table.add_column(_("Low"), justify="right", ratio=1)

        sorted_torrents = sorted(
            per_torrent,
            key=lambda t: float(t.get("average_quality_score", 0.0)),
            reverse=True,
        )[:5]

        if sorted_torrents:
            for torrent in sorted_torrents:
                per_torrent_table.add_row(
                    torrent.get("name", torrent.get("info_hash", "unknown"))[:40],
                    str(torrent.get("total_peers_ranked", 0)),
                    self._format_quality_badge(float(torrent.get("average_quality_score", 0.0))),
                    f"[green]{torrent.get('high_quality_peers', 0)}[/green]",
                    f"[yellow]{torrent.get('medium_quality_peers', 0)}[/yellow]",
                    f"[red]{torrent.get('low_quality_peers', 0)}[/red]",
                )
        else:
            per_torrent_table.add_row(_("No per-torrent data available"), "", "", "", "", "")

        content = Group(
            stats_text,
            Panel(dist_table, border_style="blue"),
            Panel(top_peers_table, border_style="cyan"),
            Panel(per_torrent_table, border_style="magenta"),
        )
        return Panel(content, title=_("Peer Quality Distribution"), border_style="bright_cyan")

    @staticmethod
    def _quality_color(score: float) -> str:
        """Get color for quality score."""
        if score >= 0.7:
            return "green"
        if score >= 0.5:
            return "yellow"
        if score >= 0.3:
            return "orange1"
        return "red"

    def _format_quality_badge(self, score: float) -> str:
        """Format quality score as a colored badge."""
        color = self._quality_color(score)
        return f"[{color}]{int(score * 100):d}%[/{color}]"





















































