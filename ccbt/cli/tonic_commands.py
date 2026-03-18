"""Tonic file and folder sync CLI commands.

This module provides CLI commands for managing .tonic files and XET folder
synchronization including create, link, sync, status, allowlist management,
and sync mode configuration.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import click
from rich.console import Console
from rich.table import Table

from ccbt.cli.tonic_generator import generate_tonic_from_folder, tonic_generate
from ccbt.core.tonic import TonicFile
from ccbt.core.tonic_link import generate_tonic_link
from ccbt.i18n import _
from ccbt.security.xet_allowlist import XetAllowlist

logger = logging.getLogger(__name__)


async def _allowlist_add(
    allowlist_path: str,
    peer_id: str,
    public_key: Optional[str],
    alias: Optional[str],
) -> None:
    """Async helper: load allowlist, add peer, save."""
    allowlist = XetAllowlist(allowlist_path=allowlist_path)
    await allowlist.load()
    public_key_bytes = None
    if public_key:
        public_key_bytes = bytes.fromhex(public_key)
        if len(public_key_bytes) != 32:
            msg = _("Public key must be 32 bytes (64 hex characters)")
            raise ValueError(msg)
    allowlist.add_peer(peer_id=peer_id, public_key=public_key_bytes, alias=alias)
    await allowlist.save()


async def _allowlist_remove(allowlist_path: str, peer_id: str) -> bool:
    """Async helper: load allowlist, remove peer, save if changed. Returns True if removed."""
    allowlist = XetAllowlist(allowlist_path=allowlist_path)
    await allowlist.load()
    removed = allowlist.remove_peer(peer_id)
    if removed:
        await allowlist.save()
    return removed


async def _allowlist_list(
    allowlist_path: str,
) -> tuple[list[str], XetAllowlist]:
    """Async helper: load allowlist, return (peer_ids, allowlist)."""
    allowlist = XetAllowlist(allowlist_path=allowlist_path)
    await allowlist.load()
    return (allowlist.get_peers(), allowlist)


async def _allowlist_alias_add(allowlist_path: str, peer_id: str, alias: str) -> bool:
    """Async helper: load, set alias, save. Returns True on success."""
    allowlist = XetAllowlist(allowlist_path=allowlist_path)
    await allowlist.load()
    if not allowlist.is_allowed(peer_id):
        return False
    success = allowlist.set_alias(peer_id, alias)
    if success:
        await allowlist.save()
    return success


async def _allowlist_alias_remove(allowlist_path: str, peer_id: str) -> bool:
    """Async helper: load, remove alias, save if changed. Returns True if removed."""
    allowlist = XetAllowlist(allowlist_path=allowlist_path)
    await allowlist.load()
    removed = allowlist.remove_alias(peer_id)
    if removed:
        await allowlist.save()
    return removed


async def _allowlist_alias_list(
    allowlist_path: str,
) -> list[tuple[str, str]]:
    """Async helper: load allowlist, return list of (peer_id, alias)."""
    allowlist = XetAllowlist(allowlist_path=allowlist_path)
    await allowlist.load()
    peers = allowlist.get_peers()
    return [
        (pid, allowlist.get_alias(pid) or "")
        for pid in peers
        if allowlist.get_alias(pid)
    ]


@click.group()
def tonic() -> None:
    """Manage .tonic files and XET folder synchronization."""


@tonic.command("create")
@click.argument(
    "folder_path", type=click.Path(exists=True, file_okay=False, dir_okay=True)
)
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
    output_path: Optional[str],
    sync_mode: str,
    source_peers: Optional[str],
    allowlist_path: Optional[str],
    git_ref: Optional[str],
    announce: Optional[str],
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
@click.argument(
    "folder_path", type=click.Path(exists=True, file_okay=False, dir_okay=True)
)
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
    _ctx,
    folder_path: str,
    tonic_file: Optional[str],
    sync_mode: Optional[str],
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
            tracker_list: Optional[list[str]] = None
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
            _tonic_file_bytes, link = asyncio.run(
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
        raise click.Abort from e


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
    _ctx,
    tonic_input: str,
    output_dir: Optional[str],
    check_interval: float,
) -> None:
    """Start syncing folder from .tonic file or tonic?: link."""
    console = Console()

    try:
        from ccbt.cli.main import _get_executor

        async def _start_sync() -> tuple[object, Any]:
            executor, _ = await _get_executor()
            if executor is None:
                msg = "Unable to acquire XET executor"
                raise RuntimeError(msg)
            result = await executor.execute(
                "xet.sync",
                tonic_input=tonic_input,
                output_dir=output_dir,
                check_interval=check_interval,
            )
            return executor, result

        _executor, result = asyncio.run(_start_sync())
        if not result.success:
            msg = result.error or "Failed to start sync"
            raise RuntimeError(msg)

        data = result.data or {}
        console.print(_("[green]✓[/green] Folder sync started"))
        console.print(
            _("  Folder key: {folder_key}").format(
                folder_key=data.get("folder_key", "unknown")
            )
        )
        console.print(
            _("  Output directory: {dir}").format(
                dir=data.get("folder_path", output_dir or "unknown")
            )
        )
        if data.get("workspace_id"):
            console.print(_("  Workspace ID: {id}").format(id=data.get("workspace_id")))
        console.print(_("  Use 'ccbt tonic status' to check sync status"))

    except Exception as e:
        console.print(_("[red]Error starting sync: {e}[/red]").format(e=e))
        logger.exception(_("Failed to start sync"))
        raise click.Abort from e


@tonic.command("status")
@click.argument("folder_path", type=str)
@click.pass_context
def tonic_status(_ctx, folder_path: str) -> None:
    """Show sync status for a folder."""
    console = Console()

    try:
        from ccbt.cli.main import _get_executor

        async def _fetch_status() -> Any:
            executor, _ = await _get_executor()
            if executor is None:
                msg = "Unable to acquire XET executor"
                raise RuntimeError(msg)
            return await executor.execute("xet.status", folder_path=folder_path)

        result = asyncio.run(_fetch_status())
        if not result.success:
            msg = result.error or "Failed to fetch sync status"
            raise RuntimeError(msg)
        status = result.data or {}

        console.print(
            _("[bold]Sync Status for: {path}[/bold]\n").format(path=folder_path)
        )

        table = Table(show_header=True, header_style="bold")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        if status.get("folder_key"):
            table.add_row("Folder Key", str(status["folder_key"]))
        if status.get("workspace_id"):
            table.add_row("Workspace ID", str(status["workspace_id"]))
        table.add_row("Sync Mode", str(status.get("sync_mode", "unknown")))
        table.add_row("Is Syncing", "Yes" if status.get("is_syncing") else "No")
        table.add_row("Pending Changes", str(status.get("pending_changes", 0)))
        table.add_row("Connected Peers", str(status.get("connected_peers", 0)))
        table.add_row("Synced Peers", str(status.get("synced_peers", 0)))
        table.add_row(
            "Sync Progress",
            f"{float(status.get('sync_progress', 0.0)) * 100:.1f}%",
        )
        current_git_ref = status.get("current_git_ref")
        if current_git_ref:
            table.add_row("Git Ref", str(current_git_ref)[:16] + "...")
        if status.get("last_sync_time"):
            import time

            last_sync_ago = time.time() - float(status["last_sync_time"])
            table.add_row("Last Sync", f"{last_sync_ago:.1f}s ago")
        if status.get("error"):
            table.add_row("Error", f"[red]{status['error']}[/red]")

        console.print(table)

    except Exception as e:
        console.print(_("[red]Error getting status: {e}[/red]").format(e=e))
        logger.exception(_("Failed to get sync status"))
        raise click.Abort from e


@tonic.command("share")
@click.argument(
    "folder_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option(
    "--sync-mode",
    type=click.Choice(["designated", "best_effort", "broadcast", "consensus"]),
    default="best_effort",
    help="Synchronization mode",
)
@click.option(
    "--check-interval",
    type=float,
    default=None,
    help="Folder check interval in seconds",
)
@click.option(
    "--allowlist",
    "_allowlist_path",
    type=click.Path(),
    help="Path to allowlist file",
)
@click.option(
    "--output",
    "-o",
    "tonic_output",
    type=click.Path(),
    help="Write .tonic file to this path",
)
@click.pass_context
def tonic_share(
    _ctx,
    folder_path: str,
    sync_mode: str,
    check_interval: Optional[float],
    _allowlist_path: Optional[str],
    tonic_output: Optional[str],
) -> None:
    """Register folder for sync and print shareable link (requires daemon)."""
    console = Console()
    try:
        from ccbt.cli.main import _get_executor

        async def _do_share() -> Any:
            executor, is_daemon = await _get_executor()
            if executor is None or not is_daemon:
                msg = _(
                    "tonic share requires the daemon. Start it with: btbt daemon start"
                )
                raise RuntimeError(msg)
            return await executor.execute(
                "xet.share_folder",
                folder_path=folder_path,
                sync_mode=sync_mode,
                check_interval=check_interval,
                output_tonic=tonic_output,
            )

        result = asyncio.run(_do_share())
        if not result.success:
            console.print(_("[red]Error: {e}[/red]").format(e=result.error or ""))
            raise click.ClickException(result.error or _("Share failed"))

        data = result.data or {}
        link = data.get("link", "")
        console.print(_("[bold green]Share link:[/bold green]"))
        console.print(link)
        if data.get("folder_key"):
            console.print(_("  Folder key: {key}").format(key=data["folder_key"]))
        if data.get("workspace_id"):
            console.print(_("  Workspace ID: {id}").format(id=data["workspace_id"]))
        if data.get("tonic_path"):
            console.print(_("  .tonic file: {path}").format(path=data["tonic_path"]))
        console.print(
            _(
                'Others can join with: ccbt tonic sync "{link}" --output <directory>'
            ).format(link=link)
        )
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        logger.exception(_("Failed to share folder"))
        raise click.Abort from e


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
    public_key: Optional[str],
    alias: Optional[str],
) -> None:
    """Add peer to allowlist."""
    console = Console()

    try:
        asyncio.run(
            _allowlist_add(
                allowlist_path=allowlist_path,
                peer_id=peer_id,
                public_key=public_key,
                alias=alias,
            )
        )
        msg = _("[green]✓[/green] Added peer {peer_id} to allowlist").format(
            peer_id=peer_id
        )
        if alias:
            msg = _(
                "[green]✓[/green] Added peer {peer_id} to allowlist with alias '{alias}'"
            ).format(peer_id=peer_id, alias=alias)
        console.print(msg)

    except ValueError as e:
        console.print(_("[red]Invalid public key: {e}[/red]").format(e=e))
        logger.exception(_("Failed to add peer to allowlist"))
        raise click.Abort from e
    except Exception as e:
        console.print(_("[red]Error adding peer to allowlist: {e}[/red]").format(e=e))
        logger.exception(_("Failed to add peer to allowlist"))
        raise click.Abort from e


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
        removed = asyncio.run(_allowlist_remove(allowlist_path, peer_id))
        if removed:
            console.print(
                _("[green]✓[/green] Removed peer {peer_id} from allowlist").format(
                    peer_id=peer_id
                )
            )
        else:
            console.print(
                _("[yellow]Peer {peer_id} not found in allowlist[/yellow]").format(
                    peer_id=peer_id
                )
            )

    except Exception as e:
        console.print(
            _("[red]Error removing peer from allowlist: {e}[/red]").format(e=e)
        )
        logger.exception(_("Failed to remove peer from allowlist"))
        raise click.Abort from e


@tonic_allowlist.command("list")
@click.argument("allowlist_path", type=click.Path())
@click.pass_context
def tonic_allowlist_list(_ctx, allowlist_path: str) -> None:
    """List peers in allowlist."""
    console = Console()

    try:
        peers, allowlist = asyncio.run(_allowlist_list(allowlist_path))

        if not peers:
            console.print(_("[yellow]Allowlist is empty[/yellow]"))
            return

        console.print(
            _("[bold]Allowlist ({count} peers):[/bold]\n").format(count=len(peers))
        )

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
        raise click.Abort from e


@tonic.group("mode")
def tonic_mode() -> None:
    """Manage synchronization mode."""


@tonic_mode.command("set")
@click.argument("folder_path", type=str)
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
    source_peers: Optional[str],
) -> None:
    """Set synchronization mode for folder."""
    console = Console()

    try:
        from ccbt.cli.main import _get_executor

        # Parse source peers
        source_peers_list: Optional[list[str]] = None
        if source_peers:
            source_peers_list = [
                p.strip() for p in source_peers.split(",") if p.strip()
            ]

        async def _set_mode() -> Any:
            executor, _ = await _get_executor()
            if executor is None:
                msg = "Unable to acquire XET executor"
                raise RuntimeError(msg)
            return await executor.execute(
                "xet.set_sync_mode",
                folder_path=folder_path,
                sync_mode=sync_mode,
                source_peers=source_peers_list,
            )

        result = asyncio.run(_set_mode())
        if not result.success:
            msg = result.error or "Failed to update sync mode"
            raise RuntimeError(msg)

        console.print(_("[green]✓[/green] Sync mode updated"))
        console.print(_("  Mode: {mode}").format(mode=sync_mode))
        if source_peers_list:
            console.print(
                _("  Source peers: {peers}").format(peers=", ".join(source_peers_list))
            )

    except Exception as e:
        console.print(_("[red]Error setting sync mode: {e}[/red]").format(e=e))
        logger.exception(_("Failed to set sync mode"))
        raise click.Abort from e


@tonic_mode.command("get")
@click.argument("folder_path", type=str)
@click.pass_context
def tonic_mode_get(_ctx, folder_path: str) -> None:
    """Get current synchronization mode for folder."""
    console = Console()

    try:
        from ccbt.cli.main import _get_executor

        async def _get_mode() -> Any:
            executor, _ = await _get_executor()
            if executor is None:
                msg = "Unable to acquire XET executor"
                raise RuntimeError(msg)
            return await executor.execute("xet.get_sync_mode", folder_path=folder_path)

        result = asyncio.run(_get_mode())
        if not result.success:
            msg = result.error or "Failed to fetch sync mode"
            raise RuntimeError(msg)
        status = result.data or {}

        console.print(
            _("[bold]Sync Mode for: {path}[/bold]\n").format(path=folder_path)
        )
        console.print(
            _("  Current mode: {mode}").format(mode=status.get("sync_mode", "unknown"))
        )

    except Exception as e:
        console.print(_("[red]Error getting sync mode: {e}[/red]").format(e=e))
        logger.exception(_("Failed to get sync mode"))
        raise click.Abort from e


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
        success = asyncio.run(_allowlist_alias_add(allowlist_path, peer_id, alias))
        if success:
            console.print(
                _("[green]✓[/green] Set alias '{alias}' for peer {peer_id}").format(
                    alias=alias, peer_id=peer_id
                )
            )
        else:
            console.print(
                _("[red]Peer {peer_id} not found in allowlist[/red]").format(
                    peer_id=peer_id
                )
            )
            console.print(_("  Add the peer first using 'tonic allowlist add'"))
            raise click.Abort

    except Exception as e:
        console.print(_("[red]Error setting alias: {e}[/red]").format(e=e))
        logger.exception(_("Failed to set alias"))
        raise click.Abort from e


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
        removed = asyncio.run(_allowlist_alias_remove(allowlist_path, peer_id))
        if removed:
            console.print(
                _("[green]✓[/green] Removed alias for peer {peer_id}").format(
                    peer_id=peer_id
                )
            )
        else:
            console.print(
                _("[yellow]No alias found for peer {peer_id}[/yellow]").format(
                    peer_id=peer_id
                )
            )

    except Exception as e:
        console.print(_("[red]Error removing alias: {e}[/red]").format(e=e))
        logger.exception(_("Failed to remove alias"))
        raise click.Abort from e


@tonic_allowlist_alias.command("list")
@click.argument("allowlist_path", type=click.Path())
@click.pass_context
def tonic_allowlist_alias_list(_ctx, allowlist_path: str) -> None:
    """List all aliases in allowlist."""
    console = Console()

    try:
        aliases = asyncio.run(_allowlist_alias_list(allowlist_path))

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
        raise click.Abort from e
