"""Advanced Metrics Collector for ccBitTorrent.

from __future__ import annotations

Provides comprehensive metrics collection including:
- Custom metrics with labels
- Metric aggregation and rollup
- Performance counters
- Resource utilization tracking
- Network statistics
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypedDict

import psutil

from ccbt.events import Event, EventType, emit_event

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    INFO = "info"


class AggregationType(Enum):
    """Types of metric aggregation."""

    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    PERCENTILE = "percentile"


@dataclass
class MetricLabel:
    """Metric label."""

    name: str
    value: str


@dataclass
class MetricValue:
    """Metric value with timestamp."""

    value: int | float | str
    timestamp: float
    labels: list[MetricLabel] = field(default_factory=list)


@dataclass
class Metric:
    """Metric definition."""

    name: str
    metric_type: MetricType
    description: str
    labels: list[MetricLabel] = field(default_factory=list)
    values: deque = field(default_factory=lambda: deque(maxlen=1000))
    aggregation: AggregationType = AggregationType.SUM
    retention_seconds: int = 3600  # 1 hour


@dataclass
class AlertRule:
    """Alert rule definition."""

    name: str
    metric_name: str
    condition: str  # e.g., "value > 100"
    severity: str = "warning"
    description: str = ""
    enabled: bool = True
    cooldown_seconds: int = 300  # 5 minutes
    last_triggered: float = 0.0


class MetricsCollector:
    """Advanced metrics collector."""

    class _NetworkIO(TypedDict):
        bytes_sent: int
        bytes_recv: int

    class _SystemMetrics(TypedDict):
        cpu_usage: float
        memory_usage: float
        disk_usage: float
        network_io: MetricsCollector._NetworkIO
        process_count: int

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: dict[str, Metric] = {}
        self.alert_rules: dict[str, AlertRule] = {}
        self.collectors: dict[str, Callable] = {}

        # System metrics
        self.system_metrics: MetricsCollector._SystemMetrics = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "disk_usage": 0.0,
            "network_io": {"bytes_sent": 0, "bytes_recv": 0},
            "process_count": 0,
        }

        # Performance tracking
        self.performance_data = {
            "peer_connections": 0,
            "download_speed": 0.0,
            "upload_speed": 0.0,
            "pieces_completed": 0,
            "pieces_failed": 0,
            "tracker_requests": 0,
            "tracker_responses": 0,
        }

        # Collection interval
        self.collection_interval = 5.0  # seconds
        self.collection_task: asyncio.Task | None = None
        self.running = False

        # Statistics
        self.stats = {
            "metrics_collected": 0,
            "alerts_triggered": 0,
            "collection_errors": 0,
        }

    async def start(self) -> None:
        """Start metrics collection."""
        if self.running:
            return

        self.running = True
        self.collection_task = asyncio.create_task(self._collection_loop())

        # Emit start event
        await emit_event(
            Event(
                event_type=EventType.MONITORING_STARTED.value,
                data={
                    "collection_interval": self.collection_interval,
                    "timestamp": time.time(),
                },
            ),
        )

    async def stop(self) -> None:
        """Stop metrics collection."""
        if not self.running:
            return

        self.running = False

        if self.collection_task:
            self.collection_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.collection_task

        # Emit stop event
        await emit_event(
            Event(
                event_type=EventType.MONITORING_STOPPED.value,
                data={
                    "timestamp": time.time(),
                },
            ),
        )

    def register_metric(
        self,
        name: str,
        metric_type: MetricType,
        description: str,
        labels: list[MetricLabel] | None = None,
        aggregation: AggregationType = AggregationType.SUM,
        retention_seconds: int = 3600,
    ) -> None:
        """Register a new metric."""
        self.metrics[name] = Metric(
            name=name,
            metric_type=metric_type,
            description=description,
            labels=labels or [],
            aggregation=aggregation,
            retention_seconds=retention_seconds,
        )

    def record_metric(
        self,
        name: str,
        value: float | str,
        labels: list[MetricLabel] | None = None,
    ) -> None:
        """Record a metric value."""
        if name not in self.metrics:
            # Auto-register metric if it doesn't exist
            self.register_metric(
                name,
                MetricType.GAUGE,
                f"Auto-registered metric: {name}",
            )

        metric = self.metrics[name]
        metric_value = MetricValue(
            value=value,
            timestamp=time.time(),
            labels=labels or [],
        )

        metric.values.append(metric_value)

        # Check alert rules
        self._check_alert_rules(name, value)

        # Also forward to global AlertManager (if available) so shared rules can trigger
        try:
            # Lazy import to avoid circular imports during module load
            from ccbt.monitoring import (
                get_alert_manager,  # type: ignore[import-untyped]
            )

            am = get_alert_manager()
            # Only attempt numeric evaluation for shared rules
            v_any: float | str = value
            if isinstance(value, str):
                # simple numeric parse; ignore parse errors
                with contextlib.suppress(Exception):
                    if value.replace(".", "", 1).isdigit():
                        v_any = float(value)
            # Schedule async processing if running in an event loop
            import asyncio as _asyncio

            with contextlib.suppress(RuntimeError):
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    task = loop.create_task(am.process_alert(name, v_any))  # type: ignore[arg-type]
                    task.add_done_callback(lambda _t: None)  # Discard task reference
        except Exception:
            # If alert manager not available, skip silently
            logger.debug(
                "Alert manager not available for metric processing", exc_info=True
            )

        # Update statistics
        self.stats["metrics_collected"] += 1

    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: list[MetricLabel] | None = None,
    ) -> None:
        """Increment a counter metric."""
        if name not in self.metrics:
            self.register_metric(name, MetricType.COUNTER, f"Counter: {name}")

        metric = self.metrics[name]
        if metric.values:
            current_value = metric.values[-1].value
            new_value = current_value + value
        else:
            new_value = value

        self.record_metric(name, new_value, labels)

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: list[MetricLabel] | None = None,
    ) -> None:
        """Set a gauge metric value."""
        if name not in self.metrics:
            self.register_metric(name, MetricType.GAUGE, f"Gauge: {name}")

        self.record_metric(name, value, labels)

    def record_histogram(
        self,
        name: str,
        value: float,
        labels: list[MetricLabel] | None = None,
    ) -> None:
        """Record a histogram value."""
        if name not in self.metrics:
            self.register_metric(name, MetricType.HISTOGRAM, f"Histogram: {name}")

        self.record_metric(name, value, labels)

    def add_alert_rule(
        self,
        name: str,
        metric_name: str,
        condition: str,
        severity: str = "warning",
        description: str = "",
        cooldown_seconds: int = 300,
    ) -> None:
        """Add an alert rule."""
        self.alert_rules[name] = AlertRule(
            name=name,
            metric_name=metric_name,
            condition=condition,
            severity=severity,
            description=description,
            cooldown_seconds=cooldown_seconds,
        )

    def get_metric(self, name: str) -> Metric | None:
        """Get a metric by name."""
        return self.metrics.get(name)

    def get_metric_value(
        self,
        name: str,
        aggregation: AggregationType | None = None,
    ) -> int | float | str | None:
        """Get aggregated metric value."""
        if name not in self.metrics:
            return None

        metric = self.metrics[name]
        if not metric.values:
            return None

        agg_type = aggregation or metric.aggregation

        if agg_type == AggregationType.SUM:
            return sum(
                v.value for v in metric.values if isinstance(v.value, (int, float))
            )
        if agg_type == AggregationType.AVG:
            values = [
                v.value for v in metric.values if isinstance(v.value, (int, float))
            ]
            return sum(values) / len(values) if values else 0
        if agg_type == AggregationType.MIN:
            values = [
                v.value for v in metric.values if isinstance(v.value, (int, float))
            ]
            return min(values) if values else 0
        if agg_type == AggregationType.MAX:
            values = [
                v.value for v in metric.values if isinstance(v.value, (int, float))
            ]
            return max(values) if values else 0
        if agg_type == AggregationType.COUNT:
            return len(metric.values)
        # Return latest value
        return metric.values[-1].value if metric.values else None

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics with their values."""
        result = {}

        for name, metric in self.metrics.items():
            result[name] = {
                "type": metric.metric_type.value,
                "description": metric.description,
                "labels": [
                    {"name": label.name, "value": label.value}
                    for label in metric.labels
                ],
                "aggregation": metric.aggregation.value,
                "retention_seconds": metric.retention_seconds,
                "value_count": len(metric.values),
                "current_value": self.get_metric_value(name),
                "aggregated_value": self.get_metric_value(name, metric.aggregation),
            }

        return result

    def get_system_metrics(self) -> dict[str, Any]:
        """Get system metrics."""
        return {
            "cpu_usage": self.system_metrics["cpu_usage"],
            "memory_usage": self.system_metrics["memory_usage"],
            "disk_usage": self.system_metrics["disk_usage"],
            "network_io": self.system_metrics["network_io"],
            "process_count": self.system_metrics["process_count"],
        }

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics."""
        return self.performance_data.copy()

    def get_metrics_statistics(self) -> dict[str, Any]:
        """Get metrics collection statistics."""
        return {
            "metrics_collected": self.stats["metrics_collected"],
            "alerts_triggered": self.stats["alerts_triggered"],
            "collection_errors": self.stats["collection_errors"],
            "registered_metrics": len(self.metrics),
            "alert_rules": len(self.alert_rules),
            "collection_interval": self.collection_interval,
            "running": self.running,
        }

    def export_metrics(self, format_type: str = "json") -> str:
        """Export metrics in specified format."""
        if format_type == "json":
            return json.dumps(self.get_all_metrics(), indent=2)
        if format_type == "prometheus":
            return self._export_prometheus_format()
        msg = f"Unsupported format: {format_type}"
        raise ValueError(msg)

    def cleanup_old_metrics(self, max_age_seconds: int = 3600) -> None:
        """Clean up old metric values."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        for metric in self.metrics.values():
            # Remove old values
            while metric.values and metric.values[0].timestamp < cutoff_time:
                metric.values.popleft()

    async def _collection_loop(self) -> None:
        """Main metrics collection loop."""
        while self.running:
            try:
                await self._collect_system_metrics()
                await self._collect_performance_metrics()
                await self._collect_custom_metrics()

                # Clean up old metrics
                self.cleanup_old_metrics()

                await asyncio.sleep(self.collection_interval)

            except Exception as e:
                self.stats["collection_errors"] += 1

                # Emit collection error event
                await emit_event(
                    Event(
                        event_type=EventType.MONITORING_ERROR.value,
                        data={
                            "error": str(e),
                            "timestamp": time.time(),
                        },
                    ),
                )

    async def _collect_system_metrics(self) -> None:
        """Collect system metrics."""
        try:
            # CPU usage
            self.system_metrics["cpu_usage"] = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            self.system_metrics["memory_usage"] = memory.percent

            # Disk usage
            disk = psutil.disk_usage("/")
            self.system_metrics["disk_usage"] = (disk.used / disk.total) * 100

            # Network I/O
            network = psutil.net_io_counters()
            self.system_metrics["network_io"] = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
            }

            # Process count
            self.system_metrics["process_count"] = len(psutil.pids())

            # Record system metrics
            self.set_gauge("system_cpu_usage", self.system_metrics["cpu_usage"])
            self.set_gauge("system_memory_usage", self.system_metrics["memory_usage"])
            self.set_gauge("system_disk_usage", self.system_metrics["disk_usage"])
            self.set_gauge(
                "system_network_bytes_sent",
                self.system_metrics["network_io"]["bytes_sent"],
            )
            self.set_gauge(
                "system_network_bytes_recv",
                self.system_metrics["network_io"]["bytes_recv"],
            )
            self.set_gauge("system_process_count", self.system_metrics["process_count"])

        except Exception as e:
            # Emit system metrics error
            await emit_event(
                Event(
                    event_type=EventType.MONITORING_ERROR.value,
                    data={
                        "error": f"System metrics collection error: {e!s}",
                        "timestamp": time.time(),
                    },
                ),
            )

    async def _collect_performance_metrics(self) -> None:
        """Collect performance metrics."""
        # Record performance metrics
        for name, value in self.performance_data.items():
            self.set_gauge(f"performance_{name}", value)

    async def _collect_custom_metrics(self) -> None:
        """Collect custom metrics from registered collectors."""
        for name, collector in self.collectors.items():
            try:
                if asyncio.iscoroutinefunction(collector):
                    value = await collector()
                else:
                    value = collector()

                self.set_gauge(f"custom_{name}", value)

            except Exception as e:
                # Emit custom metrics error
                await emit_event(
                    Event(
                        event_type=EventType.MONITORING_ERROR.value,
                        data={
                            "error": f"Custom metrics collection error for {name}: {e!s}",
                            "timestamp": time.time(),
                        },
                    ),
                )

    def _check_alert_rules(self, metric_name: str, value: float | str) -> None:
        """Check alert rules for a metric."""
        for rule_name, rule in self.alert_rules.items():
            if rule.metric_name != metric_name or not rule.enabled:
                continue

            # Check cooldown
            current_time = time.time()
            if current_time - rule.last_triggered < rule.cooldown_seconds:
                continue

            # Evaluate condition
            try:
                # Simple condition evaluation (in production, use a proper expression evaluator)
                if self._evaluate_condition(rule.condition, value):
                    rule.last_triggered = current_time
                    self.stats["alerts_triggered"] += 1

                    # Emit alert event
                    task = asyncio.create_task(
                        emit_event(
                            Event(
                                event_type=EventType.ALERT_TRIGGERED.value,
                                data={
                                    "rule_name": rule_name,
                                    "metric_name": metric_name,
                                    "value": value,
                                    "condition": rule.condition,
                                    "severity": rule.severity,
                                    "description": rule.description,
                                    "timestamp": current_time,
                                },
                            ),
                        ),
                    )
                    task.add_done_callback(lambda _t: None)  # Discard task reference

            except Exception as e:
                # Emit alert evaluation error
                task = asyncio.create_task(
                    emit_event(
                        Event(
                            event_type=EventType.MONITORING_ERROR.value,
                            data={
                                "error": f"Alert rule evaluation error for {rule_name}: {e!s}",
                                "timestamp": current_time,
                            },
                        ),
                    ),
                )
                task.add_done_callback(lambda _t: None)  # Discard task reference

    def _evaluate_condition(self, condition: str, value: float | str) -> bool:
        """Evaluate alert condition safely."""
        try:
            # Replace 'value' with actual value
            condition_expr = condition.replace("value", str(value))

            # Safe evaluation using ast and operator modules
            import ast
            import operator

            # Define safe operations
            safe_operators = {
                ast.Lt: operator.lt,
                ast.LtE: operator.le,
                ast.Gt: operator.gt,
                ast.GtE: operator.ge,
                ast.Eq: operator.eq,
                ast.NotEq: operator.ne,
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Mod: operator.mod,
                ast.Pow: operator.pow,
            }

            # Define safe unary operations
            safe_unary_operators = {
                ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }

            # Parse and evaluate safely
            tree = ast.parse(condition_expr, mode="eval")

            def safe_eval(node):
                if isinstance(node, ast.Expression):
                    return safe_eval(node.body)
                if isinstance(node, ast.Constant):
                    return node.value
                if isinstance(node, ast.Name):
                    # Only allow specific variables
                    if node.id in ["value"]:
                        return value
                    msg = f"Variable '{node.id}' not allowed"
                    raise ValueError(msg)
                if isinstance(node, ast.BinOp):
                    left = safe_eval(node.left)
                    right = safe_eval(node.right)
                    op = safe_operators.get(type(node.op))
                    if op is None:
                        msg = f"Operation {type(node.op).__name__} not allowed"
                        raise ValueError(
                            msg,
                        )
                    return op(left, right)
                if isinstance(node, ast.UnaryOp):
                    operand = safe_eval(node.operand)
                    op = safe_unary_operators.get(type(node.op))
                    if op is None:
                        msg = f"Operation {type(node.op).__name__} not allowed"
                        raise ValueError(
                            msg,
                        )
                    return op(operand)
                if isinstance(node, ast.Compare):
                    left = safe_eval(node.left)
                    for op, comparator in zip(node.ops, node.comparators):
                        right = safe_eval(comparator)
                        op_func = safe_operators.get(type(op))
                        if op_func is None:
                            msg = f"Operation {type(op).__name__} not allowed"
                            raise ValueError(
                                msg,
                            )
                        if not op_func(left, right):
                            return False
                    return True
                msg = f"Node type {type(node).__name__} not allowed"
                raise ValueError(msg)

            return safe_eval(tree)
        except Exception:
            return False

    def _export_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        for name, metric in self.metrics.items():
            # Add help comment
            lines.append(f"# HELP {name} {metric.description}")
            lines.append(f"# TYPE {name} {metric.metric_type.value}")

            # Add metric values
            for value in metric.values:
                labels_str = ""
                if value.labels:
                    label_pairs = [
                        f'{label.name}="{label.value}"' for label in value.labels
                    ]
                    labels_str = "{" + ",".join(label_pairs) + "}"

                lines.append(
                    f"{name}{labels_str} {value.value} {int(value.timestamp * 1000)}",
                )

        return "\n".join(lines)

    def register_custom_collector(self, name: str, collector: Callable) -> None:
        """Register a custom metrics collector."""
        self.collectors[name] = collector

    def unregister_custom_collector(self, name: str) -> None:
        """Unregister a custom metrics collector."""
        if name in self.collectors:
            del self.collectors[name]
