"""Additional tests for storage_service.py to achieve coverage for testable paths."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit]

from ccbt.services.storage_service import StorageOperation, StorageService


@pytest_asyncio.fixture
async def storage_service(tmp_path):
    """Create a StorageService instance for testing."""
    service = StorageService(max_concurrent_operations=2, cache_size_mb=128)
    await service.start()
    yield service
    await service.stop()


class TestStorageServiceCoverage:
    """Test coverage gaps in storage service."""

    @pytest.mark.asyncio
    async def test_stop_timeout_error(self, tmp_path):
        """Test stop() timeout error handling (line 130-131)."""
        service = StorageService(max_concurrent_operations=2)
        await service.start()

        # Create a task that won't complete quickly
        slow_task = asyncio.create_task(asyncio.sleep(10))
        service.operation_tasks = [slow_task]

        # Mock wait_for to raise TimeoutError
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            with patch.object(service.logger, "warning") as mock_warning:
                await service.stop()
                # Should log timeout warning
                mock_warning.assert_called()

        # Clean up
        slow_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await slow_task

    @pytest.mark.asyncio
    async def test_stop_queue_drain_exception(self, tmp_path):
        """Test stop() queue drain exception handling (line 141-144)."""
        service = StorageService(max_concurrent_operations=2)
        await service.start()

        # Mock queue to raise exception
        mock_queue = MagicMock()
        mock_queue.empty = Mock(return_value=False)
        mock_queue.get_nowait = Mock(side_effect=Exception("Queue error"))
        service.operation_queue = mock_queue

        # Should handle exception gracefully
        await service.stop()

    @pytest.mark.asyncio
    async def test_stop_queue_drain_with_items(self, tmp_path):
        """Test stop() queue drain with items (line 145-148)."""
        service = StorageService(max_concurrent_operations=2)
        await service.start()

        # Add operation to queue
        operation = StorageOperation(
            operation_type="write",
            file_path=str(tmp_path / "test.bin"),
            size=1024,
            timestamp=0.0,
            duration=0.0,
            success=False,
        )
        await service.operation_queue.put(operation)

        with patch.object(service.logger, "debug") as mock_debug:
            await service.stop()
            # Should log drained count
            mock_debug.assert_called()

    @pytest.mark.asyncio
    async def test_execute_operation_logging_context_failure(self, storage_service, tmp_path):
        """Test _execute_operation with LoggingContext failure (line 281-284)."""
        # Mock LoggingContext to raise exception on enter
        with patch(
            "ccbt.services.storage_service.LoggingContext",
            side_effect=Exception("Context init failed"),
        ):
            operation = StorageOperation(
                operation_type="write",
                file_path=str(tmp_path / "test.bin"),
                size=0,
                timestamp=0.0,
                duration=0.0,
                success=False,
                data=b"test",
            )

            # Should handle exception gracefully
            await storage_service._execute_operation(operation)

            # Verify metrics updated
            assert storage_service.failed_operations > 0

    @pytest.mark.asyncio
    async def test_write_file_file_info_creation(self, storage_service, tmp_path):
        """Test _write_file file info creation when not tracking (line 371)."""
        test_file = tmp_path / "new_file.bin"
        test_data = b"test data" * 100

        # Write file that doesn't exist in tracking
        result = await storage_service._write_file(str(test_file), test_data)

        assert result is True
        # File info should be created
        assert str(test_file) in storage_service.files

    @pytest.mark.asyncio
    async def test_process_operations_state_check_timeout(self, storage_service):
        """Test _process_operations state check during timeout (line 221-222)."""
        # Set queue as closed to trigger break
        storage_service._queue_closed = True

        # Mock wait_for to timeout
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            # Should break on state check
            try:
                await asyncio.wait_for(storage_service._process_operations(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

    @pytest.mark.asyncio
    async def test_process_operations_queue_exception(self, storage_service):
        """Test _process_operations queue exception handling (line 229-237)."""
        # Mock queue.get() to raise exception
        original_get = storage_service.operation_queue.get

        async def failing_get():
            raise Exception("Queue error")

        storage_service.operation_queue.get = failing_get

        # Should handle exception and continue
        try:
            await asyncio.wait_for(storage_service._process_operations(), timeout=0.5)
        except asyncio.TimeoutError:
            pass

        # Restore
        storage_service.operation_queue.get = original_get
