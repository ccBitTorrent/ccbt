"""Resume functionality for the CLI.

This module provides commands for resuming interrupted downloads
and managing checkpoint data.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Optional

from ccbt.cli.interactive import InteractiveCLI

if TYPE_CHECKING:
    from rich.console import Console
from ccbt.cli.progress import ProgressManager
from ccbt.i18n import _


async def resume_download(
    session: Optional[Any],  # Optional[AsyncSessionManager]
    info_hash_bytes: bytes,
    checkpoint: Any,
    interactive: bool,
    console: Console,
) -> None:
    """Resume a download from a checkpoint."""
    # Note: Create session safely if not provided
    if session is None:
        from ccbt.cli.main import _ensure_local_session_safe

        session = await _ensure_local_session_safe()
    try:
        # Start session if not already started
        cleanup_task = getattr(session, "_cleanup_task", None)
        if cleanup_task is None:
            await session.start()
        console.print(_("[green]Resuming download from checkpoint...[/green]"))
        resumed_info_hash = await session.checkpoint_ops.resume_from_checkpoint(  # type: ignore[attr-defined]
            info_hash_bytes,
            checkpoint,
        )
        console.print(
            _("[green]Successfully resumed download: {hash}[/green]").format(
                hash=resumed_info_hash
            )
        )

        if interactive:
            from ccbt.executor.manager import ExecutorManager

            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(session_manager=session)
            adapter = executor.adapter
            interactive_cli = InteractiveCLI(
                executor, adapter, console, session=session
            )
            await interactive_cli.run()
        else:
            progress_manager = ProgressManager(console)
            with progress_manager.create_progress() as progress:
                task = progress.add_task(
                    _("Resuming {name}").format(name=checkpoint.torrent_name),
                    total=100,
                )
                while True:
                    # Get torrent status by accessing the torrent session directly
                    info_hash_bytes = bytes.fromhex(resumed_info_hash)
                    async with session.lock:
                        torrent_session = session.torrents.get(info_hash_bytes)
                        if torrent_session:
                            torrent_status = await torrent_session.get_status()
                        else:
                            torrent_status = None
                    if not torrent_status:
                        console.print(_("[yellow]Torrent session ended[/yellow]"))
                        break
                    progress.update(
                        task,
                        completed=torrent_status.get("progress", 0) * 100,
                    )
                    if torrent_status.get("status") == "seeding":
                        console.print(
                            _("[green]Download completed: {name}[/green]").format(
                                name=checkpoint.torrent_name
                            )
                        )
                        break
                    await asyncio.sleep(1)
    finally:
        try:
            await session.stop()
        except Exception as e:
            console.print(
                _("[yellow]Warning: Error stopping session: {e}[/yellow]").format(e=e)
            )
