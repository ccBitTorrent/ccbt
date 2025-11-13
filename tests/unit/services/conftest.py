"""Pytest fixtures for service tests."""

from __future__ import annotations

import asyncio

import pytest

from ccbt.services.base import ServiceManager


@pytest.fixture
async def service_manager():
    """Provide a ServiceManager that auto-cleans up services after test."""
    mgr = ServiceManager()
    yield mgr
    
    # Cleanup: stop all services
    try:
        await mgr.shutdown()
    except Exception:
        pass  # Best effort cleanup


@pytest.fixture
def verify_tasks_cancelled():
    """Verify that tasks are cancelled after test."""
    async def _verify(service, timeout: float = 2.0):
        """Verify all background tasks are cancelled/done."""
        if hasattr(service, "operation_tasks"):
            try:
                await asyncio.wait_for(
                    asyncio.gather(*service.operation_tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                pass  # Some tasks may still be cancelling
            # Verify tasks are done or cancelled
            for task in service.operation_tasks:
                assert task.done() or task.cancelled(), "Task not cancelled"
        
    return _verify

