"""Performance benchmarks for ccBitTorrent.

Tests performance characteristics and benchmarks
using pytest-benchmark for regression detection.
"""

import asyncio
import contextlib
import tempfile
from pathlib import Path

import pytest

from ccbt.core.bencode import decode, encode
from ccbt.storage.buffers import MemoryPool, RingBuffer, ZeroCopyBuffer
from ccbt.storage.disk_io import DiskIOManager
from ccbt.utils.events import Event, EventBus, EventHandler, EventType
from ccbt.core.torrent import TorrentParser

# Check if pytest-benchmark is available
try:
    import pytest_benchmark

    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False


# Stub benchmark function for when pytest-benchmark is not available
def stub_benchmark(func, *args, **kwargs):
    """Stub benchmark function that just calls the function once."""
    if asyncio.iscoroutinefunction(func):
        # For async functions, check if we're already in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're already in an async context, return the coroutine directly
            return func(*args, **kwargs)
        except RuntimeError:
            # No running loop, create one
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(func(*args, **kwargs))
            finally:
                loop.close()
    else:
        return func(*args, **kwargs)


class TestBencodePerformance:
    """Performance tests for bencode operations."""

    def test_bencode_encode_performance(self, benchmark=None):
        """Benchmark bencode encoding performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        test_data = {
            "announce": "http://tracker.example.com/announce",
            "info": {
                "name": "test_torrent",
                "length": 1024,
                "piece length": 16384,
                "pieces": b"\x00" * 20,
            },
        }

        result = benchmark(encode, test_data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_bencode_decode_performance(self, benchmark=None):
        """Benchmark bencode decoding performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        # Test data with string keys (what we encode)
        encode_data = {
            "announce": "http://tracker.example.com/announce",
            "info": {
                "name": "test_torrent",
                "length": 1024,
                "piece length": 16384,
                "pieces": b"\x00" * 20,
            },
        }

        # Expected decode result with bytes keys (what bencode actually returns)
        expected_decode_result = {
            b"announce": b"http://tracker.example.com/announce",
            b"info": {
                b"name": b"test_torrent",
                b"length": 1024,
                b"piece length": 16384,
                b"pieces": b"\x00" * 20,
            },
        }

        encoded = encode(encode_data)
        result = benchmark(decode, encoded)
        assert result == expected_decode_result

    def test_bencode_roundtrip_performance(self, benchmark=None):
        """Benchmark bencode roundtrip performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        # Original test data with string keys
        original_data = {
            "announce": "http://tracker.example.com/announce",
            "info": {
                "name": "test_torrent",
                "length": 1024,
                "piece length": 16384,
                "pieces": b"\x00" * 20,
            },
        }

        # Expected result after encode/decode roundtrip (bytes keys)
        expected_result = {
            b"announce": b"http://tracker.example.com/announce",
            b"info": {
                b"name": b"test_torrent",
                b"length": 1024,
                b"piece length": 16384,
                b"pieces": b"\x00" * 20,
            },
        }

        def roundtrip(data):
            encoded = encode(data)
            return decode(encoded)

        result = benchmark(roundtrip, original_data)
        assert result == expected_result


class TestBufferPerformance:
    """Performance tests for buffer operations."""

    def test_ring_buffer_write_performance(self, benchmark=None):
        """Benchmark ring buffer write performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        buffer = RingBuffer(1024 * 1024)  # 1MB buffer

        test_data = b"x" * 1024  # 1KB data

        def write_data():
            return buffer.write(test_data)

        result = benchmark(write_data)
        assert result == len(test_data)

    def test_ring_buffer_read_performance(self, benchmark=None):
        """Benchmark ring buffer read performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        buffer = RingBuffer(1024 * 1024)  # 1MB buffer

        # Fill buffer with data
        test_data = b"x" * 1024  # 1KB data
        buffer.write(test_data)

        def read_data():
            return buffer.read(1024)

        result = benchmark(read_data)
        assert len(result) == 1024

    def test_memory_pool_performance(self, benchmark=None):
        """Benchmark memory pool performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        pool = MemoryPool(1024, 100)  # 1KB objects, 100 in pool

        def get_and_put():
            obj = pool.get()
            pool.put(obj)
            return obj

        result = benchmark(get_and_put)
        assert isinstance(result, bytearray)
        assert len(result) == 1024

    def test_zero_copy_buffer_performance(self, benchmark=None):
        """Benchmark zero-copy buffer performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        buffer = ZeroCopyBuffer(1024 * 1024)  # 1MB buffer

        test_data = b"x" * 1024  # 1KB data

        def write_data():
            return buffer.write(test_data)

        result = benchmark(write_data)
        assert result == len(test_data)


class TestDiskIOPerformance:
    """Performance tests for disk I/O operations."""

    @pytest.mark.asyncio
    async def test_disk_io_write_performance(self, benchmark=None):
        """Benchmark disk I/O write performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DiskIOManager()
            await manager.start()

            try:
                test_file = Path(tmpdir) / "test_write.bin"
                test_data = b"x" * 1024  # 1KB data

                async def write_file():
                    future = await manager.write_block(test_file, 0, test_data)
                    await future  # Ensure the write is actually completed

                await benchmark(write_file)

                # Verify file was written
                assert test_file.exists()
                assert test_file.stat().st_size == len(test_data)

            finally:
                await manager.stop()

    @pytest.mark.asyncio
    async def test_disk_io_read_performance(self, benchmark=None):
        """Benchmark disk I/O read performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DiskIOManager()
            await manager.start()

            try:
                test_file = Path(tmpdir) / "test_read.bin"
                test_data = b"x" * 1024  # 1KB data

                # Write test file
                future = await manager.write_block(test_file, 0, test_data)
                await future  # Ensure the write is actually completed

                async def read_file():
                    return await manager.read_block(test_file, 0, len(test_data))

                result = await benchmark(read_file)
                assert result == test_data

            finally:
                await manager.stop()

    @pytest.mark.asyncio
    async def test_disk_io_batch_performance(self, benchmark=None):
        """Benchmark disk I/O batch performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DiskIOManager()
            await manager.start()

            try:
                test_file = Path(tmpdir) / "test_batch.bin"
                test_data = b"x" * 1024  # 1KB data

                async def batch_write():
                    # Write multiple blocks
                    futures = []
                    for i in range(10):
                        future = await manager.write_block(
                            test_file,
                            i * 1024,
                            test_data,
                        )
                        futures.append(future)

                    # Wait for all writes to complete
                    for future in futures:
                        await future

                await benchmark(batch_write)

                # Verify file was written
                assert test_file.exists()
                assert test_file.stat().st_size == 10 * len(test_data)

            finally:
                await manager.stop()


class TestEventSystemPerformance:
    """Performance tests for event system."""

    @pytest.mark.asyncio
    async def test_event_emission_performance(self, benchmark=None):
        """Benchmark event emission performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        event_bus = EventBus()
        await event_bus.start()

        try:
            # Create test event
            test_event = Event(
                event_type=EventType.PEER_CONNECTED.value,
                data={"peer_ip": "192.168.1.1", "peer_port": 6881},
            )

            async def emit_event():
                await event_bus.emit(test_event)

            result = await benchmark(emit_event)
            assert result is None  # emit_event returns None

        finally:
            await event_bus.stop()

    @pytest.mark.asyncio
    async def test_event_processing_performance(self, benchmark=None):
        """Benchmark event processing performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        event_bus = EventBus()
        await event_bus.start()

        try:
            # Register event handler
            class TestHandler(EventHandler):
                def __init__(self):
                    super().__init__("test_handler")
                    self.count = 0

                async def handle(self, event):
                    self.count += 1

            handler = TestHandler()
            event_bus.register_handler(EventType.PEER_CONNECTED.value, handler)

            # Create test event
            test_event = Event(
                event_type=EventType.PEER_CONNECTED.value,
                data={"peer_ip": "192.168.1.1", "peer_port": 6881},
            )

            async def process_event():
                await event_bus.emit(test_event)
                # Wait for processing
                await asyncio.sleep(0.01)

            result = await benchmark(process_event)
            assert result is None  # process_event returns None

        finally:
            await event_bus.stop()

    @pytest.mark.asyncio
    async def test_event_batch_performance(self, benchmark=None):
        """Benchmark event batch processing performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        event_bus = EventBus()
        await event_bus.start()

        try:
            # Register event handler
            class TestHandler(EventHandler):
                def __init__(self):
                    super().__init__("test_handler")
                    self.count = 0

                async def handle(self, event):
                    self.count += 1

            handler = TestHandler()
            event_bus.register_handler(EventType.PEER_CONNECTED.value, handler)

            async def batch_emit():
                # Emit multiple events
                for i in range(100):
                    test_event = Event(
                        event_type=EventType.PEER_CONNECTED.value,
                        data={"peer_ip": f"192.168.1.{i}", "peer_port": 6881},
                    )
                    await event_bus.emit(test_event)

                # Wait for processing
                await asyncio.sleep(0.1)

            result = await benchmark(batch_emit)
            assert result is None  # batch_emit returns None

        finally:
            await event_bus.stop()


class TestTorrentParsingPerformance:
    """Performance tests for torrent parsing."""

    def test_torrent_parsing_performance(self, benchmark=None):
        """Benchmark torrent parsing performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        # Create sample torrent file in temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            torrent_file = Path(tmpdir) / "test.torrent"

            # Create proper torrent data using the bencode encoder
            torrent_data = {
                "announce": "http://tracker.example.com/announce",
                "info": {
                    "name": "test_torrent",
                    "length": 1024,
                    "piece length": 16384,
                    "pieces": b"\x00" * 20,
                },
            }

            # Encode using our bencode encoder
            encoded_data = encode(torrent_data)

            # Write to file
            with open(torrent_file, "wb") as f:
                f.write(encoded_data)

            parser = TorrentParser()

            def parse_torrent():
                return parser.parse(torrent_file)

            result = benchmark(parse_torrent)
            assert result.name == "test_torrent"
            assert result.total_length == 1024


class TestMemoryUsage:
    """Memory usage tests."""

    def test_ring_buffer_memory_usage(self, benchmark=None):
        """Test ring buffer memory usage."""
        if benchmark is None:
            benchmark = stub_benchmark

        buffer = RingBuffer(1024 * 1024)  # 1MB buffer

        def memory_test():
            # Write and read data multiple times
            for _ in range(100):
                data = b"x" * 1024
                buffer.write(data)
                buffer.read(1024)

        benchmark(memory_test)

        # Check memory usage is reasonable
        assert buffer.used_space() <= buffer.size

    def test_memory_pool_memory_usage(self, benchmark=None):
        """Test memory pool memory usage."""
        if benchmark is None:
            benchmark = stub_benchmark

        pool = MemoryPool(1024, 100)  # 1KB objects, 100 in pool

        def memory_test():
            # Get and put objects multiple times
            for _ in range(1000):
                obj = pool.get()
                pool.put(obj)

        benchmark(memory_test)

        # Check pool stats
        stats = pool.get_stats()
        assert stats.current_usage <= 100


class TestConcurrencyPerformance:
    """Concurrency performance tests."""

    @pytest.mark.asyncio
    async def test_concurrent_event_processing(self, benchmark=None):
        """Benchmark concurrent event processing."""
        if benchmark is None:
            benchmark = stub_benchmark

        event_bus = EventBus()
        await event_bus.start()

        try:
            # Register event handler
            class TestHandler(EventHandler):
                def __init__(self):
                    super().__init__("test_handler")
                    self.count = 0

                async def handle(self, event):
                    self.count += 1

            handler = TestHandler()
            event_bus.register_handler(EventType.PEER_CONNECTED.value, handler)

            async def concurrent_emit():
                # Emit events concurrently
                tasks = []
                for i in range(100):
                    test_event = Event(
                        event_type=EventType.PEER_CONNECTED.value,
                        data={"peer_ip": f"192.168.1.{i}", "peer_port": 6881},
                    )
                    task = asyncio.create_task(event_bus.emit(test_event))
                    tasks.append(task)

                await asyncio.gather(*tasks)
                # Wait for processing
                await asyncio.sleep(0.1)

            await benchmark(concurrent_emit)

        finally:
            await event_bus.stop()

    @pytest.mark.asyncio
    async def test_concurrent_disk_io(self, benchmark=None):
        """Benchmark concurrent disk I/O."""
        if benchmark is None:
            benchmark = stub_benchmark

        manager = DiskIOManager()
        await manager.start()

        try:

            async def concurrent_write():
                # Write to multiple files concurrently
                tasks = []
                for i in range(10):
                    test_file = Path(f"test_{i}.bin")
                    test_data = b"x" * 1024
                    task = asyncio.create_task(
                        manager.write_block(test_file, 0, test_data),
                    )
                    tasks.append(task)

                await asyncio.gather(*tasks)

            await benchmark(concurrent_write)

        finally:
            await manager.stop()
            # Clean up test files
            for i in range(10):
                with contextlib.suppress(FileNotFoundError):
                    Path(f"test_{i}.bin").unlink()
