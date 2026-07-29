"""Per-workspace runtime state for XET folder sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from pathlib import Path

    from ccbt.storage.xet_folder_manager import XetFolder


@dataclass
class XetFolderRuntime:
    """Owns the live runtime for a single XET workspace."""

    folder_key: str
    folder_path: Path
    sync_mode: str
    workspace_id: bytes
    tonic_source: str
    metadata_bytes: bytes
    parsed_metadata: dict[str, Any]
    source_peers: list[str] = field(default_factory=list)
    allowlist_hash: Optional[bytes] = None
    allowlist_path: Optional[str] = None
    auth_scope: str = "strict_workspace_auth"
    require_signed_metadata: bool = True
    hash_algorithm: Optional[str] = None
    git_ref: Optional[str] = None
    bootstrap_pending: bool = False
    metadata_source: str = "local"
    backend_status: dict[str, Any] = field(default_factory=dict)
    started: bool = False
    folder: Optional[XetFolder] = None

    async def start(self) -> None:
        """Start the underlying folder runtime if needed."""
        if self.folder is None:
            msg = "Folder runtime is not initialized"
            raise RuntimeError(msg)
        if self.started:
            return
        await self.folder.start()
        self.started = True

    async def stop(self) -> None:
        """Stop the underlying folder runtime if needed."""
        if self.folder is None or not self.started:
            return
        await self.folder.stop()
        self.started = False

    def to_record(self) -> dict[str, Any]:
        """Return a persistence and IPC friendly runtime record (daemon state restore, list_xet_folders)."""
        status = self.folder.get_status().model_dump() if self.folder else {}
        bootstrap_pending = (
            getattr(self.folder, "_bootstrap_pending", self.bootstrap_pending)
            if self.folder is not None
            else self.bootstrap_pending
        )
        backend_status = dict(self.backend_status)
        if self.folder is not None and self.folder.session_manager is not None:
            status_getter = getattr(
                self.folder.session_manager, "get_xet_discovery_status", None
            )
            if callable(status_getter):
                backend_status = dict(status_getter())
        return {
            "folder_key": self.folder_key,
            "folder_path": str(self.folder_path),
            "sync_mode": self.sync_mode,
            "workspace_id": self.workspace_id.hex(),
            "tonic_source": self.tonic_source,
            "source_peers": list(self.source_peers),
            "allowlist_hash": self.allowlist_hash.hex()
            if self.allowlist_hash is not None
            else None,
            "allowlist_path": self.allowlist_path,
            "auth_scope": self.auth_scope,
            "require_signed_metadata": self.require_signed_metadata,
            "hash_algorithm": self.hash_algorithm,
            "git_ref": self.git_ref,
            "bootstrap_pending": bootstrap_pending,
            "metadata_source": self.metadata_source,
            "backend_status": backend_status,
            "started": self.started,
            "status": status,
        }
