from __future__ import annotations

import asyncio
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ccbt.config.config import ConfigManager


def list_checkpoints(config_manager: ConfigManager, console: Console) -> None:
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    checkpoints = asyncio.run(checkpoint_manager.list_checkpoints())
    if not checkpoints:
        console.print("[yellow]No checkpoints found[/yellow]")
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
            console.print(f"[green]No checkpoints older than {days} days found[/green]")
            return
        console.print(
            f"[yellow]Would delete {len(old_checkpoints)} checkpoints older than {days} days:[/yellow]"
        )
        for cp in old_checkpoints:
            console.print(f"  - {cp.info_hash.hex()[:16]}... ({cp.format.value})")
        return
    deleted_count = asyncio.run(checkpoint_manager.cleanup_old_checkpoints(days))
    console.print(f"[green]Cleaned up {deleted_count} old checkpoints[/green]")


def delete_checkpoint(
    config_manager: ConfigManager, info_hash: str, console: Console
) -> None:
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    try:
        ih_bytes = bytes.fromhex(info_hash)
    except ValueError:
        console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
        raise
    deleted = asyncio.run(checkpoint_manager.delete_checkpoint(ih_bytes))
    if deleted:
        console.print(f"[green]Deleted checkpoint for {info_hash}[/green]")
    else:
        console.print(f"[yellow]No checkpoint found for {info_hash}[/yellow]")


def verify_checkpoint(
    config_manager: ConfigManager, info_hash: str, console: Console
) -> None:
    from ccbt.storage.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager(config_manager.config.disk)
    try:
        ih_bytes = bytes.fromhex(info_hash)
    except ValueError:
        console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
        raise
    valid = asyncio.run(checkpoint_manager.verify_checkpoint(ih_bytes))
    if valid:
        console.print(f"[green]Checkpoint for {info_hash} is valid[/green]")
    else:
        console.print(
            f"[yellow]Checkpoint for {info_hash} is missing or invalid[/yellow]"
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
        console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
        raise
    data = asyncio.run(checkpoint_manager.export_checkpoint(ih_bytes, fmt=format_))
    Path(output_path).write_bytes(data)
    console.print(f"[green]Exported checkpoint to {output_path}[/green]")


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
        console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
        raise
    dest_path = Path(destination)
    final_path = asyncio.run(
        checkpoint_manager.backup_checkpoint(
            ih_bytes, dest_path, compress=compress, encrypt=encrypt
        ),
    )
    console.print(f"[green]Backup created: {final_path}[/green]")


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
            console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
            raise
    cp = asyncio.run(
        checkpoint_manager.restore_checkpoint(Path(backup_file), info_hash=ih_bytes)
    )
    console.print(
        f"[green]Restored checkpoint for: {cp.torrent_name}[/green]\nInfo hash: {cp.info_hash.hex()}"
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
        console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
        raise
    src = CheckpointFormat[from_format.upper()]
    dst = CheckpointFormat[to_format.upper()]
    new_path = asyncio.run(
        checkpoint_manager.convert_checkpoint_format(ih_bytes, src, dst)
    )
    console.print(f"[green]Migrated checkpoint to {new_path}[/green]")
