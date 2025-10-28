"""Benchmark for loopback peer throughput.

Tests the performance of the async peer connection protocol
with loopback connections to measure maximum throughput.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from typing import Any

from ccbt.async_peer_connection import AsyncPeerConnectionManager
from ccbt.async_piece_manager import AsyncPieceManager
from ccbt.config import get_config
from ccbt.peer import PeerInfo


class ThroughputBenchmark:
    """Benchmark async peer connection throughput."""

    def __init__(self):
        self.config = get_config()
        self.results = {}

    async def setup_benchmark(self) -> dict[str, Any]:
        """Set up benchmark environment."""
        # Create temporary torrent data
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "file_info": {
                "name": "benchmark_file.bin",
                "total_length": 100 * 1024 * 1024,  # 100MB
                "type": "single",
            },
            "pieces_info": {
                "num_pieces": 6400,  # 100MB / 16KB pieces
                "piece_length": 16384,  # 16KB pieces
                "piece_hashes": [b"\x00" * 20] * 6400,
            },
        }

        # Create piece manager
        piece_manager = AsyncPieceManager(torrent_data)
        await piece_manager.start()

        # Create peer connection manager
        peer_manager = AsyncPeerConnectionManager(
            torrent_data,
            piece_manager,
            peer_id=b"-CC0101-" + b"x" * 12,
        )
        await peer_manager.start()

        return {
            "torrent_data": torrent_data,
            "piece_manager": piece_manager,
            "peer_manager": peer_manager,
        }

    async def cleanup_benchmark(self, setup_data: dict[str, Any]):
        """Clean up benchmark environment."""
        await setup_data["piece_manager"].stop()
        await setup_data["peer_manager"].shutdown()

    async def benchmark_message_throughput(
        self,
        setup_data: dict[str, Any],
    ) -> dict[str, float]:
        """Benchmark message throughput."""
        peer_manager = setup_data["peer_manager"]

        # Create mock peer connection
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()

        # Mock message data
        message_data = b"\x00\x00\x00\x01\x02"  # 5-byte message
        mock_reader.read.return_value = message_data

        # Benchmark message processing
        num_messages = 10000
        start_time = time.time()

        for _ in range(num_messages):
            await peer_manager._handle_message(mock_reader, mock_writer)

        end_time = time.time()

        duration = end_time - start_time
        messages_per_second = num_messages / duration

        return {
            "messages_per_second": messages_per_second,
            "duration": duration,
            "total_messages": num_messages,
        }

    async def benchmark_request_pipelining(
        self,
        setup_data: dict[str, Any],
    ) -> dict[str, float]:
        """Benchmark request pipelining performance."""
        peer_manager = setup_data["peer_manager"]

        # Create mock peer connection
        mock_connection = Mock()
        mock_connection.peer_info = PeerInfo("127.0.0.1", 6881)
        mock_connection.is_connected = True
        mock_connection.request_queue = asyncio.Queue()
        mock_connection.outstanding_requests = 0

        # Benchmark request queuing
        num_requests = 1000
        start_time = time.time()

        for i in range(num_requests):
            await peer_manager._queue_request(mock_connection, i % 100, 0, 16384)

        end_time = time.time()

        duration = end_time - start_time
        requests_per_second = num_requests / duration

        return {
            "requests_per_second": requests_per_second,
            "duration": duration,
            "total_requests": num_requests,
        }

    async def benchmark_concurrent_connections(
        self,
        setup_data: dict[str, Any],
    ) -> dict[str, float]:
        """Benchmark concurrent connection handling."""
        peer_manager = setup_data["peer_manager"]

        # Create multiple mock connections
        num_connections = 100
        connections = []

        for i in range(num_connections):
            peer_info = PeerInfo(f"127.0.0.{i + 1}", 6881)
            mock_connection = Mock()
            mock_connection.peer_info = peer_info
            mock_connection.is_connected = True
            mock_connection.request_queue = asyncio.Queue()
            mock_connection.outstanding_requests = 0
            connections.append(mock_connection)

        # Benchmark concurrent operations
        start_time = time.time()

        # Simulate concurrent operations
        tasks = []
        for connection in connections:
            task = asyncio.create_task(
                peer_manager._queue_request(connection, 0, 0, 16384),
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        end_time = time.time()

        duration = end_time - start_time
        operations_per_second = num_connections / duration

        return {
            "operations_per_second": operations_per_second,
            "duration": duration,
            "total_connections": num_connections,
        }

    async def benchmark_memory_usage(
        self,
        setup_data: dict[str, Any],
    ) -> dict[str, float]:
        """Benchmark memory usage patterns."""
        import gc

        import psutil

        # Force garbage collection
        gc.collect()

        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create many objects
        objects = []
        for i in range(10000):
            obj = {
                "id": i,
                "data": b"x" * 1000,
                "timestamp": time.time(),
            }
            objects.append(obj)

        # Get memory after object creation
        gc.collect()
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Clean up
        del objects
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        return {
            "initial_memory_mb": initial_memory,
            "peak_memory_mb": peak_memory,
            "final_memory_mb": final_memory,
            "memory_increase_mb": peak_memory - initial_memory,
        }

    async def run_benchmark(
        self,
        benchmark_name: str,
        benchmark_func,
    ) -> dict[str, float]:
        """Run a single benchmark."""
        setup_data = await self.setup_benchmark()

        try:
            # Run benchmark multiple times for accuracy
            results = []
            for _ in range(5):  # 5 runs
                result = await benchmark_func(setup_data)
                results.append(result)

            # Calculate statistics
            if "messages_per_second" in results[0]:
                values = [r["messages_per_second"] for r in results]
                mean_throughput = statistics.mean(values)
                std_throughput = statistics.stdev(values)
            elif "requests_per_second" in results[0]:
                values = [r["requests_per_second"] for r in results]
                mean_throughput = statistics.mean(values)
                std_throughput = statistics.stdev(values)
            elif "operations_per_second" in results[0]:
                values = [r["operations_per_second"] for r in results]
                mean_throughput = statistics.mean(values)
                std_throughput = statistics.stdev(values)
            else:
                mean_throughput = 0
                std_throughput = 0

            return {
                "mean_throughput": mean_throughput,
                "std_throughput": std_throughput,
                "runs": len(results),
                "raw_results": results,
            }

        finally:
            await self.cleanup_benchmark(setup_data)

    async def run_all_benchmarks(self):
        """Run all benchmarks."""
        benchmarks = [
            ("Message Throughput", self.benchmark_message_throughput),
            ("Request Pipelining", self.benchmark_request_pipelining),
            ("Concurrent Connections", self.benchmark_concurrent_connections),
            ("Memory Usage", self.benchmark_memory_usage),
        ]

        for name, func in benchmarks:
            try:
                result = await self.run_benchmark(name, func)
                self.results[name] = result

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
    parser = argparse.ArgumentParser(description="BitTorrent Throughput Benchmark")
    parser.add_argument(
        "--output",
        "-o",
        default="throughput_results.json",
        help="Output file for results",
    )
    args = parser.parse_args()

    benchmark = ThroughputBenchmark()
    await benchmark.run_all_benchmarks()
    benchmark.save_results(args.output)


if __name__ == "__main__":
    asyncio.run(main())
