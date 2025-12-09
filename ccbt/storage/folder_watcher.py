"""Folder watcher for real-time change detection in XET-enabled folders.

This module provides file system monitoring using watchdog library with
periodic polling fallback for detecting changes in XET folders.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Callable

from ccbt.utils.events import Event, EventType, emit_event

logger = logging.getLogger(__name__)

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog library not available, using polling only")


class FolderChangeHandler(FileSystemEventHandler):
    """Handler for file system change events."""

    def __init__(
        self,
        callback: Callable[[str, str], None],
        folder_path: Path,
    ) -> None:
        """Initialize change handler.

        Args:
            callback: Async callback function(event_type, file_path)
            folder_path: Path to watched folder

        """
        super().__init__()
        self.callback = callback
        self.folder_path = folder_path
        self.logger = logging.getLogger(__name__)

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle any file system event.

        Args:
            event: File system event

        """
        try:
            # Ignore directory events (we care about files)
            if event.is_directory:
                return

            # Get relative path from watched folder
            try:
                relative_path = Path(event.src_path).relative_to(self.folder_path)
            except ValueError:
                # Path not relative to folder, skip
                return

            event_type = event.event_type
            file_path = str(relative_path)

            # Call callback
            self.callback(event_type, file_path)

        except Exception as e:
            self.logger.exception("Error handling file system event")


class FolderWatcher:
    """Monitor folder for changes using watchdog and periodic polling."""

    def __init__(
        self,
        folder_path: str | Path,
        check_interval: float = 5.0,
        use_watchdog: bool = True,
    ) -> None:
        """Initialize folder watcher.

        Args:
            folder_path: Path to folder to watch
            check_interval: Interval for periodic polling in seconds (default: 5.0)
            use_watchdog: Whether to use watchdog library if available

        """
        self.folder_path = Path(folder_path).resolve()
        self.check_interval = check_interval
        self.use_watchdog = use_watchdog and WATCHDOG_AVAILABLE

        self.observer: Observer | None = None
        self.polling_task: asyncio.Task | None = None
        self.is_watching = False
        self.last_check_time = time.time()
        self.last_file_states: dict[str, float] = {}  # file_path -> mtime

        self.change_callbacks: list[Callable[[str, str], None]] = []
        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start watching folder for changes."""
        if self.is_watching:
            self.logger.warning("Folder watcher already started")
            return

        self.is_watching = True
        self.last_check_time = time.time()

        # Start watchdog observer if available
        if self.use_watchdog:
            try:
                self._start_watchdog()
            except Exception as e:
                self.logger.warning(
                    "Failed to start watchdog observer, falling back to polling: %s", e
                )
                self.use_watchdog = False

        # Always start periodic polling as fallback
        self.polling_task = asyncio.create_task(self._polling_loop())

        self.logger.info(
            "Started folder watcher for %s (watchdog=%s, polling_interval=%.1fs)",
            self.folder_path,
            self.use_watchdog,
            self.check_interval,
        )

    async def stop(self) -> None:
        """Stop watching folder."""
        if not self.is_watching:
            return

        self.is_watching = False

        # Stop watchdog observer
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=5.0)
            except Exception as e:
                self.logger.warning("Error stopping watchdog observer: %s", e)
            finally:
                self.observer = None

        # Stop polling task
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
            finally:
                self.polling_task = None

        self.logger.info("Stopped folder watcher for %s", self.folder_path)

    def add_change_callback(
        self, callback: Callable[[str, str], None]
    ) -> None:
        """Add callback for file change events.

        Args:
            callback: Async callback function(event_type, file_path)

        """
        self.change_callbacks.append(callback)

    def remove_change_callback(
        self, callback: Callable[[str, str], None]
    ) -> None:
        """Remove change callback.

        Args:
            callback: Callback to remove

        """
        if callback in self.change_callbacks:
            self.change_callbacks.remove(callback)

    def _start_watchdog(self) -> None:
        """Start watchdog file system observer."""
        if not WATCHDOG_AVAILABLE:
            return

        self.observer = Observer()

        # Create event handler
        handler = FolderChangeHandler(self._handle_change, self.folder_path)

        # Schedule observer
        self.observer.schedule(handler, str(self.folder_path), recursive=True)
        self.observer.start()

        self.logger.debug("Started watchdog observer for %s", self.folder_path)

    def _handle_change(self, event_type: str, file_path: str) -> None:
        """Handle file change event.

        Args:
            event_type: Type of event (created, modified, deleted, moved)
            file_path: Relative path to changed file

        """
        try:
            # Emit event
            asyncio.create_task(
                emit_event(
                    Event(
                        event_type=EventType.FOLDER_CHANGED.value,
                        data={
                            "folder_path": str(self.folder_path),
                            "file_path": file_path,
                            "event_type": event_type,
                            "timestamp": time.time(),
                        },
                    ),
                ),
            )

            # Call all callbacks
            for callback in self.change_callbacks:
                try:
                    callback(event_type, file_path)
                except Exception as e:
                    self.logger.exception(
                        "Error in change callback for %s", file_path
                    )

        except Exception as e:
            self.logger.exception("Error handling file change")

    async def _polling_loop(self) -> None:
        """Periodic polling loop for change detection."""
        while self.is_watching:
            try:
                await asyncio.sleep(self.check_interval)
                if not self.is_watching:
                    break

                # Check for changes
                await self._check_changes()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception("Error in polling loop")
                await asyncio.sleep(self.check_interval)

    async def _check_changes(self) -> None:
        """Check for file changes using polling."""
        if not self.folder_path.exists():
            return

        current_time = time.time()
        current_file_states: dict[str, float] = {}

        # Scan folder for files
        try:
            for file_path in self.folder_path.rglob("*"):
                if file_path.is_file():
                    try:
                        mtime = file_path.stat().st_mtime
                        relative_path = str(file_path.relative_to(self.folder_path))
                        current_file_states[relative_path] = mtime

                        # Check if file is new or modified
                        if relative_path not in self.last_file_states:
                            # New file
                            self._handle_change("created", relative_path)
                        elif (
                            abs(mtime - self.last_file_states[relative_path]) > 1.0
                        ):  # 1 second threshold
                            # Modified file
                            self._handle_change("modified", relative_path)

                    except (OSError, PermissionError) as e:
                        self.logger.debug("Error accessing file %s: %s", file_path, e)
                        continue

            # Check for deleted files
            for file_path in self.last_file_states:
                if file_path not in current_file_states:
                    self._handle_change("deleted", file_path)

            # Update file states
            self.last_file_states = current_file_states
            self.last_check_time = current_time

        except Exception as e:
            self.logger.exception("Error checking folder changes")

    def get_last_check_time(self) -> float:
        """Get timestamp of last change check.

        Returns:
            Timestamp of last check

        """
        return self.last_check_time

    def get_file_count(self) -> int:
        """Get current file count in watched folder.

        Returns:
            Number of files in folder

        """
        try:
            if not self.folder_path.exists():
                return 0
            return sum(1 for _ in self.folder_path.rglob("*") if _.is_file())
        except Exception:
            return 0

