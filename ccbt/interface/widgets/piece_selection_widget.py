"""Widget that visualizes torrent piece selection strategy metrics."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.widgets import Static
else:  # pragma: no cover - fallback when textual is unavailable
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

__all__ = ["PieceSelectionStrategyWidget"]


class PieceSelectionStrategyWidget(Static):  # type: ignore[misc]
    """Widget that renders piece selection strategy insights for a torrent."""

    DEFAULT_CSS = """
    PieceSelectionStrategyWidget {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(
        self,
        *,
        info_hash: str,
        data_provider: Any | None,
        refresh_interval: float = 2.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._info_hash = info_hash
        self._data_provider = data_provider
        self._refresh_interval = refresh_interval
        self._update_task: Any | None = None
        self._adapter: Any | None = None

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Render placeholder before metrics arrive."""
        yield Static(_("Loading piece selection metrics..."), id="piece-selection-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Start periodic refresh and register for event-driven updates."""
        self._maybe_register_for_events()
        self._start_updates()

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Stop refresh timer and unregister from adapter events."""
        if self._update_task:
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None
        if self._adapter and hasattr(self._adapter, "unregister_widget"):
            try:
                self._adapter.unregister_widget(self)
            except Exception as exc:
                logger.debug("PieceSelectionStrategyWidget: Error unregistering widget: %s", exc)
        self._adapter = None

    def _maybe_register_for_events(self) -> None:
        """Register the widget with the daemon adapter for event callbacks."""
        if not self._data_provider or not hasattr(self._data_provider, "get_adapter"):
            return
        try:
            adapter = self._data_provider.get_adapter()
            if adapter and hasattr(adapter, "register_widget"):
                adapter.register_widget(self)
                self._adapter = adapter
        except Exception as exc:
            logger.debug("PieceSelectionStrategyWidget: Error registering widget: %s", exc)

    def _start_updates(self) -> None:  # pragma: no cover
        """Schedule periodic refreshes using Textual timers."""

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
            logger.error("PieceSelectionStrategyWidget: Failed to start update loop: %s", exc, exc_info=True)

    async def _update_from_provider(self) -> None:
        """Fetch piece selection metrics and update the widget."""
        if not self._data_provider or not self._info_hash:
            self.update(
                Panel(
                    _("Piece selection metrics are unavailable in the current mode."),
                    border_style="yellow",
                )
            )
            return

        try:
            piece_health = await self._data_provider.get_piece_health(self._info_hash)
        except Exception as exc:
            logger.error("PieceSelectionStrategyWidget: Error loading data: %s", exc, exc_info=True)
            self.update(
                Panel(
                    _("Failed to load piece selection metrics: {error}").format(error=str(exc)),
                    border_style="red",
                )
            )
            return

        selection_metrics = piece_health.get("piece_selection") or {}
        if not selection_metrics:
            self.update(
                Panel(
                    _("Piece selection metrics are not available yet for this torrent."),
                    border_style="yellow",
                )
            )
            return

        prioritized = piece_health.get("prioritized_pieces") or selection_metrics.get("prioritized_pieces") or []
        self.update(self._render_metrics(selection_metrics, prioritized))

    def _render_metrics(self, metrics: dict[str, Any], prioritized: list[int]) -> Panel:
        """Render the metrics using Rich components."""
        strategy = (
            metrics.get("strategy")
            or metrics.get("selection_strategy")
            or _("Adaptive")
        )
        strategy_display = str(strategy).replace("_", " ").title()

        pipeline_util = self._clamp_percentage(metrics.get("average_pipeline_utilization", 0.0))
        request_success = self._clamp_percentage(metrics.get("request_success_rate", 0.0))
        peer_success = self._clamp_percentage(metrics.get("peer_selection_success_rate", 0.0))

        summary = Text()
        summary.append(f"{_('Strategy')}: ", style="bold cyan")
        summary.append(strategy_display, style="white")
        summary.append("   ")
        summary.append(f"{_('Pipeline Utilization')}: ", style="bold cyan")
        summary.append(f"{pipeline_util:.0f}%", style=self._percent_color(pipeline_util))
        summary.append("   ")
        summary.append(f"{_('Request Success')}: ", style="bold cyan")
        summary.append(f"{request_success:.0f}%", style=self._percent_color(request_success))
        if peer_success > 0:
            summary.append("   ")
            summary.append(f"{_('Peer Selection')}: ", style="bold cyan")
            summary.append(f"{peer_success:.0f}%", style=self._percent_color(peer_success))

        if prioritized:
            summary.append("\n")
            preview = ", ".join(str(idx) for idx in prioritized[:8])
            if len(prioritized) > 8:
                preview += _(" +{count} more").format(count=len(prioritized) - 8)
            summary.append(f"{_('Prioritized Pieces')}: {preview}", style="dim")

        efficiency_table = Table(show_header=False, box=None, expand=True, padding=(0, 1))
        efficiency_table.add_row(_("Active Block Requests"), str(metrics.get("active_block_requests", 0)))
        efficiency_table.add_row(_("Duplicate Requests Prevented"), str(metrics.get("duplicate_requests_prevented", 0)))
        efficiency_table.add_row(_("Total Requests"), str(metrics.get("total_piece_requests", 0)))
        efficiency_table.add_row(_("Successful Requests"), str(metrics.get("successful_piece_requests", 0)))
        efficiency_table.add_row(_("Failed Requests"), str(metrics.get("failed_piece_requests", 0)))

        pipeline_table = Table(show_header=False, box=None, expand=True, padding=(0, 1))
        pipeline_table.add_row(_("Pipeline Rejections"), str(metrics.get("pipeline_full_rejections", 0)))
        pipeline_table.add_row(_("Stuck Pieces Recovered"), str(metrics.get("stuck_pieces_recovered", 0)))
        pipeline_table.add_row(_("Utilization Samples"), str(metrics.get("pipeline_utilization_samples_count", 0)))
        pipeline_table.add_row(
            _("Utilization Range"),
            f"{metrics.get('pipeline_utilization_min', 0.0):.0%} - {metrics.get('pipeline_utilization_max', 0.0):.0%}",
        )
        pipeline_table.add_row(
            _("Utilization Median"),
            f"{metrics.get('pipeline_utilization_median', 0.0) * 100:.0f}%",
        )

        content = Group(
            summary,
            Panel(efficiency_table, title=_("Request Efficiency"), border_style="blue"),
            Panel(pipeline_table, title=_("Recovery & Pipeline Health"), border_style="magenta"),
        )

        return Panel(content, title=_("Piece Selection Strategy"), border_style="cyan")

    @staticmethod
    def _clamp_percentage(value: Any) -> float:
        """Clamp percent-like values to 0-100 range."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        if numeric <= 1.0:
            numeric *= 100.0
        return max(0.0, min(100.0, numeric))

    @staticmethod
    def _percent_color(value: float) -> str:
        """Return color name for a percentage value."""
        if value >= 80:
            return "green"
        if value >= 60:
            return "yellow"
        if value >= 40:
            return "orange1"
        return "red"

    def _schedule_event_refresh(self) -> None:
        """Schedule an immediate refresh triggered by an event."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        loop.create_task(self._update_from_provider())

    def on_piece_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Refresh when piece events affect this torrent."""
        if event_data.get("info_hash") == self._info_hash:
            self._schedule_event_refresh()

    def on_progress_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Refresh when progress events affect this torrent."""
        if event_data.get("info_hash") == self._info_hash:
            self._schedule_event_refresh()

    def on_peer_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Refresh when peer events affect this torrent."""
        if event_data.get("info_hash") == self._info_hash:
            self._schedule_event_refresh()

    def on_tracker_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Refresh when tracker announce results influence selection decisions."""
        if event_data.get("info_hash") == self._info_hash:
            self._schedule_event_refresh()




















































