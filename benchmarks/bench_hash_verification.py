"""Benchmark for hash verification scaling.

Tests the performance of parallel hash verification with different
worker pool sizes and piece sizes.
"""

import argparse
import asyncio
import hashlib
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from ccbt.async_piece_manager import AsyncPieceManager
from ccbt.config import get_config


class HashVerificationBenchmark:
    """Benchmark hash verification performance."""

    def __init__(self):
        self.config = get_config()
        self.results = {}

    async def setup_benchmark(self, num_pieces: int, piece_size: int) -> Dict[str, Any]:
        """Set up benchmark environment."""
        # Create torrent data
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "file_info": {
                "name": "benchmark_file.bin",
                "total_length": num_pieces * piece_size,
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": num_pieces,
                "piece_length": piece_size,
                "piece_hashes": [b"\x00" * 20] * num_pieces,
            },
        }

        # Create piece manager
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.start()

        return {
            "torrent_data": torrent_data,
            "piece_manager": piece_manager,
        }

    async def cleanup_benchmark(self, setup_data: Dict[str, Any]):
        """Clean up benchmark environment."""
        await setup_data["piece_manager"].stop()

    async def benchmark_sequential_hashing(self, setup_data: Dict[str, Any]) -> Dict[str, float]:
        """Benchmark sequential hash verification."""
        piece_manager = setup_data["piece_manager"]
        num_pieces = setup_data["torrent_data"]["pieces_info"]["num_pieces"]
        piece_size = setup_data["torrent_data"]["pieces_info"]["piece_length"]

        # Create test data
        test_data = b"X" * piece_size

        # Benchmark sequential hashing
        start_time = time.time()

        for i in range(num_pieces):
            hasher = hashlib.sha1()
            hasher.update(test_data)
            hash_result = hasher.digest()

        end_time = time.time()

        duration = end_time - start_time
        pieces_per_second = num_pieces / duration
        mb_per_second = (num_pieces * piece_size) / duration / 1024 / 1024

        return {
            "duration": duration,
            "pieces_per_second": pieces_per_second,
            "mb_per_second": mb_per_second,
            "total_pieces": num_pieces,
            "piece_size_mb": piece_size / 1024 / 1024,
        }

    async def benchmark_parallel_hashing(self, setup_data: Dict[str, Any], num_workers: int) -> Dict[str, float]:
        """Benchmark parallel hash verification with specified worker count."""
        piece_manager = setup_data["piece_manager"]
        num_pieces = setup_data["torrent_data"]["pieces_info"]["num_pieces"]
        piece_size = setup_data["torrent_data"]["pieces_info"]["piece_length"]

        # Create test data
        test_data = b"Y" * piece_size

        # Create thread pool
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Benchmark parallel hashing
            start_time = time.time()

            # Create tasks
            tasks = []
            for i in range(num_pieces):
                task = executor.submit(self._hash_piece, test_data)
                tasks.append(task)

            # Wait for all tasks
            results = [task.result() for task in tasks]

            end_time = time.time()

        duration = end_time - start_time
        pieces_per_second = num_pieces / duration
        mb_per_second = (num_pieces * piece_size) / duration / 1024 / 1024

        return {
            "duration": duration,
            "pieces_per_second": pieces_per_second,
            "mb_per_second": mb_per_second,
            "total_pieces": num_pieces,
            "piece_size_mb": piece_size / 1024 / 1024,
            "num_workers": num_workers,
        }

    def _hash_piece(self, data: bytes) -> bytes:
        """Hash a single piece of data."""
        hasher = hashlib.sha1()
        hasher.update(data)
        return hasher.digest()

    async def benchmark_worker_scaling(self, setup_data: Dict[str, Any]) -> Dict[str, Any]:
        """Benchmark hash verification with different worker counts."""
        worker_counts = [1, 2, 4, 8, 16]
        results = {}

        for num_workers in worker_counts:
            result = await self.benchmark_parallel_hashing(setup_data, num_workers)
            results[f"{num_workers}_workers"] = result

        return results

    async def benchmark_piece_size_scaling(self, num_pieces: int) -> Dict[str, Any]:
        """Benchmark hash verification with different piece sizes."""
        piece_sizes = [16384, 32768, 65536, 131072]  # 16KB, 32KB, 64KB, 128KB
        results = {}

        for piece_size in piece_sizes:
            setup_data = await self.setup_benchmark(num_pieces, piece_size)

            try:
                # Test with 4 workers
                result = await self.benchmark_parallel_hashing(setup_data, 4)
                results[f"{piece_size}B"] = result
            finally:
                await self.cleanup_benchmark(setup_data)

        return results

    async def benchmark_memory_efficiency(self, setup_data: Dict[str, Any]) -> Dict[str, float]:
        """Benchmark memory efficiency during hash verification."""
        import gc

        import psutil

        piece_manager = setup_data["piece_manager"]
        num_pieces = setup_data["torrent_data"]["pieces_info"]["num_pieces"]
        piece_size = setup_data["torrent_data"]["pieces_info"]["piece_length"]

        # Force garbage collection
        gc.collect()

        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create test data
        test_data = b"Z" * piece_size

        # Hash all pieces
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=4) as executor:
            tasks = [executor.submit(self._hash_piece, test_data) for _ in range(num_pieces)]
            results = [task.result() for task in tasks]

        end_time = time.time()

        # Get peak memory usage
        gc.collect()
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB

        duration = end_time - start_time
        memory_increase = peak_memory - initial_memory

        return {
            "initial_memory_mb": initial_memory,
            "peak_memory_mb": peak_memory,
            "memory_increase_mb": memory_increase,
            "duration": duration,
            "total_pieces": num_pieces,
            "piece_size_mb": piece_size / 1024 / 1024,
        }

    async def benchmark_batch_processing(self, setup_data: Dict[str, Any]) -> Dict[str, Any]:
        """Benchmark batch processing of hash verification."""
        piece_manager = setup_data["piece_manager"]
        num_pieces = setup_data["torrent_data"]["pieces_info"]["num_pieces"]
        piece_size = setup_data["torrent_data"]["pieces_info"]["piece_length"]

        # Test different batch sizes
        batch_sizes = [1, 4, 8, 16, 32]
        results = {}

        for batch_size in batch_sizes:
            test_data = b"W" * piece_size

            start_time = time.time()

            # Process in batches
            for i in range(0, num_pieces, batch_size):
                batch_end = min(i + batch_size, num_pieces)
                batch_tasks = []

                for j in range(i, batch_end):
                    batch_tasks.append(self._hash_piece(test_data))

                # Process batch
                batch_results = batch_tasks

            end_time = time.time()

            duration = end_time - start_time
            pieces_per_second = num_pieces / duration

            results[f"batch_{batch_size}"] = {
                "duration": duration,
                "pieces_per_second": pieces_per_second,
                "batch_size": batch_size,
            }

        return results

    async def run_benchmark(self, benchmark_name: str, benchmark_func, *args) -> Dict[str, Any]:
        """Run a single benchmark."""
        print(f"Running {benchmark_name}...")

        try:
            # Run benchmark multiple times for accuracy
            results = []
            for _ in range(3):  # 3 runs
                result = await benchmark_func(*args)
                results.append(result)

            # Calculate statistics
            if isinstance(results[0], dict):
                final_result = {}
                for key in results[0].keys():
                    if isinstance(results[0][key], (int, float)):
                        values = [r[key] for r in results]
                        final_result[key] = {
                            "mean": statistics.mean(values),
                            "std": statistics.stdev(values) if len(values) > 1 else 0,
                        }
                    else:
                        final_result[key] = results[0][key]

                return final_result
            return results[0]

        except Exception as e:
            return {"error": str(e)}

    async def run_all_benchmarks(self):
        """Run all benchmarks."""
        print("Starting Hash Verification Benchmarks")
        print("=" * 50)

        # Setup for main benchmarks
        setup_data = await self.setup_benchmark(1000, 16384)  # 1000 pieces, 16KB each

        try:
            # Sequential vs Parallel
            sequential_result = await self.run_benchmark(
                "Sequential Hashing",
                self.benchmark_sequential_hashing,
                setup_data,
            )
            self.results["Sequential Hashing"] = sequential_result

            parallel_result = await self.run_benchmark(
                "Parallel Hashing (4 workers)",
                self.benchmark_parallel_hashing,
                setup_data,
                4,
            )
            self.results["Parallel Hashing (4 workers)"] = parallel_result

            # Worker scaling
            worker_scaling = await self.run_benchmark(
                "Worker Scaling",
                self.benchmark_worker_scaling,
                setup_data,
            )
            self.results["Worker Scaling"] = worker_scaling

            # Piece size scaling
            piece_size_scaling = await self.run_benchmark(
                "Piece Size Scaling",
                self.benchmark_piece_size_scaling,
                1000,
            )
            self.results["Piece Size Scaling"] = piece_size_scaling

            # Memory efficiency
            memory_efficiency = await self.run_benchmark(
                "Memory Efficiency",
                self.benchmark_memory_efficiency,
                setup_data,
            )
            self.results["Memory Efficiency"] = memory_efficiency

            # Batch processing
            batch_processing = await self.run_benchmark(
                "Batch Processing",
                self.benchmark_batch_processing,
                setup_data,
            )
            self.results["Batch Processing"] = batch_processing

        finally:
            await self.cleanup_benchmark(setup_data)

        print("\n" + "=" * 50)
        print("Benchmark Summary:")
        for name, result in self.results.items():
            if "error" in result:
                print(f"  {name}: ERROR - {result['error']}")
            else:
                print(f"  {name}: Completed")

    def save_results(self, filename: str):
        """Save benchmark results to file."""
        import json

        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"Results saved to {filename}")


async def main():
    """Main benchmark function."""
    parser = argparse.ArgumentParser(description="Hash Verification Performance Benchmark")
    parser.add_argument("--output", "-o", default="hash_results.json",
                      help="Output file for results")
    args = parser.parse_args()

    benchmark = HashVerificationBenchmark()
    await benchmark.run_all_benchmarks()
    benchmark.save_results(args.output)


if __name__ == "__main__":
    asyncio.run(main())
