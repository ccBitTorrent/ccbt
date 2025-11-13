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
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

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
class Result:
	payload_bytes: int
	pipeline_depth: int
	duration_s: float
	bytes_transferred: int
	throughput_bytes_per_s: float
	stall_percent: float


async def run_case(payload_bytes: int, pipeline_depth: int, seconds: float) -> Result:
	queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=pipeline_depth)
	payload = b"x" * payload_bytes
	start = time.perf_counter()
	stalls = 0

	async def timed_producer() -> None:
		nonlocal stalls
		while (time.perf_counter() - start) < seconds:
			try:
				queue.put_nowait(payload)
			except asyncio.QueueFull:
				stalls += 1
				await asyncio.sleep(0)
		await queue.put(b"")

	async def timed_consumer() -> int:
		total = 0
		while True:
			chunk = await queue.get()
			if not chunk:
				break
			total += len(chunk)
			queue.task_done()
		return total

	producer_task = asyncio.create_task(timed_producer())
	consumer_task = asyncio.create_task(timed_consumer())
	transferred = await consumer_task
	await producer_task
	elapsed = max(1e-9, time.perf_counter() - start)
	throughput = transferred / elapsed
	stall_pct = (stalls / (stalls + (transferred // max(1, payload_bytes)) + 1)) * 100.0
	return Result(payload_bytes, pipeline_depth, elapsed, transferred, throughput, stall_pct)


def print_table(results: List[Result]) -> None:
	print("Payload | Pipeline | Duration (s) | Throughput | Stall %")
	print("-" * 72)
	for r in results:
		print(" | ".join([str(r.payload_bytes), str(r.pipeline_depth), f"{r.duration_s:.2f}", f"{r.throughput_bytes_per_s / (1024**2):.2f} MiB/s", f"{r.stall_percent:.2f}"]))


def write_json(output_dir: Path, benchmark: str, config_name: str, results: List[Result]) -> Path:
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
	parser = argparse.ArgumentParser(description="Loopback throughput benchmark")
	parser.add_argument("--payloads", nargs="*", default=["16KiB", "64KiB"], help="Payload sizes")
	parser.add_argument("--pipelines", nargs="*", default=["8", "128"], help="Pipeline depths")
	parser.add_argument("--seconds", type=float, default=3.0, help="Duration per case")
	parser.add_argument("--quick", action="store_true", help="Quick mode (short, fewer cases)")
	parser.add_argument("--config-file", default=None, help="Label config used")
	parser.add_argument("--output-dir", default="site/reports/benchmarks/artifacts", help="Artifacts output dir (deprecated)")
	parser.add_argument(
		"--record-mode",
		choices=["auto", "pre-commit", "commit", "both", "none"],
		default="auto",
		help="Recording mode: auto (detect), pre-commit, commit, both, or none",
	)

	args = parser.parse_args()

	def parse_size(s: str) -> int:
		s = s.lower()
		if s.endswith("kib"):
			return int(float(s[:-3]) * 1024)
		if s.endswith("kb"):
			return int(float(s[:-2]) * 1024)
		return int(s)

	payloads = [parse_size(s) for s in args.payloads]
	pipelines = [int(p) for p in args.pipelines]
	seconds = 1.0 if args.quick else args.seconds

	if args.quick:
		payloads = payloads[:1]
		pipelines = pipelines[:1]

	results: List[Result] = []
	for payload in payloads:
		for pipe in pipelines:
			res = asyncio.run(run_case(payload, pipe, seconds))
			results.append(res)

	print_table(results)
	output_dir = Path(args.output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)
	cfg = derive_config_name(args.config_file)
	
	# Record benchmark results using new system
	per_run_path, timeseries_path = record_benchmark_results("loopback_throughput", cfg, results, args.record_mode)
	
	# Backward compatibility
	out = write_json(output_dir, "loopback_throughput", cfg, results)
	print(f"\nWrote (legacy): {out}")
	
	# Print recording results
	if per_run_path:
		print(f"Recorded per-run: {per_run_path}")
	if timeseries_path:
		print(f"Updated timeseries: {timeseries_path}")
	
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
