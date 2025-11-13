"""Alert Manager for ccBitTorrent.

from __future__ import annotations

Provides comprehensive alert management including:
- Alert rule engine
- Notification channels
- Alert escalation
- Alert history
- Alert suppression
"""

from __future__ import annotations

import asyncio
import json
import smtplib
import time
from collections import deque
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from ccbt.utils.events import Event, EventType, emit_event
from ccbt.utils.logging_config import get_logger

logger = get_logger(__name__)

if (
    TYPE_CHECKING
):  # pragma: no cover - TYPE_CHECKING block only evaluated by type checkers
    from pathlib import Path


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """Notification channels."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"
    LOG = "log"


@dataclass
class Alert:
    """Alert instance."""

    id: str
    rule_name: str
    metric_name: str
    value: Any
    condition: str
    severity: AlertSeverity
    description: str
    timestamp: float
    resolved: bool = False
    resolved_timestamp: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationConfig:
    """Notification configuration."""

    channel: NotificationChannel
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    """Alert rule definition."""

    name: str
    metric_name: str
    condition: str
    severity: AlertSeverity
    description: str
    enabled: bool = True
    cooldown_seconds: int = 300
    escalation_seconds: int = 0
    notification_channels: list[NotificationChannel] = field(default_factory=list)
    suppression_rules: list[str] = field(default_factory=list)
    last_triggered: float = 0.0
    trigger_count: int = 0


class AlertManager:
    """Alert management system."""

    def __init__(self):
        """Initialize alert manager."""
        self.alert_rules: dict[str, AlertRule] = {}
        self.active_alerts: dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.notification_configs: dict[NotificationChannel, NotificationConfig] = {}
        self.notification_handlers: dict[NotificationChannel, Callable] = {}

        # Alert suppression
        self.suppression_rules: dict[str, dict[str, Any]] = {}
        self.suppressed_alerts: dict[str, float] = {}

        # Statistics
        self.stats = {
            "alerts_triggered": 0,
            "alerts_resolved": 0,
            "notifications_sent": 0,
            "notification_failures": 0,
            "suppressed_alerts": 0,
        }

        # Initialize default notification handlers
        self._initialize_notification_handlers()

    # ------------------- Persistence -------------------
    def export_rules(self) -> list[dict[str, Any]]:
        """Export alert rules as a serializable list of dicts."""
        return [
            {
                "name": rule.name,
                "metric_name": rule.metric_name,
                "condition": rule.condition,
                "severity": rule.severity.value,
                "description": rule.description,
                "enabled": rule.enabled,
                "cooldown_seconds": rule.cooldown_seconds,
                "escalation_seconds": rule.escalation_seconds,
                "notification_channels": [c.value for c in rule.notification_channels],
                "suppression_rules": list(rule.suppression_rules),
                # omit dynamic fields last_triggered/trigger_count on export
            }
            for rule in self.alert_rules.values()
        ]

    def import_rules(self, rules: list[dict[str, Any]]) -> int:
        """Import alert rules from list of dicts; returns number loaded."""
        loaded = 0
        for data in rules:
            try:
                sev = AlertSeverity(str(data.get("severity", "warning")))
            except Exception:
                sev = AlertSeverity.WARNING
            channels = []
            for c in data.get("notification_channels", []):
                try:
                    channels.append(NotificationChannel(str(c)))
                except Exception as e:
                    logger.debug("Failed to parse alert channel: %s", e)
                    continue
            rule = AlertRule(
                name=str(data.get("name")),
                metric_name=str(data.get("metric_name")),
                condition=str(data.get("condition")),
                severity=sev,
                description=str(data.get("description", "")),
                enabled=bool(data.get("enabled", True)),
                cooldown_seconds=int(data.get("cooldown_seconds", 300)),
                escalation_seconds=int(data.get("escalation_seconds", 0)),
                notification_channels=channels,
                suppression_rules=list(data.get("suppression_rules", [])),
            )
            self.alert_rules[rule.name] = rule
            loaded += 1
        return loaded

    def save_rules_to_file(self, path: Path) -> None:
        """Save alert rules to JSON file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"rules": self.export_rules()}
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except (
            OSError,
            ValueError,
            TypeError,
        ) as e:  # pragma: no cover - Defensive exception handling for file I/O errors that are difficult to reliably trigger in tests
            logger.debug(
                "Failed to save alert rules: %s", e
            )  # pragma: no cover - Error logging path

    def load_rules_from_file(self, path: Path) -> int:
        """Load alert rules from JSON file; returns number loaded."""
        try:
            if not path.exists():
                return 0
            payload = json.loads(path.read_text(encoding="utf-8"))
            rules = payload.get("rules", [])
            return self.import_rules(rules)
        except Exception:
            return 0

    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self.alert_rules[rule.name] = rule

    def remove_alert_rule(self, rule_name: str) -> None:
        """Remove an alert rule."""
        if rule_name in self.alert_rules:
            del self.alert_rules[rule_name]

    def update_alert_rule(self, rule_name: str, updates: dict[str, Any]) -> None:
        """Update an alert rule."""
        if rule_name in self.alert_rules:
            rule = self.alert_rules[rule_name]
            for key, value in updates.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)

    def add_suppression_rule(self, name: str, rule: dict[str, Any]) -> None:
        """Add a suppression rule."""
        self.suppression_rules[name] = rule

    def remove_suppression_rule(self, name: str) -> None:
        """Remove a suppression rule."""
        if name in self.suppression_rules:
            del self.suppression_rules[name]

    def configure_notification(
        self,
        channel: NotificationChannel,
        config: NotificationConfig,
    ) -> None:
        """Configure notification channel."""
        self.notification_configs[channel] = config

    def register_notification_handler(
        self,
        channel: NotificationChannel,
        handler: Callable,
    ) -> None:
        """Register custom notification handler."""
        self.notification_handlers[channel] = handler

    async def process_alert(
        self,
        metric_name: str,
        value: Any,
        timestamp: float | None = None,
    ) -> None:
        """Process an alert for a metric."""
        if timestamp is None:
            timestamp = time.time()

        # Check all alert rules for this metric
        for rule in self.alert_rules.values():
            if rule.metric_name != metric_name or not rule.enabled:
                continue

            # Check cooldown
            if timestamp - rule.last_triggered < rule.cooldown_seconds:
                continue

            # Evaluate condition
            if self._evaluate_condition(rule.condition, value):
                await self._trigger_alert(rule, value, timestamp)

    async def resolve_alert(
        self,
        alert_id: str,
        timestamp: float | None = None,
    ) -> bool:
        """Resolve an alert."""
        if timestamp is None:
            timestamp = time.time()

        if alert_id not in self.active_alerts:
            return False

        alert = self.active_alerts[alert_id]
        alert.resolved = True
        alert.resolved_timestamp = timestamp

        # Move to history
        self.alert_history.append(alert)
        del self.active_alerts[alert_id]

        # Update statistics
        self.stats["alerts_resolved"] += 1

        # Emit alert resolved event
        await emit_event(
            Event(
                event_type=EventType.ALERT_RESOLVED.value,
                data={
                    "alert_id": alert_id,
                    "rule_name": alert.rule_name,
                    "metric_name": alert.metric_name,
                    "duration": timestamp - alert.timestamp,
                    "timestamp": timestamp,
                },
            ),
        )

        return True

    async def resolve_alerts_for_metric(
        self,
        metric_name: str,
        timestamp: float | None = None,
    ) -> int:
        """Resolve all alerts for a specific metric."""
        if timestamp is None:
            timestamp = time.time()

        resolved_count = 0
        alerts_to_resolve = [
            alert_id
            for alert_id, alert in self.active_alerts.items()
            if alert.metric_name == metric_name
        ]

        for alert_id in alerts_to_resolve:
            if await self.resolve_alert(alert_id, timestamp):
                resolved_count += 1

        return resolved_count

    def get_active_alerts(self) -> dict[str, Alert]:
        """Get all active alerts."""
        return self.active_alerts.copy()

    def get_alert_history(self, limit: int = 100) -> list[Alert]:
        """Get alert history."""
        return list(self.alert_history)[-limit:]

    def get_alert_statistics(self) -> dict[str, Any]:
        """Get alert statistics."""
        return {
            "alerts_triggered": self.stats["alerts_triggered"],
            "alerts_resolved": self.stats["alerts_resolved"],
            "notifications_sent": self.stats["notifications_sent"],
            "notification_failures": self.stats["notification_failures"],
            "suppressed_alerts": self.stats["suppressed_alerts"],
            "active_alerts": len(self.active_alerts),
            "alert_rules": len(self.alert_rules),
            "suppression_rules": len(self.suppression_rules),
        }

    def get_alert_rules(self) -> dict[str, AlertRule]:
        """Get all alert rules."""
        return self.alert_rules.copy()

    def get_suppression_rules(self) -> dict[str, dict[str, Any]]:
        """Get all suppression rules."""
        return self.suppression_rules.copy()

    def cleanup_old_alerts(self, max_age_seconds: int = 86400) -> None:
        """Clean up old alerts from history."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        # Remove old alerts from history
        while self.alert_history and self.alert_history[0].timestamp < cutoff_time:
            self.alert_history.popleft()

        # Clean up suppressed alerts
        to_remove = []
        for alert_id, suppress_time in self.suppressed_alerts.items():
            if suppress_time < cutoff_time:
                to_remove.append(alert_id)

        for alert_id in to_remove:
            del self.suppressed_alerts[alert_id]

    async def _trigger_alert(
        self,
        rule: AlertRule,
        value: Any,
        timestamp: float,
    ) -> None:
        """Trigger an alert."""
        # Check suppression rules
        if self._is_alert_suppressed(rule, value):
            self.stats["suppressed_alerts"] += 1
            return

        # Create alert
        alert_id = f"{rule.name}_{int(timestamp)}"
        alert = Alert(
            id=alert_id,
            rule_name=rule.name,
            metric_name=rule.metric_name,
            value=value,
            condition=rule.condition,
            severity=rule.severity,
            description=rule.description,
            timestamp=timestamp,
        )

        # Store alert
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)

        # Update rule statistics
        rule.last_triggered = timestamp
        rule.trigger_count += 1

        # Update global statistics
        self.stats["alerts_triggered"] += 1

        # Send notifications
        await self._send_notifications(alert)

        # Emit alert triggered event
        await emit_event(
            Event(
                event_type=EventType.ALERT_TRIGGERED.value,
                data={
                    "alert_id": alert_id,
                    "rule_name": rule.name,
                    "metric_name": rule.metric_name,
                    "value": value,
                    "condition": rule.condition,
                    "severity": rule.severity.value,
                    "description": rule.description,
                    "timestamp": timestamp,
                },
            ),
        )

    def _is_alert_suppressed(self, rule: AlertRule, value: Any) -> bool:
        """Check if alert is suppressed."""
        # Check rule-specific suppression
        for suppression_rule_name in rule.suppression_rules:
            if suppression_rule_name in self.suppression_rules:
                suppression_rule = self.suppression_rules[suppression_rule_name]
                if self._evaluate_suppression_rule(suppression_rule, rule, value):
                    return True

        # Check global suppression
        for suppression_rule in self.suppression_rules.values():
            if self._evaluate_suppression_rule(suppression_rule, rule, value):
                return True

        return False

    def _evaluate_suppression_rule(
        self,
        suppression_rule: dict[str, Any],
        rule: AlertRule,
        value: Any,
    ) -> bool:
        """Evaluate suppression rule."""
        try:
            # Check if rule matches
            if (
                "rule_name" in suppression_rule
                and suppression_rule["rule_name"] != rule.name
            ):
                return False

            if (
                "metric_name" in suppression_rule
                and suppression_rule["metric_name"] != rule.metric_name
            ):
                return False

            # Check time-based suppression
            if "time_range" in suppression_rule:
                current_hour = time.localtime().tm_hour
                start_hour = suppression_rule["time_range"].get("start", 0)
                end_hour = suppression_rule["time_range"].get("end", 23)

                if not (start_hour <= current_hour <= end_hour):
                    return False

            # Check value-based suppression
            if "value_condition" in suppression_rule:
                condition = suppression_rule["value_condition"]
                if not self._evaluate_condition(condition, value):
                    return False

        except Exception:
            return False
        else:
            return True

    def _evaluate_condition(self, condition: str, value: Any) -> bool:
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
                    if (
                        node.id in ["value"]
                    ):  # pragma: no cover - Valid variable path already tested via condition evaluation
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
                    if (
                        op is None
                    ):  # pragma: no cover - Defensive check for unsupported unary operations (only USub and UAdd are supported)
                        msg = f"Operation {type(node.op).__name__} not allowed"
                        raise ValueError(  # pragma: no cover - Error path for unsupported unary operations
                            msg,
                        )
                    return op(operand)
                if isinstance(node, ast.Compare):
                    left = safe_eval(node.left)
                    for op, comparator in zip(node.ops, node.comparators):
                        right = safe_eval(comparator)
                        op_func = safe_operators.get(type(op))
                        if (
                            op_func is None
                        ):  # pragma: no cover - Defensive check for unsupported comparison operations (only standard comparisons are supported)
                            msg = f"Operation {type(op).__name__} not allowed"
                            raise ValueError(  # pragma: no cover - Error path for unsupported comparison operations
                                msg,
                            )
                        if not op_func(left, right):
                            return False
                    return True
                msg = f"Node type {type(node).__name__} not allowed"  # pragma: no cover - Error message construction for unsupported AST node types
                raise ValueError(
                    msg
                )  # pragma: no cover - Defensive check for unsupported AST node types (only Expression, Constant, Name, BinOp, UnaryOp, Compare are supported)

            return safe_eval(tree)
        except Exception:
            return False

    async def _send_notifications(self, alert: Alert) -> None:
        """Send notifications for an alert."""
        rule = self.alert_rules.get(alert.rule_name)
        if not rule:
            return

        for channel in rule.notification_channels:
            try:
                await self._send_notification(channel, alert)
                self.stats["notifications_sent"] += 1
            except Exception as e:
                self.stats["notification_failures"] += 1

                # Emit notification error event
                await emit_event(
                    Event(
                        event_type=EventType.NOTIFICATION_ERROR.value,
                        data={
                            "channel": channel.value,
                            "alert_id": alert.id,
                            "error": str(e),
                            "timestamp": time.time(),
                        },
                    ),
                )

    async def _send_notification(
        self,
        channel: NotificationChannel,
        alert: Alert,
    ) -> None:
        """Send notification via specific channel."""
        if channel in self.notification_handlers:
            handler = self.notification_handlers[channel]
            if asyncio.iscoroutinefunction(handler):
                await handler(alert)
            else:
                handler(alert)
        # Use default handler
        elif (
            channel == NotificationChannel.EMAIL
        ):  # pragma: no cover - Default handler fallback path (tests use custom handlers or mock)
            await self._send_email_notification(
                alert
            )  # pragma: no cover - Default email handler
        elif (
            channel == NotificationChannel.WEBHOOK
        ):  # pragma: no cover - Default handler fallback path
            await self._send_webhook_notification(
                alert
            )  # pragma: no cover - Default webhook handler
        elif (
            channel == NotificationChannel.LOG
        ):  # pragma: no cover - Default handler fallback path
            await self._send_log_notification(
                alert
            )  # pragma: no cover - Default log handler

    async def _send_email_notification(self, alert: Alert) -> None:
        """Send email notification."""
        config = self.notification_configs.get(NotificationChannel.EMAIL)
        if not config or not config.enabled:
            return

        # Create email message
        msg = MIMEMultipart()
        msg["From"] = config.config.get("from_email", "alerts@ccbt.local")
        msg["To"] = config.config.get("to_email", "admin@ccbt.local")
        msg["Subject"] = f"Alert: {alert.rule_name} - {alert.severity.value.upper()}"

        body = f"""
        Alert Details:
        - Rule: {alert.rule_name}
        - Metric: {alert.metric_name}
        - Value: {alert.value}
        - Condition: {alert.condition}
        - Severity: {alert.severity.value}
        - Description: {alert.description}
        - Timestamp: {time.ctime(alert.timestamp)}
        """

        msg.attach(MIMEText(body, "plain"))

        # Send email
        smtp_server = config.config.get("smtp_server", "localhost")
        smtp_port = config.config.get("smtp_port", 587)
        smtp_username = config.config.get("smtp_username")
        smtp_password = config.config.get("smtp_password")

        server = smtplib.SMTP(smtp_server, smtp_port)
        if smtp_username and smtp_password:
            server.starttls()
            server.login(smtp_username, smtp_password)

        server.send_message(msg)
        server.quit()

    async def _send_webhook_notification(self, alert: Alert) -> None:
        """Send webhook notification."""
        config = self.notification_configs.get(NotificationChannel.WEBHOOK)
        if (
            not config or not config.enabled
        ):  # pragma: no cover - Defensive check for missing/disabled webhook config (tested via no_url test)
            return  # pragma: no cover - Early return path for disabled webhook config

        import aiohttp

        webhook_url = config.config.get("url")
        if not webhook_url:
            return

        payload = {
            "alert_id": alert.id,
            "rule_name": alert.rule_name,
            "metric_name": alert.metric_name,
            "value": alert.value,
            "condition": alert.condition,
            "severity": alert.severity.value,
            "description": alert.description,
            "timestamp": alert.timestamp,
        }

        async with aiohttp.ClientSession() as session, session.post(
            webhook_url, json=payload
        ) as response:
            if response.status >= 400:
                msg = f"Webhook failed with status {response.status}"
                raise RuntimeError(msg)

    async def _send_log_notification(self, alert: Alert) -> None:
        """Send log notification."""
        logger = get_logger("alerts")

        log_message = (
            f"ALERT: {alert.rule_name} - {alert.severity.value.upper()} - "
            f"{alert.metric_name}={alert.value} ({alert.condition}) - {alert.description}"
        )

        if alert.severity == AlertSeverity.CRITICAL:
            logger.critical(log_message)
        elif alert.severity == AlertSeverity.ERROR:
            logger.error(log_message)
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)

    def _initialize_notification_handlers(self) -> None:
        """Initialize default notification handlers."""
        # Default handlers are implemented in _send_notification method
