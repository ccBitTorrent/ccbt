from __future__ import annotations

import asyncio
import time
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from ccbt.config.config import ConfigManager
from ccbt.i18n import _
from ccbt.utils.logging_config import get_logger

logger = get_logger(__name__)


def list_checkpoints(config_manager: ConfigManager, console: Console) -> None:
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    checkpoints = asyncio.run(checkpoint_manager.list_checkpoints())
    if not checkpoints:
        console.print(_("[yellow]No checkpoints found[/yellow]"))
        return
    table = Table(title="Available Checkpoints")
    table.add_column("Info Hash", style="cyan")
    table.add_column("Format", style="green")
    table.add_column("Size", style="blue")
    table.add_column("Created", style="magenta")
    table.add_column("Updated", style="yellow")
    for cp in checkpoints:
        table.add_row(
            cp.info_hash.hex()[:16] + "...",
            cp.checkpoint_format.value,
            f"{cp.size:,} bytes",
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(cp.created_at)),
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(cp.updated_at)),
        )
    console.print(table)


def clean_checkpoints(
    config_manager: ConfigManager, days: int, dry_run: bool, console: Console
) -> None:
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    if dry_run:
        checkpoints = asyncio.run(checkpoint_manager.list_checkpoints())
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        old_checkpoints = [cp for cp in checkpoints if cp.updated_at < cutoff_time]
        if not old_checkpoints:
            console.print(_("[green]No checkpoints older than {days} days found[/green]").format(days=days))
            return
        console.print(
            _("[yellow]Would delete {count} checkpoints older than {days} days:[/yellow]").format(count=len(old_checkpoints), days=days)
        )
        for cp in old_checkpoints:
            format_value = getattr(cp, "format", None)
            format_str = format_value.value if format_value and hasattr(format_value, "value") else "unknown"
            console.print(_("  - {hash}... ({format})").format(hash=cp.info_hash.hex()[:16], format=format_str))
        return
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(_("Cleaning up old checkpoints..."), total=None)
        deleted_count = asyncio.run(checkpoint_manager.cleanup_old_checkpoints(days))
        progress.update(task, description=_("Cleanup complete"))
    console.print(_("[green]Cleaned up {count} old checkpoints[/green]").format(count=deleted_count))


def delete_checkpoint(
    config_manager: ConfigManager, info_hash: str, console: Console
) -> None:
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    try:
        ih_bytes = bytes.fromhex(info_hash)
    except ValueError:
        logger.exception(_("Invalid info hash format: %s"), info_hash)
        console.print(_("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash))
        raise
    deleted = asyncio.run(checkpoint_manager.delete_checkpoint(ih_bytes))
    if deleted:
        console.print(_("[green]Deleted checkpoint for {hash}[/green]").format(hash=info_hash))
    else:
        console.print(_("[yellow]No checkpoint found for {hash}[/yellow]").format(hash=info_hash))


def verify_checkpoint(
    config_manager: ConfigManager, info_hash: str, console: Console
) -> None:
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    try:
        ih_bytes = bytes.fromhex(info_hash)
    except ValueError:
        logger.exception(_("Invalid info hash format: %s"), info_hash)
        console.print(_("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash))
        raise
    valid = asyncio.run(checkpoint_manager.verify_checkpoint(ih_bytes))
    if valid:
        console.print(_("[green]Checkpoint for {hash} is valid[/green]").format(hash=info_hash))
    else:
        console.print(
            _("[yellow]Checkpoint for {hash} is missing or invalid[/yellow]").format(hash=info_hash)
        )


def export_checkpoint(
    config_manager: ConfigManager,
    info_hash: str,
    format_: str,
    output_path: str,
    console: Console,
) -> None:
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    try:
        ih_bytes = bytes.fromhex(info_hash)
    except ValueError:
        logger.exception(_("Invalid info hash format: %s"), info_hash)
        console.print(_("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash))
        raise
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(_("Exporting checkpoint..."), total=None)
        data = asyncio.run(checkpoint_manager.export_checkpoint(ih_bytes, fmt=format_))
        progress.update(task, description=_("Writing export file..."))
        Path(output_path).write_bytes(data)
        progress.update(task, description=_("Export complete"))
    console.print(_("[green]Exported checkpoint to {path}[/green]").format(path=output_path))


def backup_checkpoint(
    config_manager: ConfigManager,
    info_hash: str,
    destination: str,
    compress: bool,
    encrypt: bool,
    console: Console,
) -> None:
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    try:
        ih_bytes = bytes.fromhex(info_hash)
    except ValueError:
        logger.exception(_("Invalid info hash format: %s"), info_hash)
        console.print(_("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash))
        raise
    dest_path = Path(destination)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(_("Creating backup..."), total=None)
        if compress:
            progress.update(task, description=_("Compressing backup..."))
        if encrypt:
            progress.update(task, description=_("Encrypting backup..."))
        final_path = asyncio.run(
            checkpoint_manager.backup_checkpoint(
                ih_bytes, dest_path, compress=compress, encrypt=encrypt
            ),
        )
        progress.update(task, description=_("Backup complete"))
    console.print(_("[green]Backup created: {path}[/green]").format(path=final_path))


def restore_checkpoint(
    config_manager: ConfigManager,
    backup_file: str,
    info_hash: str | None,
    console: Console,
) -> None:
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    ih_bytes = None
    if info_hash:
        try:
            ih_bytes = bytes.fromhex(info_hash)
        except ValueError:
            console.print(_("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash))
            raise
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(_("Restoring checkpoint..."), total=None)
        cp = asyncio.run(
            checkpoint_manager.restore_checkpoint(Path(backup_file), info_hash=ih_bytes)
        )
        progress.update(task, description=_("Restore complete"))
    console.print(
        _("[green]Restored checkpoint for: {name}[/green]\nInfo hash: {hash}").format(name=cp.torrent_name, hash=cp.info_hash.hex())
    )


def migrate_checkpoint(
    config_manager: ConfigManager,
    info_hash: str,
    from_format: str,
    to_format: str,
    console: Console,
) -> None:
    from ccbt.models import CheckpointFormat
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    try:
        ih_bytes = bytes.fromhex(info_hash)
    except ValueError:
        logger.exception(_("Invalid info hash format: %s"), info_hash)
        console.print(_("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash))
        raise
    src = CheckpointFormat[from_format.upper()]
    dst = CheckpointFormat[to_format.upper()]
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            _("Migrating checkpoint format from {from_fmt} to {to_fmt}...").format(
                from_fmt=from_format, to_fmt=to_format
            ),
            total=None,
        )
        new_path = asyncio.run(
            checkpoint_manager.convert_checkpoint_format(ih_bytes, src, dst)
        )
        progress.update(task, description=_("Migration complete"))
    console.print(_("[green]Migrated checkpoint to {path}[/green]").format(path=new_path))


    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    ih_bytes = None
    if info_hash:
        try:
            ih_bytes = bytes.fromhex(info_hash)
        except ValueError:
            console.print(_("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash))
            raise
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(_("Restoring checkpoint..."), total=None)
        cp = asyncio.run(
            checkpoint_manager.restore_checkpoint(Path(backup_file), info_hash=ih_bytes)
        )
        progress.update(task, description=_("Restore complete"))
    console.print(
        _("[green]Restored checkpoint for: {name}[/green]\nInfo hash: {hash}").format(name=cp.torrent_name, hash=cp.info_hash.hex())
    )


def migrate_checkpoint(
    config_manager: ConfigManager,
    info_hash: str,
    from_format: str,
    to_format: str,
    console: Console,
) -> None:
    from ccbt.models import CheckpointFormat
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    try:
        ih_bytes = bytes.fromhex(info_hash)
    except ValueError:
        logger.exception(_("Invalid info hash format: %s"), info_hash)
        console.print(_("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash))
        raise
    src = CheckpointFormat[from_format.upper()]
    dst = CheckpointFormat[to_format.upper()]
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            _("Migrating checkpoint format from {from_fmt} to {to_fmt}...").format(
                from_fmt=from_format, to_fmt=to_format
            ),
            total=None,
        )
        new_path = asyncio.run(
            checkpoint_manager.convert_checkpoint_format(ih_bytes, src, dst)
        )
        progress.update(task, description=_("Migration complete"))
    console.print(_("[green]Migrated checkpoint to {path}[/green]").format(path=new_path))
