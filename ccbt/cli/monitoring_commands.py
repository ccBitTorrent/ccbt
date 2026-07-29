"""Monitoring CLI commands (dashboard, alerts, metrics)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Optional

import click
from rich.console import Console

from ccbt.i18n import _
from ccbt.monitoring import get_alert_manager

logger = logging.getLogger(__name__)

# Exception messages
DAEMON_STARTUP_FAILED_MSG = "Daemon startup failed"
SESSION_CREATION_FAILED_MSG = "Session creation failed"


@click.command("dashboard")
@click.option(
    "--refresh",
    "-r",
    type=float,
    default=1.0,
    help="Refresh interval (s)",
)
@click.option(
    "--rules",
    "-f",
    type=click.Path(),
    default=None,
    help="Path to alert rules JSON to load on start",
)
@click.option(
    "--no-splash",
    "-a",
    is_flag=True,
    help="Disable splash screen (useful for debugging)",
)
def dashboard(refresh: float, rules: Optional[str], no_splash: bool) -> None:
    """Start terminal monitoring dashboard (Textual)."""
    console = Console()

    # Import here to avoid circular imports
    import click

    from ccbt.cli.verbosity import get_verbosity_from_ctx
    from ccbt.interface.terminal_dashboard import (
        _prepare_dashboard_session,
        _show_startup_splash,
        run_dashboard,
    )

    # Get verbosity from context (defaults to 0 = NORMAL)
    ctx = click.get_current_context(silent=True)
    verbosity = get_verbosity_from_ctx(ctx.obj if ctx and hasattr(ctx, "obj") else None)
    verbosity_count = verbosity.verbosity_count

    # Start splash screen if enabled (only for daemon mode)
    splash_manager = None
    splash_manager, _splash_thread = _show_startup_splash(
        no_splash=no_splash,
        verbosity_count=verbosity_count,
        console=console,
    )
    session: Optional[Any] = (
        None  # Optional[AsyncSessionManager | DaemonInterfaceAdapter]
    )
    # ALWAYS use daemon - try to ensure it's running
    try:
        import sys

        success, session = asyncio.run(
            _prepare_dashboard_session(splash_manager=splash_manager)
        )
        if success and session:
            if not splash_manager:  # Only print if splash not shown
                console.print(_("[green]Connected to daemon[/green]"))
        else:
            # Daemon start failed - show error and exit
            console.print(
                _(
                    "[red]Failed to start daemon. Cannot proceed without daemon.[/red]\n"
                    "[yellow]Please check:[/yellow]\n"
                    "  1. Daemon logs for startup errors\n"
                    "  2. Port conflicts (check if port is already in use)\n"
                    "  3. Permissions (ensure you have permission to start daemon)\n\n"
                    "[cyan]To start daemon manually: 'btbt daemon start'[/cyan]"
                )
            )
            raise click.ClickException(DAEMON_STARTUP_FAILED_MSG)
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error ensuring daemon is running: {e}[/red]").format(e=e))
        raise click.ClickException(DAEMON_STARTUP_FAILED_MSG) from e

    if session is None:
        console.print(_("[red]Failed to create session[/red]"))
        raise click.ClickException(SESSION_CREATION_FAILED_MSG)

    if sys.platform == "win32":
        import time

        time.sleep(0.5)

    try:
        # CRITICAL: Do NOT call session.start() here in a throwaway asyncio.run().
        # Doing so binds the aiohttp ClientSession + WebSocket tasks to a loop that
        # closes before Textual starts its own loop, leaving the adapter with a dead
        # connection (_websocket_connected=True on a closed loop). The adapter is
        # started inside Textual's event loop by TerminalDashboard.on_mount ->
        # _ensure_adapter_ready() -> await self.session.start(). The IPCClient's
        # _ensure_session() recreates the aiohttp session on Textual's loop on first
        # use, so the IPCClient returned by _ensure_daemon_running() is safe to reuse.

        # If rules path provided, pre-load into global alert manager before launching
        if rules:
            try:
                from pathlib import Path

                am = get_alert_manager()
                am.load_rules_from_file(Path(rules))  # type: ignore[attr-defined]
                console.print(
                    _("[green]Loaded alert rules from {path}[/green]").format(
                        path=rules
                    )
                )
            except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
                console.print(
                    _("[red]Failed to load alert rules: {e}[/red]").format(e=e)
                )
        # Pass splash_manager to run_dashboard so it can end when dashboard is rendered
        run_dashboard(session, refresh=refresh, splash_manager=splash_manager)
    except KeyboardInterrupt:
        # Treat user interrupt as graceful dashboard exit instead of an error.
        console.print(_("[yellow]Dashboard stopped (interrupt received).[/yellow]"))
        # Clear splash on interrupt
        if splash_manager:
            with contextlib.suppress(Exception):
                splash_manager.stop_splash()
        return
    except click.Abort:
        # Click maps EOF/terminal abort to click.Abort. For Textual this often means
        # the command was launched without an interactive TTY, so the dashboard cannot
        # stay attached to a terminal UI.
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise click.ClickException(
                _(
                    "Dashboard requires an interactive terminal (TTY). "
                    "Please run 'btbt dashboard --no-splash' in a regular terminal window."
                )
            ) from None
        # Interactive terminal + abort: keep Click's native behavior.
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        # Clear splash on error
        if splash_manager:
            with contextlib.suppress(Exception):
                splash_manager.stop_splash()
        console.print(_("[red]Dashboard error: {e}[/red]").format(e=e))
        raise
    finally:
        # Ensure splash is cleared on exit
        if splash_manager:
            try:
                splash_manager.stop_splash()
                # Restore log level if it was suppressed
                import logging

                root_logger = logging.getLogger()
                original_level = getattr(splash_manager, "_original_log_level", None)
                if original_level:
                    root_logger.setLevel(original_level)
            except Exception:
                pass


@click.command("alerts")
@click.option("--list", "-L", "list_", is_flag=True, help="List alert rules")
@click.option("--list-active", "-I", is_flag=True, help="List active alerts")
@click.option("--add", "-a", "add_rule", is_flag=True, help="Add an alert rule")
@click.option(
    "--remove", "-R", "remove_rule", is_flag=True, help="Remove an alert rule"
)
@click.option("--clear-active", "-C", is_flag=True, help="Resolve all active alerts")
@click.option(
    "--test",
    "-t",
    "test_rule",
    is_flag=True,
    help="Test a rule by evaluating a value",
)
@click.option(
    "--load",
    "-l",
    type=click.Path(),
    default=None,
    help="Load alert rules from JSON file",
)
@click.option(
    "--save",
    "-s",
    type=click.Path(),
    default=None,
    help="Save alert rules to JSON file",
)
@click.option("--name", "-n", type=str, default=None, help="Rule name")
@click.option("--metric", "-m", type=str, default=None, help="Metric name for rule")
@click.option(
    "--condition",
    "-c",
    type=str,
    default=None,
    help="Condition expression, e.g., 'value > 80'",
)
@click.option(
    "--severity",
    "-e",
    type=click.Choice(["info", "warning", "error", "critical"]),
    default="warning",
)
@click.option(
    "--value",
    "-V",
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
    load: Optional[str],
    save: Optional[str],
    name: Optional[str],
    metric: Optional[str],
    condition: Optional[str],
    severity: str,
    value: Optional[str],
) -> None:
    """Manage alert rules (add/list/remove/test/clear)."""
    console = Console()
    am = get_alert_manager()
    # Load/save first if requested
    if load or save:
        # Resolve default path from config if not provided
        try:
            from ccbt.config.config import get_config

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
                _("[green]Loaded {count} alert rules from {path}[/green]").format(
                    count=count, path=rules_path
                ),
            )
        except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
            console.print(_("[red]Failed to load rules: {e}[/red]").format(e=e))
        return
    if save:
        try:
            from pathlib import Path

            rules_path = Path(save or default_path)
            am.save_rules_to_file(rules_path)  # type: ignore[attr-defined]
            console.print(
                _("[green]Saved alert rules to {path}[/green]").format(path=rules_path)
            )
        except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
            console.print(_("[red]Failed to save rules: {e}[/red]").format(e=e))
        return

    if list_:
        if not getattr(am, "alert_rules", None):
            console.print(_("[yellow]No alert rules defined[/yellow]"))
            return
        for rn, rule in am.alert_rules.items():
            console.print(
                _(
                    "- {name}: metric={metric}, cond={condition}, severity={severity}"
                ).format(
                    name=rn,
                    metric=rule.metric_name,
                    condition=rule.condition,
                    severity=getattr(rule.severity, "value", rule.severity),
                ),
            )
        return
    if list_active:
        active = getattr(am, "active_alerts", {})
        if not active:
            console.print(_("[yellow]No active alerts[/yellow]"))
            return
        for aid, alert in active.items():
            sev = getattr(alert.severity, "value", str(alert.severity))
            console.print(
                _("- {id}: {severity} rule={rule} value={value}").format(
                    id=aid, severity=sev, rule=alert.rule_name, value=alert.value
                )
            )
        return
    if add_rule:
        if not all([name, metric, condition]):
            console.print(
                _(
                    "[red]--name, --metric and --condition are required to add a rule[/red]"
                ),
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
        console.print(_("[green]Added alert rule {name}[/green]").format(name=name))
        return
    if remove_rule:
        if not name:
            console.print(_("[red]--name is required to remove a rule[/red]"))
            return
        am.remove_alert_rule(name)
        console.print(_("[green]Removed alert rule {name}[/green]").format(name=name))
        return
    if clear_active:
        try:
            for aid in list(getattr(am, "active_alerts", {}).keys()):
                asyncio.run(am.resolve_alert(aid))
            console.print(_("[green]Cleared all active alerts[/green]"))
        except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
            console.print(
                _("[red]Failed to clear active alerts: {e}[/red]").format(e=e)
            )
        return
    if test_rule:
        if not name:
            console.print(_("[red]--name is required to test a rule[/red]"))
            return
        if not value:
            console.print(_("[red]--value is required with --test[/red]"))
            return
        rule = getattr(am, "alert_rules", {}).get(name)
        if not rule:
            console.print(_("[red]Rule not found: {name}[/red]").format(name=name))
            return
        try:
            v_any = float(value) if value.replace(".", "", 1).isdigit() else value
        except Exception:  # pragma: no cover - Defensive exception handler for edge cases in float conversion that are difficult to trigger in practice
            v_any = value
        try:
            asyncio.run(am.process_alert(rule.metric_name, v_any))
            console.print(
                _("[green]Tested rule {name} with value {value}[/green]").format(
                    name=name, value=v_any
                )
            )
        except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
            console.print(_("[red]Failed to test rule: {e}[/red]").format(e=e))
        return
    console.print(
        _(
            "[yellow]Use --list/--list-active, --add, --remove, --clear-active, --test, --load or --save[/yellow]"
        ),
    )


@click.command("metrics")
@click.option(
    "--format",
    "-f",
    "format_",
    type=click.Choice(["json", "prometheus"]),
    default="json",
    help="Export format",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file (defaults to stdout)",
)
@click.option(
    "--duration",
    "-d",
    type=float,
    default=0.0,
    help="Collect for N seconds (0 = once)",
)
@click.option(
    "--interval",
    "-i",
    type=float,
    default=None,
    help="Collection interval seconds (defaults to config)",
)
@click.option(
    "--include-system",
    "-s",
    is_flag=True,
    help="Include system metrics snapshot in JSON output",
)
@click.option(
    "--include-performance",
    "-p",
    is_flag=True,
    help="Include performance metrics snapshot in JSON output",
)
def metrics(
    format_: str,
    output: Optional[str],
    duration: float,
    interval: Optional[float],
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
            logger.debug(_("Failed to collect system metrics: %s"), e)
        try:
            await mc.collect_performance_metrics()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug(_("Failed to collect performance metrics: %s"), e)
        try:
            await mc._collect_custom_metrics()  # noqa: SLF001
        except Exception as e:
            logger.debug(_("Failed to collect custom metrics: %s"), e)

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
            from ccbt.config.config import get_config

            cfg_iv = float(get_config().observability.metrics_interval)
        except Exception as e:
            logger.debug(_("Failed to get metrics interval from config: %s"), e)

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
            console.print(
                _("[green]Wrote metrics to {path}[/green]").format(path=output)
            )
        # Print to stdout
        elif format_ == "prometheus":
            # Avoid Rich formatting for Prometheus text exposition
            click.echo(result)
        else:
            console.print(result)
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(_("[red]Metrics error: {e}[/red]").format(e=e))
