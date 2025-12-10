"""Swarm timeline widget for historical swarm trends and annotations."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ccbt.i18n import _

logger = logging.getLogger(__name__)

try:
    from textual.widgets import Static
except ImportError:

    class Static:  # type: ignore[no-redef]
        pass


SPARK_CHARS = "▁▂▃▄▅▆▇█"


class SwarmTimelineWidget(Static):  # type: ignore[misc]
    """Widget that renders swarm availability/download timelines with annotations."""

    DEFAULT_CSS = """
    SwarmTimelineWidget {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(
        self,
        data_provider: Any | None,
        info_hash: str | None = None,
        limit: int = 3,
        history_seconds: int = 3600,
        refresh_interval: float = 4.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._data_provider = data_provider
        self._info_hash = info_hash
        self._limit = max(1, limit)
        self._history_seconds = max(60, history_seconds)
        self._refresh_interval = refresh_interval
        self._update_task: Any | None = None

    def compose(self) -> Any:  # pragma: no cover
        yield Static(_("Loading swarm timeline..."), id="swarm-timeline-placeholder")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        self._start_updates()

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        if self._update_task:
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:  # pragma: no cover
        if not self._data_provider:
            self.update(Panel(_("Timeline data is unavailable in the current mode."), border_style="yellow"))
            return

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
            logger.error("SwarmTimelineWidget: Failed to start update interval: %s", exc, exc_info=True)

    async def _update_from_provider(self) -> None:
        if not self._data_provider:
            return
        try:
            samples = await self._data_provider.get_swarm_health_samples(
                self._info_hash,
                limit=self._limit,
                include_history=True,
                history_seconds=self._history_seconds,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("SwarmTimelineWidget: Error loading timeline data: %s", exc, exc_info=True)
            self.update(Panel(_("Failed to load swarm timeline: {error}").format(error=str(exc)), border_style="red"))
            return

        if not samples:
            self.update(Panel(_("No swarm activity captured for the selected window."), border_style="yellow"))
            return

        self.update(self._render_timeline(samples))

    def _render_timeline(self, samples: list[dict[str, Any]]) -> Panel:
        window_minutes = int(self._history_seconds / 60)
        summary = Text()
        summary.append(
            _("Tracking {count} torrent(s) across {minutes} minute window").format(
                count=len(samples),
                minutes=window_minutes,
            ),
            style="cyan",
        )
        summary.append("   ")
        summary.append(_("Updated at {time}").format(time=time.strftime("%H:%M:%S")), style="green")

        table = Table(show_header=True, box=None, expand=True, pad_edge=False)
        table.add_column(_("Torrent"), ratio=2, overflow="fold")
        table.add_column(_("Availability Trend"), ratio=3)
        table.add_column(_("Download Trend"), ratio=3)
        table.add_column(_("Events"), ratio=2, overflow="fold")

        for sample in samples:
            history = sample.get("history") or []
            if not history:
                history = [
                    {
                        "timestamp": sample.get("timestamp", time.time()),
                        "swarm_availability": float(sample.get("swarm_availability", 0.0)),
                        "download_rate": float(sample.get("download_rate", 0.0)),
                    }
                ]
            availability_series = [
                float(point.get("swarm_availability", sample.get("swarm_availability", 0.0))) * 100.0
                for point in history
            ]
            download_series = [
                float(point.get("download_rate", sample.get("download_rate", 0.0))) / 1024.0
                for point in history
            ]

            name = sample.get("name") or (sample.get("info_hash") or "unknown")[:16]
            availability_line = f"{self._sparkline(availability_series)} {availability_series[-1]:.1f}%"
            download_line = f"{self._sparkline(download_series)} {download_series[-1]:.1f} KiB/s"
            events = self._derive_events(sample, history)
            events_text = "\n".join(events) if events else _("No significant events detected.")

            table.add_row(name, availability_line, download_line, events_text)

        content = Group(summary, Panel(table, title=_("Timeline"), border_style="blue"))
        return Panel(content, title=_("Swarm Timeline"), border_style="cyan")

    def _sparkline(self, values: list[float]) -> str:
        if not values:
            return "·"
        min_val = min(values)
        max_val = max(values)
        if max_val == min_val:
            idx = min(len(SPARK_CHARS) - 1, int(len(SPARK_CHARS) / 2))
            return SPARK_CHARS[idx] * len(values)

        spark = []
        span = max_val - min_val
        for val in values:
            normalized = (val - min_val) / span if span else 0.0
            idx = int(normalized * (len(SPARK_CHARS) - 1))
            idx = max(0, min(idx, len(SPARK_CHARS) - 1))
            spark.append(SPARK_CHARS[idx])
        return "".join(spark)

    def _derive_events(self, sample: dict[str, Any], history: list[dict[str, Any]]) -> list[str]:
        events: list[str] = []
        if len(history) >= 2:
            start = history[0]
            end = history[-1]
            availability_delta = (float(end.get("swarm_availability", 0.0)) - float(start.get("swarm_availability", 0.0))) * 100.0
            if abs(availability_delta) >= 1.0:
                direction = _("rose") if availability_delta > 0 else _("fell")
                events.append(
                    _("Availability {direction} {delta:+.1f}pp").format(direction=direction, delta=availability_delta)
                )

            peak_download = max(history, key=lambda point: float(point.get("download_rate", 0.0)))
            trough_download = min(history, key=lambda point: float(point.get("download_rate", 0.0)))
            peak_rate = float(peak_download.get("download_rate", 0.0)) / 1024.0
            trough_rate = float(trough_download.get("download_rate", 0.0)) / 1024.0
            if peak_rate - trough_rate >= 5.0:
                events.append(
                    _("Download swing {delta:.1f} KiB/s (peak {peak:.1f} KiB/s)").format(
                        delta=peak_rate - trough_rate,
                        peak=peak_rate,
                    )
                )

        trend = sample.get("trend")
        if trend:
            delta_pp = float(sample.get("trend_delta", 0.0) or 0.0) * 100.0
            events.append(
                _("Trend: {trend} ({delta:+.1f}pp)").format(trend=trend.title(), delta=delta_pp)
            )

        last_timestamp = history[-1].get("timestamp") if history else None
        if last_timestamp:
            events.append(_("Last sample {age}").format(age=self._format_relative_time(float(last_timestamp))))

        # Limit to top 3 annotations for readability
        return events[:3]

    @staticmethod
    def _format_relative_time(timestamp: float) -> str:
        delta = max(0.0, time.time() - timestamp)
        if delta < 60:
            return _("{seconds:.0f}s ago").format(seconds=delta)
        minutes = delta / 60.0
        if minutes < 60:
            return _("{minutes:.0f}m ago").format(minutes=minutes)
        hours = minutes / 60.0
        return _("{hours:.1f}h ago").format(hours=hours)

    def on_piece_event(self, *_: Any, **__: Any) -> None:  # pragma: no cover
        self._trigger_event_refresh()

    def on_progress_event(self, *_: Any, **__: Any) -> None:  # pragma: no cover
        self._trigger_event_refresh()

    def on_peer_event(self, *_: Any, **__: Any) -> None:  # pragma: no cover
        self._trigger_event_refresh()

    def _trigger_event_refresh(self) -> None:
        if not self._data_provider:
            return

        def schedule() -> None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            loop.create_task(self._update_from_provider())

        try:
            schedule()
        except Exception as exc:  # pragma: no cover
            logger.debug("SwarmTimelineWidget: Failed to schedule event refresh: %s", exc)




















































