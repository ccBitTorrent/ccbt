"""High-level XET folder management wrapper.

This module provides easy-to-use wrappers for XET folder operations including
sync, peer management, status checking, and version tracking.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from ccbt.models import XetSyncStatus
from ccbt.session.xet_sync_manager import XetSyncManager
from ccbt.storage.folder_watcher import FolderWatcher
from ccbt.storage.git_versioning import GitVersioning

logger = logging.getLogger(__name__)


class XetFolder:
    """High-level wrapper for XET-enabled folder operations."""

    def __init__(
        self,
        folder_path: str | Path,
        sync_mode: str = "best_effort",
        source_peers: list[str] | None = None,
        check_interval: float = 5.0,
        enable_git: bool = True,
    ) -> None:
        """Initialize XET folder.

        Args:
            folder_path: Path to folder
            sync_mode: Synchronization mode
            source_peers: Designated source peer IDs (for designated mode)
            check_interval: Folder check interval in seconds
            enable_git: Enable git versioning

        """
        self.folder_path = Path(folder_path).resolve()
        self.sync_mode = sync_mode
        self.source_peers = source_peers or []
        self.check_interval = check_interval
        self.enable_git = enable_git

        # Initialize components
        self.sync_manager = XetSyncManager(
            folder_path=str(self.folder_path),
            sync_mode=sync_mode,
            source_peers=source_peers,
        )

        self.folder_watcher = FolderWatcher(
            folder_path=self.folder_path,
            check_interval=check_interval,
        )

        self.git_versioning: GitVersioning | None = None
        if enable_git:
            self.git_versioning = GitVersioning(folder_path=self.folder_path)

        self.logger = logging.getLogger(__name__)
        self._is_syncing = False

    async def start(self) -> None:
        """Start folder synchronization."""
        # Start folder watcher
        await self.folder_watcher.start()

        # Set up change callback
        self.folder_watcher.add_change_callback(self._on_folder_change)

        # Initialize git ref in sync manager if git versioning is enabled
        if self.git_versioning:
            try:
                current_ref = await asyncio.wait_for(
                    self.git_versioning.get_current_commit(),
                    timeout=5.0,
                )
                if current_ref:
                    self.sync_manager.set_current_git_ref(current_ref)
                    self.logger.debug(
                        "Initialized git ref in sync manager: %s",
                        current_ref[:16],
                    )
            except (asyncio.TimeoutError, Exception) as e:
                self.logger.debug("Error initializing git ref: %s", e)

        self.logger.info("Started XET folder sync for %s", self.folder_path)

    async def stop(self) -> None:
        """Stop folder synchronization."""
        await self.folder_watcher.stop()
        self.logger.info("Stopped XET folder sync for %s", self.folder_path)

    async def sync(self) -> bool:
        """Trigger manual synchronization.

        Returns:
            True if sync started successfully

        """
        if self._is_syncing:
            self.logger.warning("Sync already in progress")
            return False

        self._is_syncing = True

        try:
            # Process queued updates
            processed = await self.sync_manager.process_updates(
                self._handle_update
            )
            self.logger.info("Processed %d updates", processed)
            return True
        except Exception as e:
            self.logger.exception("Error during sync")
            return False
        finally:
            self._is_syncing = False

    async def add_peer(
        self, peer_info: Any, is_source: bool = False
    ) -> None:  # PeerInfo
        """Add peer to folder sync.

        Args:
            peer_info: Peer information
            is_source: Whether peer is a designated source

        """
        await self.sync_manager.add_peer(peer_info, is_source=is_source)
        self.logger.info("Added peer %s to folder sync", peer_info)

    async def remove_peer(self, peer_id: str) -> None:
        """Remove peer from folder sync.

        Args:
            peer_id: Peer identifier

        """
        await self.sync_manager.remove_peer(peer_id)
        self.logger.info("Removed peer %s from folder sync", peer_id)

    def set_sync_mode(
        self, sync_mode: str, source_peers: list[str] | None = None
    ) -> None:
        """Set synchronization mode for folder.

        Args:
            sync_mode: Synchronization mode (designated/best_effort/broadcast/consensus)
            source_peers: List of designated source peer IDs (for designated mode)

        """
        from ccbt.session.xet_sync_manager import SyncMode

        self.sync_mode = sync_mode
        if source_peers:
            self.source_peers = source_peers
        # Update sync manager's sync mode
        self.sync_manager.sync_mode = SyncMode(sync_mode)
        if source_peers:
            self.sync_manager.source_peers = set(source_peers)
        self.logger.info(
            "Set sync mode to %s for folder %s", sync_mode, self.folder_path
        )

    def get_status(self) -> XetSyncStatus:
        """Get current sync status.

        Returns:
            XetSyncStatus object

        """
        status = self.sync_manager.get_status()

        # Update with git ref if available
        if self.git_versioning:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, create task
                    task = asyncio.create_task(
                        self.git_versioning.get_current_commit()
                    )
                    # Don't await, just set None for now
                    status.current_git_ref = None
                else:
                    status.current_git_ref = asyncio.run(
                        self.git_versioning.get_current_commit()
                    )
            except Exception as e:
                self.logger.debug("Error getting git ref: %s", e)

        return status

    async def get_versions(self, max_refs: int = 10) -> list[str]:
        """Get list of git versions.

        Args:
            max_refs: Maximum number of refs to return

        Returns:
            List of git commit hashes

        """
        if not self.git_versioning:
            return []

        try:
            return await self.git_versioning.get_commit_refs(max_refs=max_refs)
        except Exception as e:
            self.logger.exception("Error getting versions")
            return []

    def _on_folder_change(self, event_type: str, file_path: str) -> None:
        """Handle folder change event.

        Args:
            event_type: Type of change (created, modified, deleted)
            file_path: Path to changed file

        """
        self.logger.debug("Folder change detected: %s - %s", event_type, file_path)

        # Queue update for synchronization
        asyncio.create_task(
            self._queue_folder_change(event_type, file_path)
        )

    async def _queue_folder_change(self, event_type: str, file_path: str) -> None:
        """Queue folder change for synchronization.

        Args:
            event_type: Type of change
            file_path: Path to changed file

        """
        try:
            # Calculate chunk hash for file (simplified - in practice would use XET chunking)
            file_path_obj = self.folder_path / file_path
            if file_path_obj.exists() and file_path_obj.is_file():
                # Get file hash
                import hashlib

                with open(file_path_obj, "rb") as f:
                    file_data = f.read()
                    chunk_hash = hashlib.sha256(file_data).digest()

                # Get git ref if available
                git_ref = None
                if self.git_versioning:
                    git_ref = await self.git_versioning.get_current_commit()

                # Queue update
                await self.sync_manager.queue_update(
                    file_path=file_path,
                    chunk_hash=chunk_hash,
                    git_ref=git_ref,
                    priority=1 if event_type == "created" else 0,
                )

        except Exception as e:
            self.logger.exception("Error queueing folder change")

    async def _handle_update(self, entry: Any) -> None:  # UpdateEntry
        """Handle a queued update.

        Args:
            entry: Update entry

        """
        self.logger.debug(
            "Processing update: %s (chunk=%s, git_ref=%s)",
            entry.file_path,
            entry.chunk_hash.hex()[:16],
            entry.git_ref,
        )

        # In a real implementation, this would:
        # 1. Download chunk from peer if needed
        # 2. Update local file
        # 3. Update git if enabled
        # 4. Notify other peers

        # Update git ref in sync manager if changed
        if self.git_versioning:
            try:
                current_ref = await asyncio.wait_for(
                    self.git_versioning.get_current_commit(),
                    timeout=5.0,
                )
                if current_ref:
                    self.sync_manager.set_current_git_ref(current_ref)
                    
                    # Auto-commit if enabled and there are changes
                    if self.git_versioning.auto_commit:
                        try:
                            new_commit = await asyncio.wait_for(
                                self.git_versioning.auto_commit_if_changes(),
                                timeout=10.0,
                            )
                            if new_commit:
                                # Update ref after auto-commit
                                self.sync_manager.set_current_git_ref(new_commit)
                                self.logger.debug(
                                    "Auto-committed changes, new ref: %s",
                                    new_commit[:16],
                                )
                        except asyncio.TimeoutError:
                            self.logger.warning("Timeout during auto-commit")
                        except Exception as e:
                            self.logger.debug("Error during auto-commit: %s", e)
            except (asyncio.TimeoutError, Exception) as e:
                self.logger.debug("Error updating git ref: %s", e)

        # For now, just log
        self.logger.info("Update processed: %s", entry.file_path)

