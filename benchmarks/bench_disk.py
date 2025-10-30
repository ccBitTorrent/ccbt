"""Benchmark for disk I/O performance.

Tests the performance of async disk I/O operations including
preallocation, write batching, mmap, and hash verification.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import os
import statistics
import tempfile
import time
from typing import Any

from ccbt.config import get_config
from ccbt.storage.disk_io import (
    DiskIOManager,
)


class DiskIOBenchmark:
    """Benchmark disk I/O performance."""

    def __init__(self):
        self.config = get_config()
        self.results = {}
        self.temp_files = []

    async def setup_benchmark(self) -> dict[str, Any]:
        """Set up benchmark environment."""
        # Create disk I/O manager
        disk_io = DiskIOManager(asyncio.get_event_loop(), self.config)
        await disk_io.start()

        return {
            "disk_io": disk_io,
        }

    async def cleanup_benchmark(self, setup_data: dict[str, Any]):
        """Clean up benchmark environment."""
        await setup_data["disk_io"].stop()

        # Clean up temp files
        for temp_file in self.temp_files:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp_file)

    def create_temp_file(self, size: int) -> str:
        """Create temporary file for benchmarking."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        self.temp_files.append(temp_path)
        return temp_path

    async def benchmark_preallocation(
        self,
        setup_data: dict[str, Any],
    ) -> dict[str, float]:
        """Benchmark file preallocation performance."""
        disk_io = setup_data["disk_io"]

        # Test different file sizes
        sizes = [1024 * 1024, 10 * 1024 * 1024, 100 * 1024 * 1024]  # 1MB, 10MB, 100MB
        results = {}

        for size in sizes:
            temp_file = self.create_temp_file(size)

            # Benchmark preallocation
            start_time = time.time()
            await disk_io.preallocate_file(temp_file, size)
            end_time = time.time()

            duration = end_time - start_time
            speed_mb_s = (size / 1024 / 1024) / duration

            results[f"{size // (1024 * 1024)}MB"] = {
                "duration": duration,
                "speed_mb_s": speed_mb_s,
                "size_mb": size / 1024 / 1024,
            }

        return results

    async def benchmark_write_performance(
        self,
        setup_data: dict[str, Any],
    ) -> dict[str, float]:
        """Benchmark write performance with different strategies."""
        disk_io = setup_data["disk_io"]

        # Test data sizes
        data_sizes = [1024, 10240, 102400, 1024000]  # 1KB, 10KB, 100KB, 1MB
        results = {}

        for data_size in data_sizes:
            temp_file = self.create_temp_file(data_size)
            test_data = b"X" * data_size

            # Benchmark single write
            start_time = time.time()
            await disk_io.write_block(temp_file, 0, test_data)
            end_time = time.time()

            single_write_time = end_time - start_time
            single_write_speed = data_size / single_write_time / 1024 / 1024  # MB/s

            # Benchmark batched writes
            batch_size = 1024  # 1KB batches
            start_time = time.time()

            for i in range(0, data_size, batch_size):
                chunk = test_data[i : i + batch_size]
                await disk_io.write_block(temp_file, i, chunk)

            end_time = time.time()

            batched_write_time = end_time - start_time
            batched_write_speed = data_size / batched_write_time / 1024 / 1024  # MB/s

            results[f"{data_size}B"] = {
                "single_write_speed_mb_s": single_write_speed,
                "batched_write_speed_mb_s": batched_write_speed,
                "single_write_time": single_write_time,
                "batched_write_time": batched_write_time,
            }

        return results

    async def benchmark_read_performance(
        self,
        setup_data: dict[str, Any],
    ) -> dict[str, float]:
        """Benchmark read performance with mmap vs regular reads."""
        disk_io = setup_data["disk_io"]

        # Create test file
        temp_file = self.create_temp_file(10 * 1024 * 1024)  # 10MB
        test_data = b"Y" * (10 * 1024 * 1024)
        await disk_io.write_block(temp_file, 0, test_data)

        # Test different read sizes
        read_sizes = [1024, 10240, 102400, 1024000]  # 1KB, 10KB, 100KB, 1MB
        results = {}

        for read_size in read_sizes:
            # Benchmark regular read
            start_time = time.time()
            await disk_io.read_block(temp_file, 0, read_size)
            end_time = time.time()

            regular_read_time = end_time - start_time
            regular_read_speed = read_size / regular_read_time / 1024 / 1024  # MB/s

            # Benchmark mmap read
            start_time = time.time()
            await disk_io.read_block_mmap(temp_file, 0, read_size)
            end_time = time.time()

            mmap_read_time = end_time - start_time
            mmap_read_speed = read_size / mmap_read_time / 1024 / 1024  # MB/s

            results[f"{read_size}B"] = {
                "regular_read_speed_mb_s": regular_read_speed,
                "mmap_read_speed_mb_s": mmap_read_speed,
                "regular_read_time": regular_read_time,
                "mmap_read_time": mmap_read_time,
            }

        return results

    async def benchmark_hash_verification(
        self,
        setup_data: dict[str, Any],
    ) -> dict[str, float]:
        """Benchmark hash verification performance."""
        disk_io = setup_data["disk_io"]

        # Test different piece sizes
        piece_sizes = [16384, 32768, 65536]  # 16KB, 32KB, 64KB
        results = {}

        for piece_size in piece_sizes:
            temp_file = self.create_temp_file(piece_size)
            test_data = b"Z" * piece_size

            # Write test data
            await disk_io.write_block(temp_file, 0, test_data)

            # Benchmark hash verification
            start_time = time.time()

            # Read data and hash it
            read_data = await disk_io.read_block_mmap(temp_file, 0, piece_size)
            hasher = hashlib.sha1()
            hasher.update(read_data)
            hasher.digest()

            end_time = time.time()

            hash_time = end_time - start_time
            hash_speed = piece_size / hash_time / 1024 / 1024  # MB/s

            results[f"{piece_size}B"] = {
                "hash_time": hash_time,
                "hash_speed_mb_s": hash_speed,
                "piece_size_mb": piece_size / 1024 / 1024,
            }

        return results

    async def benchmark_concurrent_operations(
        self,
        setup_data: dict[str, Any],
    ) -> dict[str, float]:
        """Benchmark concurrent disk operations."""
        disk_io = setup_data["disk_io"]

        # Create multiple temp files
        num_files = 10
        temp_files = [self.create_temp_file(1024 * 1024) for _ in range(num_files)]

        # Benchmark concurrent writes
        start_time = time.time()

        tasks = []
        for i, temp_file in enumerate(temp_files):
            data = f"File {i} data".encode() * 1000
            task = asyncio.create_task(
                disk_io.write_block(temp_file, 0, data),
            )
            tasks.append(task)

        await asyncio.gather(*tasks)
        end_time = time.time()

        concurrent_write_time = end_time - start_time
        concurrent_write_speed = (
            (num_files * 1024 * 1024) / concurrent_write_time / 1024 / 1024
        )  # MB/s

        # Benchmark concurrent reads
        start_time = time.time()

        tasks = []
        for temp_file in temp_files:
            task = asyncio.create_task(
                disk_io.read_block(temp_file, 0, 1024 * 1024),
            )
            tasks.append(task)

        await asyncio.gather(*tasks)
        end_time = time.time()

        concurrent_read_time = end_time - start_time
        concurrent_read_speed = (
            (num_files * 1024 * 1024) / concurrent_read_time / 1024 / 1024
        )  # MB/s

        return {
            "concurrent_write_speed_mb_s": concurrent_write_speed,
            "concurrent_read_speed_mb_s": concurrent_read_speed,
            "concurrent_write_time": concurrent_write_time,
            "concurrent_read_time": concurrent_read_time,
            "num_files": num_files,
        }

    async def benchmark_memory_usage(
        self,
        setup_data: dict[str, Any],
    ) -> dict[str, float]:
        """Benchmark memory usage during disk operations."""
        import gc

        import psutil

        disk_io = setup_data["disk_io"]

        # Force garbage collection
        gc.collect()

        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create large file
        temp_file = self.create_temp_file(100 * 1024 * 1024)  # 100MB
        large_data = b"X" * (100 * 1024 * 1024)

        # Write large file
        await disk_io.write_block(temp_file, 0, large_data)

        # Get memory after write
        gc.collect()
        after_write_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Read large file
        await disk_io.read_block_mmap(temp_file, 0, 100 * 1024 * 1024)

        # Get memory after read
        gc.collect()
        after_read_memory = process.memory_info().rss / 1024 / 1024  # MB

        return {
            "initial_memory_mb": initial_memory,
            "after_write_memory_mb": after_write_memory,
            "after_read_memory_mb": after_read_memory,
            "write_memory_increase_mb": after_write_memory - initial_memory,
            "read_memory_increase_mb": after_read_memory - after_write_memory,
        }

    async def run_benchmark(
        self,
        benchmark_name: str,
        benchmark_func,
    ) -> dict[str, Any]:
        """Run a single benchmark."""
        setup_data = await self.setup_benchmark()

        try:
            # Run benchmark multiple times for accuracy
            results = []
            for _ in range(3):  # 3 runs
                result = await benchmark_func(setup_data)
                results.append(result)

            # Calculate statistics for numeric values
            if isinstance(results[0], dict):
                # Handle nested results
                final_result = {}
                for key in results[0]:
                    if isinstance(results[0][key], dict):
                        # Nested dictionary
                        nested_result = {}
                        for nested_key in results[0][key]:
                            if isinstance(results[0][key][nested_key], (int, float)):
                                values = [r[key][nested_key] for r in results]
                                nested_result[nested_key] = {
                                    "mean": statistics.mean(values),
                                    "std": statistics.stdev(values)
                                    if len(values) > 1
                                    else 0,
                                }
                            else:
                                nested_result[nested_key] = results[0][key][nested_key]
                        final_result[key] = nested_result
                    elif isinstance(results[0][key], (int, float)):
                        values = [r[key] for r in results]
                        final_result[key] = {
                            "mean": statistics.mean(values),
                            "std": statistics.stdev(values) if len(values) > 1 else 0,
                        }
                    else:
                        final_result[key] = results[0][key]

                return final_result
            return results[0]

        finally:
            await self.cleanup_benchmark(setup_data)

    async def run_all_benchmarks(self):
        """Run all benchmarks."""
        benchmarks = [
            ("Preallocation Performance", self.benchmark_preallocation),
            ("Write Performance", self.benchmark_write_performance),
            ("Read Performance", self.benchmark_read_performance),
            ("Hash Verification", self.benchmark_hash_verification),
            ("Concurrent Operations", self.benchmark_concurrent_operations),
            ("Memory Usage", self.benchmark_memory_usage),
        ]

        for name, func in benchmarks:
            try:
                result = await self.run_benchmark(name, func)
                self.results[name] = result

                if isinstance(result, dict):
                    for value in result.values():
                        if isinstance(value, dict) and "mean" in value:
                            pass
                        else:
                            pass
                else:
                    pass

            except Exception as e:
                self.results[name] = {"error": str(e)}

        for name, result in self.results.items():
            if "error" in result:
                pass
            else:
                pass

    def save_results(self, filename: str):
        """Save benchmark results to file."""
        import json

        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)


async def main():
    """Main benchmark function."""
    parser = argparse.ArgumentParser(description="Disk I/O Performance Benchmark")
    parser.add_argument(
        "--output",
        "-o",
        default="disk_results.json",
        help="Output file for results",
    )
    args = parser.parse_args()

    benchmark = DiskIOBenchmark()
    await benchmark.run_all_benchmarks()
    benchmark.save_results(args.output)


if __name__ == "__main__":
    asyncio.run(main())
