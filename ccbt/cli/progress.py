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

import contextlib
from typing import TYPE_CHECKING, Any, Callable, Iterator, Mapping

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ccbt.i18n import _

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
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

    def create_progress(self, _description: str | None = None) -> Progress:
        """Create a new progress bar with i18n support.

        Args:
            description: Optional progress description (will be translated)

        Returns:
            Progress instance

        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )

    def create_download_progress(
        self, _torrent: TorrentInfo | Mapping[str, Any]
    ) -> Progress:
        """Create download progress bar with i18n support."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.downloaded]{task.fields[downloaded]}"),
            TextColumn("[progress.speed]{task.fields[speed]}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )

    def create_upload_progress(
        self, _torrent: TorrentInfo | Mapping[str, Any]
    ) -> Progress:
        """Create upload progress bar with i18n support."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.uploaded]{task.fields[uploaded]}"),
            TextColumn("[progress.speed]{task.fields[speed]}"),
            TimeElapsedColumn(),
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
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
            console=self.console,
        )

    def create_operation_progress(
        self, _description: str | None = None, show_speed: bool = False
    ) -> Progress:
        """Create a generic operation progress bar.

        Args:
            description: Optional progress description (will be translated)
            show_speed: Whether to show speed information

        Returns:
            Progress instance

        """
        columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ]

        if show_speed:
            columns.append(TextColumn("[progress.speed]{task.fields[speed]}"))

        columns.extend([TimeElapsedColumn(), TimeRemainingColumn()])

        return Progress(*columns, console=self.console)

    def create_multi_task_progress(
        self, _description: str | None = None
    ) -> Progress:
        """Create a progress bar for multiple parallel tasks.

        Args:
            description: Optional progress description (will be translated)

        Returns:
            Progress instance

        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.completed]{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )

    def create_indeterminate_progress(
        self, _description: str | None = None
    ) -> Progress:
        """Create an indeterminate progress bar (no known total).

        Args:
            description: Optional progress description (will be translated)

        Returns:
            Progress instance

        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=self.console,
        )

    @contextlib.contextmanager
    def with_progress(
        self,
        description: str,
        total: int | None = None,
        progress_type: str = "operation",
    ) -> Iterator[tuple[Progress, int]]:
        """Context manager for automatic progress tracking.

        Args:
            description: Progress description (will be translated)
            total: Total number of items (None for indeterminate)
            progress_type: Type of progress ("operation", "download", "upload", etc.)

        Yields:
            Tuple of (Progress instance, task_id)

        """
        # Translate description
        translated_desc = _(description)

        # Create appropriate progress bar
        if progress_type == "download":
            progress = self.create_download_progress({})
        elif progress_type == "upload":
            progress = self.create_upload_progress({})
        elif progress_type == "indeterminate" or total is None:
            progress = self.create_indeterminate_progress(translated_desc)
        else:
            progress = self.create_operation_progress(translated_desc)

        with progress:
            # Initialize task with appropriate fields based on progress type
            if progress_type == "download":
                task_id = progress.add_task(
                    translated_desc, total=total, downloaded="0 B", speed="0 B/s"
                )
            elif progress_type == "upload":
                task_id = progress.add_task(
                    translated_desc, total=total, uploaded="0 B", speed="0 B/s"
                )
            else:
                task_id = progress.add_task(translated_desc, total=total)
            try:
                yield progress, task_id
            finally:
                # Progress is automatically cleaned up by context manager
                pass

    def create_progress_callback(
        self, progress: Progress, task_id: int
    ) -> Callable[[float, dict[str, Any] | None], None]:
        """Create a progress callback for async operations.

        Args:
            progress: Progress instance
            task_id: Task ID

        Returns:
            Callback function that can be called with (completed, fields_dict)

        """
        def callback(completed: float, fields: dict[str, Any] | None = None) -> None:
            """Update progress with completed amount and optional fields."""
            progress.update(task_id, completed=completed)
            if fields:
                progress.update(task_id, **fields)

        return callback
