"""Integration tests for StorageService with DiskIOManager.

Tests the full integration of StorageService writing large files
using DiskIOManager and verifying data integrity.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_storage_service_large_file_integration(tmp_path: Path):
    """Integration test: Write large file and verify integrity."""
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    mgr = ServiceManager()

    await mgr.register_service(svc)
    await mgr.start_service(svc.name)

    # Create a large file (10MB for integration test)
    file_path = tmp_path / "large_integration.bin"
    # Use pattern to verify integrity
    pattern = b"INTEGRATION_TEST_DATA"
    test_data = pattern * (10 * 1024 * 1024 // len(pattern))

    result = await svc.write_file(str(file_path), test_data)
    assert result is True

    # Wait for write to complete
    for _ in range(500):  # Up to 5 seconds
        if svc.active_operations == 0 and svc.total_operations >= 1:
            break
        await asyncio.sleep(0.01)

    # Verify file exists and has correct size
    assert file_path.exists()
    assert file_path.stat().st_size == len(test_data)

    # Verify data integrity by reading back
    with open(file_path, "rb") as f:
        read_data = f.read()

    assert len(read_data) == len(test_data)

    # Verify pattern appears throughout
    assert pattern in read_data[:1024]
    assert pattern in read_data[-1024:]

    # Verify first and last chunks match
    assert read_data[:len(pattern)] == pattern
    assert read_data[-len(pattern):] == pattern

    # Verify DiskIOManager stats show writes
    if svc.disk_io:
        stats = svc.disk_io.stats
        assert stats.get("writes", 0) > 0
        assert stats.get("bytes_written", 0) >= len(test_data)

    await mgr.stop_service(svc.name)


@pytest.mark.asyncio
async def test_storage_service_chunked_writes_verify(tmp_path: Path):
    """Verify that chunked writes actually occur for large files."""
    from ccbt.config.config import get_config
    from ccbt.services.base import ServiceManager
    from ccbt.services.storage_service import StorageService

    svc = StorageService(max_concurrent_operations=2)
    mgr = ServiceManager()

    await mgr.register_service(svc)
    await mgr.start_service(svc.name)

    config = get_config()
    chunk_size = config.disk.write_buffer_kib * 1024

    file_path = tmp_path / "chunked_verify.bin"
    # Create file larger than chunk size to trigger chunking
    test_data = b"CHUNK" * (chunk_size * 2 // 5)  # ~2 chunks

    # Record initial write stats
    initial_writes = svc.disk_io.stats.get("writes", 0) if svc.disk_io else 0

    result = await svc.write_file(str(file_path), test_data)
    assert result is True

    # Wait for write to complete
    for _ in range(500):
        if svc.active_operations == 0 and svc.total_operations >= 1:
            break
        await asyncio.sleep(0.01)

    # Verify file integrity
    assert file_path.exists()
    written_data = file_path.read_bytes()
    assert written_data == test_data

    # Verify chunked writes occurred (multiple write operations)
    if svc.disk_io:
        final_writes = svc.disk_io.stats.get("writes", 0)
        assert final_writes > initial_writes
        # Should have at least 2 write operations for chunked file
        assert (final_writes - initial_writes) >= 1

    await mgr.stop_service(svc.name)

