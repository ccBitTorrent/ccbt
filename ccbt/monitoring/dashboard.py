"""Dashboard Manager for ccBitTorrent.

from __future__ import annotations

Provides comprehensive dashboard functionality including:
- Real-time metrics display
- Grafana dashboard templates
- Custom dashboard creation
- Metric visualization
- Alert integration
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ccbt.i18n import _
from ccbt.utils.events import Event, EventType, emit_event
from ccbt.utils.logging_config import get_logger

logger = get_logger(__name__)
MIN_MAGNET_PARTS = 2


class TorrentFileNotFoundError(ValueError):
    """Torrent file not found error."""

    def __init__(self, file_path: str):  # pragma: no cover
        """Initialize torrent file not found error."""
        super().__init__(_(f"Torrent file not found: {file_path}"))  # pragma: no cover


class InvalidTorrentExtensionError(ValueError):
    """Invalid torrent file extension error."""

    def __init__(self, file_path: str):  # pragma: no cover
        """Initialize invalid torrent extension error."""
        super().__init__(
            _(f"File must have .torrent extension: {file_path}")
        )  # pragma: no cover


class InvalidMagnetFormatError(ValueError):
    """Invalid magnet link format error."""

    def __init__(self):  # pragma: no cover
        """Initialize invalid magnet format error."""
        super().__init__(
            _("Invalid magnet link format - must start with 'magnet:?'")
        )  # pragma: no cover


class MissingBtihError(ValueError):
    """Missing btih parameter error."""

    def __init__(self):  # pragma: no cover
        """Initialize missing btih error."""
        super().__init__(
            _("Invalid magnet link - missing 'xt=urn:btih:' parameter")
        )  # pragma: no cover


if TYPE_CHECKING:  # pragma: no cover
    from ccbt.session import AsyncSessionManager  # pragma: no cover


class DashboardType(Enum):
    """Dashboard types."""

    OVERVIEW = "overview"
    PERFORMANCE = "performance"
    NETWORK = "network"
    SECURITY = "security"
    ALERTS = "alerts"
    CUSTOM = "custom"


class WidgetType(Enum):
    """Widget types."""

    METRIC = "metric"
    GRAPH = "graph"
    TABLE = "table"
    ALERT = "alert"
    LOG = "log"
    CUSTOM = "custom"


@dataclass
class Widget:
    """Dashboard widget."""

    id: str
    type: WidgetType
    title: str
    position: dict[str, int]  # x, y, width, height
    config: dict[str, Any] = field(default_factory=dict)
    refresh_interval: int = 5  # seconds
    enabled: bool = True


@dataclass
class Dashboard:
    """Dashboard definition."""

    id: str
    name: str
    type: DashboardType
    description: str
    widgets: list[Widget] = field(default_factory=list)
    refresh_interval: int = 5  # seconds
    enabled: bool = True
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class DashboardData:
    """Dashboard data."""

    dashboard_id: str
    timestamp: float
    data: dict[str, Any]


class DashboardManager:
    """Dashboard management system."""

    # Constants for magnet link validation
    MIN_MAGNET_PARTS = 2

    def __init__(self):
        """Initialize the dashboard manager."""
        self.dashboards: dict[str, Dashboard] = {}
        self.dashboard_data: dict[str, DashboardData] = {}
        self.data_sources: dict[str, Any] = {}

        # Real-time data
        self.real_time_data: dict[str, Any] = {}
        self.data_subscribers: dict[str, list[Callable]] = defaultdict(list)

        # Dashboard templates
        self.templates: dict[DashboardType, Dashboard] = {}

        # Statistics
        self.stats = {
            "dashboards_created": 0,
            "widgets_created": 0,
            "data_updates": 0,
            "subscribers": 0,
        }

        # Initialize default templates
        self._initialize_templates()

    def create_dashboard(
        self,
        name: str,
        dashboard_type: DashboardType,
        description: str = "",
        widgets: list[Widget] | None = None,
    ) -> str:
        """Create a new dashboard."""
        dashboard_id = f"dashboard_{int(time.time())}"

        dashboard = Dashboard(
            id=dashboard_id,
            name=name,
            type=dashboard_type,
            description=description,
            widgets=widgets or [],
            created_at=time.time(),
            updated_at=time.time(),
        )

        self.dashboards[dashboard_id] = dashboard
        self.stats["dashboards_created"] += 1

        # Emit dashboard created event
        task = asyncio.create_task(
            emit_event(
                Event(
                    event_type=EventType.DASHBOARD_CREATED.value,
                    data={
                        "dashboard_id": dashboard_id,
                        "name": name,
                        "type": dashboard_type.value,
                        "timestamp": time.time(),
                    },
                ),
            ),
        )
        task.add_done_callback(lambda _t: None)  # Discard task reference

        return dashboard_id

    def add_widget(self, dashboard_id: str, widget: Widget) -> bool:
        """Add widget to dashboard."""
        if dashboard_id not in self.dashboards:
            return False

        dashboard = self.dashboards[dashboard_id]
        dashboard.widgets.append(widget)
        dashboard.updated_at = time.time()

        self.stats["widgets_created"] += 1

        # Emit widget added event
        task = asyncio.create_task(
            emit_event(
                Event(
                    event_type=EventType.WIDGET_ADDED.value,
                    data={
                        "dashboard_id": dashboard_id,
                        "widget_id": widget.id,
                        "type": widget.type.value,
                        "timestamp": time.time(),
                    },
                ),
            ),
        )
        task.add_done_callback(lambda _t: None)  # Discard task reference

        return True

    def remove_widget(self, dashboard_id: str, widget_id: str) -> bool:
        """Remove widget from dashboard."""
        if dashboard_id not in self.dashboards:
            return False

        dashboard = self.dashboards[dashboard_id]
        dashboard.widgets = [w for w in dashboard.widgets if w.id != widget_id]
        dashboard.updated_at = time.time()

        # Emit widget removed event
        task = asyncio.create_task(
            emit_event(
                Event(
                    event_type=EventType.WIDGET_REMOVED.value,
                    data={
                        "dashboard_id": dashboard_id,
                        "widget_id": widget_id,
                        "timestamp": time.time(),
                    },
                ),
            ),
        )
        task.add_done_callback(lambda _t: None)  # Discard task reference

        return True

    def update_widget(
        self,
        dashboard_id: str,
        widget_id: str,
        updates: dict[str, Any],
    ) -> bool:
        """Update widget configuration."""
        if dashboard_id not in self.dashboards:
            return False

        dashboard = self.dashboards[dashboard_id]
        for widget in dashboard.widgets:
            if widget.id == widget_id:
                for key, value in updates.items():
                    if hasattr(widget, key):
                        setattr(widget, key, value)

                dashboard.updated_at = time.time()

                # Emit widget updated event
                task = asyncio.create_task(
                    emit_event(
                        Event(
                            event_type=EventType.WIDGET_UPDATED.value,
                            data={
                                "dashboard_id": dashboard_id,
                                "widget_id": widget_id,
                                "updates": updates,
                                "timestamp": time.time(),
                            },
                        ),
                    ),
                )
                task.add_done_callback(lambda _t: None)  # Discard task reference

                return True

        return False

    def get_dashboard(self, dashboard_id: str) -> Dashboard | None:
        """Get dashboard by ID."""
        return self.dashboards.get(dashboard_id)

    def get_all_dashboards(self) -> dict[str, Dashboard]:
        """Get all dashboards."""
        return self.dashboards.copy()

    def get_dashboard_data(self, dashboard_id: str) -> DashboardData | None:
        """Get dashboard data."""
        return self.dashboard_data.get(dashboard_id)

    async def update_dashboard_data(
        self,
        dashboard_id: str,
        data: dict[str, Any],
    ) -> None:
        """Update dashboard data."""
        dashboard_data = DashboardData(
            dashboard_id=dashboard_id,
            timestamp=time.time(),
            data=data,
        )

        self.dashboard_data[dashboard_id] = dashboard_data
        self.real_time_data[dashboard_id] = data

        # Notify subscribers
        if dashboard_id in self.data_subscribers:

            async def _notify_subscriber(subscriber, dashboard_data):
                """Notify a single subscriber safely."""
                try:
                    if asyncio.iscoroutinefunction(subscriber):
                        task = asyncio.create_task(subscriber(dashboard_data))
                        task.add_done_callback(
                            lambda _t: None
                        )  # Discard task reference
                    else:
                        subscriber(dashboard_data)
                except Exception as e:
                    # Emit subscriber error event
                    task = asyncio.create_task(
                        emit_event(
                            Event(
                                event_type=EventType.DASHBOARD_ERROR.value,
                                data={
                                    "error": f"Subscriber error: {e!s}",
                                    "dashboard_id": dashboard_id,
                                    "timestamp": time.time(),
                                },
                            ),
                        ),
                    )
                    task.add_done_callback(lambda _t: None)  # Discard task reference

            for subscriber in self.data_subscribers[dashboard_id]:
                await _notify_subscriber(subscriber, dashboard_data)

        self.stats["data_updates"] += 1

    def subscribe_to_dashboard(self, dashboard_id: str, callback: Callable) -> None:
        """Subscribe to dashboard data updates."""
        self.data_subscribers[dashboard_id].append(callback)
        self.stats["subscribers"] += 1

    def unsubscribe_from_dashboard(self, dashboard_id: str, callback: Callable) -> None:
        """Unsubscribe from dashboard data updates."""
        if dashboard_id in self.data_subscribers:
            try:
                self.data_subscribers[dashboard_id].remove(callback)
                self.stats["subscribers"] -= 1
            except ValueError:  # pragma: no cover
                pass  # pragma: no cover

    def create_grafana_dashboard(self, dashboard_id: str) -> dict[str, Any]:
        """Create Grafana dashboard JSON."""
        dashboard = self.get_dashboard(dashboard_id)
        if not dashboard:
            return {}

        grafana_dashboard: dict[str, Any] = {
            "dashboard": {
                "id": None,
                "title": dashboard.name,
                "description": dashboard.description,
                "tags": ["ccbt", dashboard.type.value],
                "timezone": "browser",
                "refresh": f"{dashboard.refresh_interval}s",
                "time": {
                    "from": "now-1h",
                    "to": "now",
                },
                "panels": [],  # type: list[dict[str, Any]]
            },
        }

        # Convert widgets to Grafana panels
        for widget in dashboard.widgets:
            panel = self._widget_to_grafana_panel(widget)
            if panel:
                grafana_dashboard["dashboard"]["panels"].append(panel)

        return grafana_dashboard

    def export_dashboard(self, dashboard_id: str, format_type: str = "json") -> str:
        """Export dashboard in specified format."""
        dashboard = self.get_dashboard(dashboard_id)
        if not dashboard:
            return ""

        if format_type == "json":  # pragma: no cover
            return json.dumps(  # pragma: no cover
                {  # pragma: no cover
                    "dashboard": dashboard,  # pragma: no cover
                    "data": self.dashboard_data.get(dashboard_id),  # pragma: no cover
                },  # pragma: no cover
                indent=2,  # pragma: no cover
            )  # pragma: no cover
        if format_type == "grafana":
            return json.dumps(self.create_grafana_dashboard(dashboard_id), indent=2)
        msg = f"Unsupported format: {format_type}"
        raise ValueError(msg)

    def get_dashboard_statistics(self) -> dict[str, Any]:
        """Get dashboard statistics."""
        return {
            "dashboards_created": self.stats["dashboards_created"],
            "widgets_created": self.stats["widgets_created"],
            "data_updates": self.stats["data_updates"],
            "subscribers": self.stats["subscribers"],
            "active_dashboards": len(self.dashboards),
            "data_sources": len(self.data_sources),
            "templates": len(self.templates),
        }

    def _initialize_templates(self) -> None:
        """Initialize default dashboard templates."""
        # Overview template
        overview_dashboard = Dashboard(
            id="template_overview",
            name="Overview",
            type=DashboardType.OVERVIEW,
            description="System overview dashboard",
            widgets=[
                Widget(
                    id="system_metrics",
                    type=WidgetType.METRIC,
                    title="System Metrics",
                    position={"x": 0, "y": 0, "width": 6, "height": 4},
                    config={"metrics": ["cpu_usage", "memory_usage", "disk_usage"]},
                ),
                Widget(
                    id="network_metrics",
                    type=WidgetType.GRAPH,
                    title="Network Activity",
                    position={"x": 6, "y": 0, "width": 6, "height": 4},
                    config={"metrics": ["bytes_sent", "bytes_received"]},
                ),
            ],
        )
        self.templates[DashboardType.OVERVIEW] = overview_dashboard

        # Performance template
        performance_dashboard = Dashboard(
            id="template_performance",
            name="Performance",
            type=DashboardType.PERFORMANCE,
            description="Performance monitoring dashboard",
            widgets=[
                Widget(
                    id="download_speed",
                    type=WidgetType.GRAPH,
                    title="Download Speed",
                    position={"x": 0, "y": 0, "width": 12, "height": 6},
                    config={"metric": "download_speed", "unit": "bytes/s"},
                ),
                Widget(
                    id="upload_speed",
                    type=WidgetType.GRAPH,
                    title="Upload Speed",
                    position={"x": 0, "y": 6, "width": 12, "height": 6},
                    config={"metric": "upload_speed", "unit": "bytes/s"},
                ),
            ],
        )
        self.templates[DashboardType.PERFORMANCE] = performance_dashboard

        # Security template
        security_dashboard = Dashboard(
            id="template_security",
            name="Security",
            type=DashboardType.SECURITY,
            description="Security monitoring dashboard",
            widgets=[
                Widget(
                    id="security_events",
                    type=WidgetType.TABLE,
                    title="Security Events",
                    position={"x": 0, "y": 0, "width": 12, "height": 8},
                    config={
                        "columns": [
                            "timestamp",
                            "event_type",
                            "severity",
                            "description",
                        ],
                    },
                ),
                Widget(
                    id="blocked_ips",
                    type=WidgetType.METRIC,
                    title="Blocked IPs",
                    position={"x": 0, "y": 8, "width": 6, "height": 4},
                    config={"metric": "blocked_ips_count"},
                ),
            ],
        )
        self.templates[DashboardType.SECURITY] = security_dashboard

    def _widget_to_grafana_panel(self, widget: Widget) -> dict[str, Any] | None:
        """Convert widget to Grafana panel."""
        if widget.type == WidgetType.METRIC:
            return {
                "id": widget.id,
                "title": widget.title,
                "type": "stat",
                "gridPos": widget.position,
                "targets": [
                    {
                        "expr": widget.config.get("metric", ""),
                        "refId": "A",
                    },
                ],
            }
        if widget.type == WidgetType.GRAPH:
            return {
                "id": widget.id,
                "title": widget.title,
                "type": "graph",
                "gridPos": widget.position,
                "targets": [
                    {
                        "expr": widget.config.get("metric", ""),
                        "refId": "A",
                    },
                ],
                "yAxes": [
                    {
                        "label": widget.config.get("unit", ""),
                        "min": 0,
                    },
                ],
            }
        if widget.type == WidgetType.TABLE:
            return {
                "id": widget.id,
                "title": widget.title,
                "type": "table",
                "gridPos": widget.position,
                "targets": [
                    {
                        "expr": widget.config.get("query", ""),
                        "refId": "A",
                    },
                ],
                "columns": widget.config.get("columns", []),
            }
        if widget.type == WidgetType.ALERT:
            return {
                "id": widget.id,
                "title": widget.title,
                "type": "alertlist",
                "gridPos": widget.position,
                "options": {
                    "showOptions": "current",
                    "maxItems": widget.config.get("max_items", 10),
                },
            }

        return None

    def create_dashboard_from_template(
        self,
        template_type: DashboardType,
        name: str,
    ) -> str:
        """Create dashboard from template."""
        if template_type not in self.templates:
            msg = f"Template not found: {template_type}"
            raise ValueError(msg)

        template = self.templates[template_type]

        # Create new dashboard based on template
        dashboard_id = self.create_dashboard(name, template_type, template.description)
        dashboard = self.dashboards[dashboard_id]

        # Copy widgets from template
        for widget in template.widgets:
            new_widget = Widget(
                id=f"{widget.id}_{int(time.time())}",
                type=widget.type,
                title=widget.title,
                position=widget.position.copy(),
                config=widget.config.copy(),
                refresh_interval=widget.refresh_interval,
                enabled=widget.enabled,
            )
            dashboard.widgets.append(new_widget)

        return dashboard_id

    async def add_torrent_file(
        self,
        session: AsyncSessionManager,
        file_path: str,
        _output_dir: str | None = None,
        resume: bool = False,
        download_limit: int = 0,
        upload_limit: int = 0,
    ) -> dict[str, Any]:
        """Add torrent from file with optional configuration."""

        def _raise_file_not_found():  # pragma: no cover
            raise TorrentFileNotFoundError(file_path)  # pragma: no cover

        def _raise_invalid_extension():  # pragma: no cover
            raise InvalidTorrentExtensionError(file_path)  # pragma: no cover

        try:
            # Validate file
            if not Path(file_path).exists():  # pragma: no cover
                _raise_file_not_found()  # pragma: no cover

            if not file_path.lower().endswith(".torrent"):  # pragma: no cover
                _raise_invalid_extension()  # pragma: no cover

            # Add to session
            info_hash = await session.add_torrent(
                file_path, resume=resume
            )  # pragma: no cover

            # Apply rate limits if specified
            if download_limit > 0 or upload_limit > 0:  # pragma: no cover
                await session.set_rate_limits(
                    info_hash, download_limit, upload_limit
                )  # pragma: no cover

            # Emit success event
            await emit_event(  # pragma: no cover
                Event(  # pragma: no cover
                    event_type=EventType.TORRENT_ADDED.value,  # pragma: no cover
                    data={
                        "info_hash": info_hash,
                        "source": "file",
                        "path": file_path,
                    },  # pragma: no cover
                ),  # pragma: no cover
            )  # pragma: no cover
        except Exception as e:  # pragma: no cover
            # Emit error event
            await emit_event(  # pragma: no cover
                Event(  # pragma: no cover
                    event_type=EventType.DASHBOARD_ERROR.value,  # pragma: no cover
                    data={
                        "error": str(e),
                        "operation": "add_torrent_file",
                    },  # pragma: no cover
                ),  # pragma: no cover
            )  # pragma: no cover
            return {"success": False, "error": str(e)}  # pragma: no cover
        else:
            return {"success": True, "info_hash": info_hash}  # pragma: no cover

    async def add_torrent_magnet(
        self,
        session: AsyncSessionManager,
        magnet_uri: str,
        _output_dir: str | None = None,
        resume: bool = False,
        download_limit: int = 0,
        upload_limit: int = 0,
    ) -> dict[str, Any]:
        """Add torrent from magnet link with optional configuration."""

        def _raise_invalid_magnet_format():  # pragma: no cover
            raise InvalidMagnetFormatError  # pragma: no cover

        def _raise_missing_btih():  # pragma: no cover
            raise MissingBtihError  # pragma: no cover

        try:
            # Validate magnet link
            if not magnet_uri.startswith("magnet:?"):  # pragma: no cover
                _raise_invalid_magnet_format()  # pragma: no cover

            if "xt=urn:btih:" not in magnet_uri:  # pragma: no cover
                _raise_missing_btih()  # pragma: no cover

            # Add to session
            info_hash = await session.add_magnet(
                magnet_uri, resume=resume
            )  # pragma: no cover

            # Apply rate limits if specified
            if download_limit > 0 or upload_limit > 0:  # pragma: no cover
                await session.set_rate_limits(
                    info_hash, download_limit, upload_limit
                )  # pragma: no cover

            # Emit success event
            await emit_event(  # pragma: no cover
                Event(  # pragma: no cover
                    event_type=EventType.TORRENT_ADDED.value,  # pragma: no cover
                    data={  # pragma: no cover
                        "info_hash": info_hash,  # pragma: no cover
                        "source": "magnet",  # pragma: no cover
                        "uri": magnet_uri,  # pragma: no cover
                    },  # pragma: no cover
                ),  # pragma: no cover
            )  # pragma: no cover
        except Exception as e:  # pragma: no cover
            # Emit error event
            await emit_event(  # pragma: no cover
                Event(  # pragma: no cover
                    event_type=EventType.DASHBOARD_ERROR.value,  # pragma: no cover
                    data={
                        "error": str(e),
                        "operation": "add_torrent_magnet",
                    },  # pragma: no cover
                ),  # pragma: no cover
            )  # pragma: no cover
            return {"success": False, "error": str(e)}  # pragma: no cover
        else:
            return {"success": True, "info_hash": info_hash}  # pragma: no cover

    def validate_torrent_file(self, file_path: str) -> dict[str, Any]:
        """Validate torrent file before adding."""
        try:
            path = Path(file_path)
            if not path.exists():
                return {"valid": False, "error": _(f"File not found: {file_path}")}

            if not path.is_file():
                return {"valid": False, "error": _(f"Path is not a file: {file_path}")}

            if not file_path.lower().endswith(".torrent"):
                return {
                    "valid": False,
                    "error": _(f"File must have .torrent extension: {file_path}"),
                }

            # Check file size (basic validation)
            if path.stat().st_size == 0:
                return {
                    "valid": False,
                    "error": _(f"Torrent file is empty: {file_path}"),
                }

            return {"valid": True, "path": str(path.absolute())}
        except Exception as e:  # pragma: no cover
            return {
                "valid": False,
                "error": _(f"Validation error: {e}"),
            }  # pragma: no cover

    def validate_magnet_link(self, magnet_uri: str) -> dict[str, Any]:
        """Validate magnet link format."""
        try:
            if not magnet_uri.startswith("magnet:?"):
                return {
                    "valid": False,
                    "error": _("Magnet link must start with 'magnet:?'"),
                }

            if "xt=urn:btih:" not in magnet_uri:
                return {
                    "valid": False,
                    "error": _("Magnet link must contain 'xt=urn:btih:' parameter"),
                }

            # Extract info hash for basic validation
            parts = magnet_uri.split("xt=urn:btih:")
            if len(parts) < MIN_MAGNET_PARTS:  # pragma: no cover
                return {
                    "valid": False,
                    "error": _("Invalid magnet link format"),
                }  # pragma: no cover

            info_hash_part = parts[1].split("&")[0]
            if len(info_hash_part) not in [
                40,
                32,
            ]:  # SHA-1 (40 chars) or MD5 (32 chars)
                return {
                    "valid": False,
                    "error": _("Invalid info hash length in magnet link"),
                }

        except Exception as e:  # pragma: no cover
            return {
                "valid": False,
                "error": _(f"Validation error: {e}"),
            }  # pragma: no cover
        else:
            return {"valid": True, "uri": magnet_uri}

    def get_add_torrent_options(self) -> dict[str, Any]:
        """Get available configuration options for adding torrents."""
        return {
            "output_dir": {
                "type": "string",
                "default": ".",
                "description": "Output directory for downloaded files",
            },
            "resume": {
                "type": "boolean",
                "default": False,
                "description": "Resume from checkpoint if available",
            },
            "download_limit": {
                "type": "integer",
                "default": 0,
                "min": 0,
                "description": "Download rate limit in KiB/s (0 = unlimited)",
            },
            "upload_limit": {
                "type": "integer",
                "default": 0,
                "min": 0,
                "description": "Upload rate limit in KiB/s (0 = unlimited)",
            },
            "priority": {
                "type": "choice",
                "choices": ["low", "normal", "high"],
                "default": "normal",
                "description": "Torrent priority",
            },
        }
