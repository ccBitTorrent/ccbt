#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

# Add project root to path for imports when run as script
# This must be done before any local imports
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_script_dir, os.pardir, os.pardir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import argparse
import asyncio
import json
import platform
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union

from ccbt.storage.disk_io import DiskIOManager  # type: ignore

# Import bench_utils using relative import or direct import
try:
    from tests.performance.bench_utils import record_benchmark_results
except ImportError:
    # Fallback: import directly from same directory
    import importlib.util
    _bench_utils_path = os.path.join(os.path.dirname(__file__), "bench_utils.py")
    _spec = importlib.util.spec_from_file_location("bench_utils", _bench_utils_path)
    _bench_utils = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_bench_utils)  # type: ignore
    record_benchmark_results = _bench_utils.record_benchmark_results


@dataclass
class BenchmarkResult:
    size_bytes: int
    iterations: int
    write_elapsed_s: float
    read_elapsed_s: float
    write_throughput_bytes_per_s: float
    read_throughput_bytes_per_s: float


def parse_size(size_str: str) -> int:
    suffixes = [("gib", 1024 ** 3), ("gb", 1024 ** 3), ("mib", 1024 ** 2), ("mb", 1024 ** 2), ("kib", 1024), ("kb", 1024), ("b", 1)]
    s = size_str.strip().lower()
    for suf, mul in suffixes:
        if s.endswith(suf):
            return int(float(s[:-len(suf)]) * mul)
    return int(s)


def format_bytes(n: Union[int, float]) -> str:
    value: float = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024.0 or unit == "GiB":  # type: ignore[comparison-overlap]
            # Format with appropriate precision
            if value.is_integer():
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value = value / 1024.0
    return f"{value} B"


async def run_case(size_bytes: int, iterations: int) -> BenchmarkResult:
    """Run a disk I/O benchmark case."""
    manager = DiskIOManager()
    await manager.start()
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "bench.bin"
            data = b"X" * size_bytes
            
            # Write benchmark
            write_start = time.perf_counter()
            write_total = 0
            for _ in range(iterations):
                future = await manager.write_block(test_file, 0, data)
                await future  # Ensure write completes
                write_total += size_bytes
            write_elapsed = time.perf_counter() - write_start
            
            # Read benchmark
            read_start = time.perf_counter()
            read_total = 0
            for _ in range(iterations):
                chunk = await manager.read_block(test_file, 0, size_bytes)
                read_total += len(chunk)
            read_elapsed = time.perf_counter() - read_start
            
            write_throughput = write_total / max(write_elapsed, 1e-9)
            read_throughput = read_total / max(read_elapsed, 1e-9)
            
            result = BenchmarkResult(
                size_bytes=size_bytes,
                iterations=iterations,
                write_elapsed_s=write_elapsed,
                read_elapsed_s=read_elapsed,
                write_throughput_bytes_per_s=write_throughput,
                read_throughput_bytes_per_s=read_throughput,
            )
            
            # Note: Stop manager and close all file handles BEFORE temp directory cleanup
            # This prevents Windows file locking issues (PermissionError [WinError 32])
            # Force flush all pending operations first
            if hasattr(manager, '_flush_all_writes'):
                try:
                    await asyncio.wait_for(manager._flush_all_writes(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass  # Continue with stop() anyway
            
            # Stop the manager to close all file handles
            await manager.stop()
            
            # Windows-specific: Give file handles additional time to close
            if sys.platform == "win32":
                await asyncio.sleep(0.2)
            
            # Explicitly delete the test file to ensure it's released
            # This is a safety measure - the file should already be closed by manager.stop()
            try:
                if test_file.exists():
                    test_file.unlink()
            except Exception:
                pass  # File may already be deleted or locked, which is fine
            
            # Additional wait for Windows to fully release file handles
            if sys.platform == "win32":
                await asyncio.sleep(0.1)
            
            return result
    finally:
        # Ensure manager is stopped even if an exception occurs
        # (though it should already be stopped above)
        try:
            if manager._running:  # type: ignore[attr-defined]
                await manager.stop()
        except Exception:
            pass  # Manager may already be stopped


def print_table(results: List[BenchmarkResult]) -> None:
    print("Size | Iterations | Write Elapsed (s) | Read Elapsed (s) | Write Throughput | Read Throughput")
    print("-" * 100)
    for r in results:
        size_str = format_bytes(r.size_bytes)
        write_tput = f"{r.write_throughput_bytes_per_s / (1024**2):.2f} MiB/s"
        read_tput = f"{r.read_throughput_bytes_per_s / (1024**2):.2f} MiB/s"
        print(f"{size_str} | {r.iterations} | {r.write_elapsed_s:.3f} | {r.read_elapsed_s:.3f} | {write_tput} | {read_tput}")


def write_json(output_dir: Path, benchmark: str, config_name: str, results: List[BenchmarkResult]) -> Path:
    meta = {
        "benchmark": benchmark,
        "config": config_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
        },
    }
    data = {"meta": meta, "results": [asdict(r) for r in results]}
    filename = f"{benchmark}-{config_name}-{platform.system()}-{platform.release()}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Disk I/O performance benchmark")
    parser.add_argument(
        "--sizes",
        nargs="+",
        default=["256KiB", "1MiB", "4MiB"],
        help="Sizes to test (default: 256KiB 1MiB 4MiB)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations per size (default: 10)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: fewer iterations and smaller sizes",
    )
    parser.add_argument(
        "--config-file",
        type=str,
        help="Config file path (for recording mode detection)",
    )
    parser.add_argument(
        "--record-mode",
        type=str,
        default="auto",
        choices=["auto", "pre-commit", "commit", "both", "none"],
        help="Recording mode for benchmark results",
    )
    
    args = parser.parse_args()
    
    # Quick mode adjustments
    if args.quick:
        sizes = ["256KiB", "1MiB"]
        iterations = 5
    else:
        sizes = args.sizes
        iterations = args.iterations
    
    # Parse sizes
    size_bytes_list = [parse_size(s) for s in sizes]
    
    # Run benchmarks
    results: List[BenchmarkResult] = []
    for size_bytes in size_bytes_list:
        result = asyncio.run(run_case(size_bytes, iterations))
        results.append(result)
    
    # Print results
    print_table(results)
    
    # Record results
    config_name = "default"
    if args.config_file:
        config_name = Path(args.config_file).stem
    
    per_run_path, timeseries_path = record_benchmark_results(
        benchmark_name="disk_io",
        config_name=config_name,
        results=results,
        record_mode=args.record_mode,
    )
    
    # Also write legacy format for compatibility
    legacy_output_dir = Path("site/reports/benchmarks/artifacts")
    if legacy_output_dir.exists() or args.record_mode != "none":
        legacy_path = write_json(legacy_output_dir, "disk_io", config_name, results)
        print(f"\nWrote (legacy): {legacy_path}")
    
    if per_run_path:
        print(f"Recorded per-run: {per_run_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())








