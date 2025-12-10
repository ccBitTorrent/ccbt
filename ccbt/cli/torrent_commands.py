"""CLI commands for torrent control operations."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console

from ccbt.i18n import _


def _get_executor():
    """Lazy import to avoid circular dependency."""
    from ccbt.cli.main import _get_executor as _get_executor_impl

    return _get_executor_impl


@click.group()
def torrent() -> None:
    """Manage torrent operations."""


@torrent.command("pause")
@click.argument("info_hash")
@click.pass_context
def torrent_pause(ctx, info_hash: str) -> None:
    """Pause a torrent download."""
    console = Console()

    async def _pause_torrent() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute("torrent.pause", info_hash=info_hash)
            if not result.success:
                raise click.ClickException(result.error or _("Failed to pause torrent"))

            # Show checkpoint status if available
            checkpoint_info = ""
            if result.data and result.data.get("checkpoint_saved"):
                checkpoint_info = _(" (checkpoint saved)")
            
            console.print(
                _("[green]Torrent paused: {info_hash}{checkpoint_info}[/green]").format(
                    info_hash=info_hash, checkpoint_info=checkpoint_info
                )
            )
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_pause_torrent())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@torrent.command("resume")
@click.argument("info_hash")
@click.pass_context
def torrent_resume(ctx, info_hash: str) -> None:
    """Resume a paused torrent download."""
    console = Console()

    async def _resume_torrent() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute("torrent.resume", info_hash=info_hash)
            if not result.success:
                raise click.ClickException(result.error or _("Failed to resume torrent"))

            # Show checkpoint restoration status if available
            checkpoint_info = ""
            if result.data:
                if result.data.get("checkpoint_restored"):
                    checkpoint_info = _(" (checkpoint restored)")
                elif result.data.get("checkpoint_not_found"):
                    checkpoint_info = _(" (no checkpoint found)")

            console.print(
                _("[green]Torrent resumed: {info_hash}{checkpoint_info}[/green]").format(
                    info_hash=info_hash, checkpoint_info=checkpoint_info
                )
            )
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_resume_torrent())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@torrent.command("cancel")
@click.argument("info_hash")
@click.pass_context
def torrent_cancel(ctx, info_hash: str) -> None:
    """Cancel a torrent download (pause but keep in session)."""
    console = Console()

    async def _cancel_torrent() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute("torrent.cancel", info_hash=info_hash)
            if not result.success:
                raise click.ClickException(result.error or _("Failed to cancel torrent"))

            # Show checkpoint status if available
            checkpoint_info = ""
            if result.data and result.data.get("checkpoint_saved"):
                checkpoint_info = _(" (checkpoint saved)")

            console.print(
                _("[green]Torrent cancelled: {info_hash}{checkpoint_info}[/green]").format(
                    info_hash=info_hash, checkpoint_info=checkpoint_info
                )
            )
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_cancel_torrent())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@torrent.command("force-start")
@click.argument("info_hash")
@click.pass_context
def torrent_force_start(ctx, info_hash: str) -> None:
    """Force start a torrent (bypass queue limits)."""
    console = Console()

    async def _force_start_torrent() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute("torrent.force_start", info_hash=info_hash)
            if not result.success:
                raise click.ClickException(result.error or _("Failed to force start torrent"))

            console.print(_("[green]Torrent force started: {info_hash}[/green]").format(info_hash=info_hash))
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_force_start_torrent())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@torrent.command("add-tracker")
@click.argument("info_hash")
@click.argument("tracker_url")
@click.pass_context
def torrent_add_tracker(ctx, info_hash: str, tracker_url: str) -> None:
    """Add a tracker URL to a torrent."""
    console = Console()

    async def _add_tracker() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute(
                "torrent.add_tracker", info_hash=info_hash, tracker_url=tracker_url
            )
            if not result.success:
                raise click.ClickException(result.error or _("Failed to add tracker"))

            console.print(
                _("[green]Tracker added: {url} to torrent {info_hash}[/green]").format(
                    url=tracker_url, info_hash=info_hash
                )
            )
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_add_tracker())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@torrent.command("remove-tracker")
@click.argument("info_hash")
@click.argument("tracker_url")
@click.pass_context
def torrent_remove_tracker(ctx, info_hash: str, tracker_url: str) -> None:
    """Remove a tracker URL from a torrent."""
    console = Console()

    async def _remove_tracker() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute(
                "torrent.remove_tracker", info_hash=info_hash, tracker_url=tracker_url
            )
            if not result.success:
                raise click.ClickException(result.error or _("Failed to remove tracker"))

            console.print(
                _("[green]Tracker removed: {url} from torrent {info_hash}[/green]").format(
                    url=tracker_url, info_hash=info_hash
                )
            )
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_remove_tracker())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@click.group()
def pex() -> None:
    """Peer Exchange (PEX) operations."""


@pex.command("refresh")
@click.argument("info_hash")
@click.pass_context
def pex_refresh(ctx, info_hash: str) -> None:
    """Refresh Peer Exchange (PEX) for a torrent."""
    console = Console()

    async def _refresh_pex() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            # Use the executor adapter's refresh_pex method if available
            if hasattr(executor.adapter, "refresh_pex"):
                result = await executor.adapter.refresh_pex(info_hash)
                if result.get("success"):
                    console.print(
                        _("[green]PEX refreshed for torrent: {info_hash}[/green]").format(
                            info_hash=info_hash
                        )
                    )
                else:
                    error = result.get("error", _("Failed to refresh PEX"))
                    raise click.ClickException(error)
            else:
                # Fallback: try via executor
                result = await executor.execute("torrent.refresh_pex", info_hash=info_hash)
                if not result.success:
                    raise click.ClickException(result.error or _("Failed to refresh PEX"))
                console.print(
                    _("[green]PEX refreshed for torrent: {info_hash}[/green]").format(
                        info_hash=info_hash
                    )
                )
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_refresh_pex())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@click.group()
def dht() -> None:
    """DHT (Distributed Hash Table) operations."""


@dht.command("aggressive")
@click.argument("info_hash")
@click.option("--enable/--disable", default=True, help="Enable or disable aggressive mode (default: enable)")
@click.pass_context
def dht_aggressive(ctx, info_hash: str, enable: bool) -> None:
    """Set DHT aggressive discovery mode for a torrent."""
    console = Console()

    async def _set_aggressive_mode() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            # Use the executor adapter's IPC client if available
            if hasattr(executor.adapter, "ipc_client") and hasattr(executor.adapter.ipc_client, "set_dht_aggressive_mode"):
                result = await executor.adapter.ipc_client.set_dht_aggressive_mode(info_hash, enable)
                if result.get("success"):
                    mode_str = _("enabled") if enable else _("disabled")
                    console.print(
                        _("[green]DHT aggressive mode {mode} for torrent: {info_hash}[/green]").format(
                            mode=mode_str, info_hash=info_hash
                        )
                    )
                else:
                    error = result.get("error", _("Failed to set DHT aggressive mode"))
                    raise click.ClickException(error)
            else:
                # Fallback: try via executor
                result = await executor.execute("torrent.set_dht_aggressive_mode", info_hash=info_hash, enabled=enable)
                if not result.success:
                    raise click.ClickException(result.error or _("Failed to set DHT aggressive mode"))
                mode_str = _("enabled") if enable else _("disabled")
                console.print(
                    _("[green]DHT aggressive mode {mode} for torrent: {info_hash}[/green]").format(
                        mode=mode_str, info_hash=info_hash
                    )
                )
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_set_aggressive_mode())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@click.group()
def global_controls() -> None:
    """Global torrent control operations."""


@global_controls.command("pause-all")
@click.pass_context
def global_pause_all(ctx) -> None:
    """Pause all torrents."""
    console = Console()

    async def _pause_all() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute("torrent.global_pause_all")
            if not result.success:
                raise click.ClickException(result.error or _("Failed to pause all torrents"))

            count = result.data.get("success_count", 0)
            console.print(_("[green]Paused {count} torrent(s)[/green]").format(count=count))
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_pause_all())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@global_controls.command("resume-all")
@click.pass_context
def global_resume_all(ctx) -> None:
    """Resume all paused torrents."""
    console = Console()

    async def _resume_all() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute("torrent.global_resume_all")
            if not result.success:
                raise click.ClickException(result.error or _("Failed to resume all torrents"))

            count = result.data.get("success_count", 0)
            console.print(_("[green]Resumed {count} torrent(s)[/green]").format(count=count))
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_resume_all())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@global_controls.command("force-start-all")
@click.pass_context
def global_force_start_all(ctx) -> None:
    """Force start all torrents (bypass queue limits)."""
    console = Console()

    async def _force_start_all() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute("torrent.global_force_start_all")
            if not result.success:
                raise click.ClickException(result.error or _("Failed to force start all torrents"))

            count = result.data.get("success_count", 0)
            console.print(_("[green]Force started {count} torrent(s)[/green]").format(count=count))
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_force_start_all())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@click.group()
def peer() -> None:
    """Manage peer connections and rate limits."""


@peer.command("set-rate-limit")
@click.argument("info_hash")
@click.argument("peer_key")
@click.option("--upload", "-u", type=int, default=0, help="Upload rate limit (KiB/s, 0 = unlimited)")
@click.pass_context
def peer_set_rate_limit(ctx, info_hash: str, peer_key: str, upload: int) -> None:
    """Set upload rate limit for a specific peer."""
    console = Console()

    async def _set_rate_limit() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute(
                "peer.set_rate_limit",
                info_hash=info_hash,
                peer_key=peer_key,
                upload_limit_kib=upload,
            )
            if not result.success:
                raise click.ClickException(
                    result.error or _("Failed to set per-peer rate limit")
                )

            console.print(
                _("[green]Per-peer rate limit set: {peer_key} = {upload} KiB/s[/green]").format(
                    peer_key=peer_key, upload=upload
                )
            )
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_set_rate_limit())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@peer.command("get-rate-limit")
@click.argument("info_hash")
@click.argument("peer_key")
@click.pass_context
def peer_get_rate_limit(ctx, info_hash: str, peer_key: str) -> None:
    """Get upload rate limit for a specific peer."""
    console = Console()

    async def _get_rate_limit() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute(
                "peer.get_rate_limit",
                info_hash=info_hash,
                peer_key=peer_key,
            )
            if not result.success:
                raise click.ClickException(
                    result.error or _("Failed to get per-peer rate limit")
                )

            limit = result.data.get("upload_limit_kib", 0)
            limit_str = f"{limit} KiB/s" if limit > 0 else _("unlimited")
            console.print(
                _("[green]Per-peer rate limit for {peer_key}: {limit}[/green]").format(
                    peer_key=peer_key, limit=limit_str
                )
            )
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_get_rate_limit())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@peer.command("set-all-rate-limits")
@click.option("--upload", "-u", type=int, default=0, help="Upload rate limit (KiB/s, 0 = unlimited)")
@click.pass_context
def peer_set_all_rate_limits(ctx, upload: int) -> None:
    """Set upload rate limit for all active peers."""
    console = Console()

    async def _set_all_rate_limits() -> None:
        executor, is_daemon = await _get_executor()()

        if not executor:
            raise click.ClickException(
                _("Cannot connect to daemon. Start daemon with: 'btbt daemon start'")
            )

        try:
            result = await executor.execute(
                "peer.set_all_rate_limits",
                upload_limit_kib=upload,
            )
            if not result.success:
                raise click.ClickException(
                    result.error or _("Failed to set all peers rate limits")
                )

            updated_count = result.data.get("updated_count", 0)
            console.print(
                _("[green]Set rate limit for {count} peers: {upload} KiB/s[/green]").format(
                    count=updated_count, upload=upload
                )
            )
        finally:
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_set_all_rate_limits())
    except click.ClickException:
        raise
    except Exception as e:
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e

