from __future__ import annotations

import asyncio
from typing import Any

from rich.console import Console

from ccbt.cli.interactive import InteractiveCLI
from ccbt.cli.progress import ProgressManager
from ccbt.i18n import _
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
        console.print(_("[green]Resuming download from checkpoint...[/green]"))
        resumed_info_hash = await session.resume_from_checkpoint(
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
            interactive_cli = InteractiveCLI(executor, adapter, console, session=session)
            await interactive_cli.run()
        else:
            progress_manager = ProgressManager(console)
            with progress_manager.create_progress() as progress:
                task = progress.add_task(
                    _("Resuming {name}").format(name=checkpoint.torrent_name),
                    total=100,
                )
                while True:
                    torrent_status = await session.get_torrent_status(resumed_info_hash)
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
            console.print(_("[yellow]Warning: Error stopping session: {e}[/yellow]").format(e=e))
