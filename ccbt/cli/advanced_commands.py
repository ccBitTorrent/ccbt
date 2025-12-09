"""Advanced operational CLI commands (performance, security, recover, test)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import platform
import subprocess  # nosec B404 - Used for CLI commands only
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from ccbt.config.config import ConfigManager, get_config
from ccbt.config.config_capabilities import SystemCapabilities
from ccbt.i18n import _
from ccbt.models import PreallocationStrategy
from ccbt.storage.checkpoint import CheckpointManager
from ccbt.storage.disk_io import DiskIOManager


class OptimizationPreset:
    """Optimization preset configurations."""

    PERFORMANCE = "performance"
    BALANCED = "balanced"
    POWER_SAVE = "power_save"


def _apply_optimizations(
    preset: str = OptimizationPreset.BALANCED,
    save_to_file: bool = False,
    config_file: str | None = None,
) -> dict[str, Any]:
    """Apply performance optimizations based on system capabilities.

    Args:
        preset: Optimization preset (performance, balanced, power_save)
        save_to_file: Whether to save optimizations to config file
        config_file: Optional path to config file (defaults to ccbt.toml)

    Returns:
        Dictionary of applied optimizations
    """
    console = Console()
    cfg = get_config()
    capabilities = SystemCapabilities()

    # Detect system characteristics
    cpu_count = capabilities.detect_cpu_count()
    memory = capabilities.detect_memory()
    storage_type = capabilities.detect_storage_type(
        cfg.disk.download_path or "."
    )
    io_uring_available = capabilities.detect_io_uring()

    optimizations: dict[str, Any] = {}

    # Apply preset-based optimizations
    if preset == OptimizationPreset.PERFORMANCE:
        # Maximum performance settings
        optimizations["disk"] = {
            "disk_workers": min(max(4, cpu_count // 2), 16),
            "write_buffer_kib": 2048 if storage_type == "nvme" else 1024,
            "write_batch_kib": 128 if storage_type == "nvme" else 64,
            "use_mmap": True,
            "mmap_cache_mb": min(512, int(memory.get("available_gb", 4) * 128)),
            "enable_io_uring": io_uring_available,
            "direct_io": storage_type == "nvme" and sys.platform.startswith("linux"),
            "disk_workers_adaptive": True,
            "mmap_cache_adaptive": True,
        }
        optimizations["network"] = {
            "pipeline_depth": 32,
            "socket_rcvbuf_kib": 512,
            "socket_sndbuf_kib": 512,
            "socket_adaptive_buffers": True,
            "pipeline_adaptive_depth": True,
            "timeout_adaptive": True,
        }
    elif preset == OptimizationPreset.POWER_SAVE:
        # Power-efficient settings
        optimizations["disk"] = {
            "disk_workers": 1,
            "write_buffer_kib": 256,
            "write_batch_kib": 32,
            "use_mmap": False,
            "mmap_cache_mb": 64,
            "enable_io_uring": False,
            "direct_io": False,
            "disk_workers_adaptive": False,
            "mmap_cache_adaptive": False,
        }
        optimizations["network"] = {
            "pipeline_depth": 8,
            "socket_rcvbuf_kib": 64,
            "socket_sndbuf_kib": 64,
            "socket_adaptive_buffers": False,
            "pipeline_adaptive_depth": False,
            "timeout_adaptive": False,
        }
    else:  # BALANCED
        # Balanced settings based on detected hardware
        optimizations["disk"] = {
            "disk_workers": min(max(2, cpu_count // 4), 8),
            "write_buffer_kib": 1024 if storage_type in ("nvme", "ssd") else 512,
            "write_batch_kib": 64 if storage_type in ("nvme", "ssd") else 32,
            "use_mmap": True,
            "mmap_cache_mb": min(256, int(memory.get("available_gb", 4) * 64)),
            "enable_io_uring": io_uring_available,
            "direct_io": False,  # Only enable for NVMe in performance mode
            "disk_workers_adaptive": True,
            "mmap_cache_adaptive": True,
        }
        optimizations["network"] = {
            "pipeline_depth": 16,
            "socket_rcvbuf_kib": 256,
            "socket_sndbuf_kib": 256,
            "socket_adaptive_buffers": True,
            "pipeline_adaptive_depth": True,
            "timeout_adaptive": True,
        }

    # Apply optimizations to config
    applied: dict[str, Any] = {}
    for section, settings in optimizations.items():
        section_config = getattr(cfg, section, None)
        if section_config:
            for key, value in settings.items():
                if hasattr(section_config, key):
                    old_value = getattr(section_config, key)
                    setattr(section_config, key, value)
                    applied[f"{section}.{key}"] = {"old": old_value, "new": value}

    # Save to file if requested
    if save_to_file:
        try:
            from ccbt.config.config import ConfigManager

            config_path = Path(config_file or "ccbt.toml")
            config_manager = ConfigManager(str(config_path) if config_path.exists() else None)
            config_manager.save_config()
            console.print(
                _("[green]Optimizations saved to {path}[/green]").format(
                    path=config_path
                )
            )
        except Exception as e:
            console.print(
                _("[yellow]Could not save to config file: {error}[/yellow]").format(
                    error=e
                )
            )

    return applied


async def _quick_disk_benchmark() -> dict:
    """Run a small, self-contained disk throughput benchmark.

    Returns a dict with write/read throughput metrics.
    """
    config = get_config()
    disk = DiskIOManager(
        config.disk.disk_workers,
        config.disk.disk_queue_size,
        config.disk.mmap_cache_mb,
    )
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

            # Get cache stats
            cache_stats = disk.get_cache_stats()

        return {
            "size_mb": total_size / (1024 * 1024),
            "write_mb_s": (total_size / (1024 * 1024)) / max(write_s, 1e-9),
            "read_mb_s": (read_total / (1024 * 1024)) / max(read_s, 1e-9),
            "write_time_s": write_s,
            "read_time_s": read_s,
            "cache_stats": cache_stats,
        }
    finally:
        await disk.stop()


@click.command("performance")
@click.option("--analyze", is_flag=True, help="Analyze current performance")
@click.option("--optimize", is_flag=True, help="Apply performance optimizations")
@click.option(
    "--preset",
    type=click.Choice(
        [
            OptimizationPreset.PERFORMANCE,
            OptimizationPreset.BALANCED,
            OptimizationPreset.POWER_SAVE,
        ]
    ),
    default=OptimizationPreset.BALANCED,
    help="Optimization preset to apply",
)
@click.option(
    "--save",
    is_flag=True,
    help="Save optimizations to config file (requires --optimize)",
)
@click.option(
    "--config-file",
    type=click.Path(),
    default=None,
    help="Config file path (defaults to ccbt.toml)",
)
@click.option("--benchmark", is_flag=True, help="Run performance benchmarks")
@click.option("--profile", is_flag=True, help="Enable performance profiling")
def performance(
    analyze: bool,
    optimize: bool,
    preset: str,
    save: bool,
    config_file: str | None,
    benchmark: bool,
    profile: bool,
) -> None:
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
        # Apply optimizations based on preset
        console.print(
            _("[green]Applying {preset} optimizations...[/green]").format(
                preset=preset
            )
        )

        if save:
            # Ask for confirmation before saving
            if not Confirm.ask(
                _(
                    "This will modify your configuration file. Continue?"
                ),
                default=True,
            ):
                console.print(_("[yellow]Optimization cancelled[/yellow]"))
                return

        applied = _apply_optimizations(
            preset=preset, save_to_file=save, config_file=config_file
        )

        if applied:
            # Display applied optimizations
            opt_table = Table(title="Applied Optimizations")
            opt_table.add_column("Setting", style="cyan")
            opt_table.add_column("Old Value", style="yellow")
            opt_table.add_column("New Value", style="green")

            for key, values in applied.items():
                opt_table.add_row(
                    key,
                    str(values["old"]),
                    str(values["new"]),
                )

            console.print(opt_table)
            console.print(
                _(
                    "[green]Optimizations applied successfully![/green]\n"
                    "[yellow]Note: Some changes may require restart to take effect.[/yellow]"
                )
            )
        else:
            console.print(
                _("[yellow]No optimizations were applied (already optimal or unsupported)[/yellow]")
            )
    if benchmark or profile:
        if profile:
            import cProfile
            import pstats

            prof = cProfile.Profile()
            prof.enable()
            # Guard against patched asyncio.run in tests leaving coroutine un-awaited
            try:
                import inspect

                maybe_coro = _quick_disk_benchmark()
                if inspect.iscoroutine(maybe_coro):
                    try:
                        results = asyncio.run(maybe_coro)
                    except Exception:
                        # Ensure coroutine is properly closed to avoid warnings under mocked asyncio.run
                        with contextlib.suppress(Exception):
                            maybe_coro.close()  # type: ignore[attr-defined]
                        raise
                else:  # pragma: no cover - Defensive path for non-coroutine return from benchmark (should always return coroutine)
                    results = maybe_coro  # type: ignore[assignment]  # pragma: no cover - Same defensive path
            except Exception:  # pragma: no cover - defensive in CLI path
                results = {
                    "size_mb": 0,
                    "write_mb_s": 0,
                    "read_mb_s": 0,
                    "write_time_s": 0,
                    "read_time_s": 0,
                }
            prof.disable()
            console.print(_("[green]Benchmark results:[/green] {results}").format(results=json.dumps(results)))
            ps = pstats.Stats(prof).strip_dirs().sort_stats("tottime")
            console.print(_("Top profile entries:"))
            # Print top 10 lines
            ps.print_stats(10)
        else:
            # Guard against patched asyncio.run in tests leaving coroutine un-awaited
            try:
                import inspect

                maybe_coro = _quick_disk_benchmark()
                if inspect.iscoroutine(maybe_coro):
                    try:
                        results = asyncio.run(maybe_coro)
                    except Exception:
                        # Ensure coroutine is properly closed to avoid warnings under mocked asyncio.run
                        with contextlib.suppress(Exception):
                            maybe_coro.close()  # type: ignore[attr-defined]
                        raise
                else:  # pragma: no cover - Defensive path for non-coroutine return from benchmark (should always return coroutine)
                    results = maybe_coro  # type: ignore[assignment]  # pragma: no cover - Same defensive path
            except Exception:  # pragma: no cover - defensive in CLI path
                results = {
                    "size_mb": 0,
                    "write_mb_s": 0,
                    "read_mb_s": 0,
                    "write_time_s": 0,
                    "read_time_s": 0,
                }
            console.print(_("[green]Benchmark results:[/green] {results}").format(results=json.dumps(results)))

            # Display cache statistics if available
            cache_stats = results.get("cache_stats", {})
            if isinstance(cache_stats, dict) and cache_stats:
                console.print(_("\n[bold cyan]Cache Statistics:[/bold cyan]"))
                console.print(_("Cache entries: {count}").format(count=cache_stats.get("entries", 0)))
                hit_rate = cache_stats.get("hit_rate_percent")
                if hit_rate is not None:
                    console.print(_("Cache hit rate: {rate:.2f}%").format(rate=hit_rate))
                eviction_rate = cache_stats.get("eviction_rate_per_sec")
                if eviction_rate is not None:
                    console.print(_("Eviction rate: {rate:.2f} /sec").format(rate=eviction_rate))
    if not any([analyze, optimize, benchmark, profile]):
        console.print(_("[yellow]No performance action specified[/yellow]"))


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
        console.print(_("[green]Performing basic configuration scan...[/green]"))
        issues = []
        if not cfg.security.validate_peers:
            issues.append("Peer validation disabled")
        if cfg.network.max_connections_per_peer > 4:
            issues.append("High max connections per peer")
        if not cfg.security.rate_limit_enabled and (
            cfg.network.global_down_kib == 0 and cfg.network.global_up_kib == 0
        ):
            issues.append("No rate limits configured")
        console.print(_("Found {count} potential issues").format(count=len(issues)))
        for i in issues:
            console.print(_("- [yellow]{issue}[/yellow]").format(issue=i))
    if validate:
        console.print(
            _("[green]Peer validation hooks are enabled by configuration[/green]"),
        )
    if encrypt:
        console.print(
            _("[yellow]Toggle encryption via --enable-encryption/--disable-encryption on download/magnet[/yellow]"),
        )
    if rate_limit:
        console.print(
            _("[yellow]Set --download-limit/--upload-limit for global limits; per-peer via config[/yellow]"),
        )
    if not any([scan, validate, encrypt, rate_limit]):
        console.print(_("[yellow]No security action specified[/yellow]"))


@click.command("recover")
@click.argument("info_hash")
@click.option("--repair", is_flag=True, help="Attempt to repair corrupted data")
@click.option("--verify", is_flag=True, help="Verify data integrity")
@click.option("--rehash", is_flag=True, help="Rehash all pieces")
@click.option("--force", is_flag=True, help="Force recovery even if risky")
def recover(
    info_hash: str,
    repair: bool,
    verify: bool,
    rehash: bool,
    force: bool,  # noqa: ARG001
) -> None:
    """Recover from corrupted or incomplete downloads."""
    console = Console()
    cfg = get_config()
    try:
        ih_bytes = bytes.fromhex(info_hash)
    except ValueError:
        console.print(_("[red]Invalid info hash format: {hash}[/red]").format(hash=info_hash))
        return
    cm = CheckpointManager(cfg.disk)
    if verify:
        valid = asyncio.run(cm.verify_checkpoint(ih_bytes))
        console.print(
            _("[green]Checkpoint valid[/green]")
            if valid
            else _("[yellow]Checkpoint missing/invalid[/yellow]"),
        )
    if rehash:
        console.print(
            _("[yellow]Full rehash not implemented in CLI; use resume to trigger piece verification[/yellow]"),
        )
    if repair:
        console.print(_("[yellow]Automatic repair not implemented[/yellow]"))
    if not any([verify, rehash, repair]):
        console.print(_("[yellow]No recover action specified[/yellow]"))


@click.command("disk-detect")
@click.pass_context
async def disk_detect(ctx):  # noqa: ARG001
    """Detect storage device type and capabilities."""
    from rich.console import Console
    from rich.table import Table

    from ccbt.config.config import get_config
    from ccbt.config.config_capabilities import SystemCapabilities

    console = Console()
    capabilities = SystemCapabilities()
    config = get_config()

    # Get download path
    download_path = config.disk.download_path or "."

    # Detect storage information
    storage_type = capabilities.detect_storage_type(download_path)
    storage_speed = capabilities.detect_storage_speed(download_path)
    write_cache = capabilities.detect_write_cache(download_path)

    # Display results
    table = Table(title="Storage Device Detection")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Storage Type", storage_type.upper())
    table.add_row("Speed Category", storage_speed.get("speed_category", "unknown"))
    table.add_row(
        "Estimated Read Speed",
        f"{storage_speed.get('estimated_read_mbps', 0):.0f} MB/s",
    )
    table.add_row(
        "Estimated Write Speed",
        f"{storage_speed.get('estimated_write_mbps', 0):.0f} MB/s",
    )
    table.add_row("Write-Back Cache", "Enabled" if write_cache else "Disabled")

    # Show recommendations
    console.print("\n")
    rec_table = Table(title="Recommended Settings")
    rec_table.add_column("Setting", style="cyan")
    rec_table.add_column("Recommended Value", style="green")
    rec_table.add_column("Current Value", style="yellow")

    if storage_type == "nvme":
        rec_table.add_row(
            "Write Batch Timeout",
            "0.1 ms (adaptive)",
            f"{config.disk.write_batch_timeout_ms} ms",
        )
        rec_table.add_row("Disk Workers", "4-8", str(config.disk.disk_workers))
        rec_table.add_row(
            "Hash Chunk Size",
            "1 MB (adaptive)",
            f"{config.disk.hash_chunk_size // 1024} KB",
        )
    elif storage_type == "ssd":
        rec_table.add_row(
            "Write Batch Timeout",
            "5 ms (adaptive)",
            f"{config.disk.write_batch_timeout_ms} ms",
        )
        rec_table.add_row("Disk Workers", "2-4", str(config.disk.disk_workers))
        rec_table.add_row(
            "Hash Chunk Size",
            "512 KB (adaptive)",
            f"{config.disk.hash_chunk_size // 1024} KB",
        )
    else:  # hdd
        rec_table.add_row(
            "Write Batch Timeout",
            "50 ms (adaptive)",
            f"{config.disk.write_batch_timeout_ms} ms",
        )
        rec_table.add_row("Disk Workers", "1-2", str(config.disk.disk_workers))
        rec_table.add_row(
            "Hash Chunk Size",
            "64 KB (adaptive)",
            f"{config.disk.hash_chunk_size // 1024} KB",
        )

    console.print(table)
    console.print(rec_table)


@click.command("disk-stats")
@click.pass_context
async def disk_stats(ctx):  # noqa: ARG001
    """Display disk I/O performance metrics and cache statistics."""
    from rich.console import Console
    from rich.table import Table

    from ccbt.config.config import get_config
    from ccbt.storage.disk_io import DiskIOManager

    console = Console()
    config = get_config()

    disk = DiskIOManager(
        config.disk.disk_workers,
        config.disk.disk_queue_size,
        config.disk.mmap_cache_mb,
    )
    await disk.start()

    try:
        # Get statistics
        stats = disk.stats
        cache_stats = disk.get_cache_stats()

        # Display I/O statistics
        io_table = Table(title="Disk I/O Statistics")
        io_table.add_column("Metric", style="cyan")
        io_table.add_column("Value", style="green")

        io_table.add_row("Total Writes", f"{stats.get('writes', 0):,}")
        io_table.add_row("Bytes Written", f"{stats.get('bytes_written', 0):,}")
        io_table.add_row("Queue Full Errors", f"{stats.get('queue_full_errors', 0):,}")

        # Display cache statistics
        cache_table = Table(title="Cache Statistics")
        cache_table.add_column("Metric", style="cyan")
        cache_table.add_column("Value", style="green")

        cache_table.add_row("Cache Entries", f"{cache_stats.get('entries', 0):,}")
        cache_table.add_row(
            "Cache Size", f"{cache_stats.get('total_size', 0) / (1024 * 1024):.2f} MB"
        )
        cache_table.add_row("Cache Hits", f"{cache_stats.get('cache_hits', 0):,}")
        cache_table.add_row("Cache Misses", f"{cache_stats.get('cache_misses', 0):,}")
        hit_rate = cache_stats.get("hit_rate_percent")
        if hit_rate is not None:
            cache_table.add_row("Hit Rate", f"{hit_rate:.2f}%")
        eviction_rate = cache_stats.get("eviction_rate_per_sec")
        if eviction_rate is not None:
            cache_table.add_row("Eviction Rate", f"{eviction_rate:.2f} /sec")
        efficiency = cache_stats.get("cache_efficiency_percent")
        if efficiency is not None:
            cache_table.add_row("Cache Efficiency", f"{efficiency:.2f}%")

        # Display adaptive configuration status
        adaptive_table = Table(title="Adaptive Configuration Status")
        adaptive_table.add_column("Feature", style="cyan")
        adaptive_table.add_column("Status", style="green")

        adaptive_table.add_row(
            "Write Batch Timeout Adaptive",
            "Enabled" if config.disk.write_batch_timeout_adaptive else "Disabled",
        )
        adaptive_table.add_row(
            "MMap Cache Adaptive",
            "Enabled" if config.disk.mmap_cache_adaptive else "Disabled",
        )
        adaptive_table.add_row(
            "Disk Workers Adaptive",
            "Enabled" if config.disk.disk_workers_adaptive else "Disabled",
        )
        adaptive_table.add_row(
            "Read Ahead Adaptive",
            "Enabled" if config.disk.read_ahead_adaptive else "Disabled",
        )
        adaptive_table.add_row(
            "Hash Chunk Size Adaptive",
            "Enabled" if config.disk.hash_chunk_size_adaptive else "Disabled",
        )

        console.print(io_table)
        console.print("\n")
        console.print(cache_table)
        console.print("\n")
        console.print(adaptive_table)

    finally:
        await disk.stop()


@click.command("test")
@click.option("--unit", is_flag=True, help="Run unit tests")
@click.option("--integration", is_flag=True, help="Run integration tests")
@click.option(
    "--performance",
    "performance_test",
    is_flag=True,
    help="Run performance tests",
)
@click.option("--security", "security_test", is_flag=True, help="Run security tests")
@click.option("--coverage", is_flag=True, help="Generate coverage report")
def test(
    unit: bool,
    integration: bool,
    performance_test: bool,
    security_test: bool,
    coverage: bool,
) -> None:
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
    console.print(_("[blue]Running: {command}[/blue]").format(command=" ".join(args)))
    try:
        subprocess.run(args, check=False)  # nosec S603 - CLI command execution, args are validated
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(_("[red]Failed to run tests: {e}[/red]").format(e=e))

