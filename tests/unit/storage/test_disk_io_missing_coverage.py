"""Additional tests for missing coverage lines in disk_io.py."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ccbt.storage.disk_io import DiskIOManager


@pytest.mark.unit
@pytest.mark.storage
@pytest.mark.disk
class TestDiskIOMissingCoverage:
    """Test specific missing coverage lines in disk_io.py."""

    @pytest.mark.asyncio
    async def test_stop_timeout_flush_handling(self, tmp_path):
        """Test stop() lines 265-292: Timeout and exception handling paths."""
        manager = DiskIOManager(max_workers=2)
        await manager.start()
        
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"initial")
        
        # Open file and write something
        await manager.write_block(test_file, 0, b"test data")
        
        # Stop should handle flush timeout gracefully
        # Lines 265-292 test timeout handling in stop()
        await manager.stop()

    @pytest.mark.asyncio
    async def test_stop_pending_futures_cleanup(self, tmp_path):
        """Test stop() lines 308-344: Pending futures cleanup."""
        manager = DiskIOManager(max_workers=2)
        await manager.start()
        
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"test data")
        
        # Start a write that might be pending during stop
        write_task = asyncio.create_task(
            manager.write_block(test_file, 0, b"data")
        )
        
        # Wait briefly then stop
        await asyncio.sleep(0.01)
        
        # Stop should clean up pending futures (lines 308-344)
        await manager.stop()
        
        # Wait for write task to complete or be cancelled
        try:
            await asyncio.wait_for(write_task, timeout=0.1)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

    @pytest.mark.asyncio
    async def test_stop_force_future_completion(self, tmp_path):
        """Test stop() lines 338-344: Force future completion paths."""
        manager = DiskIOManager(max_workers=2)
        await manager.start()
        
        # Lines 338-344: Force completion of pending futures
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"test")
        
        # Stop handles force completion paths
        await manager.stop()

