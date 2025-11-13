"""CLI commands for file selection and prioritization."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.table import Table

from ccbt.cli.main import _get_executor


def _format_size(bytes_count: int) -> str:
    """Format bytes as human-readable size."""
    size = float(bytes_count)
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PiB"  # pragma: no cover - Edge case: extremely large sizes (PiB+), unlikely in real usage


@click.group()
def files() -> None:
    """Manage file selection for torrents."""


@files.command("list")
@click.argument("info_hash")
@click.pass_context
def files_list(ctx, info_hash: str) -> None:
    """List files in a torrent with selection status."""
    console = Console()

    async def _list_files() -> None:
        """Async helper for files list."""
        # Get executor (file commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. File management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute("file.list", info_hash=info_hash)

            if not result.success:
                raise click.ClickException(result.error or "Failed to list files")

            file_list = result.data["files"]

            # Create table
            table = Table(title=f"Files in torrent {info_hash[:16]}...")
            table.add_column("Index", style="cyan", justify="right")
            table.add_column("Name", style="green")
            table.add_column("Size", justify="right", style="magenta")
            table.add_column("Attributes", style="yellow", justify="center")
            table.add_column("Priority", style="yellow")
            table.add_column("Selected", style="blue", justify="center")
            table.add_column("Progress", justify="right", style="cyan")

            for file_info in file_list.files:
                size_str = _format_size(file_info.size)
                selected_str = "✓" if file_info.selected else "✗"
                progress_str = f"{file_info.progress * 100:.1f}%"
                attributes_str = file_info.attributes or "-"

                table.add_row(
                    str(file_info.index),
                    file_info.name,
                    size_str,
                    attributes_str,
                    file_info.priority,
                    selected_str,
                    progress_str,
                )

            console.print(table)
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_list_files())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@files.command("select")
@click.argument("info_hash")
@click.argument("file_indices", nargs=-1, type=int, required=True)
@click.pass_context
def files_select(ctx, info_hash: str, file_indices: tuple[int, ...]) -> None:
    """Select files for download."""
    console = Console()

    async def _select_files() -> None:
        """Async helper for files select."""
        # Get executor (file commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. File management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute(
                "file.select",
                info_hash=info_hash,
                file_indices=list(file_indices),
            )

            if not result.success:
                raise click.ClickException(result.error or "Failed to select files")

            console.print(
                f"[green]Selected {len(file_indices)} file(s)[/green]",
            )
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_select_files())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@files.command("deselect")
@click.argument("info_hash")
@click.argument("file_indices", nargs=-1, type=int, required=True)
@click.pass_context
def files_deselect(ctx, info_hash: str, file_indices: tuple[int, ...]) -> None:
    """Deselect files from download."""
    console = Console()

    async def _deselect_files() -> None:
        """Async helper for files deselect."""
        # Get executor (file commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. File management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute(
                "file.deselect",
                info_hash=info_hash,
                file_indices=list(file_indices),
            )

            if not result.success:
                raise click.ClickException(result.error or "Failed to deselect files")

            console.print(
                f"[green]Deselected {len(file_indices)} file(s)[/green]",
            )
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_deselect_files())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@files.command("select-all")
@click.argument("info_hash")
@click.pass_context
def files_select_all(ctx, info_hash: str) -> None:
    """Select all files."""
    console = Console()

    async def _select_all() -> None:
        """Async helper for files select-all."""
        # Get executor (file commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. File management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Get file list first to get all file indices
            list_result = await executor.execute("file.list", info_hash=info_hash)

            if not list_result.success:
                raise click.ClickException(list_result.error or "Failed to list files")

            file_list = list_result.data["files"]
            all_indices = [f.index for f in file_list.files]

            # Select all files
            result = await executor.execute(
                "file.select",
                info_hash=info_hash,
                file_indices=all_indices,
            )

            if not result.success:
                raise click.ClickException(result.error or "Failed to select all files")

            console.print("[green]Selected all files[/green]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_select_all())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@files.command("deselect-all")
@click.argument("info_hash")
@click.pass_context
def files_deselect_all(ctx, info_hash: str) -> None:
    """Deselect all files."""
    console = Console()

    async def _deselect_all() -> None:
        """Async helper for files deselect-all."""
        # Get executor (file commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. File management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Get file list first to get all file indices
            list_result = await executor.execute("file.list", info_hash=info_hash)

            if not list_result.success:
                raise click.ClickException(list_result.error or "Failed to list files")

            file_list = list_result.data["files"]
            all_indices = [f.index for f in file_list.files]

            # Deselect all files
            result = await executor.execute(
                "file.deselect",
                info_hash=info_hash,
                file_indices=all_indices,
            )

            if not result.success:
                raise click.ClickException(
                    result.error or "Failed to deselect all files"
                )

            console.print("[green]Deselected all files[/green]")
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_deselect_all())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e)) from e


@files.command("priority")
@click.argument("info_hash")
@click.argument("file_index", type=int)
@click.argument(
    "priority",
    type=click.Choice(["maximum", "high", "normal", "low", "do_not_download"]),
)
@click.pass_context
def files_priority(
    ctx,
    info_hash: str,
    file_index: int,
    priority: str,
) -> None:
    """Set priority for a file."""
    console = Console()

    async def _set_priority() -> None:
        """Async helper for files priority."""
        # Get executor (file commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                "Daemon is not running. File management commands require the daemon to be running.\n"
                "Start the daemon with: 'btbt daemon start'"
            )

        try:
            # Execute command via executor
            result = await executor.execute(
                "file.priority",
                info_hash=info_hash,
                file_index=file_index,
                priority=priority,
            )

            if not result.success:
                raise click.ClickException(
                    result.error or "Failed to set file priority"
                )

            console.print(
                f"[green]Set file {file_index} priority to {priority.upper()}[/green]",
            )
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
