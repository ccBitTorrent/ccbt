"""Widget for visualizing peer quality distribution across all torrents."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.widgets import Static
else:
    try:
        from textual.app import ComposeResult  # type: ignore
        from textual.reactive import reactive  # type: ignore
        from textual.widgets import DataTable, Static  # type: ignore
    except ImportError:  # pragma: no cover
        ComposeResult = Any  # type: ignore[assignment,misc]

        class Static:  # type: ignore[no-redef]
            """Fallback Static widget when Textual is unavailable."""

            def data_bind(self, **kwargs: Any) -> None:
                pass

        class DataTable:  # type: ignore[no-redef]
            """Fallback DataTable widget when Textual is unavailable."""

        class reactive:  # type: ignore[no-redef]
            def __init__(self, default: Any = None, *args: Any, **kwargs: Any) -> None:
                self.default = default

            def __class_getitem__(cls, item: Any) -> type:
                return cls

            def __set_name__(self, owner: Any, name: str) -> None:
                self._name = name

            def __get__(self, instance: Any, owner: Any) -> Any:
                if instance is None:
                    return self
                return instance.__dict__.get(self._name, self.default)

            def __set__(self, instance: Any, value: Any) -> None:
                instance.__dict__[self._name] = value

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

    # F2.6.4: bound to TerminalDashboard.peer_quality_distribution via data_bind.
    peer_quality_distribution: reactive = reactive({}, layout=False)  # type: ignore[assignment]

    def __init__(
        self,
        data_provider: Optional[Any],
        refresh_interval: float = 3.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._data_provider = data_provider

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose widget layout."""
        yield Static(id="peer-quality-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Bind to App peer_quality_distribution reactive (F2.6.4)."""
        try:
            from ccbt.interface.terminal_dashboard import TerminalDashboard

            self.data_bind(peer_quality_distribution=TerminalDashboard.peer_quality_distribution)
        except Exception as exc:  # pragma: no cover
            logger.debug("PeerQualityDistributionWidget data_bind skipped: %s", exc)

    def watch_peer_quality_distribution(self, value: dict[str, Any]) -> None:  # pragma: no cover
        """Reactive watcher: render distribution from the bound dict (F2.6.4)."""
        if isinstance(value, dict):
            self.update(self._render_distribution(value))

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





















































