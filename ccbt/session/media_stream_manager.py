"""Manager for daemon-backed media stream runtimes."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Optional

from ccbt.session.media_stream_runtime import MediaStreamRuntime


class MediaStreamManager:
    """Manage active media stream runtimes for torrent files."""

    def __init__(self, session_manager: Any) -> None:
        """Initialize the runtime registry for media streams."""
        self._session_manager = session_manager
        self._streams: dict[str, MediaStreamRuntime] = {}
        self._stream_by_info_hash: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def start_stream(
        self,
        info_hash_hex: str,
        *,
        file_index: int,
        port: Optional[int] = None,
    ) -> dict[str, Any]:
        """Start or replace the active media stream for a torrent."""
        media_config = getattr(self._session_manager.config, "media", None)
        if media_config is None or not media_config.enable_media_streaming:
            msg = "Media streaming is disabled in configuration"
            raise RuntimeError(msg)

        existing_stream_id = await self._get_stream_id_for_info_hash(info_hash_hex)
        if existing_stream_id is not None:
            await self.stop_stream(existing_stream_id)

        torrent_session = await self._get_torrent_session(info_hash_hex)
        if not torrent_session.ensure_file_selection_manager():
            msg = "File selection metadata is not ready for this torrent"
            raise RuntimeError(msg)
        file_manager = torrent_session.file_selection_manager
        if file_manager is None:
            msg = "File selection manager is not available for this torrent"
            raise RuntimeError(msg)

        try:
            file_info = file_manager.torrent_info.files[file_index]
        except IndexError as exc:
            msg = f"Invalid file index: {file_index}"
            raise ValueError(msg) from exc
        if file_info.is_padding:
            msg = "Padding files cannot be streamed"
            raise ValueError(msg)

        relative_path = getattr(file_info, "full_path", None) or file_info.name
        file_path = Path(torrent_session.output_dir) / relative_path
        runtime = MediaStreamRuntime(
            stream_id=uuid.uuid4().hex,
            info_hash_hex=info_hash_hex,
            file_index=file_index,
            file_name=file_info.name,
            file_path=file_path,
            file_size=file_info.length,
            file_offset=self._compute_file_offset(
                file_manager.torrent_info.files, file_index
            ),
            bind_host=media_config.bind_host,
            requested_port=port if port is not None else media_config.default_port,
            token_ttl_seconds=media_config.token_ttl_seconds,
            startup_buffer_seconds=media_config.startup_buffer_seconds,
            request_wait_timeout_seconds=media_config.request_wait_timeout_seconds,
            assumed_bitrate_bytes_per_second=media_config.assumed_bitrate_bytes_per_second,
            chunk_size=media_config.stream_chunk_size_kib * 1024,
            torrent_session=torrent_session,
            session_manager=self._session_manager,
            piece_manager=torrent_session.piece_manager,
            file_selection_manager=file_manager,
        )
        async with self._lock:
            self._streams[runtime.stream_id] = runtime
            self._stream_by_info_hash[info_hash_hex] = runtime.stream_id
        try:
            await runtime.start()
            return await runtime.to_start_record()
        except Exception:
            async with self._lock:
                self._streams.pop(runtime.stream_id, None)
                self._stream_by_info_hash.pop(info_hash_hex, None)
            await runtime.stop()
            raise

    async def stop_stream(self, stream_id: str) -> bool:
        """Stop an active stream by identifier."""
        async with self._lock:
            runtime = self._streams.pop(stream_id, None)
            if runtime is None:
                return False
            self._stream_by_info_hash.pop(runtime.info_hash_hex, None)
        await runtime.stop()
        return True

    async def stop_stream_for_torrent(self, info_hash_hex: str) -> bool:
        """Stop the active stream for a torrent if present."""
        stream_id = await self._get_stream_id_for_info_hash(info_hash_hex)
        if stream_id is None:
            return False
        return await self.stop_stream(stream_id)

    async def get_status(
        self,
        *,
        stream_id: Optional[str] = None,
        info_hash_hex: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Return a status snapshot for a stream."""
        runtime: Optional[MediaStreamRuntime]
        async with self._lock:
            if stream_id is not None:
                runtime = self._streams.get(stream_id)
            elif info_hash_hex is not None:
                stream_key = self._stream_by_info_hash.get(info_hash_hex)
                runtime = self._streams.get(stream_key) if stream_key else None
            else:
                runtime = None
        if runtime is None:
            return None
        await runtime.refresh_readiness()
        return await runtime.to_status_record()

    async def has_active_stream(self, info_hash_hex: str) -> bool:
        """Return whether a torrent currently has an active media stream."""
        async with self._lock:
            return info_hash_hex in self._stream_by_info_hash

    async def stop_all_streams(self) -> None:
        """Stop all active media streams."""
        async with self._lock:
            stream_ids = list(self._streams.keys())
        for stream_id in stream_ids:
            await self.stop_stream(stream_id)

    async def _get_stream_id_for_info_hash(self, info_hash_hex: str) -> Optional[str]:
        """Return the active stream id for a torrent if present."""
        async with self._lock:
            return self._stream_by_info_hash.get(info_hash_hex)

    async def _get_torrent_session(self, info_hash_hex: str) -> Any:
        """Look up a torrent session by hex info hash."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError as exc:
            msg = f"Invalid info hash format: {info_hash_hex}"
            raise ValueError(msg) from exc

        async with self._session_manager.lock:
            torrent_session = self._session_manager.torrents.get(info_hash)
        if torrent_session is None:
            msg = f"Torrent not found: {info_hash_hex}"
            raise ValueError(msg)
        return torrent_session

    @staticmethod
    def _compute_file_offset(files: list[Any], target_index: int) -> int:
        """Return the torrent-global starting byte offset for a file."""
        return sum(int(file_info.length) for file_info in files[:target_index])
