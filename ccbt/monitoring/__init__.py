"""Advanced monitoring for ccBitTorrent.

Provides comprehensive monitoring including:
- Custom metrics collection
- Alert rule engine
- Metric aggregation
- OpenTelemetry support
- Distributed tracing
"""

from .alert_manager import AlertManager
from .dashboard import DashboardManager
from .metrics_collector import MetricsCollector
from .tracing import TracingManager

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
