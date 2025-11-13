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
import json
import os
import platform
import random
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

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
class OpResult:
	pattern: str
	size_bytes: int
	ops: int
	elapsed_s: float
	throughput_bytes_per_s: float
	p50_ms: float
	p95_ms: float
	p99_ms: float


def parse_size(size_str: str) -> int:
	suffixes = [("gib", 1024 ** 3), ("gb", 1024 ** 3), ("mib", 1024 ** 2), ("mb", 1024 ** 2), ("kib", 1024), ("kb", 1024), ("b", 1)]
	s = size_str.strip().lower()
	for suf, mul in suffixes:
		if s.endswith(suf):
			return int(float(s[:-len(suf)]) * mul)
	return int(s)


def quantiles_ms(samples: List[float]) -> Tuple[float, float, float]:
	if not samples:
		return (0.0, 0.0, 0.0)
	xs = sorted(samples)
	def q(p: float) -> float:
		idx = max(0, min(len(xs)-1, int(p * (len(xs)-1))))
		return xs[idx] * 1000.0
	return (q(0.5), q(0.95), q(0.99))


async def seq_write(tmp_path: Path, size: int, ops: int) -> OpResult:
	buf = os.urandom(size)
	latencies: List[float] = []
	start = time.perf_counter()
	total = 0
	manager = DiskIOManager()
	await manager.start()
	try:
		for i in range(ops):
			t0 = time.perf_counter()
			fut = await manager.write_block(tmp_path, i * size, buf)
			await fut
			latencies.append(time.perf_counter() - t0)
			total += len(buf)
		await manager._flush_all_writes()  # noqa: SLF001
	finally:
		await manager.stop()
	elapsed = time.perf_counter() - start
	p50, p95, p99 = quantiles_ms(latencies)
	tput = total / elapsed if elapsed > 0 else 0.0
	return OpResult("seq-write", size, ops, elapsed, tput, p50, p95, p99)


async def seq_read(tmp_path: Path, size: int, ops: int) -> OpResult:
	latencies: List[float] = []
	start = time.perf_counter()
	total = 0
	manager = DiskIOManager()
	await manager.start()
	try:
		offset = 0
		for _ in range(ops):
			t0 = time.perf_counter()
			data = await manager.read_block(tmp_path, offset, size)
			latencies.append(time.perf_counter() - t0)
			total += len(data)
			offset += size
	finally:
		await manager.stop()
	elapsed = time.perf_counter() - start
	p50, p95, p99 = quantiles_ms(latencies)
	tput = total / elapsed if elapsed > 0 else 0.0
	return OpResult("seq-read", size, ops, elapsed, tput, p50, p95, p99)


async def rand_read(tmp_path: Path, size: int, ops: int) -> OpResult:
	latencies: List[float] = []
	file_size = tmp_path.stat().st_size
	rng = random.Random(123456)
	start = time.perf_counter()
	total = 0
	manager = DiskIOManager()
	await manager.start()
	try:
		for _ in range(ops):
			off = rng.randrange(0, max(1, file_size - size))
			t0 = time.perf_counter()
			data = await manager.read_block(tmp_path, off, size)
			latencies.append(time.perf_counter() - t0)
			total += len(data)
	finally:
		await manager.stop()
	elapsed = time.perf_counter() - start
	p50, p95, p99 = quantiles_ms(latencies)
	tput = total / elapsed if elapsed > 0 else 0.0
	return OpResult("rand-read", size, ops, elapsed, tput, p50, p95, p99)


def print_table(results: List[OpResult]) -> None:
	print("Pattern | Size | Ops | Elapsed (s) | Throughput | p50 (ms) | p95 (ms) | p99 (ms)")
	print("-" * 96)
	for r in results:
		print(" | ".join([r.pattern, f"{r.size_bytes} B", str(r.ops), f"{r.elapsed_s:.3f}", format_bytes(r.throughput_bytes_per_s), f"{r.p50_ms:.2f}", f"{r.p95_ms:.2f}", f"{r.p99_ms:.2f}"]))


def format_bytes(n: float) -> str:
	unit = "B/s"
	v = n
	for u in ("B/s", "KiB/s", "MiB/s", "GiB/s"):
		unit = u
		if v < 1024 or u == "GiB/s":
			break
		v /= 1024
	return f"{v:.2f} {unit}"


def write_json(output_dir: Path, benchmark: str, config_name: str, results: List[OpResult]) -> Path:
	meta = {"benchmark": benchmark, "config": config_name, "timestamp": datetime.now(timezone.utc).isoformat(), "platform": {"system": platform.system(), "release": platform.release(), "python": sys.version.split()[0]}}
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
	parser = argparse.ArgumentParser(description="Disk I/O benchmark")
	parser.add_argument("--sizes", nargs="*", default=["256KiB", "1MiB", "4MiB"], help="Buffer sizes")
	parser.add_argument("--ops", type=int, default=200, help="Operations per pattern")
	parser.add_argument("--patterns", nargs="*", default=["seq-write", "seq-read", "rand-read"], help="Patterns")
	parser.add_argument("--quick", action="store_true", help="Run minimal quick mode")
	parser.add_argument("--config-file", default=None, help="Label for configuration used")
	parser.add_argument("--output-dir", default="site/reports/benchmarks/artifacts", help="Artifacts output dir (deprecated)")
	parser.add_argument(
		"--record-mode",
		choices=["auto", "pre-commit", "commit", "both", "none"],
		default="auto",
		help="Recording mode: auto (detect), pre-commit, commit, both, or none",
	)

	args = parser.parse_args()
	sizes = [parse_size(s) for s in args.sizes]
	ops = 50 if args.quick else args.ops

	output_dir = Path(args.output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)

	results: List[OpResult] = []
	import asyncio as _asyncio
	with tempfile.TemporaryDirectory() as td:
		tp = Path(td) / "bench.tmp"
		async def _prefill() -> None:
			manager = DiskIOManager()
			await manager.start()
			try:
				chunk = os.urandom(max(sizes))
				offset = 0
				for _ in range(max(1, ops // 10)):
					fut = await manager.write_block(tp, offset, chunk)
					await fut
					offset += len(chunk)
				await manager._flush_all_writes()  # noqa: SLF001
			finally:
				await manager.stop()

		_asyncio.run(_prefill())

		for size in sizes:
			if "seq-write" in args.patterns:
				results.append(_asyncio.run(seq_write(tp, size, ops)))
			if "seq-read" in args.patterns:
				results.append(_asyncio.run(seq_read(tp, size, ops)))
			if "rand-read" in args.patterns:
				results.append(_asyncio.run(rand_read(tp, size, ops)))

	print_table(results)
	cfg = derive_config_name(args.config_file)
	
	# Record benchmark results using new system
	per_run_path, timeseries_path = record_benchmark_results("disk_io", cfg, results, args.record_mode)
	
	# Backward compatibility
	out = write_json(output_dir, "disk_io", cfg, results)
	print(f"\nWrote (legacy): {out}")
	
	# Print recording results
	if per_run_path:
		print(f"Recorded per-run: {per_run_path}")
	if timeseries_path:
		print(f"Updated timeseries: {timeseries_path}")
	
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
