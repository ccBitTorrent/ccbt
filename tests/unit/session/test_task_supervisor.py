import asyncio
import pytest

from ccbt.session.tasks import TaskSupervisor


@pytest.mark.asyncio
async def test_task_supervisor_create_and_cancel():
    sup = TaskSupervisor()

    async def sleeper():
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise

    task = sup.create_task(sleeper(), name="sleeper")
    assert task in sup.tasks
    sup.cancel_all()
    await sup.wait_all_cancelled(timeout=0.1)
    # After cancellation, the task should be done or cancelled
    assert task.done()


