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
import hashlib
import json
import os
import platform
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union

from ccbt.piece.piece_manager import PieceData, PieceManager  # type: ignore

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
    elapsed_s: float
    bytes_processed: int
    throughput_bytes_per_s: float


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


def generate_buffer(size: int) -> bytes:
    rng = random.Random(123456)
    return bytes(rng.getrandbits(8) for _ in range(size))


def run_case(size_bytes: int, iterations: int) -> BenchmarkResult:
    buf = generate_buffer(size_bytes)
    expected_hash = hashlib.sha1(buf).digest()

    piece = PieceData(piece_index=0, length=size_bytes)
    if piece.blocks:
        piece.blocks[0].data = buf
        piece.blocks[0].received = True
    piece.state = piece.state.COMPLETE  # type: ignore[attr-defined]

    torrent_data = {
        "pieces_info": {"num_pieces": 1, "piece_length": size_bytes, "piece_hashes": [expected_hash]},
        "file_info": {"total_length": size_bytes},
    }
    manager = PieceManager(torrent_data)

    start = time.perf_counter()
    total = 0
    for _ in range(iterations):
        ok = manager._hash_piece_optimized(piece, expected_hash)  # noqa: SLF001
        if not ok:
            _ = piece.verify_hash(expected_hash)
        total += size_bytes
    elapsed = time.perf_counter() - start
    throughput = total / max(elapsed, 1e-9)
    return BenchmarkResult(size_bytes=size_bytes, iterations=iterations, elapsed_s=elapsed, bytes_processed=total, throughput_bytes_per_s=throughput)


def ensure_artifacts_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def write_json(output_dir: Path, benchmark: str, config_name: str, results: List[BenchmarkResult]) -> Path:
    """Legacy function for backward compatibility."""
    meta = {
        "benchmark": benchmark,
        "config": config_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": {"system": platform.system(), "release": platform.release(), "python": sys.version.split()[0]},
    }
    data = {"meta": meta, "results": [asdict(r) for r in results]}
    filename = f"{benchmark}-{config_name}-{platform.system()}-{platform.release()}.json"
    path = output_dir / filename
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def derive_config_name(config_file: str | None) -> str:
    if not config_file:
        return "default"
    stem = Path(config_file).stem
    parts = stem.split("example-config-")
    if len(parts) == 2 and parts[1]:
        return parts[1]
    return stem


def main() -> int:
    parser = argparse.ArgumentParser(description="SHA1 hash verify benchmark")
    parser.add_argument("--sizes", nargs="*", default=["1MiB", "4MiB", "16MiB"], help="Buffer sizes")
    parser.add_argument("--iterations", type=int, default=64, help="Iterations per size")
    parser.add_argument("--quick", action="store_true", help="Run minimal quick mode")
    parser.add_argument("--config-file", default=None, help="Path to client config used (for labeling only)")
    parser.add_argument(
        "--output-dir",
        default="site/reports/benchmarks/artifacts",
        help="Output directory for artifacts (deprecated, use --record-mode)",
    )
    parser.add_argument(
        "--record-mode",
        choices=["auto", "pre-commit", "commit", "both", "none"],
        default="auto",
        help="Recording mode: auto (detect), pre-commit, commit, both, or none",
    )

    args = parser.parse_args()

    sizes = [parse_size(s) for s in args.sizes]
    iterations = 8 if args.quick else args.iterations

    results: List[BenchmarkResult] = []
    for size in sizes:
        results.append(run_case(size, iterations))

    print(" | ".join(("Size", "Iterations", "Elapsed (s)", "Throughput")))
    print("-" * 64)
    for r in results:
        print(" | ".join([format_bytes(r.size_bytes), str(r.iterations), f"{r.elapsed_s:.3f}", f"{r.throughput_bytes_per_s/ (1024**2):.2f} MiB/s"]))

    config_name = derive_config_name(args.config_file)

    # Record benchmark results using new system
    per_run_path, timeseries_path = record_benchmark_results("hash_verify", config_name, results, args.record_mode)

    # Backward compatibility: write to old location if --output-dir specified
    if args.output_dir and args.output_dir != "site/reports/benchmarks/artifacts":
        output_dir = Path(args.output_dir)
        ensure_artifacts_dir(output_dir)
        out_path = write_json(output_dir, "hash_verify", config_name, results)
        print(f"\nWrote (legacy): {out_path}")

    # Print recording results
    if per_run_path:
        print(f"\nRecorded per-run: {per_run_path}")
    if timeseries_path:
        print(f"Updated timeseries: {timeseries_path}")
    if not per_run_path and not timeseries_path:
        print("\nNo benchmark recording (mode: none or auto detected none)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


