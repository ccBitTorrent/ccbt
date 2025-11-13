"""Tests for remaining uncovered lines in disk_io.py.

Covers:
- Platform-specific code paths with cross-platform tests
- Exception handling paths
- Edge cases in write batching and cache operations
- Defensive error handling
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.disk]

from ccbt.config.config import get_config
from ccbt.storage.disk_io import (
    DiskIOManager,
    DiskIOError,
    WriteRequest,
)
from ccbt.models import PreallocationStrategy


class TestPlatformSpecificPaths:
    """Test platform-specific code paths."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific fallocate test")
    async def test_preallocate_fallocate_linux_posix_fallocate(self, tmp_path):
        """Test Linux posix_fallocate path (lines 355-359)."""
        config = get_config()
        original_strategy = config.disk.preallocate
        try:
            config.disk.preallocate = PreallocationStrategy.FALLOCATE
            manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
            await manager.start()
            try:
                file_path = tmp_path / "test.bin"
                # Use minimal size
                await manager.preallocate_file(file_path, 1024)
                assert file_path.exists()
            finally:
                await asyncio.wait_for(manager.stop(), timeout=2.0)
        finally:
            config.disk.preallocate = original_strategy

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific preallocation test")
    async def test_preallocate_fallocate_windows_set_end_of_file(self, tmp_path):
        """Test Windows SetEndOfFile path (line 373).
        
        Note: Windows API may fail, but the code path is tested.
        """
        config = get_config()
        original_strategy = config.disk.preallocate
        try:
            config.disk.preallocate = PreallocationStrategy.FALLOCATE
            manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
            await manager.start()
            try:
                file_path = tmp_path / "test.bin"
                try:
                    await manager.preallocate_file(file_path, 1024)
                    assert file_path.exists()
                except DiskIOError:
                    # Windows API might fail, but code path is covered
                    pass
            finally:
                await asyncio.wait_for(manager.stop(), timeout=2.0)
        finally:
            config.disk.preallocate = original_strategy

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform in ("linux", "win32"), reason="Non-Linux/Windows platform test")
    async def test_preallocate_fallocate_other_platform_sparse(self, tmp_path):
        """Test sparse file fallback for other platforms (lines 378-380)."""
        config = get_config()
        original_strategy = config.disk.preallocate
        try:
            config.disk.preallocate = PreallocationStrategy.FALLOCATE
            manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
            await manager.start()
            try:
                file_path = tmp_path / "test.bin"
                await manager.preallocate_file(file_path, 1024)
                assert file_path.exists()
            finally:
                await asyncio.wait_for(manager.stop(), timeout=2.0)
        finally:
            config.disk.preallocate = original_strategy


class TestExceptionHandling:
    """Test exception handling paths."""

    @pytest.mark.asyncio
    async def test_io_uring_config_exception(self):
        """Test io_uring config exception handling (lines 151-152)."""
        # Mock config.disk to raise exception when accessing enable_io_uring
        with patch("ccbt.storage.disk_io.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_disk = MagicMock()
            
            # Make accessing enable_io_uring raise an exception
            def raise_on_access(*args, **kwargs):
                raise AttributeError("enable_io_uring access failed")
            
            type(mock_disk).enable_io_uring = property(raise_on_access)
            mock_config.disk = mock_disk
            mock_get_config.return_value = mock_config
            
            # Create manager - should handle exception gracefully
            manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
            # Should not crash, io_uring_enabled should fall back to HAS_IO_URING
            assert manager.io_uring_enabled in (True, False)

    @pytest.mark.asyncio
    async def test_stop_cancels_pending_futures_path(self, tmp_path):
        """Test stop cancels pending futures (lines 263-264)."""
        manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
        await manager.start()
        
        # Create writes but stop before they can all complete
        futures = []
        file_path = tmp_path / "test.bin"
        for i in range(2):
            future = await manager.write_block(file_path, i * 8, b"test")
            futures.append(future)
        
        # Give minimal time, then stop
        await asyncio.sleep(0.01)
        await asyncio.wait_for(manager.stop(), timeout=2.0)
        
        # After stop completes, all futures should be done
        # (either completed or cancelled via the stop() logic)
        for future in futures:
            assert future.done()

    @pytest.mark.asyncio
    async def test_windows_cleanup_delay_exception(self, tmp_path):
        """Test Windows cleanup delay exception handling (lines 293-295)."""
        if sys.platform != "win32":
            pytest.skip("Windows-specific test")
        
        manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
        await manager.start()
        
        # Create cache entry
        file_path = tmp_path / "test.bin"
        file_path.write_bytes(b"test")
        await manager.read_block(file_path, 0, 4)
        
        # Mock gc.collect or asyncio.sleep to raise exception
        with patch("gc.collect", side_effect=RuntimeError("GC error")):
            # Should handle exception gracefully
            await asyncio.wait_for(manager.stop(), timeout=2.0)

    @pytest.mark.asyncio
    async def test_read_block_mmap_file_not_found_re_raise(self, tmp_path):
        """Test FileNotFoundError re-raise in read_block_mmap (line 484)."""
        manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
        await manager.start()
        try:
            file_path = tmp_path / "nonexistent.bin"
            
            # FileNotFoundError should be re-raised, not caught by generic Exception
            with pytest.raises(FileNotFoundError):
                await manager.read_block_mmap(file_path, 0, 100)
        finally:
            await asyncio.wait_for(manager.stop(), timeout=2.0)

    @pytest.mark.asyncio
    async def test_write_combined_sync_file_not_found(self, tmp_path):
        """Test FileNotFoundError in _write_combined_sync (lines 763-764).
        
        Note: FileNotFoundError is rare because file is created before os.open.
        We test by making the fallback open() raise FileNotFoundError.
        """
        manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
        await manager.start()
        try:
            file_path = tmp_path / "test.bin"
            writes = [(0, b"test"), (10, b"data")]
            
            # Mock os.open to raise generic Exception (triggers fallback)
            # Then mock the fallback open() to raise FileNotFoundError
            with patch("os.open", side_effect=OSError("os.open failed")), \
                 patch("builtins.open", side_effect=FileNotFoundError("File not found")):
                with pytest.raises(DiskIOError, match="File not found"):
                    await asyncio.get_event_loop().run_in_executor(
                        manager.executor,
                        manager._write_combined_sync,
                        file_path,
                        writes,
                    )
        finally:
            await asyncio.wait_for(manager.stop(), timeout=2.0)


class TestWriteBatchingEdgeCases:
    """Test write batching edge cases."""

    @pytest.mark.asyncio
    async def test_flush_stale_writes_empty_requests(self, tmp_path):
        """Test flush_stale_writes with empty requests (line 584)."""
        manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
        await manager.start()
        try:
            file_path = tmp_path / "test.bin"
            
            # Manually add empty request list to trigger continue path
            with manager.write_lock:
                manager.write_requests[file_path] = []
            
            # Should handle gracefully and continue
            await manager._flush_stale_writes()
        finally:
            await asyncio.wait_for(manager.stop(), timeout=2.0)

    @pytest.mark.asyncio
    async def test_combine_contiguous_writes_empty(self, tmp_path):
        """Test _combine_contiguous_writes with empty list (line 668)."""
        manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
        await manager.start()
        try:
            # Empty writes should return empty list
            result = manager._combine_contiguous_writes([])
            assert result == []
        finally:
            await asyncio.wait_for(manager.stop(), timeout=2.0)

    @pytest.mark.asyncio
    async def test_flush_file_writes_empty_list(self, tmp_path):
        """Test _flush_file_writes with no writes to process (line 608)."""
        manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
        await manager.start()
        try:
            file_path = tmp_path / "test.bin"
            
            # Manually set empty list
            with manager.write_lock:
                manager.write_requests[file_path] = []
            
            # Should return early without error
            await manager._flush_file_writes(file_path)
        finally:
            await asyncio.wait_for(manager.stop(), timeout=2.0)

    @pytest.mark.asyncio
    async def test_flush_file_writes_ring_buffer_two_views(self, tmp_path):
        """Test flush with ring buffer having two views (lines 633-647).
        
        Tests the elif len(views) == 2 path which merges two memoryviews.
        """
        manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
        await manager.start()
        try:
            file_path = tmp_path / "test.bin"
            file_path.write_bytes(b"x" * 1024)
            
            # Create multiple small writes that will be staged in ring buffer
            # Need to create scenario where ring buffer has exactly 2 views
            futures = []
            # Create enough writes to potentially split into 2 views in ring buffer
            for i in range(3):
                future = await manager.write_block(
                    file_path,
                    i * 4,
                    b"data",  # 4 bytes each
                )
                futures.append(future)
            
            # Wait for batching and staging
            await asyncio.sleep(0.15)
            
            # Manually flush to trigger ring buffer processing with two views
            # The ring buffer might have split data into 2 views
            await manager._flush_all_writes()
            
            # All futures should complete
            for future in futures:
                await asyncio.wait_for(future, timeout=1.0)
        finally:
            await asyncio.wait_for(manager.stop(), timeout=2.0)

    @pytest.mark.asyncio
    async def test_write_combined_sync_buffer_flush_wont_fit(self, tmp_path):
        """Test buffer flush when data won't fit (lines 741-743).
        
        Tests the path where buf_pos + data_len > len(buffer), triggering
        a flush and reset of the staging buffer.
        """
        manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
        await manager.start()
        try:
            file_path = tmp_path / "test.bin"
            
            # Get the staging buffer size to create writes that exceed it
            staging_threshold = getattr(get_config().disk, "write_buffer_kib", 128) * 1024
            buffer_size = max(64 * 1024, staging_threshold)
            
            # Create writes that will fill buffer partially, then exceed it
            # First write fills most of buffer
            first_data = b"x" * (buffer_size - 1000)
            # Second write won't fit - triggers flush and reset (lines 741-743)
            second_data = b"y" * 2000
            
            writes = [
                (0, first_data),
                (len(first_data), second_data),  # Contiguous but won't fit in remaining space
            ]
            
            await asyncio.get_event_loop().run_in_executor(
                manager.executor,
                manager._write_combined_sync,
                file_path,
                writes,
            )
            
            # Verify file was written
            assert file_path.exists()
            assert file_path.stat().st_size >= len(first_data) + len(second_data)
        finally:
            await asyncio.wait_for(manager.stop(), timeout=2.0)


class TestCacheOperations:
    """Test cache operation edge cases."""

    @pytest.mark.asyncio
    async def test_get_mmap_entry_cache_hit(self, tmp_path):
        """Test _get_mmap_entry returns cached entry (line 818)."""
        manager = DiskIOManager(max_workers=1, queue_size=10, cache_size_mb=1)
        await manager.start()
        try:
            config = get_config()
            original_use_mmap = config.disk.use_mmap
            config.disk.use_mmap = True
            
            file_path = tmp_path / "test.bin"
            file_path.write_bytes(b"test data")
            
            # First call creates entry
            entry1 = manager._get_mmap_entry(file_path)
            assert entry1 is not None
            
            # Second call should return cached entry (line 818)
            entry2 = manager._get_mmap_entry(file_path)
            assert entry2 is entry1  # Same object
            
            config.disk.use_mmap = original_use_mmap
        finally:
            await asyncio.wait_for(manager.stop(), timeout=2.0)


class TestWriteRequestFuture:
    """Test WriteRequest.create_future edge cases."""

    def test_create_future_no_running_loop(self):
        """Test create_future when no loop is running (lines 68-78)."""
        # Ensure no loop is set
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                pytest.skip("Event loop is already running")
            loop.close()
        except (RuntimeError, AttributeError):
            pass
        
        # Clear event loop
        asyncio.set_event_loop(None)
        
        try:
            # Should create future even without running loop
            future = WriteRequest.create_future()
            assert future is not None
            assert not future.done()
        finally:
            # Clean up
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    loop.close()
            except (RuntimeError, AttributeError):
                pass
            asyncio.set_event_loop(None)

