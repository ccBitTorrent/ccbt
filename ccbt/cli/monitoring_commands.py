"""Monitoring CLI commands (dashboard, alerts, metrics)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import click
from rich.console import Console

from ccbt.interface.terminal_dashboard import run_dashboard
from ccbt.monitoring import get_alert_manager
from ccbt.session.session import AsyncSessionManager

logger = logging.getLogger(__name__)


@click.command("dashboard")
@click.option("--refresh", type=float, default=1.0, help="Refresh interval (s)")
@click.option(
    "--rules",
    type=click.Path(),
    default=None,
    help="Path to alert rules JSON to load on start",
)
def dashboard(refresh: float, rules: str | None) -> None:
    """Start terminal monitoring dashboard (Textual)."""
    console = Console()
    try:
        session = AsyncSessionManager(".")
        # If rules path provided, pre-load into global alert manager before launching
        if rules:
            try:
                from pathlib import Path

                am = get_alert_manager()
                am.load_rules_from_file(Path(rules))  # type: ignore[attr-defined]
                console.print(f"[green]Loaded alert rules from {rules}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to load alert rules: {e}[/red]")
        run_dashboard(session, refresh=refresh)
    except Exception as e:
        console.print(f"[red]Dashboard error: {e}[/red]")


@click.command("alerts")
@click.option("--list", "list_", is_flag=True, help="List alert rules")
@click.option("--list-active", is_flag=True, help="List active alerts")
@click.option("--add", "add_rule", is_flag=True, help="Add an alert rule")
@click.option("--remove", "remove_rule", is_flag=True, help="Remove an alert rule")
@click.option("--clear-active", is_flag=True, help="Resolve all active alerts")
@click.option(
    "--test",
    "test_rule",
    is_flag=True,
    help="Test a rule by evaluating a value",
)
@click.option(
    "--load",
    type=click.Path(),
    default=None,
    help="Load alert rules from JSON file",
)
@click.option(
    "--save",
    type=click.Path(),
    default=None,
    help="Save alert rules to JSON file",
)
@click.option("--name", type=str, default=None, help="Rule name")
@click.option("--metric", type=str, default=None, help="Metric name for rule")
@click.option(
    "--condition",
    type=str,
    default=None,
    help="Condition expression, e.g., 'value > 80'",
)
@click.option(
    "--severity",
    type=click.Choice(["info", "warning", "error", "critical"]),
    default="warning",
)
@click.option(
    "--value",
    type=str,
    default=None,
    help="Value to evaluate when using --test",
)
def alerts(
    list_: bool,
    list_active: bool,
    add_rule: bool,
    remove_rule: bool,
    clear_active: bool,
    test_rule: bool,
    load: str | None,
    save: str | None,
    name: str | None,
    metric: str | None,
    condition: str | None,
    severity: str,
    value: str | None,
) -> None:
    """Manage alert rules (add/list/remove/test/clear)."""
    console = Console()
    am = get_alert_manager()
    # Load/save first if requested
    if load or save:
        # Resolve default path from config if not provided
        try:
            from ccbt.config.config import get_config  # type: ignore[import-untyped]

            default_path = getattr(
                get_config().observability,
                "alerts_rules_path",
                ".ccbt/alerts.json",
            )
        except Exception:
            default_path = ".ccbt/alerts.json"
    if load:
        try:
            from pathlib import Path

            rules_path = Path(load or default_path)
            count = am.load_rules_from_file(rules_path)  # type: ignore[attr-defined]
            console.print(
                f"[green]Loaded {count} alert rules from {rules_path}[/green]",
            )
        except Exception as e:
            console.print(f"[red]Failed to load rules: {e}[/red]")
        return
    if save:
        try:
            from pathlib import Path

            rules_path = Path(save or default_path)
            am.save_rules_to_file(rules_path)  # type: ignore[attr-defined]
            console.print(f"[green]Saved alert rules to {rules_path}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to save rules: {e}[/red]")
        return

    if list_:
        if not getattr(am, "alert_rules", None):
            console.print("[yellow]No alert rules defined[/yellow]")
            return
        for rn, rule in am.alert_rules.items():
            console.print(
                f"- {rn}: metric={rule.metric_name}, cond={rule.condition}, severity={getattr(rule.severity, 'value', rule.severity)}",
            )
        return
    if list_active:
        active = getattr(am, "active_alerts", {})
        if not active:
            console.print("[yellow]No active alerts[/yellow]")
            return
        for aid, alert in active.items():
            sev = getattr(alert.severity, "value", str(alert.severity))
            console.print(f"- {aid}: {sev} rule={alert.rule_name} value={alert.value}")
        return
    if add_rule:
        if not all([name, metric, condition]):
            console.print(
                "[red]--name, --metric and --condition are required to add a rule[/red]",
            )
            return
        from ccbt.monitoring.alert_manager import AlertRule, AlertSeverity

        sev = {
            "info": AlertSeverity.INFO,
            "warning": AlertSeverity.WARNING,
            "error": AlertSeverity.ERROR,
            "critical": AlertSeverity.CRITICAL,
        }[severity]
        am.add_alert_rule(
            AlertRule(
                name=str(name),
                metric_name=str(metric),
                condition=str(condition),
                severity=sev,
                description=f"Rule {name}",
            ),
        )
        console.print(f"[green]Added alert rule {name}[/green]")
        return
    if remove_rule:
        if not name:
            console.print("[red]--name is required to remove a rule[/red]")
            return
        am.remove_alert_rule(name)
        console.print(f"[green]Removed alert rule {name}[/green]")
        return
    if clear_active:
        try:
            for aid in list(getattr(am, "active_alerts", {}).keys()):
                asyncio.run(am.resolve_alert(aid))
            console.print("[green]Cleared all active alerts[/green]")
        except Exception as e:
            console.print(f"[red]Failed to clear active alerts: {e}[/red]")
        return
    if test_rule:
        if not name:
            console.print("[red]--name is required to test a rule[/red]")
            return
        if not value:
            console.print("[red]--value is required with --test[/red]")
            return
        rule = getattr(am, "alert_rules", {}).get(name)
        if not rule:
            console.print(f"[red]Rule not found: {name}[/red]")
            return
        try:
            v_any = float(value) if value.replace(".", "", 1).isdigit() else value
        except Exception:
            v_any = value
        try:
            asyncio.run(am.process_alert(rule.metric_name, v_any))
            console.print(f"[green]Tested rule {name} with value {v_any}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to test rule: {e}[/red]")
        return
    console.print(
        "[yellow]Use --list/--list-active, --add, --remove, --clear-active, --test, --load or --save[/yellow]",
    )


@click.command("metrics")
@click.option(
    "--format",
    "format_",
    type=click.Choice(["json", "prometheus"]),
    default="json",
    help="Export format",
)
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help="Output file (defaults to stdout)",
)
@click.option(
    "--duration",
    type=float,
    default=0.0,
    help="Collect for N seconds (0 = once)",
)
@click.option(
    "--interval",
    type=float,
    default=None,
    help="Collection interval seconds (defaults to config)",
)
@click.option(
    "--include-system",
    is_flag=True,
    help="Include system metrics snapshot in JSON output",
)
@click.option(
    "--include-performance",
    is_flag=True,
    help="Include performance metrics snapshot in JSON output",
)
def metrics(
    format_: str,
    output: str | None,
    duration: float,
    interval: float | None,
    include_system: bool,
    include_performance: bool,
) -> None:
    """Collect and export metrics (JSON or Prometheus)."""
    console = Console()
    from pathlib import Path

    from ccbt.monitoring import MetricsCollector

    async def _collect_once(mc: MetricsCollector) -> None:
        # One-shot collection, without starting the background loop
        try:
            await mc.collect_system_metrics()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Failed to collect system metrics: %s", e)
        try:
            await mc.collect_performance_metrics()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Failed to collect performance metrics: %s", e)
        try:
            await mc._collect_custom_metrics()  # noqa: SLF001
        except Exception as e:
            logger.debug("Failed to collect custom metrics: %s", e)

    async def _collect_duration(
        mc: MetricsCollector,
        seconds: float,
        iv: float,
    ) -> None:
        with contextlib.suppress(Exception):
            mc.collection_interval = max(0.2, float(iv))
        await mc.start()
        try:
            # Sleep for duration, then stop
            await asyncio.sleep(max(0.0, seconds))
        finally:
            await mc.stop()

    async def _run() -> str:
        # Load interval from config if not provided
        cfg_iv = 5.0
        try:
            # lazy import to avoid cycles
            from ccbt.config.config import get_config  # type: ignore[import-untyped]

            cfg_iv = float(get_config().observability.metrics_interval)
        except Exception as e:
            logger.debug("Failed to get metrics interval from config: %s", e)

        mc = MetricsCollector()
        if duration and duration > 0:
            await _collect_duration(
                mc,
                duration,
                interval if interval is not None else cfg_iv,
            )
        else:
            await _collect_once(mc)

        if format_ == "prometheus":
            return mc._export_prometheus_format()  # noqa: SLF001

        # JSON
        import json

        payload: dict[str, Any] = {
            "metrics": mc.get_all_metrics(),
        }
        if include_system:
            with contextlib.suppress(Exception):
                payload["system"] = mc.get_system_metrics()
        if include_performance:
            with contextlib.suppress(Exception):
                payload["performance"] = mc.get_performance_metrics()
        return json.dumps(payload, indent=2)

    try:
        result = asyncio.run(_run())
        if output:
            Path(output).write_text(result, encoding="utf-8")
            console.print(f"[green]Wrote metrics to {output}[/green]")
        # Print to stdout
        elif format_ == "prometheus":
            # Avoid Rich formatting for Prometheus text exposition
            click.echo(result)
        else:
            console.print(result)
    except Exception as e:
        console.print(f"[red]Metrics error: {e}[/red]")
