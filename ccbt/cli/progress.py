"""Progress Manager for ccBitTorrent CLI.

from __future__ import annotations

Provides comprehensive progress tracking including:
- Download progress bars
- Upload progress bars
- Piece completion tracking
- Speed monitoring
- ETA calculation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

if TYPE_CHECKING:
    from rich.console import Console

    from ccbt.models import TorrentInfo


class ProgressManager:
    """Progress manager for CLI."""

    def __init__(self, console: Console):
        """Initialize progress manager.

        Args:
            console: Rich console for output
        """
        self.console = console
        self.active_progress: dict[str, Progress] = {}
        self.progress_tasks: dict[str, Any] = {}

    def create_progress(self) -> Progress:
        """Create a new progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        )

    def create_download_progress(
        self, _torrent: TorrentInfo | Mapping[str, Any]
    ) -> Progress:
        """Create download progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.downloaded]{task.fields[downloaded]}"),
            TextColumn("[progress.speed]{task.fields[speed]}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        )

    def create_upload_progress(
        self, _torrent: TorrentInfo | Mapping[str, Any]
    ) -> Progress:
        """Create upload progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.uploaded]{task.fields[uploaded]}"),
            TextColumn("[progress.speed]{task.fields[speed]}"),
            TimeElapsedColumn(),
        )

    def create_piece_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create piece completion progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.pieces]{task.fields[pieces]}"),
            TimeElapsedColumn(),
        )

    def create_speed_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create speed monitoring progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.download_speed]{task.fields[download_speed]}"),
            TextColumn("[progress.upload_speed]{task.fields[upload_speed]}"),
            TimeElapsedColumn(),
        )

    def create_peer_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create peer connection progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.peers]{task.fields[peers]}"),
            TimeElapsedColumn(),
        )

    def create_verification_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create hash verification progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.verified]{task.fields[verified]}"),
            TimeElapsedColumn(),
        )

    def create_metadata_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create metadata download progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.metadata]{task.fields[metadata]}"),
            TimeElapsedColumn(),
        )

    def create_tracker_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create tracker communication progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.trackers]{task.fields[trackers]}"),
            TimeElapsedColumn(),
        )

    def create_dht_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create DHT progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.dht_nodes]{task.fields[dht_nodes]}"),
            TimeElapsedColumn(),
        )

    def create_pex_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create PEX progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.pex_peers]{task.fields[pex_peers]}"),
            TimeElapsedColumn(),
        )

    def create_webseed_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create WebSeed progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.webseeds]{task.fields[webseeds]}"),
            TimeElapsedColumn(),
        )

    def create_encryption_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create encryption progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.encrypted]{task.fields[encrypted]}"),
            TimeElapsedColumn(),
        )

    def create_security_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create security progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.security_checks]{task.fields[security_checks]}"),
            TimeElapsedColumn(),
        )

    def create_ml_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create ML progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.ml_predictions]{task.fields[ml_predictions]}"),
            TimeElapsedColumn(),
        )

    def create_monitoring_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create monitoring progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.metrics]{task.fields[metrics]}"),
            TimeElapsedColumn(),
        )

    def create_observability_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create observability progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.traces]{task.fields[traces]}"),
            TimeElapsedColumn(),
        )

    def create_dashboard_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create dashboard progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.dashboards]{task.fields[dashboards]}"),
            TimeElapsedColumn(),
        )

    def create_alert_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create alert progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.alerts]{task.fields[alerts]}"),
            TimeElapsedColumn(),
        )

    def create_tracing_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create tracing progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.spans]{task.fields[spans]}"),
            TimeElapsedColumn(),
        )

    def create_profiling_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create profiling progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.profiles]{task.fields[profiles]}"),
            TimeElapsedColumn(),
        )

    def create_debug_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create debug progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.debug_info]{task.fields[debug_info]}"),
            TimeElapsedColumn(),
        )

    def create_completion_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create completion progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.completion]{task.fields[completion]}"),
            TimeElapsedColumn(),
        )

    def create_cleanup_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create cleanup progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.cleanup]{task.fields[cleanup]}"),
            TimeElapsedColumn(),
        )

    def create_finalization_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create finalization progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.finalization]{task.fields[finalization]}"),
            TimeElapsedColumn(),
        )

    def create_verification_final_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create final verification progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn(
                "[progress.final_verification]{task.fields[final_verification]}",
            ),
            TimeElapsedColumn(),
        )

    def create_success_progress(self, _torrent: TorrentInfo) -> Progress:
        """Create success progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.success]{task.fields[success]}"),
            TimeElapsedColumn(),
        )
