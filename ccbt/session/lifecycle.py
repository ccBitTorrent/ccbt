from __future__ import annotations

from ccbt.session.models import SessionContext
from ccbt.session.tasks import TaskSupervisor


class LifecycleController:
    """Owns high-level start/pause/resume/stop sequencing for a torrent session."""

    def __init__(
        self, ctx: SessionContext, tasks: TaskSupervisor | None = None
    ) -> None:
        self._ctx = ctx
        self._tasks = tasks or TaskSupervisor()

    # Placeholder: sequencing can be expanded as we extract logic from session.py
    async def on_start(self) -> None:  # pragma: no cover - orchestrator entrypoint
        # No-op here; extraction will migrate steps into this controller.
        return

    async def on_pause(self) -> None:  # pragma: no cover
        return

    async def on_resume(self) -> None:  # pragma: no cover
        return

    async def on_stop(self) -> None:  # pragma: no cover
        # Cancel background tasks owned by controllers if they use the shared supervisor.
        self._tasks.cancel_all()
