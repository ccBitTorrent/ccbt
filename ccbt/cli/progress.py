"""Progress Manager for ccBitTorrent CLI.

Provides comprehensive progress tracking including:
- Download progress bars
- Upload progress bars
- Piece completion tracking
- Speed monitoring
- ETA calculation
"""

from typing import Any, Dict

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ..models import TorrentInfo


class ProgressManager:
    """Progress manager for CLI."""

    def __init__(self, console: Console):
        self.console = console
        self.active_progress: Dict[str, Progress] = {}
        self.progress_tasks: Dict[str, Any] = {}

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

    def create_download_progress(self, torrent: TorrentInfo) -> Progress:
        """Create download progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.downloaded]{task.fields[downloaded]}"),
            TextColumn("[progress.speed]{task.fields[speed]}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        )

        return progress

    def create_upload_progress(self, torrent: TorrentInfo) -> Progress:
        """Create upload progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.uploaded]{task.fields[uploaded]}"),
            TextColumn("[progress.speed]{task.fields[speed]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_piece_progress(self, torrent: TorrentInfo) -> Progress:
        """Create piece completion progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.pieces]{task.fields[pieces]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_speed_progress(self, torrent: TorrentInfo) -> Progress:
        """Create speed monitoring progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.download_speed]{task.fields[download_speed]}"),
            TextColumn("[progress.upload_speed]{task.fields[upload_speed]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_peer_progress(self, torrent: TorrentInfo) -> Progress:
        """Create peer connection progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.peers]{task.fields[peers]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_verification_progress(self, torrent: TorrentInfo) -> Progress:
        """Create hash verification progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.verified]{task.fields[verified]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_metadata_progress(self, torrent: TorrentInfo) -> Progress:
        """Create metadata download progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.metadata]{task.fields[metadata]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_tracker_progress(self, torrent: TorrentInfo) -> Progress:
        """Create tracker communication progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.trackers]{task.fields[trackers]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_dht_progress(self, torrent: TorrentInfo) -> Progress:
        """Create DHT progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.dht_nodes]{task.fields[dht_nodes]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_pex_progress(self, torrent: TorrentInfo) -> Progress:
        """Create PEX progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.pex_peers]{task.fields[pex_peers]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_webseed_progress(self, torrent: TorrentInfo) -> Progress:
        """Create WebSeed progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.webseeds]{task.fields[webseeds]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_encryption_progress(self, torrent: TorrentInfo) -> Progress:
        """Create encryption progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.encrypted]{task.fields[encrypted]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_security_progress(self, torrent: TorrentInfo) -> Progress:
        """Create security progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.security_checks]{task.fields[security_checks]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_ml_progress(self, torrent: TorrentInfo) -> Progress:
        """Create ML progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.ml_predictions]{task.fields[ml_predictions]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_monitoring_progress(self, torrent: TorrentInfo) -> Progress:
        """Create monitoring progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.metrics]{task.fields[metrics]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_observability_progress(self, torrent: TorrentInfo) -> Progress:
        """Create observability progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.traces]{task.fields[traces]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_dashboard_progress(self, torrent: TorrentInfo) -> Progress:
        """Create dashboard progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.dashboards]{task.fields[dashboards]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_alert_progress(self, torrent: TorrentInfo) -> Progress:
        """Create alert progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.alerts]{task.fields[alerts]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_tracing_progress(self, torrent: TorrentInfo) -> Progress:
        """Create tracing progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.spans]{task.fields[spans]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_profiling_progress(self, torrent: TorrentInfo) -> Progress:
        """Create profiling progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.profiles]{task.fields[profiles]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_debug_progress(self, torrent: TorrentInfo) -> Progress:
        """Create debug progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.debug_info]{task.fields[debug_info]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_completion_progress(self, torrent: TorrentInfo) -> Progress:
        """Create completion progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.completion]{task.fields[completion]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_cleanup_progress(self, torrent: TorrentInfo) -> Progress:
        """Create cleanup progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.cleanup]{task.fields[cleanup]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_finalization_progress(self, torrent: TorrentInfo) -> Progress:
        """Create finalization progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.finalization]{task.fields[finalization]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_verification_final_progress(self, torrent: TorrentInfo) -> Progress:
        """Create final verification progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.final_verification]{task.fields[final_verification]}"),
            TimeElapsedColumn(),
        )

        return progress

    def create_success_progress(self, torrent: TorrentInfo) -> Progress:
        """Create success progress bar."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.success]{task.fields[success]}"),
            TimeElapsedColumn(),
        )

        return progress
