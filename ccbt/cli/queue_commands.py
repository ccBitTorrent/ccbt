"""CLI commands for queue management."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.table import Table

from ccbt.cli.main import _get_executor


@click.group()
def queue() -> None:
    """Manage torrent queue and priorities."""


@queue.command("list")
@click.pass_context
def queue_list(ctx) -> None:
    """List all torrents in queue with their priorities."""
    console = Console()

    async def _list_queue() -> None:
        """Async helper for queue list."""
        # Get executor (queue commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. Queue management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute("queue.list")

            if not result.success:
                raise click.ClickException(result.error or "Failed to get queue")

            queue_list_response = result.data["queue"]

            table = Table(title="Torrent Queue")
            table.add_column("Position", style="cyan")
            table.add_column("Info Hash", style="magenta")
            table.add_column("Priority", style="yellow")
            table.add_column("Status", style="green")
            table.add_column("Down (KiB/s)", style="blue")
            table.add_column("Up (KiB/s)", style="blue")

            for entry in queue_list_response.entries:
                table.add_row(
                    str(entry.queue_position),
                    entry.info_hash[:16] + "...",
                    entry.priority.upper(),
                    entry.status.upper(),
                    str(entry.allocated_down_kib),
                    str(entry.allocated_up_kib),
                )

            console.print(table)

            # Print statistics
            stats = queue_list_response.statistics
            console.print("\n[bold]Statistics:[/bold]")
            console.print(f"  Total: {stats.get('total_torrents', 0)}")
            console.print(f"  Active Downloading: {stats.get('active_downloading', 0)}")
            console.print(f"  Active Seeding: {stats.get('active_seeding', 0)}")
            console.print(f"  Queued: {stats.get('queued', 0)}")
            console.print(f"  Paused: {stats.get('paused', 0)}")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_list_queue())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@queue.command("add")
@click.argument("info_hash")
@click.option(
    "--priority",
    type=click.Choice(["maximum", "high", "normal", "low", "paused"]),
    default="normal",
    help="Priority level",
)
@click.pass_context
def queue_add(ctx, info_hash: str, priority: str) -> None:
    """Add torrent to queue with specified priority."""
    console = Console()

    async def _add_to_queue() -> None:
        """Async helper for queue add."""
        # Get executor (queue commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. Queue management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute(
                "queue.add",
                info_hash=info_hash,
                priority=priority,
            )

            if not result.success:
                raise click.ClickException(result.error or "Failed to add to queue")

            console.print(
                f"[green]Added torrent to queue with priority {priority.upper()}[/green]"
            )
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_add_to_queue())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@queue.command("remove")
@click.argument("info_hash")
@click.pass_context
def queue_remove(ctx, info_hash: str) -> None:
    """Remove torrent from queue."""
    console = Console()

    async def _remove_from_queue() -> None:
        """Async helper for queue remove."""
        # Get executor (queue commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. Queue management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute("queue.remove", info_hash=info_hash)

            if not result.success:
                if "not found" in (result.error or "").lower():
                    console.print("[yellow]Torrent not found in queue[/yellow]")
                    return
                raise click.ClickException(
                    result.error or "Failed to remove from queue"
                )

            console.print("[green]Removed torrent from queue[/green]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_remove_from_queue())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@queue.command("priority")
@click.argument("info_hash")
@click.argument(
    "priority",
    type=click.Choice(["maximum", "high", "normal", "low", "paused"]),
)
@click.pass_context
def queue_priority(ctx, info_hash: str, priority: str) -> None:
    """Set torrent priority."""
    console = Console()

    async def _set_priority() -> None:
        """Async helper for queue priority."""
        # Get executor (queue commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. Queue management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor - use add_to_queue which updates priority
            result = await executor.execute(
                "queue.add",
                info_hash=info_hash,
                priority=priority,
            )

            if not result.success:
                if "not found" in (result.error or "").lower():
                    console.print("[yellow]Torrent not found in queue[/yellow]")
                    return
                raise click.ClickException(result.error or "Failed to set priority")

            console.print(f"[green]Set priority to {priority.upper()}[/green]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_set_priority())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@queue.command("reorder")
@click.argument("info_hash")
@click.argument("position", type=int)
@click.pass_context
def queue_reorder(ctx, info_hash: str, position: int) -> None:
    """Move torrent to specific position in queue."""
    console = Console()

    async def _reorder_queue() -> None:
        """Async helper for queue reorder."""
        # Get executor (queue commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. Queue management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute(
                "queue.move",
                info_hash=info_hash,
                new_position=position,
            )

            if not result.success:
                if (
                    "not found" in (result.error or "").lower()
                    or "failed" in (result.error or "").lower()
                ):
                    console.print("[yellow]Failed to move torrent[/yellow]")
                    return
                raise click.ClickException(result.error or "Failed to move in queue")

            console.print(f"[green]Moved to position {position}[/green]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_reorder_queue())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@queue.command("pause")
@click.argument("info_hash")
@click.pass_context
def queue_pause(ctx, info_hash: str) -> None:
    """Pause torrent in queue."""
    console = Console()

    async def _pause_torrent() -> None:
        """Async helper for queue pause."""
        # Get executor (queue commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. Queue management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute("queue.pause", info_hash=info_hash)

            if not result.success:
                if "not found" in (result.error or "").lower():
                    console.print("[yellow]Torrent not found[/yellow]")
                    return
                raise click.ClickException(result.error or "Failed to pause torrent")

            console.print("[green]Paused torrent[/green]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_pause_torrent())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@queue.command("resume")
@click.argument("info_hash")
@click.pass_context
def queue_resume(ctx, info_hash: str) -> None:
    """Resume paused torrent."""
    console = Console()

    async def _resume_torrent() -> None:
        """Async helper for queue resume."""
        # Get executor (queue commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. Queue management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute("queue.resume", info_hash=info_hash)

            if not result.success:
                if "not found" in (result.error or "").lower():
                    console.print("[yellow]Torrent not found[/yellow]")
                    return
                raise click.ClickException(result.error or "Failed to resume torrent")

            console.print("[green]Resumed torrent[/green]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_resume_torrent())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@queue.command("clear")
@click.pass_context
def queue_clear(ctx) -> None:
    """Clear all torrents from queue."""
    console = Console()

    async def _clear_queue() -> None:
        """Async helper for queue clear."""
        # Get executor (queue commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. Queue management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute("queue.clear")

            if not result.success:
                raise click.ClickException(result.error or "Failed to clear queue")

            console.print("[green]Cleared queue[/green]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_clear_queue())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e
