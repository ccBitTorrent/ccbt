"""Media command executor."""

from __future__ import annotations

from typing import Any, Optional

from ccbt.executor.base import CommandExecutor, CommandResult


class MediaExecutor(CommandExecutor):
    """Executor for media streaming commands."""

    async def execute(
        self,
        command: str,
        *_args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute media command."""
        if command == "media.start":
            return await self._start_stream(**kwargs)
        if command == "media.stop":
            return await self._stop_stream(**kwargs)
        if command == "media.status":
            return await self._get_status(**kwargs)
        if command == "media.launch_vlc":
            return await self._launch_player(**kwargs)
        return CommandResult(success=False, error=f"Unknown media command: {command}")

    async def _start_stream(
        self,
        info_hash: str,
        file_index: int,
        port: Optional[int] = None,
    ) -> CommandResult:
        """Start a stream for the selected torrent file."""
        try:
            response = await self.adapter.start_media_stream(
                info_hash,
                file_index=file_index,
                port=port,
            )
            return CommandResult(success=True, data=response.model_dump())
        except Exception as exc:
            return CommandResult(success=False, error=str(exc))

    async def _stop_stream(self, stream_id: str) -> CommandResult:
        """Stop an active stream."""
        try:
            stopped = await self.adapter.stop_media_stream(stream_id)
            return CommandResult(success=stopped, data={"stopped": stopped})
        except Exception as exc:
            return CommandResult(success=False, error=str(exc))

    async def _get_status(
        self,
        stream_id: Optional[str] = None,
        info_hash: Optional[str] = None,
    ) -> CommandResult:
        """Get media stream status."""
        try:
            status = await self.adapter.get_media_stream_status(
                stream_id=stream_id,
                info_hash=info_hash,
            )
            return CommandResult(
                success=status is not None,
                data={"status": status.model_dump() if status is not None else None},
                error=None if status is not None else "Media stream not found",
            )
        except Exception as exc:
            return CommandResult(success=False, error=str(exc))

    async def _launch_player(self, stream_url: str) -> CommandResult:
        """Launch the local media player."""
        try:
            result = await self.adapter.launch_media_player(stream_url)
            return CommandResult(
                success=bool(result.get("launched", False)),
                data=result,
                error=result.get("error"),
            )
        except Exception as exc:
            return CommandResult(success=False, error=str(exc))
