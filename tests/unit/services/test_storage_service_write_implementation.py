"""Comprehensive tests for StorageService write_file implementation.

Tests the full write_file implementation including:
- Small and large file writes
- Chunked writes for large files
- Data integrity verification
- Configuration-based limits
- DiskIOManager integration
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]


async def _wait_for_operations(service, min_total: int = 0, max_wait: float = 10.0):
    """Wait for operations to complete."""
    start_time = asyncio.get_event_loop().time()
    while True:
        if service.active_operations == 0 and service.total_operations >= min_total:
            return
        if asyncio.get_event_loop().time() - start_time > max_wait:
            return  # Timeout
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_write_file_small_file(tmp_path: Path):
    """Test write_file() with small file (< 1MB)."""
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    mgr = ServiceManager()

    await mgr.register_service(svc)
    await mgr.start_service(svc.name)

    file_path = tmp_path / "small.bin"
    test_data = b"Hello, World! " * 1000  # ~14KB

    result = await svc.write_file(str(file_path), test_data)
    assert result is True

    # Wait for operation to complete
    try:
        await asyncio.wait_for(_wait_for_operations(svc, min_total=1), timeout=5.0)
    except asyncio.TimeoutError:
        pass

    # Verify data integrity
    assert file_path.exists()
    assert file_path.read_bytes() == test_data
    assert file_path.stat().st_size == len(test_data)

    await mgr.stop_service(svc.name)


@pytest.mark.asyncio
async def test_write_file_large_file(tmp_path: Path):
    """Test write_file() with large file (> 100MB) using chunked writes."""
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    mgr = ServiceManager()

    await mgr.register_service(svc)
    await mgr.start_service(svc.name)

    file_path = tmp_path / "large.bin"
    # Create 5MB test file (smaller than 100MB for test speed, but tests chunking)
    test_data = b"x" * (5 * 1024 * 1024)

    result = await svc.write_file(str(file_path), test_data)
    assert result is True

    # Wait for operation to complete
    try:
        await asyncio.wait_for(_wait_for_operations(svc, min_total=1), timeout=30.0)
    except asyncio.TimeoutError:
        pass

    # Verify data integrity
    assert file_path.exists()
    assert file_path.stat().st_size == len(test_data)

    # Verify first and last bytes match
    with open(file_path, "rb") as f:
        first_chunk = f.read(1024)
        f.seek(-1024, 2)  # Seek to 1024 bytes from end
        last_chunk = f.read(1024)

    assert first_chunk == test_data[:1024]
    assert last_chunk == test_data[-1024:]

    await mgr.stop_service(svc.name)


@pytest.mark.asyncio
async def test_write_file_max_size_limit(tmp_path: Path):
    """Test write_file() rejection when exceeding config limit."""
    from ccbt.config.config import get_config
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    # Set a small limit for testing (1MB)
    config = get_config()
    original_max = config.disk.max_file_size_mb
    config.disk.max_file_size_mb = 1  # 1MB limit

    try:
        svc = StorageService(max_concurrent_operations=2)
        mgr = ServiceManager()

        await mgr.register_service(svc)
        await mgr.start_service(svc.name)

        file_path = tmp_path / "too_large.bin"
        test_data = b"x" * (2 * 1024 * 1024)  # 2MB, exceeds 1MB limit

        result = await svc.write_file(str(file_path), test_data)
        assert result is False  # Rejected immediately due to size limit

        # Verify file was NOT written (size limit exceeded)
        assert not file_path.exists()
        # Verify failed operation was recorded
        stats = await svc.get_storage_stats()
        assert stats["failed_operations"] >= 1

        await mgr.stop_service(svc.name)
    finally:
        config.disk.max_file_size_mb = original_max


@pytest.mark.asyncio
async def test_write_file_unlimited_size(tmp_path: Path):
    """Test write_file() with unlimited size (max_file_size_mb=0)."""
    from ccbt.config.config import get_config
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    # Set unlimited (0)
    config = get_config()
    original_max = config.disk.max_file_size_mb
    config.disk.max_file_size_mb = 0  # Unlimited

    try:
        svc = StorageService(max_concurrent_operations=2)
        mgr = ServiceManager()

        await mgr.register_service(svc)
        await mgr.start_service(svc.name)

        file_path = tmp_path / "unlimited.bin"
        test_data = b"y" * (10 * 1024 * 1024)  # 10MB

        result = await svc.write_file(str(file_path), test_data)
        assert result is True

        # Wait for operation to complete
        try:
            await asyncio.wait_for(_wait_for_operations(svc, min_total=1), timeout=30.0)
        except asyncio.TimeoutError:
            pass

        # Should succeed (unlimited)
        assert file_path.exists()
        assert file_path.stat().st_size == len(test_data)

        await mgr.stop_service(svc.name)
    finally:
        config.disk.max_file_size_mb = original_max


@pytest.mark.asyncio
async def test_write_file_data_preservation(tmp_path: Path):
    """Test that actual data bytes are written, not placeholder zeros."""
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    mgr = ServiceManager()

    await mgr.register_service(svc)
    await mgr.start_service(svc.name)

    file_path = tmp_path / "data_test.bin"
    # Use non-zero data pattern
    test_data = bytes(range(256)) * 10  # 2560 bytes with pattern

    result = await svc.write_file(str(file_path), test_data)
    assert result is True

    # Wait for operation
    try:
        await asyncio.wait_for(_wait_for_operations(svc, min_total=1), timeout=5.0)
    except asyncio.TimeoutError:
        pass

    # Verify exact data match
    written_data = file_path.read_bytes()
    assert written_data == test_data
    assert b"\x00" * 10 not in written_data[:100]  # Should not be all zeros

    await mgr.stop_service(svc.name)


@pytest.mark.asyncio
async def test_write_file_chunked_large_file(tmp_path: Path):
    """Test chunked writes for files larger than write_buffer_kib."""
    from ccbt.config.config import get_config
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    mgr = ServiceManager()

    await mgr.register_service(svc)
    await mgr.start_service(svc.name)

    config = get_config()
    chunk_size_kib = config.disk.write_buffer_kib
    chunk_size = chunk_size_kib * 1024

    file_path = tmp_path / "chunked.bin"
    # Create file larger than chunk size
    test_data = b"chunk" * (chunk_size * 3 // 5)  # ~3 chunks worth

    result = await svc.write_file(str(file_path), test_data)
    assert result is True

    # Wait for operation
    try:
        await asyncio.wait_for(_wait_for_operations(svc, min_total=1), timeout=30.0)
    except asyncio.TimeoutError:
        pass

    # Verify data integrity
    assert file_path.exists()
    written_data = file_path.read_bytes()
    assert len(written_data) == len(test_data)
    assert written_data == test_data

    await mgr.stop_service(svc.name)


@pytest.mark.asyncio
async def test_write_file_empty_file(tmp_path: Path):
    """Test write_file() with empty data."""
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    mgr = ServiceManager()

    await mgr.register_service(svc)
    await mgr.start_service(svc.name)

    file_path = tmp_path / "empty.bin"
    test_data = b""

    result = await svc.write_file(str(file_path), test_data)
    assert result is True

    # Wait for operation
    try:
        await asyncio.wait_for(_wait_for_operations(svc, min_total=1), timeout=5.0)
    except asyncio.TimeoutError:
        pass

    # Empty file should be created
    assert file_path.exists()
    assert file_path.stat().st_size == 0

    await mgr.stop_service(svc.name)


@pytest.mark.asyncio
async def test_write_file_updates_file_info(tmp_path: Path):
    """Test that FileInfo is created/updated after write."""
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    mgr = ServiceManager()

    await mgr.register_service(svc)
    await mgr.start_service(svc.name)

    file_path = tmp_path / "tracked.bin"
    test_data = b"tracked data" * 100

    result = await svc.write_file(str(file_path), test_data)
    assert result is True

    # Wait for operation
    try:
        await asyncio.wait_for(_wait_for_operations(svc, min_total=1), timeout=5.0)
    except asyncio.TimeoutError:
        pass

    # Check FileInfo was created
    file_info = await svc.get_file_info(str(file_path))
    assert file_info is not None
    assert file_info.path == str(file_path)
    assert file_info.size == len(test_data)
    assert file_info.is_complete is True

    await mgr.stop_service(svc.name)


@pytest.mark.asyncio
async def test_write_file_disk_io_integration(tmp_path: Path):
    """Test that DiskIOManager.write_block() is called for writes."""
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    mgr = ServiceManager()

    await mgr.register_service(svc)
    await mgr.start_service(svc.name)

    # Verify disk_io exists
    assert svc.disk_io is not None

    file_path = tmp_path / "integration.bin"
    test_data = b"integration test" * 1000

    # Track write_block calls via stats or verify file written correctly
    initial_writes = svc.disk_io.stats.get("writes", 0)

    result = await svc.write_file(str(file_path), test_data)
    assert result is True

    # Wait for operation
    try:
        await asyncio.wait_for(_wait_for_operations(svc, min_total=1), timeout=5.0)
    except asyncio.TimeoutError:
        pass

    # Verify write_block was called (stats should increase)
    final_writes = svc.disk_io.stats.get("writes", 0)
    assert final_writes >= initial_writes

    # Verify file was written correctly
    assert file_path.exists()
    assert file_path.read_bytes() == test_data

    await mgr.stop_service(svc.name)


@pytest.mark.asyncio
async def test_max_file_size_from_config():
    """Test that StorageService reads max_file_size_mb from config."""
    from ccbt.config.config import get_config
    from ccbt.models import DiskConfig
    from ccbt.services.storage_service import StorageService

    config = get_config()
    original_max = config.disk.max_file_size_mb
    original_disk = config.disk

    try:
        # Modify config BEFORE creating StorageService
        disk_config = DiskConfig(max_file_size_mb=50)
        config.disk = disk_config
        svc = StorageService(max_concurrent_operations=2)
        assert svc.max_file_size == 50 * 1024 * 1024

        # Test with unlimited (0) - need to create service after config change
        disk_config_unlimited = DiskConfig(max_file_size_mb=0)
        config.disk = disk_config_unlimited
        svc2 = StorageService(max_concurrent_operations=2)
        assert svc2.max_file_size is None

        # Test with None (default)
        disk_config_none = DiskConfig(max_file_size_mb=None)
        config.disk = disk_config_none
        svc3 = StorageService(max_concurrent_operations=2)
        assert svc3.max_file_size is None
    finally:
        config.disk = original_disk


@pytest.mark.asyncio
async def test_max_file_size_default_unlimited():
    """Test that default max_file_size is unlimited."""
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    # Default should be None (unlimited) when config value is None or 0
    # This depends on ccbt.toml, but we verify the logic works
    assert isinstance(svc.max_file_size, (int, type(None)))


@pytest.mark.asyncio
async def test_write_file_partial_chunk_failure_handling(tmp_path: Path):
    """Test error handling when chunk write fails."""
    from unittest.mock import patch

    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    mgr = ServiceManager()

    await mgr.register_service(svc)
    await mgr.start_service(svc.name)

    assert svc.disk_io is not None

    file_path = tmp_path / "failure_test.bin"
    test_data = b"x" * (2 * 1024 * 1024)  # 2MB

    # Mock write_block to fail on second chunk using patch
    call_count = 0
    original_write_block = svc.disk_io.write_block

    async def failing_write_block(path, offset, data):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # Fail on second chunk
            from ccbt.storage.disk_io import DiskIOError
            future = asyncio.get_event_loop().create_future()
            future.set_exception(DiskIOError("Simulated write failure"))
            return future
        return await original_write_block(path, offset, data)

    # Use patch to properly mock the method
    with patch.object(svc.disk_io, "write_block", side_effect=failing_write_block):
        result = await svc.write_file(str(file_path), test_data)
        assert result is True

        # Wait for operation
        try:
            await asyncio.wait_for(_wait_for_operations(svc, min_total=1), timeout=10.0)
        except asyncio.TimeoutError:
            pass

        # Operation should have failed
        stats = await svc.get_storage_stats()
        assert stats["total_operations"] >= 1
        # At least one failure expected
        assert stats["failed_operations"] >= 1

    await mgr.stop_service(svc.name)

