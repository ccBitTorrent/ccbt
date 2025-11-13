"""Network quality monitoring screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Footer, Header, Static
else:
    try:
        from textual.app import ComposeResult
        from textual.containers import Vertical
        from textual.widgets import (
            Footer,
            Header,
            Static,
        )
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]
        Vertical = None  # type: ignore[assignment, misc]
        Footer = None  # type: ignore[assignment, misc]
        Header = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]

from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from ccbt.interface.screens.base import MonitoringScreen


class NetworkQualityScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display network quality metrics for peers and connections."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #global_stats {
        height: 1fr;
        min-height: 5;
    }
    #peer_quality {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the network quality screen."""
        yield Header()
        with Vertical():
            yield Static(id="global_stats")
            yield Static(id="content")
            yield Static(id="peer_quality")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh network quality metrics display."""
        try:
            global_stats_widget = self.query_one("#global_stats", Static)
            content = self.query_one("#content", Static)
            peer_quality = self.query_one("#peer_quality", Static)

            # Get global stats
            stats = await self.session.get_global_stats()
            all_status = await self.session.get_status()

            # Global network stats
            global_table = Table(
                title="Global Network Statistics",
                expand=True,
                show_header=False,
                box=None,
            )
            global_table.add_column("Metric", style="cyan", ratio=1)
            global_table.add_column("Value", style="green", ratio=2)

            def format_speed(s: float) -> str:
                """Format speed."""
                if s >= 1024 * 1024:
                    return f"{s / (1024**2):.2f} MB/s"
                if s >= 1024:
                    return f"{s / 1024:.2f} KB/s"
                return f"{s:.2f} B/s"

            global_table.add_row("Total Torrents", str(stats.get("num_torrents", 0)))
            global_table.add_row("Active Torrents", str(stats.get("num_active", 0)))
            global_table.add_row(
                "Global Download Rate", format_speed(stats.get("download_rate", 0.0))
            )
            global_table.add_row(
                "Global Upload Rate", format_speed(stats.get("upload_rate", 0.0))
            )

            # Calculate bandwidth utilization
            config = self.session.config
            if config and hasattr(config, "network"):
                max_download = getattr(config.network, "max_download_speed", 0)
                max_upload = getattr(config.network, "max_upload_speed", 0)
                download_rate = stats.get("download_rate", 0.0)
                upload_rate = stats.get("upload_rate", 0.0)

                if max_download > 0:
                    download_util = (download_rate / max_download) * 100.0
                    global_table.add_row(
                        "Download Utilization", f"{download_util:.1f}%"
                    )
                if max_upload > 0:
                    upload_util = (upload_rate / max_upload) * 100.0
                    global_table.add_row("Upload Utilization", f"{upload_util:.1f}%")

            global_stats_widget.update(Panel(global_table))

            # Per-torrent network quality
            torrent_table = Table(title="Per-Torrent Network Quality", expand=True)
            torrent_table.add_column("Torrent", style="cyan", ratio=2)
            torrent_table.add_column("Down Rate", style="green", ratio=1)
            torrent_table.add_column("Up Rate", style="green", ratio=1)
            torrent_table.add_column("Progress", style="yellow", ratio=1)
            torrent_table.add_column("Status", style="dim", ratio=1)

            for ih, status in list(all_status.items())[:10]:  # Limit to first 10
                name = str(status.get("name", ih[:12]))[:40]
                down_rate = float(status.get("download_rate", 0.0))
                up_rate = float(status.get("upload_rate", 0.0))
                progress = float(status.get("progress", 0.0)) * 100
                status_str = str(status.get("status", "-"))

                torrent_table.add_row(
                    name,
                    format_speed(down_rate),
                    format_speed(up_rate),
                    f"{progress:.1f}%",
                    status_str,
                )

            content.update(Panel(torrent_table))

            # Peer connection quality (for first torrent if available)
            if all_status:
                first_ih = next(iter(all_status.keys()))
                peers = await self.session.get_peers_for_torrent(first_ih)
                if peers:
                    # Calculate aggregate peer metrics
                    total_peers = len(peers)
                    choked_peers = sum(1 for p in peers if p.get("choked", True))
                    unchoke_ratio = (
                        ((total_peers - choked_peers) / total_peers * 100.0)
                        if total_peers > 0
                        else 0.0
                    )

                    # Calculate average latency
                    latencies = [
                        float(p.get("request_latency", 0.0))
                        for p in peers
                        if p.get("request_latency", 0.0) > 0
                    ]
                    avg_latency = (
                        (sum(latencies) / len(latencies) * 1000.0) if latencies else 0.0
                    )  # Convert to ms

                    # Calculate piece request success rate
                    total_requests = sum(
                        int(p.get("pieces_downloaded", 0))
                        + int(p.get("pieces_uploaded", 0))
                        for p in peers
                    )
                    successful_requests = sum(
                        int(p.get("pieces_downloaded", 0)) for p in peers
                    )
                    request_success_rate = (
                        (successful_requests / total_requests * 100.0)
                        if total_requests > 0
                        else 0.0
                    )

                    # Create peer metrics summary
                    peer_metrics_table = Table(
                        title="Peer Metrics Summary",
                        expand=True,
                        show_header=False,
                        box=None,
                    )
                    peer_metrics_table.add_column("Metric", style="cyan", ratio=1)
                    peer_metrics_table.add_column("Value", style="green", ratio=2)
                    peer_metrics_table.add_row("Total Peers", str(total_peers))
                    peer_metrics_table.add_row("Choked Peers", str(choked_peers))
                    peer_metrics_table.add_row("Unchoke Ratio", f"{unchoke_ratio:.1f}%")
                    peer_metrics_table.add_row(
                        "Average Latency",
                        f"{avg_latency:.1f} ms" if avg_latency > 0 else "N/A",
                    )
                    peer_metrics_table.add_row(
                        "Piece Request Success Rate", f"{request_success_rate:.1f}%"
                    )

                    peer_table = Table(
                        title=f"Peer Quality (Torrent: {first_ih[:12]}...)", expand=True
                    )
                    peer_table.add_column("IP", style="cyan", ratio=2)
                    peer_table.add_column("Down", style="green", ratio=1)
                    peer_table.add_column("Up", style="green", ratio=1)
                    peer_table.add_column("Quality", style="yellow", ratio=1)

                    for peer in peers[:15]:  # Limit to first 15 peers
                        ip = str(peer.get("ip", "-"))
                        down = float(peer.get("download_rate", 0.0))
                        up = float(peer.get("upload_rate", 0.0))
                        quality = self._calculate_connection_quality(peer)
                        quality_indicator = self._format_quality_indicator(quality)

                        peer_table.add_row(
                            ip,
                            format_speed(down),
                            format_speed(up),
                            quality_indicator,
                        )

                    # Combine metrics and peer table
                    peer_quality.update(Panel(Group(peer_metrics_table, peer_table)))
                else:
                    peer_quality.update(
                        Panel("No peers available", title="Peer Quality")
                    )
            else:
                peer_quality.update(
                    Panel("No torrents available", title="Peer Quality")
                )

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading network quality metrics: {e}",
                    title="Error",
                    border_style="red",
                )
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
            return f"[green]{quality:.0f}%[/green] ████████"
        if quality >= 60:
            return f"[yellow]{quality:.0f}%[/yellow] ██████░░"
        if quality >= 40:
            return f"[orange1]{quality:.0f}%[/orange1] ████░░░░"
        return f"[red]{quality:.0f}%[/red] ██░░░░░░"

