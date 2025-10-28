"""Advanced monitoring for ccBitTorrent.

from __future__ import annotations

Provides comprehensive monitoring including:
- Custom metrics collection
- Alert rule engine
- Metric aggregation
- OpenTelemetry support
- Distributed tracing
"""

from __future__ import annotations

from ccbt.monitoring.alert_manager import AlertManager
from ccbt.monitoring.dashboard import DashboardManager
from ccbt.monitoring.metrics_collector import MetricsCollector
from ccbt.monitoring.tracing import TracingManager

__all__ = [
    "AlertManager",
    "DashboardManager",
    "MetricsCollector",
    "TracingManager",
    "get_alert_manager",
]

# Global alert manager singleton for CLI/UI integration
_GLOBAL_ALERT_MANAGER: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    """Return a process-global AlertManager to share rules/alerts across components."""
    global _GLOBAL_ALERT_MANAGER
    if _GLOBAL_ALERT_MANAGER is None:
        _GLOBAL_ALERT_MANAGER = AlertManager()
    return _GLOBAL_ALERT_MANAGER
