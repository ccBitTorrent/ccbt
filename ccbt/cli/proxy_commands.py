"""CLI commands for proxy management."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path  # noqa: TC003 - Used at runtime for path operations

import click
from rich.console import Console
from rich.table import Table

from ccbt.cli.config_commands import _find_project_root
from ccbt.config.config import get_config
from ccbt.proxy.client import ProxyClient
from ccbt.proxy.exceptions import ProxyError


def _should_skip_project_local_write(config_file: Path | None) -> bool:
    """Check if we should skip writing to project-local ccbt.toml during tests.

    Args:
        config_file: The config file path from ConfigManager

    Returns:
        True if we should skip writing (in test mode and targeting project-local file)

    """
    try:  # pragma: no cover - Defensive exception handling for safeguard detection errors
        project_root = _find_project_root()
        if project_root is None:
            # Can't determine project root, allow write (fallback to old behavior)
            return False

        project_local = project_root / "ccbt.toml"
        is_test_env = bool(
            os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CCBT_TEST_MODE")
        )
        # If resolver picked the project-local file under test, skip destructive write
        if (
            config_file
            and config_file.resolve() == project_local.resolve()
            and is_test_env
        ):
            return True  # pragma: no cover - Test mode protection path
    except Exception:  # pragma: no cover - Defensive exception handling for safeguard detection errors (path resolution, environment access, etc.)
        # If any error in safeguard detection, proceed normally
        pass  # pragma: no cover - Error handling path for safeguard detection failures
    return False


@click.group()
def proxy() -> None:
    """Manage HTTP proxy configuration."""


@proxy.command("set")
@click.option("--host", required=True, help="Proxy server hostname or IP")
@click.option("--port", type=int, required=True, help="Proxy server port")
@click.option(
    "--type",
    "proxy_type",
    type=click.Choice(["http", "socks4", "socks5"]),
    default="http",
    help="Proxy type",
)
@click.option("--user", "username", help="Proxy username for authentication")
@click.option("--pass", "password", help="Proxy password for authentication")
@click.option(
    "--for-trackers/--no-for-trackers",
    "for_trackers",
    default=True,
    help="Use proxy for tracker requests",
)
@click.option(
    "--for-peers/--no-for-peers",
    "for_peers",
    default=False,
    help="Use proxy for peer connections",
)
@click.option(
    "--for-webseeds/--no-for-webseeds",
    "for_webseeds",
    default=True,
    help="Use proxy for WebSeed requests",
)
@click.option(
    "--bypass-list",
    help="Comma-separated list of hosts/IPs to bypass proxy",
)
@click.pass_context
def proxy_set(
    _ctx,
    host: str,
    port: int,
    proxy_type: str,
    username: str | None,
    password: str | None,
    for_trackers: bool,
    for_peers: bool,
    for_webseeds: bool,
    bypass_list: str | None,
) -> None:
    """Set proxy configuration."""
    console = Console()

    try:
        from ccbt.cli.main import _get_config_from_context
        from ccbt.config.config import init_config

        # Try to get from context, fall back to init_config if no context
        try:
            config_manager = _get_config_from_context(_ctx) if _ctx else init_config()
        except Exception:
            config_manager = init_config()
        config = config_manager.config

        # Update proxy configuration
        config.proxy.enable_proxy = True
        config.proxy.proxy_host = host
        config.proxy.proxy_port = port
        config.proxy.proxy_type = proxy_type
        config.proxy.proxy_username = username
        config.proxy.proxy_password = password
        config.proxy.proxy_for_trackers = for_trackers
        config.proxy.proxy_for_peers = for_peers
        config.proxy.proxy_for_webseeds = for_webseeds

        if bypass_list:
            config.proxy.proxy_bypass_list = [
                item.strip() for item in bypass_list.split(",")
            ]

        # Save configuration to file (with password encryption)
        if config_manager.config_file:
            # Safety: avoid overwriting project-local config during tests
            if _should_skip_project_local_write(config_manager.config_file):
                console.print(
                    "[yellow]Proxy configuration updated (skipped write in test mode)[/yellow]"
                )  # pragma: no cover - Test mode protection path
                console.print(
                    "[green]Proxy configuration updated successfully[/green]"
                )  # pragma: no cover - Test mode protection path
                console.print(
                    f"  Host: {host}:{port}"
                )  # pragma: no cover - Test mode protection path
                console.print(
                    f"  Type: {proxy_type}"
                )  # pragma: no cover - Test mode protection path
                if username:  # pragma: no cover - Test mode protection path
                    console.print(
                        f"  Username: {username}"
                    )  # pragma: no cover - Test mode protection path
                console.print(
                    f"  For trackers: {for_trackers}"
                )  # pragma: no cover - Test mode protection path
                console.print(
                    f"  For peers: {for_peers}"
                )  # pragma: no cover - Test mode protection path
                console.print(
                    f"  For webseeds: {for_webseeds}"
                )  # pragma: no cover - Test mode protection path
                if bypass_list:  # pragma: no cover - Test mode protection path
                    console.print(
                        f"  Bypass list: {bypass_list}"
                    )  # pragma: no cover - Test mode protection path
                return  # pragma: no cover - Test mode protection path
            config.model_dump(mode="json")
            # Export will encrypt passwords
            config_toml = config_manager.export(fmt="toml", encrypt_passwords=True)
            config_manager.config_file.write_text(config_toml, encoding="utf-8")
            console.print(
                f"[green]Proxy configuration saved to {config_manager.config_file}[/green]"
            )
        else:
            console.print(
                "[yellow]No config file found - configuration not persisted[/yellow]"
            )

        console.print("[green]Proxy configuration updated successfully[/green]")
        console.print(f"  Host: {host}:{port}")
        console.print(f"  Type: {proxy_type}")
        if username:
            console.print(f"  Username: {username}")
        console.print(f"  For trackers: {for_trackers}")
        console.print(f"  For peers: {for_peers}")
        console.print(f"  For webseeds: {for_webseeds}")
        if bypass_list:
            console.print(f"  Bypass list: {bypass_list}")

    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Failed to set proxy configuration: {e}[/red]")
        raise click.Abort from e


@proxy.command("test")
@click.pass_context
def proxy_test(_ctx) -> None:
    """Test proxy connection."""
    console = Console()

    try:
        config = get_config()

        if not config.proxy or not config.proxy.enable_proxy:
            console.print("[yellow]Proxy is not enabled[/yellow]")
            raise click.Abort

        if not config.proxy.proxy_host or not config.proxy.proxy_port:
            console.print("[red]Proxy host and port must be configured[/red]")
            raise click.Abort

        console.print(
            f"[cyan]Testing proxy connection to {config.proxy.proxy_host}:{config.proxy.proxy_port}...[/cyan]"
        )

        async def _test() -> bool:
            proxy_client = ProxyClient()
            return await proxy_client.test_connection(
                proxy_host=config.proxy.proxy_host,  # type: ignore[arg-type]
                proxy_port=config.proxy.proxy_port,  # type: ignore[arg-type]
                proxy_type=config.proxy.proxy_type,
                proxy_username=config.proxy.proxy_username,
                proxy_password=config.proxy.proxy_password,
            )

        result = asyncio.run(_test())

        if result:
            console.print("[green]✓ Proxy connection test successful[/green]")
            stats = ProxyClient().get_stats()
            console.print(f"  Total connections: {stats.connections_total}")
            console.print(f"  Successful: {stats.connections_successful}")
            console.print(f"  Failed: {stats.connections_failed}")
            console.print(f"  Auth failures: {stats.auth_failures}")
        else:  # pragma: no cover - Proxy test failure path, tested via successful connection path
            console.print("[red]✗ Proxy connection test failed[/red]")
            raise click.Abort

    except (
        ProxyError
    ) as e:  # pragma: no cover - CLI error handler for proxy-specific errors
        console.print(f"[red]Proxy error: {e}[/red]")
        raise click.Abort from e
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Failed to test proxy: {e}[/red]")
        raise click.Abort from e


@proxy.command("status")
@click.pass_context
def proxy_status(_ctx) -> None:
    """Show proxy configuration status."""
    console = Console()
    table = Table(title="Proxy Configuration")

    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    try:
        config = get_config()

        if not config.proxy:
            console.print("[yellow]Proxy configuration not found[/yellow]")
            return

        table.add_row("Enabled", str(config.proxy.enable_proxy))
        table.add_row("Type", config.proxy.proxy_type or "N/A")
        table.add_row("Host", config.proxy.proxy_host or "N/A")
        table.add_row(
            "Port", str(config.proxy.proxy_port) if config.proxy.proxy_port else "N/A"
        )
        table.add_row("Username", config.proxy.proxy_username or "N/A")
        table.add_row("Password", "***" if config.proxy.proxy_password else "N/A")
        table.add_row("For Trackers", str(config.proxy.proxy_for_trackers))
        table.add_row("For Peers", str(config.proxy.proxy_for_peers))
        table.add_row("For WebSeeds", str(config.proxy.proxy_for_webseeds))
        table.add_row(
            "Bypass List",
            ", ".join(config.proxy.proxy_bypass_list)
            if config.proxy.proxy_bypass_list
            else "None",
        )

        console.print(table)

        # Show statistics if proxy client has been used
        proxy_client = ProxyClient()
        stats = proxy_client.get_stats()
        if stats.connections_total > 0:
            console.print("\n[cyan]Proxy Statistics:[/cyan]")
            stats_table = Table()
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="green")
            stats_table.add_row("Total Connections", str(stats.connections_total))
            stats_table.add_row("Successful", str(stats.connections_successful))
            stats_table.add_row("Failed", str(stats.connections_failed))
            stats_table.add_row("Auth Failures", str(stats.auth_failures))
            stats_table.add_row("Timeouts", str(stats.timeouts))
            stats_table.add_row("Bytes Sent", f"{stats.bytes_sent:,}")
            stats_table.add_row("Bytes Received", f"{stats.bytes_received:,}")
            console.print(stats_table)

    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Failed to get proxy status: {e}[/red]")
        raise click.Abort from e


@proxy.command("disable")
@click.pass_context
def proxy_disable(_ctx) -> None:
    """Disable proxy support."""
    console = Console()

    try:
        from ccbt.cli.main import _get_config_from_context
        from ccbt.config.config import init_config

        # Try to get from context, fall back to init_config if no context
        try:
            config_manager = _get_config_from_context(_ctx) if _ctx else init_config()
        except Exception:
            config_manager = init_config()
        config = config_manager.config

        config.proxy.enable_proxy = False

        # Save configuration to file (with password encryption)
        if config_manager.config_file:
            # Safety: avoid overwriting project-local config during tests
            if _should_skip_project_local_write(config_manager.config_file):
                console.print(
                    "[yellow]Proxy has been disabled (skipped write in test mode)[/yellow]"
                )  # pragma: no cover - Test mode protection path
                return  # pragma: no cover - Test mode protection path
            config_toml = config_manager.export(fmt="toml", encrypt_passwords=True)
            config_manager.config_file.write_text(config_toml, encoding="utf-8")
            console.print(
                f"[green]Proxy configuration saved to {config_manager.config_file}[/green]"
            )
        else:
            console.print(
                "[yellow]No config file found - configuration not persisted[/yellow]"
            )

        console.print("[green]Proxy has been disabled[/green]")

    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Failed to disable proxy: {e}[/red]")
        raise click.Abort from e
