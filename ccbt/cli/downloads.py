from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from rich.console import Console

from ccbt.cli.interactive import InteractiveCLI
from ccbt.cli.progress import ProgressManager
from ccbt.executor.executor import UnifiedCommandExecutor
from ccbt.executor.session_adapter import LocalSessionAdapter
from ccbt.i18n import _
from ccbt.session.session import AsyncSessionManager


async def start_interactive_download(
    session: AsyncSessionManager,
    torrent_data: dict[str, Any],
    console: Console,
    resume: bool = False,
    queue_priority: str | None = None,
    files_selection: tuple[int, ...] | None = None,
    file_priorities: tuple[str, ...] | None = None,
) -> None:
    cleanup_task = getattr(session, "_cleanup_task", None)
    if cleanup_task is None:
        await session.start()

    # Create executor with local adapter
    adapter = LocalSessionAdapter(session)
    executor = UnifiedCommandExecutor(adapter)

    # Add torrent using executor
    if isinstance(torrent_data, dict) and "path" in torrent_data:
        torrent_path = torrent_data["path"]
        result = await executor.execute(
            "torrent.add",
            path_or_magnet=str(torrent_path),
            output_dir=torrent_data.get("download_path"),
            resume=resume,
        )
        if not result.success:
            raise RuntimeError(result.error or _("Failed to add torrent"))
        info_hash_hex = result.data["info_hash"]
    else:
        # Fallback to session method for dict data (not a file path)
        info_hash_hex = await session.add_torrent(torrent_data, resume=resume)

    # Handle file selection using executor
    if files_selection:
        result = await executor.execute(
            "file.select",
            info_hash=info_hash_hex,
            file_indices=list(files_selection),
        )
        if not result.success:
            console.print(
                _("[yellow]Warning: Failed to select files: {error}[/yellow]").format(
                    error=result.error
                )
            )

    # Handle file priorities using executor
    if file_priorities:
        for priority_spec in file_priorities:
            try:
                file_idx_str, priority_str = priority_spec.split("=", 1)
                file_idx = int(file_idx_str.strip())
                result = await executor.execute(
                    "file.priority",
                    info_hash=info_hash_hex,
                    file_index=file_idx,
                    priority=priority_str.strip().lower(),
                )
                if not result.success:
                    console.print(
                        _(
                            "[yellow]Invalid priority spec '{spec}': {error}[/yellow]"
                        ).format(spec=priority_spec, error=result.error)
                    )
            except ValueError as e:
                console.print(
                    _(
                        "[yellow]Invalid priority spec '{spec}': {error}[/yellow]"
                    ).format(spec=priority_spec, error=e)
                )

    interactive_cli = InteractiveCLI(executor, adapter, console, session=session)
    await interactive_cli.download_torrent(torrent_data, resume=resume)

    # Handle queue priority using executor
    if queue_priority and interactive_cli.current_info_hash_hex:
        result = await executor.execute(
            "queue.add",
            info_hash=interactive_cli.current_info_hash_hex,
            priority=queue_priority.lower(),
        )
        if not result.success:
            console.print(
                _(
                    "[yellow]Warning: Failed to set queue priority: {error}[/yellow]"
                ).format(error=result.error)
            )


async def start_basic_download(
    session: AsyncSessionManager,
    torrent_data: dict[str, Any],
    console: Console,
    resume: bool = False,
    queue_priority: str | None = None,
    files_selection: tuple[int, ...] | None = None,
    file_priorities: tuple[str, ...] | None = None,
) -> None:
    cleanup_task = getattr(session, "_cleanup_task", None)
    if cleanup_task is None:
        await session.start()

    # Create executor with local adapter
    adapter = LocalSessionAdapter(session)
    executor = UnifiedCommandExecutor(adapter)

    progress_manager = ProgressManager(console)

    torrent_name = (
        torrent_data.get("name", "Unknown")
        if isinstance(torrent_data, dict)
        else getattr(torrent_data, "name", "Unknown")
    )

    # Use enhanced download progress with speed, ETA, and peer count
    with progress_manager.create_download_progress({}) as progress:
        task = progress.add_task(
            _("Downloading {name}").format(name=torrent_name),
            total=100,
            downloaded="0 B",
            speed="0 B/s",
        )

        # Add torrent using executor
        if isinstance(torrent_data, dict) and "path" in torrent_data:
            torrent_path = torrent_data["path"]
            result = await executor.execute(
                "torrent.add",
                path_or_magnet=str(torrent_path),
                output_dir=torrent_data.get("download_path"),
                resume=resume,
            )
            if not result.success:
                raise RuntimeError(result.error or _("Failed to add torrent"))
            info_hash_hex = result.data["info_hash"]
        else:
            # Fallback to session method for dict data (not a file path)
            info_hash_hex = await session.add_torrent(torrent_data, resume=resume)

        # Handle queue priority using executor
        if queue_priority:
            result = await executor.execute(
                "queue.add",
                info_hash=info_hash_hex,
                priority=queue_priority.lower(),
            )
            if not result.success:
                console.print(
                    _(
                        "[yellow]Warning: Failed to set queue priority: {error}[/yellow]"
                    ).format(error=result.error)
                )

        # Handle file selection using executor
        if files_selection:
            result = await executor.execute(
                "file.select",
                info_hash=info_hash_hex,
                file_indices=list(files_selection),
            )
            if result.success:
                console.print(
                    _("[green]Selected {count} file(s) for download[/green]").format(
                        count=len(files_selection)
                    )
                )
            else:
                console.print(
                    _(
                        "[yellow]Warning: Failed to select files: {error}[/yellow]"
                    ).format(error=result.error)
                )

        # Handle file priorities using executor
        if file_priorities:
            for priority_spec in file_priorities:
                try:
                    file_idx_str, priority_str = priority_spec.split("=", 1)
                    file_idx = int(file_idx_str.strip())
                    result = await executor.execute(
                        "file.priority",
                        info_hash=info_hash_hex,
                        file_index=file_idx,
                        priority=priority_str.strip().lower(),
                    )
                    if not result.success:
                        console.print(
                            _(
                                "[yellow]Invalid priority spec '{spec}': {error}[/yellow]"
                            ).format(spec=priority_spec, error=result.error)
                        )
                except ValueError as e:
                    console.print(
                        _(
                            "[yellow]Invalid priority spec '{spec}': {error}[/yellow]"
                        ).format(spec=priority_spec, error=e)
                    )

        # Monitor progress using executor
        while True:
            result = await executor.execute("torrent.status", info_hash=info_hash_hex)
            if not result.success or not result.data.get("status"):
                break

            torrent_status = result.data["status"]
            progress_val = (
                getattr(torrent_status, "progress", 0.0)
                if hasattr(torrent_status, "progress")
                else torrent_status.get("progress", 0.0)
                if isinstance(torrent_status, dict)
                else 0.0
            )
            status_str = (
                getattr(torrent_status, "status", "unknown")
                if hasattr(torrent_status, "status")
                else torrent_status.get("status", "unknown")
                if isinstance(torrent_status, dict)
                else "unknown"
            )

            # Extract additional metrics for enhanced progress display
            download_speed = (
                getattr(torrent_status, "download_speed", 0.0)
                if hasattr(torrent_status, "download_speed")
                else torrent_status.get("download_speed", 0.0)
                if isinstance(torrent_status, dict)
                else 0.0
            )
            downloaded_bytes = (
                getattr(torrent_status, "downloaded", 0)
                if hasattr(torrent_status, "downloaded")
                else torrent_status.get("downloaded", 0)
                if isinstance(torrent_status, dict)
                else 0
            )

            # Format speed and downloaded bytes
            def format_bytes(bytes_val: float) -> str:
                """Format bytes to human-readable format."""
                for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
                    if bytes_val < 1024.0:
                        return f"{bytes_val:.1f} {unit}"
                    bytes_val /= 1024.0
                return f"{bytes_val:.1f} PiB"

            speed_str = format_bytes(download_speed) + "/s"
            downloaded_str = format_bytes(downloaded_bytes)

            # Update progress with all metrics
            progress.update(
                task,
                completed=progress_val * 100,
                downloaded=downloaded_str,
                speed=speed_str,
            )

            if status_str == "seeding":
                console.print(
                    _("[green]Download completed: {name}[/green]").format(
                        name=torrent_name
                    )
                )
                break

            await asyncio.sleep(1)


async def start_basic_magnet_download(
    session: AsyncSessionManager,
    magnet_link: str,
    console: Console,
    resume: bool = False,
) -> None:
    cleanup_task = getattr(session, "_cleanup_task", None)
    if cleanup_task is None:
        console.print(_("[cyan]Initializing session components...[/cyan]"))
        await session.start()

    # Wait for session to be ready (best effort)
    # Note: is_ready method may not exist on all session implementations

    progress_manager = ProgressManager(console)

    with progress_manager.create_progress() as progress:
        from ccbt.core.magnet import parse_magnet

        try:
            magnet_info = parse_magnet(magnet_link)
            torrent_name = magnet_info.display_name or "Unknown"
        except Exception:
            torrent_name = "Unknown"

        task = progress.add_task(
            _("Downloading {name}").format(name=torrent_name), total=100
        )

        # Create executor with local adapter
        adapter = LocalSessionAdapter(session)
        executor = UnifiedCommandExecutor(adapter)

        console.print(_("[cyan]Adding magnet link and fetching metadata...[/cyan]"))
        try:
            result = await executor.execute(
                "torrent.add",
                path_or_magnet=magnet_link,
                resume=resume,
            )
            if not result.success:
                raise RuntimeError(result.error or _("Failed to add magnet link"))
            info_hash_hex = result.data["info_hash"]
            console.print(
                _("[green]Magnet added successfully: {hash}...[/green]").format(
                    hash=info_hash_hex[:16]
                )
            )
        except Exception as e:
            console.print(
                _("[red]Failed to add magnet link: {error}[/red]").format(error=e)
            )
            raise

        last_status_message = ""
        metadata_fetched = False
        peers_discovered = False
        download_start_time = None
        no_peer_warning_shown = False

        try:
            torrent_registered = False
            for _attempt in range(30):
                result = await executor.execute(
                    "torrent.status", info_hash=info_hash_hex
                )
                if result.success and result.data.get("status"):
                    torrent_registered = True
                    break
                await asyncio.sleep(1)

            if not torrent_registered:
                raise RuntimeError(_("Failed to register torrent in session"))

            while True:
                result = await executor.execute(
                    "torrent.status", info_hash=info_hash_hex
                )
                if not result.success or not result.data.get("status"):
                    await asyncio.sleep(2)
                    result = await executor.execute(
                        "torrent.status", info_hash=info_hash_hex
                    )
                    if not result.success or not result.data.get("status"):
                        console.print(_("[yellow]Torrent session ended[/yellow]"))
                        break
                    torrent_status = result.data["status"]
                else:
                    torrent_status = result.data["status"]

                # Extract status fields
                if hasattr(torrent_status, "status"):
                    current_status = torrent_status.status
                    current_progress = getattr(torrent_status, "progress", 0.0)
                    connected_peers = getattr(torrent_status, "num_peers", 0)
                    download_rate = getattr(torrent_status, "download_rate", 0.0)
                elif isinstance(torrent_status, dict):
                    current_status = torrent_status.get("status", "unknown")
                    current_progress = torrent_status.get("progress", 0.0)
                    connected_peers = torrent_status.get(
                        "connected_peers", torrent_status.get("num_peers", 0)
                    )
                    download_rate = torrent_status.get("download_rate", 0.0)
                else:
                    current_status = "unknown"
                    current_progress = 0.0
                    connected_peers = 0
                    download_rate = 0.0

                progress.update(task, completed=current_progress * 100)

                if current_status == "metadata_fetching":
                    status_msg = _("[yellow]Fetching metadata from peers...[/yellow]")
                    if status_msg != last_status_message:
                        console.print(status_msg)
                        last_status_message = status_msg
                elif current_status in ("downloading", "seeding"):
                    if not metadata_fetched and current_progress > 0:
                        metadata_fetched = True
                        console.print(
                            _("[green]Metadata fetched successfully![/green]")
                        )

                    if connected_peers > 0 and not peers_discovered:
                        peers_discovered = True
                        console.print(
                            _("[green]Connected to {count} peer(s)[/green]").format(
                                count=connected_peers
                            )
                        )

                # CRITICAL FIX: Add user-facing warning if no peers connect after reasonable time
                if current_status == "downloading" and connected_peers == 0:
                    import time

                    if download_start_time is None:
                        download_start_time = time.time()

                    elapsed = time.time() - download_start_time
                    if elapsed > 30.0 and not no_peer_warning_shown:
                        no_peer_warning_shown = True
                        console.print(
                            _(
                                "\n[yellow]Warning: No peers connected after 30 seconds[/yellow]"
                            )
                        )
                        console.print(_("[cyan]Troubleshooting:[/cyan]"))
                        console.print(
                            _(
                                "  • Run 'btbt diagnose-connections' to check connection status"
                            )
                        )
                        console.print(_("  • Verify NAT/firewall settings"))
                        console.print(_("  • Ensure DHT is enabled: --enable-dht"))
                        console.print(_("  • Check if torrent has active seeders"))

                    if download_rate > 0:
                        rate_mb = download_rate / (1024 * 1024)
                        status_msg = _(
                            "[cyan]Downloading: {progress:.1f}% "
                            "({rate:.2f} MB/s, {peers} peers)[/cyan]"
                        ).format(
                            progress=current_progress * 100,
                            rate=rate_mb,
                            peers=connected_peers,
                        )
                    else:
                        status_msg = _(
                            "[cyan]Downloading: {progress:.1f}% ({peers} peers)[/cyan]"
                        ).format(progress=current_progress * 100, peers=connected_peers)

                    if status_msg != last_status_message:
                        console.print(status_msg)
                        last_status_message = status_msg

                if current_status == "seeding":
                    console.print(
                        _("[green]Download completed: {name}[/green]").format(
                            name=torrent_name
                        )
                    )
                    break

                await asyncio.sleep(1)
        except KeyboardInterrupt:
            console.print(_("\n[yellow]Download interrupted by user[/yellow]"))
            # CRITICAL: Save checkpoints before stopping
            try:
                if hasattr(session, "config") and session.config.disk.checkpoint_enabled:
                    # Save checkpoint for the torrent if it exists
                    async with session.lock:
                        for info_hash, torrent_session in list(session.torrents.items()):
                            try:
                                if (
                                    hasattr(torrent_session, "checkpoint_controller")
                                    and torrent_session.checkpoint_controller
                                ):
                                    await torrent_session.checkpoint_controller.save_checkpoint_state(
                                        torrent_session
                                    )
                                    console.print(
                                        _("[green]Checkpoint saved for torrent[/green]")
                                    )
                            except Exception as e:
                                console.print(
                                    _(
                                        "[yellow]Warning: Failed to save checkpoint: {error}[/yellow]"
                                    ).format(error=e)
                                )
            except Exception as e:
                console.print(
                    _(
                        "[yellow]Warning: Error saving checkpoint: {error}[/yellow]"
                    ).format(error=e)
                )
            
            # CRITICAL FIX: Ensure session is properly stopped on KeyboardInterrupt
            # This prevents "Unclosed client session" warnings
            try:
                await session.stop()
            except Exception as e:
                console.print(
                    _(
                        "[yellow]Warning: Error stopping session: {error}[/yellow]"
                    ).format(error=e)
                )
            raise
        finally:
            # CRITICAL FIX: Always try to stop session in finally block
            # This ensures cleanup even if an exception occurs
            try:
                result = await executor.execute(
                    "torrent.status", info_hash=info_hash_hex
                )
                if result.success and result.data.get("status"):
                    torrent_status = result.data["status"]
                    status_str = (
                        getattr(torrent_status, "status", "unknown")
                        if hasattr(torrent_status, "status")
                        else torrent_status.get("status", "unknown")
                        if isinstance(torrent_status, dict)
                        else "unknown"
                    )
                    if status_str == "seeding":
                        console.print(
                            _("[green]Download completed, stopping session...[/green]")
                        )
                        await session.stop()
                    else:
                        # Don't stop session if download is still in progress
                        # User may want to resume later
                        pass
                else:
                    # Torrent not found or error - don't stop session
                    pass
            except KeyboardInterrupt:
                # If KeyboardInterrupt occurs in finally, just stop session
                with contextlib.suppress(Exception):
                    await session.stop()
                raise
            except Exception:
                # Best-effort cleanup
                with contextlib.suppress(Exception):
                    await session.stop()


async def start_interactive_magnet_download(
    session: AsyncSessionManager,
    magnet_link: str,
    console: Console,
    resume: bool = False,
) -> None:
    cleanup_task = getattr(session, "_cleanup_task", None)
    if cleanup_task is None:
        console.print(_("[cyan]Initializing session components...[/cyan]"))
        await session.start()

    # Wait for session to be ready (best effort)
    # Note: is_ready method may not exist on all session implementations

    # Create executor with local adapter
    adapter = LocalSessionAdapter(session)
    executor = UnifiedCommandExecutor(adapter)

    result = await executor.execute(
        "torrent.add",
        path_or_magnet=magnet_link,
        resume=resume,
    )
    if not result.success:
        raise RuntimeError(result.error or "Failed to add magnet link")

    from ccbt.interface.terminal_dashboard import TerminalDashboard

    app = TerminalDashboard(session)
    try:
        app.run()  # type: ignore[attr-defined]
    except KeyboardInterrupt:
        console.print(_("[yellow]Download interrupted by user[/yellow]"))

async def start_interactive_magnet_download(
    session: AsyncSessionManager,
    magnet_link: str,
    console: Console,
    resume: bool = False,
) -> None:
    cleanup_task = getattr(session, "_cleanup_task", None)
    if cleanup_task is None:
        console.print(_("[cyan]Initializing session components...[/cyan]"))
        await session.start()

    # Wait for session to be ready (best effort)
    # Note: is_ready method may not exist on all session implementations

    # Create executor with local adapter
    adapter = LocalSessionAdapter(session)
    executor = UnifiedCommandExecutor(adapter)

    result = await executor.execute(
        "torrent.add",
        path_or_magnet=magnet_link,
        resume=resume,
    )
    if not result.success:
        raise RuntimeError(result.error or "Failed to add magnet link")

    from ccbt.interface.terminal_dashboard import TerminalDashboard

    app = TerminalDashboard(session)
    try:
        app.run()  # type: ignore[attr-defined]
    except KeyboardInterrupt:
        console.print(_("[yellow]Download interrupted by user[/yellow]"))
