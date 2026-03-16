"""Resolve tonic files and tonic links into workspace metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ccbt.core.tonic import TonicFile
from ccbt.core.tonic_link import parse_tonic_link


@dataclass
class ResolvedTonicMetadata:
    """Resolved workspace metadata used to start a folder runtime."""

    workspace_id: bytes
    metadata_bytes: bytes
    parsed_metadata: dict[str, Any]
    tonic_source: str


class XetMetadataResolver:
    """Resolve local or linked tonic metadata into a runtime snapshot."""

    def __init__(self) -> None:
        """Initialize tonic parsing helpers for metadata resolution."""
        self._tonic_file = TonicFile()

    async def resolve(
        self,
        tonic_input: str,
        session_manager: Optional[Any] = None,
    ) -> ResolvedTonicMetadata:
        """Resolve a ``.tonic`` file path or ``tonic?:`` link."""
        if tonic_input.startswith("tonic?:"):
            return await self._resolve_link(
                tonic_input, session_manager=session_manager
            )
        return self._resolve_file(tonic_input)

    def _resolve_file(self, tonic_input: str) -> ResolvedTonicMetadata:
        tonic_path = Path(tonic_input)
        metadata_bytes = tonic_path.read_bytes()
        parsed_metadata = self._tonic_file.parse_bytes(metadata_bytes)
        workspace_id = self._tonic_file.get_info_hash(parsed_metadata)
        return ResolvedTonicMetadata(
            workspace_id=workspace_id,
            metadata_bytes=metadata_bytes,
            parsed_metadata=parsed_metadata,
            tonic_source=str(tonic_path.resolve()),
        )

    async def _resolve_link(
        self,
        tonic_input: str,
        session_manager: Optional[Any] = None,
    ) -> ResolvedTonicMetadata:
        link_info = parse_tonic_link(tonic_input)
        metadata_bytes: Optional[bytes] = None
        workspace_id_hex = link_info.info_hash.hex()

        if session_manager is not None:
            getter = getattr(session_manager, "get_registered_xet_metadata", None)
            if callable(getter):
                metadata_bytes = await getter(workspace_id_hex)
            if metadata_bytes is None:
                fetcher = getattr(session_manager, "fetch_xet_metadata", None)
                if callable(fetcher):
                    metadata_bytes = await fetcher(workspace_id_hex)

        if metadata_bytes is None:
            msg = f"No metadata is available for tonic link {workspace_id_hex}"
            raise RuntimeError(msg)

        parsed_metadata = self._tonic_file.parse_bytes(metadata_bytes)
        return ResolvedTonicMetadata(
            workspace_id=link_info.info_hash,
            metadata_bytes=metadata_bytes,
            parsed_metadata=parsed_metadata,
            tonic_source=tonic_input,
        )
