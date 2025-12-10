"""CLI commands for per-torrent configuration management.

from __future__ import annotations

Provides commands to set, get, list, and reset per-torrent configuration options.
"""

from __future__ import annotations

import asyncio
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from ccbt.daemon.daemon_manager import DaemonManager
from ccbt.daemon.ipc_client import IPCClient  # type: ignore[attr-defined]
from ccbt.i18n import _
from ccbt.session.session import AsyncSessionManager
from ccbt.utils.logging_config import get_logger

logger = get_logger(__name__)
console = Console()


async def _get_torrent_session(
    info_hash_hex: str, session_manager: AsyncSessionManager | None = None
) -> Any:
    """Get torrent session by info hash.

    Args:
        info_hash_hex: Torrent info hash as hex string
        session_manager: Optional session manager (will create if None)

    Returns:
        AsyncTorrentSession instance or None if not found

    """
    if session_manager is None:
        session_manager = AsyncSessionManager(".")

    try:
        info_hash = bytes.fromhex(info_hash_hex)
    except ValueError:
        console.print(_("[red]Invalid info hash format[/red]"))
        return None

    async with session_manager.lock:
        torrent_session = session_manager.torrents.get(info_hash)
        return torrent_session


def _parse_value(raw: str) -> bool | int | float | str:
    """Parse string value to appropriate type.

    Args:
        raw: Raw string value

    Returns:
        Parsed value (bool, int, float, or str)

    """
    low = raw.lower()
    if low in {"true", "1", "yes", "on"}:
        return True
    if low in {"false", "0", "no", "off"}:
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


@click.group("torrent")
def torrent() -> None:
    """Manage torrent configuration and operations."""


@torrent.group("config")
def torrent_config() -> None:
    """Manage per-torrent configuration options."""


@torrent_config.command("set")
@click.argument("info_hash")
@click.argument("key")
@click.argument("value")
@click.option(
    "--save-checkpoint",
    is_flag=True,
    help=_("Save checkpoint immediately after setting option"),
)
@click.pass_context
def torrent_config_set(
    ctx: click.Context, info_hash: str, key: str, value: str, save_checkpoint: bool
) -> None:
    """Set a per-torrent configuration option.

    Examples:
        btbt torrent config set abc123... piece_selection sequential
        btbt torrent config set abc123... streaming_mode true
        btbt torrent config set abc123... max_peers_per_torrent 50

    """
    async def _set_option() -> None:
        # Check if daemon is running
        daemon_manager = DaemonManager()
        if daemon_manager.is_running():
            # Use daemon IPC
            client = IPCClient()
            try:
                # Get torrent session via IPC
                result = await client.execute(
                    "torrent.get_session", info_hash=info_hash
                )
                if not result.success:
                    console.print(
                        _("[red]Torrent not found: {hash}[/red]").format(
                            hash=info_hash[:12] + "..."
                        )
                    )
                    return

                # Set option via IPC
                parsed_value = _parse_value(value)
                result = await client.execute(
                    "torrent.set_option",
                    info_hash=info_hash,
                    key=key,
                    value=parsed_value,
                )
                if result.success:
                    console.print(
                        _("[green]Set {key} = {value} for torrent {hash}[/green]").format(
                            key=key, value=parsed_value, hash=info_hash[:12] + "..."
                        )
                    )
                    if save_checkpoint:
                        await client.execute(
                            "torrent.save_checkpoint", info_hash=info_hash
                        )
                        console.print(_("[green]Checkpoint saved[/green]"))
                else:
                    console.print(
                        _("[red]Failed to set option: {error}[/red]").format(
                            error=result.error or "Unknown error"
                        )
                    )
            finally:
                await client.close()
        else:
            # Use local session
            session_manager = AsyncSessionManager(".")
            torrent_session = await _get_torrent_session(info_hash, session_manager)
            if torrent_session is None:
                console.print(
                    _("[red]Torrent not found: {hash}[/red]").format(
                        hash=info_hash[:12] + "..."
                    )
                )
                return

            # Set option
            parsed_value = _parse_value(value)
            torrent_session.options[key] = parsed_value
            torrent_session._apply_per_torrent_options()

            console.print(
                _("[green]Set {key} = {value} for torrent {hash}[/green]").format(
                    key=key, value=parsed_value, hash=info_hash[:12] + "..."
                )
            )

            if save_checkpoint:
                if hasattr(torrent_session, "checkpoint_controller"):
                    await torrent_session.checkpoint_controller.save_checkpoint_state(
                        torrent_session
                    )
                    console.print(_("[green]Checkpoint saved[/green]"))

    asyncio.run(_set_option())


@torrent_config.command("get")
@click.argument("info_hash")
@click.argument("key")
@click.pass_context
def torrent_config_get(ctx: click.Context, info_hash: str, key: str) -> None:
    """Get a per-torrent configuration option value.

    Examples:
        btbt torrent config get abc123... piece_selection
        btbt torrent config get abc123... streaming_mode

    """
    async def _get_option() -> None:
        # Check if daemon is running
        daemon_manager = DaemonManager()
        if daemon_manager.is_running():
            # Use daemon IPC
            client = IPCClient()
            try:
                result = await client.execute(
                    "torrent.get_option", info_hash=info_hash, key=key
                )
                if result.success:
                    value = result.data.get("value")
                    if value is not None:
                        console.print(_("{key} = {value}").format(key=key, value=value))
                    else:
                        console.print(_("[yellow]{key} is not set[/yellow]").format(key=key))
                else:
                    console.print(
                        _("[red]Torrent not found or option not set[/red]")
                    )
            finally:
                await client.close()
        else:
            # Use local session
            session_manager = AsyncSessionManager(".")
            torrent_session = await _get_torrent_session(info_hash, session_manager)
            if torrent_session is None:
                console.print(
                    _("[red]Torrent not found: {hash}[/red]").format(
                        hash=info_hash[:12] + "..."
                    )
                )
                return

            # Get option
            value = torrent_session.options.get(key)
            if value is not None:
                console.print(_("{key} = {value}").format(key=key, value=value))
            else:
                console.print(_("[yellow]{key} is not set[/yellow]").format(key=key))

    asyncio.run(_get_option())


@torrent_config.command("list")
@click.argument("info_hash")
@click.pass_context
def torrent_config_list(ctx: click.Context, info_hash: str) -> None:
    """List all per-torrent configuration options and rate limits.

    Examples:
        btbt torrent config list abc123...

    """
    async def _list_options() -> None:
        # Check if daemon is running
        daemon_manager = DaemonManager()
        if daemon_manager.is_running():
            # Use daemon IPC
            client = IPCClient()
            try:
                result = await client.execute(
                    "torrent.get_config", info_hash=info_hash
                )
                if result.success:
                    data = result.data
                    options = data.get("options", {})
                    rate_limits = data.get("rate_limits", {})

                    table = Table(title=_("Per-Torrent Config: {hash}...").format(hash=info_hash[:12]))
                    table.add_column(_("Option"), style="cyan")
                    table.add_column(_("Value"), style="green")

                    if options:
                        for opt_key, opt_value in sorted(options.items()):
                            table.add_row(opt_key, str(opt_value))
                    else:
                        table.add_row(_("(no options set)"), "-")

                    if rate_limits:
                        table.add_row("", "")  # Separator
                        table.add_row(
                            _("Download Limit"),
                            f"{rate_limits.get('down_kib', 0)} KiB/s"
                            if rate_limits.get("down_kib", 0) > 0
                            else _("Unlimited"),
                        )
                        table.add_row(
                            _("Upload Limit"),
                            f"{rate_limits.get('up_kib', 0)} KiB/s"
                            if rate_limits.get("up_kib", 0) > 0
                            else _("Unlimited"),
                        )

                    console.print(table)
                else:
                    console.print(
                        _("[red]Torrent not found: {hash}[/red]").format(
                            hash=info_hash[:12] + "..."
                        )
                    )
            finally:
                await client.close()
        else:
            # Use local session
            session_manager = AsyncSessionManager(".")
            torrent_session = await _get_torrent_session(info_hash, session_manager)
            if torrent_session is None:
                console.print(
                    _("[red]Torrent not found: {hash}[/red]").format(
                        hash=info_hash[:12] + "..."
                    )
                )
                return

            # Get options and rate limits
            options = torrent_session.options
            rate_limits = {}
            if session_manager and hasattr(session_manager, "_per_torrent_limits"):
                info_hash_bytes = bytes.fromhex(info_hash)
                rate_limits = session_manager._per_torrent_limits.get(
                    info_hash_bytes, {}
                )

            table = Table(title=_("Per-Torrent Config: {hash}...").format(hash=info_hash[:12]))
            table.add_column(_("Option"), style="cyan")
            table.add_column(_("Value"), style="green")

            if options:
                for opt_key, opt_value in sorted(options.items()):
                    table.add_row(opt_key, str(opt_value))
            else:
                table.add_row(_("(no options set)"), "-")

            if rate_limits:
                table.add_row("", "")  # Separator
                table.add_row(
                    _("Download Limit"),
                    f"{rate_limits.get('down_kib', 0)} KiB/s"
                    if rate_limits.get("down_kib", 0) > 0
                    else _("Unlimited"),
                )
                table.add_row(
                    _("Upload Limit"),
                    f"{rate_limits.get('up_kib', 0)} KiB/s"
                    if rate_limits.get("up_kib", 0) > 0
                    else _("Unlimited"),
                )

            console.print(table)

    asyncio.run(_list_options())


@torrent_config.command("reset")
@click.argument("info_hash")
@click.option(
    "--key",
    type=str,
    help=_("Reset specific key only (otherwise resets all options)"),
)
@click.option(
    "--save-checkpoint",
    is_flag=True,
    help=_("Save checkpoint after reset"),
)
@click.pass_context
def torrent_config_reset(
    ctx: click.Context, info_hash: str, key: str | None, save_checkpoint: bool
) -> None:
    """Reset per-torrent configuration options.

    Examples:
        btbt torrent config reset abc123...  # Reset all options
        btbt torrent config reset abc123... --key piece_selection  # Reset specific option

    """
    async def _reset_options() -> None:
        # Check if daemon is running
        daemon_manager = DaemonManager()
        if daemon_manager.is_running():
            # Use daemon IPC
            client = IPCClient()
            try:
                result = await client.execute(
                    "torrent.reset_options",
                    info_hash=info_hash,
                    key=key,
                )
                if result.success:
                    if key:
                        console.print(
                            _("[green]Reset {key} for torrent {hash}[/green]").format(
                                key=key, hash=info_hash[:12] + "..."
                            )
                        )
                    else:
                        console.print(
                            _("[green]Reset all options for torrent {hash}[/green]").format(
                                hash=info_hash[:12] + "..."
                            )
                        )
                    if save_checkpoint:
                        await client.execute(
                            "torrent.save_checkpoint", info_hash=info_hash
                        )
                        console.print(_("[green]Checkpoint saved[/green]"))
                else:
                    console.print(
                        _("[red]Failed to reset options: {error}[/red]").format(
                            error=result.error or "Unknown error"
                        )
                    )
            finally:
                await client.close()
        else:
            # Use local session
            session_manager = AsyncSessionManager(".")
            torrent_session = await _get_torrent_session(info_hash, session_manager)
            if torrent_session is None:
                console.print(
                    _("[red]Torrent not found: {hash}[/red]").format(
                        hash=info_hash[:12] + "..."
                    )
                )
                return

            # Reset options
            if key:
                torrent_session.options.pop(key, None)
                console.print(
                    _("[green]Reset {key} for torrent {hash}[/green]").format(
                        key=key, hash=info_hash[:12] + "..."
                    )
                )
            else:
                torrent_session.options.clear()
                console.print(
                    _("[green]Reset all options for torrent {hash}[/green]").format(
                        hash=info_hash[:12] + "..."
                    )
                )

            # Re-apply options (will use global defaults)
            torrent_session._apply_per_torrent_options()

            if save_checkpoint:
                if hasattr(torrent_session, "checkpoint_controller"):
                    await torrent_session.checkpoint_controller.save_checkpoint_state(
                        torrent_session
                    )
                    console.print(_("[green]Checkpoint saved[/green]"))

    asyncio.run(_reset_options())







