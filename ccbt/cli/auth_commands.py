"""CLI commands for authenticated swarm security configuration."""

from __future__ import annotations

from typing import Any, Iterable, Optional

import click
from rich.console import Console
from rich.table import Table

from ccbt.cli.ssl_commands import _should_skip_project_local_write
from ccbt.config.config import get_config, init_config
from ccbt.i18n import _

console = Console()


def _normalize_discovery_mode(value: str) -> str:
    """Normalize discovery mode input to underscore style."""
    return str(value).strip().lower().replace("-", "_")


def _normalize_bool(value: str) -> bool:
    """Normalize string bool-like values."""
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _load_auth_config(ctx: Optional[click.Context]) -> tuple[Any, Any]:
    """Return config manager and authenticated swarm config block."""
    if ctx is None:
        config_manager = init_config()
    else:
        try:
            from ccbt.cli.main import _get_config_from_context

            config_manager = _get_config_from_context(ctx)
        except Exception:
            config_manager = init_config()

    config = config_manager.config
    security = getattr(config, "security", None)
    if security is None:
        msg = "No security configuration"
        raise RuntimeError(msg)
    auth_cfg = getattr(security, "authenticated_swarms", None)
    if auth_cfg is None:
        msg = "No authenticated swarms configuration"
        raise RuntimeError(msg)
    return config_manager, auth_cfg


def _persist_auth_config(config_manager: Any, message: str) -> None:
    """Persist config for auth changes with project-local safety behavior."""
    if config_manager.config_file:
        if _should_skip_project_local_write(config_manager.config_file):
            console.print(
                "[yellow]Authenticated swarm setting updated "
                "(test mode, write skipped)[/yellow]"
            )
            return
        config_toml = config_manager.export(fmt="toml")
        config_manager.config_file.write_text(config_toml, encoding="utf-8")
        console.print(f"[green]{message}: {config_manager.config_file}[/green]")
    else:
        console.print(
            "[yellow]Authenticated swarm setting updated "
            "(configuration not persisted - no config file)[/yellow]"
        )


@click.group("auth")
def auth() -> None:
    """Manage authenticated-swarms configuration."""


@auth.command("status")
@click.pass_context
def auth_status(_ctx) -> None:
    """Show authenticated swarms settings."""
    try:
        cfg = get_config()
        security = getattr(cfg, "security", None)
        if security is None:
            console.print(_("[yellow]No security configuration loaded[/yellow]"))
            return

        auth_cfg = getattr(security, "authenticated_swarms", None)
        if auth_cfg is None:
            console.print(
                _("[yellow]No authenticated swarms configuration found[/yellow]")
            )
            return

        table = Table(title="Authenticated Swarms", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        trusted_ids = getattr(auth_cfg, "trusted_swarm_ids", [])
        if isinstance(trusted_ids, list):
            trusted_display = ", ".join(trusted_ids) if trusted_ids else "none"
        else:
            trusted_display = "invalid"

        table.add_row("Mode", str(getattr(auth_cfg, "mode", "off")))
        table.add_row(
            "Discovery Mode", str(getattr(auth_cfg, "discovery_mode", "trackers_only"))
        )
        table.add_row(
            "Discovery strict for strict mode",
            str(bool(getattr(auth_cfg, "discovery_strict_for_strict_mode", False))),
        )
        table.add_row("Trusted swarm IDs", trusted_display)
        table.add_row(
            "Fail closed on parse errors",
            str(bool(getattr(auth_cfg, "fail_closed_on_parse_errors", False))),
        )
        table.add_row(
            "Trust store path",
            str(getattr(auth_cfg, "trust_store_path", "")) or "not configured",
        )
        table.add_row(
            "Trust store refresh interval (s)",
            str(float(getattr(auth_cfg, "trust_store_refresh_interval_s", 60.0))),
        )
        table.add_row(
            "Revocation profile path",
            str(getattr(auth_cfg, "revocation_profile_path", "")) or "not configured",
        )
        table.add_row(
            "Revocation refresh interval (s)",
            str(float(getattr(auth_cfg, "revocation_refresh_interval_s", 300.0))),
        )

        console.print(table)
    except Exception as e:  # pragma: no cover - CLI error handler
        console.print(
            _("[red]Error reading authenticated swarm status: {e}[/red]").format(e=e)
        )
        raise click.Abort from e


@auth.command("set-mode")
@click.argument(
    "mode", type=click.Choice(["off", "opportunistic", "strict"], case_sensitive=False)
)
@click.pass_context
def auth_set_mode(ctx, mode: str) -> None:
    """Set authenticated-swarms admission mode."""
    try:
        config_manager, auth_cfg = _load_auth_config(ctx)
        auth_cfg.mode = str(mode).strip().lower()
        _persist_auth_config(
            config_manager,
            f"Authenticated swarm mode set to {auth_cfg.mode}",
        )
    except Exception as e:  # pragma: no cover - CLI error handler
        console.print(
            _("[red]Error updating authenticated swarm mode: {e}[/red]").format(e=e)
        )
        raise click.Abort from e


@auth.command("set-discovery-mode")
@click.argument(
    "mode",
    type=click.Choice(
        [
            "full",
            "trackers_only",
            "dht_only",
            "pex_off",
            "trackers-only",
            "dht-only",
            "pex-off",
        ],
        case_sensitive=False,
    ),
)
@click.pass_context
def auth_set_discovery_mode(ctx, mode: str) -> None:
    """Set authenticated-swarms discovery mode."""
    normalized = _normalize_discovery_mode(mode)
    try:
        config_manager, auth_cfg = _load_auth_config(ctx)
        auth_cfg.discovery_mode = normalized
        _persist_auth_config(
            config_manager,
            f"Authenticated swarm discovery mode set to {auth_cfg.discovery_mode}",
        )
    except Exception as e:  # pragma: no cover - CLI error handler
        console.print(_("[red]Error updating discovery mode: {e}[/red]").format(e=e))
        raise click.Abort from e


@auth.command("set-discovery-strict")
@click.argument(
    "enabled",
    type=click.Choice(["true", "false", "1", "0", "yes", "no"], case_sensitive=False),
)
@click.pass_context
def auth_set_discovery_strict(ctx, enabled: str) -> None:
    """Set whether strict mode enables strict discovery policy."""
    try:
        config_manager, auth_cfg = _load_auth_config(ctx)
        auth_cfg.discovery_strict_for_strict_mode = _normalize_bool(enabled)
        _persist_auth_config(
            config_manager,
            f"Authenticated swarm strict discovery set to {auth_cfg.discovery_strict_for_strict_mode}",
        )
    except Exception as e:  # pragma: no cover - CLI error handler
        console.print(
            _("[red]Error updating strict discovery mode: {e}[/red]").format(e=e)
        )
        raise click.Abort from e


@auth.command("set-trusted-ids")
@click.argument("ids", nargs=-1)
@click.option("--clear", "-C", is_flag=True, default=False)
@click.pass_context
def auth_set_trusted_ids(ctx, ids: Iterable[str], clear: bool) -> None:
    """Set explicit trusted swarm ids list."""
    try:
        config_manager, auth_cfg = _load_auth_config(ctx)
        if clear:
            auth_cfg.trusted_swarm_ids = []
        else:
            auth_cfg.trusted_swarm_ids = [str(v).strip() for v in ids if str(v).strip()]
        _persist_auth_config(config_manager, "Updated trusted swarm IDs")
    except Exception as e:  # pragma: no cover - CLI error handler
        console.print(_("[red]Error updating trusted IDs: {e}[/red]").format(e=e))
        raise click.Abort from e


@auth.command("set-fail-closed-on-parse-errors")
@click.argument(
    "enabled",
    type=click.Choice(["true", "false", "1", "0", "yes", "no"], case_sensitive=False),
)
@click.pass_context
def auth_set_parse_failure_mode(ctx, enabled: str) -> None:
    """Set fail-closed behavior for parse/reload errors."""
    try:
        config_manager, auth_cfg = _load_auth_config(ctx)
        auth_cfg.fail_closed_on_parse_errors = _normalize_bool(enabled)
        _persist_auth_config(
            config_manager,
            f"Updated fail-closed parse-policy to {auth_cfg.fail_closed_on_parse_errors}",
        )
    except Exception as e:  # pragma: no cover - CLI error handler
        console.print(
            _("[red]Error updating parse-policy behavior: {e}[/red]").format(e=e)
        )
        raise click.Abort from e
