"""Torrent session lifecycle management.

This module provides lifecycle controllers for managing the start, pause,
resume, and stop sequences of torrent sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ccbt.session.tasks import TaskSupervisor

if TYPE_CHECKING:
    from ccbt.session.models import SessionContext


class LifecycleController:
    """Owns high-level start/pause/resume/stop sequencing for a torrent session."""

    def __init__(
        self, ctx: SessionContext, tasks: TaskSupervisor | None = None
    ) -> None:
        """Initialize the lifecycle controller with session context and optional task supervisor."""
        self._ctx = ctx
        self._tasks = tasks or TaskSupervisor()

    async def on_start(self, session: Any) -> None:
        """Orchestrate session start sequencing.

        Args:
            session: AsyncTorrentSession instance

        """
        # Lifecycle sequencing is managed by session.start() method
        # This hook can be used for pre/post start operations if needed

    async def on_pause(self, _session: Any) -> None:
        """Orchestrate session pause sequencing.

        Args:
            session: AsyncTorrentSession instance

        """
        # Cancel background tasks
        self._tasks.cancel_all()
        await self._tasks.wait_all_cancelled(timeout=5.0)

    async def on_resume(self, _session: Any) -> None:
        """Orchestrate session resume sequencing.

        Args:
            session: AsyncTorrentSession instance

        """
        # Cancel any existing background tasks before resuming
        self._tasks.cancel_all()
        await self._tasks.wait_all_cancelled(timeout=5.0)

    async def on_stop(self, _session: Any) -> None:
        """Orchestrate session stop sequencing.

        Args:
            session: AsyncTorrentSession instance

        """
        # Cancel background tasks owned by controllers if they use the shared supervisor
        self._tasks.cancel_all()
        await self._tasks.wait_all_cancelled(timeout=5.0)
