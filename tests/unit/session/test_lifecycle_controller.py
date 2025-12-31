"""Unit tests for LifecycleController."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.session.lifecycle import LifecycleController
from ccbt.session.models import SessionContext
from ccbt.session.tasks import TaskSupervisor


class TestLifecycleController:
    """Test LifecycleController functionality."""

    @pytest.fixture
    def ctx(self):
        """Create a mock session context."""
        return SessionContext(
            config=Mock(),
            torrent_data={"info_hash": b"x" * 20},
            output_dir=Mock(),
        )

    @pytest.fixture
    def tasks(self):
        """Create a TaskSupervisor instance."""
        return TaskSupervisor()

    @pytest.fixture
    def controller(self, ctx, tasks):
        """Create LifecycleController instance."""
        return LifecycleController(ctx, tasks)

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        session = Mock()
        return session

    @pytest.mark.asyncio
    async def test_on_start(self, controller, mock_session):
        """Test on_start hook."""
        # on_start is currently a no-op, just verify it doesn't raise
        await controller.on_start(mock_session)

    @pytest.mark.asyncio
    async def test_on_pause_cancels_tasks(self, controller, mock_session, tasks):
        """Test on_pause cancels all tasks."""
        # Create a task
        async def sleeper():
            await asyncio.sleep(10)

        task = tasks.create_task(sleeper(), name="test_task")
        assert len(tasks.tasks) == 1

        # Call on_pause
        await controller.on_pause(mock_session)

        # Task should be cancelled
        assert task.done() or task.cancelled()

    @pytest.mark.asyncio
    async def test_on_resume_cancels_tasks(self, controller, mock_session, tasks):
        """Test on_resume cancels all tasks."""
        # Create a task
        async def sleeper():
            await asyncio.sleep(10)

        task = tasks.create_task(sleeper(), name="test_task")
        assert len(tasks.tasks) == 1

        # Call on_resume
        await controller.on_resume(mock_session)

        # Task should be cancelled
        assert task.done() or task.cancelled()

    @pytest.mark.asyncio
    async def test_on_stop_cancels_tasks(self, controller, mock_session, tasks):
        """Test on_stop cancels all tasks."""
        # Create a task
        async def sleeper():
            await asyncio.sleep(10)

        task = tasks.create_task(sleeper(), name="test_task")
        assert len(tasks.tasks) == 1

        # Call on_stop
        await controller.on_stop(mock_session)

        # Task should be cancelled
        assert task.done() or task.cancelled()

    def test_init_without_tasks(self, ctx):
        """Test initialization without TaskSupervisor."""
        controller = LifecycleController(ctx, None)
        assert controller._tasks is not None
        assert isinstance(controller._tasks, TaskSupervisor)


































































