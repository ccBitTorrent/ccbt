"""Tonic file and folder sync CLI commands.

This module provides CLI commands for managing .tonic files and XET folder
synchronization including create, link, sync, status, allowlist management,
and sync mode configuration.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ccbt.cli.tonic_generator import generate_tonic_from_folder, tonic_generate
from ccbt.core.tonic import TonicFile
from ccbt.core.tonic_link import generate_tonic_link, parse_tonic_link
from ccbt.i18n import _
from ccbt.security.xet_allowlist import XetAllowlist
from ccbt.storage.xet_folder_manager import XetFolder

logger = logging.getLogger(__name__)


@click.group()
def tonic() -> None:
    """Manage .tonic files and XET folder synchronization."""


@tonic.command("create")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(),
    help="Output .tonic file path",
)
@click.option(
    "--sync-mode",
    type=click.Choice(["designated", "best_effort", "broadcast", "consensus"]),
    default="best_effort",
    help="Synchronization mode",
)
@click.option(
    "--source-peers",
    help="Comma-separated list of designated source peer IDs",
)
@click.option(
    "--allowlist",
    "allowlist_path",
    type=click.Path(),
    help="Path to allowlist file",
)
@click.option(
    "--git-ref",
    help="Git commit hash/ref to track",
)
@click.option(
    "--announce",
    help="Primary tracker announce URL",
)
@click.option(
    "--generate-link",
    is_flag=True,
    help="Also generate tonic?: link",
)
@click.pass_context
def tonic_create(
    ctx,
    folder_path: str,
    output_path: str | None,
    sync_mode: str,
    source_peers: str | None,
    allowlist_path: str | None,
    git_ref: str | None,
    announce: str | None,
    generate_link: bool,
) -> None:
    """Generate .tonic file from folder."""
    tonic_generate.callback(
        ctx,
        folder_path,
        output_path,
        sync_mode,
        source_peers,
        allowlist_path,
        git_ref,
        announce,
        generate_link,
    )


@tonic.command("link")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option(
    "--tonic-file",
    type=click.Path(exists=True),
    help="Path to .tonic file (if not provided, will generate)",
)
@click.option(
    "--sync-mode",
    type=click.Choice(["designated", "best_effort", "broadcast", "consensus"]),
    help="Synchronization mode (overrides .tonic file)",
)
@click.pass_context
def tonic_link(
    ctx,
    folder_path: str,
    tonic_file: str | None,
    sync_mode: str | None,
) -> None:
    """Generate tonic?: link from folder or .tonic file."""
    console = Console()

    try:
        if tonic_file:
            # Parse existing .tonic file
            tonic_parser = TonicFile()
            parsed_data = tonic_parser.parse(tonic_file)
            info_hash = tonic_parser.get_info_hash(parsed_data)

            # Use data from .tonic file
            display_name = parsed_data["info"]["name"]
            trackers = parsed_data.get("announce_list") or (
                [[parsed_data["announce"]]] if parsed_data.get("announce") else None
            )
            git_refs = parsed_data.get("git_refs")
            sync_mode = sync_mode or parsed_data.get("sync_mode", "best_effort")
            source_peers = parsed_data.get("source_peers")
            allowlist_hash = parsed_data.get("allowlist_hash")

            # Flatten trackers
            tracker_list: list[str] | None = None
            if trackers:
                tracker_list = [url for tier in trackers for url in tier]

            link = generate_tonic_link(
                info_hash=info_hash,
                display_name=display_name,
                trackers=tracker_list,
                git_refs=git_refs,
                sync_mode=sync_mode,
                source_peers=source_peers,
                allowlist_hash=allowlist_hash,
            )
        else:
            # Generate .tonic file first, then link
            _, link = asyncio.run(
                generate_tonic_from_folder(
                    folder_path=folder_path,
                    generate_link=True,
                    sync_mode=sync_mode or "best_effort",
                )
            )

        if link:
            console.print(_("[green]✓[/green] Tonic link:"))
            console.print(f"  {link}")
        else:
            console.print(_("[yellow]Failed to generate tonic link[/yellow]"))

    except Exception as e:
        console.print(_("[red]Error generating tonic link: {e}[/red]").format(e=e))
        logger.exception(_("Failed to generate tonic link"))
        raise click.Abort() from e


@tonic.command("sync")
@click.argument("tonic_input", type=str)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(),
    help="Output directory for synced folder",
)
@click.option(
    "--check-interval",
    type=float,
    default=5.0,
    help="Check interval in seconds",
)
@click.pass_context
def tonic_sync(
    ctx,
    tonic_input: str,
    output_dir: str | None,
    check_interval: float,
) -> None:
    """Start syncing folder from .tonic file or tonic?: link."""
    console = Console()

    try:
        # Determine if input is a link or file
        if tonic_input.startswith("tonic?:"):
            # Parse tonic link
            link_info = parse_tonic_link(tonic_input)
            console.print(_("[cyan]Parsed tonic link: {name}[/cyan]").format(name=link_info.display_name or _("Unknown")))

            # For now, just show that we would sync
            # In full implementation, would:
            # 1. Fetch .tonic file using info_hash
            # 2. Create XetFolder instance
            # 3. Start real-time sync
            console.print(_("[yellow]Tonic link sync not yet fully implemented[/yellow]"))
            console.print(_("  This would fetch the .tonic file and start syncing"))

        else:
            # Assume it's a .tonic file path
            tonic_path = Path(tonic_input)
            if not tonic_path.exists():
                console.print(_("[red]Tonic file not found: {path}[/red]").format(path=tonic_path))
                raise click.Abort()

            # Parse .tonic file
            tonic_parser = TonicFile()
            parsed_data = tonic_parser.parse(tonic_path)

            folder_name = parsed_data["info"]["name"]
            sync_mode = parsed_data.get("sync_mode", "best_effort")

            # Determine output directory
            if not output_dir:
                output_dir = folder_name

            console.print(_("[cyan]Starting sync for: {name}[/cyan]").format(name=folder_name))
            console.print(_("  Sync mode: {mode}").format(mode=sync_mode))
            console.print(_("  Output directory: {dir}").format(dir=output_dir))

            # Create folder manager and start sync
            folder = XetFolder(
                folder_path=output_dir,
                sync_mode=sync_mode,
                check_interval=check_interval,
            )

            async def _start_sync() -> None:
                await folder.start()
                console.print(_("[green]✓[/green] Folder sync started"))
                console.print(_("  Use 'ccbt tonic status' to check sync status"))

            asyncio.run(_start_sync())

    except Exception as e:
        console.print(_("[red]Error starting sync: {e}[/red]").format(e=e))
        logger.exception(_("Failed to start sync"))
        raise click.Abort() from e


@tonic.command("status")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.pass_context
def tonic_status(_ctx, folder_path: str) -> None:
    """Show sync status for a folder."""
    console = Console()

    try:
        folder = XetFolder(folder_path=folder_path)
        status = folder.get_status()

        console.print(_("[bold]Sync Status for: {path}[/bold]\n").format(path=folder_path))

        table = Table(show_header=True, header_style="bold")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Sync Mode", status.sync_mode)
        table.add_row("Is Syncing", "Yes" if status.is_syncing else "No")
        table.add_row("Pending Changes", str(status.pending_changes))
        table.add_row("Connected Peers", str(status.connected_peers))
        table.add_row("Synced Peers", str(status.synced_peers))
        table.add_row("Sync Progress", f"{status.sync_progress * 100:.1f}%")
        if status.current_git_ref:
            table.add_row("Git Ref", status.current_git_ref[:16] + "...")
        if status.last_sync_time:
            import time

            last_sync_ago = time.time() - status.last_sync_time
            table.add_row("Last Sync", f"{last_sync_ago:.1f}s ago")
        if status.error:
            table.add_row("Error", f"[red]{status.error}[/red]")

        console.print(table)

    except Exception as e:
        console.print(_("[red]Error getting status: {e}[/red]").format(e=e))
        logger.exception(_("Failed to get sync status"))
        raise click.Abort() from e


@tonic.group("allowlist")
def tonic_allowlist() -> None:
    """Manage encrypted allowlist for XET folders."""


@tonic_allowlist.command("add")
@click.argument("allowlist_path", type=click.Path())
@click.argument("peer_id", type=str)
@click.option(
    "--public-key",
    help="Ed25519 public key (hex format, 64 chars)",
)
@click.option(
    "--alias",
    help="Human-readable alias for this peer",
)
@click.pass_context
def tonic_allowlist_add(
    _ctx,
    allowlist_path: str,
    peer_id: str,
    public_key: str | None,
    alias: str | None,
) -> None:
    """Add peer to allowlist."""
    console = Console()

    try:
        allowlist = XetAllowlist(allowlist_path=allowlist_path)
        asyncio.run(allowlist.load())

        public_key_bytes = None
        if public_key:
            try:
                public_key_bytes = bytes.fromhex(public_key)
                if len(public_key_bytes) != 32:
                    msg = _("Public key must be 32 bytes (64 hex characters)")
                    raise ValueError(msg)
            except ValueError as e:
                console.print(_("[red]Invalid public key: {e}[/red]").format(e=e))
                raise click.Abort() from e

        allowlist.add_peer(peer_id=peer_id, public_key=public_key_bytes, alias=alias)
        asyncio.run(allowlist.save())

        msg = _("[green]✓[/green] Added peer {peer_id} to allowlist").format(peer_id=peer_id)
        if alias:
            msg = _("[green]✓[/green] Added peer {peer_id} to allowlist with alias '{alias}'").format(peer_id=peer_id, alias=alias)
        console.print(msg)

    except Exception as e:
        console.print(_("[red]Error adding peer to allowlist: {e}[/red]").format(e=e))
        logger.exception(_("Failed to add peer to allowlist"))
        raise click.Abort() from e


@tonic_allowlist.command("remove")
@click.argument("allowlist_path", type=click.Path())
@click.argument("peer_id", type=str)
@click.pass_context
def tonic_allowlist_remove(
    _ctx,
    allowlist_path: str,
    peer_id: str,
) -> None:
    """Remove peer from allowlist."""
    console = Console()

    try:
        allowlist = XetAllowlist(allowlist_path=allowlist_path)
        asyncio.run(allowlist.load())

        removed = allowlist.remove_peer(peer_id)
        if removed:
            asyncio.run(allowlist.save())
            console.print(_("[green]✓[/green] Removed peer {peer_id} from allowlist").format(peer_id=peer_id))
        else:
            console.print(_("[yellow]Peer {peer_id} not found in allowlist[/yellow]").format(peer_id=peer_id))

    except Exception as e:
        console.print(_("[red]Error removing peer from allowlist: {e}[/red]").format(e=e))
        logger.exception(_("Failed to remove peer from allowlist"))
        raise click.Abort() from e


@tonic_allowlist.command("list")
@click.argument("allowlist_path", type=click.Path())
@click.pass_context
def tonic_allowlist_list(_ctx, allowlist_path: str) -> None:
    """List peers in allowlist."""
    console = Console()

    try:
        allowlist = XetAllowlist(allowlist_path=allowlist_path)
        asyncio.run(allowlist.load())

        peers = allowlist.get_peers()

        if not peers:
            console.print(_("[yellow]Allowlist is empty[/yellow]"))
            return

        console.print(_("[bold]Allowlist ({count} peers):[/bold]\n").format(count=len(peers)))

        table = Table(show_header=True, header_style="bold")
        table.add_column("Peer ID", style="cyan")
        table.add_column("Alias", style="yellow")
        table.add_column("Public Key", style="green")
        table.add_column("Added At", style="blue")

        for peer_id in peers:
            peer_info = allowlist.get_peer_info(peer_id)
            public_key = peer_info.get("public_key", "") if peer_info else ""
            added_at = peer_info.get("added_at", 0) if peer_info else 0

            # Get alias from metadata
            alias = None
            if peer_info:
                metadata = peer_info.get("metadata", {})
                if isinstance(metadata, dict):
                    alias = metadata.get("alias")

            import time

            added_at_str = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(added_at))
                if added_at
                else "Unknown"
            )

            table.add_row(
                peer_id,
                alias or "-",
                public_key[:16] + "..." if public_key else "None",
                added_at_str,
            )

        console.print(table)

    except Exception as e:
        console.print(_("[red]Error listing allowlist: {e}[/red]").format(e=e))
        logger.exception(_("Failed to list allowlist"))
        raise click.Abort() from e


@tonic.group("mode")
def tonic_mode() -> None:
    """Manage synchronization mode."""


@tonic_mode.command("set")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.argument(
    "sync_mode",
    type=click.Choice(["designated", "best_effort", "broadcast", "consensus"]),
)
@click.option(
    "--source-peers",
    help="Comma-separated list of source peer IDs (for designated mode)",
)
@click.pass_context
def tonic_mode_set(
    _ctx,
    folder_path: str,
    sync_mode: str,
    source_peers: str | None,
) -> None:
    """Set synchronization mode for folder."""
    console = Console()

    try:
        # Parse source peers
        source_peers_list: list[str] | None = None
        if source_peers:
            source_peers_list = [p.strip() for p in source_peers.split(",") if p.strip()]

        # Update folder's sync mode
        folder = XetFolder(folder_path=folder_path)
        folder.set_sync_mode(sync_mode, source_peers_list)
        
        console.print(_("[green]✓[/green] Sync mode updated"))
        console.print(_("  Mode: {mode}").format(mode=sync_mode))
        if source_peers_list:
            console.print(_("  Source peers: {peers}").format(peers=', '.join(source_peers_list)))

    except Exception as e:
        console.print(_("[red]Error setting sync mode: {e}[/red]").format(e=e))
        logger.exception(_("Failed to set sync mode"))
        raise click.Abort() from e


@tonic_mode.command("get")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.pass_context
def tonic_mode_get(_ctx, folder_path: str) -> None:
    """Get current synchronization mode for folder."""
    console = Console()

    try:
        folder = XetFolder(folder_path=folder_path)
        status = folder.get_status()

        console.print(_("[bold]Sync Mode for: {path}[/bold]\n").format(path=folder_path))
        console.print(_("  Current mode: {mode}").format(mode=status.sync_mode))

    except Exception as e:
        console.print(_("[red]Error getting sync mode: {e}[/red]").format(e=e))
        logger.exception(_("Failed to get sync mode"))
        raise click.Abort() from e


@tonic_allowlist.group("alias")
def tonic_allowlist_alias() -> None:
    """Manage aliases for peers in allowlist."""


@tonic_allowlist_alias.command("add")
@click.argument("allowlist_path", type=click.Path())
@click.argument("peer_id", type=str)
@click.argument("alias", type=str)
@click.pass_context
def tonic_allowlist_alias_add(
    _ctx,
    allowlist_path: str,
    peer_id: str,
    alias: str,
) -> None:
    """Add or update alias for a peer."""
    console = Console()

    try:
        allowlist = XetAllowlist(allowlist_path=allowlist_path)
        asyncio.run(allowlist.load())

        if not allowlist.is_allowed(peer_id):
            console.print(_("[red]Peer {peer_id} not found in allowlist[/red]").format(peer_id=peer_id))
            console.print(_("  Add the peer first using 'tonic allowlist add'"))
            raise click.Abort()

        success = allowlist.set_alias(peer_id, alias)
        if success:
            asyncio.run(allowlist.save())
            console.print(_("[green]✓[/green] Set alias '{alias}' for peer {peer_id}").format(alias=alias, peer_id=peer_id))
        else:
            console.print(_("[red]Failed to set alias for peer {peer_id}[/red]").format(peer_id=peer_id))
            raise click.Abort()

    except Exception as e:
        console.print(_("[red]Error setting alias: {e}[/red]").format(e=e))
        logger.exception(_("Failed to set alias"))
        raise click.Abort() from e


@tonic_allowlist_alias.command("remove")
@click.argument("allowlist_path", type=click.Path())
@click.argument("peer_id", type=str)
@click.pass_context
def tonic_allowlist_alias_remove(
    _ctx,
    allowlist_path: str,
    peer_id: str,
) -> None:
    """Remove alias for a peer."""
    console = Console()

    try:
        allowlist = XetAllowlist(allowlist_path=allowlist_path)
        asyncio.run(allowlist.load())

        removed = allowlist.remove_alias(peer_id)
        if removed:
            asyncio.run(allowlist.save())
            console.print(_("[green]✓[/green] Removed alias for peer {peer_id}").format(peer_id=peer_id))
        else:
            console.print(_("[yellow]No alias found for peer {peer_id}[/yellow]").format(peer_id=peer_id))

    except Exception as e:
        console.print(_("[red]Error removing alias: {e}[/red]").format(e=e))
        logger.exception(_("Failed to remove alias"))
        raise click.Abort() from e


@tonic_allowlist_alias.command("list")
@click.argument("allowlist_path", type=click.Path())
@click.pass_context
def tonic_allowlist_alias_list(_ctx, allowlist_path: str) -> None:
    """List all aliases in allowlist."""
    console = Console()

    try:
        allowlist = XetAllowlist(allowlist_path=allowlist_path)
        asyncio.run(allowlist.load())

        peers = allowlist.get_peers()
        aliases = []

        for peer_id in peers:
            alias = allowlist.get_alias(peer_id)
            if alias:
                aliases.append((peer_id, alias))

        if not aliases:
            console.print(_("[yellow]No aliases found in allowlist[/yellow]"))
            return

        console.print(_("[bold]Aliases ({count}):[/bold]\n").format(count=len(aliases)))

        table = Table(show_header=True, header_style="bold")
        table.add_column("Peer ID", style="cyan")
        table.add_column("Alias", style="yellow")

        for peer_id, alias in aliases:
            table.add_row(peer_id, alias)

        console.print(table)

    except Exception as e:
        console.print(_("[red]Error listing aliases: {e}[/red]").format(e=e))
        logger.exception(_("Failed to list aliases"))
        raise click.Abort() from e
