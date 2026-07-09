"""High-level XET folder management wrapper.

This module provides easy-to-use wrappers for XET folder operations including
sync, peer management, status checking, and version tracking.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

from ccbt.core.tonic import TonicFile
from ccbt.models import PeerInfo, XetFileMetadata, XetTorrentMetadata
from ccbt.session.xet_realtime_sync import XetRealtimeSync
from ccbt.session.xet_sync_manager import XetSyncManager
from ccbt.storage.xet_chunking import GearhashChunker
from ccbt.storage.xet_deduplication import XetDeduplication
from ccbt.storage.xet_hashing import XetHasher
from ccbt.utils.compat import to_thread_compat
from ccbt.utils.events import Event, EventType, emit_event

if TYPE_CHECKING:
    from ccbt.models import XetSyncStatus
from ccbt.storage.folder_watcher import FolderWatcher
from ccbt.storage.git_versioning import GitVersioning

logger = logging.getLogger(__name__)


class XetFolder:
    """High-level wrapper for XET-enabled folder operations."""

    def __init__(
        self,
        folder_path: Union[str, Path],
        sync_mode: str = "best_effort",
        source_peers: Optional[list[str]] = None,
        check_interval: float = 5.0,
        enable_git: bool = True,
        session_manager: Optional[Any] = None,
        workspace_id: Optional[bytes] = None,
        folder_key: Optional[str] = None,
        metadata_bytes: Optional[bytes] = None,
        parsed_metadata: Optional[dict[str, Any]] = None,
        tonic_source: Optional[str] = None,
        allowlist_path: Optional[str] = None,
        auth_scope: str = "strict_workspace_auth",
        require_signed_metadata: bool = True,
        hash_algorithm: Optional[str] = None,
    ) -> None:
        """Initialize XET folder.

        Args:
            folder_path: Path to folder
            sync_mode: Synchronization mode
            source_peers: Designated source peer IDs (for designated mode)
            check_interval: Folder check interval in seconds
            enable_git: Enable git versioning
            session_manager: Optional session manager used for shared runtime state
            workspace_id: Optional workspace identifier (info hash bytes)
            folder_key: Optional stable key used for runtime registration
            metadata_bytes: Optional serialized tonic metadata payload
            parsed_metadata: Optional parsed tonic metadata structure
            tonic_source: Source descriptor for imported metadata/link
            allowlist_path: Optional allowlist path for strict workspace auth
            auth_scope: Authorization scope enforced during peer handshake
            require_signed_metadata: Require signed metadata envelopes from peers
            hash_algorithm: Requested hash algorithm override

        """
        self.folder_path = Path(folder_path).resolve()
        self.sync_mode = sync_mode
        self.source_peers = source_peers or []
        self.check_interval = check_interval
        self.enable_git = enable_git
        self.session_manager = session_manager
        self.workspace_id = workspace_id
        self.folder_key = folder_key
        self.metadata_bytes = metadata_bytes
        self.parsed_metadata = parsed_metadata
        self.tonic_source = tonic_source
        self.allowlist_path = allowlist_path
        self.auth_scope = auth_scope
        self.require_signed_metadata = require_signed_metadata
        self.hash_algorithm = hash_algorithm or XetHasher.get_hash_algorithm()

        # Initialize components
        self.sync_manager = XetSyncManager(
            session_manager=session_manager,
            folder_path=str(self.folder_path),
            sync_mode=sync_mode,
            source_peers=source_peers,
            check_interval=check_interval,
        )

        self.folder_watcher = FolderWatcher(
            folder_path=self.folder_path,
            check_interval=check_interval,
        )

        self.git_versioning: Optional[GitVersioning] = None
        if enable_git:
            self.git_versioning = GitVersioning(folder_path=self.folder_path)

        xet_state_dir = self.folder_path / ".xet"
        xet_state_dir.mkdir(parents=True, exist_ok=True)
        self.chunker = GearhashChunker()
        self.hasher = XetHasher()
        self.dedup = XetDeduplication(
            cache_db_path=xet_state_dir / "cache.db",
            dht_client=getattr(session_manager, "dht_client", None),
        )
        # CAS client may be None until start() when discovery graph is ready
        self.cas_client = getattr(session_manager, "xet_cas_client", None)

        self.logger = logging.getLogger(__name__)
        self._is_syncing = False
        self._realtime_sync: Optional[XetRealtimeSync] = None
        self._metadata_lock = asyncio.Lock()
        self._tonic_file = TonicFile()
        self._bootstrap_pending = bool(parsed_metadata)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stopped = False

        if self.parsed_metadata and self.workspace_id is None:
            self.workspace_id = self._tonic_file.get_info_hash(self.parsed_metadata)
        if self.parsed_metadata:
            allowlist_hash = self.parsed_metadata.get("allowlist_hash")
            if isinstance(allowlist_hash, bytes):
                self.sync_manager.set_allowlist_hash(allowlist_hash)

    def __del__(self) -> None:
        """Best-effort cleanup for short-lived folder wrappers in tests/CLI paths."""
        if getattr(self, "_stopped", False):
            return
        with contextlib.suppress(Exception):
            self.dedup.close()

    async def start(self) -> None:
        """Start folder synchronization."""
        self._loop = asyncio.get_running_loop()
        # Require CAS client at start time (discovery graph must be initialized)
        if self.cas_client is None and self.session_manager is not None:
            self.cas_client = getattr(self.session_manager, "xet_cas_client", None)
        if self.cas_client is None:
            msg = (
                "XET discovery not initialized: session manager has no shared "
                "P2PCASClient. Ensure the session creates the discovery graph "
                "(e.g. _ensure_xet_discovery_graph) before starting XET folders."
            )
            raise RuntimeError(msg)
        # Set up change callback
        self.folder_watcher.add_change_callback(self._on_folder_change)
        self.folder_path.mkdir(parents=True, exist_ok=True)

        await self.sync_manager.start()
        if self._bootstrap_pending and not self._workspace_has_user_files():
            await self._bootstrap_from_imported_metadata()
        else:
            await self._refresh_metadata_snapshot()

        # Start folder watcher
        await self.folder_watcher.start()

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

        self._realtime_sync = XetRealtimeSync(
            folder=self,
            check_interval=self.check_interval,
            session_manager=self.session_manager,
        )
        await self._realtime_sync.start()

        await emit_event(
            Event(
                event_type=EventType.FOLDER_SYNC_STARTED.value,
                data={
                    "folder_key": self.folder_key,
                    "folder_path": str(self.folder_path),
                    "workspace_id": self.workspace_id.hex()
                    if self.workspace_id is not None
                    else None,
                },
            )
        )
        self.logger.info("Started XET folder sync for %s", self.folder_path)

    async def stop(self) -> None:
        """Stop folder synchronization."""
        self._stopped = True
        self._loop = None
        if self._realtime_sync is not None:
            await self._realtime_sync.stop()
            self._realtime_sync = None
        await self.folder_watcher.stop()
        await self.sync_manager.stop()
        self.dedup.close()
        self.logger.info("Stopped XET folder sync for %s", self.folder_path)

    async def sync(self) -> tuple[bool, int]:
        """Trigger manual synchronization.

        Returns:
            Tuple of (started_successfully, number_of_updates_processed).
            When started_successfully is False (e.g. already syncing or exception),
            number_of_updates_processed is 0.
        """
        if self._is_syncing:
            self.logger.warning("Sync already in progress")
            return (False, 0)

        self._is_syncing = True

        try:
            # Process queued updates
            processed = await self.sync_manager.process_updates(self._handle_update)
            try:
                await emit_event(
                    Event(
                        event_type=EventType.FOLDER_SYNC_COMPLETED.value,
                        data={
                            "folder_key": self.folder_key,
                            "folder_path": str(self.folder_path),
                            "processed_updates": processed,
                            "workspace_id": self.workspace_id.hex()
                            if self.workspace_id is not None
                            else None,
                        },
                    )
                )
            except Exception:
                self.logger.debug(
                    "Failed to emit FOLDER_SYNC_COMPLETED (non-fatal)", exc_info=True
                )
            self.logger.info("Processed %d updates", processed)
            return (True, processed)
        except Exception:
            self.sync_manager.set_last_error("Sync failed")
            try:
                await emit_event(
                    Event(
                        event_type=EventType.FOLDER_SYNC_ERROR.value,
                        data={
                            "folder_key": self.folder_key,
                            "folder_path": str(self.folder_path),
                            "workspace_id": self.workspace_id.hex()
                            if self.workspace_id is not None
                            else None,
                        },
                    )
                )
            except Exception:
                self.logger.debug(
                    "Failed to emit FOLDER_SYNC_ERROR (non-fatal)", exc_info=True
                )
            self.logger.exception("Error during sync")
            return (False, 0)
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
        self, sync_mode: str, source_peers: Optional[list[str]] = None
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

        if status.current_git_ref is None:
            status.current_git_ref = self.sync_manager.get_current_git_ref()

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
        except Exception:
            self.logger.exception("Error getting versions")
            return []

    def _workspace_has_user_files(self) -> bool:
        """Return True when the workspace already contains synced user files."""
        for file_path_obj in self.folder_path.rglob("*"):
            if not file_path_obj.is_file():
                continue
            relative_parts = file_path_obj.relative_to(self.folder_path).parts
            if relative_parts and relative_parts[0] in {".git", ".xet"}:
                continue
            return True
        return False

    def _normalize_snapshot_file_metadata(
        self, metadata: Any
    ) -> Optional[XetFileMetadata]:
        """Convert parsed tonic snapshot entries into XetFileMetadata models."""
        if isinstance(metadata, XetFileMetadata):
            return metadata
        if isinstance(metadata, dict):
            try:
                return XetFileMetadata.model_validate(metadata)
            except Exception:
                self.logger.debug("Invalid snapshot file metadata entry", exc_info=True)
                return None
        return None

    def _iter_snapshot_file_metadata(
        self, parsed_metadata: Optional[dict[str, Any]] = None
    ) -> list[XetFileMetadata]:
        """Return normalized file manifests from a parsed tonic snapshot."""
        snapshot = (
            parsed_metadata if parsed_metadata is not None else self.parsed_metadata
        )
        if not snapshot:
            return []
        xet_metadata = snapshot.get("xet_metadata")
        if not isinstance(xet_metadata, dict):
            return []
        file_metadata = xet_metadata.get("file_metadata", [])
        if not isinstance(file_metadata, list):
            return []
        manifests: list[XetFileMetadata] = []
        for metadata in file_metadata:
            normalized = self._normalize_snapshot_file_metadata(metadata)
            if normalized is not None:
                manifests.append(normalized)
        return manifests

    async def apply_remote_metadata_snapshot(self, metadata_bytes: bytes) -> bool:
        """Adopt a remote tonic snapshot for this workspace runtime.

        This updates in-memory file manifests without forcing a full local metadata
        rebuild, which is important when an incoming update references a file path
        that the current runtime has not materialized yet.
        """
        try:
            parsed_metadata = self._tonic_file.parse_bytes(metadata_bytes)
            workspace_id = self._tonic_file.get_info_hash(parsed_metadata)
        except Exception:
            self.logger.debug(
                "Failed to parse remote XET metadata snapshot", exc_info=True
            )
            return False

        canonical_workspace_id = self.workspace_id or workspace_id
        if self.workspace_id is not None and workspace_id != self.workspace_id:
            self.logger.debug(
                "Accepting remote metadata snapshot with derived info hash %s for canonical workspace %s",
                workspace_id.hex()[:16],
                self.workspace_id.hex()[:16],
            )

        manifests = self._iter_snapshot_file_metadata(parsed_metadata)
        async with self._metadata_lock:
            self.metadata_bytes = metadata_bytes
            self.parsed_metadata = parsed_metadata
            self.workspace_id = canonical_workspace_id
            allowlist_hash = parsed_metadata.get("allowlist_hash")
            if isinstance(allowlist_hash, bytes):
                self.sync_manager.set_allowlist_hash(allowlist_hash)
            self.sync_manager.file_metadata_by_path.update(
                {metadata.file_path: metadata for metadata in manifests}
            )
            git_refs = parsed_metadata.get("git_refs")
            if isinstance(git_refs, list) and git_refs:
                current_git_ref = git_refs[0]
                if isinstance(current_git_ref, str):
                    self.sync_manager.set_current_git_ref(current_git_ref)

        if self.session_manager is not None and hasattr(
            self.session_manager, "register_xet_metadata"
        ):
            await self.session_manager.register_xet_metadata(
                canonical_workspace_id.hex(),
                metadata_bytes,
            )
        return True

    def _build_chunk_provider_context(self) -> dict[str, Any]:
        """Build a workspace-scoped context for CAS chunk transfers."""
        if self.workspace_id is None:
            return {"folder_key": self.folder_key, "workspace_id": None}
        return {
            "folder_key": self.folder_key,
            "workspace_id": self.workspace_id,
            "workspace_id_hex": self.workspace_id.hex(),
        }

    async def _bootstrap_from_imported_metadata(self) -> None:
        """Use imported workspace metadata as authority until local materialization succeeds."""
        manifests = self._iter_snapshot_file_metadata()
        self.sync_manager.file_metadata_by_path = {
            metadata.file_path: metadata for metadata in manifests
        }

        if (
            self.workspace_id is not None
            and self.session_manager is not None
            and hasattr(self.session_manager, "register_xet_metadata")
        ):
            await self.session_manager.register_xet_metadata(
                self.workspace_id.hex(),
                self.metadata_bytes or b"",
            )

        if not manifests:
            self._bootstrap_pending = False
            return

        for metadata in manifests:
            await self.sync_manager.queue_update(
                file_path=metadata.file_path,
                chunk_hash=metadata.file_hash,
                git_ref=self.sync_manager.get_current_git_ref(),
                priority=2,
                file_metadata=metadata,
            )

        started, _ = await self.sync()
        if started and self._workspace_has_user_files():
            self._bootstrap_pending = False

    def _on_folder_change(self, event_type: str, file_path: str) -> None:
        """Handle folder change event.

        Args:
            event_type: Type of change (created, modified, deleted)
            file_path: Path to changed file

        """
        path_parts = Path(file_path).parts
        if path_parts and path_parts[0] in {".git", ".xet"}:
            return
        self.logger.debug("Folder change detected: %s - %s", event_type, file_path)

        def _schedule() -> None:
            asyncio.create_task(  # noqa: RUF006
                self._queue_folder_change(event_type, file_path)
            )

        if self._loop is None or not self._loop.is_running():
            return
        self._loop.call_soon_threadsafe(_schedule)

    async def _queue_folder_change(self, event_type: str, file_path: str) -> None:
        """Queue folder change for synchronization.

        Args:
            event_type: Type of change
            file_path: Path to changed file

        """
        try:
            git_ref = self.sync_manager.get_current_git_ref()
            if self.git_versioning:
                git_ref = await self.git_versioning.get_current_commit()
                self.sync_manager.set_current_git_ref(git_ref)

            deleted = event_type == "deleted"
            file_metadata = None
            chunk_hash = bytes(32)
            if not deleted:
                file_metadata = await self._build_file_metadata(file_path)
                if file_metadata is None:
                    return
                chunk_hash = file_metadata.file_hash

            await self._refresh_metadata_snapshot()
            await self.sync_manager.queue_update(
                file_path=file_path,
                chunk_hash=chunk_hash,
                git_ref=git_ref,
                priority=1 if event_type == "created" else 0,
                file_metadata=file_metadata,
                deleted=deleted,
            )
            if (
                self.session_manager is not None
                and self.workspace_id is not None
                and hasattr(self.session_manager, "broadcast_xet_update")
            ):
                await self.session_manager.broadcast_xet_update(
                    workspace_id_hex=self.workspace_id.hex(),
                    source_folder_key=self.folder_key,
                    file_path=file_path,
                    chunk_hash=chunk_hash,
                    git_ref=git_ref,
                    file_metadata=file_metadata,
                    deleted=deleted,
                )

        except Exception:
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
        target_path = self.folder_path / entry.file_path

        if entry.deleted:
            exists = await to_thread_compat(target_path.exists)
            if exists:
                await to_thread_compat(lambda: target_path.unlink(missing_ok=True))
            await self._refresh_metadata_snapshot()
            self.sync_manager.set_last_error(None)
            self.logger.info("Deleted synced file: %s", entry.file_path)
            return

        def _metadata_matches_update(
            metadata: Optional[XetFileMetadata],
            expected_chunk_hash: bytes,
        ) -> bool:
            if expected_chunk_hash == bytes(32):
                return True
            chunk_hashes = getattr(metadata, "chunk_hashes", None)
            if isinstance(chunk_hashes, list) and expected_chunk_hash in chunk_hashes:
                return True
            file_hash = getattr(metadata, "file_hash", None)
            return file_hash is not None and file_hash == expected_chunk_hash

        metadata_refreshed = False
        entry_metadata = entry.file_metadata
        while True:
            file_metadata = entry_metadata or self.sync_manager.get_file_metadata(
                entry.file_path
            )
            if file_metadata is None:
                file_metadata = self._get_file_metadata_from_snapshot(entry.file_path)
            if (
                file_metadata is None
                and self.session_manager is not None
                and self.workspace_id is not None
                and hasattr(self.session_manager, "fetch_xet_metadata")
            ):
                metadata_bytes = await self.session_manager.fetch_xet_metadata(
                    self.workspace_id.hex()
                )
                if metadata_bytes is not None:
                    await self.apply_remote_metadata_snapshot(metadata_bytes)
                    file_metadata = self.sync_manager.get_file_metadata(entry.file_path)
                    if file_metadata is None:
                        file_metadata = self._get_file_metadata_from_snapshot(
                            entry.file_path
                        )
            if file_metadata is None:
                msg = f"Missing file metadata for {entry.file_path}"
                raise FileNotFoundError(msg)
            if entry.chunk_hash != bytes(32) and not _metadata_matches_update(
                file_metadata, entry.chunk_hash
            ):
                file_hash_value = (
                    file_metadata.file_hash.hex()[:16]
                    if hasattr(file_metadata, "file_hash")
                    and file_metadata.file_hash is not None
                    else "None"
                )
                msg = (
                    f"Incoming file metadata hash mismatch for {entry.file_path}: "
                    f"expected={entry.chunk_hash.hex()[:16]} file_hash="
                    f"{file_hash_value}"
                )
                if not metadata_refreshed and (
                    self.session_manager is not None
                    and self.workspace_id is not None
                    and hasattr(self.session_manager, "fetch_xet_metadata")
                ):
                    metadata_refreshed = True
                    metadata_bytes = await self.session_manager.fetch_xet_metadata(
                        self.workspace_id.hex()
                    )
                    if metadata_bytes is not None:
                        await self.apply_remote_metadata_snapshot(metadata_bytes)
                        entry_metadata = None
                        continue
                self.sync_manager.set_last_error(msg)
                raise FileNotFoundError(msg)
            break
        file_chunks: list[bytes] = []
        actual_chunk_hashes: list[bytes] = []
        for chunk_hash in file_metadata.chunk_hashes:
            chunk_path = await self.dedup.check_chunk_exists(chunk_hash)
            if chunk_path is None:
                chunk_path = await self._fetch_missing_chunk(
                    entry.file_path,
                    chunk_hash,
                    source_peer=entry.source_peer,
                )
            if chunk_path is None:
                msg = f"Missing chunk {chunk_hash.hex()[:16]} for {entry.file_path}"
                self.sync_manager.set_last_error(msg)
                raise FileNotFoundError(msg)
            chunk_bytes = await to_thread_compat(chunk_path.read_bytes)
            actual_chunk_hash = self.hasher.compute_chunk_hash(
                chunk_bytes, algorithm=self.hash_algorithm
            )
            if actual_chunk_hash != chunk_hash:
                msg = f"Chunk hash mismatch for {entry.file_path}"
                self.sync_manager.set_last_error(msg)
                raise ValueError(msg)
            actual_chunk_hashes.append(actual_chunk_hash)
            file_chunks.append(chunk_bytes)

        rebuilt_data = b"".join(file_chunks)
        rebuilt_hash = self.hasher.build_merkle_tree_from_hashes(
            actual_chunk_hashes, algorithm=self.hash_algorithm
        )
        if rebuilt_hash != file_metadata.file_hash:
            msg = f"File hash mismatch for {entry.file_path}"
            self.sync_manager.set_last_error(msg)
            raise ValueError(msg)

        def _write_materialized_file() -> None:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(rebuilt_data[: file_metadata.total_size])

        await to_thread_compat(_write_materialized_file)

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

        await self._refresh_metadata_snapshot()
        latest_metadata = await self._build_file_metadata(entry.file_path)
        if latest_metadata is not None:
            self.sync_manager.file_metadata_by_path[entry.file_path] = latest_metadata
        elif file_metadata is not None:
            # Fallback to update payload metadata only when local rebuild is unavailable.
            self.sync_manager.file_metadata_by_path[entry.file_path] = file_metadata
        self._bootstrap_pending = False
        self.sync_manager.set_last_error(None)
        self.logger.info("Update processed: %s", entry.file_path)

    async def _fetch_missing_chunk(
        self,
        file_path: str,
        chunk_hash: bytes,
        source_peer: Optional[str] = None,
    ) -> Optional[Path]:
        """Fetch a missing chunk from session-local runtimes or remote CAS peers."""
        if (
            self.session_manager is not None
            and self.workspace_id is not None
            and hasattr(self.session_manager, "fetch_xet_chunk")
        ):
            chunk_bytes = await self.session_manager.fetch_xet_chunk(
                workspace_id_hex=self.workspace_id.hex(),
                chunk_hash=chunk_hash,
                exclude_folder_key=self.folder_key,
            )
            if chunk_bytes is not None:
                await self.dedup.store_chunk(
                    chunk_hash=chunk_hash,
                    chunk_data=chunk_bytes,
                    file_path=file_path,
                    file_offset=0,
                )
                return await self.dedup.check_chunk_exists(chunk_hash)

        if self.cas_client is None:
            return None
        peers = []
        if source_peer:
            peers = await self.cas_client.find_chunk_peers(
                chunk_hash,
                workspace_id_hex=self.workspace_id.hex()
                if self.workspace_id is not None
                else None,
            )
            peers = [peer for peer in peers if str(peer) == source_peer] or peers
        else:
            peers = await self.cas_client.find_chunk_peers(
                chunk_hash,
                workspace_id_hex=self.workspace_id.hex()
                if self.workspace_id is not None
                else None,
            )

        if not peers:
            return None

        torrent_context = self._build_chunk_provider_context()
        for peer in peers:
            try:
                connection_manager = None
                if self.session_manager is not None and hasattr(
                    self.session_manager, "get_xet_connection_manager"
                ):
                    connection_manager = (
                        await self.session_manager.get_xet_connection_manager(peer)
                    )
                chunk_bytes = await self.cas_client.download_chunk(
                    chunk_hash,
                    peer,
                    torrent_data=torrent_context,
                    connection_manager=connection_manager,
                )
                await self.dedup.store_chunk(
                    chunk_hash=chunk_hash,
                    chunk_data=chunk_bytes,
                    file_path=file_path,
                    file_offset=0,
                )
                return await self.dedup.check_chunk_exists(chunk_hash)
            except Exception:
                self.logger.debug(
                    "Failed to download chunk %s from %s",
                    chunk_hash.hex()[:16],
                    peer,
                    exc_info=True,
                )
        return None

    async def _build_file_metadata(self, file_path: str) -> Optional[XetFileMetadata]:
        """Build chunk manifest for a workspace file and persist its chunks."""
        if self.cas_client is None:
            return None
        file_path_obj = self.folder_path / file_path
        exists = await to_thread_compat(file_path_obj.exists)
        if not exists or not await to_thread_compat(file_path_obj.is_file):
            return None

        file_data = await to_thread_compat(file_path_obj.read_bytes)
        chunk_hashes: list[bytes] = []
        offset = 0
        for chunk_data in self.chunker.chunk_buffer(file_data):
            chunk_hash = self.hasher.compute_chunk_hash(
                chunk_data, algorithm=self.hash_algorithm
            )
            await self.dedup.store_chunk(
                chunk_hash=chunk_hash,
                chunk_data=chunk_data,
                file_path=file_path,
                file_offset=offset,
            )
            local_peer_info = None
            if self.session_manager is not None:
                local_port = (
                    self.session_manager.config.network.xet_port
                    or self.session_manager.config.network.listen_port
                )
                local_peer_info = PeerInfo(
                    ip="127.0.0.1",
                    port=local_port,
                    peer_source="xet-local",
                )
            await self.cas_client.announce_chunk(
                chunk_hash,
                peer_info=local_peer_info,
                workspace_id_hex=self.workspace_id.hex()
                if self.workspace_id is not None
                else None,
            )
            chunk_hashes.append(chunk_hash)
            offset += len(chunk_data)

        file_hash = (
            self.hasher.build_merkle_tree_from_hashes(
                chunk_hashes, algorithm=self.hash_algorithm
            )
            if chunk_hashes
            else self.hasher.compute_chunk_hash(b"", algorithm=self.hash_algorithm)
        )
        file_metadata = XetFileMetadata(
            file_path=file_path,
            file_hash=file_hash,
            chunk_hashes=chunk_hashes,
            total_size=len(file_data),
        )
        await self.dedup.store_file_metadata(file_metadata)
        return file_metadata

    async def _refresh_metadata_snapshot(self) -> None:
        """Rebuild and publish the current tonic metadata for this workspace."""
        async with self._metadata_lock:
            file_metadata: list[XetFileMetadata] = []
            all_chunk_hashes: set[bytes] = set()

            def _list_workspace_files() -> list[Path]:
                out: list[Path] = []
                for p in self.folder_path.rglob("*"):
                    if not p.is_file():
                        continue
                    try:
                        rel = p.relative_to(self.folder_path)
                    except ValueError:
                        continue
                    parts = rel.parts
                    if parts and parts[0] in {".git", ".xet"}:
                        continue
                    out.append(p)
                return out

            workspace_files = await to_thread_compat(_list_workspace_files)

            for file_path_obj in workspace_files:
                relative_path = str(file_path_obj.relative_to(self.folder_path))
                metadata = await self._build_file_metadata(relative_path)
                if metadata is None:
                    continue
                file_metadata.append(metadata)
                all_chunk_hashes.update(metadata.chunk_hashes)

            git_refs: Optional[list[str]] = None
            if self.git_versioning:
                current_ref = await self.git_versioning.get_current_commit()
                if current_ref:
                    git_refs = [current_ref]
                    self.sync_manager.set_current_git_ref(current_ref)

            announce = None
            announce_list = None
            comment = None
            allowlist_hash = self.sync_manager.get_allowlist_hash()
            if self.parsed_metadata:
                announce = self.parsed_metadata.get("announce")
                announce_list = self.parsed_metadata.get("announce_list")
                comment = self.parsed_metadata.get("comment")

            tonic_bytes = self._tonic_file.create(
                folder_name=self.folder_path.name,
                xet_metadata=XetTorrentMetadata(
                    chunk_hashes=sorted(all_chunk_hashes),
                    file_metadata=file_metadata,
                    piece_metadata=[],
                    xorb_hashes=[],
                ),
                git_refs=git_refs,
                sync_mode=self.sync_mode,
                source_peers=self.source_peers or None,
                allowlist_hash=allowlist_hash,
                announce=announce,
                announce_list=announce_list,
                comment=comment,
            )
            self.metadata_bytes = tonic_bytes
            self.parsed_metadata = self._tonic_file.parse_bytes(tonic_bytes)
            if self.workspace_id is None:
                self.workspace_id = self._tonic_file.get_info_hash(self.parsed_metadata)
            self.sync_manager.file_metadata_by_path = {
                metadata.file_path: metadata for metadata in file_metadata
            }

            if self.session_manager is not None and hasattr(
                self.session_manager, "register_xet_metadata"
            ):
                await self.session_manager.register_xet_metadata(
                    self.workspace_id.hex(),
                    tonic_bytes,
                )

    def _get_file_metadata_from_snapshot(
        self, file_path: str
    ) -> Optional[XetFileMetadata]:
        """Look up a file manifest in the current workspace metadata snapshot."""
        if not self.parsed_metadata:
            return None
        xet_metadata = self.parsed_metadata.get("xet_metadata")
        if not isinstance(xet_metadata, dict):
            return None
        for metadata in xet_metadata.get("file_metadata", []):
            normalized = self._normalize_snapshot_file_metadata(metadata)
            if normalized is not None and normalized.file_path == file_path:
                return normalized
        return None

    async def get_chunk_bytes(self, chunk_hash: bytes) -> Optional[bytes]:
        """Return local chunk bytes if available for this workspace runtime."""
        chunk_path = await self.dedup.check_chunk_exists(chunk_hash)
        if chunk_path is None:
            return None
        return await to_thread_compat(chunk_path.read_bytes)
