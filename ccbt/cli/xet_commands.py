"""Xet protocol CLI commands (enable, disable, status, stats, cache-info)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ccbt.config.config import ConfigManager
from ccbt.protocols.base import ProtocolType
from ccbt.protocols.xet import XetProtocol
from ccbt.session.session import AsyncSessionManager
from ccbt.storage.xet_deduplication import XetDeduplication

logger = logging.getLogger(__name__)


async def _get_xet_protocol() -> XetProtocol | None:
    """Get Xet protocol instance from session manager.
    
    Note: If daemon is running, this will check via IPC but cannot return
    the actual protocol instance. Commands using this should handle None
    and route operations via IPC instead.
    """
    from ccbt.cli.main import _get_executor
    from ccbt.executor.session_adapter import LocalSessionAdapter
    from ccbt.executor.executor import UnifiedCommandExecutor
    
    # Get executor (daemon or local)
    executor, is_daemon = await _get_executor()
    
    if is_daemon and executor:
        # Daemon mode - use executor to get protocol info
        result = await executor.execute("protocol.get_xet")
        if result.success and result.data.get("protocol"):
            protocol_info = result.data["protocol"]
            # Protocol is enabled in daemon, but we can't return the instance
            # Commands should use executor for operations instead
            if protocol_info.enabled:
                return None  # Protocol enabled but instance not available in daemon mode
        return None
    
    # Local mode - get protocol from session
    if executor and isinstance(executor.adapter, LocalSessionAdapter):
        session = executor.adapter.session_manager
        try:
            # Find Xet protocol in session's protocols list
            protocols = getattr(session, "protocols", [])
            for protocol in protocols:
                if isinstance(protocol, XetProtocol):
                    return protocol
            # Also try protocol manager if protocols list is empty
            protocol_manager = getattr(session, "protocol_manager", None)
            if protocol_manager:
                xet_protocol = protocol_manager.get_protocol(ProtocolType.XET)
                if isinstance(xet_protocol, XetProtocol):
                    return xet_protocol
        except Exception:  # pragma: no cover - CLI error handler
            logger.exception("Failed to get Xet protocol from session")
    
    # Fallback: create temporary session if executor not available
    # CRITICAL FIX: Use safe local session creation helper
    try:
        from ccbt.cli.main import _ensure_local_session_safe

        session = await _ensure_local_session_safe(force_local=True)
        try:
            # Find Xet protocol in session's protocols list
            protocols = getattr(session, "protocols", [])
            for protocol in protocols:
                if isinstance(protocol, XetProtocol):
                    return protocol
            # Also try protocol manager if protocols list is empty
            protocol_manager = getattr(session, "protocol_manager", None)
            if protocol_manager:
                xet_protocol = protocol_manager.get_protocol(ProtocolType.XET)
                if isinstance(xet_protocol, XetProtocol):
                    return xet_protocol
            return None
        finally:
            await session.stop()
    except Exception:  # pragma: no cover - CLI error handler
        logger.exception("Failed to get Xet protocol")
        return None


@click.group()
def xet() -> None:
    """Manage Xet protocol for content-defined chunking and deduplication."""


@xet.command("enable")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.pass_context
def xet_enable(_ctx, config_file: str | None) -> None:
    """Enable Xet protocol in configuration."""
    console = Console()
    from ccbt.cli.main import _get_config_from_context
    from ccbt.config.config import init_config
    
    # Use config_file if provided, otherwise try context, fall back to init_config
    if config_file:
        from ccbt.cli.main import _get_config_from_context
    from ccbt.config.config import init_config
    
    # Use config_file if provided, otherwise try context, fall back to init_config
    if config_file:
        cm = ConfigManager(config_file)
    else:
        try:
            cm = _get_config_from_context(_ctx) if _ctx else init_config()
        except Exception:
            cm = init_config()
    else:
        try:
            cm = _get_config_from_context(_ctx) if _ctx else init_config()
        except Exception:
            cm = init_config()
    cm.config.disk.xet_enabled = True

    # Save to config file
    if cm.config_file:
        cm.config_file.parent.mkdir(parents=True, exist_ok=True)
        import toml

        config_dict = cm.config.model_dump(mode="json")
        if cm.config_file.exists():
            existing = toml.load(str(cm.config_file))
            config_dict.update(existing)
        cm.config_file.write_text(toml.dumps(config_dict), encoding="utf-8")

    console.print("[green]✓[/green] Xet protocol enabled")
    console.print(f"  Configuration saved to: {cm.config_file or 'default location'}")


@xet.command("disable")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.pass_context
def xet_disable(_ctx, config_file: str | None) -> None:
    """Disable Xet protocol in configuration."""
    console = Console()
    from ccbt.cli.main import _get_config_from_context
    from ccbt.config.config import init_config
    
    # Use config_file if provided, otherwise try context, fall back to init_config
    if config_file:
        cm = ConfigManager(config_file)
    else:
        try:
            cm = _get_config_from_context(_ctx) if _ctx else init_config()
        except Exception:
            cm = init_config()
    cm.config.disk.xet_enabled = False

    # Save to config file
    if cm.config_file:
        cm.config_file.parent.mkdir(parents=True, exist_ok=True)
        import toml

        config_dict = cm.config.model_dump(mode="json")
        if cm.config_file.exists():
            existing = toml.load(str(cm.config_file))
            config_dict.update(existing)
        cm.config_file.write_text(toml.dumps(config_dict), encoding="utf-8")

    console.print("[yellow]✓[/yellow] Xet protocol disabled")
    console.print(f"  Configuration saved to: {cm.config_file or 'default location'}")


@xet.command("status")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.pass_context
def xet_status(_ctx, config_file: str | None) -> None:
    """Show Xet protocol status and configuration."""
    console = Console()
    from ccbt.cli.main import _get_config_from_context
    from ccbt.config.config import init_config
    
    # Use config_file if provided, otherwise try context, fall back to init_config
    if config_file:
        cm = ConfigManager(config_file)
    else:
        try:
            cm = _get_config_from_context(_ctx) if _ctx else init_config()
        except Exception:
            cm = init_config()
    config = cm.config

    console.print("[bold]Xet Protocol Status[/bold]\n")

    # Configuration status
    xet_config = config.disk
    console.print("[bold]Configuration:[/bold]")
    console.print(f"  Enabled: {xet_config.xet_enabled}")
    console.print(f"  Deduplication: {xet_config.xet_deduplication_enabled}")
    console.print(f"  P2P CAS: {xet_config.xet_use_p2p_cas}")
    console.print(f"  Compression: {xet_config.xet_compression_enabled}")
    console.print(
        f"  Chunk size range: {xet_config.xet_chunk_min_size}-{xet_config.xet_chunk_max_size} bytes"
    )
    console.print(f"  Target chunk size: {xet_config.xet_chunk_target_size} bytes")
    console.print(f"  Cache DB: {xet_config.xet_cache_db_path}")
    console.print(f"  Chunk store: {xet_config.xet_chunk_store_path}")

    # Runtime status (if session is available)
    async def _show_runtime_status() -> None:
        """Show runtime status from active session."""
        try:
            protocol = await _get_xet_protocol()
            if protocol:
                console.print("\n[bold]Runtime Status:[/bold]")
                console.print(f"  Protocol state: {protocol.state}")
                if protocol.cas_client:
                    console.print("  P2P CAS client: Active")
                else:
                    console.print("  P2P CAS client: Not initialized")
            else:
                console.print("\n[yellow]Runtime Status:[/yellow]")
                console.print("  Protocol not active (session may not be running)")
        except Exception as e:
            logger.debug("Failed to get runtime status: %s", e)
            console.print("\n[yellow]Runtime Status:[/yellow]")
            console.print("  Unable to connect to active session")

    asyncio.run(_show_runtime_status())


@xet.command("stats")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.pass_context
def xet_stats(_ctx, config_file: str | None, json_output: bool) -> None:
    """Show Xet deduplication cache statistics."""
    console = Console()
    from ccbt.cli.main import _get_config_from_context
    from ccbt.config.config import init_config
    
    # Use config_file if provided, otherwise try context, fall back to init_config
    if config_file:
        cm = ConfigManager(config_file)
    else:
        try:
            cm = _get_config_from_context(_ctx) if _ctx else init_config()
        except Exception:
            cm = init_config()
    config = cm.config

    if not config.disk.xet_enabled:
        console.print("[yellow]Xet protocol is disabled[/yellow]")
        return

    async def _show_stats() -> None:
        """Show deduplication cache statistics."""
        try:
            # Open deduplication cache
            dedup_path = Path(config.disk.xet_cache_db_path)
            dedup_path.parent.mkdir(parents=True, exist_ok=True)

            async with XetDeduplication(dedup_path) as dedup:
                stats = dedup.get_cache_stats()

                if json_output:
                    click.echo(json.dumps(stats, indent=2))
                else:
                    console.print("[bold]Xet Deduplication Cache Statistics[/bold]\n")

                    table = Table(show_header=True, header_style="bold")
                    table.add_column("Metric", style="cyan")
                    table.add_column("Value", style="green")

                    table.add_row("Total chunks", str(stats.get("total_chunks", 0)))
                    table.add_row("Unique chunks", str(stats.get("unique_chunks", 0)))
                    table.add_row("Total size (bytes)", str(stats.get("total_size", 0)))
                    table.add_row("Cache size (bytes)", str(stats.get("cache_size", 0)))
                    table.add_row(
                        "Average chunk size", str(stats.get("avg_chunk_size", 0))
                    )
                    table.add_row(
                        "Deduplication ratio", f"{stats.get('dedup_ratio', 0.0):.2f}"
                    )

                    console.print(table)

        except Exception as e:
            console.print(f"[red]Error retrieving stats: {e}[/red]")
            logger.exception("Failed to get Xet stats")

    asyncio.run(_show_stats())


@xet.command("cache-info")
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.option("--limit", type=int, default=10, help="Limit number of chunks to show")
@click.pass_context
def xet_cache_info(
    _ctx, config_file: str | None, json_output: bool, limit: int
) -> None:
    """Show detailed information about cached chunks."""
    console = Console()
    from ccbt.cli.main import _get_config_from_context
    from ccbt.config.config import init_config
    
    # Use config_file if provided, otherwise try context, fall back to init_config
    if config_file:
        cm = ConfigManager(config_file)
    else:
        try:
            cm = _get_config_from_context(_ctx) if _ctx else init_config()
        except Exception:
            cm = init_config()
    config = cm.config

    if not config.disk.xet_enabled:
        console.print("[yellow]Xet protocol is disabled[/yellow]")
        return

    async def _show_cache_info() -> None:
        """Show cache information."""
        try:
            dedup_path = Path(config.disk.xet_cache_db_path)
            dedup_path.parent.mkdir(parents=True, exist_ok=True)

            async with XetDeduplication(dedup_path) as dedup:
                stats = dedup.get_cache_stats()

                if json_output:
                    # Get sample chunks
                    import sqlite3

                    conn = sqlite3.connect(dedup_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT chunk_hash, size, ref_count, created_at, last_accessed FROM chunks ORDER BY last_accessed DESC LIMIT ?",
                        (limit,),
                    )
                    chunks = cursor.fetchall()
                    conn.close()

                    chunk_list = [
                        {
                            "hash": row[0].hex()
                            if isinstance(row[0], bytes)
                            else row[0],
                            "size": row[1],
                            "ref_count": row[2],
                            "created_at": row[3],
                            "last_accessed": row[4],
                        }
                        for row in chunks
                    ]
                    click.echo(
                        json.dumps(
                            {"stats": stats, "sample_chunks": chunk_list}, indent=2
                        )
                    )
                else:
                    console.print("[bold]Xet Cache Information[/bold]\n")
                    console.print(f"Total chunks: {stats.get('total_chunks', 0)}")
                    console.print(f"Cache size: {stats.get('cache_size', 0)} bytes")
                    console.print(
                        f"\n[bold]Sample chunks (last {limit} accessed):[/bold]\n"
                    )

                    import sqlite3

                    conn = sqlite3.connect(dedup_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT chunk_hash, size, ref_count, created_at, last_accessed FROM chunks ORDER BY last_accessed DESC LIMIT ?",
                        (limit,),
                    )
                    chunks = cursor.fetchall()
                    conn.close()

                    if chunks:
                        table = Table(show_header=True, header_style="bold")
                        table.add_column("Hash", style="cyan", max_width=20)
                        table.add_column("Size", style="green")
                        table.add_column("Ref Count", style="yellow")
                        table.add_column("Created", style="blue")
                        table.add_column("Last Accessed", style="magenta")

                        for row in chunks:
                            chunk_hash = row[0]
                            hash_str = (
                                chunk_hash.hex()[:16] + "..."
                                if isinstance(chunk_hash, bytes)
                                else str(chunk_hash)[:16]
                            )
                            table.add_row(
                                hash_str,
                                str(row[1]),
                                str(row[2]),
                                str(row[3]),
                                str(row[4]),
                            )
                        console.print(table)
                    else:
                        console.print("[yellow]No chunks in cache[/yellow]")

        except Exception as e:
            console.print(f"[red]Error retrieving cache info: {e}[/red]")
            logger.exception("Failed to get Xet cache info")

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
    _ctx, config_file: str | None, dry_run: bool, max_age_days: int
) -> None:
    """Clean up unused chunks from the deduplication cache."""
    console = Console()
    from ccbt.cli.main import _get_config_from_context
    from ccbt.config.config import init_config
    
    # Use config_file if provided, otherwise try context, fall back to init_config
    if config_file:
        cm = ConfigManager(config_file)
    else:
        try:
            cm = _get_config_from_context(_ctx) if _ctx else init_config()
        except Exception:
            cm = init_config()
    config = cm.config

    if not config.disk.xet_enabled:
        console.print("[yellow]Xet protocol is disabled[/yellow]")
        return

    async def _cleanup() -> None:
        """Clean up unused chunks."""
        try:
            dedup_path = Path(config.disk.xet_cache_db_path)
            dedup_path.parent.mkdir(parents=True, exist_ok=True)

            async with XetDeduplication(dedup_path) as dedup:
                if dry_run:
                    console.print(
                        f"[yellow]Dry run: Would clean chunks older than {max_age_days} days[/yellow]"
                    )
                    # Get stats before cleanup
                    stats_before = dedup.get_cache_stats()
                    console.print(
                        f"Current chunks: {stats_before.get('total_chunks', 0)}"
                    )
                else:
                    max_age_seconds = max_age_days * 24 * 60 * 60

                    # Clean up unused chunks
                    cleaned = await dedup.cleanup_unused_chunks(
                        max_age_seconds=max_age_seconds
                    )

                    console.print(f"[green]✓[/green] Cleaned {cleaned} unused chunks")
                    stats_after = dedup.get_cache_stats()
                    console.print(
                        f"Remaining chunks: {stats_after.get('total_chunks', 0)}"
                    )

        except Exception as e:
            console.print(f"[red]Error during cleanup: {e}[/red]")
            logger.exception("Failed to cleanup Xet cache")

    asyncio.run(_cleanup())
