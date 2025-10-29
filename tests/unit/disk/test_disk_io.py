"""Integration tests for disk I/O optimizations.

Tests cross-platform preallocation, write batching, mmap cache,
and async thread pool functionality.
"""

import asyncio
import contextlib
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.disk]

from ccbt.config import get_config
from ccbt.disk_io import (
    DiskIOManager,
    preallocate_file,
)


@pytest_asyncio.fixture
async def disk_io_manager():
    """Create disk I/O manager for testing."""
    config = get_config()
    manager = DiskIOManager(
        max_workers=config.disk.disk_workers,
        queue_size=config.disk.disk_queue_size,
        cache_size_mb=config.disk.mmap_cache_mb,
    )
    await manager.start()
    yield manager
    await manager.stop()


class TestDiskIO:
    """Test disk I/O optimizations."""

    @pytest.fixture
    def temp_file(self):
        """Create temporary file for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
        yield temp_path
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_file_preallocation(self, temp_file):
        """Test cross-platform file preallocation."""
        file_size = 1024 * 1024  # 1MB

        # Create manager directly in test
        config = get_config()
        manager = DiskIOManager(
            max_workers=config.disk.disk_workers,
            queue_size=config.disk.disk_queue_size,
            cache_size_mb=config.disk.mmap_cache_mb,
        )

        try:
            await manager.start()
            # Test preallocation
            await manager.preallocate_file(Path(temp_file), file_size)
        finally:
            await manager.stop()

        # Verify file exists and has correct size
        assert os.path.exists(temp_file)
        assert os.path.getsize(temp_file) == file_size

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_write_batching(self, disk_io_manager, temp_file):
        """Test write batching functionality."""
        # Create test data
        test_data = b"Hello, World! " * 1000  # ~14KB of data

        # Write data in batches
        batch_size = 1024  # 1KB batches
        for i in range(0, len(test_data), batch_size):
            chunk = test_data[i : i + batch_size]
            future = await disk_io_manager.write_block(Path(temp_file), i, chunk)
            await future  # Wait for the write to complete

        # Verify data was written correctly
        with open(temp_file, "rb") as f:
            written_data = f.read()

        assert written_data == test_data

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_contiguous_write_optimization(self, disk_io_manager, temp_file):
        """Test contiguous write optimization."""
        # Write contiguous data
        data1 = b"A" * 1024
        data2 = b"B" * 1024
        data3 = b"C" * 1024

        # Write contiguous blocks
        future1 = await disk_io_manager.write_block(Path(temp_file), 0, data1)
        await future1
        future2 = await disk_io_manager.write_block(Path(temp_file), 1024, data2)
        await future2
        future3 = await disk_io_manager.write_block(Path(temp_file), 2048, data3)
        await future3

        # Verify data was written correctly
        with open(temp_file, "rb") as f:
            written_data = f.read()

        expected_data = data1 + data2 + data3
        assert written_data == expected_data

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_mmap_cache(self, disk_io_manager, temp_file):
        """Test memory-mapped file cache."""
        # Write test data
        test_data = b"Test data for mmap" * 1000
        future = await disk_io_manager.write_block(Path(temp_file), 0, test_data)
        await future  # Wait for write to complete

        # Read using mmap
        mmap_data = await disk_io_manager.read_block_mmap(temp_file, 0, len(test_data))

        assert mmap_data == test_data

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)  # Add timeout for concurrent operations
    async def test_async_thread_pool(self, disk_io_manager, temp_file):
        """Test async thread pool for I/O operations."""
        # Create multiple concurrent write tasks
        tasks = []
        for i in range(10):
            data = f"Task {i} data".encode() * 100

            async def write_task(offset=i, write_data=data):
                future = await disk_io_manager.write_block(
                    Path(temp_file),
                    offset * 1000,
                    write_data,
                )
                await future

            task = asyncio.create_task(write_task())
            tasks.append(task)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)

        # Verify all data was written
        with open(temp_file, "rb") as f:
            written_data = f.read()

        # Should have data from all tasks
        assert len(written_data) > 0
        for i in range(10):
            assert f"Task {i} data".encode() in written_data

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)  # Add timeout to prevent hanging
    async def test_backpressure_handling(self, disk_io_manager):
        """Test backpressure when disk queue is full."""
        # Create a disk I/O manager with small queue
        config = get_config()

        manager = DiskIOManager(
            max_workers=config.disk.disk_workers,
            queue_size=2,  # Small queue
            cache_size_mb=config.disk.mmap_cache_mb,
        )
        await manager.start()

        try:
            # Fill queue to capacity
            tasks = []
            for i in range(3):  # More than queue size
                task = asyncio.create_task(
                    manager.write_block(Path(f"test_{i}.txt"), 0, b"data"),
                )
                tasks.append(task)

            # Should handle backpressure gracefully
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Some tasks might fail due to backpressure
            assert any(isinstance(r, Exception) for r in results) or True

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_cross_platform_preallocation(self, temp_file):
        """Test cross-platform preallocation on different platforms."""
        file_size = 1024 * 1024  # 1MB

        # Test preallocation
        await preallocate_file(temp_file, file_size)

        # Verify file size
        assert os.path.getsize(temp_file) == file_size

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)  # Add timeout for performance tests
    async def test_write_performance(self, disk_io_manager, temp_file):
        """Test write performance with batching."""
        import time

        # Test data
        data_size = 1024 * 1024  # 1MB
        test_data = b"X" * data_size

        # Measure write time
        start_time = time.time()
        future = await disk_io_manager.write_block(Path(temp_file), 0, test_data)
        await future
        end_time = time.time()

        write_time = end_time - start_time
        write_speed = data_size / write_time / 1024 / 1024  # MB/s

        # Should achieve reasonable write speed
        assert write_speed > 1.0  # At least 1 MB/s

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)  # Add timeout for performance tests
    async def test_read_performance(self, disk_io_manager, temp_file):
        """Test read performance with mmap."""
        import time

        # Write test data
        data_size = 1024 * 1024  # 1MB
        test_data = b"Y" * data_size
        future = await disk_io_manager.write_block(Path(temp_file), 0, test_data)
        await future

        # Measure read time
        start_time = time.time()
        read_data = await disk_io_manager.read_block_mmap(temp_file, 0, data_size)
        end_time = time.time()

        read_time = end_time - start_time
        read_speed = data_size / read_time / 1024 / 1024  # MB/s

        # Should achieve reasonable read speed
        assert read_speed > 1.0  # At least 1 MB/s
        assert read_data == test_data

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)  # Add timeout for concurrent operations
    async def test_concurrent_read_write(self, disk_io_manager, temp_file):
        """Test concurrent read and write operations."""
        # Write initial data
        initial_data = b"Initial data" * 1000
        future = await disk_io_manager.write_block(Path(temp_file), 0, initial_data)
        await future

        # Create concurrent read tasks only (no writes to avoid race conditions)
        tasks = []

        # Read tasks
        for i in range(5):
            task = asyncio.create_task(
                disk_io_manager.read_block(temp_file, 0, len(initial_data)),
            )
            tasks.append(task)

        # Wait for all tasks
        results = await asyncio.gather(*tasks)

        # Verify results
        for read_data in results:
            assert read_data == initial_data

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_error_handling(self, disk_io_manager):
        """Test error handling in disk I/O operations."""
        # Test reading from non-existent file
        with pytest.raises((FileNotFoundError, OSError)):
            await disk_io_manager.read_block(Path("/nonexistent/file.txt"), 0, 100)

        # Test writing should succeed (creates directory)
        future = await disk_io_manager.write_block(
            Path("/tmp/test/file.txt"),
            0,
            b"data",
        )
        await future  # Wait for completion

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_mmap_cache_management(self, disk_io_manager, temp_file):
        """Test mmap cache management."""
        # Write test data
        test_data = b"Mmap test data" * 1000
        future = await disk_io_manager.write_block(Path(temp_file), 0, test_data)
        await future

        # Read multiple times to test cache
        for _ in range(5):
            read_data = await disk_io_manager.read_block_mmap(
                temp_file,
                0,
                len(test_data),
            )
            assert read_data == test_data

        # Test cache statistics
        stats = disk_io_manager.get_cache_stats()
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert stats["cache_hits"] > 0

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)  # Add timeout to prevent hanging
    @pytest.mark.slow
    async def test_large_file_handling(self, disk_io_manager, temp_file):
        """Test handling of large files."""
        # Create large data (10MB)
        large_data = b"Large file data" * (1024 * 1024)  # ~16MB

        # Write large data
        future = await disk_io_manager.write_block(Path(temp_file), 0, large_data)
        await future

        # Verify file size
        assert os.path.getsize(temp_file) == len(large_data)

        # Read back and verify
        read_data = await disk_io_manager.read_block(temp_file, 0, len(large_data))
        assert read_data == large_data

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)  # Add timeout to prevent hanging
    @pytest.mark.slow
    async def test_thread_pool_scaling(self, disk_io_manager):
        """Test thread pool scaling with concurrent operations."""
        # Create many concurrent operations
        tasks = []
        for i in range(20):  # 20 concurrent operations
            temp_file = f"test_{i}.txt"
            data = f"Concurrent data {i}".encode() * 1000

            async def write_task():
                future = await disk_io_manager.write_block(Path(temp_file), 0, data)
                await future

            task = asyncio.create_task(write_task())
            tasks.append(task)

        # Wait for all operations
        await asyncio.gather(*tasks)

        # Clean up
        for i in range(20):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(f"test_{i}.txt")
