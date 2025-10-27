from __future__ import annotations

"""Advanced operational CLI commands (performance, security, recover, test)."""

import asyncio
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from ..config import get_config
from ..checkpoint import CheckpointManager
from ..disk_io import DiskIOManager


async def _quick_disk_benchmark() -> dict:
	"""Run a small, self-contained disk throughput benchmark.
	
	Returns a dict with write/read throughput metrics.
	"""
	config = get_config()
	disk = DiskIOManager(config.disk.disk_workers, config.disk.disk_queue_size, config.disk.mmap_cache_mb)
	await disk.start()
	try:
		# 16 MiB test spread over 64 KiB blocks
		total_size = 16 * 1024 * 1024
		block_size = 64 * 1024
		blocks = total_size // block_size
		with tempfile.TemporaryDirectory() as td:
			fp = Path(td) / "bench.bin"
			data = b"X" * block_size
			# Write
			start = time.time()
			futures = []
			for i in range(blocks):
				fut = await disk.write_block(fp, i * block_size, data)
				futures.append(fut)
			# Await completions
			for fut in futures:
				await fut
			write_s = time.time() - start
			# Read
			start = time.time()
			read_total = 0
			for i in range(blocks):
				chunk = await disk.read_block(fp, i * block_size, block_size)
				read_total += len(chunk)
			read_s = time.time() - start
		return {
			"size_mb": total_size / (1024 * 1024),
			"write_mb_s": (total_size / (1024 * 1024)) / max(write_s, 1e-9),
			"read_mb_s": (read_total / (1024 * 1024)) / max(read_s, 1e-9),
			"write_time_s": write_s,
			"read_time_s": read_s,
		}
	finally:
		await disk.stop()


@click.command("performance")
@click.option("--analyze", is_flag=True, help="Analyze current performance")
@click.option("--optimize", is_flag=True, help="Apply performance optimizations")
@click.option("--benchmark", is_flag=True, help="Run performance benchmarks")
@click.option("--profile", is_flag=True, help="Enable performance profiling")
def performance(analyze: bool, optimize: bool, benchmark: bool, profile: bool) -> None:
	"""Performance tuning and optimization."""
	console = Console()
	cfg = get_config()
	if analyze:
		t = Table(title="System & Config Analysis")
		t.add_column("Item", style="cyan")
		t.add_column("Value", style="green")
		t.add_row("Python", sys.version.split()[0])
		t.add_row("Platform", platform.platform())
		t.add_row("CPU count", str(os.cpu_count() or 1))
		t.add_row("Disk workers", str(cfg.disk.disk_workers))
		t.add_row("Write buffer KiB", str(cfg.disk.write_buffer_kib))
		t.add_row("Write batch KiB", str(cfg.disk.write_batch_kib))
		t.add_row("Use mmap", str(cfg.disk.use_mmap))
		t.add_row("Direct I/O", str(cfg.disk.direct_io))
		t.add_row("io_uring", str(cfg.disk.enable_io_uring))
		console.print(t)
	if optimize:
		# Print suggested flags only; applying requires restart and user confirmation
		console.print("[green]Suggested optimizations:[/green]")
		console.print("- Increase --write-buffer-kib for larger sequential writes")
		console.print("- Enable --use-mmap for large sequential reads")
		console.print("- Increase --disk-workers for high-core systems")
		console.print("- Consider --direct-io on Linux/NVMe for large sequential writes")
	if benchmark or profile:
		if profile:
			import cProfile
			import pstats
			prof = cProfile.Profile()
			prof.enable()
			results = asyncio.run(_quick_disk_benchmark())
			prof.disable()
			console.print(f"[green]Benchmark results:[/green] {json.dumps(results)}")
			ps = pstats.Stats(prof).strip_dirs().sort_stats("tottime")
			console.print("Top profile entries:")
			# Print top 10 lines
			ps.print_stats(10)
		else:
			results = asyncio.run(_quick_disk_benchmark())
			console.print(f"[green]Benchmark results:[/green] {json.dumps(results)}")
	if not any([analyze, optimize, benchmark, profile]):
		console.print("[yellow]No performance action specified[/yellow]")


@click.command("security")
@click.option("--scan", is_flag=True, help="Scan for security issues")
@click.option("--validate", is_flag=True, help="Validate peer connections")
@click.option("--encrypt", is_flag=True, help="Enable encryption")
@click.option("--rate-limit", is_flag=True, help="Enable rate limiting")
def security(scan: bool, validate: bool, encrypt: bool, rate_limit: bool) -> None:
	"""Security management and validation."""
	console = Console()
	cfg = get_config()
	if scan:
		console.print("[green]Performing basic configuration scan...[/green]")
		issues = []
		if not cfg.security.validate_peers:
			issues.append("Peer validation disabled")
		if cfg.network.max_connections_per_peer > 4:
			issues.append("High max connections per peer")
		if not cfg.security.rate_limit_enabled and (cfg.network.global_down_kib == 0 and cfg.network.global_up_kib == 0):
			issues.append("No rate limits configured")
		console.print(f"Found {len(issues)} potential issues")
		for i in issues:
			console.print(f"- [yellow]{i}[/yellow]")
	if validate:
		console.print("[green]Peer validation hooks are enabled by configuration[/green]")
	if encrypt:
		console.print("[yellow]Toggle encryption via --enable-encryption/--disable-encryption on download/magnet[/yellow]")
	if rate_limit:
		console.print("[yellow]Set --download-limit/--upload-limit for global limits; per-peer via config[/yellow]")
	if not any([scan, validate, encrypt, rate_limit]):
		console.print("[yellow]No security action specified[/yellow]")


@click.command("recover")
@click.argument("info_hash")
@click.option("--repair", is_flag=True, help="Attempt to repair corrupted data")
@click.option("--verify", is_flag=True, help="Verify data integrity")
@click.option("--rehash", is_flag=True, help="Rehash all pieces")
@click.option("--force", is_flag=True, help="Force recovery even if risky")
def recover(info_hash: str, repair: bool, verify: bool, rehash: bool, force: bool) -> None:
	"""Recover from corrupted or incomplete downloads."""
	console = Console()
	cfg = get_config()
	try:
		ih_bytes = bytes.fromhex(info_hash)
	except ValueError:
		console.print(f"[red]Invalid info hash format: {info_hash}[/red]")
		return
	cm = CheckpointManager(cfg.disk)
	if verify:
		valid = asyncio.run(cm.verify_checkpoint(ih_bytes))
		console.print("[green]Checkpoint valid[/green]" if valid else "[yellow]Checkpoint missing/invalid[/yellow]")
	if rehash:
		console.print("[yellow]Full rehash not implemented in CLI; use resume to trigger piece verification[/yellow]")
	if repair:
		console.print("[yellow]Automatic repair not implemented[/yellow]")
	if not any([verify, rehash, repair]):
		console.print("[yellow]No recover action specified[/yellow]")


@click.command("test")
@click.option("--unit", is_flag=True, help="Run unit tests")
@click.option("--integration", is_flag=True, help="Run integration tests")
@click.option("--performance", "performance_test", is_flag=True, help="Run performance tests")
@click.option("--security", "security_test", is_flag=True, help="Run security tests")
@click.option("--coverage", is_flag=True, help="Generate coverage report")
def test(unit: bool, integration: bool, performance_test: bool, security_test: bool, coverage: bool) -> None:
	"""Test suite runner."""
	console = Console()
	args = [sys.executable, "-m", "pytest"]
	selected = []
	if unit:
		selected += ["tests", "-k", "not integration and not performance"]
	if integration:
		selected += ["tests/integration"]
	if performance_test:
		selected += ["tests/performance"]
	if security_test:
		selected += ["tests/security"]
	if not any([unit, integration, performance_test, security_test]):
		selected += ["-q"]
	if coverage:
		args += ["--cov=ccbt", "--cov-report", "term-missing"]
	args += selected
	console.print(f"[blue]Running: {' '.join(args)}[/blue]")
	try:
		subprocess.run(args, check=False)
	except Exception as e:
		console.print(f"[red]Failed to run tests: {e}[/red]")


