"""Xet protocol CLI commands (enable, disable, status, stats, cache-info)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

import click
from rich.console import Console
from rich.table import Table

from ccbt.i18n import _

logger = logging.getLogger(__name__)


@click.group()
def xet() -> None:
    """Manage Xet protocol for content-defined chunking and deduplication."""


@xet.command("enable")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.pass_context
def xet_enable(_ctx, config_file: Optional[str]) -> None:
    """Enable Xet protocol in configuration."""
    console = Console()
    if config_file:
        logger.debug("Ignoring --config for executor-backed xet enable command")
    try:
        from ccbt.cli.main import _get_executor

        async def _enable() -> Any:
            executor, _is_daemon = await _get_executor()
            if executor is None:
                msg = "Unable to acquire XET executor"
                raise RuntimeError(msg)
            return await executor.execute("xet.enable")

        result = asyncio.run(_enable())
        if not result.success:
            msg = result.error or "Failed to enable XET"
            raise RuntimeError(msg)
        console.print(_("[green]✓[/green] Xet protocol enabled"))
    except Exception as e:
        console.print(_("[red]Error enabling Xet protocol: {e}[/red]").format(e=e))
        raise click.Abort from e


@xet.command("disable")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.pass_context
def xet_disable(_ctx, config_file: Optional[str]) -> None:
    """Disable Xet protocol in configuration."""
    console = Console()
    if config_file:
        logger.debug("Ignoring --config for executor-backed xet disable command")
    try:
        from ccbt.cli.main import _get_executor

        async def _disable() -> Any:
            executor, _is_daemon = await _get_executor()
            if executor is None:
                msg = "Unable to acquire XET executor"
                raise RuntimeError(msg)
            return await executor.execute("xet.disable")

        result = asyncio.run(_disable())
        if not result.success:
            msg = result.error or "Failed to disable XET"
            raise RuntimeError(msg)
        console.print(_("[yellow]✓[/yellow] Xet protocol disabled"))
    except Exception as e:
        console.print(_("[red]Error disabling Xet protocol: {e}[/red]").format(e=e))
        raise click.Abort from e


@xet.command("status")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.pass_context
def xet_status(_ctx, config_file: Optional[str]) -> None:
    """Show Xet protocol status and configuration."""
    console = Console()
    if config_file:
        logger.debug("Ignoring --config for executor-backed xet status command")
    try:
        from ccbt.cli.main import _get_executor

        async def _load_status() -> tuple[Any, Any]:
            executor, _is_daemon = await _get_executor()
            if executor is None:
                msg = "Unable to acquire XET executor"
                raise RuntimeError(msg)
            config_result = await executor.execute("xet.get_config")
            protocol_result = await executor.execute("protocol.get_xet")
            return config_result, protocol_result

        config_result, protocol_result = asyncio.run(_load_status())
        if not config_result.success:
            msg = config_result.error or "Failed to get XET config"
            raise RuntimeError(msg)

        config_data = config_result.data or {}
        console.print(_("[bold]Xet Protocol Status[/bold]\n"))
        console.print(_("[bold]Configuration:[/bold]"))
        console.print(
            _("  Enabled: {enabled}").format(
                enabled=config_data.get("protocol_enabled", False)
            )
        )
        console.print(
            _("  Workspace sync enabled: {enabled}").format(
                enabled=config_data.get("workspace_sync_enabled", False)
            )
        )
        console.print(
            _("  Default sync mode: {mode}").format(
                mode=config_data.get("default_sync_mode", "unknown")
            )
        )
        console.print(
            _("  Check interval: {seconds}").format(
                seconds=config_data.get("check_interval", "unknown")
            )
        )
        console.print(
            _("  XET port: {port}").format(port=config_data.get("xet_port", "auto"))
        )

        console.print(_("\n[bold]Runtime Status:[/bold]"))
        protocol = (
            (protocol_result.data or {}).get("protocol")
            if protocol_result.success
            else None
        )
        if protocol is None:
            console.print(_("  Protocol not active (session may not be running)"))
        else:
            console.print(
                _("  Protocol enabled: {enabled}").format(enabled=protocol.enabled)
            )
            console.print(
                _("  Supports XET: {enabled}").format(enabled=protocol.supports_xet)
            )
            console.print(
                _("  Supports DHT: {enabled}").format(enabled=protocol.supports_dht)
            )
            console.print(
                _("  Supports PEX: {enabled}").format(enabled=protocol.supports_pex)
            )
    except Exception as e:
        console.print(_("[red]Error getting Xet status: {e}[/red]").format(e=e))
        raise click.Abort from e


@xet.command("stats")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.pass_context
def xet_stats(_ctx, config_file: Optional[str], json_output: bool) -> None:
    """Show Xet deduplication cache statistics."""
    console = Console()
    if config_file:
        logger.debug("Ignoring --config for executor-backed xet stats command")

    async def _show_stats() -> None:
        """Show deduplication cache statistics."""
        try:
            from ccbt.cli.main import _get_executor

            executor, _is_daemon = await _get_executor()
            if executor is None:
                msg = "Unable to acquire XET executor"
                raise RuntimeError(msg)
            result = await executor.execute("xet.cache_stats")
            if not result.success:
                raise RuntimeError(result.error or "Failed to retrieve XET stats")
            stats = (result.data or {}).get("stats", {})

            if json_output:
                click.echo(json.dumps(stats, indent=2))
                return
            console.print(_("[bold]Xet Deduplication Cache Statistics[/bold]\n"))
            table = Table(show_header=True, header_style="bold")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Total chunks", str(stats.get("total_chunks", 0)))
            table.add_row("Unique chunks", str(stats.get("unique_chunks", 0)))
            table.add_row("Total size (bytes)", str(stats.get("total_size", 0)))
            table.add_row("Cache size (bytes)", str(stats.get("cache_size", 0)))
            table.add_row("Average chunk size", str(stats.get("avg_chunk_size", 0)))
            table.add_row("Deduplication ratio", f"{stats.get('dedup_ratio', 0.0):.2f}")
            console.print(table)

        except Exception as e:
            console.print(_("[red]Error retrieving stats: {e}[/red]").format(e=e))
            logger.exception(_("Failed to get Xet stats"))

    asyncio.run(_show_stats())


@xet.command("cache-info")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.option("--limit", type=int, default=10, help="Limit number of chunks to show")
@click.pass_context
def xet_cache_info(
    _ctx, config_file: Optional[str], json_output: bool, limit: int
) -> None:
    """Show detailed information about cached chunks."""
    console = Console()
    if config_file:
        logger.debug("Ignoring --config for executor-backed xet cache-info command")

    async def _show_cache_info() -> None:
        """Show cache information."""
        try:
            from ccbt.cli.main import _get_executor

            executor, _is_daemon = await _get_executor()
            if executor is None:
                msg = "Unable to acquire XET executor"
                raise RuntimeError(msg)
            result = await executor.execute("xet.cache_info", limit=limit)
            if not result.success:
                raise RuntimeError(result.error or "Failed to retrieve cache info")
            payload = result.data or {}
            stats = payload.get("stats", {})
            chunks = payload.get("sample_chunks", [])

            if json_output:
                click.echo(
                    json.dumps({"stats": stats, "sample_chunks": chunks}, indent=2)
                )
                return

            console.print(_("[bold]Xet Cache Information[/bold]\n"))
            console.print(
                _("Total chunks: {count}").format(count=stats.get("total_chunks", 0))
            )
            console.print(
                _("Cache size: {size} bytes").format(size=stats.get("cache_size", 0))
            )
            console.print(
                _("\n[bold]Sample chunks (last {limit} accessed):[/bold]\n").format(
                    limit=limit
                )
            )

            if chunks:
                table = Table(show_header=True, header_style="bold")
                table.add_column("Hash", style="cyan", max_width=20)
                table.add_column("Size", style="green")
                table.add_column("Ref Count", style="yellow")
                table.add_column("Created", style="blue")
                table.add_column("Last Accessed", style="magenta")
                for chunk in chunks:
                    hash_value = str(chunk.get("hash", ""))
                    table.add_row(
                        f"{hash_value[:16]}..." if hash_value else "",
                        str(chunk.get("size", 0)),
                        str(chunk.get("ref_count", 0)),
                        str(chunk.get("created_at", "")),
                        str(chunk.get("last_accessed", "")),
                    )
                console.print(table)
            else:
                console.print(_("[yellow]No chunks in cache[/yellow]"))

        except Exception as e:
            console.print(_("[red]Error retrieving cache info: {e}[/red]").format(e=e))
            logger.exception(_("Failed to get Xet cache info"))

    asyncio.run(_show_cache_info())


@xet.command("cleanup")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be cleaned without actually cleaning",
)
@click.option(
    "--max-age-days", type=int, default=30, help="Maximum age in days for unused chunks"
)
@click.pass_context
def xet_cleanup(
    _ctx, config_file: Optional[str], dry_run: bool, max_age_days: int
) -> None:
    """Clean up unused chunks from the deduplication cache."""
    console = Console()
    if config_file:
        logger.debug("Ignoring --config for executor-backed xet cleanup command")

    async def _cleanup() -> None:
        """Clean up unused chunks."""
        try:
            from ccbt.cli.main import _get_executor

            executor, _is_daemon = await _get_executor()
            if executor is None:
                msg = "Unable to acquire XET executor"
                raise RuntimeError(msg)
            result = await executor.execute(
                "xet.cache_cleanup",
                dry_run=dry_run,
                max_age_days=max_age_days,
            )
            if not result.success:
                raise RuntimeError(result.error or "Failed to cleanup XET cache")

            payload = result.data or {}
            if payload.get("dry_run"):
                console.print(
                    _(
                        "[yellow]Dry run: Would clean chunks older than {days} days[/yellow]"
                    ).format(days=payload.get("max_age_days", max_age_days))
                )
                stats_before = payload.get("stats_before", {})
                console.print(
                    _("Current chunks: {count}").format(
                        count=stats_before.get("total_chunks", 0)
                    )
                )
                return

            console.print(
                _("[green]✓[/green] Cleaned {cleaned} unused chunks").format(
                    cleaned=payload.get("cleaned", 0)
                )
            )
            stats_after = payload.get("stats_after", {})
            console.print(
                _("Remaining chunks: {count}").format(
                    count=stats_after.get("total_chunks", 0)
                )
            )

        except Exception as e:
            console.print(_("[red]Error during cleanup: {e}[/red]").format(e=e))
            logger.exception(_("Failed to cleanup Xet cache"))

    asyncio.run(_cleanup())
