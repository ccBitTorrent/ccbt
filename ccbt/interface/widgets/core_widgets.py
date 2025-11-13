"""Core widget components for the terminal dashboard."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.widgets import DataTable, Sparkline, Static
else:
    try:
        from textual.widgets import DataTable, Sparkline, Static
    except ImportError:
        # Fallback for when textual is not available
        class DataTable:  # type: ignore[no-redef]
            pass

        class Sparkline:  # type: ignore[no-redef]
            pass

        class Static:  # type: ignore[no-redef]
            pass


from rich.panel import Panel
from rich.table import Table


class Overview(Static):  # type: ignore[misc]
    """Simple widget to render global stats."""

    def update_from_stats(self, stats: dict[str, Any]) -> None:  # pragma: no cover
        """Update dashboard with statistics."""
        rows = [
            ("Torrents", str(stats.get("num_torrents", 0))),
            ("Active", str(stats.get("num_active", 0))),
            ("Paused", str(stats.get("num_paused", 0))),
            ("Seeding", str(stats.get("num_seeding", 0))),
            ("Down Rate", f"{stats.get('download_rate', 0.0):.1f} B/s"),
            ("Up Rate", f"{stats.get('upload_rate', 0.0):.1f} B/s"),
            ("Avg Progress", f"{stats.get('average_progress', 0.0) * 100:.1f}%"),
        ]
        t = Table(show_header=False, box=None, expand=True)
        t.add_column("Key", style="cyan", ratio=1)
        t.add_column("Value", style="green", ratio=2)
        for k, v in rows:
            t.add_row(k, v)
        self.update(Panel(t, title="Overview"))


class TorrentsTable(DataTable):  # type: ignore[misc]
    """Widget to render per-torrent status table."""

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the torrents table widget."""
        # Textual widget lifecycle - requires widget mounting context
        self.zebra_stripes = True
        self.add_columns("Info Hash", "Name", "Status", "Progress", "Down/Up (B/s)")

    def update_from_status(
        self, status: dict[str, dict[str, Any]]
    ) -> None:  # pragma: no cover
        """Update torrents table with current status."""
        self.clear()
        for ih, st in status.items():
            progress = f"{float(st.get('progress', 0.0)) * 100:.1f}%"
            rates = f"{float(st.get('download_rate', 0.0)):.0f} / {float(st.get('upload_rate', 0.0)):.0f}"
            self.add_row(
                ih,
                str(st.get("name", "-")),
                str(st.get("status", "-")),
                progress,
                rates,
                key=ih,
            )

    def get_selected_info_hash(self) -> str | None:  # pragma: no cover
        """Get the info hash of the currently selected torrent."""
        if hasattr(self, "cursor_row_key"):
            with contextlib.suppress(Exception):
                row_key = self.cursor_row_key
                return None if row_key is None else str(row_key)
        return None


class PeersTable(DataTable):  # type: ignore[misc]
    """Widget to render peers for selected torrent."""

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the peers table widget."""
        # Textual widget lifecycle - requires widget mounting context
        self.zebra_stripes = True
        self.add_columns(
            "IP",
            "Port",
            "Down (B/s)",
            "Up (B/s)",
            "Latency",
            "Quality",
            "Health",
            "Choked",
            "Client",
        )

    def _calculate_connection_quality(
        self, peer_data: dict[str, Any]
    ) -> float:  # pragma: no cover
        """Calculate connection quality score (0-100).

        Args:
            peer_data: Peer data dictionary

        Returns:
            Quality score (0-100)
        """
        down = float(peer_data.get("download_rate", 0.0))
        up = float(peer_data.get("upload_rate", 0.0))
        choked = peer_data.get("choked", True)

        # Simple quality calculation
        # Higher speeds and unchoked = better quality
        quality = 0.0
        if not choked:
            quality += 50.0

        # Speed contribution (normalized, max 50 points)
        total_speed = down + up
        if total_speed > 0:
            # Assume 1 MB/s = 50 points (max)
            speed_score = min(50.0, (total_speed / (1024 * 1024)) * 50.0)
            quality += speed_score

        return min(100.0, max(0.0, quality))

    def _format_quality_indicator(self, quality: float) -> str:  # pragma: no cover
        """Format quality as visual indicator.

        Args:
            quality: Quality score (0-100)

        Returns:
            Formatted quality string
        """
        if quality >= 80:
            return f"[green]{quality:.0f}%[/green]"
        if quality >= 60:
            return f"[yellow]{quality:.0f}%[/yellow]"
        if quality >= 40:
            return f"[orange1]{quality:.0f}%[/orange1]"
        return f"[red]{quality:.0f}%[/red]"

    def _get_health_status(self, quality: float) -> str:  # pragma: no cover
        """Get health status string based on quality score.

        Args:
            quality: Quality score (0-100)

        Returns:
            Health status string
        """
        if quality >= 80:
            return "[green]Excellent[/green]"
        if quality >= 60:
            return "[yellow]Good[/yellow]"
        if quality >= 40:
            return "[orange1]Fair[/orange1]"
        return "[red]Poor[/red]"

    def update_from_peers(
        self, peers: list[dict[str, Any]]
    ) -> None:  # pragma: no cover
        """Update peers table with current peer data."""
        self.clear()
        for p in peers or []:
            # Calculate quality score
            quality = self._calculate_connection_quality(p)
            quality_str = self._format_quality_indicator(quality)
            health_status = self._get_health_status(quality)

            # Get latency
            latency = p.get("request_latency", 0.0)
            if latency and latency > 0:
                latency_str = f"{latency * 1000:.1f} ms"
            else:
                latency_str = "N/A"

            self.add_row(
                str(p.get("ip", "-")),
                str(p.get("port", "-")),
                f"{float(p.get('download_rate', 0.0)):.0f}",
                f"{float(p.get('upload_rate', 0.0)):.0f}",
                latency_str,
                quality_str,
                health_status,
                str(p.get("choked", False)),
                str(p.get("client", "?")),
            )


class SpeedSparklines(Static):  # type: ignore[misc]
    """Widget to show download/upload speed history."""

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the speed sparklines widget."""
        # Textual widget lifecycle - requires widget mounting context
        self._down = Sparkline()
        self._up = Sparkline()
        self._down_history: list[float] = []
        self._up_history: list[float] = []
        # Mount sparklines as children instead of wrapping in Container
        self.mount(self._down, self._up)
        # Update with a simple title instead of Panel
        self.update("Speeds")

    def update_from_stats(self, stats: dict[str, Any]) -> None:  # pragma: no cover
        """Update sparklines with current speed statistics."""
        self._down_history.append(float(stats.get("download_rate", 0.0)))
        self._up_history.append(float(stats.get("upload_rate", 0.0)))
        # Keep last 120 samples (~2 minutes at 1s)
        self._down_history = self._down_history[-120:]
        self._up_history = self._up_history[-120:]
        with contextlib.suppress(Exception):
            self._down.data = self._down_history  # type: ignore[attr-defined]
            self._up.data = self._up_history  # type: ignore[attr-defined]
