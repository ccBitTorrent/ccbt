"""CLI commands for NAT traversal management."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.table import Table

from ccbt.cli.main import _get_executor


@click.group()
def nat() -> None:
    """Manage NAT traversal (NAT-PMP and UPnP) port mappings."""


@nat.command("status")
@click.pass_context
def nat_status(ctx) -> None:
    """Show NAT traversal status and active port mappings."""
    console = Console()

    async def _show_status() -> None:
        """Async helper for NAT status."""
        # Get executor (NAT commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. NAT management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute("nat.status")

            if not result.success:
                raise click.ClickException(result.error or "Failed to get NAT status")

            nat_status_response = result.data["status"]

            console.print("[bold]NAT Traversal Status[/bold]\n")

            # Protocol status
            if nat_status_response.method:
                console.print(
                    f"[green]Active Protocol:[/green] {nat_status_response.method.upper()}"
                )
            else:
                console.print("[yellow]Active Protocol:[/yellow] None (not discovered)")

            # External IP
            if nat_status_response.external_ip:
                console.print(
                    f"[green]External IP:[/green] {nat_status_response.external_ip}"
                )
            else:
                console.print("[yellow]External IP:[/yellow] Not available")

            # Port mappings
            console.print("\n[bold]Active Port Mappings:[/bold]")
            if nat_status_response.mappings:
                table = Table()
                table.add_column("Protocol", style="cyan")
                table.add_column("Internal Port", style="magenta")
                table.add_column("External Port", style="yellow")
                table.add_column("Source", style="green")
                table.add_column("Expires At", style="blue")

                for mapping in nat_status_response.mappings:
                    expires_str = (
                        mapping.get("expires_at")
                        if mapping.get("expires_at")
                        else "Permanent"
                    )
                    table.add_row(
                        mapping.get("protocol", "TCP").upper(),
                        str(mapping.get("internal_port", "")),
                        str(mapping.get("external_port", "")),
                        mapping.get("source", "UNKNOWN").upper(),
                        str(expires_str),
                    )

                console.print(table)
            else:
                console.print("[dim]No active port mappings[/dim]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_show_status())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@nat.command("discover")
@click.pass_context
def nat_discover(ctx) -> None:
    """Manually discover NAT devices (NAT-PMP or UPnP)."""
    console = Console()

    async def _discover() -> None:
        """Async helper for NAT discovery."""
        # Get executor (NAT commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. NAT management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            console.print("[bold]Discovering NAT devices...[/bold]\n")
            result = await executor.execute("nat.discover")

            if not result.success:
                raise click.ClickException(result.error or "Failed to discover NAT")

            discover_result = result.data

            if discover_result.get("status") == "discovered" and discover_result.get(
                "result"
            ):
                console.print("\n[green]✓ Discovery successful![/green]")
                # Get updated status to show protocol and external IP
                status_result = await executor.execute("nat.status")
                if status_result.success:
                    nat_status = status_result.data["status"]
                    if nat_status.method:
                        console.print(f"  Protocol: {nat_status.method.upper()}")
                    if nat_status.external_ip:
                        console.print(f"  External IP: {nat_status.external_ip}")
            else:
                console.print("\n[yellow]✗ No NAT devices discovered[/yellow]")
                console.print("  Make sure NAT-PMP or UPnP is enabled on your router")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_discover())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@nat.command("map")
@click.option("--port", type=int, required=True, help="Port to map")
@click.option(
    "--protocol",
    type=click.Choice(["tcp", "udp"]),
    default="tcp",
    help="Protocol (tcp or udp)",
)
@click.option(
    "--external-port", type=int, default=0, help="External port (0 for automatic)"
)
@click.pass_context
def nat_map(ctx, port: int, protocol: str, external_port: int) -> None:
    """Manually map a port using NAT-PMP or UPnP."""
    console = Console()

    async def _map_port() -> None:
        """Async helper for port mapping."""
        # Get executor (NAT commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. NAT management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            console.print(f"[bold]Mapping {protocol.upper()} port {port}...[/bold]")
            result = await executor.execute(
                "nat.map",
                internal_port=port,
                external_port=external_port if external_port > 0 else None,
                protocol=protocol,
            )

            if not result.success:
                raise click.ClickException(result.error or "Failed to map port")

            map_result = result.data

            if map_result.get("status") == "mapped" and map_result.get("result"):
                console.print("[green]✓ Port mapping successful![/green]")
                mapping_result = map_result.get("result", {})
                if isinstance(mapping_result, dict):
                    console.print(
                        f"  Internal: {mapping_result.get('internal_port', port)}"
                    )
                    console.print(
                        f"  External: {mapping_result.get('external_port', 'auto')}"
                    )
                    console.print(f"  Protocol: {protocol.upper()}")
            else:
                console.print("[red]✗ Port mapping failed[/red]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_map_port())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@nat.command("unmap")
@click.option("--port", type=int, required=True, help="External port to unmap")
@click.option(
    "--protocol",
    type=click.Choice(["tcp", "udp"]),
    default="tcp",
    help="Protocol (tcp or udp)",
)
@click.pass_context
def nat_unmap(ctx, port: int, protocol: str) -> None:
    """Remove a port mapping."""
    console = Console()

    async def _unmap_port() -> None:
        """Async helper for port unmapping."""
        # Get executor (NAT commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. NAT management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            console.print(
                f"[bold]Removing {protocol.upper()} port mapping for port {port}...[/bold]"
            )
            result = await executor.execute("nat.unmap", port=port, protocol=protocol)

            if not result.success:
                raise click.ClickException(result.error or "Failed to unmap port")

            unmap_result = result.data

            if unmap_result.get("status") == "unmapped":
                console.print("[green]✓ Port mapping removed[/green]")
            else:
                console.print("[red]✗ Failed to remove port mapping[/red]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_unmap_port())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@nat.command("external-ip")
@click.pass_context
def nat_external_ip(ctx) -> None:
    """Show external IP address from NAT gateway."""
    console = Console()

    async def _get_external_ip() -> None:
        """Async helper for getting external IP."""
        # Get executor (NAT commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. NAT management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute("nat.status")

            if not result.success:
                raise click.ClickException(result.error or "Failed to get NAT status")

            nat_status = result.data["status"]

            if nat_status.external_ip:
                console.print(f"[green]External IP:[/green] {nat_status.external_ip}")
                if nat_status.method:
                    console.print(f"[dim]Protocol: {nat_status.method.upper()}[/dim]")
            else:
                console.print("[yellow]External IP not available[/yellow]")
                console.print(
                    "  Make sure NAT traversal is enabled and a device is discovered"
                )
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_get_external_ip())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@nat.command("refresh")
@click.pass_context
def nat_refresh(ctx) -> None:
    """Refresh NAT port mappings."""
    console = Console()

    async def _refresh_mappings() -> None:
        """Async helper for refreshing mappings."""
        # Get executor (NAT commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. NAT management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute("nat.refresh")

            if not result.success:
                raise click.ClickException(result.error or "Failed to refresh mappings")

            refresh_result = result.data

            if refresh_result.get("status") == "refreshed":
                console.print("[green]✓ Port mappings refreshed[/green]")
            else:
                console.print("[yellow]Refresh completed with warnings[/yellow]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_refresh_mappings())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e
