"""Alerts dashboard monitoring screen."""

from __future__ import annotations

import time as time_module
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

from rich.panel import Panel
from rich.table import Table

from ccbt.interface.screens.base import MonitoringScreen


class AlertsDashboardScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display enhanced alerts with filtering and management."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #rules_table {
        height: 1fr;
    }
    #active_alerts {
        height: 1fr;
    }
    #alert_history {
        height: 1fr;
        min-height: 5;
    }
    #statistics {
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the alerts dashboard screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="active_alerts")
            yield Static(id="alert_history")
            yield Static(id="statistics")
        yield Footer()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh alerts display."""
        try:
            content = self.query_one("#content", Static)
            active_alerts = self.query_one("#active_alerts", Static)
            alert_history = self.query_one("#alert_history", Static)
            statistics = self.query_one("#statistics", Static)

            # Alert rules table
            if getattr(self.alert_manager, "alert_rules", None):
                rules_table = Table(title="Alert Rules", expand=True)
                rules_table.add_column("Name", style="cyan", ratio=2)
                rules_table.add_column("Metric", style="green", ratio=2)
                rules_table.add_column("Condition", style="dim", ratio=2)
                rules_table.add_column("Severity", style="red", ratio=1)
                rules_table.add_column("Enabled", style="yellow", ratio=1)

                for rule_name, rule in self.alert_manager.alert_rules.items():
                    severity_str = getattr(rule.severity, "value", str(rule.severity))
                    rules_table.add_row(
                        rule_name,
                        rule.metric_name,
                        rule.condition,
                        severity_str,
                        "Yes" if rule.enabled else "No",
                    )

                content.update(Panel(rules_table))
            else:
                content.update(Panel("No alert rules configured", title="Alert Rules"))

            # Active alerts
            if (
                getattr(self.alert_manager, "active_alerts", None)
                and self.alert_manager.active_alerts
            ):
                act_table = Table(title="Active Alerts", expand=True)
                act_table.add_column("Severity", style="red", ratio=1)
                act_table.add_column("Rule", style="yellow", ratio=2)
                act_table.add_column("Metric", style="cyan", ratio=2)
                act_table.add_column("Value", style="green", ratio=2)
                act_table.add_column("Time", style="dim", ratio=2)

                for alert in list(self.alert_manager.active_alerts.values())[
                    :20
                ]:  # Limit to 20
                    severity_str = self._format_alert_severity(alert.severity)
                    time_str = time_module.strftime(
                        "%H:%M:%S", time_module.localtime(alert.timestamp)
                    )
                    act_table.add_row(
                        severity_str,
                        alert.rule_name,
                        alert.metric_name,
                        str(alert.value),
                        time_str,
                    )

                active_alerts.update(Panel(act_table))
            else:
                active_alerts.update(Panel("No active alerts", title="Active Alerts"))

            # Alert history
            if getattr(self.alert_manager, "alert_history", None):
                history_list = list(self.alert_manager.alert_history)[-50:]  # Last 50
                if history_list:
                    hist_table = Table(title="Alert History (Last 50)", expand=True)
                    hist_table.add_column("Severity", style="red", ratio=1)
                    hist_table.add_column("Rule", style="yellow", ratio=2)
                    hist_table.add_column("Value", style="green", ratio=2)
                    hist_table.add_column("Time", style="dim", ratio=2)
                    hist_table.add_column("Resolved", style="dim", ratio=1)

                    for alert in reversed(history_list):  # Most recent first
                        severity_str = self._format_alert_severity(alert.severity)
                        time_str = time_module.strftime(
                            "%H:%M:%S", time_module.localtime(alert.timestamp)
                        )
                        resolved_str = "Yes" if alert.resolved else "No"
                        hist_table.add_row(
                            severity_str,
                            alert.rule_name,
                            str(alert.value),
                            time_str,
                            resolved_str,
                        )

                    alert_history.update(Panel(hist_table))
                else:
                    alert_history.update(
                        Panel("No alert history", title="Alert History")
                    )
            else:
                alert_history.update(
                    Panel("Alert history not available", title="Alert History")
                )

            # Statistics
            stats = getattr(self.alert_manager, "stats", {})
            stats_table = Table(
                title="Alert Statistics", expand=True, show_header=False, box=None
            )
            stats_table.add_column("Statistic", style="cyan", ratio=1)
            stats_table.add_column("Value", style="green", ratio=2)

            stats_table.add_row(
                "Alerts Triggered", str(stats.get("alerts_triggered", 0))
            )
            stats_table.add_row("Alerts Resolved", str(stats.get("alerts_resolved", 0)))
            stats_table.add_row(
                "Notifications Sent", str(stats.get("notifications_sent", 0))
            )
            stats_table.add_row(
                "Notification Failures", str(stats.get("notification_failures", 0))
            )
            stats_table.add_row(
                "Suppressed Alerts", str(stats.get("suppressed_alerts", 0))
            )

            statistics.update(Panel(stats_table))

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading alerts: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    def _format_alert_severity(self, severity: Any) -> str:  # pragma: no cover
        """Format alert severity with colors.

        Args:
            severity: AlertSeverity enum or string

        Returns:
            Formatted severity string
        """
        from ccbt.monitoring.alert_manager import AlertSeverity

        if isinstance(severity, AlertSeverity):
            sev_str = severity.value
        else:
            sev_str = str(severity)

        if sev_str == "critical":
            return f"[bold red]{sev_str.upper()}[/bold red]"
        if sev_str == "error":
            return f"[red]{sev_str.upper()}[/red]"
        if sev_str == "warning":
            return f"[yellow]{sev_str.upper()}[/yellow]"
        return f"[dim]{sev_str.upper()}[/dim]"

