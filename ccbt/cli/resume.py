from __future__ import annotations

import asyncio
from typing import Any

from rich.console import Console

from ccbt.cli.interactive import InteractiveCLI
from ccbt.cli.progress import ProgressManager
from ccbt.session.session import AsyncSessionManager


async def resume_download(
    session: AsyncSessionManager | None,
    info_hash_bytes: bytes,
    checkpoint: Any,
    interactive: bool,
    console: Console,
) -> None:
    """Resume a download from a checkpoint."""
    # CRITICAL FIX: Create session safely if not provided
    if session is None:
        from ccbt.cli.main import _ensure_local_session_safe

        session = await _ensure_local_session_safe()
    try:
        # Start session if not already started
        cleanup_task = getattr(session, "_cleanup_task", None)
        if cleanup_task is None:
            await session.start()
        console.print("[green]Resuming download from checkpoint...[/green]")
        resumed_info_hash = await session.resume_from_checkpoint(
            info_hash_bytes,
            checkpoint,
        )
        console.print(
            f"[green]Successfully resumed download: {resumed_info_hash}[/green]"
        )

        if interactive:
            interactive_cli = InteractiveCLI(session, console)
            await interactive_cli.run()
        else:
            progress_manager = ProgressManager(console)
            with progress_manager.create_progress() as progress:
                task = progress.add_task(
                    f"Resuming {checkpoint.torrent_name}",
                    total=100,
                )
                while True:
                    torrent_status = await session.get_torrent_status(resumed_info_hash)
                    if not torrent_status:
                        console.print("[yellow]Torrent session ended[/yellow]")
                        break
                    progress.update(
                        task,
                        completed=torrent_status.get("progress", 0) * 100,
                    )
                    if torrent_status.get("status") == "seeding":
                        console.print(
                            f"[green]Download completed: {checkpoint.torrent_name}[/green]"
                        )
                        break
                    await asyncio.sleep(1)
    finally:
        try:
            await session.stop()
        except Exception as e:
            console.print(f"[yellow]Warning: Error stopping session: {e}[/yellow]")
