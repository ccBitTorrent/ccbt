
"""IPFS protocol CLI commands (add, get, pin, unpin, stats, peers)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ccbt.i18n import _
from ccbt.protocols.base import ProtocolType

# IPFS support is optional - handle ImportError gracefully
try:
    from ccbt.protocols.ipfs import IPFSProtocol
except ImportError:
    IPFSProtocol = None  # type: ignore[assignment, misc]

from ccbt.session.session import AsyncSessionManager

logger = logging.getLogger(__name__)


async def _get_ipfs_protocol() -> IPFSProtocol | None:
    """Get IPFS protocol instance from session manager.

    Note: If daemon is running, this will check via IPC but cannot return
    the actual protocol instance. Commands using this should handle None
    and route operations via IPC instead.
    """
    if IPFSProtocol is None:
        return None

    from ccbt.cli.main import _get_executor
    from ccbt.executor.session_adapter import LocalSessionAdapter

    # Get executor (daemon or local)
    executor, is_daemon = await _get_executor()

    if is_daemon and executor:
        # Daemon mode - use executor to get protocol info
        result = await executor.execute("protocol.get_ipfs")
        if result.success and result.data.get("protocol"):
            protocol_info = result.data["protocol"]
            # Protocol is enabled in daemon, but we can't return the instance
            # Commands should use executor for operations instead
            if protocol_info.enabled:
                return (
                    None  # Protocol enabled but instance not available in daemon mode
                )
        return None

    # Local mode - get protocol from session
    if executor and isinstance(executor.adapter, LocalSessionAdapter):
        session = executor.adapter.session_manager
        try:
            # Find IPFS protocol in session's protocols list
            protocols = getattr(session, "protocols", [])
            for protocol in protocols:
                if isinstance(protocol, IPFSProtocol):
                    return protocol
            # Also try protocol manager if protocols list is empty
            protocol_manager = getattr(session, "protocol_manager", None)
            if protocol_manager:
                ipfs_protocol = protocol_manager.get_protocol(ProtocolType.IPFS)
                if isinstance(ipfs_protocol, IPFSProtocol):
                    return ipfs_protocol
        except Exception:  # pragma: no cover - CLI error handler
            logger.exception("Failed to get IPFS protocol from session")

    # Fallback: create temporary session if executor not available
    # CRITICAL FIX: Use safe local session creation helper
    try:
        from ccbt.cli.main import _ensure_local_session_safe

        session = await _ensure_local_session_safe(force_local=True)
        try:
            # Find IPFS protocol in session's protocols list
            protocols = getattr(session, "protocols", [])
            for protocol in protocols:
                if isinstance(protocol, IPFSProtocol):
                    return protocol
            # Also try protocol manager if protocols list is empty
            protocol_manager = getattr(session, "protocol_manager", None)
            if protocol_manager:
                ipfs_protocol = protocol_manager.get_protocol(ProtocolType.IPFS)
                if isinstance(ipfs_protocol, IPFSProtocol):
                    return ipfs_protocol
            return None
        finally:
            await session.stop()
    except Exception:  # pragma: no cover - CLI error handler
        logger.exception("Failed to get IPFS protocol")
        return None


@click.command("ipfs-add")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--pin/--no-pin", default=False, help="Pin content after adding")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def ipfs_add(path: Path, pin: bool, json_output: bool) -> None:
    """Add file or directory to IPFS."""
    console = Console()

    async def _add() -> None:
        if IPFSProtocol is None:
            console.print(
                "[red]Error: IPFS support not available.[/red]\n"
                "[yellow]Install the 'ipfshttpclient' package: pip install ipfshttpclient[/yellow]"
            )
            return
        ipfs = await _get_ipfs_protocol()
        if not ipfs:
            console.print(_("[red]IPFS protocol not available[/red]"))
            return

        try:
            # Read file content
            if path.is_file():
                content = path.read_bytes()
                cid = await ipfs.add_content(content)
                if pin:
                    await ipfs.pin_content(cid)
                if json_output:
                    console.print(json.dumps({"cid": cid, "pinned": pin}))
                else:
                    console.print(_("[green]Added to IPFS:[/green] {cid}").format(cid=cid))
                    if pin:
                        console.print(_("[green]Content pinned[/green]"))
            else:
                console.print(_("[red]Directories not yet supported[/red]"))
        except Exception as e:  # pragma: no cover - CLI error handler
            console.print(_("[red]Error adding content: {e}[/red]").format(e=e))
            logger.exception(_("Failed to add content"))

    asyncio.run(_add())


@click.command("ipfs-get")
@click.argument("cid", type=str)
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Output file path"
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def ipfs_get(cid: str, output: Path | None, json_output: bool) -> None:
    """Get content from IPFS by CID."""
    console = Console()

    async def _get() -> None:
        ipfs = await _get_ipfs_protocol()
        if not ipfs:
            console.print(_("[red]IPFS protocol not available[/red]"))
            return

        try:
            content = await ipfs.get_content(cid)
            if not content:
                console.print(_("[red]Content not found: {cid}[/red]").format(cid=cid))
                return

            if output:
                output.write_bytes(content)
                if json_output:
                    console.print(json.dumps({"cid": cid, "saved_to": str(output)}))
                else:
                    console.print(_("[green]Content saved to:[/green] {output}").format(output=output))
            elif json_output:
                console.print(json.dumps({"cid": cid, "size": len(content)}))
            else:
                console.print(content.decode("utf-8", errors="replace"))
        except Exception as e:  # pragma: no cover - CLI error handler
            console.print(_("[red]Error getting content: {e}[/red]").format(e=e))
            logger.exception(_("Failed to get content"))

    asyncio.run(_get())


@click.command("ipfs-pin")
@click.argument("cid", type=str)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def ipfs_pin(cid: str, json_output: bool) -> None:
    """Pin content in IPFS."""
    console = Console()

    async def _pin() -> None:
        ipfs = await _get_ipfs_protocol()
        if not ipfs:
            console.print(_("[red]IPFS protocol not available[/red]"))
            return

        try:
            await ipfs.pin_content(cid)
            if json_output:
                console.print(json.dumps({"cid": cid, "pinned": True}))
            else:
                console.print(_("[green]Pinned:[/green] {cid}").format(cid=cid))
        except Exception as e:  # pragma: no cover - CLI error handler
            console.print(_("[red]Error pinning content: {e}[/red]").format(e=e))
            logger.exception(_("Failed to pin content"))

    asyncio.run(_pin())


@click.command("ipfs-unpin")
@click.argument("cid", type=str)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def ipfs_unpin(cid: str, json_output: bool) -> None:
    """Unpin content in IPFS."""
    console = Console()

    async def _unpin() -> None:
        ipfs = await _get_ipfs_protocol()
        if not ipfs:
            console.print(_("[red]IPFS protocol not available[/red]"))
            return

        try:
            await ipfs.unpin_content(cid)
            if json_output:
                console.print(json.dumps({"cid": cid, "pinned": False}))
            else:
                console.print(_("[green]Unpinned:[/green] {cid}").format(cid=cid))
        except Exception as e:  # pragma: no cover - CLI error handler
            console.print(_("[red]Error unpinning content: {e}[/red]").format(e=e))
            logger.exception(_("Failed to unpin content"))

    asyncio.run(_unpin())


@click.command("ipfs-stats")
@click.argument("cid", type=str, required=False)
@click.option("--all", "all_stats", is_flag=True, help="Show stats for all content")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def ipfs_stats(cid: str | None, all_stats: bool, json_output: bool) -> None:
    """Show IPFS content statistics."""
    console = Console()

    async def _stats() -> None:
        ipfs = await _get_ipfs_protocol()
        if not ipfs:
            console.print(_("[red]IPFS protocol not available[/red]"))
            return

        try:
            if all_stats:
                stats = ipfs.get_all_content_stats()
                if json_output:
                    console.print(json.dumps(stats, indent=2))
                else:
                    table = Table(title="IPFS Content Statistics")
                    table.add_column("CID", style="cyan")
                    table.add_column("Size", style="green")
                    table.add_column("Pinned", style="yellow")
                    for cid_key, stat in stats.items():
                        table.add_row(
                            cid_key,
                            str(stat.get("size", 0)),
                            str(stat.get("pinned", False)),
                        )
                    console.print(table)
            elif cid:
                stats = ipfs.get_content_stats(cid)
                if json_output:
                    console.print(json.dumps(stats, indent=2) if stats else "null")
                elif stats:
                    table = Table(title=f"IPFS Stats: {cid}")
                    table.add_column("Metric", style="cyan")
                    table.add_column("Value", style="green")
                    for key, value in stats.items():
                        table.add_row(key, str(value))
                    console.print(table)
                else:
                    console.print(_("[red]No stats found for CID: {cid}[/red]").format(cid=cid))
            else:
                console.print(_("[red]Specify CID or use --all[/red]"))
        except Exception as e:  # pragma: no cover - CLI error handler
            console.print(_("[red]Error getting stats: {e}[/red]").format(e=e))
            logger.exception(_("Failed to get stats"))

    asyncio.run(_stats())


@click.command("ipfs-peers")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def ipfs_peers(json_output: bool) -> None:
    """List connected IPFS peers."""
    console = Console()

    async def _peers() -> None:
        ipfs = await _get_ipfs_protocol()
        if not ipfs:
            console.print(_("[red]IPFS protocol not available[/red]"))
            return

        try:
            peers_dict = ipfs.get_ipfs_peers()
            # Convert IPFSPeer objects to dicts for JSON serialization
            peers_list = [
                {
                    "peer_id": peer.peer_id,
                    "multiaddr": peer.multiaddr,
                    "protocols": peer.protocols,
                }
                for peer in peers_dict.values()
            ]
            if json_output:
                console.print(json.dumps(peers_list, indent=2))
            else:
                table = Table(title="IPFS Peers")
                table.add_column("Peer ID", style="cyan")
                table.add_column("Multiaddr", style="green")
                table.add_column("Protocols", style="yellow")
                for peer in peers_list:
                    table.add_row(
                        peer.get("peer_id", "N/A"),
                        peer.get("multiaddr", "N/A"),
                        ", ".join(peer.get("protocols", [])),
                    )
                console.print(table)
        except Exception as e:  # pragma: no cover - CLI error handler
            console.print(_("[red]Error getting peers: {e}[/red]").format(e=e))
            logger.exception(_("Failed to get peers"))

    asyncio.run(_peers())


@click.command("ipfs-content")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def ipfs_content(json_output: bool) -> None:
    """List all IPFS content."""
    console = Console()

    async def _content() -> None:
        ipfs = await _get_ipfs_protocol()
        if not ipfs:
            console.print(_("[red]IPFS protocol not available[/red]"))
            return

        try:
            content_dict = ipfs.get_ipfs_content()
            # Convert IPFSContent objects to dicts for JSON serialization
            content_list = [
                {
                    "cid": content.cid,
                    "size": content.size,
                    "blocks": len(content.blocks),
                }
                for content in content_dict.values()
            ]
            if json_output:
                console.print(json.dumps(content_list, indent=2))
            else:
                table = Table(title="IPFS Content")
                table.add_column("CID", style="cyan")
                table.add_column("Size", style="green")
                table.add_column("Blocks", style="yellow")
                for cont in content_list:
                    table.add_row(
                        cont.get("cid", "N/A"),
                        str(cont.get("size", 0)),
                        str(cont.get("blocks", 0)),
                    )
                console.print(table)
        except Exception as e:  # pragma: no cover - CLI error handler
            console.print(_("[red]Error getting content: {e}[/red]").format(e=e))
            logger.exception(_("Failed to get content"))

    asyncio.run(_content())


@click.group("ipfs")
def ipfs_group() -> None:
    """IPFS protocol commands.

    Note: IPFS support requires the 'ipfshttpclient' package.
    Install it with: pip install ipfshttpclient
    """
    # Note: We don't check IPFSProtocol here to allow the group to be created
    # Individual commands will handle the missing dependency gracefully


# Register all commands to the group
ipfs_group.add_command(ipfs_add)
ipfs_group.add_command(ipfs_get)
ipfs_group.add_command(ipfs_pin)
ipfs_group.add_command(ipfs_unpin)
ipfs_group.add_command(ipfs_stats)
ipfs_group.add_command(ipfs_peers)
ipfs_group.add_command(ipfs_content)
