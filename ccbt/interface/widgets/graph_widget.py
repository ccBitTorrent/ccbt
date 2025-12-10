"""Reusable graph widget for displaying metrics graphs.

Provides a base class for all graph types with common functionality.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ccbt.interface.data_provider import DataProvider
else:
    try:
        from ccbt.interface.data_provider import DataProvider
    except ImportError:
        DataProvider = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Sparkline, Static, DataTable
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class Sparkline:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class DataTable:  # type: ignore[no-redef]
        pass

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ccbt.interface.widgets.piece_availability_bar import (
    PIECE_HEALTH_COLORS,
    PIECE_HEALTH_GLYPHS,
    PIECE_HEALTH_LABELS,
    determine_piece_health_level,
)

logger = logging.getLogger(__name__)


class BaseGraphWidget(Container):  # type: ignore[misc]
    """Base class for graph widgets.

    Provides common functionality for all graph types including:
    - Data buffer management
    - Sparkline rendering
    - Update handling
    """

    DEFAULT_CSS = """
    BaseGraphWidget {
        height: 1fr;
        min-height: 15;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    
    #graph-title {
        height: 1;
        min-height: 1;
        display: block;
    }
    
    #graph-content {
        height: 1fr;
        min-height: 12;
        display: block;
    }
    
    Sparkline {
        height: 10;
        min-height: 10;
        width: 1fr;
        min-width: 20;
        display: block;
    }
    """

    def __init__(
        self,
        title: str,
        data_provider: DataProvider | None = None,
        max_samples: int = 120,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize base graph widget.

        Args:
            title: Graph title
            data_provider: Optional DataProvider for fetching metrics
            max_samples: Maximum number of data points to keep
        """
        super().__init__(*args, **kwargs)
        self._title = title
        self._data_provider = data_provider
        self._max_samples = max_samples
        self._data_history: list[float] = []
        self._sparkline: Sparkline | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the graph widget."""
        yield Static(self._title, id="graph-title")
        with Container(id="graph-content"):
            yield Sparkline(id="graph-sparkline")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the graph widget."""
        try:
            self._sparkline = self.query_one("#graph-sparkline", Sparkline)  # type: ignore[attr-defined]
            # CRITICAL FIX: Initialize with varying data pattern so Sparkline renders a visible line
            # A flat line (all same value) may not be visible - use a simple wave pattern
            if self._sparkline:
                # Create a simple visible pattern: [0.1, 0.2, 0.1, 0.2, ...] repeated
                initial_data = [0.1 + (i % 2) * 0.1 for i in range(20)]
                self._sparkline.data = initial_data  # type: ignore[attr-defined]
                self._sparkline.display = True  # type: ignore[attr-defined]
                if hasattr(self._sparkline, "refresh"):
                    self._sparkline.refresh()  # type: ignore[attr-defined]
                logger.debug("BaseGraphWidget: Initialized sparkline with %d varying data points", len(initial_data))
        except Exception as e:
            logger.debug("Error mounting graph widget: %s", e)

    def add_data_point(self, value: float) -> None:  # pragma: no cover
        """Add a data point to the graph.

        Args:
            value: Data point value
        """
        self._data_history.append(value)
        # Keep only last max_samples
        self._data_history = self._data_history[-self._max_samples :]
        self._update_display()

    def set_data(self, data: list[float]) -> None:  # pragma: no cover
        """Set graph data directly.

        Args:
            data: List of data points
        """
        self._data_history = data[-self._max_samples :]
        self._update_display()

    def _update_display(self) -> None:  # pragma: no cover
        """Update the graph display."""
        if self._sparkline and self._data_history:
            try:
                self._sparkline.data = self._data_history  # type: ignore[attr-defined]
                # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                if hasattr(self._sparkline, "refresh"):
                    self._sparkline.refresh()  # type: ignore[attr-defined]
            except Exception as e:
                logger.error("Error updating graph display: %s", e, exc_info=True)

    def on_piece_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle piece-related events (PIECE_REQUESTED, PIECE_DOWNLOADED, PIECE_VERIFIED, PIECE_COMPLETED).
        
        Args:
            event_type: Event type string
            event_data: Event data dictionary containing info_hash, piece_index, etc.
        
        This method can be overridden by subclasses to handle piece events.
        By default, it triggers a refresh to update the widget.
        """
        # Add event to timeline for annotation
        import time
        event_label = event_type.replace("PIECE_", "").replace("_", " ").title()
        if event_type == "PIECE_COMPLETED":
            piece_index = event_data.get("piece_index", "?")
            event_label = f"Piece {piece_index} Completed"
        self._add_event_annotation(time.time(), event_type, event_label, event_data.get("info_hash"))
        
        # Default implementation: trigger refresh if this widget cares about piece events
        # Subclasses can override to handle specific events
        try:
            # Trigger async update if data provider is available
            if self._data_provider:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    # Schedule update (non-blocking)
                    loop.create_task(self._update_from_provider())
                except RuntimeError:
                    # No event loop, skip
                    pass
        except Exception as e:
            logger.debug("BaseGraphWidget.on_piece_event: Error handling piece event: %s", e)

    def on_progress_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle progress update events (PROGRESS_UPDATED).
        
        Args:
            event_type: Event type string
            event_data: Event data dictionary containing info_hash, progress, etc.
        
        This method can be overridden by subclasses to handle progress events.
        By default, it triggers a refresh to update the widget.
        """
        # Note: Progress events are too frequent to annotate individually
        # Only annotate significant milestones (e.g., 25%, 50%, 75%, 100%)
        progress = event_data.get("progress", 0.0)
        if isinstance(progress, (int, float)) and progress > 0:
            milestones = [0.25, 0.50, 0.75, 1.0]
            for milestone in milestones:
                if abs(progress - milestone) < 0.01:  # Within 1% of milestone
                    import time
                    self._add_event_annotation(
                        time.time(),
                        event_type,
                        f"Progress {int(milestone * 100)}%",
                        event_data.get("info_hash"),
                    )
                    break
        
        # Default implementation: trigger refresh
        try:
            if self._data_provider:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._update_from_provider())
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("BaseGraphWidget.on_progress_event: Error handling progress event: %s", e)

    def on_peer_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle peer-related events (PEER_CONNECTED, PEER_DISCONNECTED, etc.).
        
        Args:
            event_type: Event type string
            event_data: Event data dictionary containing info_hash, peer_key, etc.
        
        This method can be overridden by subclasses that care about peer events.
        By default, it does nothing (not all widgets care about peer events).
        """
        # Add peer events to timeline (only for UploadDownloadGraphWidget)
        if hasattr(self, "_add_event_annotation"):
            import time
            event_label = event_type.replace("PEER_", "").replace("_", " ").title()
            self._add_event_annotation(time.time(), event_type, event_label, event_data.get("info_hash"))
        
        # Default implementation: no-op (most widgets don't care about peer events)
        # Subclasses like PeerQualitySummaryWidget can override
        pass
    
    def on_tracker_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle tracker-related events (TRACKER_ANNOUNCE_STARTED, TRACKER_ANNOUNCE_SUCCESS, etc.).
        
        Args:
            event_type: Event type string
            event_data: Event data dictionary containing info_hash, tracker_url, etc.
        
        This method can be overridden by subclasses that care about tracker events.
        By default, it adds events to the timeline if the widget supports annotations.
        """
        # Add tracker events to timeline (only for UploadDownloadGraphWidget)
        if hasattr(self, "_add_event_annotation"):
            import time
            event_label = event_type.replace("TRACKER_", "").replace("_", " ").title()
            # Only annotate successful announces to avoid clutter
            if "SUCCESS" in event_type:
                self._add_event_annotation(time.time(), event_type, event_label, event_data.get("info_hash"))

    async def _update_from_provider(self) -> None:
        """Update widget from data provider.
        
        This is a placeholder that subclasses should override if they want
        to support event-driven updates. By default, widgets continue using
        polling via their existing update mechanisms.
        """
        # Default: no-op (widgets use their own polling mechanisms)
        pass


class UploadDownloadGraphWidget(BaseGraphWidget):  # type: ignore[misc]
    """Graph widget for combined upload and download speeds."""

    def __init__(
        self,
        data_provider: DataProvider | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize upload/download graph widget."""
        super().__init__("Upload & Download Speed", data_provider, *args, **kwargs)
        self._download_history: list[float] = []
        self._upload_history: list[float] = []
        self._timestamps: list[float] = []  # Store timestamps for time-based display
        self._download_sparkline: Sparkline | None = None
        self._upload_sparkline: Sparkline | None = None
        self._update_task: Any | None = None
        # Event timeline tracking for annotations
        self._event_timeline: list[dict[str, Any]] = []  # List of {timestamp, type, label, info_hash}
        self._max_events = 50  # Keep last 50 events
        self._event_annotations_widget: Static | None = None

    DEFAULT_CSS = """
    UploadDownloadGraphWidget {
        height: 1fr;
        min-height: 20;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    
    #graph-title {
        height: 1;
        min-height: 1;
        text-style: bold;
        display: block;
    }
    
    #graph-content {
        height: 1fr;
        min-height: 18;
        layout: vertical;
        display: block;
        overflow-y: auto;
        overflow-x: hidden;
    }
    
    #download-label, #upload-label {
        height: 1;
        min-height: 1;
        margin: 0 1;
        display: block;
    }
    
    Sparkline {
        height: 10;
        min-height: 10;
        width: 1fr;
        min-width: 20;
        margin: 1;
        display: block;
        border: solid $primary;
        background: $surface;
        color: $primary;
    }
    
    #download-sparkline, #upload-sparkline {
        height: 10;
        min-height: 10;
        width: 1fr;
        display: block;
        color: $primary;
    }
    """
    
    def compose(self) -> Any:  # pragma: no cover
        """Compose the upload/download graph widget."""
        yield Static("Upload & Download Speed", id="graph-title")
        with Vertical(id="graph-content"):
            yield Static("Download (KiB/s):", id="download-label")
            yield Sparkline(id="download-sparkline")
            yield Static("Upload (KiB/s):", id="upload-label")
            yield Sparkline(id="upload-sparkline")
            yield Static("", id="event-annotations")  # Event timeline annotations

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the upload/download graph widget."""
        try:
            self._download_sparkline = self.query_one("#download-sparkline", Sparkline)  # type: ignore[attr-defined]
            self._upload_sparkline = self.query_one("#upload-sparkline", Sparkline)  # type: ignore[attr-defined]
            self._event_annotations_widget = self.query_one("#event-annotations", Static)  # type: ignore[attr-defined]
            
            # CRITICAL FIX: Initialize with VARYING data pattern so Sparklines render a visible line
            # A flat line (all same value) may not be visible - use a simple wave pattern
            # Create a visible pattern: [0.1, 0.2, 0.1, 0.2, ...] repeated for 20 points
            initial_data = [0.1 + (i % 2) * 0.1 for i in range(20)]
            if self._download_sparkline:
                self._download_sparkline.data = initial_data  # type: ignore[attr-defined]
                self._download_sparkline.display = True  # type: ignore[attr-defined]
                # CRITICAL: Ensure widget is visible and has proper size
                if hasattr(self._download_sparkline, "styles"):
                    self._download_sparkline.styles.min_height = 10  # type: ignore[attr-defined]
                self._download_sparkline.refresh()  # type: ignore[attr-defined]
                logger.debug("UploadDownloadGraphWidget: Initialized download sparkline with %d varying data points", len(initial_data))
            if self._upload_sparkline:
                self._upload_sparkline.data = initial_data  # type: ignore[attr-defined]
                self._upload_sparkline.display = True  # type: ignore[attr-defined]
                # CRITICAL: Ensure widget is visible and has proper size
                if hasattr(self._upload_sparkline, "styles"):
                    self._upload_sparkline.styles.min_height = 10  # type: ignore[attr-defined]
                self._upload_sparkline.refresh()  # type: ignore[attr-defined]
                logger.debug("UploadDownloadGraphWidget: Initialized upload sparkline with %d varying data points", len(initial_data))
            
            # CRITICAL FIX: Start periodic updates if data provider is available
            if self._data_provider:
                logger.debug("UploadDownloadGraphWidget: Starting update loop with data provider")
                self._start_updates()
                # CRITICAL FIX: Trigger immediate update after widget is fully mounted
                # Use call_after_refresh to ensure widget is ready and event loop is accessible
                def trigger_initial_update() -> None:
                    """Trigger initial data update after widget is ready."""
                    try:
                        import asyncio
                        # Get the running event loop
                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            loop = asyncio.get_event_loop()
                        # Create task in the correct event loop
                        task = loop.create_task(self._update_from_provider())
                        logger.debug("UploadDownloadGraphWidget: Scheduled initial update task: %s", task)
                    except Exception as e:
                        logger.error("UploadDownloadGraphWidget: Error scheduling initial update: %s", e, exc_info=True)
                
                self.call_after_refresh(trigger_initial_update)  # type: ignore[attr-defined]
            else:
                logger.warning("UploadDownloadGraphWidget: No data provider available - graphs will not update")
        except Exception as e:
            logger.error("Error mounting upload/download graph: %s", e, exc_info=True)

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount the widget and stop updates."""
        if self._update_task:
            # set_interval returns a Timer which has stop(), not cancel()
            # Fallback code might create a Task which has cancel()
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:  # pragma: no cover
        """Start periodic updates from data provider."""
        import asyncio
        
        def schedule_update() -> None:
            """Schedule async update (wrapper for set_interval)."""
            try:
                # CRITICAL FIX: Get the event loop and create task properly
                # Textual widgets run in the app's event loop, so we can get it directly
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # No running loop, try to get event loop
                    loop = asyncio.get_event_loop()
                
                # Create task in the correct event loop
                task = loop.create_task(self._update_from_provider())
                logger.debug("UploadDownloadGraphWidget: Created async update task: %s", task)
            except Exception as e:
                logger.error("Error scheduling graph update: %s", e, exc_info=True)
        
        try:
            # CRITICAL FIX: set_interval doesn't work with async functions directly
            # Use wrapper function that creates async task
            # CRITICAL FIX: Reduced interval from 2.0s to 1.0s for tighter performance updates
            self._update_task = self.set_interval(1.0, schedule_update)  # type: ignore[attr-defined]
            # Trigger initial update immediately using call_after_refresh to ensure widget is ready
            self.call_after_refresh(schedule_update)  # type: ignore[attr-defined]
            logger.debug("UploadDownloadGraphWidget: Update loop started")
        except Exception as e:
            logger.error("Error starting graph update loop: %s", e, exc_info=True)

    async def _update_from_provider(self) -> None:  # pragma: no cover
        """Update graph data from data provider."""
        if not self._data_provider:
            logger.warning("UploadDownloadGraphWidget: No data provider available in _update_from_provider")
            # Show zero data if no provider
            self._download_history = [0.0] * min(10, self._max_samples)
            self._upload_history = [0.0] * min(10, self._max_samples)
            self._update_display()
            return
        
        try:
            # Fetch rate samples (last 120 seconds by default)
            # CRITICAL FIX: Use shorter timeout for UI responsiveness
            # If daemon is busy (e.g., adding torrent), don't block UI for 30+ seconds
            logger.debug("UploadDownloadGraphWidget: Fetching rate samples from data provider...")
            try:
                samples = await asyncio.wait_for(
                    self._data_provider.get_rate_samples(seconds=120),
                    timeout=10.0  # 10 second timeout for UI responsiveness (increased from 5.0)
                )
            except asyncio.TimeoutError:
                logger.debug("UploadDownloadGraphWidget: Metrics fetch timed out, using cached/existing data")
                # Keep existing display, don't update - prevents UI hang
                return
            except Exception as e:
                logger.debug("UploadDownloadGraphWidget: Error fetching rate samples (will retry next cycle): %s", e)
                # Keep existing display, don't update
                return
            
            logger.debug("UploadDownloadGraphWidget: Retrieved %d rate samples", len(samples) if samples else 0)
            
            if not samples:
                logger.debug("UploadDownloadGraphWidget: No rate samples returned from provider")
                # Show zero data if no samples
                if not self._download_history:
                    self._download_history = [0.0] * min(10, self._max_samples)
                if not self._upload_history:
                    self._upload_history = [0.0] * min(10, self._max_samples)
                self._update_display()
                return
            
            # Extract download and upload rates from samples
            # Samples format: [{"timestamp": ..., "download_rate": ..., "upload_rate": ...}, ...]
            # OR: [RateSample(...), ...] from Pydantic models
            # CRITICAL: Ensure samples are sorted by timestamp for proper time-based display
            if samples:
                # Sort by timestamp to ensure chronological order
                def get_timestamp(s: Any) -> float:
                    """Extract timestamp from sample (dict or Pydantic model)."""
                    if isinstance(s, dict):
                        return float(s.get("timestamp", 0.0))
                    elif hasattr(s, "timestamp"):
                        return float(getattr(s, "timestamp", 0.0))
                    return 0.0
                
                samples = sorted(samples, key=get_timestamp)
            
            download_rates: list[float] = []
            upload_rates: list[float] = []
            timestamps: list[float] = []
            
            for sample in samples:
                # Handle both dict and Pydantic model formats
                if isinstance(sample, dict):
                    # Extract timestamp for time-based display
                    timestamp = float(sample.get("timestamp", 0.0))
                    timestamps.append(timestamp)
                    # Convert bytes/sec to KiB/s
                    download_kib = float(sample.get("download_rate", 0.0)) / 1024.0
                    upload_kib = float(sample.get("upload_rate", 0.0)) / 1024.0
                    download_rates.append(download_kib)
                    upload_rates.append(upload_kib)
                elif hasattr(sample, "timestamp") and hasattr(sample, "download_rate") and hasattr(sample, "upload_rate"):
                    # Handle RateSample Pydantic model objects
                    timestamp = float(getattr(sample, "timestamp", 0.0))
                    timestamps.append(timestamp)
                    download_kib = float(getattr(sample, "download_rate", 0.0)) / 1024.0
                    upload_kib = float(getattr(sample, "upload_rate", 0.0)) / 1024.0
                    download_rates.append(download_kib)
                    upload_rates.append(upload_kib)
                else:
                    logger.warning("UploadDownloadGraphWidget: Unknown sample format: %s", type(sample))
            
            logger.debug("UploadDownloadGraphWidget: Extracted %d download rates, %d upload rates, %d timestamps", 
                         len(download_rates), len(upload_rates), len(timestamps))
            
            # CRITICAL FIX: Always update histories with actual time series data
            # Use the real data even if it's all zeros - Sparklines can render zero data
            # Only use placeholder pattern if we have NO data at all (empty list)
            if download_rates:
                # Keep only the most recent samples (time-ordered) - USE REAL DATA
                self._download_history = download_rates[-self._max_samples :]
                logger.debug("UploadDownloadGraphWidget: Download history updated with %d REAL data points (range: %.2f - %.2f KiB/s)", 
                           len(self._download_history), 
                           min(self._download_history) if self._download_history else 0.0,
                           max(self._download_history) if self._download_history else 0.0)
            else:
                # No data available - only use placeholder if history is empty
                if not self._download_history:
                    # Initialize with VARYING pattern so line is visible (not flat)
                    num_points = min(20, self._max_samples)
                    self._download_history = [0.1 + (i % 2) * 0.1 for i in range(num_points)]
                    logger.debug("UploadDownloadGraphWidget: Initialized download history with placeholder pattern (no data yet)")
            
            if upload_rates:
                # Keep only the most recent samples (time-ordered) - USE REAL DATA
                self._upload_history = upload_rates[-self._max_samples :]
                logger.debug("UploadDownloadGraphWidget: Upload history updated with %d REAL data points (range: %.2f - %.2f KiB/s)", 
                           len(self._upload_history),
                           min(self._upload_history) if self._upload_history else 0.0,
                           max(self._upload_history) if self._upload_history else 0.0)
            else:
                # No data available - only use placeholder if history is empty
                if not self._upload_history:
                    # Initialize with VARYING pattern so line is visible (not flat)
                    num_points = min(20, self._max_samples)
                    self._upload_history = [0.1 + (i % 2) * 0.1 for i in range(num_points)]
                    logger.debug("UploadDownloadGraphWidget: Initialized upload history with placeholder pattern (no data yet)")
            
            # Store timestamps for time-based ordering (Sparkline uses sequential index, but we ensure chronological order)
            self._timestamps = timestamps[-self._max_samples :] if timestamps else []
            
            logger.debug("UploadDownloadGraphWidget: Final histories - download: %d points, upload: %d points, timestamps: %d", 
                        len(self._download_history), len(self._upload_history), len(self._timestamps))
            
            # Update sparklines
            self._update_display()
            # Update event annotations
            self._update_event_annotations()
        except Exception as e:
            logger.error("Error updating upload/download graph from provider: %s", e, exc_info=True)
            # Still update display with existing data or zeros
            if not self._download_history:
                self._download_history = [0.0] * min(10, self._max_samples)
            if not self._upload_history:
                self._upload_history = [0.0] * min(10, self._max_samples)
            self._update_display()
            self._update_event_annotations()

    def _update_display(self) -> None:  # pragma: no cover
        """Update the graph display for UploadDownloadGraphWidget."""
        # CRITICAL FIX: Try to update even if not fully attached yet (for initial render)
        # Only skip if explicitly hidden
        if hasattr(self, "display") and self.display is False:  # type: ignore[attr-defined]
            logger.debug("UploadDownloadGraphWidget: Widget explicitly hidden, skipping display update")
            return
        
        try:
            if self._download_sparkline:
                # CRITICAL FIX: Always set data - use real data even if all zeros
                # Sparklines can render zero data, but need at least some variation to be visible
                if self._download_history and len(self._download_history) > 0:
                    # Ensure data has some variation - if all zeros, add slight variation for visibility
                    data_min = min(self._download_history) if self._download_history else 0.0
                    data_max = max(self._download_history) if self._download_history else 0.0
                    if data_min == data_max == 0.0:
                        # All zeros - add tiny variation so line is visible
                        display_data = [0.0] * len(self._download_history)
                    else:
                        display_data = self._download_history
                    
                    self._download_sparkline.data = display_data  # type: ignore[attr-defined]
                    logger.debug("UploadDownloadGraphWidget: Updated download sparkline with %d data points (range: %.2f - %.2f KiB/s)", 
                              len(display_data), 
                              data_min,
                              data_max)
                else:
                    # No history yet - use placeholder pattern with variation
                    placeholder = [0.1 + (i % 2) * 0.1 for i in range(20)]
                    self._download_sparkline.data = placeholder  # type: ignore[attr-defined]
                    logger.debug("UploadDownloadGraphWidget: Updated download sparkline with placeholder pattern (no data yet)")
                # CRITICAL FIX: Ensure widget is visible and refresh
                self._download_sparkline.display = True  # type: ignore[attr-defined]
                # Force repaint by calling refresh
                if hasattr(self._download_sparkline, "refresh"):
                    self._download_sparkline.refresh()  # type: ignore[attr-defined]
                # Also call update to trigger Textual's update cycle
                if hasattr(self._download_sparkline, "update"):
                    self._download_sparkline.update()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating download sparkline: %s", e, exc_info=True)
        
        try:
            if self._upload_sparkline:
                # CRITICAL FIX: Always set data - use real data even if all zeros
                if self._upload_history and len(self._upload_history) > 0:
                    # Ensure data has some variation - if all zeros, add slight variation for visibility
                    data_min = min(self._upload_history) if self._upload_history else 0.0
                    data_max = max(self._upload_history) if self._upload_history else 0.0
                    if data_min == data_max == 0.0:
                        # All zeros - add tiny variation so line is visible
                        display_data = [0.0] * len(self._upload_history)
                    else:
                        display_data = self._upload_history
                    
                    self._upload_sparkline.data = display_data  # type: ignore[attr-defined]
                    logger.debug("UploadDownloadGraphWidget: Updated upload sparkline with %d data points (range: %.2f - %.2f KiB/s)", 
                              len(display_data),
                              data_min,
                              data_max)
                else:
                    # No history yet - use placeholder pattern with variation
                    placeholder = [0.1 + (i % 2) * 0.1 for i in range(20)]
                    self._upload_sparkline.data = placeholder  # type: ignore[attr-defined]
                    logger.debug("UploadDownloadGraphWidget: Updated upload sparkline with placeholder pattern (no data yet)")
                # CRITICAL FIX: Ensure widget is visible and refresh
                self._upload_sparkline.display = True  # type: ignore[attr-defined]
                # Force repaint by calling refresh
                if hasattr(self._upload_sparkline, "refresh"):
                    self._upload_sparkline.refresh()  # type: ignore[attr-defined]
                # Also call update to trigger Textual's update cycle
                if hasattr(self._upload_sparkline, "update"):
                    self._upload_sparkline.update()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating upload sparkline: %s", e, exc_info=True)
        
        # CRITICAL FIX: Trigger parent widget refresh to ensure repaint
        try:
            self.refresh()  # Refresh parent widget to trigger repaint
        except Exception:
            pass
        
        # Update event annotations
        self._update_event_annotations()
    
    def _add_event_annotation(self, timestamp: float, event_type: str, label: str, info_hash: str | None = None) -> None:
        """Add an event annotation to the timeline.
        
        Args:
            timestamp: Event timestamp (seconds since epoch)
            event_type: Event type string
            label: Human-readable event label
            info_hash: Optional torrent info hash
        """
        self._event_timeline.append({
            "timestamp": timestamp,
            "type": event_type,
            "label": label,
            "info_hash": info_hash,
        })
        # Keep only recent events
        self._event_timeline = self._event_timeline[-self._max_events:]
    
    def _update_event_annotations(self) -> None:
        """Update the event annotations display."""
        if not self._event_annotations_widget:
            return
        
        try:
            import time
            current_time = time.time()
            
            # Filter events within the graph time window (last 120 seconds)
            time_window = 120.0
            recent_events = [
                e for e in self._event_timeline
                if current_time - e["timestamp"] <= time_window
            ]
            
            if not recent_events:
                self._event_annotations_widget.update("")
                return
            
            # Sort by timestamp (oldest first)
            recent_events.sort(key=lambda e: e["timestamp"])
            
            # Create annotation text
            annotation_parts: list[str] = []
            for event in recent_events[-10:]:  # Show last 10 events
                age_seconds = current_time - event["timestamp"]
                if age_seconds < 60:
                    age_str = f"{int(age_seconds)}s ago"
                elif age_seconds < 3600:
                    age_str = f"{int(age_seconds / 60)}m ago"
                else:
                    age_str = f"{int(age_seconds / 3600)}h ago"
                
                # Color code by event type
                if "TRACKER" in event["type"]:
                    color = "cyan"
                elif "PIECE" in event["type"]:
                    color = "green"
                elif "PEER" in event["type"]:
                    color = "yellow"
                else:
                    color = "white"
                
                annotation_parts.append(f"[{color}]{event['label']}[/{color}] ({age_str})")
            
            if annotation_parts:
                annotation_text = " • ".join(annotation_parts)
                self._event_annotations_widget.update(f"[dim]Events:[/dim] {annotation_text}")
            else:
                self._event_annotations_widget.update("")
        except Exception as e:
            logger.debug("Error updating event annotations: %s", e)


class PieceHealthPictogram(Container):  # type: ignore[misc]
    """Render per-piece availability as a colored square pictogram."""

    DEFAULT_CSS = """
    PieceHealthPictogram {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #piece-health-body {
        height: 1fr;
        layout: vertical;
    }
    """

    def __init__(
        self,
        info_hash_hex: str,
        data_provider: DataProvider | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._info_hash = info_hash_hex
        self._data_provider = data_provider
        self._stats: Static | None = None
        self._content: Static | None = None
        self._legend: Static | None = None
        self._update_task: Any | None = None
        self._row_width = 16

    def compose(self) -> Any:  # pragma: no cover
        """Compose the pictogram layout."""
        yield Static("Piece Health", id="piece-health-title")
        with Container(id="piece-health-body"):
            yield Static("Loading piece data…", id="piece-health-stats")
            yield Static("", id="piece-health-content")
            yield Static("", id="piece-health-legend")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Query children and start polling."""
        try:
            self._stats = self.query_one("#piece-health-stats", Static)  # type: ignore[attr-defined]
            self._content = self.query_one("#piece-health-content", Static)  # type: ignore[attr-defined]
            self._legend = self.query_one("#piece-health-legend", Static)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("PieceHealthPictogram: failed to query children: %s", exc)
        self._start_updates()

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Stop refresh loop."""
        if self._update_task:
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:
        """Kick off periodic updates."""
        if not self._data_provider:
            if self._stats:
                self._stats.update("Data provider unavailable")
            return

        import asyncio

        def schedule_update() -> None:
            try:
                asyncio.create_task(self._update_from_provider())
            except Exception as exc:
                logger.debug("PieceHealthPictogram: schedule error: %s", exc)

        try:
            # CRITICAL FIX: Reduced interval from 3.0s to 1.5s for tighter updates
            self._update_task = self.set_interval(1.5, schedule_update)  # type: ignore[attr-defined]
            self.call_after_refresh(schedule_update)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("PieceHealthPictogram: failed to start timer: %s", exc)

    async def _update_from_provider(self) -> None:
        """Fetch piece health payload and update the pictogram."""
        if not self._data_provider or not self._stats or not self._content:
            return

        try:
            data = await self._data_provider.get_piece_health(self._info_hash)
        except Exception as exc:
            logger.debug("PieceHealthPictogram: error fetching piece data: %s", exc)
            data = {}

        availability = data.get("availability", []) or []
        if not availability:
            self._stats.update("No piece availability yet")
            self._content.update("")
            if self._legend:
                self._legend.update("")
            return

        max_peers = max(1, int(data.get("max_peers", 1)))
        total_pieces = len(availability)
        available_pieces = sum(1 for count in availability if count > 0)
        availability_pct = available_pieces / total_pieces * 100 if total_pieces else 0.0
        avg_peers = sum(availability) / total_pieces if total_pieces else 0.0

        stats_text = (
            f"Available pieces: {available_pieces}/{total_pieces} "
            f"({availability_pct:.1f}%) | Avg peers: {avg_peers:.1f} "
            f"| Max peers: {max_peers}"
        )
        self._stats.update(stats_text)

        sampled = self._downsample_availability(availability, max_segments=48)
        rows = math.ceil(len(sampled) / self._row_width)
        pictogram = Text()
        for row in range(rows):
            start = row * self._row_width
            end = start + self._row_width
            row_values = sampled[start:end]
            line = Text()
            for value in row_values:
                ratio = value / max_peers if max_peers else 0.0
                level = determine_piece_health_level(ratio)
                glyph = PIECE_HEALTH_GLYPHS.get(level, "□")
                color = PIECE_HEALTH_COLORS.get(level, "grey46")
                line.append(glyph, style=color)
            pictogram.append(line)
            if row < rows - 1:
                pictogram.append("\n")

        self._content.update(pictogram)

        if self._legend:
            legend = Text(style="dim")
            for level in ("excellent", "healthy", "fragile", "empty"):
                glyph = PIECE_HEALTH_GLYPHS[level]
                color = PIECE_HEALTH_COLORS[level]
                legend.append(glyph, style=color)
                legend.append(f" {PIECE_HEALTH_LABELS[level]}  ", style="dim")
            self._legend.update(legend)

    @staticmethod
    def _downsample_availability(values: list[int], max_segments: int) -> list[int]:
        """Downsample a long availability list to a fixed number of segments."""
        if not values:
            return []
        if len(values) <= max_segments:
            return values

        sampled: list[int] = []
        step = len(values) / max_segments
        for idx in range(max_segments):
            start = int(idx * step)
            end = int((idx + 1) * step)
            if end <= start:
                end = start + 1
            segment = values[start:end]
            sampled.append(int(sum(segment) / len(segment)))
        return sampled

    def update_from_stats(self, stats: dict[str, Any]) -> None:  # pragma: no cover
        """Update graph with statistics (for compatibility with GraphsSectionContainer).
        
        Args:
            stats: Dictionary containing download_rate and upload_rate
        """
        try:
            download_rate = float(stats.get("download_rate", 0.0)) / 1024.0  # Convert to KiB/s
            upload_rate = float(stats.get("upload_rate", 0.0)) / 1024.0  # Convert to KiB/s
            
            self._download_history.append(download_rate)
            self._upload_history.append(upload_rate)
            
            # Keep only last max_samples
            self._download_history = self._download_history[-self._max_samples :]
            self._upload_history = self._upload_history[-self._max_samples :]
            
            # Update display
            self._update_display()
        except Exception as e:
            logger.debug("Error updating upload/download graph from stats: %s", e)


class DiskGraphWidget(BaseGraphWidget):  # type: ignore[misc]
    """Graph widget for disk I/O metrics."""

    DEFAULT_CSS = """
    DiskGraphWidget {
        height: 1fr;
        min-height: 20;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    
    #graph-title {
        height: 1;
        min-height: 1;
        text-style: bold;
        display: block;
    }
    
    #graph-content {
        height: 1fr;
        min-height: 18;
        layout: vertical;
        display: block;
    }
    
    #read-label, #write-label, #cache-label {
        height: 1;
        min-height: 1;
        margin: 0 1;
        display: block;
    }
    
    Sparkline {
        height: 10;
        min-height: 10;
        width: 1fr;
        min-width: 20;
        margin: 1;
        display: block;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize disk graph widget."""
        super().__init__("Disk I/O", data_provider, *args, **kwargs)
        self._read_history: list[float] = []
        self._write_history: list[float] = []
        self._cache_hit_history: list[float] = []
        self._read_sparkline: Sparkline | None = None
        self._write_sparkline: Sparkline | None = None
        self._cache_sparkline: Sparkline | None = None
        self._update_task: Any | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the disk graph widget."""
        yield Static("Disk I/O Metrics", id="graph-title")
        with Vertical(id="graph-content"):
            yield Static("Read Throughput (MB/s):", id="read-label")
            yield Sparkline(id="read-sparkline")
            yield Static("Write Throughput (MB/s):", id="write-label")
            yield Sparkline(id="write-sparkline")
            yield Static("Cache Hit Rate (%):", id="cache-label")
            yield Sparkline(id="cache-sparkline")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the disk graph widget."""
        try:
            self._read_sparkline = self.query_one("#read-sparkline", Sparkline)  # type: ignore[attr-defined]
            self._write_sparkline = self.query_one("#write-sparkline", Sparkline)  # type: ignore[attr-defined]
            self._cache_sparkline = self.query_one("#cache-sparkline", Sparkline)  # type: ignore[attr-defined]
            
            # Initialize with zero data so graphs render immediately
            if self._read_sparkline:
                self._read_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            if self._write_sparkline:
                self._write_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            if self._cache_sparkline:
                self._cache_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            
            # Start periodic updates if data provider is available
            if self._data_provider:
                self._start_updates()
        except Exception as e:
            logger.debug("Error mounting disk graph: %s", e)

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount the widget and stop updates."""
        if self._update_task:
            # set_interval returns a Timer which has stop(), not cancel()
            # Fallback code might create a Task which has cancel()
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:  # pragma: no cover
        """Start periodic updates from data provider."""
        import asyncio
        
        def schedule_update() -> None:
            """Schedule async update (wrapper for set_interval)."""
            try:
                # Create task to run async update
                asyncio.create_task(self._update_from_provider())
            except Exception as e:
                logger.debug("Error scheduling disk graph update: %s", e)
        
        try:
            # CRITICAL FIX: set_interval doesn't work with async functions directly
            # Use wrapper function that creates async task
            # CRITICAL FIX: Reduced interval from 2.0s to 1.0s for tighter performance updates
            self._update_task = self.set_interval(1.0, schedule_update)  # type: ignore[attr-defined]
            # Trigger initial update immediately
            self.call_later(schedule_update)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error starting disk graph update loop: %s", e)

    async def _update_from_provider(self) -> None:  # pragma: no cover
        """Update graph data from data provider."""
        if not self._data_provider:
            logger.debug("DiskGraphWidget: No data provider available")
            # Show zero data if no provider
            self._read_history = [0.0] * min(10, self._max_samples)
            self._write_history = [0.0] * min(10, self._max_samples)
            self._cache_hit_history = [0.0] * min(10, self._max_samples)
            self._update_display()
            return
        
        try:
            # Fetch disk I/O metrics
            # CRITICAL FIX: Use shorter timeout for UI responsiveness
            try:
                metrics = await asyncio.wait_for(
                    self._data_provider.get_disk_io_metrics(),
                    timeout=10.0  # 10 second timeout for UI responsiveness (increased from 5.0)
                )
            except asyncio.TimeoutError:
                logger.debug("DiskGraphWidget: Metrics fetch timed out, using cached/existing data")
                return
            except Exception as e:
                logger.debug("DiskGraphWidget: Error fetching disk I/O metrics (will retry next cycle): %s", e)
                return
            
            if not metrics:
                logger.debug("DiskGraphWidget: No disk I/O metrics returned from provider")
                # Show zero data if no metrics
                if not self._read_history:
                    self._read_history = [0.0] * min(10, self._max_samples)
                if not self._write_history:
                    self._write_history = [0.0] * min(10, self._max_samples)
                if not self._cache_hit_history:
                    self._cache_hit_history = [0.0] * min(10, self._max_samples)
                self._update_display()
                return
            
            # Extract metrics (already in correct units from get_disk_io_metrics)
            read_throughput_mb = metrics.get("read_throughput", 0.0) / 1024.0  # Convert KiB/s to MB/s
            write_throughput_mb = metrics.get("write_throughput", 0.0) / 1024.0  # Convert KiB/s to MB/s
            cache_hit_rate = metrics.get("cache_hit_rate", 0.0)  # Already in percentage
            
            # Update histories
            self._read_history.append(read_throughput_mb)
            self._write_history.append(write_throughput_mb)
            self._cache_hit_history.append(cache_hit_rate)
            
            # Keep only last max_samples
            self._read_history = self._read_history[-self._max_samples :]
            self._write_history = self._write_history[-self._max_samples :]
            self._cache_hit_history = self._cache_hit_history[-self._max_samples :]
            
            # Ensure we have at least some data for display
            if not self._read_history:
                self._read_history = [0.0] * min(10, self._max_samples)
            if not self._write_history:
                self._write_history = [0.0] * min(10, self._max_samples)
            if not self._cache_hit_history:
                self._cache_hit_history = [0.0] * min(10, self._max_samples)
            
            # Update sparklines
            self._update_display()
        except Exception as e:
            logger.error("Error updating disk graph from provider: %s", e, exc_info=True)
            # Still update display with existing data or zeros
            if not self._read_history:
                self._read_history = [0.0] * min(10, self._max_samples)
            if not self._write_history:
                self._write_history = [0.0] * min(10, self._max_samples)
            if not self._cache_hit_history:
                self._cache_hit_history = [0.0] * min(10, self._max_samples)
            self._update_display()

    def _update_display(self) -> None:  # pragma: no cover
        """Update the graph display."""
        try:
            if self._read_sparkline:
                if self._read_history:
                    self._read_sparkline.data = self._read_history  # type: ignore[attr-defined]
                else:
                    self._read_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                if hasattr(self._read_sparkline, "refresh"):
                    self._read_sparkline.refresh()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating read sparkline: %s", e, exc_info=True)
        try:
            if self._write_sparkline:
                if self._write_history:
                    self._write_sparkline.data = self._write_history  # type: ignore[attr-defined]
                else:
                    self._write_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                if hasattr(self._write_sparkline, "refresh"):
                    self._write_sparkline.refresh()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating write sparkline: %s", e, exc_info=True)
        try:
            if self._cache_sparkline:
                if self._cache_hit_history:
                    self._cache_sparkline.data = self._cache_hit_history  # type: ignore[attr-defined]
                else:
                    self._cache_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                if hasattr(self._cache_sparkline, "refresh"):
                    self._cache_sparkline.refresh()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating cache sparkline: %s", e, exc_info=True)


class NetworkGraphWidget(BaseGraphWidget):  # type: ignore[misc]
    """Graph widget for network timing metrics."""

    DEFAULT_CSS = """
    NetworkGraphWidget {
        height: 1fr;
        min-height: 20;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    
    #graph-title {
        height: 1;
        min-height: 1;
        text-style: bold;
        display: block;
    }
    
    #graph-content {
        height: 1fr;
        min-height: 18;
        layout: vertical;
        display: block;
    }
    
    #utp-label, #overhead-label {
        height: 1;
        min-height: 1;
        margin: 0 1;
        display: block;
    }
    
    Sparkline {
        height: 10;
        min-height: 10;
        width: 1fr;
        min-width: 20;
        margin: 1;
        display: block;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize network graph widget."""
        super().__init__("Network Timing", data_provider, *args, **kwargs)
        self._utp_delay_history: list[float] = []
        self._overhead_history: list[float] = []
        self._utp_sparkline: Sparkline | None = None
        self._overhead_sparkline: Sparkline | None = None
        self._update_task: Any | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the network graph widget."""
        yield Static("Network Timing Metrics", id="graph-title")
        with Vertical(id="graph-content"):
            yield Static("uTP Delay (ms):", id="utp-label")
            yield Sparkline(id="utp-sparkline")
            yield Static("Network Overhead (KiB/s):", id="overhead-label")
            yield Sparkline(id="overhead-sparkline")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the network graph widget."""
        try:
            self._utp_sparkline = self.query_one("#utp-sparkline", Sparkline)  # type: ignore[attr-defined]
            self._overhead_sparkline = self.query_one("#overhead-sparkline", Sparkline)  # type: ignore[attr-defined]
            
            # Initialize with zero data so graphs render immediately
            if self._utp_sparkline:
                self._utp_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            if self._overhead_sparkline:
                self._overhead_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            
            # Start periodic updates if data provider is available
            if self._data_provider:
                self._start_updates()
        except Exception as e:
            logger.debug("Error mounting network graph: %s", e)

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount the widget and stop updates."""
        if self._update_task:
            # set_interval returns a Timer which has stop(), not cancel()
            # Fallback code might create a Task which has cancel()
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:  # pragma: no cover
        """Start periodic updates from data provider."""
        import asyncio
        
        def schedule_update() -> None:
            """Schedule async update (wrapper for set_interval)."""
            try:
                # Create task to run async update
                asyncio.create_task(self._update_from_provider())
            except Exception as e:
                logger.debug("Error scheduling network graph update: %s", e)
        
        try:
            # CRITICAL FIX: set_interval doesn't work with async functions directly
            # Use wrapper function that creates async task
            # CRITICAL FIX: Reduced interval from 2.0s to 1.0s for tighter performance updates
            self._update_task = self.set_interval(1.0, schedule_update)  # type: ignore[attr-defined]
            # Trigger initial update immediately
            self.call_later(schedule_update)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error starting network graph update loop: %s", e)

    async def _update_from_provider(self) -> None:  # pragma: no cover
        """Update graph data from data provider."""
        if not self._data_provider:
            logger.debug("NetworkGraphWidget: No data provider available")
            # Show zero data if no provider
            if not self._utp_delay_history:
                self._utp_delay_history = [0.0] * min(10, self._max_samples)
            if not self._overhead_history:
                self._overhead_history = [0.0] * min(10, self._max_samples)
            self._update_display()
            return
        
        try:
            # Fetch network timing metrics
            # CRITICAL FIX: Use shorter timeout for UI responsiveness
            try:
                metrics = await asyncio.wait_for(
                    self._data_provider.get_network_timing_metrics(),
                    timeout=10.0  # 10 second timeout for UI responsiveness (increased from 5.0)
                )
            except asyncio.TimeoutError:
                logger.debug("NetworkGraphWidget: Metrics fetch timed out, using cached/existing data")
                return
            except Exception as e:
                logger.debug("NetworkGraphWidget: Error fetching network timing metrics (will retry next cycle): %s", e)
                return
            
            if not metrics:
                logger.debug("NetworkGraphWidget: No network timing metrics returned from provider")
                # Show zero data if no metrics
                if not self._utp_delay_history:
                    self._utp_delay_history = [0.0] * min(10, self._max_samples)
                if not self._overhead_history:
                    self._overhead_history = [0.0] * min(10, self._max_samples)
                self._update_display()
                return
            
            # Extract metrics (already in correct units)
            utp_delay_ms = metrics.get("utp_delay_ms", 0.0)
            overhead_kib = metrics.get("network_overhead_rate", 0.0)
            
            # Update histories
            self._utp_delay_history.append(utp_delay_ms)
            self._overhead_history.append(overhead_kib)
            
            # Keep only last max_samples
            self._utp_delay_history = self._utp_delay_history[-self._max_samples :]
            self._overhead_history = self._overhead_history[-self._max_samples :]
            
            # Update sparklines
            self._update_display()
        except Exception as e:
            logger.error("Error updating network graph from provider: %s", e, exc_info=True)
            # Still update display with existing data or zeros
            if not self._utp_delay_history:
                self._utp_delay_history = [0.0] * min(10, self._max_samples)
            if not self._overhead_history:
                self._overhead_history = [0.0] * min(10, self._max_samples)
            self._update_display()
            # Show zero data on error
            if not self._utp_delay_history:
                self._utp_delay_history = [0.0] * min(10, self._max_samples)
            if not self._overhead_history:
                self._overhead_history = [0.0] * min(10, self._max_samples)
            self._update_display()

    def _update_display(self) -> None:  # pragma: no cover
        """Update the graph display."""
        try:
            if self._utp_sparkline:
                if self._utp_delay_history:
                    self._utp_sparkline.data = self._utp_delay_history  # type: ignore[attr-defined]
                else:
                    self._utp_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                if hasattr(self._utp_sparkline, "refresh"):
                    self._utp_sparkline.refresh()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating uTP sparkline: %s", e, exc_info=True)
        try:
            if self._overhead_sparkline:
                if self._overhead_history:
                    self._overhead_sparkline.data = self._overhead_history  # type: ignore[attr-defined]
                else:
                    self._overhead_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                if hasattr(self._overhead_sparkline, "refresh"):
                    self._overhead_sparkline.refresh()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating overhead sparkline: %s", e, exc_info=True)


class DownloadGraphWidget(BaseGraphWidget):  # type: ignore[misc]
    """Graph widget for download speed only."""

    def __init__(
        self,
        data_provider: DataProvider | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize download graph widget."""
        super().__init__("Download Speed", data_provider, *args, **kwargs)
        self._download_history: list[float] = []
        self._update_task: Any | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the download graph widget."""
        yield Static("Download Speed (KiB/s)", id="graph-title")
        with Container(id="graph-content"):
            yield Sparkline(id="graph-sparkline")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the download graph widget."""
        try:
            self._sparkline = self.query_one("#graph-sparkline", Sparkline)  # type: ignore[attr-defined]
            
            # Start periodic updates if data provider is available
            if self._data_provider:
                self._start_updates()
        except Exception as e:
            logger.debug("Error mounting download graph: %s", e)

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount the widget and stop updates."""
        if self._update_task:
            # set_interval returns a Timer which has stop(), not cancel()
            # Fallback code might create a Task which has cancel()
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:  # pragma: no cover
        """Start periodic updates from data provider."""
        import asyncio
        
        def schedule_update() -> None:
            """Schedule async update (wrapper for set_interval)."""
            try:
                # Create task to run async update
                asyncio.create_task(self._update_from_provider())
            except Exception as e:
                logger.debug("Error scheduling download graph update: %s", e)
        
        try:
            # CRITICAL FIX: set_interval doesn't work with async functions directly
            # Use wrapper function that creates async task
            self._update_task = self.set_interval(1.0, schedule_update)  # type: ignore[attr-defined]
            # Trigger initial update immediately
            self.call_later(schedule_update)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error starting download graph update loop: %s", e)

    async def _update_from_provider(self) -> None:  # pragma: no cover
        """Update graph data from data provider."""
        if not self._data_provider:
            logger.debug("DownloadGraphWidget: No data provider available")
            # Show zero data if no provider
            if not self._download_history:
                self._download_history = [0.0] * min(10, self._max_samples)
            self._update_display()
            return
        
        try:
            # Fetch rate samples
            # CRITICAL FIX: Use shorter timeout for UI responsiveness
            try:
                samples = await asyncio.wait_for(
                    self._data_provider.get_rate_samples(seconds=120),
                    timeout=10.0  # 10 second timeout for UI responsiveness (increased from 5.0)
                )
            except asyncio.TimeoutError:
                logger.debug("DownloadGraphWidget: Metrics fetch timed out, using cached/existing data")
                return
            except Exception as e:
                logger.debug("DownloadGraphWidget: Error fetching rate samples (will retry next cycle): %s", e)
                return
            
            if not samples:
                logger.debug("DownloadGraphWidget: No rate samples returned from provider")
                # Show zero data if no samples
                if not self._download_history:
                    self._download_history = [0.0] * min(10, self._max_samples)
                self._update_display()
                return
            
            # Extract download rates
            download_rates: list[float] = []
            for sample in samples:
                if isinstance(sample, dict):
                    # Convert bytes/sec to KiB/s
                    download_kib = sample.get("download_rate", 0.0) / 1024.0
                    download_rates.append(download_kib)
            
            # Update history
            if download_rates:
                self._download_history = download_rates[-self._max_samples :]
            else:
                # Initialize with zeros if no data
                self._download_history = [0.0] * min(10, self._max_samples)
            
            # Update sparkline
            self._update_display()
        except Exception as e:
            logger.error("Error updating download graph from provider: %s", e, exc_info=True)
            # Show zero data on error
            if not self._download_history:
                self._download_history = [0.0] * min(10, self._max_samples)
            self._update_display()

    def _update_display(self) -> None:  # pragma: no cover
        """Update the graph display."""
        try:
            if self._sparkline:
                if self._download_history:
                    self._sparkline.data = self._download_history  # type: ignore[attr-defined]
                else:
                    self._sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                if hasattr(self._sparkline, "refresh"):
                    self._sparkline.refresh()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating download sparkline: %s", e, exc_info=True)


class UploadGraphWidget(BaseGraphWidget):  # type: ignore[misc]
    """Graph widget for upload speed only."""

    def __init__(
        self,
        data_provider: DataProvider | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize upload graph widget."""
        super().__init__("Upload Speed", data_provider, *args, **kwargs)
        self._upload_history: list[float] = []
        self._update_task: Any | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the upload graph widget."""
        yield Static("Upload Speed (KiB/s)", id="graph-title")
        with Container(id="graph-content"):
            yield Sparkline(id="graph-sparkline")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the upload graph widget."""
        try:
            self._sparkline = self.query_one("#graph-sparkline", Sparkline)  # type: ignore[attr-defined]
            
            # Start periodic updates if data provider is available
            if self._data_provider:
                self._start_updates()
        except Exception as e:
            logger.debug("Error mounting upload graph: %s", e)

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount the widget and stop updates."""
        if self._update_task:
            # set_interval returns a Timer which has stop(), not cancel()
            # Fallback code might create a Task which has cancel()
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:  # pragma: no cover
        """Start periodic updates from data provider."""
        import asyncio
        
        def schedule_update() -> None:
            """Schedule async update (wrapper for set_interval)."""
            try:
                # Create task to run async update
                asyncio.create_task(self._update_from_provider())
            except Exception as e:
                logger.debug("Error scheduling upload graph update: %s", e)
        
        try:
            # CRITICAL FIX: set_interval doesn't work with async functions directly
            # Use wrapper function that creates async task
            self._update_task = self.set_interval(1.0, schedule_update)  # type: ignore[attr-defined]
            # Trigger initial update immediately
            self.call_later(schedule_update)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error starting upload graph update loop: %s", e)

    async def _update_from_provider(self) -> None:  # pragma: no cover
        """Update graph data from data provider."""
        if not self._data_provider:
            logger.debug("UploadGraphWidget: No data provider available")
            # Show zero data if no provider
            if not self._upload_history:
                self._upload_history = [0.0] * min(10, self._max_samples)
            self._update_display()
            return
        
        try:
            # Fetch rate samples
            # CRITICAL FIX: Use shorter timeout for UI responsiveness
            try:
                samples = await asyncio.wait_for(
                    self._data_provider.get_rate_samples(seconds=120),
                    timeout=10.0  # 10 second timeout for UI responsiveness (increased from 5.0)
                )
            except asyncio.TimeoutError:
                logger.debug("UploadGraphWidget: Metrics fetch timed out, using cached/existing data")
                return
            except Exception as e:
                logger.debug("UploadGraphWidget: Error fetching rate samples (will retry next cycle): %s", e)
                return
            
            if not samples:
                logger.debug("UploadGraphWidget: No rate samples returned from provider")
                # Show zero data if no samples
                if not self._upload_history:
                    self._upload_history = [0.0] * min(10, self._max_samples)
                self._update_display()
                return
            
            # Extract upload rates
            upload_rates: list[float] = []
            for sample in samples:
                if isinstance(sample, dict):
                    # Convert bytes/sec to KiB/s
                    upload_kib = sample.get("upload_rate", 0.0) / 1024.0
                    upload_rates.append(upload_kib)
            
            # Update history
            if upload_rates:
                self._upload_history = upload_rates[-self._max_samples :]
            else:
                # Initialize with zeros if no data
                self._upload_history = [0.0] * min(10, self._max_samples)
            
            # Update sparkline
            self._update_display()
        except Exception as e:
            logger.error("Error updating upload graph from provider: %s", e, exc_info=True)
            # Show zero data on error
            if not self._upload_history:
                self._upload_history = [0.0] * min(10, self._max_samples)
            self._update_display()

    def _update_display(self) -> None:  # pragma: no cover
        """Update the graph display."""
        try:
            if self._sparkline:
                if self._upload_history:
                    self._sparkline.data = self._upload_history  # type: ignore[attr-defined]
                else:
                    self._sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                if hasattr(self._sparkline, "refresh"):
                    self._sparkline.refresh()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating upload sparkline: %s", e, exc_info=True)


class PerTorrentGraphWidget(Container):  # type: ignore[misc]
    """Graph widget for per-torrent performance monitoring with peer metrics."""

    DEFAULT_CSS = """
    PerTorrentGraphWidget {
        height: 1fr;
        layout: vertical;
    }
    #title {
        height: 3;
        margin: 1;
        text-align: center;
    }
    #graphs-section {
        height: 2fr;
        layout: horizontal;
    }
    #speed-graphs {
        width: 1fr;
        layout: vertical;
    }
    #peer-performance {
        width: 1fr;
        layout: vertical;
    }
    #metrics-section {
        height: 1fr;
        layout: horizontal;
    }
    #metrics-left, #metrics-right {
        width: 1fr;
        layout: vertical;
    }
    #health-section {
        height: 1fr;
        layout: horizontal;
        min-height: 12;
        gap: 1;
    }
    #health-section > * {
        width: 1fr;
    }
    Static {
        height: 1;
        margin: 0 1;
    }
    Sparkline {
        height: 5;
        margin: 1;
    }
    DataTable {
        height: 1fr;
        margin: 1;
    }
    """

    def __init__(
        self,
        info_hash_hex: str,
        data_provider: DataProvider | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize per-torrent graph widget.

        Args:
            info_hash_hex: Torrent info hash in hex format
            data_provider: Optional DataProvider for fetching metrics
        """
        super().__init__(*args, **kwargs)
        self.info_hash_hex = info_hash_hex
        self._data_provider = data_provider
        self._download_history: list[float] = []
        self._upload_history: list[float] = []
        self._piece_rate_history: list[float] = []
        self._download_sparkline: Sparkline | None = None
        self._upload_sparkline: Sparkline | None = None
        self._piece_rate_sparkline: Sparkline | None = None
        self._peer_table: DataTable | None = None
        self._update_task: Any | None = None
        self._max_samples = 120

    def compose(self) -> Any:  # pragma: no cover
        """Compose the per-torrent graph widget."""
        yield Static(f"Torrent Performance: {self.info_hash_hex[:16]}...", id="title")
        
        with Container(id="graphs-section"):
            with Container(id="speed-graphs"):
                yield Static("Download Speed (KiB/s):", id="download-label")
                yield Sparkline(id="download-sparkline")
                yield Static("Upload Speed (KiB/s):", id="upload-label")
                yield Sparkline(id="upload-sparkline")
                yield Static("Piece Download Rate (pieces/s):", id="piece-rate-label")
                yield Sparkline(id="piece-rate-sparkline")
            
            with Container(id="peer-performance"):
                yield Static("Top Performing Peers", id="peer-label")
                yield DataTable(id="peer-table", zebra_stripes=True)
        
        with Container(id="metrics-section"):
            with Container(id="metrics-left"):
                yield Static("Progress:", id="progress-label")
                yield Static("0.0%", id="progress-value")
                yield Static("Pieces:", id="pieces-label")
                yield Static("0/0", id="pieces-value")
                yield Static("Swarm Availability:", id="availability-label")
                yield Static("0.0%", id="availability-value")
            
            with Container(id="metrics-right"):
                yield Static("Connected Peers:", id="peers-label")
                yield Static("0", id="peers-value")
                yield Static("Active Peers:", id="active-label")
                yield Static("0", id="active-value")
                yield Static("Bytes Downloaded:", id="downloaded-label")
                yield Static("0 B", id="downloaded-value")

        with Container(id="health-section"):
            yield SwarmHealthDotPlot(
                data_provider=self._data_provider,
                info_hash_hex=self.info_hash_hex,
                max_rows=1,
                id="per-torrent-swarm-health",
            )
            yield PieceHealthPictogram(
                self.info_hash_hex,
                self._data_provider,
                id="piece-health-pictogram",
            )

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the widget and start updates."""
        try:
            self._download_sparkline = self.query_one("#download-sparkline", Sparkline)  # type: ignore[attr-defined]
            self._upload_sparkline = self.query_one("#upload-sparkline", Sparkline)  # type: ignore[attr-defined]
            self._piece_rate_sparkline = self.query_one("#piece-rate-sparkline", Sparkline)  # type: ignore[attr-defined]
            self._peer_table = self.query_one("#peer-table", DataTable)  # type: ignore[attr-defined]
            
            # Initialize sparklines with zero data so they render immediately
            if self._download_sparkline:
                self._download_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            if self._upload_sparkline:
                self._upload_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            if self._piece_rate_sparkline:
                self._piece_rate_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            
            if self._peer_table:
                self._peer_table.add_columns(
                    "Peer",
                    "Download (KiB/s)",
                    "Upload (KiB/s)",
                    "Latency (ms)",
                    "Pieces",
                )
            
            if self._data_provider:
                self._start_updates()
                # Register nested widgets for event-driven updates
                try:
                    swarm_widget = self.query_one("#per-torrent-swarm-health", SwarmHealthDotPlot)  # type: ignore[attr-defined]
                    if swarm_widget:
                        self._register_nested_widget(swarm_widget)
                    piece_widget = self.query_one("#piece-health-pictogram", PieceHealthPictogram)  # type: ignore[attr-defined]
                    if piece_widget:
                        self._register_nested_widget(piece_widget)
                except Exception as e:
                    logger.debug("Error registering nested widgets in PerTorrentGraphWidget: %s", e)
        except Exception as e:
            logger.debug("Error mounting per-torrent graph: %s", e)
    
    def _register_nested_widget(self, widget: Any) -> None:
        """Register a nested widget with the adapter for event-driven updates.
        
        Args:
            widget: Nested widget instance to register
        """
        try:
            if self._data_provider and hasattr(self._data_provider, "get_adapter"):
                adapter = self._data_provider.get_adapter()
                if adapter and hasattr(adapter, "register_widget"):
                    adapter.register_widget(widget)
                    logger.debug("Registered nested widget %s for event-driven updates", type(widget).__name__)
        except Exception as e:
            logger.debug("Error registering nested widget: %s", e)

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount and stop updates."""
        if self._update_task:
            # set_interval returns a Timer which has stop(), not cancel()
            # Fallback code might create a Task which has cancel()
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:  # pragma: no cover
        """Start periodic updates."""
        import asyncio
        
        def schedule_update() -> None:
            """Schedule async update (wrapper for set_interval)."""
            try:
                # Create task to run async update
                asyncio.create_task(self._update_from_provider())
            except Exception as e:
                logger.debug("Error scheduling per-torrent graph update: %s", e)
        
        try:
            # CRITICAL FIX: set_interval doesn't work with async functions directly
            # Use wrapper function that creates async task
            # CRITICAL FIX: Reduced interval from 2.0s to 1.0s for tighter performance updates
            self._update_task = self.set_interval(1.0, schedule_update)  # type: ignore[attr-defined]
            # Trigger initial update immediately
            self.call_later(schedule_update)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error starting per-torrent graph update loop: %s", e)

    async def _update_from_provider(self) -> None:  # pragma: no cover
        """Update graph data from data provider."""
        if not self._data_provider:
            return

        try:
            # Fetch per-torrent performance metrics
            metrics = await self._data_provider.get_per_torrent_performance(self.info_hash_hex)
            
            if not metrics:
                return

            # Update speed histories
            download_rate_kib = metrics.get("download_rate", 0.0) / 1024.0
            upload_rate_kib = metrics.get("upload_rate", 0.0) / 1024.0
            piece_rate = metrics.get("piece_download_rate", 0.0)
            
            self._download_history.append(download_rate_kib)
            self._upload_history.append(upload_rate_kib)
            self._piece_rate_history.append(piece_rate)
            
            # Keep only last max_samples
            self._download_history = self._download_history[-self._max_samples :]
            self._upload_history = self._upload_history[-self._max_samples :]
            self._piece_rate_history = self._piece_rate_history[-self._max_samples :]
            
            # Update sparklines
            try:
                if self._download_sparkline:
                    if self._download_history:
                        self._download_sparkline.data = self._download_history  # type: ignore[attr-defined]
                    else:
                        self._download_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                    # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                    if hasattr(self._download_sparkline, "refresh"):
                        self._download_sparkline.refresh()  # type: ignore[attr-defined]
            except Exception as e:
                logger.error("Error updating download sparkline: %s", e, exc_info=True)
            try:
                if self._upload_sparkline:
                    if self._upload_history:
                        self._upload_sparkline.data = self._upload_history  # type: ignore[attr-defined]
                    else:
                        self._upload_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                    # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                    if hasattr(self._upload_sparkline, "refresh"):
                        self._upload_sparkline.refresh()  # type: ignore[attr-defined]
            except Exception as e:
                logger.error("Error updating upload sparkline: %s", e, exc_info=True)
            try:
                if self._piece_rate_sparkline:
                    if self._piece_rate_history:
                        self._piece_rate_sparkline.data = self._piece_rate_history  # type: ignore[attr-defined]
                    else:
                        self._piece_rate_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                    # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                    if hasattr(self._piece_rate_sparkline, "refresh"):
                        self._piece_rate_sparkline.refresh()  # type: ignore[attr-defined]
                    else:
                        self._piece_rate_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            except Exception as e:
                logger.debug("Error updating piece rate sparkline: %s", e)
            
            # Update metrics display
            progress = metrics.get("progress", 0.0) * 100.0
            pieces_completed = metrics.get("pieces_completed", 0)
            pieces_total = metrics.get("pieces_total", 0)
            swarm_availability = metrics.get("swarm_availability", 0.0) * 100.0
            connected_peers = metrics.get("connected_peers", 0)
            active_peers = metrics.get("active_peers", 0)
            bytes_downloaded = metrics.get("bytes_downloaded", 0)
            
            # Format bytes
            if bytes_downloaded > 1024 * 1024 * 1024:
                downloaded_str = f"{bytes_downloaded / (1024 * 1024 * 1024):.2f} GB"
            elif bytes_downloaded > 1024 * 1024:
                downloaded_str = f"{bytes_downloaded / (1024 * 1024):.2f} MB"
            elif bytes_downloaded > 1024:
                downloaded_str = f"{bytes_downloaded / 1024:.2f} KB"
            else:
                downloaded_str = f"{bytes_downloaded} B"
            
            # Update static widgets
            try:
                self.query_one("#progress-value", Static).update(f"{progress:.1f}%")  # type: ignore[attr-defined]
                self.query_one("#pieces-value", Static).update(f"{pieces_completed}/{pieces_total}")  # type: ignore[attr-defined]
                self.query_one("#availability-value", Static).update(f"{swarm_availability:.1f}%")  # type: ignore[attr-defined]
                self.query_one("#peers-value", Static).update(str(connected_peers))  # type: ignore[attr-defined]
                self.query_one("#active-value", Static).update(str(active_peers))  # type: ignore[attr-defined]
                self.query_one("#downloaded-value", Static).update(downloaded_str)  # type: ignore[attr-defined]
            except Exception as e:
                logger.debug("Error updating metrics display: %s", e)
            
            # Update peer table
            if self._peer_table:
                self._peer_table.clear()
                top_peers = metrics.get("top_peers", [])
                for peer in top_peers[:10]:  # Top 10 peers
                    peer_key = peer.get("peer_key", "unknown")
                    download_kib = peer.get("download_rate", 0.0) / 1024.0
                    upload_kib = peer.get("upload_rate", 0.0) / 1024.0
                    latency_ms = peer.get("request_latency", 0.0) * 1000.0
                    pieces_received = peer.get("pieces_received", 0)
                    
                    self._peer_table.add_row(
                        peer_key,
                        f"{download_kib:.1f}",
                        f"{upload_kib:.1f}",
                        f"{latency_ms:.1f}",
                        str(pieces_received),
                        key=peer_key,
                    )
        except Exception as e:
            logger.debug("Error updating per-torrent graph from provider: %s", e)

    def _update_display(self) -> None:  # pragma: no cover
        """Update the graph display."""
        try:
            if self._download_sparkline:
                if self._download_history:
                    self._download_sparkline.data = self._download_history  # type: ignore[attr-defined]
                else:
                    self._download_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                if hasattr(self._download_sparkline, "refresh"):
                    self._download_sparkline.refresh()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating download sparkline: %s", e, exc_info=True)
        try:
            if self._upload_sparkline:
                if self._upload_history:
                    self._upload_sparkline.data = self._upload_history  # type: ignore[attr-defined]
                else:
                    self._upload_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
                # CRITICAL FIX: Force refresh to ensure Sparkline repaints
                if hasattr(self._upload_sparkline, "refresh"):
                    self._upload_sparkline.refresh()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating upload sparkline: %s", e, exc_info=True)

    def update_from_stats(self, stats: dict[str, Any]) -> None:  # pragma: no cover
        """Update graph with statistics (legacy method for backward compatibility).

        Args:
            stats: Dictionary containing download_rate and upload_rate
        """
        download_rate = float(stats.get("download_rate", 0.0)) / 1024.0  # Convert to KiB/s
        upload_rate = float(stats.get("upload_rate", 0.0)) / 1024.0  # Convert to KiB/s
        
        self._download_history.append(download_rate)
        self._upload_history.append(upload_rate)
        
        # Keep only last max_samples
        self._download_history = self._download_history[-self._max_samples :]
        self._upload_history = self._upload_history[-self._max_samples :]
        
        # Update sparklines
        self._update_display()


class PerformanceGraphWidget(Container):  # type: ignore[misc]
    """Performance graph widget showing upload/download speeds only."""

    DEFAULT_CSS = """
    PerformanceGraphWidget {
        height: 1fr;
        min-height: 20;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    #upload-download-section {
        height: 1fr;
        min-height: 18;
        layout: vertical;
        padding: 0 1;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    #ud-graph-container {
        height: 1fr;
        min-height: 16;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    Static {
        height: auto;
        min-height: 1;
        margin: 0 1;
        display: block;
    }
    Sparkline {
        height: 10;
        min-height: 10;
        width: 1fr;
        min-width: 20;
        margin: 1;
        display: block;
        border: solid $primary;
        background: $surface;
    }
    #ud-title {
        height: 1;
        min-height: 1;
        text-style: bold;
        display: block;
    }
    #graph-content {
        height: 1fr;
        min-height: 18;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize performance graph widget (upload/download only)."""
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._upload_download_widget: UploadDownloadGraphWidget | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the performance graph widget.
        
        CRITICAL FIX: Don't create widgets in compose() - just yield placeholders.
        Widgets will be created in on_mount() to avoid blocking compose().
        """
        with Container(id="upload-download-section"):
            yield Static("Upload & Download Speed", id="ud-title")
            # CRITICAL FIX: Don't create widget here - just yield a placeholder container
            # The actual widget will be created in on_mount() to avoid blocking
            with Container(id="ud-graph-container"):
                yield Static("Loading graph...", id="ud-graph-placeholder")
    
    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the performance graph widget.
        
        CRITICAL FIX: Create the UploadDownloadGraphWidget here instead of in compose()
        to avoid blocking compose() and causing pending callback warnings.
        """
        logger.debug("PerformanceGraphWidget.on_mount: Starting mount (data_provider=%s)", self._data_provider is not None)
        try:
            # CRITICAL FIX: Ensure widget is visible
            self.display = True  # type: ignore[attr-defined]
            
            # CRITICAL FIX: Create widget in on_mount() instead of compose()
            if self._data_provider:
                # Try to create widget immediately, with fallback to call_after_refresh
                try:
                    # Find the container where we'll mount the widget
                    container = self.query_one("#ud-graph-container", Container)  # type: ignore[attr-defined]
                    if container:
                        logger.debug("PerformanceGraphWidget: Found container, creating UploadDownloadGraphWidget")
                        # Remove placeholder
                        try:
                            placeholder = self.query_one("#ud-graph-placeholder", Static)  # type: ignore[attr-defined]
                            if placeholder:
                                placeholder.remove()  # type: ignore[attr-defined]
                        except Exception as e:
                            logger.debug("PerformanceGraphWidget: Placeholder not found or already removed: %s", e)
                        
                        # Create and mount the actual widget
                        from ccbt.interface.widgets.graph_widget import UploadDownloadGraphWidget
                        self._upload_download_widget = UploadDownloadGraphWidget(
                            data_provider=self._data_provider,
                            id="ud-graph"
                        )
                        container.mount(self._upload_download_widget)  # type: ignore[attr-defined]
                        self._upload_download_widget.display = True  # type: ignore[attr-defined]
                        # Ensure container is visible
                        container.display = True  # type: ignore[attr-defined]
                        # Register nested widget for event-driven updates
                        self._register_nested_widget(self._upload_download_widget)
                        logger.debug("PerformanceGraphWidget: UploadDownloadGraphWidget created and mounted successfully")
                        # CRITICAL FIX: Schedule an update after widget is fully attached
                        def ensure_widget_initialized() -> None:
                            try:
                                if self._upload_download_widget:
                                    # Force refresh to ensure Sparklines render
                                    self._upload_download_widget.refresh()  # type: ignore[attr-defined]
                                    # Trigger initial data fetch
                                    import asyncio
                                    asyncio.create_task(self._upload_download_widget._update_from_provider())  # type: ignore[attr-defined]
                            except Exception as e:
                                logger.debug("Error ensuring widget initialization: %s", e)
                        self.call_after_refresh(ensure_widget_initialized)  # type: ignore[attr-defined]
                    else:
                        logger.warning("PerformanceGraphWidget: Could not find #ud-graph-container, will retry after refresh")
                        # Fallback: schedule creation after refresh
                        def create_graph_widget() -> None:
                            try:
                                container = self.query_one("#ud-graph-container", Container)  # type: ignore[attr-defined]
                                if container:
                                    try:
                                        placeholder = self.query_one("#ud-graph-placeholder", Static)  # type: ignore[attr-defined]
                                        if placeholder:
                                            placeholder.remove()  # type: ignore[attr-defined]
                                    except Exception:
                                        pass
                                    from ccbt.interface.widgets.graph_widget import UploadDownloadGraphWidget
                                    self._upload_download_widget = UploadDownloadGraphWidget(
                                        data_provider=self._data_provider,
                                        id="ud-graph"
                                    )
                                    container.mount(self._upload_download_widget)  # type: ignore[attr-defined]
                                    self._upload_download_widget.display = True  # type: ignore[attr-defined]
                                    container.display = True  # type: ignore[attr-defined]
                                    # Register nested widget for event-driven updates
                                    self._register_nested_widget(self._upload_download_widget)
                                    logger.debug("PerformanceGraphWidget: UploadDownloadGraphWidget created after refresh")
                                    # CRITICAL FIX: Schedule an update after widget is fully attached
                                    def ensure_widget_initialized() -> None:
                                        try:
                                            if self._upload_download_widget:
                                                # Force refresh to ensure Sparklines render
                                                self._upload_download_widget.refresh()  # type: ignore[attr-defined]
                                                # Trigger initial data fetch
                                                import asyncio
                                                asyncio.create_task(self._upload_download_widget._update_from_provider())  # type: ignore[attr-defined]
                                        except Exception as e:
                                            logger.debug("Error ensuring widget initialization: %s", e)
                                    self.call_after_refresh(ensure_widget_initialized)  # type: ignore[attr-defined]
                            except Exception as e:
                                logger.error("Error creating UploadDownloadGraphWidget after refresh: %s", e, exc_info=True)
                        self.call_after_refresh(create_graph_widget)  # type: ignore[attr-defined]
                except Exception as e:
                    logger.error("Error creating UploadDownloadGraphWidget: %s", e, exc_info=True)
                    # Show error message
                    try:
                        placeholder = self.query_one("#ud-graph-placeholder", Static)  # type: ignore[attr-defined]
                        if placeholder:
                            placeholder.update(f"Error loading graph: {e}")  # type: ignore[attr-defined]
                    except Exception:
                        pass
            else:
                logger.warning("PerformanceGraphWidget: No data provider available")
                # Update placeholder to show data provider is missing
                try:
                    placeholder = self.query_one("#ud-graph-placeholder", Static)  # type: ignore[attr-defined]
                    if placeholder:
                        placeholder.update("Data provider not available")  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception as e:
            logger.error("Error mounting PerformanceGraphWidget: %s", e, exc_info=True)

    def update_from_stats(self, stats: dict[str, Any]) -> None:  # pragma: no cover
        """Update graph with statistics (forward to nested UploadDownloadGraphWidget).
        
        Args:
            stats: Dictionary containing download_rate and upload_rate
        """
        try:
            # Forward update to nested widget if it exists
            if self._upload_download_widget:
                self._upload_download_widget.update_from_stats(stats)
            else:
                # Try to find it if not yet set
                try:
                    from ccbt.interface.widgets.graph_widget import UploadDownloadGraphWidget
                    nested_widget = self.query_one(UploadDownloadGraphWidget)  # type: ignore[attr-defined]
                    if nested_widget:
                        nested_widget.update_from_stats(stats)
                        self._upload_download_widget = nested_widget
                except Exception:
                    # Widget not yet mounted, ignore
                    pass
        except Exception as e:
            logger.debug("Error updating PerformanceGraphWidget from stats: %s", e)

    def on_piece_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle piece-related events by triggering refresh of child widget."""
        try:
            if self._upload_download_widget:
                self._upload_download_widget.on_piece_event(event_type, event_data)
            # Also trigger our own update if we have _update_from_provider
            if hasattr(self, "_update_from_provider"):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._update_from_provider())  # type: ignore[attr-defined]
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("PerformanceGraphWidget.on_piece_event: Error: %s", e)

    def on_progress_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle progress update events by triggering refresh."""
        try:
            if self._upload_download_widget:
                self._upload_download_widget.on_progress_event(event_type, event_data)
            if hasattr(self, "_update_from_provider"):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._update_from_provider())  # type: ignore[attr-defined]
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("PerformanceGraphWidget.on_progress_event: Error: %s", e)

    def on_peer_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle peer-related events (not typically relevant for this widget)."""
        pass

    def _register_nested_widget(self, widget: Any) -> None:
        """Register a nested widget with the adapter for event-driven updates.
        
        Args:
            widget: Nested widget instance to register
        """
        try:
            if self._data_provider and hasattr(self._data_provider, "get_adapter"):
                adapter = self._data_provider.get_adapter()
                if adapter and hasattr(adapter, "register_widget"):
                    adapter.register_widget(widget)
                    logger.debug("Registered nested widget %s for event-driven updates", type(widget).__name__)
        except Exception as e:
            logger.debug("Error registering nested widget: %s", e)


class SystemResourcesGraphWidget(Container):  # type: ignore[misc]
    """Graph widget for system resources (CPU, Memory, Disk)."""

    DEFAULT_CSS = """
    SystemResourcesGraphWidget {
        height: 1fr;
        min-height: 20;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    #system-section {
        height: 1fr;
        min-height: 18;
        layout: vertical;
        padding: 0 1;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    #system-title {
        height: 1;
        min-height: 1;
        text-style: bold;
        display: block;
    }
    #system-metrics-content {
        height: 1fr;
        min-height: 16;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
        display: block;
    }
    Static {
        height: auto;
        min-height: 1;
        margin: 0 1;
        display: block;
    }
    Sparkline {
        height: 10;
        min-height: 10;
        width: 1fr;
        min-width: 20;
        margin: 1;
        display: block;
        border: solid $primary;
        background: $surface;
    }
    #cpu-label, #memory-label, #disk-label {
        height: 1;
        min-height: 1;
        margin: 0 1;
        display: block;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize system resources graph widget."""
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._cpu_history: list[float] = []
        self._memory_history: list[float] = []
        self._disk_history: list[float] = []
        self._cpu_sparkline: Sparkline | None = None
        self._memory_sparkline: Sparkline | None = None
        self._disk_sparkline: Sparkline | None = None
        self._update_task: Any | None = None
        self._max_samples = 120

    def compose(self) -> Any:  # pragma: no cover
        """Compose the system resources graph widget."""
        with Container(id="system-section"):
            yield Static("System Resources", id="system-title")
            with Container(id="system-metrics-content"):
                yield Static("CPU Usage (%):", id="cpu-label")
                yield Sparkline(id="cpu-sparkline")
                yield Static("Memory Usage (%):", id="memory-label")
                yield Sparkline(id="memory-sparkline")
                yield Static("Disk Usage (%):", id="disk-label")
                yield Sparkline(id="disk-sparkline")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the system resources graph widget."""
        try:
            self._cpu_sparkline = self.query_one("#cpu-sparkline", Sparkline)  # type: ignore[attr-defined]
            self._memory_sparkline = self.query_one("#memory-sparkline", Sparkline)  # type: ignore[attr-defined]
            self._disk_sparkline = self.query_one("#disk-sparkline", Sparkline)  # type: ignore[attr-defined]
            
            # Initialize with zero data so graphs render immediately
            if self._cpu_sparkline:
                self._cpu_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            if self._memory_sparkline:
                self._memory_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            if self._disk_sparkline:
                self._disk_sparkline.data = [0.0] * 10  # type: ignore[attr-defined]
            
            # Start periodic updates if data provider is available
            if self._data_provider:
                self._start_updates()
        except Exception as e:
            logger.debug("Error mounting system resources graph: %s", e)

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount the widget and stop updates."""
        if self._update_task:
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:  # pragma: no cover
        """Start periodic updates from data provider."""
        import asyncio
        
        def schedule_update() -> None:
            """Schedule async update (wrapper for set_interval)."""
            try:
                # Create task to run async update
                asyncio.create_task(self._update_from_provider())
            except Exception as e:
                logger.debug("Error scheduling system resources graph update: %s", e)
        
        try:
            # CRITICAL FIX: set_interval doesn't work with async functions directly
            # Use wrapper function that creates async task
            # CRITICAL FIX: Reduced interval from 2.0s to 1.0s for tighter performance updates
            self._update_task = self.set_interval(1.0, schedule_update)  # type: ignore[attr-defined]
            # Trigger initial update immediately
            self.call_later(schedule_update)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error starting system resources graph update loop: %s", e)

    def on_piece_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle piece-related events (system resources don't typically care about pieces)."""
        # System resources are not directly affected by piece events
        pass

    def on_progress_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle progress update events (system resources may be affected by overall activity)."""
        # Trigger refresh to update system metrics
        try:
            if hasattr(self, "_update_from_provider"):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._update_from_provider())  # type: ignore[attr-defined]
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("SystemResourcesGraphWidget.on_progress_event: Error: %s", e)

    def on_peer_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle peer-related events (not typically relevant for system resources)."""
        pass


class SwarmHealthDotPlot(Container):  # type: ignore[misc]
    """Graph widget that renders swarm availability using patterned dot plots with gradients."""

    DEFAULT_CSS = """
    SwarmHealthDotPlot {
        height: 1fr;
        min-height: 16;
        layout: vertical;
        overflow: hidden auto;
        padding: 0 1;
    }
    #swarm-health-body {
        height: 1fr;
        layout: vertical;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider | None = None,
        info_hash_hex: str | None = None,
        max_rows: int = 6,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._info_hash = info_hash_hex
        self._content: Static | None = None
        self._legend: Static | None = None
        self._update_task: Any | None = None
        self._max_rows = max_rows
        self._dot_count = 12
        self._previous_samples: dict[str, dict[str, Any]] = {}  # Track previous samples for trends

    def compose(self) -> Any:  # pragma: no cover
        """Compose the swarm health widget."""
        title = "Swarm Health" if not self._info_hash else "Torrent Swarm Health"
        yield Static(title, id="swarm-health-title")
        with Container(id="swarm-health-body"):
            yield Static("Loading swarm data…", id="swarm-health-content")
            yield Static("", id="swarm-health-legend")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Start periodic updates after mounting."""
        try:
            self._content = self.query_one("#swarm-health-content", Static)  # type: ignore[attr-defined]
            self._legend = self.query_one("#swarm-health-legend", Static)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("SwarmHealthDotPlot: failed to query children: %s", exc)
        self._start_updates()

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Stop update loop when unmounted."""
        if self._update_task:
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:
        """Schedule periodic updates using Textual timers."""
        if not self._data_provider:
            if self._content:
                self._content.update("Data provider not available")
            return

        import asyncio

        def schedule_update() -> None:
            try:
                asyncio.create_task(self._update_from_provider())
            except Exception as exc:  # pragma: no cover
                logger.debug("SwarmHealthDotPlot: error scheduling update: %s", exc)

        try:
            self._update_task = self.set_interval(2.5, schedule_update)  # type: ignore[attr-defined]
            self.call_after_refresh(schedule_update)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("SwarmHealthDotPlot: failed to start interval: %s", exc)

    async def _update_from_provider(self) -> None:
        """Fetch swarm health samples and update UI with trends and annotations."""
        if not self._data_provider or not self._content:
            return
        try:
            samples = await self._data_provider.get_swarm_health_samples(
                self._info_hash,
                limit=self._max_rows,
                include_history=True,
            )
        except Exception as exc:
            logger.debug("SwarmHealthDotPlot: error fetching swarm samples: %s", exc)
            samples = []

        if not samples:
            self._content.update("No swarm activity yet")
            if self._legend:
                self._legend.update("")
            return

        table = Table(show_header=True, box=None, expand=True, padding=(0, 1))
        table.add_column("Torrent", style="cyan", ratio=1)
        table.add_column("Availability", ratio=2)
        table.add_column("Trend", style="dim", ratio=1)
        table.add_column("Rates", style="green", ratio=1)

        strongest_sample = max(samples, key=lambda s: float(s.get("swarm_availability", 0.0)))
        rarity_percentiles: dict[str, float] | None = None

        for sample in samples:
            info_hash = sample.get("info_hash", "")
            ratio = float(sample.get("swarm_availability", 0.0))
            name = sample.get("name") or info_hash[:16] if info_hash else "unknown"
            if not rarity_percentiles:
                rarity_percentiles = sample.get("rarity_percentiles")
            
            # Build two-row patterned dot grid
            dots = self._build_patterned_dot_grid(ratio, sample)
            
            # Calculate trend
            trend_indicator = self._get_trend_indicator(sample, info_hash)
            
            # Add annotation for critical torrents
            if ratio < 0.25:
                name = f"{name} [red][!][/red]"
            
            rates = self._format_rate_pair(
                float(sample.get("download_rate", 0.0)),
                float(sample.get("upload_rate", 0.0)),
            )
            table.add_row(name, dots, trend_indicator, rates)
            
            # Store current sample for next trend calculation
            self._previous_samples[info_hash] = sample

        table_panel = Panel(table, title="Swarm Availability", border_style="blue")
        if rarity_percentiles:
            rarity_panel = self._render_rarity_percentiles(rarity_percentiles)
            content = Group(table_panel, rarity_panel)
        else:
            content = table_panel
        self._content.update(content)

        if self._legend:
            legend = Text()
            legend.append("●", style="green")
            legend.append(" = excellent, ", style="dim")
            legend.append("◐", style="yellow")
            legend.append(" = healthy, ", style="dim")
            legend.append("◌", style="orange1")
            legend.append(" = fragile, ", style="dim")
            legend.append("□", style="grey46")
            legend.append(" = empty", style="dim")
            self._legend.update(legend)

    def _render_rarity_percentiles(self, percentiles: dict[str, float]) -> Panel:
        """Render rarity percentile summary panel."""
        table = Table(show_header=False, box=None, expand=True, padding=(0, 1))
        table.add_column("Percentile", style="magenta", ratio=1)
        table.add_column("Availability", justify="right", ratio=1)

        display_order = ["p10", "p25", "p50", "p75", "p90", "p95"]
        added = False
        for key in display_order:
            if key in percentiles:
                value = float(percentiles[key])
                table.add_row(f"P{key[1:]}", f"{value * 100:.1f}%")
                added = True

        if not added:
            for key in sorted(percentiles):
                value = float(percentiles[key])
                table.add_row(key.upper(), f"{value * 100:.1f}%")

        summary_text = Text("Swarm rarity percentiles indicate how scarce pieces are across torrents.", style="dim")
        return Panel(
            Group(summary_text, table),
            title="Rarity Percentiles",
            border_style="purple",
        )

    def _build_dot_pattern(self, ratio: float) -> Text:
        """Create a colored dot pattern for a ratio (legacy single-row)."""
        filled = int(round(self._dot_count * max(0.0, min(1.0, ratio))))
        pattern = Text()
        fill_color = self._color_for_ratio(ratio)
        for idx in range(self._dot_count):
            char = "●" if idx < filled else "◌"
            color = fill_color if idx < filled else "grey35"
            pattern.append(char, style=color)
        return pattern
    
    def _build_patterned_dot_grid(self, ratio: float, sample: dict[str, Any]) -> Text:
        """Create a two-row patterned dot grid with gradients.
        
        Uses alternating glyphs (●, ◐, ◌) based on availability and peer counts
        to create visual patterns that show swarm health gradients.
        """
        # Calculate gradient based on ratio and peer counts
        connected_peers = int(sample.get("connected_peers", 0))
        active_peers = int(sample.get("active_peers", 0))
        peer_factor = min(1.0, (active_peers / max(connected_peers, 1)) if connected_peers > 0 else 0.0)
        
        # Two rows of dots
        dots_per_row = self._dot_count // 2
        total_dots = self._dot_count
        
        pattern = Text()
        fill_color = self._color_for_ratio(ratio)
        peer_buckets = self._calculate_peer_buckets(sample, total_dots)
        
        # Calculate filled dots
        filled = int(round(total_dots * max(0.0, min(1.0, ratio))))
        
        for idx in range(total_dots):
            if idx < filled:
                # Use gradient: solid for high availability, half-filled for medium, outline for low
                if ratio >= 0.8:
                    char = "●"  # Solid
                elif ratio >= 0.5:
                    # Alternate between solid and half-filled
                    char = "●" if (idx % 2 == 0) else "◐"
                elif ratio >= 0.25:
                    # Use half-filled and outline
                    char = "◐" if (idx % 2 == 0) else "◌"
                else:
                    # Mostly outline with occasional half-filled
                    char = "◌" if (idx % 3 != 0) else "◐"
                color = fill_color
            else:
                char = "□"  # Empty square
                color = "grey46"
            
            pattern.append(char, style=color)
            bucket = peer_buckets[idx] if idx < len(peer_buckets) else (0, 0)
            pattern.append(self._format_peer_bucket(*bucket), style="grey50")
            
            # Add newline after first row
            if idx == dots_per_row - 1:
                pattern.append("\n")
        
        return pattern
    
    def _get_trend_indicator(self, sample: dict[str, Any], info_hash: str) -> str:
        """Get trend indicator arrow based on previous sample."""
        if not info_hash or info_hash not in self._previous_samples:
            return "—"  # No trend data yet
        
        previous = self._previous_samples[info_hash]
        current_avail = float(sample.get("swarm_availability", 0.0))
        previous_avail = float(previous.get("swarm_availability", 0.0))
        
        delta = current_avail - previous_avail
        delta_percentage = delta * 100
        threshold = 0.05  # 5% change threshold

        def _format_delta(value: float) -> str:
            return f"{value:+.1f}pp"
        
        if delta > threshold:
            return f"[green]↑ {_format_delta(delta_percentage)}[/green]"  # Improving
        if delta < -threshold:
            return f"[red]↓ {_format_delta(delta_percentage)}[/red]"  # Degrading
        return f"[dim]→ {_format_delta(delta_percentage)}[/dim]"  # Stable

    @staticmethod
    def _format_rate_pair(download_rate: float, upload_rate: float) -> str:
        """Format download/upload rates into human-readable KiB/s strings."""
        def _format(rate: float) -> str:
            if rate >= 1024 * 1024:
                return f"{rate / (1024 * 1024):.1f} MiB/s"
            if rate >= 1024:
                return f"{rate / 1024:.1f} KiB/s"
            return f"{rate:.0f} B/s"

        return f"↓ {_format(download_rate)} • ↑ {_format(upload_rate)}"

    @staticmethod
    def _color_for_ratio(ratio: float) -> str:
        """Map availability ratio to a Rich color."""
        if ratio >= 0.8:
            return "green"
        if ratio >= 0.5:
            return "yellow"
        if ratio >= 0.25:
            return "orange1"
        return "red"

    @staticmethod
    def _format_peer_bucket(active_bucket: int, connected_bucket: int) -> str:
        """Format peer bucket counts for display alongside dots."""
        if connected_bucket <= 0 and active_bucket <= 0:
            return "  0/0 "
        return f" {active_bucket:02}/{connected_bucket:02} "

    def _calculate_peer_buckets(self, sample: dict[str, Any], total_slots: int) -> list[tuple[int, int]]:
        """Distribute active/connected peers across dot slots for annotations."""
        if total_slots <= 0:
            return []

        connected_peers = max(int(sample.get("connected_peers", 0)), 0)
        active_peers = max(int(sample.get("active_peers", 0)), 0)

        if connected_peers == 0 and active_peers == 0:
            return [(0, 0)] * total_slots

        bucket_size = max(1, math.ceil(max(connected_peers, active_peers) / total_slots))
        remaining_connected = connected_peers
        remaining_active = active_peers
        buckets: list[tuple[int, int]] = []

        for _ in range(total_slots):
            if remaining_connected <= 0 and remaining_active <= 0:
                buckets.append((0, 0))
                continue

            connected_bucket = min(bucket_size, remaining_connected) if remaining_connected > 0 else 0
            remaining_connected = max(0, remaining_connected - connected_bucket)

            active_bucket = min(connected_bucket, remaining_active) if connected_bucket > 0 else 0
            remaining_active = max(0, remaining_active - active_bucket)

            buckets.append((active_bucket, connected_bucket))

        return buckets

    def on_piece_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle piece-related events by triggering refresh."""
        try:
            if hasattr(self, "_update_from_provider"):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._update_from_provider())
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("SwarmHealthDotPlot.on_piece_event: Error: %s", e)

    def on_progress_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle progress update events by triggering refresh."""
        try:
            if hasattr(self, "_update_from_provider"):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._update_from_provider())
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("SwarmHealthDotPlot.on_progress_event: Error: %s", e)

    def on_peer_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle peer-related events by triggering refresh (swarm health depends on peers)."""
        try:
            if hasattr(self, "_update_from_provider"):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._update_from_provider())
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("SwarmHealthDotPlot.on_peer_event: Error: %s", e)


class PeerQualitySummaryWidget(Container):  # type: ignore[misc]
    """Widget showing global peer quality distributions."""

    DEFAULT_CSS = """
    PeerQualitySummaryWidget {
        height: 1fr;
        min-height: 16;
        layout: vertical;
        padding: 0 1;
    }
    #peer-quality-body {
        height: 1fr;
        layout: vertical;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._summary: Static | None = None
        self._table: DataTable | None = None
        self._update_task: Any | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the peer quality widget."""
        yield Static("Peer Quality", id="peer-quality-title")
        with Container(id="peer-quality-body"):
            yield Static("Loading peer metrics…", id="peer-quality-summary")
            yield DataTable(id="peer-quality-table", zebra_stripes=True)

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Initialize table and start polling."""
        try:
            self._summary = self.query_one("#peer-quality-summary", Static)  # type: ignore[attr-defined]
            self._table = self.query_one("#peer-quality-table", DataTable)  # type: ignore[attr-defined]
            if self._table:
                self._table.add_columns("Peer", "↓ (KiB/s)", "↑ (KiB/s)", "Quality")
        except Exception as exc:
            logger.debug("PeerQualitySummaryWidget: failed to set up table: %s", exc)
        self._start_updates()

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Cancel periodic updates when removed."""
        if self._update_task:
            if hasattr(self._update_task, "stop"):
                self._update_task.stop()  # type: ignore[attr-defined]
            elif hasattr(self._update_task, "cancel"):
                self._update_task.cancel()  # type: ignore[attr-defined]
            self._update_task = None

    def _start_updates(self) -> None:
        """Kick off periodic refresh."""
        if not self._data_provider:
            if self._summary:
                self._summary.update("Peer metrics unavailable")
            return

        import asyncio

        def schedule_update() -> None:
            try:
                asyncio.create_task(self._update_from_provider())
            except Exception as exc:
                logger.debug("PeerQualitySummaryWidget: schedule error: %s", exc)

        try:
            # CRITICAL FIX: Reduced interval from 3.0s to 1.5s for tighter updates
            self._update_task = self.set_interval(1.5, schedule_update)  # type: ignore[attr-defined]
            self.call_after_refresh(schedule_update)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("PeerQualitySummaryWidget: failed to start timer: %s", exc)

    async def _update_from_provider(self) -> None:
        """Fetch metrics and refresh UI."""
        if not self._data_provider or not self._summary or not self._table:
            return

        try:
            metrics = await self._data_provider.get_peer_metrics()
        except Exception as exc:
            logger.debug("PeerQualitySummaryWidget: error fetching metrics: %s", exc)
            metrics = {}

        total_peers = int(metrics.get("total_peers", 0))
        active_peers = int(metrics.get("active_peers", 0))
        peers = metrics.get("peers", []) or []

        distribution = self._rank_peers(peers)
        summary_text = (
            f"Total: {total_peers} • Active: {active_peers} | "
            f"Excellent: {distribution['excellent']} | "
            f"Good: {distribution['good']} | "
            f"Fair: {distribution['fair']} | "
            f"Poor: {distribution['poor']}"
        )
        self._summary.update(summary_text)

        self._table.clear()
        top_peers = sorted(
            peers,
            key=lambda p: (
                float(p.get("total_download_rate", 0.0)) + float(p.get("total_upload_rate", 0.0))
            ),
            reverse=True,
        )[:6]

        for peer in top_peers:
            peer_label = peer.get("peer_key") or f"{peer.get('ip', '?')}:{peer.get('port', '?')}"
            down = float(peer.get("total_download_rate", 0.0)) / 1024.0
            up = float(peer.get("total_upload_rate", 0.0)) / 1024.0
            quality = self._format_quality(down + up)
            self._table.add_row(
                str(peer_label),
                f"{down:.1f}",
                f"{up:.1f}",
                quality,
            )

    @staticmethod
    def _rank_peers(peers: list[dict[str, Any]]) -> dict[str, int]:
        """Classify peers into coarse quality buckets."""
        distribution = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
        for peer in peers or []:
            total_rate = (
                float(peer.get("total_download_rate", 0.0))
                + float(peer.get("total_upload_rate", 0.0))
            ) / 1024.0  # KiB/s
            if total_rate >= 1024:
                distribution["excellent"] += 1
            elif total_rate >= 256:
                distribution["good"] += 1
            elif total_rate >= 32:
                distribution["fair"] += 1
            else:
                distribution["poor"] += 1
        return distribution

    @staticmethod
    def _format_quality(kib_per_s: float) -> str:
        """Return a colored quality label for a bandwidth figure."""
        if kib_per_s >= 1024:
            return "[green]Excellent[/green]"
        if kib_per_s >= 256:
            return "[yellow]Good[/yellow]"
        if kib_per_s >= 32:
            return "[orange1]Fair[/orange1]"
        return "[red]Poor[/red]"

    def on_piece_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle piece-related events (not directly relevant for peer quality)."""
        # Peer quality is more about peer performance than piece events
        pass

    def on_progress_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle progress update events (may affect peer quality metrics)."""
        # Trigger refresh to update peer metrics
        try:
            if hasattr(self, "_update_from_provider"):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._update_from_provider())
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("PeerQualitySummaryWidget.on_progress_event: Error: %s", e)

    def on_peer_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle peer-related events by triggering refresh (this widget cares about peers)."""
        try:
            if hasattr(self, "_update_from_provider"):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._update_from_provider())
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("PeerQualitySummaryWidget.on_peer_event: Error: %s", e)

