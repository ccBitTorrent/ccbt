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
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from ccbt.storage.file_assembler import AsyncFileAssembler  # type: ignore
from ccbt.models import TorrentInfo, FileInfo  # type: ignore

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
	piece_size_bytes: int
	block_size_bytes: int
	blocks: int
	elapsed_s: float
	throughput_bytes_per_s: float


def parse_size(size_str: str) -> int:
	suffixes = [("gib", 1024 ** 3), ("gb", 1024 ** 3), ("mib", 1024 ** 2), ("mb", 1024 ** 2), ("kib", 1024), ("kb", 1024), ("b", 1)]
	s = size_str.strip().lower()
	for suf, mul in suffixes:
		if s.endswith(suf):
			return int(float(s[:-len(suf)]) * mul)
	return int(s)


def run_case(piece_size: int, block_size: int) -> Result:
	blocks = (piece_size + block_size - 1) // block_size
	data = os.urandom(piece_size)
	view = memoryview(data)

	torrent_data = TorrentInfo(
		name="bench",
		info_hash=b"0" * 20,
		announce="http://localhost/announce",
		files=[FileInfo(name="bench.bin", length=piece_size)],
		total_length=piece_size,
		piece_length=piece_size,
		pieces=[hashlib.sha1(view).digest()],
		num_pieces=1,
	)

	start = time.perf_counter()
	with tempfile.TemporaryDirectory() as td:
		assembler = AsyncFileAssembler(torrent_data, td)
		async def _go() -> None:
			async with assembler:
				await assembler.write_piece_to_file(0, view)
		import asyncio as _asyncio
		_asyncio.run(_go())

	elapsed = time.perf_counter() - start
	tput = piece_size / max(elapsed, 1e-9)
	return Result(piece_size, block_size, blocks, elapsed, tput)


def print_table(results: List[Result]) -> None:
	print("Piece | Block | Blocks | Elapsed (s) | Throughput")
	print("-" * 72)
	for r in results:
		print(" | ".join([f"{r.piece_size_bytes}", f"{r.block_size_bytes}", str(r.blocks), f"{r.elapsed_s:.3f}", f"{r.throughput_bytes_per_s / (1024**2):.2f} MiB/s"]))


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
	parser = argparse.ArgumentParser(description="Piece assembly benchmark")
	parser.add_argument("--piece-sizes", nargs="*", default=["1MiB", "4MiB"], help="Piece sizes")
	parser.add_argument("--block-size", default="16KiB", help="Block size")
	parser.add_argument("--quick", action="store_true", help="Quick mode")
	parser.add_argument("--config-file", default=None, help="Label config used")
	parser.add_argument("--output-dir", default="site/reports/benchmarks/artifacts", help="Artifacts output dir (deprecated)")
	parser.add_argument(
		"--record-mode",
		choices=["auto", "pre-commit", "commit", "both", "none"],
		default="auto",
		help="Recording mode: auto (detect), pre-commit, commit, both, or none",
	)

	args = parser.parse_args()
	piece_sizes = [parse_size(s) for s in args.piece_sizes]
	block_size = parse_size(args.block_size)
	if args.quick:
		piece_sizes = piece_sizes[:1]

	results = [run_case(ps, block_size) for ps in piece_sizes]
	print_table(results)

	output_dir = Path(args.output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)
	cfg = derive_config_name(args.config_file)
	
	# Record benchmark results using new system
	per_run_path, timeseries_path = record_benchmark_results("piece_assembly", cfg, results, args.record_mode)
	
	# Backward compatibility
	out = write_json(output_dir, "piece_assembly", cfg, results)
	print(f"\nWrote (legacy): {out}")
	
	# Print recording results
	if per_run_path:
		print(f"Recorded per-run: {per_run_path}")
	if timeseries_path:
		print(f"Updated timeseries: {timeseries_path}")
	
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
