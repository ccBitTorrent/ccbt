"""Runtime for a single daemon-backed media stream."""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from aiohttp import web

from ccbt.models import PieceSelectionStrategy, PieceState
from ccbt.utils.events import Event, emit_event

if TYPE_CHECKING:
    from pathlib import Path


def _open_seek(path: Any, start: int) -> Any:
    """Open path in binary read mode and seek to start (for use in asyncio.to_thread)."""
    handle = path.open("rb")
    handle.seek(start)
    return handle


def _parse_range_header(value: Optional[str], total_size: int) -> tuple[int, int, int]:
    """Parse a simple HTTP byte range header."""
    if total_size <= 0:
        return 0, -1, 200
    if not value:
        return 0, total_size - 1, 200
    if not value.startswith("bytes="):
        msg = "Unsupported Range header"
        raise web.HTTPBadRequest(text=msg)

    range_spec = value[len("bytes=") :].strip()
    if "," in range_spec:
        msg = "Multiple byte ranges are not supported"
        raise web.HTTPBadRequest(text=msg)

    start_text, end_text = range_spec.split("-", 1)
    if not start_text:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise web.HTTPRequestRangeNotSatisfiable
        start = max(total_size - suffix_length, 0)
        end = total_size - 1
        return start, end, 206

    start = int(start_text)
    end = total_size - 1 if not end_text else int(end_text)
    if start < 0 or end < start or start >= total_size:
        raise web.HTTPRequestRangeNotSatisfiable
    return start, min(end, total_size - 1), 206


@dataclass
class MediaStreamRuntime:
    """Own the live HTTP range server for a single torrent file."""

    stream_id: str
    info_hash_hex: str
    file_index: int
    file_name: str
    file_path: Path
    file_size: int
    file_offset: int
    bind_host: str
    requested_port: int
    token_ttl_seconds: float
    startup_buffer_seconds: float
    request_wait_timeout_seconds: float
    assumed_bitrate_bytes_per_second: int
    chunk_size: int
    torrent_session: Any
    session_manager: Any
    piece_manager: Any
    file_selection_manager: Any
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    state: str = "starting"
    bytes_served: int = 0
    client_count: int = 0
    current_range_start: Optional[int] = None
    current_range_end: Optional[int] = None
    available_bytes: int = 0
    buffer_progress: float = 0.0
    last_error: Optional[str] = None
    token_expires_at: float = field(init=False)
    bound_port: int = 0
    runner: Optional[web.AppRunner] = None
    site: Optional[web.TCPSite] = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _previous_streaming_mode: bool = field(default=False, init=False, repr=False)
    _previous_piece_selection: PieceSelectionStrategy = field(
        default=PieceSelectionStrategy.RAREST_FIRST,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Finish derived initialization."""
        self.token_expires_at = time.time() + self.token_ttl_seconds

    @property
    def stream_url(self) -> Optional[str]:
        """Return the tokenized stream URL when bound."""
        if self.bound_port <= 0:
            return None
        return f"http://{self.bind_host}:{self.bound_port}/stream?token={self.token}"

    async def start(self) -> None:
        """Start the localhost HTTP range server."""
        await self._enable_streaming_mode()
        app = web.Application()
        app.router.add_get("/stream", self._handle_stream_request)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(
            self.runner,
            self.bind_host,
            self.requested_port,
        )
        try:
            await self.site.start()
            await self._capture_bound_port()
            await self._emit_event("media_stream_started")
            await self.refresh_readiness()
        except Exception:
            if self.site is not None:
                with contextlib.suppress(Exception):
                    await self.site.stop()
            if self.runner is not None:
                with contextlib.suppress(Exception):
                    await self.runner.cleanup()
            raise

    async def stop(self) -> None:
        """Stop the stream and restore piece-selection settings."""
        async with self._lock:
            self.state = "stopped"
        await self._restore_piece_selection()
        if self.site is not None:
            with contextlib.suppress(Exception):
                await self.site.stop()
        if self.runner is not None:
            with contextlib.suppress(Exception):
                await self.runner.cleanup()
        await self._emit_event("media_stream_stopped")

    async def refresh_readiness(self) -> None:
        """Refresh startup buffer/readiness state."""
        available_bytes = await self._estimate_available_bytes(0)
        minimum_ready_bytes = min(
            self.file_size,
            max(
                self.chunk_size,
                int(
                    self.assumed_bitrate_bytes_per_second * self.startup_buffer_seconds
                ),
            ),
        )
        progress = (
            1.0
            if minimum_ready_bytes == 0
            else min(
                1.0,
                available_bytes / float(minimum_ready_bytes),
            )
        )
        async with self._lock:
            self.available_bytes = available_bytes
            self.buffer_progress = progress
        if available_bytes >= minimum_ready_bytes or available_bytes >= self.file_size:
            await self._set_state("ready")
        else:
            await self._set_state("buffering")

    async def to_status_record(self) -> dict[str, Any]:
        """Return the current runtime status as a serializable dictionary."""
        async with self._lock:
            return {
                "stream_id": self.stream_id,
                "info_hash": self.info_hash_hex,
                "file_index": self.file_index,
                "file_name": self.file_name,
                "file_path": str(self.file_path),
                "file_size": self.file_size,
                "state": self.state,
                "stream_url": self.stream_url,
                "bind_host": self.bind_host,
                "bind_port": self.bound_port,
                "token_expires_at": self.token_expires_at,
                "bytes_served": self.bytes_served,
                "client_count": self.client_count,
                "current_range_start": self.current_range_start,
                "current_range_end": self.current_range_end,
                "available_bytes": self.available_bytes,
                "buffer_progress": self.buffer_progress,
                "last_error": self.last_error,
            }

    async def to_start_record(self) -> dict[str, Any]:
        """Return the response payload for stream startup."""
        await self.refresh_readiness()
        return {
            "stream_id": self.stream_id,
            "info_hash": self.info_hash_hex,
            "file_index": self.file_index,
            "state": self.state,
            "stream_url": self.stream_url or "",
            "launched_external": False,
        }

    async def _capture_bound_port(self) -> None:
        """Resolve the bound port after the server starts.

        Uses the runner's public ``addresses`` attribute (aiohttp 3.3+), which
        holds the result of socket.getsockname() for each served socket.
        Falls back to requested_port when it was explicitly set (non-zero).
        """
        if self.runner is not None:
            addresses = getattr(self.runner, "addresses", None)
            if addresses and len(addresses) >= 1:
                addr = addresses[0]
                if isinstance(addr, tuple) and len(addr) >= 2:
                    self.bound_port = int(addr[1])
                    return
        if self.requested_port and self.requested_port != 0:
            self.bound_port = self.requested_port

    async def _handle_stream_request(self, request: web.Request) -> web.StreamResponse:
        """Serve a HEAD/GET request with byte-range support."""
        self._validate_token(request)
        if self.file_size <= 0:
            raise web.HTTPNotFound(text="Selected file is empty")

        method = request.method.upper()
        start, end, status_code = _parse_range_header(
            request.headers.get("Range"),
            self.file_size,
        )
        await self._record_range_request(start, end)
        available_end = await self._wait_for_requested_bytes(start)
        if available_end < start:
            raise web.HTTPServiceUnavailable(
                text="Requested media range is not buffered yet",
                headers={"Retry-After": "1"},
            )

        end = min(end, available_end)
        if end < self.file_size - 1 and status_code == 200:
            status_code = 206
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(max(end - start + 1, 0)),
        }
        if status_code == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{self.file_size}"

        if method == "HEAD":
            return web.Response(status=status_code, headers=headers)

        response = web.StreamResponse(status=status_code, headers=headers)
        await response.prepare(request)
        await self._increment_clients()
        try:
            await self._write_stream_bytes(response, start, end)
        finally:
            await self._decrement_clients()
            with contextlib.suppress(Exception):
                await response.write_eof()
        return response

    def _validate_token(self, request: web.Request) -> None:
        """Reject requests with a missing or expired token."""
        provided = request.query.get("token") or ""
        expired = time.time() > self.token_expires_at
        match = hmac.compare_digest(provided, self.token)
        if not match or expired:
            raise web.HTTPUnauthorized(text="Invalid or expired media stream token")

    async def _write_stream_bytes(
        self,
        response: web.StreamResponse,
        start: int,
        end: int,
    ) -> None:
        """Write the selected byte range to the client."""
        remaining = end - start + 1
        handle = await asyncio.to_thread(_open_seek, self.file_path, start)
        try:
            while remaining > 0:
                read_size = min(self.chunk_size, remaining)
                chunk = await asyncio.to_thread(handle.read, read_size)
                if not chunk:
                    break
                await response.write(chunk)
                remaining -= len(chunk)
                async with self._lock:
                    self.bytes_served += len(chunk)
        finally:
            await asyncio.to_thread(handle.close)

    async def _wait_for_requested_bytes(self, start_offset: int) -> int:
        """Wait briefly for the requested range to become locally readable."""
        deadline = time.monotonic() + self.request_wait_timeout_seconds
        while True:
            available_bytes = await self._estimate_available_bytes(start_offset)
            if available_bytes > start_offset:
                await self.refresh_readiness()
                return available_bytes - 1
            await self._set_state("buffering")
            if time.monotonic() >= deadline:
                break
            await asyncio.sleep(0.25)
        available_bytes = await self._estimate_available_bytes(start_offset)
        await self.refresh_readiness()
        return available_bytes - 1

    async def _record_range_request(self, start: int, end: int) -> None:
        """Record a requested range and translate it into a seek hint."""
        async with self._lock:
            self.current_range_start = start
            self.current_range_end = end
        await self._notify_piece_manager_for_offset(start)

    async def _notify_piece_manager_for_offset(self, file_offset: int) -> None:
        """Turn a byte offset into a playback/seek hint for the piece manager."""
        global_offset = self.file_offset + file_offset
        piece_length = getattr(self.piece_manager, "piece_length", 0) or 1
        target_piece = global_offset // piece_length
        with contextlib.suppress(Exception):
            await self.piece_manager.handle_streaming_seek(int(target_piece))

    async def _estimate_available_bytes(self, start_offset: int) -> int:
        """Estimate how many contiguous bytes are locally readable."""
        exists = await asyncio.to_thread(self.file_path.exists)
        if not exists:
            return 0
        stat_result = await asyncio.to_thread(self.file_path.stat)
        on_disk_size = min(stat_result.st_size, self.file_size)
        mapper = getattr(self.file_selection_manager, "mapper", None)
        pieces = getattr(self.piece_manager, "pieces", None)
        if mapper is None or pieces is None:
            return on_disk_size

        available_until = start_offset
        for piece_index in self.file_selection_manager.get_pieces_for_file(
            self.file_index
        ):
            overlap = self._file_overlap_for_piece(piece_index)
            if overlap is None:
                continue
            overlap_start, overlap_end = overlap
            if overlap_end <= start_offset:
                continue
            piece = pieces[piece_index]
            if piece.state != PieceState.VERIFIED:
                if overlap_start > start_offset:
                    return min(overlap_start, on_disk_size)
                return min(start_offset, on_disk_size)
            available_until = max(available_until, overlap_end)
        return min(available_until, on_disk_size)

    def _file_overlap_for_piece(self, piece_index: int) -> Optional[tuple[int, int]]:
        """Return the file-local byte overlap for a piece."""
        piece_to_files = getattr(
            self.file_selection_manager.mapper, "piece_to_files", {}
        )
        for mapped_file_index, file_offset, length in piece_to_files.get(
            piece_index, []
        ):
            if mapped_file_index == self.file_index:
                return file_offset, file_offset + length
        return None

    async def _increment_clients(self) -> None:
        """Increment active client count."""
        async with self._lock:
            self.client_count += 1

    async def _decrement_clients(self) -> None:
        """Decrement active client count."""
        async with self._lock:
            self.client_count = max(0, self.client_count - 1)

    async def _enable_streaming_mode(self) -> None:
        """Switch the torrent's piece manager into streaming-aware mode."""
        strategy = getattr(
            getattr(self.piece_manager, "config", None), "strategy", None
        )
        if strategy is None:
            return
        self._previous_streaming_mode = bool(getattr(strategy, "streaming_mode", False))
        self._previous_piece_selection = getattr(
            strategy,
            "piece_selection",
            PieceSelectionStrategy.RAREST_FIRST,
        )
        strategy.streaming_mode = True
        if strategy.piece_selection != PieceSelectionStrategy.SEQUENTIAL:
            strategy.piece_selection = PieceSelectionStrategy.SEQUENTIAL

    async def _restore_piece_selection(self) -> None:
        """Restore piece-selection settings after streaming stops."""
        strategy = getattr(
            getattr(self.piece_manager, "config", None), "strategy", None
        )
        if strategy is None:
            return
        strategy.streaming_mode = self._previous_streaming_mode
        strategy.piece_selection = self._previous_piece_selection

    async def _set_state(self, state: str, error: Optional[str] = None) -> None:
        """Update runtime state and emit an event if it changed."""
        async with self._lock:
            changed = state != self.state or error != self.last_error
            self.state = state
            self.last_error = error
        if not changed:
            return
        if state == "buffering":
            await self._emit_event("media_stream_buffering")
        elif state == "ready":
            await self._emit_event("media_stream_ready")
        elif state == "error":
            await self._emit_event("media_stream_error")

    async def _emit_event(self, event_type: str) -> None:
        """Emit a media runtime event through the shared event bus."""
        await emit_event(
            Event(
                event_type=event_type,
                data=await self.to_status_record(),
            )
        )
