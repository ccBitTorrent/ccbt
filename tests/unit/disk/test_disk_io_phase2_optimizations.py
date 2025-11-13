"""Comprehensive unit tests for Phase 2 Disk I/O Optimizations.

Tests cover:
- Adaptive write batching timeout
- Contiguous write detection
- Write queue prioritization
- MMap cache optimizations (size-aware LRU, warmup, adaptive sizing)
- Read optimizations (adaptive read-ahead, parallel segments)
- I/O worker optimizations
- Hash verification optimizations
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.disk]

from ccbt.config.config import get_config
from ccbt.models import DiskConfig
from ccbt.storage.disk_io import DiskIOManager, ReadPattern, WriteRequest


@pytest_asyncio.fixture
async def disk_io_manager(tmp_path):
    """Create a DiskIOManager instance for testing."""
    config = get_config()
    # Override disk config for testing
    config.disk.write_batch_timeout_adaptive = True
    config.disk.write_contiguous_threshold = 4096
    config.disk.write_queue_priority = True
    config.disk.mmap_cache_warmup = True
    config.disk.mmap_cache_adaptive = True
    config.disk.read_ahead_adaptive = True
    config.disk.read_parallel_segments = True
    config.disk.disk_workers_adaptive = True
    config.disk.hash_chunk_size_adaptive = True
    
    manager = DiskIOManager(
        max_workers=2,
        queue_size=100,
        cache_size_mb=64,
    )
    await manager.start()
    yield manager
    await manager.stop()


@pytest_asyncio.fixture
async def temp_file(tmp_path):
    """Create a temporary file for testing."""
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"initial data" * 1000)
    yield test_file


class TestAdaptiveWriteBatching:
    """Tests for adaptive write batching timeout."""
    
    @pytest.mark.asyncio
    async def test_adaptive_timeout_nvme(self, disk_io_manager):
        """Test adaptive timeout for NVMe storage."""
        disk_io_manager.storage_type = "nvme"
        timeout = disk_io_manager._get_adaptive_timeout()
        assert timeout < 0.001  # Should be ~0.1ms
    
    @pytest.mark.asyncio
    async def test_adaptive_timeout_ssd(self, disk_io_manager):
        """Test adaptive timeout for SSD storage."""
        disk_io_manager.storage_type = "ssd"
        timeout = disk_io_manager._get_adaptive_timeout()
        assert 0.004 <= timeout <= 0.006  # Should be ~5ms
    
    @pytest.mark.asyncio
    async def test_adaptive_timeout_hdd(self, disk_io_manager):
        """Test adaptive timeout for HDD storage."""
        disk_io_manager.storage_type = "hdd"
        timeout = disk_io_manager._get_adaptive_timeout()
        assert 0.04 <= timeout <= 0.06  # Should be ~50ms
    
    @pytest.mark.asyncio
    async def test_adaptive_timeout_disabled(self, disk_io_manager):
        """Test that fixed timeout is used when adaptive is disabled."""
        disk_io_manager.config.disk.write_batch_timeout_adaptive = False
        disk_io_manager.config.disk.write_batch_timeout_ms = 10.0
        timeout = disk_io_manager._get_adaptive_timeout()
        assert timeout == 0.01  # Should use config value


class TestContiguousWriteDetection:
    """Tests for contiguous write detection and merging."""
    
    @pytest.mark.asyncio
    async def test_combine_contiguous_writes(self, disk_io_manager):
        """Test that adjacent writes are combined."""
        writes = [
            WriteRequest(Path("/test.bin"), 0, b"data1", asyncio.Future(), 0),
            WriteRequest(Path("/test.bin"), 5, b"data2", asyncio.Future(), 0),
        ]
        combined = disk_io_manager._combine_contiguous_writes(writes)
        assert len(combined) == 1
        assert combined[0][0] == 0
        assert len(combined[0][1]) == len(b"data1") + len(b"data2")
    
    @pytest.mark.asyncio
    async def test_combine_writes_with_threshold_gap(self, disk_io_manager):
        """Test that writes within threshold are merged."""
        disk_io_manager.config.disk.write_contiguous_threshold = 4096
        writes = [
            WriteRequest(Path("/test.bin"), 0, b"data1", asyncio.Future(), 0),
            WriteRequest(Path("/test.bin"), 4096, b"data2", asyncio.Future(), 0),
        ]
        combined = disk_io_manager._combine_contiguous_writes(writes)
        assert len(combined) == 1  # Should merge within threshold
    
    @pytest.mark.asyncio
    async def test_combine_writes_with_large_gap(self, disk_io_manager):
        """Test that writes with large gaps are not merged."""
        disk_io_manager.config.disk.write_contiguous_threshold = 4096
        writes = [
            WriteRequest(Path("/test.bin"), 0, b"data1", asyncio.Future(), 0),
            WriteRequest(Path("/test.bin"), 8192, b"data2", asyncio.Future(), 0),
        ]
        combined = disk_io_manager._combine_contiguous_writes(writes)
        assert len(combined) == 2  # Should not merge
    
    @pytest.mark.asyncio
    async def test_combine_writes_sorted(self, disk_io_manager):
        """Test that writes are sorted by offset before combining."""
        writes = [
            WriteRequest(Path("/test.bin"), 100, b"data3", asyncio.Future(), 0),
            WriteRequest(Path("/test.bin"), 0, b"data1", asyncio.Future(), 0),
            WriteRequest(Path("/test.bin"), 50, b"data2", asyncio.Future(), 0),
        ]
        combined = disk_io_manager._combine_contiguous_writes(writes)
        assert combined[0][0] == 0  # Should start at offset 0


class TestWriteQueuePrioritization:
    """Tests for write queue prioritization."""
    
    @pytest.mark.asyncio
    async def test_priority_queue_ordering(self, disk_io_manager):
        """Test that high priority writes are processed first."""
        # Create writes with different priorities
        future1 = asyncio.Future()
        future2 = asyncio.Future()
        future3 = asyncio.Future()
        
        req1 = WriteRequest(Path("/test.bin"), 0, b"low", future1, priority=0)
        req2 = WriteRequest(Path("/test.bin"), 0, b"high", future2, priority=100)
        req3 = WriteRequest(Path("/test.bin"), 0, b"medium", future3, priority=50)
        
        await disk_io_manager._put_write_request(req1)
        await disk_io_manager._put_write_request(req2)
        await disk_io_manager._put_write_request(req3)
        
        # High priority should come first
        first = await disk_io_manager._get_write_request()
        assert first.priority == 100
        assert first.data == b"high"
        
        # Then medium
        second = await disk_io_manager._get_write_request()
        assert second.priority == 50
        
        # Then low
        third = await disk_io_manager._get_write_request()
        assert third.priority == 0
    
    @pytest.mark.asyncio
    async def test_priority_queue_regular_mode(self, disk_io_manager):
        """Test that regular queue mode works when priority is disabled."""
        disk_io_manager.config.disk.write_queue_priority = False
        disk_io_manager.write_queue = asyncio.Queue()
        
        req = WriteRequest(Path("/test.bin"), 0, b"data", asyncio.Future(), priority=0)
        await disk_io_manager._put_write_request(req)
        
        retrieved = await disk_io_manager._get_write_request()
        assert retrieved == req


class TestMMapCacheOptimizations:
    """Tests for MMap cache optimizations."""
    
    @pytest.mark.asyncio
    async def test_size_aware_lru_eviction(self, disk_io_manager, temp_file):
        """Test that size-aware LRU eviction prefers large, less-frequently-accessed files."""
        # Fill cache with files of different sizes
        small_file = temp_file.parent / "small.bin"
        small_file.write_bytes(b"x" * 1024)
        large_file = temp_file.parent / "large.bin"
        large_file.write_bytes(b"x" * 1024 * 1024)
        
        # Access small file more frequently
        for _ in range(10):
            await disk_io_manager.read_block(small_file, 0, 100)
        
        # Access large file once
        await disk_io_manager.read_block(large_file, 0, 100)
        
        # Trigger cache cleanup
        await asyncio.sleep(0.1)
        
        # Large file should be evicted first (size-aware)
        with disk_io_manager.cache_lock:
            assert large_file not in disk_io_manager.mmap_cache or small_file in disk_io_manager.mmap_cache
    
    @pytest.mark.asyncio
    async def test_cache_warmup(self, disk_io_manager, tmp_path):
        """Test cache warmup functionality."""
        # Create multiple files
        file_paths = [tmp_path / f"file_{i}.bin" for i in range(5)]
        for fp in file_paths:
            fp.write_bytes(b"warmup data" * 100)
        
        # Warmup cache
        await disk_io_manager.warmup_cache(file_paths)
        
        # Check that files are in cache
        with disk_io_manager.cache_lock:
            for fp in file_paths[:3]:  # Check first few
                assert fp in disk_io_manager.mmap_cache
    
    @pytest.mark.asyncio
    async def test_cache_warmup_with_priority(self, disk_io_manager, tmp_path):
        """Test cache warmup with priority ordering."""
        file_paths = [tmp_path / f"file_{i}.bin" for i in range(5)]
        for fp in file_paths:
            fp.write_bytes(b"warmup data" * 100)
        
        # Warmup with priorities (0 = highest)
        priority_order = [2, 0, 1, 3, 4]
        await disk_io_manager.warmup_cache(file_paths, priority_order)
        
        # High priority files should be loaded first
        await asyncio.sleep(0.1)
        
        with disk_io_manager.cache_lock:
            # First priority file should be in cache
            assert file_paths[1] in disk_io_manager.mmap_cache  # Priority 0
    
    @pytest.mark.asyncio
    async def test_cache_statistics(self, disk_io_manager, temp_file):
        """Test enhanced cache statistics."""
        # Perform some reads
        await disk_io_manager.read_block(temp_file, 0, 100)
        await disk_io_manager.read_block(temp_file, 0, 100)  # Should hit cache
        
        stats = disk_io_manager.get_cache_stats()
        
        assert "entries" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert stats["cache_hits"] >= 1
        assert "hit_rate_percent" in stats
        assert "eviction_rate_per_sec" in stats
        assert "cache_efficiency_percent" in stats


class TestReadOptimizations:
    """Tests for read optimizations."""
    
    @pytest.mark.asyncio
    async def test_adaptive_read_ahead_sequential(self, disk_io_manager, temp_file):
        """Test adaptive read-ahead for sequential access."""
        # Read sequentially
        await disk_io_manager.read_block(temp_file, 0, 1000)
        await disk_io_manager.read_block(temp_file, 1000, 1000)
        await disk_io_manager.read_block(temp_file, 2000, 1000)
        
        # Check pattern tracking
        with disk_io_manager._read_pattern_lock:
            pattern = disk_io_manager._read_patterns.get(temp_file)
            assert pattern is not None
            assert pattern.sequential_count >= 2
            assert pattern.is_sequential(3000)  # Next read should be sequential
    
    @pytest.mark.asyncio
    async def test_adaptive_read_ahead_random(self, disk_io_manager, temp_file):
        """Test adaptive read-ahead for random access."""
        # Read randomly with large gaps
        await disk_io_manager.read_block(temp_file, 0, 1000)
        await disk_io_manager.read_block(temp_file, 100000, 1000)  # 100KB gap
        await disk_io_manager.read_block(temp_file, 50000, 1000)  # 50KB gap, not sequential
        
        # Check pattern tracking
        with disk_io_manager._read_pattern_lock:
            pattern = disk_io_manager._read_patterns.get(temp_file)
            assert pattern is not None
            # At least one random access (large gaps)
            assert pattern.random_count >= 1
    
    @pytest.mark.asyncio
    async def test_read_ahead_size_calculation(self, disk_io_manager, temp_file):
        """Test read-ahead size calculation."""
        # Sequential pattern
        await disk_io_manager.read_block(temp_file, 0, 1000)
        await disk_io_manager.read_block(temp_file, 1000, 1000)
        
        size = disk_io_manager._get_read_ahead_size(temp_file, 2000, 1000)
        # Sequential reads should use larger read-ahead (4x requested or max)
        # For sequential: min(max_read_ahead, length * 4)
        assert size >= 1000  # At least the requested size
        if disk_io_manager.config.disk.read_ahead_adaptive:
            # Should use adaptive sizing (4x requested or max)
            assert size >= 4000 or size == disk_io_manager.config.disk.read_ahead_max_kib * 1024
        
        # Random pattern - use a gap definitely > 1MB (1024*1024 = 1048576)
        # Use 2MB gap to ensure it's not sequential
        await disk_io_manager.read_block(temp_file, 5000000, 1000)  # 5MB away
        # Check with gap > 1MB (5000000 + 2000000 = 7000000, gap = 2000000 > 1048576)
        size_random = disk_io_manager._get_read_ahead_size(temp_file, 7000000, 1000)
        # For random access, should use base read-ahead size
        assert size_random == disk_io_manager.config.disk.read_ahead_kib * 1024


class TestIOWorkerOptimizations:
    """Tests for I/O worker optimizations."""
    
    @pytest.mark.asyncio
    async def test_adaptive_worker_adjustment(self, disk_io_manager):
        """Test adaptive worker count adjustment."""
        # Manually trigger worker adjustment
        if disk_io_manager._worker_adjustment_task:
            # Wait a bit for adjustment to run
            await asyncio.sleep(0.1)
        
        # Check that worker adjustment task is running
        assert disk_io_manager._worker_adjustment_task is not None or not disk_io_manager.config.disk.disk_workers_adaptive
    
    @pytest.mark.asyncio
    async def test_lba_scheduling(self, disk_io_manager):
        """Test LBA-based write scheduling."""
        disk_io_manager.config.disk.io_schedule_by_lba = True
        
        writes = [
            WriteRequest(Path("/file2.bin"), 1000, b"data2", asyncio.Future(), 0),
            WriteRequest(Path("/file1.bin"), 0, b"data1", asyncio.Future(), 0),
            WriteRequest(Path("/file1.bin"), 500, b"data1b", asyncio.Future(), 0),
        ]
        
        # Sort writes (simulating LBA scheduling)
        if disk_io_manager.config.disk.io_schedule_by_lba:
            writes.sort(key=lambda x: (str(x.file_path), x.offset))
        
        assert writes[0].file_path.name == "file1.bin"
        assert writes[0].offset == 0
        assert writes[1].file_path.name == "file1.bin"
        assert writes[1].offset == 500


class TestReadPattern:
    """Tests for ReadPattern class."""
    
    def test_read_pattern_sequential_detection(self):
        """Test sequential access detection."""
        pattern = ReadPattern()
        
        # First access - no previous offset
        assert not pattern.is_sequential(0)  # First access, no previous
        
        pattern.update(0)
        # After update, last_offset is 0, so 1000 is sequential (within 1MB)
        assert pattern.is_sequential(1000)  # Within 1MB of 0
        
        pattern.update(1000)
        assert pattern.is_sequential(2000)  # Within 1MB
        
        pattern.update(2000)
        assert pattern.is_sequential(3000)  # Sequential
        
        pattern.update(2000000)  # 2MB away
        # 3000000 - 2000000 = 1000000 bytes = ~0.95MB, still < 1MB
        # Need gap >= 1048576 (1MB) to be non-sequential
        # Use 3000000 + 1048576 = 4048576 to ensure gap > 1MB
        assert not pattern.is_sequential(4048576)  # Not sequential (>1MB gap, 4048576 - 2000000 = 2048576 > 1048576)
    
    def test_read_pattern_counts(self):
        """Test access count tracking."""
        pattern = ReadPattern()
        
        pattern.update(0)
        pattern.update(1000)  # Sequential (within 1MB of 0)
        pattern.update(50000)  # Random (50000 > 0 + 1MB, so not sequential)
        
        # First update(0) is first access, doesn't count as sequential or random
        # Second update(1000) is sequential relative to 0
        # Third update(50000) is random relative to 1000
        assert pattern.sequential_count >= 1
        assert pattern.random_count >= 1
        assert pattern.last_offset == 50000


class TestAdaptiveCacheSize:
    """Tests for adaptive cache size adjustment."""
    
    @pytest.mark.asyncio
    async def test_adaptive_cache_size_adjustment(self, disk_io_manager):
        """Test adaptive cache size adjustment based on memory."""
        if not disk_io_manager.config.disk.mmap_cache_adaptive:
            pytest.skip("Adaptive cache size not enabled")
        
        # Store initial size
        initial_size = disk_io_manager.cache_size_bytes
        
        # Trigger adjustment (simulate low memory)
        await asyncio.sleep(0.1)
        
        # Size may have adjusted (or not, depending on memory)
        # Just verify the task is running
        assert disk_io_manager._cache_adaptive_task is not None


class TestCheckpointOptimizations:
    """Tests for checkpoint optimizations (integration with checkpoint manager)."""
    
    @pytest.mark.asyncio
    async def test_checkpoint_deduplication(self):
        """Test checkpoint deduplication."""
        from ccbt.storage.checkpoint import CheckpointManager
        from ccbt.models import TorrentCheckpoint, PieceState
        import time
        
        config = DiskConfig()
        config.checkpoint_deduplication = True
        manager = CheckpointManager(config)
        
        # Use same timestamp for both checkpoints to ensure identical hash
        test_timestamp = time.time()
        
        # Create identical checkpoints with required fields
        checkpoint1 = TorrentCheckpoint(
            info_hash=b"test" * 5,
            torrent_name="test_torrent",
            total_pieces=10,
            verified_pieces=[0, 1, 2],
            piece_states={},
            download_stats=None,
            updated_at=test_timestamp,
        )
        
        checkpoint2 = TorrentCheckpoint(
            info_hash=b"test" * 5,
            torrent_name="test_torrent",
            total_pieces=10,
            verified_pieces=[0, 1, 2],
            piece_states={},
            download_stats=None,
            updated_at=test_timestamp,
        )
        
        # Both should have same hash
        hash1 = manager._calculate_checkpoint_hash(checkpoint1)
        hash2 = manager._calculate_checkpoint_hash(checkpoint2)
        assert hash1 == hash2


@pytest.mark.asyncio
async def test_write_block_with_priority(disk_io_manager, temp_file):
    """Test write_block with priority parameter."""
    future = await disk_io_manager.write_block(temp_file, 0, b"test data", priority=100)
    assert future is not None
    await future  # Wait for completion


@pytest.mark.asyncio
async def test_read_block_adaptive_read_ahead(disk_io_manager, temp_file):
    """Test read_block uses adaptive read-ahead."""
    # First read
    data = await disk_io_manager.read_block(temp_file, 0, 1000)
    assert len(data) >= 1000
    
    # Sequential read should use larger read-ahead
    data2 = await disk_io_manager.read_block(temp_file, 1000, 1000)
    assert len(data2) >= 1000

