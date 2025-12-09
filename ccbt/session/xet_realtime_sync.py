"""Real-time folder synchronization loop for XET folders.

This module provides a background task for periodic folder updates with
chunk hash comparison, git ref comparison, and automatic peer discovery.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ccbt.storage.xet_folder_manager import XetFolder
from ccbt.utils.events import Event, EventType, emit_event

logger = logging.getLogger(__name__)


class XetRealtimeSync:
    """Real-time folder synchronization background task."""

    def __init__(
        self,
        folder: XetFolder,
        check_interval: float = 5.0,
        session_manager: Any | None = None,  # AsyncSessionManager
    ) -> None:
        """Initialize real-time sync.

        Args:
            folder: XetFolder instance to sync
            check_interval: Interval between checks in seconds
            session_manager: Session manager for peer discovery

        """
        self.folder = folder
        self.check_interval = check_interval
        self.session_manager = session_manager

        self._sync_task: asyncio.Task | None = None
        self._is_running = False
        self._last_chunk_hashes: dict[str, bytes] = {}  # file_path -> chunk_hash
        self._last_git_ref: str | None = None

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start real-time sync loop."""
        if self._is_running:
            self.logger.warning("Real-time sync already running")
            return

        self._is_running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        self.logger.info(
            "Started real-time sync for %s (interval=%.1fs)",
            self.folder.folder_path,
            self.check_interval,
        )

    async def stop(self) -> None:
        """Stop real-time sync loop."""
        if not self._is_running:
            return

        self._is_running = False

        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            finally:
                self._sync_task = None

        self.logger.info("Stopped real-time sync for %s", self.folder.folder_path)

    async def _sync_loop(self) -> None:
        """Main synchronization loop."""
        while self._is_running:
            try:
                await asyncio.sleep(self.check_interval)
                if not self._is_running:
                    break

                # Check for changes
                await self._check_for_updates()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception("Error in sync loop")
                await asyncio.sleep(self.check_interval)

    async def _check_for_updates(self) -> None:
        """Check for folder updates and sync with peers."""
        try:
            # Check git ref changes with timeout
            if self.folder.git_versioning:
                try:
                    current_ref = await asyncio.wait_for(
                        self.folder.git_versioning.get_current_commit(),
                        timeout=5.0,
                    )
                    if current_ref != self._last_git_ref:
                        if self._last_git_ref is not None:
                            self.logger.info(
                                "Git ref changed: %s -> %s",
                                self._last_git_ref[:16] if self._last_git_ref else None,
                                current_ref[:16] if current_ref else None,
                            )

                            # Get changed files with timeout
                            try:
                                changed_files = await asyncio.wait_for(
                                    self.folder.git_versioning.get_changed_files(
                                        since_ref=self._last_git_ref
                                    ),
                                    timeout=10.0,
                                )
                                for file_path in changed_files:
                                    await self._queue_file_update(file_path)
                            except asyncio.TimeoutError:
                                self.logger.warning(
                                    "Timeout getting changed files for git ref %s",
                                    current_ref[:16] if current_ref else None,
                                )
                            except Exception as e:
                                self.logger.warning(
                                    "Error getting changed files: %s", e
                                )

                        self._last_git_ref = current_ref
                        # Update git ref in sync manager
                        if current_ref:
                            self.folder.sync_manager.set_current_git_ref(current_ref)
                            
                            # Auto-commit if enabled
                            if self.folder.git_versioning.auto_commit:
                                try:
                                    new_commit = await asyncio.wait_for(
                                        self.folder.git_versioning.auto_commit_if_changes(),
                                        timeout=10.0,
                                    )
                                    if new_commit:
                                        self._last_git_ref = new_commit
                                        self.folder.sync_manager.set_current_git_ref(new_commit)
                                        self.logger.debug(
                                            "Auto-committed changes, new ref: %s",
                                            new_commit[:16],
                                        )
                                except (asyncio.TimeoutError, Exception) as e:
                                    self.logger.debug("Error during auto-commit: %s", e)
                except asyncio.TimeoutError:
                    self.logger.warning("Timeout checking git ref")
                except Exception as e:
                    self.logger.warning("Error checking git ref: %s", e)

            # Check chunk hashes for changes with timeout
            try:
                await asyncio.wait_for(self._check_chunk_hashes(), timeout=30.0)
            except asyncio.TimeoutError:
                self.logger.warning("Timeout checking chunk hashes")
            except Exception as e:
                self.logger.warning("Error checking chunk hashes: %s", e)

            # Discover peers for updated chunks with timeout
            try:
                await asyncio.wait_for(self._discover_peers(), timeout=10.0)
            except asyncio.TimeoutError:
                self.logger.warning("Timeout discovering peers")
            except Exception as e:
                self.logger.warning("Error discovering peers: %s", e)

            # Process sync queue with timeout
            try:
                await asyncio.wait_for(self.folder.sync(), timeout=60.0)
            except asyncio.TimeoutError:
                self.logger.warning("Timeout syncing folder")
            except Exception as e:
                self.logger.warning("Error syncing folder: %s", e)

            # Emit sync event (non-critical, don't fail on error)
            try:
                await asyncio.wait_for(
                    emit_event(
                        Event(
                            event_type=EventType.FOLDER_SYNC_CHECK.value,
                            data={
                                "folder_path": str(self.folder.folder_path),
                                "timestamp": time.time(),
                            },
                        ),
                    ),
                    timeout=2.0,
                )
            except Exception as e:
                self.logger.debug("Error emitting sync event: %s", e)

        except Exception as e:
            self.logger.exception(
                "Error checking for updates in folder %s", self.folder.folder_path
            )

    async def _check_chunk_hashes(self) -> None:
        """Check chunk hashes for changes."""
        try:
            folder_path = self.folder.folder_path

            # Scan folder for files
            current_hashes: dict[str, bytes] = {}
            for file_path in folder_path.rglob("*"):
                if file_path.is_file():
                    try:
                        relative_path = str(file_path.relative_to(folder_path))
                        # Calculate chunk hash (simplified - in practice use XET chunking)
                        import hashlib

                        with open(file_path, "rb") as f:
                            file_data = f.read()
                            chunk_hash = hashlib.sha256(file_data).digest()

                        current_hashes[relative_path] = chunk_hash

                        # Check if hash changed
                        if relative_path in self._last_chunk_hashes:
                            if self._last_chunk_hashes[relative_path] != chunk_hash:
                                self.logger.debug(
                                    "Chunk hash changed for %s", relative_path
                                )
                                await self._queue_file_update(relative_path)
                        else:
                            # New file
                            await self._queue_file_update(relative_path)

                    except (OSError, PermissionError) as e:
                        self.logger.debug("Error checking file %s: %s", file_path, e)
                        continue

            # Check for deleted files
            for file_path in self._last_chunk_hashes:
                if file_path not in current_hashes:
                    self.logger.debug("File deleted: %s", file_path)
                    # Queue deletion update
                    await self.folder.sync_manager.queue_update(
                        file_path=file_path,
                        chunk_hash=b"",  # Empty hash for deletion
                        git_ref=self._last_git_ref,
                        priority=2,  # High priority for deletions
                    )

            # Update hash cache
            self._last_chunk_hashes = current_hashes

        except Exception as e:
            self.logger.exception("Error checking chunk hashes")

    async def _queue_file_update(self, file_path: str) -> None:
        """Queue a file update for synchronization.

        Args:
            file_path: Path to updated file

        """
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                file_path_obj = self.folder.folder_path / file_path
                if file_path_obj.exists() and file_path_obj.is_file():
                    # Calculate chunk hash with timeout
                    import hashlib

                    try:
                        with open(file_path_obj, "rb") as f:
                            file_data = f.read()
                            chunk_hash = hashlib.sha256(file_data).digest()
                    except (OSError, PermissionError) as e:
                        self.logger.warning(
                            "Error reading file %s: %s", file_path, e
                        )
                        return

                    # Get git ref with timeout
                    git_ref = None
                    if self.folder.git_versioning:
                        try:
                            git_ref = await asyncio.wait_for(
                                self.folder.git_versioning.get_current_commit(),
                                timeout=5.0,
                            )
                        except (asyncio.TimeoutError, Exception) as e:
                            self.logger.debug(
                                "Error getting git ref for %s: %s", file_path, e
                            )

                    # Queue update with timeout
                    try:
                        await asyncio.wait_for(
                            self.folder.sync_manager.queue_update(
                                file_path=file_path,
                                chunk_hash=chunk_hash,
                                git_ref=git_ref,
                                priority=1,
                            ),
                            timeout=5.0,
                        )
                        return  # Success
                    except asyncio.TimeoutError:
                        if attempt < max_retries - 1:
                            self.logger.debug(
                                "Timeout queueing update for %s, retrying...",
                                file_path,
                            )
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        else:
                            self.logger.warning(
                                "Failed to queue update for %s after %d attempts",
                                file_path,
                                max_retries,
                            )
                            return
                else:
                    # File doesn't exist or isn't a file, skip
                    return

            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.debug(
                        "Error queueing file update for %s (attempt %d/%d): %s, retrying...",
                        file_path,
                        attempt + 1,
                        max_retries,
                        e,
                    )
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    self.logger.exception(
                        "Error queueing file update for %s after %d attempts",
                        file_path,
                        max_retries,
                    )

    async def _discover_peers(self) -> None:
        """Discover peers for updated chunks."""
        if not self.session_manager:
            return

        try:
            # Get peers from session manager
            # This is a simplified version - in practice would query DHT/trackers
            # for peers that have specific chunks

            # For now, just log that we would discover peers
            queue_size = self.folder.sync_manager.get_queue_size()
            if queue_size > 0:
                self.logger.debug(
                    "Would discover peers for %d queued updates", queue_size
                )

        except Exception as e:
            self.logger.exception("Error discovering peers")

    def get_last_check_time(self) -> float:
        """Get timestamp of last check.

        Returns:
            Timestamp of last check

        """
        return self.folder.folder_watcher.get_last_check_time()
