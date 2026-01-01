"""CLI commands for per-torrent configuration management.

from __future__ import annotations

Provides commands to set, get, list, and reset per-torrent configuration options.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

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
        return session_manager.torrents.get(info_hash)


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


async def _set_torrent_option(
    info_hash: str, key: str, value: str, save_checkpoint: bool
) -> None:
    """Set a per-torrent configuration option (async implementation).

    Args:
        info_hash: Torrent info hash as hex string
        key: Configuration option key
        value: Configuration option value (will be parsed)
        save_checkpoint: Whether to save checkpoint after setting option

    """
    # Check if daemon is running
    daemon_manager = DaemonManager()
    if daemon_manager.is_running():
        # Use daemon executor
        from ccbt.executor.manager import ExecutorManager

        client = IPCClient()
        try:
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(ipc_client=client)
            # Check if torrent exists via adapter
            adapter = executor.adapter
            torrent_status = await adapter.get_torrent_status(info_hash)
            if not torrent_status:
                console.print(
                    _("[red]Torrent not found: {hash}[/red]").format(
                        hash=info_hash[:12] + "..."
                    )
                )
                return

            parsed_value = _parse_value(value)
            # Use executor.execute for consistency with executor pattern
            result = await executor.execute(
                "torrent.set_option",
                info_hash=info_hash,
                key=key,
                value=parsed_value,
            )
            success = (
                result.success
                if hasattr(result, "success")
                else result.get("success", False)
                if isinstance(result, dict)
                else False
            )
            if success:
                console.print(
                    _("[green]Set {key} = {value} for torrent {hash}[/green]").format(
                        key=key, value=parsed_value, hash=info_hash[:12] + "..."
                    )
                )
                if save_checkpoint:
                    # Use executor.execute for consistency
                    checkpoint_result = await executor.execute(
                        "torrent.save_checkpoint",
                        info_hash=info_hash,
                    )
                    checkpoint_success = (
                        checkpoint_result.success
                        if hasattr(checkpoint_result, "success")
                        else checkpoint_result.get("success", False)
                        if isinstance(checkpoint_result, dict)
                        else False
                    )
                    if checkpoint_success:
                        console.print(_("[green]Checkpoint saved[/green]"))
                    else:
                        console.print(
                            _("[yellow]Warning: Checkpoint save failed[/yellow]")
                        )
            else:
                console.print(_("[red]Failed to set option[/red]"))
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
        torrent_session.apply_per_torrent_options()

        console.print(
            _("[green]Set {key} = {value} for torrent {hash}[/green]").format(
                key=key, value=parsed_value, hash=info_hash[:12] + "..."
            )
        )

        if save_checkpoint and hasattr(torrent_session, "checkpoint_controller"):
            await torrent_session.checkpoint_controller.save_checkpoint_state(
                torrent_session
            )
            console.print(_("[green]Checkpoint saved[/green]"))


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
    _ctx: click.Context, info_hash: str, key: str, value: str, save_checkpoint: bool
) -> None:
    """Set a per-torrent configuration option.

    Examples:
        btbt torrent config set abc123... piece_selection sequential
        btbt torrent config set abc123... streaming_mode true
        btbt torrent config set abc123... max_peers_per_torrent 50

    """

    async def _set_option() -> None:
        await _set_torrent_option(info_hash, key, value, save_checkpoint)

    asyncio.run(_set_option())


async def _get_torrent_option(info_hash: str, key: str) -> None:
    """Get a per-torrent configuration option value (async implementation).

    Args:
        info_hash: Torrent info hash as hex string
        key: Configuration option key

    """
    # Check if daemon is running
    daemon_manager = DaemonManager()
    if daemon_manager.is_running():
        # Use daemon executor
        from ccbt.executor.manager import ExecutorManager

        client = IPCClient()
        try:
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(ipc_client=client)
            # Use executor.execute for consistency
            result = await executor.execute(
                "torrent.get_option",
                info_hash=info_hash,
                key=key,
            )
            value = None
            if hasattr(result, "data") and isinstance(result.data, dict):
                value = result.data.get("value")
            if value is not None:
                console.print(_("{key} = {value}").format(key=key, value=value))
            else:
                console.print(_("[yellow]{key} is not set[/yellow]").format(key=key))
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


@torrent_config.command("get")
@click.argument("info_hash")
@click.argument("key")
@click.pass_context
def torrent_config_get(_ctx: click.Context, info_hash: str, key: str) -> None:
    """Get a per-torrent configuration option value.

    Examples:
        btbt torrent config get abc123... piece_selection
        btbt torrent config get abc123... streaming_mode

    """

    async def _get_option() -> None:
        await _get_torrent_option(info_hash, key)

    asyncio.run(_get_option())


async def _list_torrent_options(info_hash: str) -> None:
    """List all per-torrent configuration options and rate limits (async implementation).

    Args:
        info_hash: Torrent info hash as hex string

    """
    # Check if daemon is running
    daemon_manager = DaemonManager()
    if daemon_manager.is_running():
        # Use daemon executor
        from ccbt.executor.manager import ExecutorManager

        client = IPCClient()
        try:
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(ipc_client=client)
            # Use executor.execute for consistency
            result = await executor.execute(
                "torrent.get_config",
                info_hash=info_hash,
            )
            data = (
                result.data
                if hasattr(result, "data")
                else result
                if isinstance(result, dict)
                else {}
            )
            options = data.get("options", {}) if isinstance(data, dict) else {}
            rate_limits = data.get("rate_limits", {}) if isinstance(data, dict) else {}

            table = Table(
                title=_("Per-Torrent Config: {hash}...").format(hash=info_hash[:12])
            )
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
        if session_manager:
            info_hash_bytes = bytes.fromhex(info_hash)
            limits = session_manager.get_per_torrent_limits(info_hash_bytes)
            # Handle both sync and async return values
            if asyncio.iscoroutine(limits):
                limits = await limits
            if limits:
                rate_limits = limits

        table = Table(
            title=_("Per-Torrent Config: {hash}...").format(hash=info_hash[:12])
        )
        table.add_column(_("Option"), style="cyan")
        table.add_column(_("Value"), style="green")

        if options:
            for opt_key, opt_value in sorted(options.items()):
                table.add_row(opt_key, str(opt_value))
        else:
            table.add_row(_("(no options set)"), "-")

        if rate_limits:
            # Ensure rate_limits is a dict, not a coroutine
            if asyncio.iscoroutine(rate_limits):
                rate_limits = await rate_limits
            if not isinstance(rate_limits, dict):
                rate_limits = {}
            table.add_row("", "")  # Separator
            # rate_limits is guaranteed to be a dict after the check above
            # Cast to help type checker understand the type
            rate_limits_dict = cast("dict[str, Any]", rate_limits)
            down_kib = rate_limits_dict.get("down_kib", 0)
            up_kib = rate_limits_dict.get("up_kib", 0)
            table.add_row(
                _("Download Limit"),
                f"{down_kib} KiB/s" if down_kib > 0 else _("Unlimited"),
            )
            table.add_row(
                _("Upload Limit"),
                f"{up_kib} KiB/s" if up_kib > 0 else _("Unlimited"),
            )

        console.print(table)


@torrent_config.command("list")
@click.argument("info_hash")
@click.pass_context
def torrent_config_list(_ctx: click.Context, info_hash: str) -> None:
    """List all per-torrent configuration options and rate limits.

    Examples:
        btbt torrent config list abc123...

    """

    async def _list_options() -> None:
        await _list_torrent_options(info_hash)

    asyncio.run(_list_options())


async def _reset_torrent_options(
    info_hash: str, key: str | None, save_checkpoint: bool
) -> None:
    """Reset per-torrent configuration options (async implementation).

    Args:
        info_hash: Torrent info hash as hex string
        key: Optional specific key to reset (None to reset all)
        save_checkpoint: Whether to save checkpoint after reset

    """
    # Check if daemon is running
    daemon_manager = DaemonManager()
    if daemon_manager.is_running():
        # Use daemon executor
        from ccbt.executor.manager import ExecutorManager

        client = IPCClient()
        try:
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(ipc_client=client)
            # Use executor.execute for consistency
            result = await executor.execute(
                "torrent.reset_options",
                info_hash=info_hash,
                key=key,
            )
            success = (
                result.success
                if hasattr(result, "success")
                else result.get("success", False)
                if isinstance(result, dict)
                else False
            )
            if success:
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
                    # Use executor.execute for consistency
                    checkpoint_result = await executor.execute(
                        "torrent.save_checkpoint",
                        info_hash=info_hash,
                    )
                    checkpoint_success = (
                        checkpoint_result.success
                        if hasattr(checkpoint_result, "success")
                        else checkpoint_result.get("success", False)
                        if isinstance(checkpoint_result, dict)
                        else False
                    )
                    if checkpoint_success:
                        console.print(_("[green]Checkpoint saved[/green]"))
                    else:
                        console.print(
                            _("[yellow]Warning: Checkpoint save failed[/yellow]")
                        )
            else:
                console.print(_("[red]Failed to reset options[/red]"))
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
        torrent_session.apply_per_torrent_options()

        if save_checkpoint and hasattr(torrent_session, "checkpoint_controller"):
            await torrent_session.checkpoint_controller.save_checkpoint_state(
                torrent_session
            )
            console.print(_("[green]Checkpoint saved[/green]"))


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
    _ctx: click.Context, info_hash: str, key: str | None, save_checkpoint: bool
) -> None:
    """Reset per-torrent configuration options.

    Examples:
        btbt torrent config reset abc123...  # Reset all options
        btbt torrent config reset abc123... --key piece_selection  # Reset specific option

    """

    async def _reset_options() -> None:
        await _reset_torrent_options(info_hash, key, save_checkpoint)

    asyncio.run(_reset_options())
